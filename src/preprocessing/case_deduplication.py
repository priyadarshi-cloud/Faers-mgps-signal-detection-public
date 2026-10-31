"""
Case Deduplication and Temporal Version Anchoring.
Anchors cases to initial receipt date (init_fda_dt) to eliminate forward-looking leakage.
Selects the latest version within a defined historical cutoff date.
"""

from typing import Optional
import pandas as pd


class CaseVersionManager:
    """Manages case deduplication and temporal window filtering."""

    @staticmethod
    def filter_by_initial_date(demo_df: pd.DataFrame, max_init_date: str) -> pd.DataFrame:
        """
        Filter cases strictly by initial receipt date (init_fda_dt <= max_init_date).
        max_init_date must be in YYYYMMDD format (e.g., '20181231').
        """
        clean_dates = demo_df["init_fda_dt"].astype(str).str.strip()
        # Keep only valid 8-digit dates <= max_init_date
        mask = (clean_dates.str.len() == 8) & (clean_dates <= str(max_init_date))
        return demo_df[mask].copy()

    @staticmethod
    def deduplicate_cases_to_latest_version(demo_df: pd.DataFrame, cutoff_date: Optional[str] = None) -> pd.DataFrame:
        """
        Consolidate multi-version cases under unique caseid.
        Selects the latest version (highest numeric caseversion or latest fda_dt)
        received on or before cutoff_date.
        """
        df = demo_df.copy()

        # If cutoff_date is supplied, filter out revisions received after cutoff_date
        if cutoff_date is not None:
            clean_fda_dt = df["fda_dt"].astype(str).str.strip()
            df = df[(clean_fda_dt.str.len() == 8) & (clean_fda_dt <= str(cutoff_date))].copy()

        # Convert caseversion to numeric for sorting
        df["_version_num"] = pd.to_numeric(df["caseversion"], errors="coerce").fillna(1)

        # Sort by caseid, version_num descending, fda_dt descending
        df = df.sort_values(by=["caseid", "_version_num", "fda_dt"], ascending=[True, False, False])

        # Drop duplicates keeping the highest version
        deduped = df.drop_duplicates(subset=["caseid"], keep="first").copy()
        deduped = deduped.drop(columns=["_version_num"])

        return deduped
