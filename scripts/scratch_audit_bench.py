import json
import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve, auc, roc_auc_score

# Load OMOP and EU-ADR matched
df_omop = pd.read_csv('data/14_phase3d_benchmark_evaluation/omop_matched_evaluation_pairs.csv')
df_euadr = pd.read_csv('data/14_phase3d_benchmark_evaluation/eu_adr_matched_evaluation_pairs.csv')

def eval_boot(df, seed=42, n_boot=1000):
    y = df['groundTruth'].values
    scores_dict = {
        'EB05': df['eb05'].values,
        'EBGM': df['ebgm'].values,
        'PRR': df['prr'].values,
        'ROR': df['ror'].values
    }
    
    # Check marginal as in script
    marginal_res = {}
    for name, s in scores_dict.items():
        p, r, _ = precision_recall_curve(y, s)
        pr_auc = auc(r, p)
        roc_auc = roc_auc_score(y, s)
        
        rng = np.random.RandomState(seed)
        boot_pr = []
        boot_roc = []
        skipped = 0
        for _ in range(n_boot):
            idx = rng.choice(len(y), size=len(y), replace=True)
            by = y[idx]
            bs = s[idx]
            if len(np.unique(by)) < 2:
                skipped += 1
                continue
            bp, br, _ = precision_recall_curve(by, bs)
            boot_pr.append(auc(br, bp))
            boot_roc.append(roc_auc_score(by, bs))
        marginal_res[name] = {
            'pr_auc': pr_auc,
            'pr_auc_ci': (np.percentile(boot_pr, 2.5), np.percentile(boot_pr, 97.5)),
            'roc_auc': roc_auc,
            'roc_auc_ci': (np.percentile(boot_roc, 2.5), np.percentile(boot_roc, 97.5)),
            'n_collected': len(boot_pr),
            'skipped': skipped
        }
        
    # Check paired difference as in TASK-T1-05
    rng = np.random.RandomState(seed)
    paired_diffs = {
        'PRR': {'pr': [], 'roc': []},
        'ROR': {'pr': [], 'roc': []},
        'EBGM': {'pr': [], 'roc': []}
    }
    skipped_paired = 0
    for _ in range(n_boot):
        idx = rng.choice(len(y), size=len(y), replace=True)
        by = y[idx]
        if len(np.unique(by)) < 2:
            skipped_paired += 1
            continue
        p_eb05, r_eb05, _ = precision_recall_curve(by, scores_dict['EB05'][idx])
        eb05_pr = auc(r_eb05, p_eb05)
        eb05_roc = roc_auc_score(by, scores_dict['EB05'][idx])
        
        for comp in ['PRR', 'ROR', 'EBGM']:
            pc, rc, _ = precision_recall_curve(by, scores_dict[comp][idx])
            c_pr = auc(rc, pc)
            c_roc = roc_auc_score(by, scores_dict[comp][idx])
            paired_diffs[comp]['pr'].append(eb05_pr - c_pr)
            paired_diffs[comp]['roc'].append(eb05_roc - c_roc)
            
    paired_res = {}
    for comp in ['PRR', 'ROR', 'EBGM']:
        paired_res[comp] = {
            'delta_pr_auc': marginal_res['EB05']['pr_auc'] - marginal_res[comp]['pr_auc'],
            'delta_pr_ci': (np.percentile(paired_diffs[comp]['pr'], 2.5), np.percentile(paired_diffs[comp]['pr'], 97.5)),
            'delta_roc_auc': marginal_res['EB05']['roc_auc'] - marginal_res[comp]['roc_auc'],
            'delta_roc_ci': (np.percentile(paired_diffs[comp]['roc'], 2.5), np.percentile(paired_diffs[comp]['roc'], 97.5)),
            'p_val_pr': np.mean(np.array(paired_diffs[comp]['pr']) <= 0) * 2,
            'p_val_roc': np.mean(np.array(paired_diffs[comp]['roc']) <= 0) * 2
        }
    return marginal_res, paired_res

print('=== OMOP BENCHMARK ===')
m_omop, p_omop = eval_boot(df_omop)
for k, v in m_omop.items():
    print(f"{k:6s} | PR-AUC: {v['pr_auc']:.4f} [{v['pr_auc_ci'][0]:.4f}, {v['pr_auc_ci'][1]:.4f}] | ROC: {v['roc_auc']:.4f} [{v['roc_auc_ci'][0]:.4f}, {v['roc_auc_ci'][1]:.4f}] | collected: {v['n_collected']} skipped: {v['skipped']}")
print('\nPaired OMOP differences vs EB05:')
for k, v in p_omop.items():
    print(f"{k:6s} | Delta PR: {v['delta_pr_auc']:+.4f} [{v['delta_pr_ci'][0]:.4f}, {v['delta_pr_ci'][1]:.4f}] p={v['p_val_pr']:.4f} | Delta ROC: {v['delta_roc_auc']:+.4f} [{v['delta_roc_ci'][0]:.4f}, {v['delta_roc_ci'][1]:.4f}] p={v['p_val_roc']:.4f}")

print('\n=== EU-ADR BENCHMARK ===')
m_euadr, p_euadr = eval_boot(df_euadr)
for k, v in m_euadr.items():
    print(f"{k:6s} | PR-AUC: {v['pr_auc']:.4f} [{v['pr_auc_ci'][0]:.4f}, {v['pr_auc_ci'][1]:.4f}] | ROC: {v['roc_auc']:.4f} [{v['roc_auc_ci'][0]:.4f}, {v['roc_auc_ci'][1]:.4f}] | collected: {v['n_collected']} skipped: {v['skipped']}")
print('\nPaired EU-ADR differences vs EB05:')
for k, v in p_euadr.items():
    print(f"{k:6s} | Delta PR: {v['delta_pr_auc']:+.4f} [{v['delta_pr_ci'][0]:.4f}, {v['delta_pr_ci'][1]:.4f}] p={v['p_val_pr']:.4f} | Delta ROC: {v['delta_roc_auc']:+.4f} [{v['delta_roc_ci'][0]:.4f}, {v['delta_roc_ci'][1]:.4f}] p={v['p_val_roc']:.4f}")
