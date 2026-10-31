import json, os, sys, hashlib
import numpy as np
import pandas as pd

CANDIDATE_CSV = 'data/10_phase3b_features/candidate_pairs_summary.csv'
EXPECTED_SHA = '1ba9e480ad1d5783e036b395460a5b763d57df565a686b02c081cc9ff0742cec'

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        while True:
            chunk = fh.read(8 * 1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

print('=== Phase 3C.1C Audit Analysis ===')
sha = sha256_file(CANDIDATE_CSV)
sha_match = sha == EXPECTED_SHA
print('SHA match:', sha_match)

df = pd.read_csv(CANDIDATE_CSV)
print('Rows loaded:', len(df))
print('Columns:', list(df.columns))

n_total = len(df)
n_unique = df.groupby(['canonical_drug','canonical_pt']).ngroups
print('Key uniqueness: total=%d, unique=%d, dups=%d' % (n_total, n_unique, n_total-n_unique))

min_a = int(df['a'].min())
max_a = int(df['a'].max())
has_a0 = min_a == 0
has_a1 = bool((df['a'] == 1).any())
print('a range: [%d, %d], a=0: %s, a=1: %s' % (min_a, max_a, has_a0, has_a1))
print('a=2: %d (%.1f%%)' % ((df['a']==2).sum(), (df['a']==2).mean()*100))
print('a=3: %d (%.1f%%)' % ((df['a']==3).sum(), (df['a']==3).mean()*100))
print('a in [2,5]: %d (%.1f%%)' % (df['a'].between(2,5).sum(), df['a'].between(2,5).mean()*100))
print('a > 10: %d (%.1f%%)' % ((df['a']>10).sum(), (df['a']>10).mean()*100))

N = 6005839
df['e'] = (df['a'] + df['b']) * (df['a'] + df['c']) / float(N)
E = df['e']
e_zeros = int((E <= 0).sum())
print('E range: [%.8f, %.2f], median=%.6f' % (E.min(), E.max(), E.median()))
print('E<=0:', e_zeros)
print('E<0.01: %d (%.1f%%)' % ((E<0.01).sum(), (E<0.01).mean()*100))
print('E<0.1: %d (%.1f%%)' % ((E<0.1).sum(), (E<0.1).mean()*100))
print('E<1.0: %d (%.1f%%)' % ((E<1.0).sum(), (E<1.0).mean()*100))
print('E>=2: %d (%.1f%%)' % ((E>=2).sum(), (E>=2).mean()*100))

log10_E = np.log10(E.values)
log10_E_r = np.round(log10_E, 2)
pairs_set = set(zip(df['a'].values.tolist(), log10_E_r.tolist()))
unique_bins = len(pairs_set)
comp = len(df) / unique_bins
print('Log-binning: %d pairs -> %d bins, compression %.1fx' % (len(df), unique_bins, comp))
print('log10(E) range: [%.3f, %.3f] (%.2f decades)' % (log10_E.min(), log10_E.max(), log10_E.max()-log10_E.min()))

df['log10e_bin'] = log10_E_r
grouped_e = df.groupby(['a','log10e_bin'])['e']
def rel_spread(g):
    if len(g) > 1:
        return float(g.std()/g.mean())
    return 0.0
rel_errors = grouped_e.apply(rel_spread)
print('Within-bin E spread: mean=%.5f%%, max=%.5f%%' % (rel_errors.mean()*100, rel_errors.max()*100))

n_drugs = df['canonical_drug'].nunique()
n_adrs = df['canonical_pt'].nunique()
theo_max = n_drugs * n_adrs
implied_missing = theo_max - len(df)
pct_missing = implied_missing / theo_max * 100
print('n_drugs=%d, n_adrs=%d, theoretical_max=%d' % (n_drugs, n_adrs, theo_max))
print('Pairs in universe (a>=2): %d' % len(df))
print('Implied missing (a<2): %d (%.1f%%)' % (implied_missing, pct_missing))

df['drug_total'] = df['a'] + df['b']
df['event_total'] = df['a'] + df['c']
dt = df.groupby('canonical_drug')['drug_total'].first()
et = df.groupby('canonical_pt')['event_total'].first()
print('Drug totals: min=%d, median=%.0f, max=%d' % (dt.min(), dt.median(), dt.max()))
print('Event totals: min=%d, median=%.0f, max=%d' % (et.min(), et.median(), et.max()))

prereqs = {
    'input_sha256_match': sha_match,
    'no_duplicate_keys': n_total == n_unique,
    'all_e_strictly_positive': e_zeros == 0,
    'min_a_is_2': min_a == 2,
    'row_count_matches_manifest': n_total == 1167891,
}
print('Prerequisites:')
for k,v in prereqs.items():
    print('  %s: %s' % (k, 'PASS' if v else 'FAIL'))

results = {
    'sha': sha, 'sha_match': sha_match,
    'n_total': n_total, 'n_unique': n_unique,
    'min_a': min_a, 'max_a': max_a,
    'has_a0': has_a0, 'has_a1': has_a1,
    'pct_a2': float((df['a']==2).mean()*100),
    'pct_a3': float((df['a']==3).mean()*100),
    'pct_a2_5': float(df['a'].between(2,5).mean()*100),
    'e_min': float(E.min()), 'e_max': float(E.max()),
    'e_median': float(E.median()), 'e_zeros': e_zeros,
    'unique_bins': unique_bins, 'compression_ratio': float(comp),
    'log10_e_min': float(log10_E.min()), 'log10_e_max': float(log10_E.max()),
    'log10_e_span': float(log10_E.max()-log10_E.min()),
    'within_bin_rel_spread_mean_pct': float(rel_errors.mean()*100),
    'within_bin_rel_spread_max_pct': float(rel_errors.max()*100),
    'n_drugs': n_drugs, 'n_adrs': n_adrs,
    'theoretical_max_pairs': theo_max,
    'implied_missing': implied_missing,
    'pct_missing': float(pct_missing),
    'prereqs': prereqs,
}
with open('data/11_phase3b_audit/phase3c1c_analysis_results.json','w') as fh:
    json.dump(results, fh, indent=2)
print('Done. Results written.')
