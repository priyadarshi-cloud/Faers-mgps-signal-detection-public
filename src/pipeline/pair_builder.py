"""
Drug-ADR Candidate Pair Construction Engine.
Constructs observational drug-adverse event pairs from deduplicated FAERS cases.
Preserves drug role distinctions (PS, SS vs C, I), normalization categories,
and case-level contextual metadata.
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd
from src.preprocessing.drug_normalizer import DrugNormalizer
from src.preprocessing.reaction_normalizer import ReactionNormalizer


class PairBuilder:
    """
    Constructs candidate drug-ADR association pairs from cleaned FAERS tables.
    Adheres strictly to the methodological requirement:
    - Primary Suspect (PS) and Secondary Suspect (SS) form candidate pairs.
    - Concomitant (C) and Interacting (I) are captured as contextual background.
    - Normalization status (NORMALIZED, AMBIGUOUS, UNRESOLVED, UNKNOWN) is strictly tracked.
    """

    def __init__(self, drug_normalizer: Optional[DrugNormalizer] = None):
        self.drug_normalizer = drug_normalizer or DrugNormalizer()
        self.reaction_normalizer = ReactionNormalizer()

    def process_drugs(self, drug_df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize drug records and classify roles and normalization status.
        """
        df = drug_df.copy()

        # Standardize role_cod
        if "role_cod" not in df.columns:
            df["role_cod"] = "UNKNOWN"
        else:
            df["role_cod"] = df["role_cod"].fillna("UNKNOWN").astype(str).str.strip().str.upper()

        # Classify suspect vs co-medication
        df["is_suspect"] = df["role_cod"].isin(["PS", "SS"])
        df["is_primary_suspect"] = df["role_cod"] == "PS"
        df["is_secondary_suspect"] = df["role_cod"] == "SS"
        df["is_concomitant"] = df["role_cod"].isin(["C", "I"])

        # Normalize drug names via unique combinations and merge
        has_prod_ai = "prod_ai" in df.columns
        dname_clean = df["drugname"].fillna("").astype(str).str.strip()
        df["_dname_clean"] = dname_clean

        if has_prod_ai:
            pai_clean = df["prod_ai"].fillna("").astype(str).str.strip()
            df["_pai_clean"] = pai_clean
            unique_combos = df[["_dname_clean", "_pai_clean"]].drop_duplicates().copy()
            unique_combos["canonical_drug"] = [
                self.drug_normalizer.normalize(drugname=r["_dname_clean"], prod_ai=r["_pai_clean"])
                for _, r in unique_combos.iterrows()
            ]
            unique_combos["norm_status"] = [
                self.drug_normalizer.get_normalization_status(drugname=r["_dname_clean"], prod_ai=r["_pai_clean"])
                for _, r in unique_combos.iterrows()
            ]
            df = pd.merge(df, unique_combos, on=["_dname_clean", "_pai_clean"], how="left")
            df = df.drop(columns=["_dname_clean", "_pai_clean"])
        else:
            unique_combos = df[["_dname_clean"]].drop_duplicates().copy()
            unique_combos["canonical_drug"] = [
                self.drug_normalizer.normalize(drugname=r["_dname_clean"], prod_ai=None)
                for _, r in unique_combos.iterrows()
            ]
            unique_combos["norm_status"] = [
                self.drug_normalizer.get_normalization_status(drugname=r["_dname_clean"], prod_ai=None)
                for _, r in unique_combos.iterrows()
            ]
            df = pd.merge(df, unique_combos, on=["_dname_clean"], how="left")
            df = df.drop(columns=["_dname_clean"])

        return df

    def process_reactions(self, reac_df: pd.DataFrame) -> pd.DataFrame:
        """
        Standardize adverse reaction records using MedDRA PT normalization.
        """
        df = reac_df.copy()
        if "pt" not in df.columns:
            df["canonical_pt"] = "UNKNOWN"
        else:
            unique_pts = df["pt"].dropna().unique()
            pt_map = {pt: self.reaction_normalizer.normalize_pt(pt) for pt in unique_pts}
            df["canonical_pt"] = df["pt"].map(pt_map).fillna("UNKNOWN")
        return df

    def build_case_pairs(
        self,
        demo_df: pd.DataFrame,
        drug_df: pd.DataFrame,
        reac_df: pd.DataFrame,
        only_normalized_drugs: bool = True,
        only_suspect_drugs: bool = True
    ) -> pd.DataFrame:
        """
        Construct report-level drug-ADR candidate associations.
        Merges demographics, suspect drugs, and reported adverse events on primaryid/caseid.

        Args:
            demo_df: Deduplicated and temporally anchored demographics table.
            drug_df: Normalized drug table.
            reac_df: Normalized reaction table.
            only_normalized_drugs: If True, restricts candidate pairs to canonical normalized ingredients.
            only_suspect_drugs: If True, restricts candidate pairs to PS and SS roles.

        Returns:
            DataFrame where each row is a (caseid, canonical_drug, canonical_pt) occurrence
            with demographic and contextual attributes.
        """
        # Step 1: Filter drugs based on configuration
        d_df = drug_df.copy()
        if only_suspect_drugs:
            d_df = d_df[d_df["is_suspect"]].copy()

        if only_normalized_drugs:
            d_df = d_df[d_df["norm_status"] == "NORMALIZED"].copy()

        # Step 2: Filter reactions (remove empty / unknown PTs)
        r_df = reac_df[reac_df["canonical_pt"] != "UNKNOWN"].copy()

        # Step 3: Inner merge suspect drugs with reactions on primaryid
        pairs = pd.merge(
            d_df[["primaryid", "caseid", "canonical_drug", "role_cod", "norm_status"]],
            r_df[["primaryid", "canonical_pt"]],
            on="primaryid",
            how="inner"
        )

        # Step 3b: Deterministic role-code prioritization
        # Methodological rule: When multiple role codes exist for the same drug ingredient
        # in the same report version, prioritize Primary Suspect (PS) over Secondary Suspect (SS),
        # followed by Concomitant (C) and Interacting (I).
        role_priority_map = {"PS": 1, "SS": 2, "C": 3, "I": 4}
        pairs["_role_priority"] = (
            pairs["role_cod"].astype(str).str.strip().str.upper().map(role_priority_map).fillna(99)
        )
        pairs = pairs.sort_values(
            by=["primaryid", "canonical_drug", "canonical_pt", "_role_priority"],
            ascending=[True, True, True, True]
        )

        # Deduplicate multiple identical (primaryid, caseid, canonical_drug, canonical_pt) within the same report
        pairs = pairs.drop_duplicates(
            subset=["primaryid", "caseid", "canonical_drug", "canonical_pt"],
            keep="first"
        )
        pairs = pairs.drop(columns=["_role_priority"])

        # Step 4: Attach demographic metadata via version-safe join
        # Ensure join keys link using BOTH primaryid and caseid to prevent cross-version leakage
        demo_cols = ["primaryid", "caseid"]
        for opt_col in ["init_fda_dt", "fda_dt", "age", "age_cod", "sex", "occp_cod"]:
            if opt_col in demo_df.columns:
                demo_cols.append(opt_col)

        demo_sub = demo_df[demo_cols].drop_duplicates(subset=["primaryid", "caseid"])

        join_keys = (
            ["primaryid", "caseid"]
            if ("primaryid" in pairs.columns and "primaryid" in demo_sub.columns)
            else ["caseid"]
        )
        pairs = pd.merge(pairs, demo_sub, on=join_keys, how="inner")

        return pairs
