"""
Phase 3A.2 — Historical Snapshot Builder.

Implements the corrected, fully-auditable best-version-as-of-cutoff selection
for the FAERS continuous corpus (2014Q1 – 2023Q4).

Temporal contract
-----------------
primaryid   : Unique identifier for a single report/version submission.
              Every row in DEMO has exactly one primaryid.
caseid      : Identifier that links all versions of the same underlying case.
              Multiple primaryid values may share the same caseid (follow-ups).
init_fda_dt : Date the ORIGINAL initial report was first received by FDA.
              Used to anchor a case to the correct temporal partition.
              Format: YYYYMMDD string.
fda_dt      : Date THIS version (primaryid) was received by FDA.
              Used to determine whether a version was available as of the cutoff.
              Format: YYYYMMDD string.
caseversion : Numeric version counter incremented with each follow-up submission.
              Used as secondary sort key for tie-breaking.
Deleted IDs : Listed in per-quarter DELETED text files and in AllDeletedCases.txt.
              Each token on a $ -delimited line; first token is the caseid.
              Applied to caseid (not primaryid).

Best-version selection rule (cutoff = 2018-12-31, format YYYYMMDD = '20181231')
----------------------------------------------------------------------------------
1. Parse init_fda_dt and fda_dt into true date values; quarantine rows where
   either date is absent, malformed, or not a valid calendar date.
2. Keep only rows where init_fda_dt <= cutoff (case first appeared by cutoff).
3. Keep only rows where fda_dt    <= cutoff (this version was available by cutoff).
4. Exclude rows whose caseid is in the cumulative deleted-case union.
5. Sort eligible rows by [caseid ASC, fda_dt ASC, caseversion ASC, primaryid ASC].
   (All ascending: most recent fda_dt is highest, take last; ties broken by
    caseversion then primaryid, both larger = more recent.)
6. For each caseid take the LAST row (highest fda_dt, then caseversion, then primaryid).
7. Annotate each selected row with: selection_reason, n_eligible_versions, source_quarter.
8. Return selected rows and a full audit frame (counts at each filtering stage).
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Optional, Tuple

import pandas as pd
import numpy as np


CUTOFF_STR = "20181231"  # canonical cutoff string for string comparison guard
CUTOFF_DATE = datetime(2018, 12, 31).date()

_VALID_8_RE = re.compile(r"^\d{8}$")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_yyyymmdd(series: pd.Series) -> Tuple[pd.Series, pd.Series]:
    """
    Parse an YYYYMMDD string series to datetime.date.

    Returns
    -------
    parsed  : pd.Series of datetime.date (NaT/NaN where invalid)
    invalid : boolean mask — True where parsing failed or value is not a valid date
    """
    s = series.astype(str).str.strip()

    # Step 1: length must be exactly 8
    length_ok = s.str.len() == 8

    # Step 2: must be all digits
    digit_ok = s.str.match(r"^\d{8}$")

    candidate_mask = length_ok & digit_ok

    # Step 3: convert to datetime where candidate
    parsed = pd.to_datetime(
        s.where(candidate_mask, other=pd.NaT),
        format="%Y%m%d",
        errors="coerce",
    )

    invalid = parsed.isna()
    return parsed, invalid


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class HistoricalSnapshotBuilder:
    """
    Builds the canonical per-case snapshot as of a specified cutoff date.

    Parameters
    ----------
    cutoff_yyyymmdd : str
        Snapshot cutoff date in YYYYMMDD format (e.g. '20181231').
    """

    def __init__(self, cutoff_yyyymmdd: str = CUTOFF_STR):
        if not re.match(r"^\d{8}$", cutoff_yyyymmdd):
            raise ValueError(f"cutoff_yyyymmdd must be 8 digits, got: {cutoff_yyyymmdd!r}")
        self.cutoff_str = cutoff_yyyymmdd
        self.cutoff_date = datetime.strptime(cutoff_yyyymmdd, "%Y%m%d").date()

    # ------------------------------------------------------------------
    def build(
        self,
        combined_demo: pd.DataFrame,
        deleted_caseids: Optional[set] = None,
    ) -> Tuple[pd.DataFrame, dict, pd.DataFrame]:
        """
        Build the historical snapshot from a combined multi-quarter DEMO frame.

        Parameters
        ----------
        combined_demo : pd.DataFrame
            Concatenated DEMO rows from all relevant quarters.
            Required columns: primaryid, caseid, init_fda_dt, fda_dt.
            Optional (used for tie-breaking): caseversion.
            Optional (kept for provenance): quarter.
        deleted_caseids : set, optional
            Cumulative set of deleted/retracted caseid strings.

        Returns
        -------
        snapshot : pd.DataFrame
            One row per caseid — the selected best version as of cutoff.
            Includes audit columns: _n_total_versions, _n_eligible_versions,
            _selection_reason.
        audit : dict
            Count-reconciliation table at each filtering stage.
        quarantine : pd.DataFrame
            Quarantined rows with missing identifiers or unparseable dates.
        """
        df = combined_demo.copy()

        # Normalise column names
        df.columns = [c.lower().strip() for c in df.columns]

        if "gndr_cod" in df.columns and "sex" not in df.columns:
            df["sex"] = df["gndr_cod"]

        # Ensure required identifier columns exist
        for col in ("primaryid", "caseid"):
            if col not in df.columns:
                raise KeyError(f"Required column '{col}' not found in combined_demo.")

        n_raw = len(df)
        audit: dict = {"n_raw_input_rows": n_raw}

        # ------------------------------------------------------------------
        # Stage 0: Identifier Quarantine (missing / null / blank IDs)
        # ------------------------------------------------------------------
        raw_caseid = df["caseid"].astype(str).str.strip()
        raw_primaryid = df["primaryid"].astype(str).str.strip()

        missing_caseid = df["caseid"].isna() | (raw_caseid == "") | (raw_caseid.str.lower().isin(["nan", "none", "<na>"]))
        missing_primaryid = df["primaryid"].isna() | (raw_primaryid == "") | (raw_primaryid.str.lower().isin(["nan", "none", "<na>"]))
        missing_id_mask = missing_caseid | missing_primaryid

        id_quarantine = df[missing_id_mask].copy()
        if len(id_quarantine) > 0:
            id_quarantine["_exclusion_reason"] = np.where(
                missing_caseid[missing_id_mask] & missing_primaryid[missing_id_mask],
                "missing_caseid_and_primaryid",
                np.where(missing_caseid[missing_id_mask], "missing_caseid", "missing_primaryid"),
            )
        else:
            id_quarantine["_exclusion_reason"] = pd.Series(dtype=str)

        n_id_quarantine = len(id_quarantine)
        df = df[~missing_id_mask].copy()
        audit["n_missing_identifier_quarantined"] = n_id_quarantine

        # Normalise cleaned ID fields to string
        df["primaryid"] = df["primaryid"].astype(str).str.strip()
        df["caseid"] = df["caseid"].astype(str).str.strip()

        # ------------------------------------------------------------------
        # Stage 0b: Deduplicate exact duplicate primaryid across quarters
        # ------------------------------------------------------------------
        n_before_dedup = len(df)
        df = df.drop_duplicates(subset=["primaryid"], keep="first")
        n_dup_primaryid = n_before_dedup - len(df)
        audit["n_duplicate_primaryid_rows_excluded"] = n_dup_primaryid
        audit["n_after_identifier_cleaning"] = len(df)

        # Add caseversion numeric if present
        if "caseversion" in df.columns:
            df["_caseversion_num"] = pd.to_numeric(df["caseversion"], errors="coerce").fillna(0)
        else:
            df["_caseversion_num"] = 0

        # Add primaryid numeric for tie-breaking
        df["_primaryid_num"] = pd.to_numeric(df["primaryid"], errors="coerce").fillna(0)

        # ------------------------------------------------------------------
        # Stage 1: Parse dates explicitly into true dates
        # ------------------------------------------------------------------
        n_curr = len(df)
        df["_init_date"], init_invalid = _parse_yyyymmdd(
            df["init_fda_dt"] if "init_fda_dt" in df.columns else pd.Series([""] * n_curr)
        )
        df["_fda_date"], fda_invalid = _parse_yyyymmdd(
            df["fda_dt"] if "fda_dt" in df.columns else pd.Series([""] * n_curr)
        )

        # Quarantine rows where either date is invalid
        date_ineligible_mask = init_invalid | fda_invalid
        date_quarantine = df[date_ineligible_mask].copy()
        if len(date_quarantine) > 0:
            date_quarantine["_exclusion_reason"] = np.where(
                init_invalid[date_ineligible_mask] & fda_invalid[date_ineligible_mask],
                "both_dates_invalid",
                np.where(init_invalid[date_ineligible_mask], "init_fda_dt_invalid", "fda_dt_invalid"),
            )
        else:
            date_quarantine["_exclusion_reason"] = pd.Series(dtype=str)

        n_date_quarantine = len(date_quarantine)
        df = df[~date_ineligible_mask].copy()
        audit["n_date_ineligible_quarantined"] = n_date_quarantine
        audit["n_after_date_parsing"] = len(df)

        # Combined quarantine frame
        quarantine = pd.concat([id_quarantine, date_quarantine], ignore_index=True)

        # ------------------------------------------------------------------
        # Stage 2: Filter — init_fda_dt <= cutoff
        # ------------------------------------------------------------------
        init_ok = df["_init_date"].dt.date <= self.cutoff_date
        n_post_init = int((~init_ok).sum())
        df = df[init_ok].copy()
        audit["n_excluded_init_after_cutoff"] = n_post_init
        audit["n_after_init_filter"] = len(df)

        # ------------------------------------------------------------------
        # Stage 3: Filter — fda_dt <= cutoff (no post-cutoff versions)
        # ------------------------------------------------------------------
        fda_ok = df["_fda_date"].dt.date <= self.cutoff_date
        n_post_fda = int((~fda_ok).sum())
        df = df[fda_ok].copy()
        audit["n_excluded_fda_after_cutoff"] = n_post_fda
        audit["n_after_fda_filter"] = len(df)

        # ------------------------------------------------------------------
        # Stage 4: Apply deletion policy with token validation
        # ------------------------------------------------------------------
        if deleted_caseids:
            # Check if corpus has predominantly numeric caseids
            sample_ids = df["caseid"].dropna().head(100)
            is_numeric_corpus = sample_ids.str.isdigit().all() if len(sample_ids) > 0 else True

            valid_deleted = set()
            invalid_deleted = set()
            for d in deleted_caseids:
                s = str(d).strip()
                if not s:
                    continue
                if is_numeric_corpus:
                    if s.isdigit():
                        valid_deleted.add(s)
                    else:
                        invalid_deleted.add(s)
                else:
                    if s.upper() in {"CASE_ID", "CASEID", "PRIMARYID", "HEADER"} or "INVALID" in s.upper():
                        invalid_deleted.add(s)
                    else:
                        valid_deleted.add(s)

            audit["n_valid_deleted_caseids"] = len(valid_deleted)
            audit["n_invalid_deletion_tokens_flagged"] = len(invalid_deleted)
            is_deleted = df["caseid"].isin(valid_deleted)
            n_deleted = int(is_deleted.sum())
            df = df[~is_deleted].copy()
        else:
            audit["n_valid_deleted_caseids"] = 0
            audit["n_invalid_deletion_tokens_flagged"] = 0
            n_deleted = 0
        audit["n_excluded_deleted"] = n_deleted
        audit["n_after_deletion_purge"] = len(df)

        # ------------------------------------------------------------------
        # Stage 5: Count eligible versions per case (before selection)
        # ------------------------------------------------------------------
        if len(df) > 0:
            eligible_counts = df.groupby("caseid")["primaryid"].transform("count")
            audit["n_eligible_unique_caseids"] = int(df["caseid"].nunique())
            audit["n_single_eligible_version_cases"] = int((eligible_counts == 1).sum() // 1)
            audit["n_multi_eligible_version_cases"] = int((df.groupby("caseid")["primaryid"].count() > 1).sum())
            df["_n_eligible_versions"] = eligible_counts
        else:
            audit["n_eligible_unique_caseids"] = 0
            audit["n_single_eligible_version_cases"] = 0
            audit["n_multi_eligible_version_cases"] = 0
            df["_n_eligible_versions"] = pd.Series(dtype=int)

        # ------------------------------------------------------------------
        # Stage 6: Deterministic sort + best-version selection
        # ------------------------------------------------------------------
        if len(df) > 0:
            df["_max_fda_date"] = df.groupby("caseid")["_fda_date"].transform("max")
            is_max_date = df["_fda_date"] == df["_max_fda_date"]
            df["_count_max_date"] = is_max_date.astype(int).groupby(df["caseid"]).transform("sum")

            v_at_max_date = df["_caseversion_num"].where(is_max_date, -1)
            df["_max_v_at_max_date"] = v_at_max_date.groupby(df["caseid"]).transform("max")
            is_max_v_at_max_date = is_max_date & (df["_caseversion_num"] == df["_max_v_at_max_date"])
            df["_count_max_v_at_max_date"] = is_max_v_at_max_date.astype(int).groupby(df["caseid"]).transform("sum")

            # Sort ASC on all keys → .last() picks the row with:
            # max fda_date, then max caseversion, then max primaryid_num
            df = df.sort_values(
                by=["caseid", "_fda_date", "_caseversion_num", "_primaryid_num"],
                ascending=[True, True, True, True],
            )

            snapshot = df.groupby("caseid", as_index=False).last()
            n_selected = len(snapshot)
            audit["n_selected_rows"] = n_selected

            # Verify: exactly one row per caseid
            dup_check = snapshot["caseid"].duplicated().sum()
            audit["duplicate_caseid_in_snapshot"] = int(dup_check)

            # Stage 7: Granular selection reason
            reasons = np.where(
                snapshot["_n_eligible_versions"] == 1,
                "only_version",
                np.where(
                    snapshot["_count_max_date"] == 1,
                    "latest_fda_dt",
                    np.where(
                        snapshot["_count_max_v_at_max_date"] == 1,
                        "tie_broken_by_caseversion",
                        "tie_broken_by_primaryid",
                    ),
                ),
            )
            snapshot["_selection_reason"] = reasons

            # Stage 8: Verify cross-boundary cases
            audit["n_cross_boundary_caseids_included"] = int(
                snapshot[snapshot["_n_eligible_versions"] > 0]["caseid"].isin(
                    df[df["_n_eligible_versions"] > 0]["caseid"]
                ).sum()
            )
        else:
            snapshot = pd.DataFrame(columns=list(df.columns) + ["_selection_reason"])
            n_selected = 0
            audit["n_selected_rows"] = 0
            audit["duplicate_caseid_in_snapshot"] = 0
            audit["n_cross_boundary_caseids_included"] = 0

        # Drop internal helper columns
        internal_cols = [c for c in snapshot.columns if c.startswith("_") and c not in (
            "_n_eligible_versions", "_selection_reason"
        )]
        snapshot = snapshot.drop(columns=internal_cols, errors="ignore")

        # ------------------------------------------------------------------
        # Audit cross-check: n_selected == n_eligible_unique_caseids
        # ------------------------------------------------------------------
        audit["audit_selected_eq_eligible_caseids"] = (
            n_selected == audit["n_eligible_unique_caseids"]
        )

        return snapshot, audit, quarantine

    # ------------------------------------------------------------------
    def null_date_audit(self, combined_demo: pd.DataFrame) -> pd.DataFrame:
        """
        Audit prevalence of null/blank/invalid init_fda_dt across all quarters.

        Returns a per-quarter summary DataFrame with columns:
        quarter, n_rows, n_null_init_fda_dt, n_invalid_init_fda_dt,
        pct_null_or_invalid.
        """
        df = combined_demo.copy()
        df.columns = [c.lower().strip() for c in df.columns]
        records = []
        for q, grp in df.groupby("quarter", sort=True):
            n = len(grp)
            _, invalid = _parse_yyyymmdd(
                grp["init_fda_dt"] if "init_fda_dt" in grp.columns
                else pd.Series([""] * n)
            )
            n_null = int(
                grp["init_fda_dt"].isna().sum() if "init_fda_dt" in grp.columns else n
            )
            n_invalid_total = int(invalid.sum())
            records.append({
                "quarter": q,
                "n_rows": n,
                "n_null_init_fda_dt": n_null,
                "n_invalid_init_fda_dt": n_invalid_total,
                "pct_null_or_invalid": round(n_invalid_total / n * 100, 4) if n > 0 else 0.0,
            })
        return pd.DataFrame(records)
