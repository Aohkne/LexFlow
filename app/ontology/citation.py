"""Bóc viện dẫn trong câu: "điểm b(i) khoản 2 Điều 22 Nghị định 52/2024/NĐ-CP".

Trước file này repo KHÔNG có parser viện dẫn nào — văn phạm chỉ nằm trong spec
(`docs/SCHEMA_KG.md` §2.b), chưa ai hiện thực. `web/lib/anchors.ts` chỉ cắt slug
mức Điều.

Ba điều spec CHƯA phủ mà văn bản thật có, đã đo trên corpus 15 văn bản:

1. **Hậu tố La Mã** `điểm b(i)`, `điểm a(ii)`, `điểm c (i)` — 4 chỗ. Văn phạm spec
   `(điểm <chữ cái>\\s+)?...` sẽ khớp "điểm b" rồi **bỏ im lặng phần "(i)"**, tức
   giải viện dẫn về đích RỘNG HƠN thực tế mà không báo gì. Ở đây `(i)` được giữ
   trong `DiemRef.tiet` — nó KHÔNG vào khoá node (xem `to_node_ids`), nhưng cũng
   không được biến mất.
2. **Nhiều đích một câu** `điểm a, điểm b, điểm c, điểm d và điểm đ khoản 2 Điều này`
   — spec có nói tới trong lời văn nhưng để ngoài regex.
3. **Tự tham chiếu** `Điều này`, `khoản này`, `Thông tư này` — spec không nhắc.

Phân biệt viện dẫn thật với chữ thường (đã đếm trên corpus):

| mẫu | khớp | vì sao |
|---|---|---|
| `điểm` + chữ ĐƠN LẺ | 210 | mẫu ngây thơ `điểm\\s+[chữ]` ra 298, dính "**điểm** nhận được lệnh" |
| `khoản` + SỐ | 401 | mẫu ngây thơ `khoản` ra 1846, dính "tài **khoản** thanh toán" (69 lần) |
| `Điều` VIẾT HOA + số/`này` | 537 | loại đúng 154 chữ "**điều** kiện", "**điều** chỉnh" |
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from app.ontology.parser import _LC, _ROMAN_ALT

# Số hiệu văn bản DẪN CHIẾU trong văn xuôi — khác đường với `app.core.so_hieu.phan_tich`, và
# cố ý giữ nguyên: mẫu này nằm trong `_CIT`, mà `_CIT` sinh ra `char_span`. Nới nó là dịch
# offset của mọi bản ghi CU đã gán nhãn. Hệ quả phải nói ra: nó mang đúng khuyết tật đã sửa ở
# `extract.py` — gặp homoglyph thì lùi lại khớp ngắn hơn — nên một dẫn chiếu tới
# `51/2025/TT-BTС` sẽ **không** khớp ở đây. Sửa cần một đợt đo riêng trên char_span.
_SO_HIEU = r"\d+/\d{4}/[A-ZĐ]+(?:-[A-ZĐ]+)+"
_LOAI_VB = "Thông tư|Nghị định|Nghị quyết|Quyết định|Pháp lệnh|Bộ luật|Luật|Hiến pháp"

# Một điểm, kèm hậu tố La Mã tuỳ chọn. Lookahead bắt chữ cái phải ĐỨNG MỘT MÌNH:
# không có nó thì "điểm nhận" khớp thành điểm "n".
_DIEM_ITEM = rf"[{_LC}](?![\wÀ-ỹ])(?:\s*\(\s*(?:{_ROMAN_ALT})\s*\))?"
_SEP = r"(?:\s*,\s*|\s+và\s+|\s+hoặc\s+)"
_DIEM_LIST = rf"{_DIEM_ITEM}(?:{_SEP}(?:điểm\s+)?{_DIEM_ITEM})*"

# Khoản/Điều có thể mang hậu tố chữ: "khoản 2đ" (KG v0.5 §5), "Điều 15a".
_NUM_ITEM = rf"\d{{1,3}}[{_LC}]?(?![\wÀ-ỹ])"
# Từ nối tiếp danh sách phải CÙNG CẤP với danh sách đang đọc. Dùng chung
# `(?:khoản\s+|Điều\s+)?` cho cả hai cấp thì "Điều 35, khoản 4 Điều 47" bị đọc
# thành Điều 35 và Điều **4** rồi Điều 47 — sai đích, im lặng. Gặp thật ở TT40
# Điều 52 khoản 2 và khoản 4.
_KHOAN_LIST = rf"{_NUM_ITEM}(?:{_SEP}(?:khoản\s+)?{_NUM_ITEM})*"
_DIEU_LIST = rf"{_NUM_ITEM}(?:{_SEP}(?:Điều\s+)?{_NUM_ITEM})*"

_VAN_BAN = rf"(?:của\s+)?(?:{_LOAI_VB})\s+(?:này|(?:số\s+)?{_SO_HIEU})"

# Chỉ mở một viện dẫn khi có tín hiệu chắc chắn (bảng trong docstring).
_TRIGGER = re.compile(
    rf"(?:điểm\s+(?=[{_LC}](?![\wÀ-ỹ]))|(?<!tài\s)khoản\s+(?=\d)|Điều\s+(?=\d|này))"
)
_CIT = re.compile(
    rf"(?:điểm\s+(?P<diem>{_DIEM_LIST})\s*,?\s*)?"
    rf"(?:khoản\s+(?P<khoan>{_KHOAN_LIST}|này)\s*,?\s*)?"
    rf"(?:Điều\s+(?P<dieu>{_DIEU_LIST}|này)\s*)?"
    rf"(?P<vb>{_VAN_BAN})?"
)
# Chữ cái phải ĐỨNG MỘT MÌNH cả hai phía. Thiếu lookbehind thì chính chữ "điểm"
# và "và" trong danh sách bị tách thành điểm giả: đ, i, m, v.
_DIEM_ONE = re.compile(
    rf"(?<![\wÀ-ỹ])([{_LC}])(?![\wÀ-ỹ])(?:\s*\(\s*({_ROMAN_ALT})\s*\))?", re.I
)
_NUM_ONE = re.compile(rf"\d{{1,3}}[{_LC}]?")
_SO_HIEU_RE = re.compile(_SO_HIEU)


class DiemRef(BaseModel):
    """Một điểm được viện dẫn. `tiet` là HẬU TỐ, không phải cấp riêng.

    Văn bản thật viết `điểm b(i)`, không viết `tiết (i) điểm b` — chữ "tiết" xuất
    hiện 0 lần trong 557k ký tự corpus. Nên số La Mã được mô hình hoá như hậu tố,
    y hệt cách KG v0.5 §5 xử lý `Điều 15a` bằng `so_hau_to`.
    """

    diem: str
    tiet: str | None = None


class CitationRef(BaseModel):
    raw: str
    span: tuple[int, int]
    diem: list[DiemRef] = Field(default_factory=list)
    khoan: list[str] = Field(default_factory=list)
    dieu: list[str] = Field(default_factory=list)
    van_ban: str | None = None  # số hiệu đã dò được
    van_ban_raw: str | None = None  # nguyên văn phần tên văn bản
    noi_bo: bool = False  # "Điều này" / "Thông tư này" / không nêu văn bản
    dieu_self: bool = False  # viết "Điều này"
    khoan_self: bool = False  # viết "khoản này"
    # Theo SCHEMA_KG §2.b: đích không phải phân giải tên văn bản thì chắc chắn hơn.
    do_tin_cay: Literal["cao", "trung_binh", "thap"] = "cao"

    @property
    def co_tiet(self) -> bool:
        return any(d.tiet for d in self.diem)


def _split_diem(raw: str) -> list[DiemRef]:
    return [
        DiemRef(diem=m.group(1), tiet=(m.group(2) or "").lower() or None)
        for m in _DIEM_ONE.finditer(raw)
    ]


def _split_num(raw: str) -> list[str]:
    return _NUM_ONE.findall(raw)


def parse_citations(text: str) -> list[CitationRef]:
    """Quét toàn bộ viện dẫn trong một đoạn. Không gọi LLM."""
    out: list[CitationRef] = []
    pos = 0
    for trig in _TRIGGER.finditer(text):
        if trig.start() < pos:
            continue  # nằm trong viện dẫn đã bóc
        m = _CIT.match(text, trig.start())
        if not m or not m.group():
            continue
        diem_raw, khoan_raw, dieu_raw, vb_raw = (
            m.group("diem"), m.group("khoan"), m.group("dieu"), m.group("vb")
        )
        if not (diem_raw or khoan_raw or dieu_raw):
            continue

        so_hieu = _SO_HIEU_RE.search(vb_raw) if vb_raw else None
        noi_bo = bool(
            (vb_raw and vb_raw.rstrip().endswith("này"))
            or (dieu_raw == "này")
            or (khoan_raw == "này")
            or not vb_raw
        )
        if so_hieu:
            tin_cay = "trung_binh"  # phải phân giải số hiệu → node
        elif vb_raw and not noi_bo:
            tin_cay = "thap"  # chỉ có tên văn bản, chưa có số hiệu
        else:
            tin_cay = "cao"  # viện dẫn nội bộ

        raw = m.group().rstrip(" ,")
        out.append(
            CitationRef(
                raw=raw,
                span=(m.start(), m.start() + len(raw)),
                diem=_split_diem(diem_raw) if diem_raw else [],
                khoan=_split_num(khoan_raw) if khoan_raw and khoan_raw != "này" else [],
                dieu=_split_num(dieu_raw) if dieu_raw and dieu_raw != "này" else [],
                van_ban=so_hieu.group() if so_hieu else None,
                van_ban_raw=vb_raw.strip() if vb_raw else None,
                noi_bo=noi_bo,
                dieu_self=dieu_raw == "này",
                khoan_self=khoan_raw == "này",
                do_tin_cay=tin_cay,  # type: ignore[arg-type]
            )
        )
        pos = m.end()
    return out


def to_node_ids(
    ref: CitationRef,
    ctx_so_hieu: str,
    ctx_dieu: str | None = None,
    ctx_khoan: str | None = None,
) -> list[str]:
    """Viện dẫn → danh sách khoá node KG. `ctx_*` dùng cho viện dẫn nội bộ.

    Hai điều cố ý làm cho KHÔNG âm thầm:

    1. Hậu tố tiết KHÔNG vào khoá — đã đo và chốt không địa chỉ hoá cấp này
       (4/586 viện dẫn, cả 4 ở văn bản hết hiệu lực). Nhưng `ref.co_tiet` giữ lại
       sự thật là viện dẫn HẸP HƠN node trả về, để bên gọi biết mà xử lý.
    2. `khoản này` / `Điều này` mà thiếu ngữ cảnh thì trả **rỗng**, không tụt lên
       khoá rộng hơn. Trả "Điều 16" cho câu viết "điểm b(i) khoản này" là sai
       lặng lẽ — mở rộng đích gấp nhiều lần mà không ai biết.
    """
    so_hieu = ref.van_ban or ctx_so_hieu
    dieu_list = ref.dieu or ([ctx_dieu] if ctx_dieu else [])
    if not dieu_list:
        return []

    khoan_list = ref.khoan
    if not khoan_list and (ref.khoan_self or ref.diem):
        # Viết "khoản này", hoặc nêu điểm mà không nêu khoản ⇒ khoản là ngữ cảnh.
        if not ctx_khoan:
            return []
        khoan_list = [ctx_khoan]

    ids = []
    for dieu in dieu_list:
        base = f"{so_hieu}#than/dieu_{dieu}"
        if not khoan_list:
            ids.append(base)
            continue
        for khoan in khoan_list:
            k = f"{base}#khoan_{khoan}"
            ids += [f"{k}#diem_{d.diem}" for d in ref.diem] or [k]
    # "điểm b(ii) và b(iii)" cùng về #diem_b vì tiết không có địa chỉ — gộp lại,
    # phần mất mát đã được `co_tiet` ghi nhận.
    return list(dict.fromkeys(ids))
