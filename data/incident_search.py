#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
1) '중대재해' + '산업안전보건법위반' 두 가지 쿼리로 판례 전체 수집
2) 합쳐서 중복 제거 후 all_docs.jsonl 저장
3) (옵션) 필터 및 청크 처리 그대로 적용 가능

출력:
  out/<ts>/all_docs.jsonl
"""

import os, re, json, time, argparse, html, uuid
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional
import requests, xml.etree.ElementTree as ET

# ----------------------------
# 설정
# ----------------------------
OC = os.getenv("OPENLAW_OC")
if not OC:
    raise SystemExit("환경변수 OPENLAW_OC 가 없습니다. export OPENLAW_OC=... 로 설정하세요.")

BASE = "https://www.law.go.kr/DRF"
HEADERS = {"User-Agent": "CJSAPA-precets/1.2 (+local)"}
TIMEOUT = 25

# ----------------------------
# 공통 함수
# ----------------------------
def http_get(url: str, params: Dict[str, Any]) -> requests.Response:
    r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r

def strip_tags(text: str) -> str:
    if not text: return ""
    t = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return html.unescape(t).strip()

def parse_date_yyyymmdd(s: str) -> Optional[str]:
    if not s: return None
    m = re.match(r"^(\d{4})(\d{2})(\d{2})$", s)
    if not m: return None
    y, mm, dd = m.groups()
    return f"{y}-{mm}-{dd}"

META_KEYS = {
    "case_no": ["사건번호","CaseNo","caseNo"],
    "case_name": ["사건명","CaseName","caseName"],
    "court": ["법원명","CourtName","court"],
    "decision_date": ["선고일자","선고일","DecisionDate","decisionDate"],
}
TEXT_FIELDS = ["판시사항","주문","이유","요지","전문","참조조문","참조판례"]

def fetch_all_ids(query: str, display: int = 100, delay: float = 0.8) -> List[str]:
    page, ids, seen = 1, [], set()
    while True:
        params = {
            "OC": OC, "target": "prec", "type": "JSON",
            "query": query, "search": 2, "display": display,
            "page": page, "sort": "ddes",
        }
        r = http_get(f"{BASE}/lawSearch.do", params)
        try:
            j = r.json()["PrecSearch"]
            items = j.get("prec", [])
            if items and not isinstance(items, list):
                items = [items]
        except Exception:
            items = []
        if not items:
            break
        new = 0
        for it in items:
            pid = it.get("판례일련번호") or it.get("ID") or it.get("판례ID")
            if pid and pid not in seen:
                seen.add(pid)
                ids.append(pid)
                new += 1
        print(f"[{query}] page={page} got={len(items)} new={new} total={len(ids)}")
        page += 1
        time.sleep(delay)
    return ids

def fetch_detail(prec_id: str, delay: float = 0.5) -> Dict[str, Any]:
    payload = {"prec_id": str(prec_id)}
    r = http_get(f"{BASE}/lawService.do", {"OC":OC,"target":"prec","type":"JSON","ID":prec_id})
    try:
        j = r.json()
        root = j.get("PrecService") or j
        if isinstance(root, list) and root: root = root[0]
    except Exception:
        root = {}
    for k, cands in META_KEYS.items():
        for ck in cands:
            if root.get(ck):
                payload[k] = root[ck].strip()
                break
    parts = []
    for tf in TEXT_FIELDS:
        if root.get(tf):
            parts.append(f"## {tf}\n{root[tf]}")
    raw = "\n\n".join(parts)
    payload["text"] = strip_tags(raw)
    di = payload.get("decision_date") or ""
    payload["decision_date_iso"] = parse_date_yyyymmdd(di) or di
    time.sleep(delay)
    return payload

# ----------------------------
# 메인
# ----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--display", type=int, default=100)
    ap.add_argument("--delay", type=float, default=0.8)
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    outdir = Path(args.outdir) if args.outdir else Path("out") / ts
    outdir.mkdir(parents=True, exist_ok=True)
    all_path = outdir / "all_docs.jsonl"

    queries = ["중대재해", "산업안전보건법위반"]
    all_ids, seen = [], set()
    for q in queries:
        ids = fetch_all_ids(q, display=args.display, delay=args.delay)
        for i in ids:
            if i not in seen:
                seen.add(i)
                all_ids.append(i)
    print(f"[merge] 전체 ID 합계={len(all_ids)}")

    with all_path.open("w", encoding="utf-8") as f:
        for i, pid in enumerate(all_ids, 1):
            try:
                d = fetch_detail(pid, delay=args.delay)
                doc = {
                    "id": f"prec:{pid}",
                    "prec_id": pid,
                    "case_no": d.get("case_no",""),
                    "case_name": d.get("case_name",""),
                    "court": d.get("court",""),
                    "decision_date": d.get("decision_date",""),
                    "decision_date_iso": d.get("decision_date_iso",""),
                    "text": d.get("text",""),
                    "source": "open.law.go.kr",
                }
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")
                if i % 20 == 0:
                    print(f"[save] {i}/{len(all_ids)}")
            except Exception as e:
                print(f"[error] {pid}: {e}")

    print(f"[done] 최종 all_docs.jsonl → {all_path}")

if __name__ == "__main__":
    main()

# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-

# """
# 1) '중대재해'로 본문검색한 판례를 전량 수집(목록→본문)
# 2) 전체 코퍼스 1파일(JSONL)로 저장
# 3) 조건 필터(선고일자 >= 2022-01-27 & 본문에 '중대재해처벌' 포함)해 vectorDB용 파일 생성
# 4) (옵션) 청크 파일까지 생성

