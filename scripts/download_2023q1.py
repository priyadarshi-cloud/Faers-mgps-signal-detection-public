import os
import time
import requests
import zipfile

dest_dir = r"data/01_raw/sample_quarters"
os.makedirs(dest_dir, exist_ok=True)

q_name = "2023q1"
url = "https://fis.fda.gov/content/Exports/faers_ascii_2023Q1.zip"
zip_path = os.path.join(dest_dir, f"{q_name}.zip")
extract_path = os.path.join(dest_dir, q_name)

headers = {'User-Agent': 'Mozilla/5.0'}
if not (os.path.exists(extract_path) and os.listdir(extract_path)):
    print(f"Downloading {url}...")
    t0 = time.time()
    r = requests.get(url, headers=headers, stream=True, timeout=120)
    if r.status_code != 200:
        # Try lowercase
        url = "https://fis.fda.gov/content/Exports/faers_ascii_2023q1.zip"
        r = requests.get(url, headers=headers, stream=True, timeout=120)
    r.raise_for_status()
    with open(zip_path, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024*1024):
            if chunk:
                f.write(chunk)
    print(f"Downloaded {os.path.getsize(zip_path)/(1024*1024):.2f} MB in {time.time()-t0:.1f}s")
    print("Extracting...")
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(extract_path)
    print("Extracted successfully.")
else:
    print(f"Already extracted at {extract_path}")
