"""Phân tích & chuẩn hoá SỐ HIỆU văn bản — `52/2024/NĐ-CP`, `59/2020/QH14`, `123/QĐ-NHNN`.

Từ vựng ở `data/ky_hieu_van_ban.json` (nguồn: `research/vb-phap-luat-ky-hieu.html`).

**Chỉ lưu MỘT dạng — dạng công bố.** Chuẩn hoá là một *hàm chạy ở biên*, không phải một
trường thứ hai. Bản nháp trước định thêm "dạng so khớp" (bỏ số 0 đầu, `Đ→D`), nhưng đo trên
dữ liệu thật thì **0 xung đột số 0 đầu** — chưa văn bản nào viết hai kiểu — nên đó là giải
một bài toán không tồn tại. Còn ID trong URL vbpl là *provenance của bản ghi thô*, không phải
một danh tính thứ ba của văn bản.

Ba điều thiết kế, mỗi điều rút từ khung ký hiệu chứ không từ suy đoán:

1. **Ký hiệu HỢP THÀNH `<loại>-<cơ quan>`.** Nên từ vựng là O(loại) + O(cơ quan), và tổ hợp
   chưa từng gặp (`TT-BNNMT`) tự hợp lệ.
2. **Năm TUỲ CHỌN.** `123/QĐ-NHNN` là văn bản hành chính, hợp lệ và không có năm. Regex đòi
   năm sẽ bỏ sót cả nhóm đó trong im lặng.
3. **Mã chỉ gồm `[A-ZĐ]`.** Đây là quy tắc CẤU TRÚC, mạnh hơn tra danh sách: nó bắt được
   homoglyph kể cả với mã cơ quan chưa có trong bảng. Ca thật: `51/2025/TT-BTС` mang
   `С` = CYRILLIC CAPITAL ES (U+0421). Regex cũ **im lặng cắt cụt** thành `51/2025/TT` — một
   khoá cụt tệ hơn không có khoá, vì nó vẫn join được vào nhầm văn bản.

`loai` là tập ĐÓNG (luật liệt kê đủ hình thức) ⇒ mã lạ là **lỗi**.
`co_quan` KHÔNG đóng được (63 UBND tỉnh, doanh nghiệp, cơ quan mới lập) ⇒ mã lạ là **cảnh báo**.
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

_DUONG_DAN = Path("data/ky_hieu_van_ban.json")

#: Chữ hoa Cyrillic/Hy Lạp trông y hệt chữ Latin. Chỉ liệt kê cặp THẬT SỰ nhìn giống nhau —
#: thêm cặp không giống là tự cho phép sửa sai thành sai khác.
HOMOGLYPH: dict[str, str] = {
    # Cyrillic
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O",
    "Р": "P", "С": "C", "Т": "T", "У": "Y", "Х": "X", "І": "I", "Ј": "J",
    # Hy Lạp
    "Α": "A", "Β": "B", "Ε": "E", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M",
    "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X", "Ζ": "Z",
}

# Cho phép cả chữ thường: `TTg` (Thủ tướng), `TTr` (Tờ trình) là chính tả CHUẨN, không phải
# lỗi gõ. Nên không được `.upper()` mù — chính tả do TỪ VỰNG quyết, xem `_theo_chinh_ta`.
_MA_HOP_LE = re.compile(r"^[A-Za-zĐđ]+$")
_SO = r"\d{1,4}[a-zA-Z]?"
_PHAN = r"[^\s/,;.)\]]+"

#: Nhóm A — Quốc hội/UBTVQH: `59/2020/QH14`. Khoá là số, không phải mã cơ quan.
_RE_QH = re.compile(rf"^({_SO})/(\d{{4}})/(QH|UBTVQH)(\d{{1,2}})$", re.IGNORECASE)
#: Nhóm B — có năm: `52/2024/NĐ-CP`. Nhóm B — không năm: `123/QĐ-NHNN`.
_RE_B_CO_NAM = re.compile(rf"^({_SO})/(\d{{4}})/({_PHAN})$")
_RE_B_KHONG_NAM = re.compile(rf"^({_SO})/({_PHAN})$")


class SoHieu(BaseModel):
    """Số hiệu đã tách phần. `chuan` là dạng công bố — thứ DUY NHẤT nên đem đi lưu."""

    chuan: str
    so: str
    nam: str | None = None
    loai: str | None = None  # "TT", "NĐ" — None với nhóm Quốc hội
    co_quan: list[str] = Field(default_factory=list)  # nhiều phần tử khi TTLT
    khoa_qh: str | None = None  # "14" trong QH14
    #: Suy từ chính ký hiệu: có năm + loại QPPL. `None` = không kết luận được (vd `QĐ`).
    qppl: bool | None = None
    canh_bao: list[str] = Field(default_factory=list)


@lru_cache(maxsize=1)
def _tu_vung(duong_dan: str = str(_DUONG_DAN)) -> tuple[dict, dict, dict]:
    p = Path(duong_dan)
    if not p.exists():
        return {}, {}, {}
    raw = json.loads(p.read_text(encoding="utf-8"))
    return raw.get("loai", {}), raw.get("co_quan", {}), raw.get("quoc_hoi", {})


def khu_homoglyph(s: str) -> tuple[str, list[str]]:
    """Đổi chữ Cyrillic/Hy Lạp trông giống Latin → Latin. Trả (chuỗi, ghi chú từng ca đổi)."""
    ra, ghi = [], []
    for ch in s:
        moi = HOMOGLYPH.get(ch)
        if moi:
            ghi.append(f"{ch!r} (U+{ord(ch):04X} {unicodedata.name(ch, '?')}) → {moi!r}")
            ra.append(moi)
        else:
            ra.append(ch)
    return "".join(ra), ghi


def _theo_chinh_ta(ma: str, bang: dict) -> str:
    """Có trong từ vựng (bỏ qua hoa/thường) ⇒ lấy ĐÚNG chính tả của từ vựng.

    Đây là chỗ `TTg`/`TTr` được giữ đúng dạng dù nguồn viết `TTG` hay `ttg`: từ vựng là nơi
    chốt chính tả, không phải một phép `.upper()`.
    """
    thap = ma.casefold()
    for k in bang:
        if k.casefold() == thap:
            return k
    return ma


def _lam_sach_ma(ma: str, o_dau: str, bang: dict, canh_bao: list[str]) -> str:
    """Mã loại/cơ quan phải là chữ cái. Ký tự lạ ⇒ thử khử homoglyph, có ghi lại."""
    ma = unicodedata.normalize("NFC", ma).strip()
    if not _MA_HOP_LE.match(ma):
        sua, ghi = khu_homoglyph(ma)
        if ghi and _MA_HOP_LE.match(sua):
            canh_bao.append(
                f"{o_dau} {ma!r} chứa ký tự nhìn giống Latin: {'; '.join(ghi)} — đã sửa"
            )
            ma = sua
    return _theo_chinh_ta(ma, bang)


def phan_tich(raw: str) -> SoHieu | None:
    """Chuỗi số hiệu → `SoHieu`, hoặc `None` nếu không đúng khuôn nào.

    KHÔNG cắt cụt bao giờ: hoặc khớp trọn một khuôn, hoặc trả `None`. Cụm chưa quy được về
    khoá thì phải nói ra để người xử lý, chứ một khoá cụt vẫn join được — vào nhầm chỗ.
    """
    if not raw:
        return None
    s = unicodedata.normalize("NFC", raw).strip().replace(" ", "")
    loai_map, co_quan_map, qh_map = _tu_vung()
    canh_bao: list[str] = []

    m = _RE_QH.match(s)
    if m:
        so, nam, cq, khoa = m.groups()
        cq = cq.upper()
        if cq not in qh_map:
            canh_bao.append(f"cơ quan {cq!r} không có trong bảng Quốc hội")
        return SoHieu(chuan=f"{so}/{nam}/{cq}{khoa}", so=so, nam=nam, co_quan=[cq],
                      khoa_qh=khoa, qppl=True, canh_bao=canh_bao)

    m = _RE_B_CO_NAM.match(s)
    nam = None
    if m:
        so, nam, duoi = m.groups()
    else:
        m = _RE_B_KHONG_NAM.match(s)
        if not m:
            return None
        so, duoi = m.groups()

    if "-" not in duoi:
        return None  # nhóm B bắt buộc `<loại>-<cơ quan>`; không có gạch nối thì chưa quy được
    phan = duoi.split("-")
    loai = _lam_sach_ma(phan[0], "mã loại", loai_map, canh_bao)
    cq = [_lam_sach_ma(x, "mã cơ quan", co_quan_map, canh_bao) for x in phan[1:]]

    if loai not in loai_map:
        canh_bao.append(f"loại văn bản {loai!r} không thuộc tập đóng — xem data/ky_hieu_van_ban.json")
    else:
        if len(cq) > 1 and not loai_map[loai].get("nhieu_co_quan"):
            canh_bao.append(f"{loai!r} không phải loại liên tịch mà có {len(cq)} cơ quan")
    for x in cq:
        if x not in co_quan_map:
            canh_bao.append(f"cơ quan {x!r} chưa có trong bảng — kiểm rồi bổ sung nếu đúng")

    # QPPL đọc được từ chính ký hiệu: phải CÓ NĂM *và* loại phải là hình thức quy phạm.
    q = loai_map.get(loai, {}).get("qppl")
    qppl = None if q is None else (bool(q) and nam is not None)

    chuan = f"{so}/{nam}/{loai}-{'-'.join(cq)}" if nam else f"{so}/{loai}-{'-'.join(cq)}"
    return SoHieu(chuan=chuan, so=so, nam=nam, loai=loai, co_quan=cq,
                  qppl=qppl, canh_bao=canh_bao)


def chuan_hoa(raw: str) -> str | None:
    """Số hiệu → dạng công bố đã chuẩn hoá, hoặc `None` nếu không phân tích được."""
    sh = phan_tich(raw)
    return sh.chuan if sh else None
