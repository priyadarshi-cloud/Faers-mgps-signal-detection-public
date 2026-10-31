"""
Inspection script to verify candidate pairs and feature matrices.
"""
import os
import pandas as pd

def main():
    base_dir = "data/03_primary"
    cp_path = os.path.join(base_dir, "phase2_candidate_pairs_summary.csv")
    ma_path = os.path.join(base_dir, "phase2_model_a_features.csv")
    mb_path = os.path.join(base_dir, "phase2_model_b_features.csv")

    print("Reading Candidate Pairs summary...")
    cp_df = pd.read_csv(cp_path)
    print(f"Candidate Pairs shape: {cp_df.shape}")
    print(f"Candidate Pairs columns: {list(cp_df.columns)}")
    print(f"Unique keys in CP: {len(cp_df.groupby(['canonical_drug', 'canonical_pt']))}")
    print(f"Min case count A: {cp_df['a'].min()}, Max A: {cp_df['a'].max()}")
    print(f"A >= 2 count: {(cp_df['a'] >= 2).sum()}")

    print("\nReading Model A Features (sampled / full row count)...")
    ma_head = pd.read_csv(ma_path, nrows=10)
    print(f"Model A columns: {list(ma_head.columns)}")

    print("\nReading Model B Features (sampled / full row count)...")
    mb_head = pd.read_csv(mb_path, nrows=10)
    print(f"Model B columns: {list(mb_head.columns)}")

if __name__ == "__main__":
    main()