# 출력:
#   out/<ts>/all_docs.jsonl           # 전체 판례(문서 단위)
#   out/<ts>/vector_docs.jsonl        # 필터 조건 통과(문서 단위)
#   out/<ts>/vector_chunks.jsonl      # (--chunk-size 지정 시) 필터 통과 청크

# 필수 환경변수:
#   OPENLAW_OC  (open.law.go.kr OC 키)
# """

# from __future__ import annotations
# import os, re, json, time, argparse, html, uuid
# from pathlib import Path
# from datetime import datetime
# from typing import Any, Dict, List, Optional
# import requests
# import xml.etree.ElementTree as ET

# # ----------------------------
# # 설정/유틸
# # ----------------------------
# OC = os.getenv("OPENLAW_OC")
# if not OC:
#     raise SystemExit("환경변수 OPENLAW_OC 가 없습니다.  export OPENLAW_OC=...  로 설정하세요.")

# BASE = "https://www.law.go.kr/DRF"
# HEADERS = {
#     "User-Agent": "CJSAPA-precets/1.1 (+local)",
#     "Accept": "application/json, text/xml, application/xml, */*",
# }
# TIMEOUT = 25

# def http_get(url: str, params: Dict[str, Any], *, retries: int = 5, backoff: float = 0.9) -> requests.Response:
#     last = None
#     for i in range(1, retries+1):
#         try:
#             r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
#             if r.status_code == 200:
#                 return r
#             last = RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
#         except Exception as e:
#             last = e
#         time.sleep(backoff * i)
#     raise RuntimeError(f"GET 실패 {url} params={params} err={last}")

# def strip_tags(text: str) -> str:
#     if not text: return ""
#     t = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
#     t = re.sub(r"<[^>]+>", " ", t)
#     t = html.unescape(t)
#     t = re.sub(r"\r\n?", "\n", t)
#     t = re.sub(r"[ \t]+", " ", t)
#     t = re.sub(r"\n{3,}", "\n\n", t)
#     return t.strip()

# def parse_date_yyyymmdd(s: str) -> Optional[str]:
#     """yyyyMMdd → yyyy-mm-dd (잘못된 값이면 None)"""
#     if not s: return None
#     m = re.match(r"^\s*(\d{4})(\d{2})(\d{2})\s*$", s)
#     if not m: return None
#     y, mm, dd = m.groups()
#     return f"{y}-{mm}-{dd}"

# def cmp_date_iso(a: str, b: str) -> int:
#     """ISO yyyy-mm-dd compare"""
#     return (a > b) - (a < b)

