import os
import time
import requests
import zipfile

dest_dir = r"data/01_raw/sample_quarters"
os.makedirs(dest_dir, exist_ok=True)

# Let's inspect 2014Q1 and 2021Q1 (or 2018Q1 and 2023Q1)
quarters_to_fetch = [
    ("2014q1", "https://fis.fda.gov/content/Exports/faers_ascii_2014q1.zip"),
    ("2019q1", "https://fis.fda.gov/content/Exports/faers_ascii_2019Q1.zip"),
    ("2023q1", "https://fis.fda.gov/content/Exports/faers_ascii_2023Q3.zip"),
]

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

for q_name, url in quarters_to_fetch[:2]: # start with first 2
    zip_path = os.path.join(dest_dir, f"{q_name}.zip")
    extract_path = os.path.join(dest_dir, q_name)

    if os.path.exists(extract_path) and os.listdir(extract_path):
        print(f"[{q_name}] Already extracted at {extract_path}")
        continue

    print(f"[{q_name}] Downloading from {url}...")
    t0 = time.time()
    try:
        r = requests.get(url, headers=headers, stream=True, timeout=60)
        r.raise_for_status()
        with open(zip_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
        size_mb = os.path.getsize(zip_path) / (1024*1024)
        print(f"[{q_name}] Downloaded {size_mb:.2f} MB in {time.time()-t0:.1f}s")

        # Extract
        print(f"[{q_name}] Extracting...")
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_path)
        print(f"[{q_name}] Extracted successfully to {extract_path}")

    except Exception as e:
        print(f"[{q_name}] Error: {e}")
