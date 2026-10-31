with open(r'data\21_track1_publication_figures\publication_figures_methods.md', encoding='utf-8') as f:
    txt = f.read()

checks = [
    ('0.8498', 'OMOP EBGM PR-AUC'),
    ('0.8071', 'OMOP EBGM ROC-AUC'),
    ('0.8313', 'OMOP PRR PR-AUC'),
    ('0.7995', 'OMOP PRR ROC-AUC'),
    ('0.8299', 'OMOP ROR PR-AUC'),
    ('0.7986', 'OMOP ROR ROC-AUC'),
    ('0.9362', 'EU-ADR PRR PR-AUC'),
    ('0.9060', 'EU-ADR PRR ROC-AUC'),
    ('0.9376', 'EU-ADR ROR PR-AUC'),
    ('0.9069', 'EU-ADR ROR ROC-AUC'),
    ('0.8619', 'OMOP EB05 PR-AUC'),
    ('0.8136', 'OMOP EB05 ROC-AUC'),
]
all_ok = True
for val, label in checks:
    ok = val in txt
    print(f'[{"OK" if ok else "MISSING"}] {label}: {val}')
    if not ok:
        all_ok = False

# Check csm label correction in generator script
with open(r'scripts\generate_task_t1_03_figures.py', encoding='utf-8') as f:
    script_txt = f.read()

old_wrong = '"csm_reporter_ratio": "Consumer Reporter Ratio"'
new_correct = '"csm_reporter_ratio": "Health Prof. Reporter Ratio"'
print()
print('[' + ('OK' if old_wrong not in script_txt else 'STILL WRONG') + '] csm label: old wrong label gone')
print('[' + ('OK' if new_correct in script_txt else 'MISSING') + '] csm label: new correct label present')
print()
print('Methods doc OK:', all_ok)
