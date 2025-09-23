#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json, re, uuid
from pathlib import Path

SRC = Path("out/20250923_155434/vector_docs.jsonl")   # 경로 맞추세요
DST = SRC.parent / "vector_chunks.jsonl"

# 파라미터
CHUNK_SIZE = 1200     # 권장 800~1200
OVERLAP = 150         # 권장 100~200
MIN_CHARS = 200       # 너무 짧은 건 한 청크로

def normalize_ws(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def split_into_chunks(text: str, chunk_size: int, overlap: int):
    text = normalize_ws(text)
    if len(text) <= max(chunk_size, MIN_CHARS):
        return [text] if text else []
    out, i, n = [], 0, len(text)
    while i < n:
        j = min(i + chunk_size, n)
        out.append(text[i:j])
        if j == n:
            break
        i = j - overlap if overlap > 0 else j
        if i < 0:
            i = 0
    return out

def main():
    total_docs = 0
    total_chunks = 0

    with SRC.open("r", encoding="utf-8") as fin, DST.open("w", encoding="utf-8") as fout:
        for line in fin:
            doc = json.loads(line)
            text = (doc.get("text") or "").strip()
            if not text:
                continue

            parent_id = doc.get("id") or f"prec:{doc.get('prec_id')}"
            chunks = split_into_chunks(text, CHUNK_SIZE, OVERLAP)
            if not chunks:
                continue

            meta = {
                "prec_id": doc.get("prec_id"),
                "case_no": doc.get("case_no"),
                "case_name": doc.get("case_name"),
                "court": doc.get("court"),
                "decision_date": doc.get("decision_date"),
                "decision_date_iso": doc.get("decision_date_iso"),
                "source": doc.get("source"),
            }

            for idx, c in enumerate(chunks):
                # 안정적인 재현을 위해 parent_id+index로 UUID5 생성
                cid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{parent_id}#{idx}"))
                rec = {
                    "id": cid,                   # 청크 고유 ID
                    "parent_id": parent_id,      # 원문 문서 ID
                    "chunk_index": idx,          # 청크 순번
                    "text": c,                   # 임베딩할 텍스트
                    "metadata": meta,            # 메타데이터
                }
                fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
                total_chunks += 1

            total_docs += 1

    print(f"[done] 문서 {total_docs}건 → 청크 {total_chunks}개 → {DST}")

if __name__ == "__main__":
    main()
