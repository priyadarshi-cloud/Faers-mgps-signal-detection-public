import json

p = r'data\14_phase3d_benchmark_evaluation\phase3d_benchmark_evaluation_results.json'
with open(p) as f:
    d = json.load(f)

be = d.get('benchmark_evaluation', {})
for bench in ['omop', 'euadr']:
    print(f'=== {bench} ===')
    for method in ['EB05', 'EBGM', 'PRR', 'ROR']:
        v = be.get(bench, {}).get(method, {})
        pr = v.get('pr_auc', 'N/A')
        roc = v.get('roc_auc', 'N/A')
        print(f'  {method}: PR-AUC={pr}, ROC-AUC={roc}')

# Print top-level keys too
print('\n=== Top keys ===')
print(list(d.keys()))
print('\n=== benchmark_evaluation keys ===')
print(list(be.keys()))
