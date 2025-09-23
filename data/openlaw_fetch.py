import os
import json
import time
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from dotenv import load_dotenv

# ----------------------------
# 환경설정
# ----------------------------
load_dotenv()
OC = os.getenv("OPENLAW_OC")
if not OC:
    raise SystemExit("환경변수 OPENLAW_OC 가 없습니다. .env 파일에 OPENLAW_OC=... 를 넣어주세요.")

BASE = "https://www.law.go.kr/DRF"  # 반드시 https
OUT_DIR = Path(".")  # 현재 폴더
RAW_DIR = OUT_DIR / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "SafeOn-RAG/1.0 (+https://safeon.example)",
    "Accept": "application/json",  # JSON 명시
}
TIMEOUT = 15


# ----------------------------
# 유틸: HTTP 요청 (리트라이)
# ----------------------------
class OpenLawError(Exception):
    pass


@retry(
    reraise=True,
    retry=retry_if_exception_type((requests.RequestException, OpenLawError)),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(4),
)
def _get(url: str, params: dict):
    r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    ct = r.headers.get("Content-Type", "")
    if r.status_code != 200:
        # HTML 에러 페이지 앞부분 로깅
        raise OpenLawError(f"HTTP {r.status_code} (CT={ct}) :: {r.text[:1000]}")
    try:
        return r.json()
    except ValueError:
        # 인증 실패/권한 미승인/IP 문제 시 HTML이 옴
        raise OpenLawError(f"JSON 아님 (CT={ct}) :: {r.text[:1000]}")


# ----------------------------
# 1) 법령 검색 → 법령ID 추출
# ----------------------------
def search_law_ids(query: str, display: int = 100, page: int = 1):
    """
    lawSearch.do 로 '법령' 검색. 결과에서 (법령ID, 법령명, 시행일자 등) 리스트 반환
    """
    url = f"{BASE}/lawSearch.do"
    params = {
        "OC": OC,
        "target": "law",
        "type": "JSON",
        "query": query,
        "display": display,
        "page": page,
    }
    data = _get(url, params)

    items = []

    # 응답 컨테이너 탐색 (버전/형식에 따라 다름)
    container = None
    for k in ("LawSearch", "law", "laws", "법령목록", "Search"):
        if k in data:
            container = data[k]
            break
    if container is None:
        if isinstance(data, list):
            container = data
        else:
            container = []

    # 항목 정규화
    def norm(item: dict):
        name = (
            item.get("법령명한글") or
            item.get("법령명") or
            item.get("lawName") or
            item.get("name") or
            item.get("법령약칭명")
        )
        type_name = (
            item.get("법령구분명") or
            item.get("법령종류명") or
            item.get("typeName")
        )
        return {
            "lawId": item.get("법령ID") or item.get("lawId") or item.get("ID"),
            "lawName": name,
            "enforceDate": item.get("시행일자") or item.get("enforcementDate"),
            "promulgationDate": item.get("공포일자") or item.get("promulgationDate"),
            "type": type_name,
        }

    if isinstance(container, dict):
        arr = container.get("law") or container.get("목록") or container.get("list") or []
    else:
        arr = container

    for it in arr:
        if isinstance(it, dict):
            items.append(norm(it))

    return items


def pick_best_match(items, target_name: str):
    """
    검색 결과에서 원하는 법령명(공백/대괄호 차이 허용)과 가장 잘 맞는 것을 고름
    """
    def normalize_name(s: str):
        return "".join((s or "").split()).replace("「", "").replace("」", "").lower()

    target_norm = normalize_name(target_name)

    # 1) 완전 일치
    for it in items:
        if normalize_name(it.get("lawName")) == target_norm:
            return it
    # 2) 부분 일치
    for it in items:
        if target_norm in normalize_name(it.get("lawName")):
            return it
    # 3) 없으면 첫 번째
    return items[0] if items else None


# ----------------------------
# 2) 법령 본문 조회
# ----------------------------
def fetch_law_body(law_id: str):
    """
    lawService.do 로 '법령 본문(JSON)' 조회
    """
    url = f"{BASE}/lawService.do"
    params = {
        "OC": OC,
        "target": "law",
        "type": "JSON",
        "ID": law_id,  # 법령ID
    }
    return _get(url, params)


# ----------------------------
# 실행: 중대재해처벌법 + 시행령
# ----------------------------
def main():
    targets = [
        "중대재해 처벌 등에 관한 법률",        # 본법
        "중대재해 처벌 등에 관한 법률 시행령",  # 시행령
    ]

    summary = []
    for name in targets:
        print(f"[검색] {name} …")
        items = search_law_ids(name)
        if not items:
            print(f"  → 검색 결과가 없습니다.")
            continue

        best = pick_best_match(items, name)
        if not best or not best.get("lawId"):
            print(f"  → 적절한 항목을 찾지 못했습니다. (best={best})")
            continue

        law_id = best["lawId"]
        law_name = best.get("lawName") or name  # 이름이 비어오면 검색어로 대체
        print(f"  → 선택: {law_name} (법령ID={law_id})")

        print(f"[본문 조회] {law_name} …")
        body = fetch_law_body(law_id)

        # 저장
        safe_name = "".join(c for c in (law_name or "law") if c.isalnum())
        out_path = RAW_DIR / f"{safe_name}_{law_id}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(body, f, ensure_ascii=False, indent=2)

        print(f"  → 저장 완료: {out_path.resolve()}")
        summary.append({"name": law_name, "lawId": law_id, "file": str(out_path)})

        # API 예절상 잠깐 쉼
        time.sleep(0.6)

    print("\n=== 요약 ===")
    for s in summary:
        print(f"- {s['name']} (ID={s['lawId']}) → {s['file']}")


if __name__ == "__main__":
    main()