# def chunk_text(s: str, sz: int, overlap: int) -> List[str]:
#     s = s.strip()
#     if sz <= 0 or not s: return [s] if s else []
#     out, i, n = [], 0, len(s)
#     while i < n:
#         j = min(i+sz, n)
#         out.append(s[i:j])
#         if j == n: break
#         i = j - overlap if overlap > 0 else j
#         if i < 0: i = 0
#     return out

# # ----------------------------
# # 검색(목록)
# # ----------------------------
# def fetch_all_ids(query: str, *, display: int = 100, delay: float = 0.8) -> List[str]:
#     page, ids, seen = 1, [], set()
#     while True:
#         params = {
#             "OC": OC, "target": "prec", "type": "JSON",
#             "query": query, "search": 2,  # 본문검색
#             "display": display, "page": page, "sort": "ddes",
#         }
#         r = http_get(f"{BASE}/lawSearch.do", params)
#         ctype = (r.headers.get("Content-Type") or "").lower()
#         items = None
#         if "json" in ctype:
#             try:
#                 j = r.json().get("PrecSearch") or {}
#                 items = j.get("prec", [])
#                 if items and not isinstance(items, list):
#                     items = [items]
#             except Exception:
#                 items = None
#         if items is None:
#             # XML 폴백
#             params["type"] = "XML"
#             r2 = http_get(f"{BASE}/lawSearch.do", params)
#             root = ET.fromstring(r2.text)
#             items = []
#             for p in root.findall(".//prec"):
#                 row = {c.tag: (c.text or "").strip() for c in list(p)}
#                 items.append(row)

#         if not items:
#             print(f"[search] page={page} 결과 없음 → 종료")
#             break

#         new = 0
#         for it in items:
#             pid = it.get("판례일련번호") or it.get("ID") or it.get("판례ID")
#             if pid and pid not in seen:
#                 seen.add(pid)
#                 ids.append(str(pid))
#                 new += 1
#         print(f"[search] page={page} got={len(items)} new={new} total={len(ids)}")
#         page += 1
#         time.sleep(delay)
#     return ids

# # ----------------------------
# # 본문 조회
# # ----------------------------
# META_KEYS = {
#     "case_no": ["사건번호","CaseNo","caseNo"],
#     "case_name": ["사건명","CaseName","caseName"],
#     "court": ["법원명","CourtName","court"],
#     "decision_date": ["선고일자","선고일","DecisionDate","decisionDate"],
# }
# TEXT_FIELDS = ["판시사항","주문","이유","요지","전문","참조조문","참조판례"]

# def parse_detail_json(j: Dict[str,Any]) -> Dict[str,Any]:
#     root = j.get("PrecService") or j.get("Prec") or j
#     if isinstance(root, list) and root: root = root[0]
#     if not isinstance(root, dict): return {}
#     out = {}
#     for k, cands in META_KEYS.items():
#         for ck in cands:
#             if root.get(ck):
#                 out[k] = str(root[ck]).strip()
#                 break
#     parts = []
#     for tf in TEXT_FIELDS:
#         if root.get(tf):
#             parts.append(f"## {tf}\n{str(root[tf])}")
#     if parts:
#         out["raw_text"] = "\n\n".join(parts)
#     return out

# def fetch_detail(prec_id: str, *, delay: float = 0.8) -> Dict[str,Any]:
#     payload = {"prec_id": str(prec_id)}
#     # JSON 시도
#     r = http_get(f"{BASE}/lawService.do", {"OC":OC,"target":"prec","type":"JSON","ID":prec_id})
#     ctype = (r.headers.get("Content-Type") or "").lower()
#     ok = False
#     if "json" in ctype:
#         try:
#             j = r.json()
#             payload.update(parse_detail_json(j))
#             ok = True
#         except Exception:
#             ok = False
#     if not ok:
#         # XML 폴백
#         r2 = http_get(f"{BASE}/lawService.do", {"OC":OC,"target":"prec","type":"XML","ID":prec_id})
#         xml = r2.text
#         def rx(tag):
#             m = re.search(fr"<{tag}>(.*?)</{tag}>", xml, flags=re.S)
#             return strip_tags(m.group(1)) if m else None
#         for k, cands in META_KEYS.items():
#             for ck in cands:
#                 v = rx(ck)
#                 if v:
#                     payload[k] = v
#                     break
#         parts = []
#         for tf in TEXT_FIELDS:
#             m = re.search(fr"<{tf}>(.*?)</{tf}>", xml, flags=re.S)
#             if m:
#                 parts.append(f"## {tf}\n{m.group(1)}")
#         if parts:
#             payload["raw_text"] = "\n\n".join(parts)

