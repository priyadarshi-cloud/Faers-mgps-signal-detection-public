"""
Baseline Disproportionality Signal Detection Engine.
Calculates exact 2x2 contingency tables, Proportional Reporting Ratio (PRR),
and Reporting Odds Ratio (ROR) with 95% confidence intervals.

MANDATORY METHODOLOGICAL INVARIANT:
PRR and ROR are computed strictly as descriptive disproportionality baselines.
They MUST NEVER be used to generate machine learning training labels,
preventing circular validation.
"""

import math
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


class DisproportionalityCalculator:
    """
    Computes 2x2 contingency tables and disproportionality metrics (PRR, ROR)
    across a cohort of unique, deduplicated pharmacovigilance reports.
    """

    def __init__(self, min_case_count: int = 1):
        """
        Args:
            min_case_count: Minimum count of co-occurrences (A cell) to compute statistics for.
        """
        self.min_case_count = min_case_count

    def compute_contingency_and_metrics(
        self,
        case_pairs_df: pd.DataFrame,
        total_case_count: int
    ) -> pd.DataFrame:
        """
        Compute 2x2 contingency matrix and PRR / ROR statistics for all drug-event pairs.

        Args:
            case_pairs_df: DataFrame containing at least ['caseid', 'canonical_drug', 'canonical_pt'].
                           Must be deduplicated at (caseid, canonical_drug, canonical_pt) level.
            total_case_count: Total universe of unique deduplicated cases (N) in the temporal window.

        Returns:
            DataFrame indexed by (canonical_drug, canonical_pt) with contingency counts
            (a, b, c, d) and baseline metrics (prr, prr_chi2, ror, ror_lower_95, ror_upper_95).
        """
        df = case_pairs_df[["caseid", "canonical_drug", "canonical_pt"]].drop_duplicates()

        # Total cases N
        N = total_case_count
        if N <= 0:
            raise ValueError(f"Total case count N must be positive, got {N}")

        # A: count of unique cases for each (drug, pt)
        pair_counts = df.groupby(["canonical_drug", "canonical_pt"])["caseid"].nunique().reset_index(name="a")

        # Filter pairs below minimum threshold
        pair_counts = pair_counts[pair_counts["a"] >= self.min_case_count].copy()
        if pair_counts.empty:
            return pd.DataFrame(columns=[
                "canonical_drug", "canonical_pt", "a", "b", "c", "d",
                "prr", "prr_chi2", "prr_signal",
                "ror", "ror_se", "ror_lower_95", "ror_upper_95", "ror_signal"
            ])

        # Marginal counts
        # drug_totals: number of unique cases mentioning drug d
        drug_totals = df.groupby("canonical_drug")["caseid"].nunique().to_dict()
        # event_totals: number of unique cases mentioning event e
        event_totals = df.groupby("canonical_pt")["caseid"].nunique().to_dict()

        # Compute B, C, D
        pair_counts["drug_total"] = pair_counts["canonical_drug"].map(drug_totals)
        pair_counts["event_total"] = pair_counts["canonical_pt"].map(event_totals)

        pair_counts["b"] = pair_counts["drug_total"] - pair_counts["a"]
        pair_counts["c"] = pair_counts["event_total"] - pair_counts["a"]
        pair_counts["d"] = N - pair_counts["a"] - pair_counts["b"] - pair_counts["c"]

        # Ensure non-negative bounds
        pair_counts["b"] = pair_counts["b"].clip(lower=0)
        pair_counts["c"] = pair_counts["c"].clip(lower=0)
        pair_counts["d"] = pair_counts["d"].clip(lower=0)

        # Calculate PRR and Chi2
        pair_counts["prr"] = pair_counts.apply(
            lambda r: self._calculate_prr(r["a"], r["b"], r["c"], r["d"]), axis=1
        )
        pair_counts["prr_chi2"] = pair_counts.apply(
            lambda r: self._calculate_chi2(r["a"], r["b"], r["c"], r["d"], N), axis=1
        )
        # Evans Signal Criteria: a >= 3 and PRR >= 2 and Chi2 >= 4
        pair_counts["prr_signal"] = (
            (pair_counts["a"] >= 3) &
            (pair_counts["prr"] >= 2.0) &
            (pair_counts["prr_chi2"] >= 4.0)
        )

        # Calculate ROR and 95% Confidence Intervals
        ror_results = pair_counts.apply(
            lambda r: self._calculate_ror(r["a"], r["b"], r["c"], r["d"]), axis=1
        )
        pair_counts["ror"] = [res[0] for res in ror_results]
        pair_counts["ror_se"] = [res[1] for res in ror_results]
        pair_counts["ror_lower_95"] = [res[2] for res in ror_results]
        pair_counts["ror_upper_95"] = [res[3] for res in ror_results]

        # ROR Signal Criteria: a >= 3 and lower 95% CI > 1.0
        pair_counts["ror_signal"] = (
            (pair_counts["a"] >= 3) &
            (pair_counts["ror_lower_95"] > 1.0)
        )

        return pair_counts.drop(columns=["drug_total", "event_total"])

    @staticmethod
    def _calculate_prr(a: int, b: int, c: int, d: int) -> float:
        """
        PRR = (A / (A + B)) / (C / (C + D))
        """
        denom_drug = a + b
        denom_other = c + d
        if denom_drug <= 0 or denom_other <= 0 or c <= 0:
            return 0.0
        prop_drug = a / denom_drug
        prop_other = c / denom_other
        if prop_other <= 0:
            return 0.0
        return float(prop_drug / prop_other)

    @staticmethod
    def _calculate_chi2(a: int, b: int, c: int, d: int, N: int) -> float:
        """
        Chi-square with Yates continuity correction:
        chi2 = N * (|AD - BC| - N/2)^2 / ((A+B)(C+D)(A+C)(B+D))
        """
        denom = (a + b) * (c + d) * (a + c) * (b + d)
        if denom <= 0:
            return 0.0
        ad_bc = abs(a * d - b * c)
        yates_num = max(0.0, ad_bc - (N / 2.0))
        chi2 = (N * (yates_num ** 2)) / denom
        return float(chi2)

    @staticmethod
    def _calculate_ror(a: int, b: int, c: int, d: int) -> Tuple[float, float, float, float]:
        """
        ROR = (A * D) / (B * C)
        SE(ln ROR) = sqrt(1/A + 1/B + 1/C + 1/D)
        CI = exp(ln ROR +/- 1.96 * SE)
        """
        if a <= 0 or b <= 0 or c <= 0 or d <= 0:
            return (0.0, 0.0, 0.0, 0.0)
        try:
            ror = (a * d) / (b * c)
            se = math.sqrt((1.0 / a) + (1.0 / b) + (1.0 / c) + (1.0 / d))
            ln_ror = math.log(ror)
            lower_ci = math.exp(ln_ror - 1.96 * se)
            upper_ci = math.exp(ln_ror + 1.96 * se)
            return (float(ror), float(se), float(lower_ci), float(upper_ci))
        except (ValueError, OverflowError, ZeroDivisionError):
            return (0.0, 0.0, 0.0, 0.0)
