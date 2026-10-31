import os
from inspect_quarter_schemas import inspect_quarter
from quantify_quarter_metrics import analyze_quarter

inspect_quarter("data/01_raw/sample_quarters/2023q1", "2023Q1")
analyze_quarter("data/01_raw/sample_quarters/2023q1", "2023Q1")
