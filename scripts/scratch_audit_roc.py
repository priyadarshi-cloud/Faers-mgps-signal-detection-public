import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score

omop = pd.read_csv('data/14_phase3d_benchmark_evaluation/omop_matched_evaluation_pairs.csv')
euadr = pd.read_csv('data/14_phase3d_benchmark_evaluation/eu_adr_matched_evaluation_pairs.csv')

print('=== OMOP POOLED ===')
for col in ['eb05', 'ebgm', 'prr', 'ror', 'a', 'e_expected', 'eb95']:
    print(f'{col}: ROC={roc_auc_score(omop["groundTruth"], omop[col]):.6f}, AP={average_precision_score(omop["groundTruth"], omop[col]):.6f}')

print('\n=== OMOP BY OUTCOME (MACRO) ===')
macro_rocs = {col: [] for col in ['eb05', 'ebgm', 'prr', 'ror']}
for out, grp in omop.groupby('outcomeName'):
    print(f'Outcome: {out} (N={len(grp)}, Pos={grp["groundTruth"].sum()})')
    for col in ['eb05', 'ebgm', 'prr', 'ror']:
        r = roc_auc_score(grp['groundTruth'], grp[col])
        macro_rocs[col].append(r)
        print(f'  {col}: {r:.4f}')

print('\nMacro average ROC:')
for col in macro_rocs:
    print(f'  {col}: mean={np.mean(macro_rocs[col]):.4f}')

print('\n=== EU-ADR POOLED ===')
for col in ['eb05', 'ebgm', 'prr', 'ror', 'a', 'e_expected', 'eb95']:
    print(f'{col}: ROC={roc_auc_score(euadr["groundTruth"], euadr[col]):.6f}, AP={average_precision_score(euadr["groundTruth"], euadr[col]):.6f}')

print('\n=== EU-ADR BY OUTCOME (MACRO) ===')
macro_rocs_eu = {col: [] for col in ['eb05', 'ebgm', 'prr', 'ror']}
for out, grp in euadr.groupby('outcomeName'):
    if grp['groundTruth'].nunique() > 1:
        for col in ['eb05', 'ebgm', 'prr', 'ror']:
            r = roc_auc_score(grp['groundTruth'], grp[col])
            macro_rocs_eu[col].append(r)
for col in macro_rocs_eu:
    print(f'  {col}: mean={np.mean(macro_rocs_eu[col]):.4f}')
