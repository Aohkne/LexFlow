"""`web/lib/quan-he.ts` phải khớp `app/core/schemas.py::REL_TYPES`.

Bảng này buộc phải tồn tại hai bản — một cho Python, một cho trình duyệt. Cái KHÔNG buộc phải
tồn tại là việc hai bản trôi khỏi nhau mà không ai biết, và đó đúng là chuyện đã xảy ra: web
kẹt lại ở bốn tên tự đặt (`SUA_DOI`, `HUONG_DAN`…) suốt từ lúc backend chuẩn hoá về 13 mã
v0.5, hỏng theo kiểu **không có lỗi nào trong console** — chỉ là người dùng đọc thấy chữ
`SUA_DOI_BO_SUNG` thay cho "Văn bản sửa đổi, bổ sung", và bản đồ sửa đổi thì rỗng đi.

Test này đọc thẳng file `.ts` bằng regex thay vì chạy Node: nó chỉ cần canh **nội dung bảng**,
và một phép so khớp văn bản thì chạy được ở mọi nơi `pytest` chạy được.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.core.schemas import REL_BAT_LOI, REL_TYPES

_TS = Path("web/lib/quan-he.ts")
pytestmark = pytest.mark.skipif(not _TS.exists(), reason="chưa có web/lib/quan-he.ts")

_MUC = re.compile(
    r"^\s{2}(?P<ma>[A-Z_]+):\s*\[\s*(?P<nhan>.+?)\s*\],\s*$",
    re.MULTILINE | re.DOTALL,
)
_CHUOI = re.compile(r'"([^"]*)"')


def _doc_bang() -> dict[str, tuple[str, str]]:
    raw = _TS.read_text(encoding="utf-8")
    than = raw.split("REL_LABELS", 1)[1].split("};", 1)[0]
    ra: dict[str, tuple[str, str]] = {}
    for m in _MUC.finditer(than):
        nhan = _CHUOI.findall(m.group("nhan"))
        assert len(nhan) == 2, f"{m.group('ma')}: phải đúng 2 nhãn, thấy {nhan}"
        ra[m.group("ma")] = (nhan[0], nhan[1])
    return ra


def test_du_13_ma_khong_thua_khong_thieu():
    assert set(_doc_bang()) == set(REL_TYPES)


def test_26_nhan_giong_het_ban_python():
    """Kể cả cặp bất quy tắc #8 (`căn cứ ban hành` ⟷ `áp dụng`) — chỗ dễ tự suy ra sai nhất."""
    assert _doc_bang() == REL_TYPES


def test_tap_bat_loi_khop():
    raw = _TS.read_text(encoding="utf-8")
    than = raw.split("REL_BAT_LOI", 1)[1].split("]", 1)[0]
    assert set(_CHUOI.findall(than)) == set(REL_BAT_LOI)


_COMMENT = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)


def test_khong_con_ten_cu_nao_trong_web():
    """Ba tên đã chết. `HUONG_DAN` không phải lệch tên — nó không phải quan hệ có thật.

    Soi MÃ, không soi văn xuôi: comment giải thích vì sao ba tên kia bị bỏ thì phải được nhắc
    tên chúng — một test cấm cả trong comment sẽ cấm luôn việc ghi lại lý do.
    """
    for p in Path("web").rglob("*.ts*"):
        if "node_modules" in p.parts or ".next" in p.parts:
            continue
        ma = _COMMENT.sub("", p.read_text(encoding="utf-8"))
        for cu in ("SUA_DOI", "HUONG_DAN", "TAM_NGUNG"):
            for m in re.finditer(rf"\b{cu}\b", ma):
                sau = ma[m.end() : m.end() + 12]
                assert sau.startswith(("_BO_SUNG", "_AP_DUNG", "_HIEU_LUC")), (
                    f"{p}: còn tên quan hệ cũ {cu!r} trong MÃ"
                )
