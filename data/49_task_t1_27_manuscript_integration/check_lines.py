with open('data/41_task_t1_19_residual_claim_check/manuscript_coauthor_review_candidate.md', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("Line 17:", repr(lines[16]))
print("Line 19:", repr(lines[18]))
print("Line 182-183:", repr(lines[181:184]))
print("Line 205:", repr(lines[204]))
