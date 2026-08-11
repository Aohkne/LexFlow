"""Cắt hợp đồng docx thành điều — đầu vào runtime của pipeline GraphCompliance.

Tách khỏi phần gold (eval/compliance/lam_gold.py): cắm hợp đồng mới không kéo
theo phần nhãn. Đề mục thấy trong 2 hợp đồng mẫu: "Điều N." / "ĐIỀU N:".
"""
from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel

from app.compliance.docx_doc import doc_docx
from app.core.schemas import Article, CorpusDocument

_DIEU_RE = re.compile(r"^\s*(?:Điều|ĐIỀU)\s+(\d+)\s*[.:]?\s*(.*)$")


class DieuHopDong(BaseModel):
    so: str
    tieu_de: str
    text: str
    doan: tuple[int, int]


class HopDong(BaseModel):
    ten: str
    dieu: list[DieuHopDong]


def parse_hop_dong(path: Path) -> HopDong:
    doan, _ = doc_docx(path)
    moc: list[tuple[int, str, str]] = []  # (idx đoạn, số, tiêu đề)
    for d in doan:
        m = _DIEU_RE.match(d.text)
        if m:
            moc.append((d.idx, m.group(1), m.group(2).strip()))
    ra: list[DieuHopDong] = []
    for i, (idx, so, tieu_de) in enumerate(moc):
        end = moc[i + 1][0] if i + 1 < len(moc) else len(doan)
        text = "\n".join(d.text for d in doan[idx:end])
        ra.append(DieuHopDong(so=so, tieu_de=tieu_de, text=text, doan=(idx, end)))
    return HopDong(ten=path.stem, dieu=ra)


def dieu_chua_doan(hd: HopDong, idx: int) -> DieuHopDong | None:
    return next((d for d in hd.dieu if d.doan[0] <= idx < d.doan[1]), None)


def to_corpus_document(hd: HopDong) -> CorpusDocument:
    """Cầu sang đường cũ: run_review nhận CorpusDocument.

    doc_type/source: CorpusDocument kế thừa DocumentMeta, đòi doc_type bắt buộc.
    Hợp đồng không phải văn bản pháp luật — "Hợp đồng" + source="internal" (tài
    liệu nội bộ đưa vào đối chiếu) là giá trị trung thực, không phải suy đoán.
    """
    return CorpusDocument(
        doc_id=hd.ten,
        title=hd.ten,
        doc_type="Hợp đồng",
        source="internal",
        articles=[
            Article(article=f"Điều {d.so}", text=d.text) for d in hd.dieu
        ],
    )
