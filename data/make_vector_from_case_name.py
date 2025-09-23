
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from pathlib import Path

# 입력 파일 (전체 판례)
SRC = Path("out/20250923_155434/all_docs.jsonl")
# 출력 파일 (벡터DB용)
DST = SRC.parent / "vector_docs.jsonl"

kept = 0
total = 0

with SRC.open("r", encoding="utf-8") as fin, DST.open("w", encoding="utf-8") as fout:
    for line in fin:
        total += 1
        doc = json.loads(line)

        text = (doc.get("text") or "").strip()
        if not text:   # 본문(text) 없으면 제외
            continue

        fout.write(json.dumps(doc, ensure_ascii=False) + "\n")
        kept += 1

print(f"[done] 입력 {total}건 중 text 있는 {kept}건 → {DST}")



# --------------
# 원래 해야되는 거 
#------------
# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-

# import json, re
# from pathlib import Path

# # 입력(전체 판례): all_docs.jsonl (오탈자 없이 경로 맞추세요)
# SRC = Path("out/20250923_150901/all_docs.jsonl")
# # 출력(벡터DB용): 조건 통과 건만 저장
# DST = SRC.parent / "vector_docs.jsonl"

# CUTOFF_ISO = "2022-01-27"
# CUTOFF_RAW = "20220127"  # decision_date가 yyyyMMdd일 때 비교
# # '중대재해처벌', '중대 재해 처벌' 등 변형 허용(대소문자 무시)
# CASE_NAME_RE = re.compile(r"중대\s*재해\s*처벌", re.IGNORECASE)

# def cmp_iso(a: str, b: str) -> int:
#     # yyyy-mm-dd 비교
#     return (a > b) - (a < b)

# def cmp_raw(a: str, b: str) -> int:
#     # yyyyMMdd 비교 (숫자/문자 비교 모두 안전하게 동작)
#     return (a > b) - (a < b)

# kept = 0
# total = 0

# with SRC.open("r", encoding="utf-8") as fin, DST.open("w", encoding="utf-8") as fout:
#     for line in fin:
#         total += 1
#         doc = json.loads(line)
#         case_name = (doc.get("case_name") or "").strip()
#         # 1) 사건명에 '중대재해처벌' 포함?
#         if not CASE_NAME_RE.search(case_name):
#             continue

#         # 2) 날짜 조건: decision_date_iso 우선, 없으면 decision_date 사용
#         iso = (doc.get("decision_date_iso") or "").strip()
#         raw = (doc.get("decision_date") or "").strip()

#         date_ok = False
#         if iso and re.match(r"^\d{4}-\d{2}-\d{2}$", iso):
#             date_ok = (cmp_iso(iso, CUTOFF_ISO) >= 0)
#         elif raw and re.match(r"^\d{8}$", raw):
#             date_ok = (cmp_raw(raw, CUTOFF_RAW) >= 0)

#         if not date_ok:
#             continue

#         # 조건 통과 → 쓰기
#         fout.write(json.dumps(doc, ensure_ascii=False) + "\n")
#         kept += 1

# print(f"[done] 입력 {total}건 중 조건 통과 {kept}건 → {DST}")
