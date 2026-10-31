import os
import glob
import pandas as pd

def inspect_quarter(q_dir, q_label):
    print(f"\n=======================================================")
    print(f"=== COMPREHENSIVE SCHEMA INSPECTION: {q_label} ===")
    print(f"=======================================================")

    # Locate ascii folder
    ascii_dir = os.path.join(q_dir, "ascii")
    if not os.path.exists(ascii_dir):
        ascii_dir = q_dir

    txt_files = glob.glob(os.path.join(ascii_dir, "*.txt"))
    for fpath in sorted(txt_files):
        fname = os.path.basename(fpath)
        file_prefix = fname[:4].upper()

        # Check first line for delimiter and columns
        with open(fpath, 'r', encoding='latin-1', errors='replace') as f:
            header_line = f.readline().strip()
            sample_line = f.readline().strip()

        delimiter = '$' if '$' in header_line else (',' if ',' in header_line else '\t')
        cols = header_line.split(delimiter)

        print(f"\n--- File: {fname} (Prefix: {file_prefix}) ---")
        print(f"Delimiter: '{delimiter}', Column Count: {len(cols)}")
        print(f"Columns: {cols}")
        print(f"Sample Row: {sample_line[:120]}...")

inspect_quarter("data/01_raw/sample_quarters/2014q1", "2014Q1")
inspect_quarter("data/01_raw/sample_quarters/2019q1", "2019Q1")
