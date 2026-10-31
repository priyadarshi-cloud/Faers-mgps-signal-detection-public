import os

def inspect_dir(path):
    print(f"=== Inspecting {path} ===")
    for root, dirs, files in os.walk(path):
        for f in sorted(files):
            full = os.path.join(root, f)
            sz_mb = os.path.getsize(full) / (1024 * 1024)
            rel = os.path.relpath(full, path)
            print(f"  {rel:35s} {sz_mb:8.2f} MB")

inspect_dir("data/01_raw/sample_quarters/2014q1")
inspect_dir("data/01_raw/sample_quarters/2019q1")
