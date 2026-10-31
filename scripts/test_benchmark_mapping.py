"""
Test and analyze mapping of OMOP and EU-ADR benchmarks to FAERS candidate pairs.
"""

import os
import sys
import pandas as pd
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCORED_PATH = os.path.join(PROJECT_ROOT, "data", "13_phase3c2_mgps_scoring", "phase3c2_scored_candidate_pairs.csv")
OMOP_PATH = os.path.join(PROJECT_ROOT, "data", "05_reference_standards", "omop", "omop_reference_set.csv")
EUADR_PATH = os.path.join(PROJECT_ROOT, "data", "05_reference_standards", "eu_adr", "eu_adr_reference_set.csv")

# Clinical mapping definitions
OMOP_HOI_MAPPINGS = {
    "OMOP Acute Liver Failure 1": [
        "Acute hepatic failure", "Hepatic failure", "Subacute hepatic failure", "Hepatotoxicity"
    ],
    "OMOP Acute myocardial Infarction  1": [
        "Myocardial infarction", "Acute myocardial infarction"
    ],
    "OMOP Acute Renal Failure 1": [
        "Acute kidney injury", "Renal failure acute", "Renal failure"
    ],
    "HOI Upper GI #3": [
        "Upper gastrointestinal haemorrhage", "Gastrointestinal haemorrhage", "Gastric haemorrhage", "Gastric ulcer haemorrhage"
    ]
}

EUADR_HOI_MAPPINGS = {
    "OMOP Acute Liver Failure 1": [
        "Acute hepatic failure", "Hepatic failure", "Hepatotoxicity"
    ],
    "OMOP Acute myocardial Infarction  1": [
        "Myocardial infarction", "Acute myocardial infarction"
    ],
    "OMOP Acute Renal Failure 1": [
        "Acute kidney injury", "Renal failure acute", "Renal failure"
    ],
    "HOI Upper GI #3": [
        "Upper gastrointestinal haemorrhage", "Gastrointestinal haemorrhage", "Gastric ulcer haemorrhage"
    ],
    "Anaphylaxis #1": [
        "Anaphylactic reaction", "Anaphylactic shock"
    ],
    "Cardiac Valve Fibrosis #1": [
        "Cardiac valve disease", "Heart valve incompetence", "Cardiac fibrosis"
    ],
    "Leukopenia Including Neutropenia and Agranulocytosis": [
        "Neutropenia", "Agranulocytosis", "Leukopenia", "Granulocytopenia"
    ],
    "OMOP Aplastic Anemia 1": [
        "Aplastic anaemia"
    ],
    "Rhabdomyolysis #1": [
        "Rhabdomyolysis"
    ],
    "Stevens-Johnson Syndrome #1": [
        "Stevens-Johnson syndrome", "Toxic epidermal necrolysis"
    ]
}

def normalize_drug(name: str) -> str:
    s = str(name).strip().lower()
    # Strip common salt suffixes for enhanced drug name normalization
    for salt in [", conjugated (usp)", " sodium", " potassium", " calcium", " hydrochloride", " hcl", " mesylate", " maleate", " tartrate", " succinate", " sulfate", " acetate", " phosphate"]:
        if s.endswith(salt):
            s = s[:-len(salt)].strip()
    return s

