"""Test parser Điều/Khoản/Điểm giữ offset — offline, không gọi Gemini."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.ontology.parser import (
    VI_LETTERS,
    clean_text,
    letter_to_so_hau_to,
    parse_dieu,
    slice_dieu,
)

_FIXTURE = Path("data/fixtures/ND52-2024-dieu22.txt")
_SO_HIEU = "52/2024/NĐ-CP"

# Rác biên tập luatvietnam đúng như trong snapshot ND52-2024: dòng "Phân tích"
# mở một khối chú giải chèn NGAY GIỮA câu chapeau và điểm a).
_RAW_BAN = """Điều 22. Các dịch vụ trung gian thanh toán
1. Dịch vụ trung gian thanh toán bao gồm: dịch vụ ví điện tử.
Phân tích
2. Điều kiện cung ứng dịch vụ trung gian thanh toán:
Tổ chức không phải là ngân hàng được cấp Giấy phép khi đáp ứng đầy đủ các điều kiện sau đây:
Phân tích
Theo quy định tại
khoản 9 Mục 2 Phụ lục I.7 Nghị quyết 24/2026/NQ-CP
: Cắt giảm điều kiện cung ứng dịch vụ trung gian thanh toán.
a) Có giấy phép thành lập;
c) Có Đề án cung ứng dịch vụ được phê duyệt theo
Mẫu số 08 ban hành kèm theo Nghị định này
;
đ) Có Bản thuyết minh giải pháp kỹ thuật.
"""


@pytest.fixture(scope="module")
def dieu22():
    return parse_dieu(_FIXTURE.read_text(encoding="utf-8"), _SO_HIEU)


def test_bang_23_chu_dung_thu_tu():
    # KG v0.5 §5: 23 chữ, `đ` là chữ duy nhất thêm so với ASCII, sau `e` là `g`.
    assert len(VI_LETTERS) == 23
    assert VI_LETTERS[:8] == ["a", "b", "c", "d", "đ", "e", "g", "h"]
    assert not {"f", "j", "w", "z"} & set(VI_LETTERS)


def test_hau_to_tra_bang_khong_dung_ord():
    assert letter_to_so_hau_to(None) == 0  # không hậu tố
    assert letter_to_so_hau_to("a") == 1
    assert letter_to_so_hau_to("đ") == 5  # ord() sẽ cho kết quả khác
    assert letter_to_so_hau_to("e") == 6
    with pytest.raises(ValueError):
        letter_to_so_hau_to("f")


def test_so_hau_to_tren_dieu_va_khoan():
    dieu = parse_dieu("Điều 15a. Tiêu đề\n2đ. Nội dung khoản.", "01/2024/TT-X")
    assert (dieu.so_goc, dieu.so_hau_to, dieu.so_hien_thi) == (15, 1, "15a")
    khoan = dieu.khoan[0]
    assert (khoan.so_goc, khoan.so_hau_to, khoan.so_hien_thi) == (2, 5, "2đ")
    assert khoan.id == "01/2024/TT-X#than/dieu_15a#khoan_2đ"


def test_tach_dung_so_khoan_va_diem(dieu22):
    assert dieu22.tieu_de.startswith("Các dịch vụ trung gian thanh toán")
    assert [k.so_hien_thi for k in dieu22.khoan] == ["1", "2", "3"]
    assert len(dieu22.khoan[1].diem) == 8


def test_khong_nuot_diem_dd(dieu22):
    """Canh bug: regex [a-z]\\) không khớp `đ)` → điểm đ bị nuốt im lặng."""
    markers = [d.so_hien_thi for d in dieu22.khoan[1].diem]
    assert markers == ["a", "b", "c", "d", "đ", "e", "g", "h"]
    assert "đ" in markers
    assert "f" not in markers  # bảng chữ VN không có f
    diem_dd = dieu22.khoan[1].diem[4]
    assert diem_dd.text.startswith("đ) Có Bản thuyết minh")


def test_khoan_khong_che_diem(dieu22):
    # Pipeline phải nhận cả 2 dạng: khoản chẻ điểm (K2) và khoản là câu độc lập.
    assert dieu22.khoan[0].diem == []
    assert dieu22.khoan[2].diem == []


def test_chapeau_khong_nam_tren_dong_danh_so(dieu22):
    """Dòng "2. Điều kiện..." chỉ là tiêu đề; Subject/Action ở dòng kế tiếp."""
    k2 = dieu22.khoan[1]
    assert k2.text.splitlines()[0] == "2. Điều kiện cung ứng dịch vụ trung gian thanh toán:"
    assert "Tổ chức không phải là ngân hàng" in k2.text.splitlines()[1]


def test_char_span_round_trip(dieu22):
    """Bất biến nền tảng: text[start:end] == text của nút, với MỌI nút."""
    src = _FIXTURE.read_text(encoding="utf-8")
    nodes = [dieu22, *dieu22.khoan, *[d for k in dieu22.khoan for d in k.diem]]
    assert len(nodes) == 1 + 3 + 8
    for n in nodes:
        assert src[n.start : n.end] == n.text, n.id
        assert 0 <= n.start < n.end <= len(src)


def test_span_khoan_bao_tron_span_diem(dieu22):
    for k in dieu22.khoan:
        for d in k.diem:
            assert k.start <= d.start < d.end <= k.end


def test_loc_rac_bien_tap():
    clean = clean_text(_RAW_BAN)
    # Rác biên tập biến mất...
    assert "Phân tích" not in clean
    assert "24/2026/NQ-CP" not in clean
    assert "Cắt giảm điều kiện" not in clean
    # ...nhưng chữ của luật thì còn nguyên, kể cả mảnh vỡ do hyperlink cắt dòng.
    assert "Mẫu số 08 ban hành kèm theo Nghị định này;" in clean
    assert "đ) Có Bản thuyết minh giải pháp kỹ thuật." in clean


def test_parse_tren_text_da_loc_rac():
    dieu = parse_dieu(clean_text(_RAW_BAN), _SO_HIEU)
    k2 = dieu.khoan[1]
    assert [d.so_hien_thi for d in k2.diem] == ["a", "c", "đ"]
    # Chú giải bị chèn giữa chapeau và điểm a) đã bị loại khỏi span của khoản.
    assert "Nghị quyết" not in k2.text
    assert k2.id == "52/2024/NĐ-CP#than/dieu_22#khoan_2"
    assert k2.diem[2].id == "52/2024/NĐ-CP#than/dieu_22#khoan_2#diem_đ"


def test_slice_dieu_cat_dung_khoi():
    doc = "Điều 21. Trước\nNội dung 21.\nĐiều 22. Sau\nNội dung 22.\nĐiều 23. Kế tiếp"
    assert slice_dieu(doc, 22) == "Điều 22. Sau\nNội dung 22."
    with pytest.raises(ValueError):
        slice_dieu(doc, 99)
