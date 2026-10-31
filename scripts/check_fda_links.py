import requests
import re
import json

urls_to_check = [
    'https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html',
    'https://www.fda.gov/drugs/questions-and-answers-fdas-adverse-event-reporting-system-faers/fda-adverse-event-reporting-system-faers-latest-quarterly-data-files'
]
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

for u in urls_to_check:
    print(f"=== Checking {u} ===")
    try:
        r = requests.get(u, headers=headers, timeout=15)
        print(f"Status: {r.status_code}, Length: {len(r.text)}")
        zip_links = re.findall(r'href=[\'"]([^\'"]+?\.zip)[\'"]', r.text, re.IGNORECASE)
        print(f"Total zip links found: {len(zip_links)}")
        ascii_zips = [l for l in zip_links if 'ascii' in l.lower()]
        print(f"ASCII zip links found: {len(ascii_zips)}")
        for l in ascii_zips[:10]:
            print(f"  {l}")
        if not ascii_zips and zip_links:
            for l in zip_links[:10]:
                print(f"  {l}")
    except Exception as e:
        print(f"Error: {e}")
