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
            doan.append(DoanVan(idx=len(doan), text=text, comment_ids=sorted(ids)))
    if dang_mo:
        warnings.warn(
            f"docx {path.name}: comment range không đóng: {sorted(dang_mo)}",
            stacklevel=2,
        )
    return doan, binh_luan
