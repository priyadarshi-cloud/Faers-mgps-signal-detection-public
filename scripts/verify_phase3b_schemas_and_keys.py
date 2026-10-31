import os
import csv
import json

features_dir = os.path.join("data", "10_phase3b_features")
manifest_path = os.path.join(features_dir, "phase3b_feature_manifest.json")

with open(manifest_path, "r", encoding="utf-8") as f:
    manifest = json.load(f)

print("Starting streaming audit of schemas, row counts, and key alignment...")

manifest_files = manifest["files"]
expected_row_count = 1167891

# 1. Header & Schema verification
for fname, meta in manifest_files.items():
    fpath = os.path.join(features_dir, fname)
    with open(fpath, "r", encoding="utf-8") as fh:
        header = fh.readline().strip().split(",")
    expected_cols = meta["columns"]
    match = (header == expected_cols)
    print(f"  Schema check {fname}: {'PASS' if match else 'FAIL'} (cols: {len(header)} vs {len(expected_cols)})")
    if not match:
        print(f"    Expected: {expected_cols}")
        print(f"    Actual:   {header}")

# 2. Check quarantine & exclusion rules from manifest specs
primary_tiers = [
    "m1_pure_contextual_features.csv",
    "m2_multimodal_features.csv",
    "m2a_count_ablation_features.csv",
    "m2b_disproportionality_ablation_features.csv"
]

quarantined = [
    "death_ratio", "life_threatening_ratio", "hospitalization_ratio",
    "disability_ratio", "serious_outcome_ratio"
]

disprop_and_contingency = [
    "a", "b", "c", "d", "prr", "prr_chi2", "ror", "ror_lower_95", "ror_upper_95"
]

for fname in primary_tiers:
    fpath = os.path.join(features_dir, fname)
    with open(fpath, "r", encoding="utf-8") as fh:
        header = set(fh.readline().strip().split(","))
    overlap_quarantine = header.intersection(quarantined)
    if overlap_quarantine:
        print(f"FAIL: Quarantined features found in {fname}: {overlap_quarantine}")
    else:
        print(f"PASS: Quarantined features absent from {fname}")

with open(os.path.join(features_dir, "m1_pure_contextual_features.csv"), "r", encoding="utf-8") as fh:
    m1_header = set(fh.readline().strip().split(","))
overlap_disprop = m1_header.intersection(disprop_and_contingency)
if overlap_disprop:
    print(f"FAIL: Disprop/contingency found in M1: {overlap_disprop}")
else:
    print(f"PASS: M1 contains no disproportionality or contingency features")

# 3. Stream row counts and verify key alignment with candidate_pairs_summary.csv
print("\nVerifying row counts and key ordering across matrices...")

def stream_keys_and_count(filepath):
    count = 0
    with open(filepath, "r", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        hdr = next(reader)
        drug_idx = hdr.index("canonical_drug")
        pt_idx = hdr.index("canonical_pt")
        for row in reader:
            count += 1
            if count == 1 or count == expected_row_count or count % 300000 == 0:
                yield count, row[drug_idx], row[pt_idx]
    yield count, None, None

# Sample check candidate_pairs_summary key sequence
candidate_samples = {}
with open(os.path.join(features_dir, "candidate_pairs_summary.csv"), "r", encoding="utf-8") as fh:
    reader = csv.reader(fh)
    hdr = next(reader)
    drug_idx = hdr.index("canonical_drug")
    pt_idx = hdr.index("canonical_pt")
    c = 0
    for row in reader:
        c += 1
        if c == 1 or c == expected_row_count or c % 300000 == 0:
            candidate_samples[c] = (row[drug_idx], row[pt_idx])
total_cand_rows = c
print(f"candidate_pairs_summary.csv total rows: {total_cand_rows} (Expected: {expected_row_count})")

for fname in manifest_files.keys():
    if fname == "candidate_pairs_summary.csv":
        continue
    fpath = os.path.join(features_dir, fname)
    with open(fpath, "r", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        hdr = next(reader)
        drug_idx = hdr.index("canonical_drug")
        pt_idx = hdr.index("canonical_pt")
        c = 0
        samples = {}
        for row in reader:
            c += 1
            if c in candidate_samples:
                samples[c] = (row[drug_idx], row[pt_idx])
    aligned = (samples == candidate_samples)
    row_match = (c == expected_row_count)
    print(f"  {fname}: rows={c} ({'PASS' if row_match else 'FAIL'}), key alignment sample: {'PASS' if aligned else 'FAIL'}")

print("\nStreaming schema & key verification complete.")
