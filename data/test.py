import requests, time, os

OC = os.getenv("OPENLAW_OC")
if not OC:
    raise SystemExit("환경변수 OPENLAW_OC를 설정하세요")

BASE = "https://www.law.go.kr/DRF"

def fetch_ids():
    ids = []
    page = 1
    while True:
        params = {
            "OC": OC,
            "target": "prec",
            "type": "JSON",
            "query": "중대재해처벌",
            "search": 2,
            "display": 100,
            "page": page,
        }
        r = requests.get(f"{BASE}/lawSearch.do", params=params, timeout=10)
        r.raise_for_status()
        j = r.json()["PrecSearch"]
        items = j.get("prec", [])
        if not items:
            break
        for it in items:
            ids.append(it["판례일련번호"])
        print(f"page={page}, 누적 {len(ids)}건")
        page += 1
        time.sleep(0.5)
    return ids

def fetch_detail(prec_id):
    params = {"OC": OC, "target": "prec", "type": "XML", "ID": prec_id}
    r = requests.get(f"{BASE}/lawService.do", params=params, timeout=10)
    r.raise_for_status()
    return r.text

if __name__ == "__main__":
    ids = fetch_ids()
    print("총 판례 수:", len(ids))

    for pid in ids:
        xml_text = fetch_detail(pid)
        with open(f"prec_{pid}.xml", "w", encoding="utf-8") as f:
            f.write(xml_text)
        print("저장:", pid)
        time.sleep(0.5)
