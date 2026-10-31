"""
OMOP Ground Truth Reference Set Ingestion and Harmonization Engine.
Parses OHDSI omopReferenceSet, normalizes drug concepts to canonical ingredients,
and maps clinical health outcomes of interest (HOIs) to MedDRA Preferred Terms.
Strictly implements non-binary status (absence = UNLISTED_UNKNOWN).
"""

import os
from typing import Dict, List, Optional, Tuple
import pandas as pd
from src.preprocessing.drug_normalizer import DrugNormalizer


class OMOPReferenceManager:
    """Manages the OHDSI OMOP Ground Truth Reference Set."""

    # Published OHDSI Health Outcomes of Interest (HOI) to standardized phenotype keys
    HOI_MAPPING = {
        500000301: "acute_liver_injury",
        500000401: "acute_renal_failure",
        500000801: "acute_myocardial_infarction",
        500001003: "upper_gi_bleeding"
    }

    # Established OHDSI / Narrow SMQ core MedDRA Preferred Terms for each HOI
    PHENOTYPE_MEDDRA_PTS = {
        "acute_liver_injury": [
            "acute hepatic failure", "hepatic failure", "hepatitis acute", "hepatotoxicity",
            "jaundice", "subacute hepatic failure", "hepatic necrosis", "drug-induced liver injury",
            "liver injury"
        ],
        "acute_renal_failure": [
            "acute kidney injury", "renal failure acute", "renal tubular necrosis", "anuria",
            "nephritis acute", "subacute renal failure"
        ],
        "acute_myocardial_infarction": [
            "acute myocardial infarction", "myocardial infarction", "silent myocardial infarction",
            "myocardial infarction recurrent"
        ],
        "upper_gi_bleeding": [
            "upper gastrointestinal haemorrhage", "gastric ulcer haemorrhage", "duodenal ulcer haemorrhage",
            "haematemesis", "melaena", "peptic ulcer haemorrhage", "gastrointestinal haemorrhage"
        ]
    }

    def __init__(self, omop_csv_path: str):
        if not os.path.exists(omop_csv_path):
            raise FileNotFoundError(f"OMOP CSV not found at {omop_csv_path}")
        self.df = pd.read_csv(omop_csv_path)
        self.drug_normalizer = DrugNormalizer()
        self._validate_and_harmonize()

    def _validate_and_harmonize(self):
        """Validate exact OHDSI row counts and harmonize drug and outcome concepts."""
        assert len(self.df) == 399, f"Expected 399 rows, found {len(self.df)}"
        assert self.df["groundTruth"].value_counts().to_dict() == {0: 234, 1: 165}, \
            f"Unexpected ground truth distribution: {self.df['groundTruth'].value_counts().to_dict()}"

        # Standardize phenotype key
        self.df["phenotype_key"] = self.df["outcomeId"].map(self.HOI_MAPPING)
        assert self.df["phenotype_key"].notna().all(), "Some outcomeIds could not be mapped to HOI keys!"

        # Normalize exposure names to canonical ingredients
        self.df["normalized_drug"] = self.df["exposureName"].apply(
            lambda name: self.drug_normalizer.normalize(drugname=name)
        )

        # Build fast lookup dictionary: (normalized_drug, phenotype_key) -> groundTruth (0 or 1)
        self.lookup: Dict[Tuple[str, str], int] = {}
        for _, row in self.df.iterrows():
            key = (row["normalized_drug"], row["phenotype_key"])
            self.lookup[key] = int(row["groundTruth"])

    def get_reference_status(self, normalized_drug: str, phenotype_key: str) -> str:
        """
        Return the exact OMOP reference status for a drug-outcome pair.
        Never assumes absence is negative.
        Returns: 'POSITIVE_CONTROL', 'NEGATIVE_CONTROL', or 'UNLISTED_UNKNOWN'.
        """
        key = (normalized_drug.lower(), phenotype_key.lower())
        if key in self.lookup:
            return "POSITIVE_CONTROL" if self.lookup[key] == 1 else "NEGATIVE_CONTROL"
        return "UNLISTED_UNKNOWN"

    def is_pt_in_phenotype(self, pt: str, phenotype_key: str) -> bool:
        """Check if a specific MedDRA PT matches the clinical definition of an HOI."""
        clean_pt = pt.strip().lower()
        allowed_pts = self.PHENOTYPE_MEDDRA_PTS.get(phenotype_key.lower(), [])
        return clean_pt in allowed_pts

    def get_pt_phenotype_matches(self, pt: str) -> List[str]:
        """Return all matching HOI phenotype keys for a given MedDRA PT."""
        clean_pt = pt.strip().lower()
        matches = []
        for hoi_key, pt_list in self.PHENOTYPE_MEDDRA_PTS.items():
            if clean_pt in pt_list:
                matches.append(hoi_key)
        return matches
