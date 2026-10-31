"""
End-to-End Pipeline Orchestration Engine for Phase 2.
Coordinates multi-quarter FAERS data ingestion, deleted case purging,
temporal anchoring, terminology normalization, drug-ADR pair construction,
baseline disproportionality calculation, contextual feature extraction,
independent OMOP reference linkage, and multi-tiered evidence classification.

MANDATORY METHODOLOGICAL INVARIANTS ENFORCED:
1. FAERS remains primary signal-discovery universe.
2. OMOP is an independent reference layer; absence NEVER means negative (strictly UNLISTED_UNKNOWN).
3. No circular validation: PRR and ROR are baseline statistics, never ML training labels.
4. Model A contains strictly contextual features (zero A, B, C, D, zero PRR, zero ROR).
5. ML signal scoring is strictly disabled (use_ml_score=False).
6. Temporal anchoring is strictly based on initial receipt date (init_fda_dt).
"""

import os
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd

from src.data_acquisition.faers_loader import FAERSQuarterLoader
from src.preprocessing.deleted_cases import DeletedCaseManager
from src.preprocessing.case_deduplication import CaseVersionManager
from src.preprocessing.drug_normalizer import DrugNormalizer
from src.preprocessing.reaction_normalizer import ReactionNormalizer
from src.pipeline.pair_builder import PairBuilder
from src.signal_detection.disproportionality import DisproportionalityCalculator
from src.features.feature_extractor import FeatureExtractor
from src.reference_standards.omop_loader import OMOPReferenceManager
from src.reference_standards.evidence_classifier import EvidenceClassifier, EvidenceCategory


