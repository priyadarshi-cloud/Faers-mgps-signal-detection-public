"""
Contextual Feature Engineering and Representation Engine.
Extracts case-level clinical, demographic, co-medication, and reporting dynamics
and aggregates them to drug-ADR candidate association vectors.

METHODOLOGICAL FIREWALL:
- Model A: Purely contextual features. ZERO contingency counts (A, B, C, D) and ZERO PRR/ROR.
- Model B: Model A + contingency cell counts (A, B, C, D) + baseline disproportionality metrics (PRR, ROR).
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


class FeatureExtractor:
    """
    Extracts multi-dimensional contextual features for candidate drug-ADR pairs.
    """

    @staticmethod
    def parse_age_to_years(age_val, age_cod_val) -> Optional[float]:
        """Convert heterogeneous FAERS age/age_cod representations to standardized years."""
        try:
            if pd.isna(age_val) or pd.isna(age_cod_val):
                return None
            val = float(str(age_val).strip())
            unit = str(age_cod_val).strip().upper()

            if unit in ["YR", "YEAR", "YEARS", "Y"]:
                years = val
            elif unit in ["MON", "MO", "MONTH", "MONTHS"]:
                years = val / 12.0
            elif unit in ["WK", "WEEK", "WEEKS", "W"]:
                years = val / 52.0
            elif unit in ["DY", "DAY", "DAYS", "D"]:
                years = val / 365.25
            elif unit in ["DEC", "DECADE", "DECADES"]:
                years = val * 10.0
            elif unit in ["HR", "HOUR", "HOURS"]:
                years = val / 8760.0
            else:
                return None

            # Plausibility check (0 to 125 years)
            if 0.0 <= years <= 125.0:
                return years
            return None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def parse_age_series_vectorized(age_series: pd.Series, age_cod_series: pd.Series) -> pd.Series:
        """Vectorized conversion of heterogeneous FAERS age/age_cod series to standardized years."""
        val = pd.to_numeric(age_series, errors="coerce")
        cod = age_cod_series.fillna("").astype(str).str.strip().str.upper()
        multiplier = pd.Series(np.nan, index=val.index, dtype=float)
        multiplier[cod.isin(["YR", "YEAR", "YEARS", "Y"])] = 1.0
        multiplier[cod.isin(["MON", "MO", "MONTH", "MONTHS"])] = 1.0 / 12.0
        multiplier[cod.isin(["WK", "WEEK", "WEEKS", "W"])] = 1.0 / 52.0
        multiplier[cod.isin(["DY", "DAY", "DAYS", "D"])] = 1.0 / 365.25
        multiplier[cod.isin(["DEC", "DECADE", "DECADES"])] = 10.0
        multiplier[cod.isin(["HR", "HOUR", "HOURS"])] = 1.0 / 8760.0
        years = val * multiplier
        return years.where((years >= 0.0) & (years <= 125.0), np.nan)

    def extract_features(
        self,
        case_pairs_df: pd.DataFrame,
        drug_df: pd.DataFrame,
        outc_df: Optional[pd.DataFrame] = None,
        rpsr_df: Optional[pd.DataFrame] = None,
        disproportionality_df: Optional[pd.DataFrame] = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Extract Model A (contextual) and Model B (extended) feature sets for candidate pairs.

        Args:
            case_pairs_df: Detailed report-level pairs with demo attributes attached.
            drug_df: Raw or processed DRUG table for case-level co-medication counts.
            outc_df: OUTC table for clinical outcome seriousness flags.
            rpsr_df: RPSR table for reporter source qualification.
            disproportionality_df: Baseline disproportionality output (A, B, C, D, PRR, ROR).

        Returns:
            Tuple of (model_a_df, model_b_df), both indexed by (canonical_drug, canonical_pt).
        """
        pairs = case_pairs_df

        # If candidate pairs filter is provided, filter pairs to candidate pairs only
        if disproportionality_df is not None and not disproportionality_df.empty:
            valid_keys_df = disproportionality_df[["canonical_drug", "canonical_pt"]].drop_duplicates()
            pairs = pd.merge(pairs, valid_keys_df, on=["canonical_drug", "canonical_pt"], how="inner")

        # Convert group-key columns to category dtype so the groupby uses only
        # the observed (drug, pt) combinations rather than the full Cartesian
        # product of all unique drugs x all unique PTs, which can exhaust memory.
        pairs = pairs.copy()
        pairs["canonical_drug"] = pairs["canonical_drug"].astype("category")
        pairs["canonical_pt"] = pairs["canonical_pt"].astype("category")

        # 1. Parse standardized age (vectorized)
        if "age" in pairs.columns and "age_cod" in pairs.columns:
            age_years = self.parse_age_series_vectorized(pairs["age"], pairs["age_cod"])
        else:
            age_years = pd.Series(np.nan, index=pairs.index)

        # 2. Case-level co-medication metrics from DRUG table
        drug_counts = drug_df.groupby("caseid")["primaryid"].count().to_dict()
        total_drugs = pairs["caseid"].map(drug_counts).fillna(1).astype(float)
        is_monotherapy = (total_drugs <= 1).astype(float)
        concomitant_drug_count = (total_drugs - 1).clip(lower=0).astype(float)

        # 3. Outcome seriousness flags from OUTC table
        if outc_df is not None and not outc_df.empty:
            outc_clean = outc_df.copy()
            outc_clean["outc_cod"] = outc_clean["outc_cod"].fillna("").astype(str).str.strip().str.upper()

            death_cases = set(outc_clean[outc_clean["outc_cod"] == "DE"]["caseid"].unique())
            lt_cases = set(outc_clean[outc_clean["outc_cod"] == "LT"]["caseid"].unique())
            ho_cases = set(outc_clean[outc_clean["outc_cod"] == "HO"]["caseid"].unique())
            ds_cases = set(outc_clean[outc_clean["outc_cod"] == "DS"]["caseid"].unique())
            any_serious_cases = set(outc_clean[outc_clean["outc_cod"].isin(["DE", "LT", "HO", "DS", "CA", "RI"])]["caseid"].unique())

            is_death = pairs["caseid"].isin(death_cases).astype(float)
            is_life_threatening = pairs["caseid"].isin(lt_cases).astype(float)
            is_hospitalization = pairs["caseid"].isin(ho_cases).astype(float)
            is_disability = pairs["caseid"].isin(ds_cases).astype(float)
            is_serious = pairs["caseid"].isin(any_serious_cases).astype(float)
        else:
            is_death = pd.Series(0.0, index=pairs.index)
            is_life_threatening = pd.Series(0.0, index=pairs.index)
            is_hospitalization = pd.Series(0.0, index=pairs.index)
            is_disability = pd.Series(0.0, index=pairs.index)
            is_serious = pd.Series(0.0, index=pairs.index)

        # 4. Reporter qualification from occp_cod / rpsr_df
        hp_cases = set()
        csm_cases = set()
        if rpsr_df is not None and not rpsr_df.empty:
            rpsr_clean = rpsr_df.copy()
            rpsr_clean["rpsr_cod"] = rpsr_clean["rpsr_cod"].fillna("").astype(str).str.strip().str.upper()
            hp_cases.update(rpsr_clean[rpsr_clean["rpsr_cod"] == "HP"]["caseid"].unique())
            csm_cases.update(rpsr_clean[rpsr_clean["rpsr_cod"] == "CSM"]["caseid"].unique())

        hp_occupations = {"MD", "PH", "HP", "RN", "LW", "PHYSICIAN", "PHARMACIST", "md", "ph", "hp", "rn", "lw", "physician", "pharmacist"}
        csm_occupations = {"CN", "CSM", "CONSUMER", "cn", "csm", "consumer"}

        if "occp_cod" in pairs.columns:
            occp_s = pairs["occp_cod"].astype(str)
            is_hp_reported = (pairs["caseid"].isin(hp_cases) | occp_s.isin(hp_occupations)).astype(float)
            is_csm_reported = (pairs["caseid"].isin(csm_cases) | occp_s.isin(csm_occupations)).astype(float)
        else:
            is_hp_reported = pairs["caseid"].isin(hp_cases).astype(float)
            is_csm_reported = pairs["caseid"].isin(csm_cases).astype(float)

        # 5. Sex flags
        if "sex" in pairs.columns:
            sex_s = pairs["sex"].astype(str)
            is_female = sex_s.isin(["F", "FEMALE", "f", "female"]).astype(float)
            is_male = sex_s.isin(["M", "MALE", "m", "male"]).astype(float)
        else:
            is_female = pd.Series(0.0, index=pairs.index)
            is_male = pd.Series(0.0, index=pairs.index)

        # 6. Primary vs Secondary suspect
        if "role_cod" in pairs.columns:
            role_s = pairs["role_cod"].astype(str)
            is_secondary_suspect = role_s.isin(["SS", "ss"]).astype(float)
        else:
            is_secondary_suspect = pd.Series(0.0, index=pairs.index)

        # 7. Build aggregation DataFrame with compact dtypes
        df_for_agg = pd.DataFrame({
            "canonical_drug": pairs["canonical_drug"],
            "canonical_pt": pairs["canonical_pt"],
            "age_years": age_years,
            "is_age_missing": age_years.isna().astype(float),
            "is_female": is_female,
            "is_male": is_male,
            "is_death": is_death,
            "is_life_threatening": is_life_threatening,
            "is_hospitalization": is_hospitalization,
            "is_disability": is_disability,
            "is_serious": is_serious,
            "is_hp_reported": is_hp_reported,
            "is_csm_reported": is_csm_reported,
            "is_monotherapy": is_monotherapy,
            "concomitant_drug_count": concomitant_drug_count,
            "is_secondary_suspect": is_secondary_suspect
        })

        agg_dict = {
            "age_years": ["mean", "median", "std"],
            "is_age_missing": "mean",
            "is_female": "mean",
            "is_male": "mean",
            "is_death": "mean",
            "is_life_threatening": "mean",
            "is_hospitalization": "mean",
            "is_disability": "mean",
            "is_serious": "mean",
            "is_hp_reported": "mean",
            "is_csm_reported": "mean",
            "is_monotherapy": "mean",
            "concomitant_drug_count": "mean",
            "is_secondary_suspect": "mean"
        }

        # observed=True is required when groupby keys are categorical; it ensures only
        # actually-present (drug, pt) pairs are emitted, not the full Cartesian grid.
        grouped = df_for_agg.groupby(
            ["canonical_drug", "canonical_pt"], as_index=False, observed=True
        ).agg(agg_dict)
        # Flatten multiindex columns
        grouped.columns = [
            "canonical_drug", "canonical_pt",
            "mean_age", "median_age", "age_std",
            "age_missing_ratio", "female_ratio", "male_ratio",
            "death_ratio", "life_threatening_ratio", "hospitalization_ratio",
            "disability_ratio", "serious_outcome_ratio",
            "hp_reporter_ratio", "csm_reporter_ratio",
            "monotherapy_ratio", "mean_concomitant_count", "secondary_suspect_ratio"
        ]
        model_a_df = grouped

        # Model B is Model A + contingency metrics (if provided)
        if disproportionality_df is not None and not disproportionality_df.empty:
            model_b_df = pd.merge(
                model_a_df,
                disproportionality_df[[
                    "canonical_drug", "canonical_pt",
                    "a", "b", "c", "d",
                    "prr", "prr_chi2", "ror", "ror_lower_95", "ror_upper_95"
                ]],
                on=["canonical_drug", "canonical_pt"],
                how="left"
            )
        else:
            model_b_df = model_a_df.copy()

        return model_a_df, model_b_df
