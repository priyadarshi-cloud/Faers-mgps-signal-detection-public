import requests

urls = [
    'https://fis.fda.gov/content/Exports/aers_ascii_2012q1.zip',
    'https://fis.fda.gov/content/Exports/faers_ascii_2014q1.zip',
    'https://fis.fda.gov/content/Exports/faers_ascii_2018q1.zip',
    'https://fis.fda.gov/content/Exports/faers_ascii_2021Q1.zip',
    'https://fis.fda.gov/content/Exports/faers_ascii_2024Q1.zip'
]
headers = {'User-Agent': 'Mozilla/5.0'}

for u in urls:
    try:
        r = requests.head(u, headers=headers, timeout=10)
        size_mb = int(r.headers.get('content-length', 0)) / (1024 * 1024)
        accept_ranges = r.headers.get('accept-ranges', 'none')
        print(f"{u.split('/')[-1]}: {size_mb:.2f} MB | Accept-Ranges: {accept_ranges} | Status: {r.status_code}")
    except Exception as e:
        print(f"Error checking {u}: {e}")