class PipelineOrchestrator:
    """
    Executes the complete Phase 2 pharmacovigilance data processing pipeline.
    """

    def __init__(
        self,
        deleted_cases_path: Optional[str] = None,
        omop_reference_path: Optional[str] = None,
        min_case_count: int = 1
    ):
        # 1. Initialize Deleted Case Manager
        self.deleted_manager = DeletedCaseManager(deleted_cases_path) if deleted_cases_path else None

        # 2. Terminology and pair components
        self.drug_normalizer = DrugNormalizer()
        self.pair_builder = PairBuilder(drug_normalizer=self.drug_normalizer)

        # 3. Disproportionality and features
        self.disproportionality_calc = DisproportionalityCalculator(min_case_count=min_case_count)
        self.feature_extractor = FeatureExtractor()

        # 4. Independent Reference Layer
        if omop_reference_path and os.path.exists(omop_reference_path):
            self.omop_manager = OMOPReferenceManager(omop_reference_path)
        else:
            self.omop_manager = None

    def run_pipeline(
        self,
        quarter_dirs: List[str],
        max_init_date: Optional[str] = None,
        cutoff_date: Optional[str] = None,
        output_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run the complete pipeline across one or more quarterly directories.

        Args:
            quarter_dirs: List of paths to quarterly directories.
            max_init_date: Max initial receipt date (YYYYMMDD) for temporal window.
            cutoff_date: Max revision fda_dt for version deduplication.
            output_dir: Optional directory to save output tables.

        Returns:
            Dictionary containing datasets and execution metrics:
            - 'summary': high-level execution statistics
            - 'candidate_pairs': aggregated pairs with disproportionality and evidence tier
            - 'model_a_features': contextual feature matrix
            - 'model_b_features': extended feature matrix with PRR/ROR baselines
        """
        print(f"\n==================================================")
        print(f"STARTING PHASE 2 PIPELINE ORCHESTRATION")
        print(f"Quarters to process: {len(quarter_dirs)}")
        print(f"Max init date filter: {max_init_date}")
        print(f"==================================================")

        all_demo = []
        all_drug = []
        all_reac = []
        all_outc = []
        all_rpsr = []

        # Step 1: Ingestion across all quarterly archives
        for q_dir in quarter_dirs:
            q_name = os.path.basename(q_dir.rstrip("/\\"))
            print(f"\n[1. Ingestion] Ingesting quarter: {q_name}...")
            loader = FAERSQuarterLoader(q_dir, deleted_manager=self.deleted_manager)

            demo_q = loader.load_demo(filter_deleted=True)
            valid_pids = set(demo_q["primaryid"].unique())

            drug_q = loader.load_drug(valid_primaryids=valid_pids)
            reac_q = loader.load_reac(valid_primaryids=valid_pids)

            try:
                outc_q = loader.load_outc(valid_primaryids=valid_pids)
            except Exception:
                outc_q = pd.DataFrame()

            try:
                rpsr_q = loader.load_rpsr(valid_primaryids=valid_pids)
            except Exception:
                rpsr_q = pd.DataFrame()

            all_demo.append(demo_q)
            all_drug.append(drug_q)
            all_reac.append(reac_q)
            if not outc_q.empty:
                all_outc.append(outc_q)
            if not rpsr_q.empty:
                all_rpsr.append(rpsr_q)

        # Concatenate across quarters
        demo_combined = pd.concat(all_demo, ignore_index=True)
        drug_combined = pd.concat(all_drug, ignore_index=True)
        reac_combined = pd.concat(all_reac, ignore_index=True)
        outc_combined = pd.concat(all_outc, ignore_index=True) if all_outc else pd.DataFrame()
        rpsr_combined = pd.concat(all_rpsr, ignore_index=True) if all_rpsr else pd.DataFrame()

        print(f"\n[Raw Ingested Records across {len(quarter_dirs)} quarters]")
        print(f"  DEMO rows: {len(demo_combined):,}")
        print(f"  DRUG rows: {len(drug_combined):,}")
        print(f"  REAC rows: {len(reac_combined):,}")

        # Step 2: Temporal Anchoring and Case-Level Version Deduplication
        print(f"\n[2. Deduplication & Temporal Anchoring]")
        if max_init_date is not None:
            initial_count = len(demo_combined)
            demo_combined = CaseVersionManager.filter_by_initial_date(demo_combined, max_init_date)
            print(f"  Filtered by init_fda_dt <= {max_init_date}: {len(demo_combined):,} cases kept (dropped {initial_count - len(demo_combined):,})")

        deduped_demo = CaseVersionManager.deduplicate_cases_to_latest_version(demo_combined, cutoff_date=cutoff_date)
        total_unique_cases = len(deduped_demo)
        valid_caseids = set(deduped_demo["caseid"].unique())
        valid_primaryids = set(deduped_demo["primaryid"].unique())
        print(f"  Deduplicated unique cases (N): {total_unique_cases:,}")

        # Filter all other tables to match active deduplicated case versions
        drug_clean = drug_combined[drug_combined["primaryid"].isin(valid_primaryids)].copy()
        reac_clean = reac_combined[reac_combined["primaryid"].isin(valid_primaryids)].copy()
        outc_clean = outc_combined[outc_combined["primaryid"].isin(valid_primaryids)].copy() if not outc_combined.empty else pd.DataFrame()
        rpsr_clean = rpsr_combined[rpsr_combined["primaryid"].isin(valid_primaryids)].copy() if not rpsr_combined.empty else pd.DataFrame()

        # Step 3: Terminology Normalization & Drug-ADR Candidate Pair Construction
        print(f"\n[3. Normalization & Candidate Pair Construction]")
        drug_proc = self.pair_builder.process_drugs(drug_clean)
        reac_proc = self.pair_builder.process_reactions(reac_clean)

        norm_stats = drug_proc["norm_status"].value_counts().to_dict()
        print(f"  Drug normalization distribution in active cases:")
        for status_k, count_v in norm_stats.items():
            print(f"    - {status_k}: {count_v:,} ({count_v / len(drug_proc) * 100:.2f}%)")

        case_pairs = self.pair_builder.build_case_pairs(
            demo_df=deduped_demo,
            drug_df=drug_proc,
            reac_df=reac_proc,
            only_normalized_drugs=True,
            only_suspect_drugs=True
        )
        print(f"  Generated {len(case_pairs):,} case-level suspect drug-ADR occurrences.")

        # Step 4: Baseline Disproportionality Calculation (PRR & ROR)
        print(f"\n[4. Baseline Disproportionality Calculation]")
        disprop_df = self.disproportionality_calc.compute_contingency_and_metrics(
            case_pairs_df=case_pairs,
            total_case_count=total_unique_cases
        )
        print(f"  Computed contingency tables for {len(disprop_df):,} distinct drug-event pairs.")
        prr_signals = int(disprop_df["prr_signal"].sum()) if "prr_signal" in disprop_df.columns else 0
        ror_signals = int(disprop_df["ror_signal"].sum()) if "ror_signal" in disprop_df.columns else 0
        print(f"  PRR signals (A>=3, PRR>=2, Chi2>=4): {prr_signals:,}")
        print(f"  ROR signals (A>=3, lower 95% CI > 1): {ror_signals:,}")

        # Step 5: Contextual Feature Extraction (Model A vs Model B)
        print(f"\n[5. Contextual Feature Extraction]")
        model_a_df, model_b_df = self.feature_extractor.extract_features(
            case_pairs_df=case_pairs,
            drug_df=drug_proc,
            outc_df=outc_clean,
            rpsr_df=rpsr_clean,
            disproportionality_df=disprop_df
        )
        print(f"  Model A feature matrix shape: {model_a_df.shape} (Purely contextual)")
        print(f"  Model B feature matrix shape: {model_b_df.shape} (Extended with PRR/ROR)")

        # Verify Model A has zero PRR/ROR or cell counts
        disprop_leak_cols = [c for c in ["a", "b", "c", "d", "prr", "ror", "prr_chi2"] if c in model_a_df.columns]
        assert len(disprop_leak_cols) == 0, f"Methodological violation: Model A contains disproportionality metrics {disprop_leak_cols}!"

        # Step 6: Independent OMOP Reference Benchmark Linkage
        print(f"\n[6. Independent OMOP Reference Set Linkage]")
        if self.omop_manager is not None:
            omop_statuses = []
            matched_phenotypes = []

            for _, row in disprop_df.iterrows():
                drug = str(row["canonical_drug"])
                pt = str(row["canonical_pt"])

                # Check if PT maps to any OMOP HOI
                matching_hois = self.omop_manager.get_pt_phenotype_matches(pt)

                if not matching_hois:
                    # Not an evaluated OMOP HOI phenotype
                    omop_statuses.append("UNLISTED_UNKNOWN")
                    matched_phenotypes.append("NONE")
                else:
                    # Check reference status for each matching HOI
                    status = "UNLISTED_UNKNOWN"
                    pheno_found = matching_hois[0]
                    for hoi in matching_hois:
                        st = self.omop_manager.get_reference_status(drug, hoi)
                        if st in ["POSITIVE_CONTROL", "NEGATIVE_CONTROL"]:
                            status = st
                            pheno_found = hoi
                            break
                    omop_statuses.append(status)
                    matched_phenotypes.append(pheno_found)

            disprop_df["omop_phenotype"] = matched_phenotypes
            disprop_df["omop_status"] = omop_statuses

            omop_dist = disprop_df["omop_status"].value_counts().to_dict()
            print(f"  OMOP Benchmark Status Distribution across pairs:")
            for st_k, cnt_v in omop_dist.items():
                print(f"    - {st_k}: {cnt_v:,} ({cnt_v / len(disprop_df) * 100:.2f}%)")
        else:
            disprop_df["omop_phenotype"] = "UNAVAILABLE"
            disprop_df["omop_status"] = "UNLISTED_UNKNOWN"

        # Step 7: Multi-Tiered Evidence Classification (ML disabled)
        print(f"\n[7. Evidence Classification (Safety invariant: use_ml_score=False)]")
        evidence_categories = []
        for _, row in disprop_df.iterrows():
            tier = EvidenceClassifier.classify_pair(
                omop_status=row["omop_status"],
                case_count_a=int(row["a"]),
                prr=float(row["prr"]),
                ror_lower_95=float(row["ror_lower_95"]),
                ml_signal_score=None,
                use_ml_score=False
            )
            evidence_categories.append(tier)

        disprop_df["evidence_category"] = evidence_categories
        tier_dist = disprop_df["evidence_category"].value_counts().to_dict()
        print(f"  Multi-Tiered Evidence Category Distribution:")
        for t_k, cnt_v in tier_dist.items():
            print(f"    - {t_k}: {cnt_v:,} ({cnt_v / len(disprop_df) * 100:.2f}%)")

        # Step 8: Export Artifacts if output_dir specified
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            pairs_out = os.path.join(output_dir, "phase2_candidate_pairs_summary.csv")
            model_a_out = os.path.join(output_dir, "phase2_model_a_features.csv")
            model_b_out = os.path.join(output_dir, "phase2_model_b_features.csv")

            print(f"\n[8. Saving Pipeline Outputs to {output_dir}]")
            disprop_df.to_csv(pairs_out, index=False)
            model_a_df.to_csv(model_a_out, index=False)
            model_b_df.to_csv(model_b_out, index=False)
            print(f"  Saved candidate pairs: {pairs_out}")
            print(f"  Saved Model A features: {model_a_out}")
            print(f"  Saved Model B features: {model_b_out}")

        print(f"\n==================================================")
        print(f"PHASE 2 PIPELINE ORCHESTRATION COMPLETED SUCCESSFULLY")
        print(f"==================================================")

        return {
            "summary": {
                "quarters_processed": len(quarter_dirs),
                "total_unique_cases_n": total_unique_cases,
                "distinct_candidate_pairs": len(disprop_df),
                "prr_signal_count": prr_signals,
                "ror_signal_count": ror_signals,
                "omop_distribution": disprop_df["omop_status"].value_counts().to_dict(),
                "evidence_distribution": disprop_df["evidence_category"].value_counts().to_dict(),
            },
            "candidate_pairs": disprop_df,
            "model_a_features": model_a_df,
            "model_b_features": model_b_df
        }
