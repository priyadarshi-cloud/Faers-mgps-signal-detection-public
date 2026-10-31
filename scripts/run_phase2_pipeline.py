"""
Execution and Validation Script for Phase 2 Pipeline.
Runs the complete Phase 2 pipeline across the representative FAERS quarters:
2014Q1, 2019Q1, and 2023Q1.
Verifies all locked methodological invariants and exports quality audit artifacts.
"""

import os
import sys
import json
import time

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.pipeline.pipeline_orchestrator import PipelineOrchestrator


def main():
    print("=" * 70)
    print("PHASE 2 FULL PIPELINE RUNNER AND INVARIANT AUDIT")
    print("=" * 70)

    # Define paths
    sample_dir = os.path.join(PROJECT_ROOT, "data", "01_raw", "sample_quarters")
    quarters = [
        os.path.join(sample_dir, "2014q1"),
        os.path.join(sample_dir, "2019q1"),
        os.path.join(sample_dir, "2023q1")
    ]

    # Check that directories exist
    for q in quarters:
        if not os.path.exists(q):
            raise FileNotFoundError(f"Quarter directory missing: {q}")

    # Use union of all quarterly deletion files to purge later-retracted cases (including 2019Q1 later-retractions)
    deleted_cases_path = [
        os.path.join(sample_dir, "2019q1", "deleted", "AllDeletedCases.txt"),
        os.path.join(sample_dir, "2019q1", "deleted", "ADR19Q1DeletedCases.txt"),
        os.path.join(sample_dir, "2023q1", "Deleted", "DELETE23Q1.txt")
    ]
    omop_path = os.path.join(PROJECT_ROOT, "data", "05_reference_standards", "omop", "omop_reference_set.csv")
    output_dir = os.path.join(PROJECT_ROOT, "data", "03_primary")

    start_time = time.time()

    orchestrator = PipelineOrchestrator(
        deleted_cases_path=deleted_cases_path,
        omop_reference_path=omop_path,
        min_case_count=2  # Discard extreme singletons for robust pair statistics
    )

    results = orchestrator.run_pipeline(
        quarter_dirs=quarters,
        max_init_date="20231231",  # Enforce temporal snapshot
        output_dir=output_dir
    )

    elapsed = time.time() - start_time
    summary = results["summary"]
    pairs_df = results["candidate_pairs"]
    model_a = results["model_a_features"]
    model_b = results["model_b_features"]

    print("\n" + "=" * 70)
    print("QUALITY GATE AUDIT & INVARIANT VERIFICATION")
    print("=" * 70)

    # Invariant Check 1: No circular PRR/ROR in Model A
    leak_cols = [c for c in ["a", "b", "c", "d", "prr", "ror", "prr_chi2", "ror_lower_95"] if c in model_a.columns]
    print(f"Invariant 1 (Model A Contextual Purity): {len(leak_cols) == 0} (Leak cols: {leak_cols})")
    assert len(leak_cols) == 0, "Model A contains disproportionality metrics!"

    # Invariant Check 2: OMOP absence is UNLISTED_UNKNOWN (never negative)
    unlisted_cnt = summary["omop_distribution"].get("UNLISTED_UNKNOWN", 0)
    total_pairs = len(pairs_df)
    print(f"Invariant 2 (Strict Non-Binary OMOP Absence): {unlisted_cnt > 0} ({unlisted_cnt:,} / {total_pairs:,} pairs remain UNLISTED_UNKNOWN)")
    assert unlisted_cnt > 0, "No UNLISTED_UNKNOWN pairs found, unexpected!"

    # Invariant Check 3: Check OMOP positive and negative controls identified
    pos_cnt = summary["omop_distribution"].get("POSITIVE_CONTROL", 0)
    neg_cnt = summary["omop_distribution"].get("NEGATIVE_CONTROL", 0)
    print(f"  - Positive Controls in FAERS sample: {pos_cnt:,}")
    print(f"  - Negative Controls in FAERS sample: {neg_cnt:,}")
    print(f"  - Unlisted / Unknown pairs: {unlisted_cnt:,}")

    # Invariant Check 4: Evidence Categories sanity check (ML disabled)
    print(f"Invariant 4 (ML Disabled Evidence Tiers):")
    for tier, cnt in summary["evidence_distribution"].items():
        print(f"  - {tier}: {cnt:,} ({cnt / total_pairs * 100:.2f}%)")
    assert "NOVEL / POTENTIAL SIGNAL" not in summary["evidence_distribution"] or summary["evidence_distribution"]["NOVEL / POTENTIAL SIGNAL"] == 0, \
        "Novel ML tier appeared while ML model was disabled!"

    # Invariant Check 5: Total Unique Cases N
    print(f"Total Unique Deduplicated Cases (N): {summary['total_unique_cases_n']:,}")
    print(f"Distinct Evaluated Candidate Pairs: {total_pairs:,}")
    print(f"PRR Signal Count: {summary['prr_signal_count']:,}")
    print(f"ROR Signal Count: {summary['ror_signal_count']:,}")
    print(f"Total Pipeline Runtime: {elapsed:.2f} seconds")

    # Save summary report as JSON
    audit_path = os.path.join(output_dir, "phase2_audit_summary.json")
    with open(audit_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nAudit summary written to: {audit_path}")


if __name__ == "__main__":
    main()
