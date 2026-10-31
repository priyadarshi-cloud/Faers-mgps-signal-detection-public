import os
import glob
import pandas as pd
import numpy as np

def analyze_quarter(q_dir, q_label):
    print(f"\n=======================================================")
    print(f"=== QUANTITATIVE FAERS ANALYSIS: {q_label} ===")
    print(f"=======================================================")

    ascii_dir = os.path.join(q_dir, "ascii")
    if not os.path.exists(ascii_dir):
        ascii_dir = q_dir

    def load_table(prefix):
        matches = glob.glob(os.path.join(ascii_dir, f"{prefix}*.txt"))
        if not matches:
            matches = glob.glob(os.path.join(ascii_dir, f"{prefix.lower()}*.txt"))
        if not matches:
            raise FileNotFoundError(f"No file matching {prefix} in {ascii_dir}")
        fpath = matches[0]
        # Read with latin-1, delimiter '$', low_memory=False
        df = pd.read_csv(fpath, sep='$', encoding='latin-1', low_memory=False, dtype=str)
        df.columns = [c.lower() for c in df.columns]
        return df, os.path.basename(fpath)

    # 1. DEMO
    demo_df, demo_file = load_table("DEMO")
    n_demo_rows = len(demo_df)
    n_unique_caseid = demo_df['caseid'].nunique()
    n_unique_primaryid = demo_df['primaryid'].nunique()

    # Sex column name check: 'sex' or 'gndr_cod'
    sex_col = 'sex' if 'sex' in demo_df.columns else 'gndr_cod'

    # Missingness
    age_missing = demo_df['age'].isna() | (demo_df['age'].str.strip() == '')
    sex_missing = demo_df[sex_col].isna() | (demo_df[sex_col].str.strip() == '') | (demo_df[sex_col].str.upper().isin(['UNK', 'NS', 'U']))
    occp_missing = demo_df['occp_cod'].isna() | (demo_df['occp_cod'].str.strip() == '')
    country_missing = demo_df['reporter_country'].isna() | (demo_df['reporter_country'].str.strip() == '')

    print(f"DEMO Table ({demo_file}):")
    print(f"  Total Report Rows (PRIMARYID): {n_demo_rows:,}")
    print(f"  Unique CASEID:                 {n_unique_caseid:,}")
    print(f"  Multi-version Cases (Follow-ups): {n_demo_rows - n_unique_caseid:,} ({(n_demo_rows - n_unique_caseid)/n_demo_rows*100:.2f}%)")
    print(f"  Missing Age %:                 {age_missing.mean()*100:.2f}%")
    print(f"  Missing/Unknown Sex %:         {sex_missing.mean()*100:.2f}% (Column: '{sex_col}')")
    print(f"  Missing Reporter Qualification (occp_cod) %: {occp_missing.mean()*100:.2f}%")
    print(f"  Missing Reporter Country %:    {country_missing.mean()*100:.2f}%")

    # Inspect i_f_code (Initial vs Follow-up)
    if 'i_f_code' in demo_df.columns:
        print(f"  Initial vs Follow-up breakdown (i_f_code):")
        print(demo_df['i_f_code'].value_counts(dropna=False).to_dict())

    # Inspect caseversion
    if 'caseversion' in demo_df.columns:
        max_v = pd.to_numeric(demo_df['caseversion'], errors='coerce').max()
        print(f"  Max Case Version in quarter: {max_v}")

    # Inspect dates
    date_cols = [c for c in ['init_fda_dt', 'fda_dt', 'event_dt', 'mfr_dt', 'rept_dt'] if c in demo_df.columns]
    print(f"  Date columns present: {date_cols}")
    for dc in date_cols[:3]:
        valid_dates = demo_df[dc].dropna().str.strip()
        print(f"    Sample {dc}: {valid_dates.iloc[0] if len(valid_dates)>0 else 'None'} (Length distribution: {valid_dates.str.len().value_counts().to_dict()})")

    # Inspect reporter qualification distribution (occp_cod)
    print(f"  Reporter Qualifications (occp_cod distribution):")
    print(demo_df['occp_cod'].value_counts(dropna=False).head(8).to_dict())

    # 2. DRUG
    drug_df, drug_file = load_table("DRUG")
    n_drug_rows = len(drug_df)
    n_drug_primaryids = drug_df['primaryid'].nunique()
    print(f"\nDRUG Table ({drug_file}):")
    print(f"  Total Drug Records:            {n_drug_rows:,}")
    print(f"  Mean Drugs per Report:         {n_drug_rows / n_demo_rows:.2f}")
    print(f"  Drug Role Distribution (role_cod):")
    role_counts = drug_df['role_cod'].value_counts(dropna=False)
    for role, cnt in role_counts.items():
        print(f"    Role '{role}': {cnt:,} ({cnt/n_drug_rows*100:.2f}%)")
    has_prod_ai = 'prod_ai' in drug_df.columns
    print(f"  Has 'prod_ai' (Active Ingredient) column?: {has_prod_ai}")
    if has_prod_ai:
        prod_ai_missing = drug_df['prod_ai'].isna() | (drug_df['prod_ai'].str.strip() == '')
        print(f"    Missing 'prod_ai' %: {prod_ai_missing.mean()*100:.2f}%")
        print(f"    Top prod_ai sample: {drug_df['prod_ai'].dropna().value_counts().head(5).to_dict()}")

    # 3. REAC
    reac_df, reac_file = load_table("REAC")
    n_reac_rows = len(reac_df)
    print(f"\nREAC Table ({reac_file}):")
    print(f"  Total Reaction Records:        {n_reac_rows:,}")
    print(f"  Unique MedDRA PTs:             {reac_df['pt'].nunique():,}")
    print(f"  Mean Reactions per Report:     {n_reac_rows / n_demo_rows:.2f}")
    print(f"  Top 5 Reported Reactions (pt): {reac_df['pt'].value_counts().head(5).to_dict()}")
    if 'drug_rec_act' in reac_df.columns:
        print(f"  'drug_rec_act' present; Top values: {reac_df['drug_rec_act'].value_counts(dropna=False).head(5).to_dict()}")

    # 4. OUTC
    outc_df, outc_file = load_table("OUTC")
    n_outc_rows = len(outc_df)
    cases_with_outc = outc_df['primaryid'].nunique()
    print(f"\nOUTC Table ({outc_file}):")
    print(f"  Total Outcome Records:         {n_outc_rows:,}")
    print(f"  Reports with at least 1 outcome: {cases_with_outc:,} ({cases_with_outc / n_demo_rows * 100:.2f}%)")
    print(f"  Missing Outcome % (reports with NO OUTC record): {(1 - cases_with_outc / n_demo_rows)*100:.2f}%")
    print(f"  Outcome Code Breakdown (outc_cod):")
    outc_counts = outc_df['outc_cod'].value_counts(dropna=False)
    for code, cnt in outc_counts.items():
        print(f"    Outcome '{code}': {cnt:,} ({cnt/n_outc_rows*100:.2f}%)")

    # 5. RPSR, INDI, THER summary counts
    rpsr_df, _ = load_table("RPSR")
    indi_df, _ = load_table("INDI")
    ther_df, _ = load_table("THER")
    print(f"\nOther Tables Summary:")
    print(f"  RPSR (Report Sources) Rows:   {len(rpsr_df):,}")
    print(f"  INDI (Indications) Rows:      {len(indi_df):,}")
    print(f"  THER (Therapy Dates) Rows:    {len(ther_df):,}")

if __name__ == '__main__':
    for q, lbl in [("2014q1", "2014Q1"), ("2019q1", "2019Q1")]:
        analyze_quarter(f"data/01_raw/sample_quarters/{q}", lbl)