#     raw = payload.get("raw_text","")
#     payload["text"] = strip_tags(raw)
#     # 날짜 ISO로 정규화
#     di = payload.get("decision_date") or ""
#     iso = parse_date_yyyymmdd(di) or di  # yyyyMMdd가 아니면 원문 유지
#     payload["decision_date_iso"] = iso
#     time.sleep(delay)
#     return payload

# # ----------------------------
# # 메인
# # ----------------------------
# def main():
#     ap = argparse.ArgumentParser()
#     ap.add_argument("--query", default="중대재해")
#     ap.add_argument("--display", type=int, default=100)
#     ap.add_argument("--delay", type=float, default=0.8)
#     ap.add_argument("--outdir", default=None)
#     ap.add_argument("--chunk-size", type=int, default=0, help=">0 이면 청크 파일 생성")
#     ap.add_argument("--chunk-overlap", type=int, default=100)
#     args = ap.parse_args()

#     ts = datetime.now().strftime("%Y%m%d_%H%M%S")
#     outdir = Path(args.outdir) if args.outdir else Path("out") / ts
#     outdir.mkdir(parents=True, exist_ok=True)

#     all_path   = outdir / "all_docs.jsonl"
#     vec_path   = outdir / "vector_docs.jsonl"
#     chunk_path = outdir / "vector_chunks.jsonl"

#     # 1) ID 전량
#     ids = fetch_all_ids(args.query, display=args.display, delay=args.delay)
#     print(f"[save] ID 수: {len(ids)}")

#     # 2) 본문 수집 → 전체 코퍼스
#     with all_path.open("w", encoding="utf-8") as f:
#         for i, pid in enumerate(ids, 1):
#             try:
#                 d = fetch_detail(pid, delay=args.delay)
#                 doc = {
#                     "id": f"prec:{pid}",
#                     "prec_id": pid,
#                     "case_no": d.get("case_no",""),
#                     "case_name": d.get("case_name",""),
#                     "court": d.get("court",""),
#                     "decision_date": d.get("decision_date",""),
#                     "decision_date_iso": d.get("decision_date_iso",""),
#                     "text": d.get("text",""),
#                     "source": "open.law.go.kr",
#                 }
#                 f.write(json.dumps(doc, ensure_ascii=False) + "\n")
#                 if i % 20 == 0:
#                     print(f"[all] {i}/{len(ids)}")
#             except Exception as e:
#                 print(f"[error] {pid}: {e}")

#     print(f"[done] 전체 코퍼스 → {all_path}")

#     # 3) 벡터DB용 필터: 날짜 & 키워드
#     CUTOFF = "2022-01-27"
#     KEY = "중대재해처벌"

#     kept = 0
#     with all_path.open("r", encoding="utf-8") as fin, vec_path.open("w", encoding="utf-8") as fout:
#         for line in fin:
#             doc = json.loads(line)
#             iso = doc.get("decision_date_iso") or ""
#             txt = doc.get("text","")
#             date_ok = (iso and cmp_date_iso(iso, CUTOFF) >= 0)
#             key_ok  = (KEY in txt)
#             if date_ok and key_ok:
#                 fout.write(json.dumps(doc, ensure_ascii=False) + "\n")
#                 kept += 1
#     print(f"[done] 벡터DB용(조건 통과 {kept}건) → {vec_path}")

#     # 4) (옵션) 청크 생성
#     if args.chunk_size and args.chunk_size > 0:
#         total = 0
#         with vec_path.open("r", encoding="utf-8") as fin, chunk_path.open("w", encoding="utf-8") as fout:
#             for line in fin:
#                 doc = json.loads(line)
#                 text = doc.get("text","")
#                 parent_id = doc["id"]
#                 chunks = chunk_text(text, args.chunk_size, args.chunk_overlap) or [""]
#                 for idx, c in enumerate(chunks):
#                     cid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{parent_id}#{idx}"))
#                     rec = {
#                         "id": cid,
#                         "parent_id": parent_id,
#                         "chunk_index": idx,
#                         "text": c,
#                         "metadata": {
#                             "prec_id": doc.get("prec_id"),
#                             "case_no": doc.get("case_no"),
#                             "case_name": doc.get("case_name"),
#                             "court": doc.get("court"),
#                             "decision_date": doc.get("decision_date"),
#                             "source": doc.get("source"),
#                         },
#                     }
#                     fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
#                     total += 1
#         print(f"[done] 청크 파일({total}개) → {chunk_path}")

