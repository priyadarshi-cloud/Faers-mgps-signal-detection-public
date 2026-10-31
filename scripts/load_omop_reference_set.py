"""
Optional Developer Utility: Download and extract upstream OMOP Reference Set RDA to CSV.

NOTE: This script is an optional developer convenience and is NOT required for reproducing
study results. The pre-converted reference standard is already bundled in:
  data/05_reference_standards/omop/omop_reference_set.csv
All research pipelines and benchmark audits read this pre-converted CSV via pandas.

If you wish to re-download and re-extract from the upstream RDA, install pyreadr
(licensed under GNU AGPL-3.0):
  pip install pyreadr==0.5.7
"""

import os
import sys
import requests
import pandas as pd

try:
    import pyreadr
except ImportError:
    print("=" * 70)
    print("NOTE: 'pyreadr' is not installed.")
    print("The pre-converted reference CSV is already bundled and available at:")
    print("  data/05_reference_standards/omop/omop_reference_set.csv")
    print("All study reproduction scripts use this CSV directly via pandas.")
    print("If you wish to re-extract the RDA file, install pyreadr:")
    print("  pip install pyreadr==0.5.7  (License: GNU AGPL-3.0)")
    print("=" * 70)
    sys.exit(0)

dest_dir = r"data/05_reference_standards/omop"
os.makedirs(dest_dir, exist_ok=True)

url = "https://raw.githubusercontent.com/OHDSI/MethodEvaluation/main/data/omopReferenceSet.rda"
rda_path = os.path.join(dest_dir, "omopReferenceSet.rda")

print(f"Downloading OMOP Reference Set from {url}...")
r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
r.raise_for_status()
with open(rda_path, 'wb') as f:
    f.write(r.content)
print(f"Saved {len(r.content)} bytes to {rda_path}")

# Read using pyreadr
result = pyreadr.read_r(rda_path)
print("Keys in RDA:", list(result.keys()))
df = result[list(result.keys())[0]]

print("\n--- OMOP Reference Set DataFrame Summary ---")
print(f"Total Rows: {len(df)}")
print("Columns:", df.columns.tolist())
print("\nSample Rows:")
print(df.head(10))

# Save as CSV for transparent inspection and future use
csv_path = os.path.join(dest_dir, "omop_reference_set.csv")
df.to_csv(csv_path, index=False)
print(f"\nSaved CSV to {csv_path}")

# Distribution of ground truth and outcomes
if 'groundTruth' in df.columns:
    print("\nGround Truth Distribution:")
    print(df['groundTruth'].value_counts(dropna=False))
if 'outcomeName' in df.columns:
    print("\nOutcome Distribution:")
    print(df['outcomeName'].value_counts(dropna=False))
    print("\nOutcome x Ground Truth:")
    print(pd.crosstab(df['outcomeName'], df['groundTruth']))
