import requests

u = 'https://fis.fda.gov/content/Exports/faers_ascii_2018q1.zip'
headers = {'User-Agent': 'Mozilla/5.0', 'Range': 'bytes=0-1023'}
r = requests.get(u, headers=headers)
print(f"Status: {r.status_code}")
print(f"Content-Range: {r.headers.get('content-range')}")
print(f"Content-Length: {r.headers.get('content-length')}")
print(f"Total size from range: {r.headers.get('content-range', '').split('/')[-1] if 'content-range' in r.headers else 'unknown'}")