# if __name__ == "__main__":
#     main()



# import requests, time, os

# OC = os.getenv("OPENLAW_OC")
# if not OC:
#     raise SystemExit("환경변수 OPENLAW_OC를 설정하세요")

# BASE = "https://www.law.go.kr/DRF"

# def fetch_ids():
#     ids = []
#     page = 1
#     while True:
#         params = {
#             "OC": OC,
#             "target": "prec",
#             "type": "JSON",
#             "query": "중대재해처벌",
#             "search": 2,
#             "display": 100,
#             "page": page,
#         }
#         r = requests.get(f"{BASE}/lawSearch.do", params=params, timeout=10)
#         r.raise_for_status()
#         j = r.json()["PrecSearch"]
#         items = j.get("prec", [])
#         if not items:
#             break
#         for it in items:
#             ids.append(it["판례일련번호"])
#         print(f"page={page}, 누적 {len(ids)}건")
#         page += 1
#         time.sleep(0.5)
#     return ids

# def fetch_detail(prec_id):
#     params = {"OC": OC, "target": "prec", "type": "XML", "ID": prec_id}
#     r = requests.get(f"{BASE}/lawService.do", params=params, timeout=10)
#     r.raise_for_status()
#     return r.text

# if __name__ == "__main__":
#     ids = fetch_ids()
#     print("총 판례 수:", len(ids))

#     for pid in ids:
#         xml_text = fetch_detail(pid)
#         with open(f"prec_{pid}.xml", "w", encoding="utf-8") as f:
#             f.write(xml_text)
#         print("저장:", pid)
#         time.sleep(0.5)






# # incident_search.py
# import os
# import json
# import time
# from pathlib import Path
# from datetime import datetime
# import re

# import requests
# from dotenv import load_dotenv

# # ----------------------------
# # 환경설정
# # ----------------------------
# load_dotenv()
# OC = os.getenv("OPENLAW_OC")
# if not OC:
#     raise SystemExit("환경변수 OPENLAW_OC 가 없습니다. .env 에 OPENLAW_OC=... 를 넣어주세요.")

# BASE = "https://www.law.go.kr/DRF"
# HEADERS = {
#     "User-Agent": "SafeOn-RAG/1.0 (+https://safeon.example)",
#     "Accept": "application/json",
# }
# TIMEOUT = 15

# OUT_DIR = Path(".")
# RUNS_DIR = OUT_DIR / "user_runs"
# RUNS_DIR.mkdir(parents=True, exist_ok=True)

# # ----------------------------
# # 공통 HTTP
# # ----------------------------
# def _get(url: str, params: dict):
#     r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
#     ct = r.headers.get("Content-Type", "")
#     if r.status_code != 200:
#         tgt = params.get("target")
#         hint = ""
#         if r.status_code in (403, 404):
#             if tgt == "prec":
#                 hint = " ← 판례(target=prec) 목록/본문 JSON 서비스가 미승인/비활성일 수 있습니다."
#         raise RuntimeError(f"HTTP {r.status_code} @ {url} (CT={ct}) :: {r.text[:800]}{hint}")
#     try:
#         return r.json()
#     except ValueError:
#         raise RuntimeError(f"JSON 아님 (CT={ct}) @ {url} :: {r.text[:1000]}")

# # ----------------------------
# # 판례 검색/조회 래퍼
# # ----------------------------
# def law_search(target: str, query: str, display: int = 50, page: int = 1):
#     url = f"{BASE}/lawSearch.do"
#     params = {"OC": OC, "target": target, "type": "JSON",
#               "query": query, "display": display, "page": page}
#     return _get(url, params)

