"""
Inspect temporal distributions of init_fda_dt and fda_dt across the ingested sample quarters.
"""
import os
import sys
import pandas as pd

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.data_acquisition.faers_loader import FAERSQuarterLoader
from src.preprocessing.deleted_cases import DeletedCaseManager

def main():
    sample_dir = os.path.join(PROJECT_ROOT, "data", "01_raw", "sample_quarters")
    quarters = ["2014q1", "2019q1", "2023q1"]

    deleted_cases_path = [
        os.path.join(sample_dir, "2019q1", "deleted", "AllDeletedCases.txt"),
        os.path.join(sample_dir, "2019q1", "deleted", "ADR19Q1DeletedCases.txt"),
        os.path.join(sample_dir, "2023q1", "Deleted", "DELETE23Q1.txt")
    ]
    deleted_mgr = DeletedCaseManager(deleted_cases_path)

    for q in quarters:
        q_dir = os.path.join(sample_dir, q)
        loader = FAERSQuarterLoader(q_dir, deleted_manager=deleted_mgr)
        demo = loader.load_demo(filter_deleted=True)
        print(f"\n--- Quarter: {q} ---")
        print(f"Total non-deleted DEMO rows: {len(demo):,}")

        # Analyze init_fda_dt
        init_dates = demo["init_fda_dt"].dropna().astype(str).str.strip()
        # Parse years (first 4 digits)
        init_years = init_dates.str.slice(0, 4)
        print("init_fda_dt year distribution (top 6):")
        print(init_years.value_counts().head(6))

        # Cases <= 20181231
        le_2018 = (init_dates <= "20181231").sum()
        gt_2018 = (init_dates > "20181231").sum()
        print(f"Cases with init_fda_dt <= 2018-12-31: {le_2018:,} ({le_2018/len(demo)*100:.2f}%)")
        print(f"Cases with init_fda_dt > 2018-12-31:  {gt_2018:,} ({gt_2018/len(demo)*100:.2f}%)")

if __name__ == "__main__":
    main()
