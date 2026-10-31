import pandas as pd
import numpy as np

print("Loading data...")
df_m1 = pd.read_csv('data/10_phase3b_features/m1_pure_contextual_features.csv', usecols=['canonical_drug', 'canonical_pt', 'hp_reporter_ratio', 'csm_reporter_ratio'])
df_cand = pd.read_csv('data/10_phase3b_features/candidate_pairs_summary.csv', usecols=['canonical_drug', 'canonical_pt', 'a'])
df_scored = pd.read_csv('data/13_phase3c2_mgps_scoring/phase3c2_scored_candidate_pairs.csv', usecols=['canonical_drug', 'canonical_pt', 'eb05'])
df_lw = pd.read_csv('data/34_task_t1_12_final_scientific_corrections/lw_pair_counts.csv')

df = df_m1.merge(df_cand, on=['canonical_drug', 'canonical_pt'], how='left')
df = df.merge(df_scored, on=['canonical_drug', 'canonical_pt'], how='left')
df = df.merge(df_lw, on=['canonical_drug', 'canonical_pt'], how='left')
df['lw_count'] = df['lw_count'].fillna(0).astype(int)
df['hp_corrected'] = np.clip(df['hp_reporter_ratio'] - (df['lw_count'] / df['a']), 0.0, 1.0)

df['sum_old'] = df['hp_reporter_ratio'] + df['csm_reporter_ratio']
df['sum_new'] = df['hp_corrected'] + df['csm_reporter_ratio']

strata_defs = [
    ('Stratum 1 (EB05 < 1.0)', df['eb05'] < 1.0),
    ('Stratum 2 (1.0 <= EB05 < 2.0)', (df['eb05'] >= 1.0) & (df['eb05'] < 2.0)),
    ('Stratum 3 (2.0 <= EB05 < 5.0)', (df['eb05'] >= 2.0) & (df['eb05'] < 5.0)),
    ('Stratum 4 (5.0 <= EB05 < 10.0)', (df['eb05'] >= 5.0) & (df['eb05'] < 10.0)),
    ('Stratum 5 (EB05 >= 10.0)', df['eb05'] >= 10.0),
]

print("\n--- BEFORE LW CORRECTION ---")
for sname, mask in strata_defs:
    sub = df[mask]
    med_hp = float(np.median(sub['hp_reporter_ratio']))
    med_csm = float(np.median(sub['csm_reporter_ratio']))
    sum_of_meds = med_hp + med_csm
    med_of_sum = float(np.median(sub['sum_old']))
    mean_of_sum = float(np.mean(sub['sum_old']))
    std_of_sum = float(np.std(sub['sum_old']))
    q25 = float(np.percentile(sub['sum_old'], 25))
    q75 = float(np.percentile(sub['sum_old'], 75))
    iqr = q75 - q25
    print(f"{sname}:")
    print(f"  med(hp)={med_hp:.4f}, med(csm)={med_csm:.4f} -> sum_of_meds={sum_of_meds:.4f}")
    print(f"  median(hp+csm)={med_of_sum:.4f} [IQR={iqr:.4f}], mean(hp+csm)={mean_of_sum:.4f} (SD={std_of_sum:.4f})")

overall_sum_of_meds_old = float(np.median(df['hp_reporter_ratio']) + np.median(df['csm_reporter_ratio']))
print(f"Overall Universe (Old):")
print(f"  sum_of_meds={overall_sum_of_meds_old:.4f}")
print(f"  median(hp+csm)={float(np.median(df['sum_old'])):.4f}, mean(hp+csm)={float(np.mean(df['sum_old'])):.4f}")

print("\n--- AFTER LW CORRECTION ---")
for sname, mask in strata_defs:
    sub = df[mask]
    med_hp = float(np.median(sub['hp_corrected']))
    med_csm = float(np.median(sub['csm_reporter_ratio']))
    sum_of_meds = med_hp + med_csm
    med_of_sum = float(np.median(sub['sum_new']))
    mean_of_sum = float(np.mean(sub['sum_new']))
    std_of_sum = float(np.std(sub['sum_new']))
    q25 = float(np.percentile(sub['sum_new'], 25))
    q75 = float(np.percentile(sub['sum_new'], 75))
    iqr = q75 - q25
    print(f"{sname}:")
    print(f"  med(hp)={med_hp:.4f}, med(csm)={med_csm:.4f} -> sum_of_meds={sum_of_meds:.4f}")
    print(f"  median(hp+csm)={med_of_sum:.4f} [IQR={iqr:.4f}], mean(hp+csm)={mean_of_sum:.4f} (SD={std_of_sum:.4f})")

overall_sum_of_meds_new = float(np.median(df['hp_corrected']) + np.median(df['csm_reporter_ratio']))
print(f"Overall Universe (New):")
print(f"  sum_of_meds={overall_sum_of_meds_new:.4f}")
print(f"  median(hp+csm)={float(np.median(df['sum_new'])):.4f}, mean(hp+csm)={float(np.mean(df['sum_new'])):.4f}")
