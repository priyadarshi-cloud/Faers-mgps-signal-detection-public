"""
FAERS Ingestion Engine.
Parses raw dollar-sign ($) delimited FAERS ASCII quarterly tables.
Reconciles cross-era schema shifts (e.g., gndr_cod -> sex, prod_ai presence).
Filters deleted cases via DeletedCaseManager.
"""

import os
import glob
from typing import Optional, Dict
import pandas as pd
from src.preprocessing.deleted_cases import DeletedCaseManager


class FAERSQuarterLoader:
    """Loads and standardizes a single FAERS quarterly data extract."""

    def __init__(self, quarter_dir: str, deleted_manager: Optional[DeletedCaseManager] = None):
        self.quarter_dir = quarter_dir
        self.deleted_manager = deleted_manager

        # Locate ascii directory
        ascii_candidate = os.path.join(quarter_dir, "ascii")
        self.data_dir = ascii_candidate if os.path.exists(ascii_candidate) else quarter_dir

    def _find_file(self, prefix: str) -> str:
        matches = glob.glob(os.path.join(self.data_dir, f"{prefix}*.txt"))
        if not matches:
            matches = glob.glob(os.path.join(self.data_dir, f"{prefix.lower()}*.txt"))
        if not matches:
            raise FileNotFoundError(f"No file matching prefix '{prefix}' in {self.data_dir}")
        return matches[0]

    def load_demo(self, filter_deleted: bool = True) -> pd.DataFrame:
        """Load DEMO table, normalizing sex column and ID data types."""
        fpath = self._find_file("DEMO")
        df = pd.read_csv(fpath, sep="$", encoding="latin-1", low_memory=False, dtype=str)
        df.columns = [c.lower() for c in df.columns]

        # Reconcile gndr_cod -> sex
        if "gndr_cod" in df.columns and "sex" not in df.columns:
            df = df.rename(columns={"gndr_cod": "sex"})

        # Clean IDs
        df["primaryid"] = df["primaryid"].astype(str).str.strip()
        df["caseid"] = df["caseid"].astype(str).str.strip()

        # Clean initial date
        if "init_fda_dt" in df.columns:
            df["init_fda_dt"] = df["init_fda_dt"].astype(str).str.strip()
        if "fda_dt" in df.columns:
            df["fda_dt"] = df["fda_dt"].astype(str).str.strip()

        # Filter deleted cases
        if filter_deleted and self.deleted_manager:
            initial_len = len(df)
            mask = ~df["caseid"].isin(self.deleted_manager.deleted_cases)
            df = df[mask].copy()
            purged = initial_len - len(df)
            if purged > 0:
                print(f"[DEMO] Purged {purged} deleted/retracted cases from {os.path.basename(fpath)}")

        return df

    def load_drug(self, valid_primaryids: Optional[set] = None) -> pd.DataFrame:
        """Load DRUG table, standardizing role_cod and drug names."""
        fpath = self._find_file("DRUG")
        df = pd.read_csv(fpath, sep="$", encoding="latin-1", low_memory=False, dtype=str)
        df.columns = [c.lower() for c in df.columns]

        df["primaryid"] = df["primaryid"].astype(str).str.strip()
        df["caseid"] = df["caseid"].astype(str).str.strip()
        if "role_cod" in df.columns:
            df["role_cod"] = df["role_cod"].astype(str).str.strip().str.upper()

        if valid_primaryids is not None:
            df = df[df["primaryid"].isin(valid_primaryids)].copy()

        return df

    def load_reac(self, valid_primaryids: Optional[set] = None) -> pd.DataFrame:
        """Load REAC table, standardizing MedDRA Preferred Terms (pt)."""
        fpath = self._find_file("REAC")
        df = pd.read_csv(fpath, sep="$", encoding="latin-1", low_memory=False, dtype=str)
        df.columns = [c.lower() for c in df.columns]

        df["primaryid"] = df["primaryid"].astype(str).str.strip()
        df["caseid"] = df["caseid"].astype(str).str.strip()
        if "pt" in df.columns:
            df["pt"] = df["pt"].astype(str).str.strip()

        if valid_primaryids is not None:
            df = df[df["primaryid"].isin(valid_primaryids)].copy()

        return df

    def load_outc(self, valid_primaryids: Optional[set] = None) -> pd.DataFrame:
        """Load OUTC table (patient outcome seriousness codes)."""
        fpath = self._find_file("OUTC")
        df = pd.read_csv(fpath, sep="$", encoding="latin-1", low_memory=False, dtype=str)
        df.columns = [c.lower() for c in df.columns]

        df["primaryid"] = df["primaryid"].astype(str).str.strip()
        df["caseid"] = df["caseid"].astype(str).str.strip()
        if "outc_cod" in df.columns:
            df["outc_cod"] = df["outc_cod"].astype(str).str.strip().str.upper()

        if valid_primaryids is not None:
            df = df[df["primaryid"].isin(valid_primaryids)].copy()

        return df

    def load_rpsr(self, valid_primaryids: Optional[set] = None) -> pd.DataFrame:
        """Load RPSR table (report sources, e.g., HP, CSM, SDY)."""
        fpath = self._find_file("RPSR")
        df = pd.read_csv(fpath, sep="$", encoding="latin-1", low_memory=False, dtype=str)
        df.columns = [c.lower() for c in df.columns]

        df["primaryid"] = df["primaryid"].astype(str).str.strip()
        df["caseid"] = df["caseid"].astype(str).str.strip()
        if "rpsr_cod" in df.columns:
            df["rpsr_cod"] = df["rpsr_cod"].astype(str).str.strip().str.upper()

        if valid_primaryids is not None:
            df = df[df["primaryid"].isin(valid_primaryids)].copy()

        return df

    def load_indi(self, valid_primaryids: Optional[set] = None) -> pd.DataFrame:
        """Load INDI table (drug indications)."""
        fpath = self._find_file("INDI")
        df = pd.read_csv(fpath, sep="$", encoding="latin-1", low_memory=False, dtype=str)
        df.columns = [c.lower() for c in df.columns]

        df["primaryid"] = df["primaryid"].astype(str).str.strip()
        df["caseid"] = df["caseid"].astype(str).str.strip()
        if "indi_pt" in df.columns:
            df["indi_pt"] = df["indi_pt"].astype(str).str.strip()

        if valid_primaryids is not None:
            df = df[df["primaryid"].isin(valid_primaryids)].copy()

        return df

    def load_ther(self, valid_primaryids: Optional[set] = None) -> pd.DataFrame:
        """Load THER table (drug therapy start/end dates and durations)."""
        fpath = self._find_file("THER")
        df = pd.read_csv(fpath, sep="$", encoding="latin-1", low_memory=False, dtype=str)
        df.columns = [c.lower() for c in df.columns]

        df["primaryid"] = df["primaryid"].astype(str).str.strip()
        df["caseid"] = df["caseid"].astype(str).str.strip()

        if valid_primaryids is not None:
            df = df[df["primaryid"].isin(valid_primaryids)].copy()

        return df