# def law_service(target: str, id_value: str):
#     url = f"{BASE}/lawService.do"
#     params = {"OC": OC, "target": target, "type": "JSON", "ID": id_value}
#     return _get(url, params)

# # ----------------------------
# # 사용자 질문 파서 (룰 기반)
# # ----------------------------
# def parse_user_query(user_query: str) -> dict:
#     txt = (user_query or "")
#     low = txt.lower()

#     industry_map = {
#         "construction": ["건설", "현장", "타워크레인", "비계", "거푸집"],
#         "manufacturing": ["제조", "공장", "프레스", "사출", "조립"],
#         "logistics": ["물류", "창고", "상하차", "지게차", "포크리프트"],
#         "transport": ["운수", "버스", "철도", "지하철", "항공", "선박"],
#     }
#     contracting_kw = ["도급", "수급", "하청", "원청", "용역", "파견", "외주"]
#     edu_kw = ["tbm", "툴박스미팅", "교육", "안전보건교육", "정기교육", "특별교육", "점검", "위험성평가", "관리체계"]

#     hazard_map = {
#         "fall": ["추락", "墜落"],
#         "caught-in": ["끼임", "협착", "감김"],
#         "amputation": ["절단", "베임", "절상", "손가락잘림", "절단사고"],
#         "electric": ["감전", "전기쇼크", "누전"],
#         "chemical": ["중독", "화학물질", "유해화학", "가스누출", "질식", "유증기"],
#         "fire": ["화재", "폭발", "폭굉", "발화"],
#         "struck-by": ["낙하", "비래", "충돌", "낙석"],
#         "collapse": ["붕괴", "전도", "좌굴", "함몰"],
#         "noise-dust": ["소음", "분진", "진동"],
#     }

#     found = {
#         "industry": None,
#         "contracting": False,
#         "education": False,
#         "hazards": set(),
#         "extra_keywords": set(),
#     }

#     for ind, kws in industry_map.items():
#         if any(k in txt for k in kws):
#             found["industry"] = ind
#             break

#     if any(k in txt for k in contracting_kw):
#         found["contracting"] = True
#         for k in ["도급", "수급", "하청", "원청"]:
#             if k in txt:
#                 found["extra_keywords"].add(k)

#     if any(k in low for k in edu_kw) or any(k in txt for k in ["TBM", "툴박스미팅", "안전보건교육"]):
#         found["education"] = True
#         for k in ["TBM", "툴박스미팅", "교육", "안전보건교육", "관리체계", "점검", "위험성평가"]:
#             if (k.lower() in low) or (k in txt):
#                 found["extra_keywords"].add(k)

#     for hz_code, kws in hazard_map.items():
#         if any(k in txt for k in kws):
#             found["hazards"].add(hz_code)
#             for k in kws[:2]:
#                 found["extra_keywords"].add(k)

#     for token in re.findall(r"[가-힣A-Za-z0-9]{2,}", txt):
#         found["extra_keywords"].add(token)

#     found["hazards"] = list(found["hazards"])
#     found["extra_keywords"] = list(found["extra_keywords"])
#     return found

# # ----------------------------
# # 정규화: 판례
# # ----------------------------
# def normalize_prec_items(data: dict):
#     arr = []
#     container = data.get("PrecSearch", {}) if isinstance(data, dict) else {}
#     items = container.get("prec") or container.get("목록") or []
#     for it in items:
#         arr.append({
#             "prec_id": it.get("판례일련번호") or it.get("ID"),
#             "case_no": it.get("사건번호"),
#             "case_name": it.get("사건명") or it.get("사건명한글"),
#             "court": it.get("선고법원") or it.get("법원명"),
#             "decision_date": it.get("선고일"),
#             "summary": it.get("판결요지") or it.get("판시사항"),
#             "ref_articles": it.get("참조조문"),
#         })
#     return arr

# # ----------------------------
# # 판례 관련 유틸
# # ----------------------------
# def uniq_by(items, key):
#     seen = set()
#     out = []
#     for x in items:
#         k = x.get(key)
#         if not k or k in seen:
#             continue
#         seen.add(k)
#         out.append(x)
#     return out