def test_mappings():
    print("Loading scored FAERS candidate table...")
    df_faers = pd.read_csv(SCORED_PATH, usecols=["canonical_drug", "canonical_pt", "a", "e_expected", "ebgm", "eb05", "eb95", "prr", "ror"])
    df_faers["drug_norm"] = df_faers["canonical_drug"].astype(str).str.strip().str.lower()
    df_faers["pt_norm"] = df_faers["canonical_pt"].astype(str).str.strip()

    # Create lookup map
    lookup = {}
    for idx, row in df_faers.iterrows():
        key = (row["drug_norm"], row["pt_norm"])
        lookup[key] = row

    print(f"Loaded {len(lookup):,} FAERS candidate pairs.")

    # 1. Evaluate OMOP mapping
    df_omop = pd.read_csv(OMOP_PATH)
    print(f"\n--- OMOP Benchmark Mapping Audit ({len(df_omop)} reference pairs) ---")
    omop_matches = []
    for _, row in df_omop.iterrows():
        d_orig = row["exposureName"]
        d_norm = str(d_orig).strip().lower()
        d_clean = normalize_drug(d_orig)
        hoi = row["outcomeName"]
        target_pts = OMOP_HOI_MAPPINGS.get(hoi, [])

        # Find best matching pair in FAERS for this drug and HOI
        matched_row = None
        matched_pt = None
        for d_try in [d_norm, d_clean]:
            for pt in target_pts:
                if (d_try, pt) in lookup:
                    c_row = lookup[(d_try, pt)]
                    if matched_row is None or c_row["eb05"] > matched_row["eb05"]:
                        matched_row = c_row
                        matched_pt = pt

        if matched_row is not None:
            omop_matches.append({
                "exposureName": d_orig,
                "outcomeName": hoi,
                "groundTruth": row["groundTruth"],
                "matched_pt": matched_pt,
                "a": matched_row["a"],
                "ebgm": matched_row["ebgm"],
                "eb05": matched_row["eb05"],
                "eb95": matched_row["eb95"],
                "prr": matched_row["prr"],
                "ror": matched_row["ror"],
            })

    df_omop_matched = pd.DataFrame(omop_matches)
    print(f"OMOP Matched Pairs: {len(df_omop_matched)} / {len(df_omop)} ({len(df_omop_matched)/len(df_omop)*100:.1f}%)")
    print(f"Ground truth in matched OMOP: Positives={sum(df_omop_matched['groundTruth']==1)}, Negatives={sum(df_omop_matched['groundTruth']==0)}")
    print(f"Unmatched OMOP: {len(df_omop) - len(df_omop_matched)} (Positives={sum(df_omop['groundTruth']==1) - sum(df_omop_matched['groundTruth']==1)}, Negatives={sum(df_omop['groundTruth']==0) - sum(df_omop_matched['groundTruth']==0)})")

    # 2. Evaluate EU-ADR mapping
    df_euadr = pd.read_csv(EUADR_PATH)
    print(f"\n--- EU-ADR Benchmark Mapping Audit ({len(df_euadr)} reference pairs) ---")
    euadr_matches = []
    for _, row in df_euadr.iterrows():
        d_orig = row["exposureName"]
        d_norm = str(d_orig).strip().lower()
        d_clean = normalize_drug(d_orig)
        hoi = row["outcomeName"]
        target_pts = EUADR_HOI_MAPPINGS.get(hoi, [])

        matched_row = None
        matched_pt = None
        for d_try in [d_norm, d_clean]:
            for pt in target_pts:
                if (d_try, pt) in lookup:
                    c_row = lookup[(d_try, pt)]
                    if matched_row is None or c_row["eb05"] > matched_row["eb05"]:
                        matched_row = c_row
                        matched_pt = pt

        if matched_row is not None:
            euadr_matches.append({
                "exposureName": d_orig,
                "outcomeName": hoi,
                "groundTruth": row["groundTruth"],
                "matched_pt": matched_pt,
                "a": matched_row["a"],
                "ebgm": matched_row["ebgm"],
                "eb05": matched_row["eb05"],
                "eb95": matched_row["eb95"],
                "prr": matched_row["prr"],
                "ror": matched_row["ror"],
            })

    df_euadr_matched = pd.DataFrame(euadr_matches)
    print(f"EU-ADR Matched Pairs: {len(df_euadr_matched)} / {len(df_euadr)} ({len(df_euadr_matched)/len(df_euadr)*100:.1f}%)")
    print(f"Ground truth in matched EU-ADR: Positives={sum(df_euadr_matched['groundTruth']==1)}, Negatives={sum(df_euadr_matched['groundTruth']==0)}")
    print(f"Unmatched EU-ADR: {len(df_euadr) - len(df_euadr_matched)} (Positives={sum(df_euadr['groundTruth']==1) - sum(df_euadr_matched['groundTruth']==1)}, Negatives={sum(df_euadr['groundTruth']==0) - sum(df_euadr_matched['groundTruth']==0)})")

if __name__ == "__main__":
    test_mappings()
