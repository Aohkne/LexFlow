"""Cắt hợp đồng docx thành điều — đầu vào runtime của pipeline GraphCompliance.

Tách khỏi phần gold (eval/compliance/lam_gold.py): cắm hợp đồng mới không kéo
theo phần nhãn. Đề mục thấy trong 2 hợp đồng mẫu: "Điều N." / "ĐIỀU N:".
"""
from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel

from app.compliance.docx_doc import doc_docx, doc_numbering
from app.core.schemas import Article, CorpusDocument

_DIEU_RE = re.compile(r"^\s*(?:Điều|ĐIỀU)\s+(\d+)\s*[.:]?\s*(.*)$")
#: Khớp lvlText của numbering.xml kiểu "ĐIỀU %1." — heading đánh số tự động, chữ số
#: không nằm trong text chạy nên _DIEU_RE (đòi \d+ literal) không bắt được.
_DIEU_LVL_RE = re.compile(r"^\s*(?:Điều|ĐIỀU)\s*%1")


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
    numbering = doc_numbering(path)
    # numId của các danh sách mà Word render tiền tố "Điều N." — heading tự động,
    # phân biệt với numId của khoản/điểm lồng bên trong cùng điều (ilvl khác 0).
    dieu_num_ids = {nid for nid, lt in numbering.items() if _DIEU_LVL_RE.match(lt)}
    moc: list[tuple[int, str, str]] = []  # (idx đoạn, số, tiêu đề)
    dem = 0  # bộ đếm điều tự động; số thủ công (literal) đồng bộ lại bộ đếm này
    for d in doan:
        m = _DIEU_RE.match(d.text)
        if m:
            # Chỉ đồng bộ TIẾN — số thủ công lạc hậu hơn bộ đếm (lỗi soạn thảo, đã
            # gặp trên hợp đồng thật: 1 heading gõ tay "Điều 4." nằm ở vị trí thứ 26)
            # không được kéo lùi bộ đếm và gây trùng số hàng loạt cho các điều sau.
            dem = max(dem, int(m.group(1)))
            moc.append((d.idx, m.group(1), m.group(2).strip()))
        elif d.num_id in dieu_num_ids and d.ilvl == "0":
            dem += 1
            moc.append((d.idx, str(dem), d.text))
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