# def prec_union_search(queries, display=50):
#     total = []
#     for q in queries:
#         try:
#             data = law_search("prec", q, display=display, page=1)
#             items = normalize_prec_items(data)
#             print(f"[prec] '{q}' → {len(items)}건")
#             total.extend(items)
#             time.sleep(0.2)
#         except Exception as e:
#             print(f"[WARN] 판례 쿼리 실패: {q} :: {e}")
#     total = uniq_by(total, "prec_id")
#     return total

# def filter_prec_by_incident(items, occurred_at: str):
#     if not occurred_at:
#         return items
#     try:
#         cut = datetime.strptime(occurred_at, "%Y-%m-%d").date()
#     except Exception:
#         return items
#     for it in items:
#         dd = it.get("decision_date")
#         try:
#             d = datetime.strptime(dd, "%Y.%m.%d").date() if dd else None
#         except Exception:
#             d = None
#         it["_priority_time"] = 0 if (d and d <= cut) else 1
#     return items

# def simple_keyword_score(text: str, keywords: list[str]) -> int:
#     txt = (text or "")
#     score = 0
#     for k in keywords:
#         if k and (k in txt):
#             score += 1
#     return score

# def rank_precedents(items, user_query: str, incident: dict):
#     kw = []
#     if user_query:
#         kw.append(user_query)
#     if incident.get("contracting"):
#         kw += ["도급", "수급", "안전보건"]
#     if incident.get("industry") == "construction":
#         kw += ["건설", "추락", "가설", "발판"]
#     elif incident.get("industry") == "manufacturing":
#         kw += ["제조", "프레스", "전단", "보호덮개"]
#     if incident.get("hazards"):
#         hzmap = {"fall": "추락", "caught-in": "끼임", "amputation": "절단", "chemical": "중독",
#                  "electric": "감전", "fire": "화재", "collapse": "붕괴", "struck-by": "낙하"}
#         kw += [hzmap.get(h, h) for h in incident["hazards"]]

#     for it in items:
#         base_text = " ".join([
#             it.get("summary") or "",
#             it.get("ref_articles") or "",
#             it.get("case_name") or "",
#         ])
#         kscore = simple_keyword_score(base_text, kw)
#         tscore = 0 if it.get("_priority_time", 1) == 0 else -1
#         it["_score"] = kscore + tscore

#     items.sort(key=lambda x: x.get("_score", 0), reverse=True)
#     for it in items:
#         it.pop("_score", None)
#         it.pop("_priority_time", None)
#     return items

# # ----------------------------
# # 판례 상세 조회/병합
# # ----------------------------
# def fetch_prec_detail(prec_id: str) -> dict:
#     data = law_service("prec", prec_id)
#     svc = data.get("PrecService", {}) if isinstance(data, dict) else {}
#     detail = {
#         "prec_id": prec_id,
#         "court": svc.get("법원명") or svc.get("선고법원"),
#         "decision_date": svc.get("선고일"),
#         "case_no": svc.get("사건번호"),
#         "case_name": svc.get("사건명"),
#         "summary": svc.get("판시사항") or svc.get("판결요지") or svc.get("참조판례"),
#         "ref_articles": svc.get("참조조문"),
#     }
#     return {k: v for k, v in detail.items() if v}

# def enrich_precedents_with_detail(items, max_fetch: int = 10):
#     enriched = []
#     for i, it in enumerate(items[:max_fetch]):
#         pid = it.get("prec_id")
#         try:
#             det = fetch_prec_detail(pid)
#             merged = {**it, **{k: v for k, v in det.items() if v}}
#             enriched.append(merged)
#             time.sleep(0.2)
#         except Exception as e:
#             print(f"[WARN] 판례 상세 실패: {pid} :: {e}")
#             enriched.append(it)
#     enriched.extend(items[max_fetch:])
#     return enriched

# # ----------------------------
# # 쿼리 빌더
# # ----------------------------
# def build_queries(incident: dict, user_query: str = ""):
#     occurred_at = incident.get("occurred_at")
#     uq = parse_user_query(user_query)

#     industry = incident.get("industry") or uq.get("industry")
#     contracting = bool(incident.get("contracting") or uq.get("contracting"))
#     hazards = list(dict.fromkeys((incident.get("hazards") or []) + (uq.get("hazards") or [])))
#     extra_kw = uq.get("extra_keywords") or []

