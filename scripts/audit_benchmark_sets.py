"""
Audit and inspect OMOP and EU-ADR benchmark reference sets against FAERS candidate universe.
"""

import os
import sys
import json
import pandas as pd
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

OMOP_PATH = os.path.join(PROJECT_ROOT, "data", "05_reference_standards", "omop", "omop_reference_set.csv")
EUADR_PATH = os.path.join(PROJECT_ROOT, "data", "05_reference_standards", "eu_adr", "eu_adr_reference_set.csv")
SCORED_PATH = os.path.join(PROJECT_ROOT, "data", "13_phase3c2_mgps_scoring", "phase3c2_scored_candidate_pairs.csv")

def main():
    print("=" * 80)
    print("AUDITING REFERENCE STANDARDS & FAERS CANDIDATE UNIVERSE")
    print("=" * 80)

    # 1. Load OMOP
    df_omop = pd.read_csv(OMOP_PATH)
    print(f"\n1. OMOP Reference Set: {len(df_omop)} rows")
    print("   Outcomes:")
    print(df_omop['outcomeName'].value_counts().to_string())
    print("   Ground Truth:")
    print(df_omop['groundTruth'].value_counts().to_string())
    print(f"   Unique drugs: {df_omop['exposureName'].nunique()}")

    # 2. Load EU-ADR
    df_euadr = pd.read_csv(EUADR_PATH)
    print(f"\n2. EU-ADR Reference Set: {len(df_euadr)} rows")
    print("   Outcomes:")
    print(df_euadr['outcomeName'].value_counts().to_string())
    print("   Ground Truth:")
    print(df_euadr['groundTruth'].value_counts().to_string())
    print(f"   Unique drugs: {df_euadr['exposureName'].nunique()}")

    # 3. Inspect scored FAERS universe
    print(f"\n3. Loading sample from scored FAERS universe ({SCORED_PATH})...")
    df_faers = pd.read_csv(SCORED_PATH, usecols=["canonical_drug", "canonical_pt"])
    print(f"   Loaded {len(df_faers):,} pairs.")
    unique_drugs = set(df_faers["canonical_drug"].dropna().str.lower().str.strip())
    unique_pts = set(df_faers["canonical_pt"].dropna().str.strip())
    print(f"   Unique FAERS drugs: {len(unique_drugs):,}")
    print(f"   Unique FAERS PTs: {len(unique_pts):,}")

    # Check drug overlap for OMOP
    omop_drugs = set(df_omop['exposureName'].dropna().str.lower().str.strip())
    omop_overlap = omop_drugs.intersection(unique_drugs)
    print(f"\n4. OMOP Drug Overlap: {len(omop_overlap)} / {len(omop_drugs)} ({len(omop_overlap)/len(omop_drugs)*100:.1f}%)")
    missing_omop_drugs = sorted(list(omop_drugs - unique_drugs))
    print(f"   Sample missing OMOP drugs ({len(missing_omop_drugs)}): {missing_omop_drugs[:10]}")

    # Check drug overlap for EU-ADR
    euadr_drugs = set(df_euadr['exposureName'].dropna().str.lower().str.strip())
    euadr_overlap = euadr_drugs.intersection(unique_drugs)
    print(f"\n5. EU-ADR Drug Overlap: {len(euadr_overlap)} / {len(euadr_drugs)} ({len(euadr_overlap)/len(euadr_drugs)*100:.1f}%)")
    missing_euadr_drugs = sorted(list(euadr_drugs - unique_drugs))
    print(f"   Sample missing EU-ADR drugs ({len(missing_euadr_drugs)}): {missing_euadr_drugs[:10]}")

    # Inspect PTs matching key outcome clinical terms
    print("\n6. Inspecting Candidate PTs for OMOP Outcomes:")
    outcome_keywords = {
        "Acute Liver Failure": ["hepatic failure", "liver failure", "acute hepatic failure", "hepatotoxicity"],
        "Acute Myocardial Infarction": ["myocardial infarction", "acute myocardial infarction"],
        "Acute Renal Failure": ["acute kidney injury", "renal failure acute", "renal failure"],
        "Upper GI Bleeding": ["gastrointestinal haemorrhage", "upper gastrointestinal haemorrhage", "gastric haemorrhage", "gastric ulcer haemorrhage"]
    }

    for hoi, kws in outcome_keywords.items():
        matched_pts = [pt for pt in unique_pts if any(kw in pt.lower() for kw in kws)]
        print(f"   {hoi} (Keywords: {kws}): {len(matched_pts)} PTs -> {matched_pts[:6]}")

if __name__ == "__main__":
    main()
