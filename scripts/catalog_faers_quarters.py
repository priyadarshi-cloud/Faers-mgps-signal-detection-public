import requests
import re
from collections import defaultdict

url = 'https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html'
headers = {'User-Agent': 'Mozilla/5.0'}
r = requests.get(url, headers=headers)
zip_links = set(re.findall(r'href=[\'"]([^\'"]+?\.zip)[\'"]', r.text, re.IGNORECASE))
ascii_links = sorted([l for l in zip_links if 'ascii' in l.lower()])

print(f"Total unique ASCII zip links: {len(ascii_links)}")
years = defaultdict(list)
for l in ascii_links:
    m = re.search(r'(\d{4})[Qq]?(\d)?', l)
    if m:
        yr = m.group(1)
        qtr = m.group(2) if m.group(2) else '?'
        years[yr].append((qtr, l))

for yr in sorted(years.keys()):
    qtrs = [f"Q{q}" for q, _ in sorted(years[yr])]
    sample_url = years[yr][0][1]
    print(f"Year {yr}: {len(years[yr])} quarters ({', '.join(qtrs)}) | Sample: {sample_url}")