#     base = ["중대재해 처벌 등에 관한 법률"]
#     meta = []

#     if contracting:
#         meta += ["도급", "수급", "안전보건 확보의무", "제4조", "제5조"]
#     if industry == "construction":
#         meta += ["건설", "추락", "발판", "가설구조물"]
#     elif industry == "manufacturing":
#         meta += ["제조", "프레스", "전단기", "보호덮개"]
#     elif industry == "logistics":
#         meta += ["물류", "창고", "상하차", "지게차"]
#     elif industry == "transport":
#         meta += ["운수", "철도", "지하철", "항공", "선박"]

#     hz_ko = {
#         "fall": "추락", "caught-in": "끼임", "amputation": "절단", "electric": "감전",
#         "chemical": "중독", "fire": "화재", "struck-by": "낙하", "collapse": "붕괴", "noise-dust": "분진"
#     }
#     for hz in hazards:
#         if hz in hz_ko:
#             meta.append(hz_ko[hz])

#     prec_queries = [
#         " ".join(base),
#         " ".join(base + ["제4조"]),
#         " ".join(base + ["제5조"]),
#     ]
#     for k in dict.fromkeys(meta):
#         prec_queries.append(" ".join(base + [k]))
#     for k in extra_kw[:5]:
#         prec_queries.append(" ".join(base + [k]))
#     if user_query:
#         prec_queries.append(" ".join(base + [user_query]))

#     prec_queries = list(dict.fromkeys([q for q in prec_queries if q]))

#     return {
#         "occurred_at": occurred_at,
#         "prec_queries": prec_queries,
#         "user_query": user_query,
#         "resolved_meta": {
#             "industry": industry,
#             "contracting": contracting,
#             "hazards": hazards,
#             "extra_keywords": extra_kw,
#         }
#     }

# # ----------------------------
# # 메인 실행 (판례만)
# # ----------------------------
# def run_incident_search(incident: dict, user_query: str = "", top_prec: int = 10):
#     q = build_queries(incident, user_query=user_query)

#     prec_items = []
#     try:
#         prec_items = prec_union_search(q["prec_queries"], display=80)
#         prec_items = filter_prec_by_incident(prec_items, q["occurred_at"])
#         prec_items = rank_precedents(prec_items, q["user_query"], {
#             "industry": q["resolved_meta"]["industry"],
#             "contracting": q["resolved_meta"]["contracting"],
#             "hazards": q["resolved_meta"]["hazards"],
#         })
#         prec_items = enrich_precedents_with_detail(prec_items, max_fetch=top_prec)
#         prec_items = prec_items[:top_prec]
#     except Exception as e:
#         print(f"[WARN] 판례 검색 건너뜀: {e}")

#     run_id = incident.get("incident_id") or f"run-{int(time.time())}"
#     save_dir = RUNS_DIR / run_id
#     save_dir.mkdir(parents=True, exist_ok=True)

#     (save_dir / "incident.json").write_text(json.dumps(incident, ensure_ascii=False, indent=2), encoding="utf-8")
#     out = {
#         "incident_id": run_id,
#         "occurred_at": q["occurred_at"],
#         "user_query": q["user_query"],
#         "queries": {"prec": q["prec_queries"]},
#         "resolved_meta": q["resolved_meta"],
#         "precedents": prec_items,
#         "created_at": datetime.utcnow().isoformat() + "Z",
#     }
#     (save_dir / "search_result.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

#     return out, save_dir

# # ----------------------------
# # 예시 실행
# # ----------------------------
# if __name__ == "__main__":
#     incident = {
#         "incident_id": "INC-2025-0001",
#         "occurred_at": "2024-11-02",
#         "industry": "construction",
#         "headcount": 62,
#         "contracting": True,
#         "hazards": ["fall", "caught-in"],
#     }
#     user_query = "하청 추락사고에서 원청 경영책임자 처벌 기준과 TBM 교육의 영향은?"

#     result, save_path = run_incident_search(incident, user_query=user_query)
#     print(f"[OK] 저장: {save_path/'search_result.json'}")
#     print(json.dumps(result, ensure_ascii=False, indent=2))
