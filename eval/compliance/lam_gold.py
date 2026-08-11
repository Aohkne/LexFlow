"""Bóc comment pháp lý từ docx thành gold.jsonl — nhãn người đầu tiên của dự án.

Chạy:  uv run python eval/compliance/lam_gold.py
Ghi:   eval/compliance/gold.jsonl  (GITIGNORE — chứa nguyên văn hợp đồng thật)

Lớp `chuan_hoa` chỉ sống ở đây: comment là văn nói ("NĐ 52", "điều 3"),
citation.py lõi đo ni cho văn luật chuẩn — không nới lõi.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.compliance.docx_doc import doc_docx
from app.compliance.hop_dong import dieu_chua_doan, parse_hop_dong
from app.ontology.citation import parse_citations, to_node_ids

#: Văn bản có mặt trong corpus LanceDB — đối chiếu Task 4 Step 1. Cập nhật tay khi corpus đổi.
SO_HIEU_CORPUS = {"52/2024/NĐ-CP", "40/2024/TT-NHNN", "15/2024/TT-NHNN", "18/2024/TT-NHNN"}

_NOI_BO_RE = re.compile(r"NVQĐ|HĐ khung|PPC ban hành|quy định nội bộ", re.I)
_LAM_RO_RE = re.compile(r"làm rõ|xác nhận|lưu ý|xin ý kiến", re.I)


def chuan_hoa(text: str) -> str:
    text = re.sub(r"\bNĐ\s+(?=\d)", "Nghị định ", text)
    text = re.sub(r"\bTT\s+(?=\d)", "Thông tư ", text)
    text = text.replace("TT_NHNN", "TT-NHNN")
    text = re.sub(r"\bđiều\b", "Điều", text)
    return text


def loai_so_bo(refs: list[str], text: str) -> str:
    if refs:
        return "phap_ly"
    if _NOI_BO_RE.search(text):
        return "noi_bo"
    if _LAM_RO_RE.search(text):
        return "lam_ro"
    return "van_phong"


def _refs_cua(comment_text: str) -> tuple[list[str], list[str]]:
    """→ (khoá node, số hiệu văn bản). Chỉ nhận ref có van_ban tường minh —
    comment không có ngữ cảnh 'Điều này' để suy."""
    khoa, vb = [], []
    for r in parse_citations(chuan_hoa(comment_text)):
        if not r.van_ban:
            continue
        vb.append(r.van_ban)
        khoa += to_node_ids(r, ctx_so_hieu=r.van_ban)
    return sorted(set(khoa)), sorted(set(vb))


def boc_gold(docx_path: Path, so_hieu_corpus: set[str] = SO_HIEU_CORPUS) -> list[dict]:
    doan, binh_luan = doc_docx(docx_path)
    hd = parse_hop_dong(docx_path)
    neo: dict[str, list[int]] = {}
    for d in doan:
        for cid in d.comment_ids:
            neo.setdefault(cid, []).append(d.idx)
    rows = []
    for bl in binh_luan:
        if not bl.text:
            continue
        idxs = neo.get(bl.id, [])
        dieu = dieu_chua_doan(hd, idxs[0]) if idxs else None
        refs, vb = _refs_cua(bl.text)
        rows.append({
            "file": docx_path.name,
            "comment_id": bl.id,
            "author": bl.author,
            "dieu_hop_dong": dieu.so if dieu else None,
            "anchor_text": " ".join(doan[i].text for i in idxs)[:500],
            "comment_text": bl.text,
            "refs": refs,
            "van_ban": vb,
            "loai": loai_so_bo(refs, bl.text),
            "trong_corpus": bool(vb) and all(v in so_hieu_corpus for v in vb),
        })
    return rows


if __name__ == "__main__":
    out = Path("eval/compliance/gold.jsonl")
    rows: list[dict] = []
    for f in sorted(Path("docs/compliance").glob("*.docx")):
        rows += boc_gold(f)
    out.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    n = {t: sum(1 for r in rows if r["loai"] == t) for t in
         ("phap_ly", "noi_bo", "lam_ro", "van_phong")}
    print(f"[gold] {out}: {len(rows)} comment — {n}")
