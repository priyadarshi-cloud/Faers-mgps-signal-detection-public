import pandas as pd
import numpy as np
from scipy import stats

print('Loading datasets...')
df_m1 = pd.read_csv('data/10_phase3b_features/m1_pure_contextual_features.csv', usecols=['canonical_drug', 'canonical_pt', 'hp_reporter_ratio', 'csm_reporter_ratio'])
df_cand = pd.read_csv('data/10_phase3b_features/candidate_pairs_summary.csv', usecols=['canonical_drug', 'canonical_pt', 'a'])
df_scored = pd.read_csv('data/13_phase3c2_mgps_scoring/phase3c2_scored_candidate_pairs.csv', usecols=['canonical_drug', 'canonical_pt', 'eb05'])
df_lw = pd.read_csv('data/34_task_t1_12_final_scientific_corrections/lw_pair_counts.csv')

print('Merging...')
df = df_m1.merge(df_cand, on=['canonical_drug', 'canonical_pt'], how='left')
df = df.merge(df_scored, on=['canonical_drug', 'canonical_pt'], how='left')
df = df.merge(df_lw, on=['canonical_drug', 'canonical_pt'], how='left')
df['lw_count'] = df['lw_count'].fillna(0).astype(int)

df['hp_corrected'] = np.clip(df['hp_reporter_ratio'] - (df['lw_count'] / df['a']), 0.0, 1.0)
diff = df['hp_reporter_ratio'] - df['hp_corrected']

n_changed = int((diff > 1e-6).sum())
print(f"Pairs changed: {n_changed} ({n_changed/len(df)*100:.2f}%)")
print(f"Mean diff: {diff.mean():.6f}")
print(f"Max diff: {diff.max():.6f}")
print(f"Old mean: {df['hp_reporter_ratio'].mean():.6f}, New mean: {df['hp_corrected'].mean():.6f}")
print(f"Old median: {df['hp_reporter_ratio'].median():.6f}, New median: {df['hp_corrected'].median():.6f}")

# Strata definitions
strata_defs = [
    ('EB05 < 1.0', df['eb05'] < 1.0),
    ('1.0 <= EB05 < 2.0', (df['eb05'] >= 1.0) & (df['eb05'] < 2.0)),
    ('2.0 <= EB05 < 5.0', (df['eb05'] >= 2.0) & (df['eb05'] < 5.0)),
    ('5.0 <= EB05 < 10.0', (df['eb05'] >= 5.0) & (df['eb05'] < 10.0)),
    ('EB05 >= 10.0', df['eb05'] >= 10.0),
]

groups_old = []
groups_new = []
for sname, mask in strata_defs:
    sub = df[mask]
    v_old = sub['hp_reporter_ratio'].values
    v_new = sub['hp_corrected'].values
    groups_old.append(v_old)
    groups_new.append(v_new)
    print(f"Stratum {sname}: N={len(sub)}, old_mean={v_old.mean():.4f}, new_mean={v_new.mean():.4f}, old_med={np.median(v_old):.4f}, new_med={np.median(v_new):.4f}")

kw_old = stats.kruskal(*groups_old)
kw_new = stats.kruskal(*groups_new)
N = len(df)
k = 5
eps2_old = (kw_old.statistic - k + 1) / (N - k)
eps2_new = (kw_new.statistic - k + 1) / (N - k)
print(f"KW old: H={kw_old.statistic:.4f}, p={kw_old.pvalue:.4e}, eps2={eps2_old:.6f}")
print(f"KW new: H={kw_new.statistic:.4f}, p={kw_new.pvalue:.4e}, eps2={eps2_new:.6f}")

# Check non-complementary denominators
sum_old = df['hp_reporter_ratio'] + df['csm_reporter_ratio']
sum_new = df['hp_corrected'] + df['csm_reporter_ratio']
print(f"Overall sum (old): mean={sum_old.mean():.4f}, median={sum_old.median():.4f}")
print(f"Overall sum (new): mean={sum_new.mean():.4f}, median={sum_new.median():.4f}")

for sname, mask in strata_defs:
    sub = df[mask]
    s_new = sub['hp_corrected'] + sub['csm_reporter_ratio']
    print(f"Stratum {sname} sum: mean={s_new.mean():.4f}, median={np.median(s_new):.4f}")
