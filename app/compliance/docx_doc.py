"""Đọc .docx bằng stdlib — đoạn văn, comment pháp lý, và neo comment→đoạn.

Chỉ zipfile + xml.etree, không python-docx: nhu cầu là text + comment anchor,
thêm thư viện cho việc regex 2 tag là vi phạm ladder.
Neo ở MỨC ĐOẠN VĂN: commentRangeStart/End có thể cắt giữa run, nhưng gold chỉ cần
biết comment thuộc đoạn nào → điều nào của hợp đồng.
"""
from __future__ import annotations

import warnings
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from pydantic import BaseModel

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class DoanVan(BaseModel):
    idx: int
    text: str
    comment_ids: list[str] = []
    #: w:pPr/w:numPr/w:numId — None nếu đoạn không nằm trong danh sách đánh số tự động.
    num_id: str | None = None
    #: w:pPr/w:numPr/w:ilvl — cấp lồng của danh sách ("0" = cấp ngoài cùng).
    ilvl: str | None = None


class BinhLuan(BaseModel):
    id: str
    author: str
    date: str | None = None
    text: str


def _text_cua(el: ET.Element) -> str:
    return " ".join("".join(t.itertext()) for t in el.iter(f"{_W}t")).strip()


def doc_docx(path: Path) -> tuple[list[DoanVan], list[BinhLuan]]:
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        binh_luan: list[BinhLuan] = []
        if "word/comments.xml" in z.namelist():
            croot = ET.fromstring(z.read("word/comments.xml"))
            for c in croot.findall(f"{_W}comment"):
                binh_luan.append(BinhLuan(
                    id=c.get(f"{_W}id") or "",
                    author=c.get(f"{_W}author") or "",
                    date=c.get(f"{_W}date"),
                    text=_text_cua(c),
                ))
    doan: list[DoanVan] = []
    dang_mo: set[str] = set()  # comment range mở vắt qua nhiều đoạn
    for p in root.iter(f"{_W}p"):
        ids = set(dang_mo)
        for el in p.iter():
            if el.tag == f"{_W}commentRangeStart":
                cid = el.get(f"{_W}id") or ""
                ids.add(cid)
                dang_mo.add(cid)
            elif el.tag == f"{_W}commentRangeEnd":
                dang_mo.discard(el.get(f"{_W}id") or "")
        text = _text_cua(p)
        if text:
            num_id = ilvl = None
            pPr = p.find(f"{_W}pPr")
            if pPr is not None:
                numPr = pPr.find(f"{_W}numPr")
                if numPr is not None:
                    nid_el = numPr.find(f"{_W}numId")
                    ilvl_el = numPr.find(f"{_W}ilvl")
                    num_id = nid_el.get(f"{_W}val") if nid_el is not None else None
                    ilvl = ilvl_el.get(f"{_W}val") if ilvl_el is not None else None
            doan.append(DoanVan(
                idx=len(doan), text=text, comment_ids=sorted(ids), num_id=num_id, ilvl=ilvl,
            ))
    if dang_mo:
        warnings.warn(
            f"docx {path.name}: comment range không đóng: {sorted(dang_mo)}",
            stacklevel=2,
        )
    return doan, binh_luan


def doc_numbering(path: Path) -> dict[str, str]:
    """numId -> lvlText của cấp 0 (ngoài cùng), đọc từ word/numbering.xml nếu có.

    Heading đánh số tự động của Word (danh sách numPr) không có số trong text chạy —
    số hiển thị do numbering.xml render (lvlText kiểu "ĐIỀU %1."), không nằm trong
    <w:t>. Đây là sự thật thô (numId -> mẫu hiển thị); diễn giải "numId nào là Điều"
    là việc của caller, không phải của module đọc docx chung này.
    """
    with zipfile.ZipFile(path) as z:
        if "word/numbering.xml" not in z.namelist():
            return {}
        root = ET.fromstring(z.read("word/numbering.xml"))
    lvl0_cua_abstract: dict[str, str] = {}
    for an in root.findall(f"{_W}abstractNum"):
        aid = an.get(f"{_W}abstractNumId") or ""
        for lvl in an.findall(f"{_W}lvl"):
            if lvl.get(f"{_W}ilvl") == "0":
                lt = lvl.find(f"{_W}lvlText")
                if lt is not None:
                    lvl0_cua_abstract[aid] = lt.get(f"{_W}val") or ""
    ra: dict[str, str] = {}
    for n in root.findall(f"{_W}num"):
        nid = n.get(f"{_W}numId") or ""
        aid_el = n.find(f"{_W}abstractNumId")
        aid = aid_el.get(f"{_W}val") if aid_el is not None else None
        if aid in lvl0_cua_abstract:
            ra[nid] = lvl0_cua_abstract[aid]
    return ra
