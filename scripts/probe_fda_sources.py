"""
Probe FDA official sources: Drugs@FDA and SrLC.
"""
import requests
import re
import json

def probe_drugsatfda():
    url = "https://www.fda.gov/drugs/drug-approvals-and-databases/drugsatfda-data-files"
    try:
        r = requests.get(url, timeout=15)
        print(f"Drugs@FDA page status: {r.status_code}")
        # Find links
        links = re.findall(r'href=[\'"]([^\'"]*?(?:download|\.zip)[^\'"]*?)[\'"]', r.text, re.IGNORECASE)
        print("Drugs@FDA download links found:")
        for l in links[:5]:
            print("  ", l)
    except Exception as e:
        print(f"Drugs@FDA error: {e}")

def probe_srlc():
    url = "https://www.accessdata.fda.gov/scripts/cder/safetylabelingchanges/"
    try:
        r = requests.get(url, timeout=15)
        print(f"\nFDA SrLC main page status: {r.status_code}")
        links = re.findall(r'href=[\'"]([^\'"]*?(?:download|export|\.csv|\.xlsx|\.zip)[^\'"]*?)[\'"]', r.text, re.IGNORECASE)
        print("SrLC download/export links found:")
        for l in links[:5]:
            print("  ", l)
    except Exception as e:
        print(f"SrLC error: {e}")

if __name__ == "__main__":
    probe_drugsatfda()
    probe_srlc()
