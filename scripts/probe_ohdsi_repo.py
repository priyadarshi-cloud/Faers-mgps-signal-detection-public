import requests

urls = [
    "https://raw.githubusercontent.com/OHDSI/MethodEvaluation/main/data/omopReferenceSet.rda",
    "https://raw.githubusercontent.com/OHDSI/MethodEvaluation/master/data/omopReferenceSet.rda",
    "https://api.github.com/repos/OHDSI/MethodEvaluation/contents/data",
    "https://api.github.com/repos/OHDSI/MethodEvaluation/contents/inst/csv"
]
headers = {'User-Agent': 'Mozilla/5.0'}

for u in urls:
    try:
        r = requests.get(u, headers=headers, timeout=10)
        print(f"URL: {u} | Status: {r.status_code} | Length: {len(r.content)}")
        if r.status_code == 200 and 'api.github.com' in u:
            items = r.json()
            if isinstance(items, list):
                print("  Files:")
                for item in items:
                    print("   -", item.get('name'), item.get('download_url'))
    except Exception as e:
        print(f"Error {u}: {e}")
