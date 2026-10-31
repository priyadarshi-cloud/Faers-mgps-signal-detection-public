"""
Verify official FDA FAERS links for all 40 quarters (2014Q1 - 2023Q4).
"""
import requests
import re
import json

def main():
    url = 'https://fis.fda.gov/extensions/FPD-QDE-FAERS/FPD-QDE-FAERS.html'
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(url, headers=headers)
    print(f"Official FIS page status: {r.status_code}")

    zip_links = set(re.findall(r'href=[\'"]([^\'"]+?\.zip)[\'"]', r.text, re.IGNORECASE))
    ascii_links = [l for l in zip_links if 'ascii' in l.lower()]
    print(f"Total ASCII ZIP links found on official FDA page: {len(ascii_links)}")

    mapping = {}
    for l in ascii_links:
        m = re.search(r'(\d{4})[Qq](\d)', l)
        if m:
            key = f"{m.group(1)}Q{m.group(2)}"
            mapping[key] = l

    quarters_40 = [f"{y}Q{q}" for y in range(2014, 2024) for q in range(1, 5)]
    found = [q for q in quarters_40 if q in mapping]
    missing = [q for q in quarters_40 if q not in mapping]

    print(f"All 40 target quarters in 2014Q1-2023Q4 found in FDA page: {len(found)} / 40")
    if missing:
        print(f"Missing quarters from FDA page: {missing}")
    else:
        print("SUCCESS: 100% of the 40 quarters (2014Q1 to 2023Q4) are verified on official FDA page.")

    # Print first 5 and last 5
    print("\nSample verified URLs:")
    for q in quarters_40[:5]:
        print(f"  {q}: {mapping[q]}")
    for q in quarters_40[-5:]:
        print(f"  {q}: {mapping[q]}")

if __name__ == '__main__':
    main()
