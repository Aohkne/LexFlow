"""Phân tích số hiệu văn bản — offline. Từ vựng: `data/ky_hieu_van_ban.json`.

Vì sao có file này: bản đầu dùng một regex lớp-ký-tự (`[A-ZĐ]+(?:-[A-ZĐ]+)*`) và nó **im
lặng cắt cụt** `51/2025/TT-BTС` — mang `С` = CYRILLIC CAPITAL ES — thành `51/2025/TT`. Một
khoá cụt **tệ hơn không có khoá**: nó vẫn join được, vào nhầm văn bản, và không ai biết.

Ba điều test canh, mỗi điều là một quyết định thiết kế rút từ khung ký hiệu
(`research/vb-phap-luat-ky-hieu.html`), không phải từ suy đoán văn phạm:

1. ký hiệu **hợp thành** `<loại>-<cơ quan>` ⇒ tổ hợp mới tự hợp lệ;
2. **năm tuỳ chọn** ⇒ regex đòi năm bỏ sót cả nhóm hành chính trong im lặng;
3. mã chỉ gồm `[A-ZĐ]` — quy tắc **cấu trúc**, bắt được homoglyph kể cả với mã chưa có trong bảng.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.so_hieu import HOMOGLYPH, chuan_hoa, khu_homoglyph, phan_tich

_BANG = Path("data/ky_hieu_van_ban.json")


# --- 1. Hai khuôn, năm tuỳ chọn ----------------------------------------------


@pytest.mark.parametrize(
    ("raw", "loai", "cq", "nam"),
    [
        ("52/2024/NĐ-CP", "NĐ", ["CP"], "2024"),
        ("40/2024/TT-NHNN", "TT", ["NHNN"], "2024"),
        ("15a/2025/NĐ-CP", "NĐ", ["CP"], "2025"),          # số có hậu tố chữ
        ("025/2024/QĐ-SHB", "QĐ", ["SHB"], "2024"),        # số 0 đầu giữ nguyên
        ("123/QĐ-NHNN", "QĐ", ["NHNN"], None),             # HÀNH CHÍNH — không năm
        ("01/2020/TTLT-BTC-BNV", "TTLT", ["BTC", "BNV"], "2020"),
    ],
)
def test_nhom_B(raw, loai, cq, nam):
    sh = phan_tich(raw)
    assert sh is not None
    assert (sh.loai, sh.co_quan, sh.nam) == (loai, cq, nam)
    assert sh.chuan == raw


@pytest.mark.parametrize("raw", ["59/2020/QH14", "14/2022/QH15", "76/2015/QH13"])
def test_nhom_A_quoc_hoi(raw):
    """Nhóm Quốc hội thay phần cơ quan bằng số KHOÁ — không có `<loại>-<cơ quan>`."""
    sh = phan_tich(raw)
    assert sh is not None and sh.chuan == raw
    assert sh.loai is None and sh.khoa_qh == raw[-2:]
    assert sh.qppl is True


def test_so_0_dau_GIU_NGUYEN():
    """Đo trên dữ liệu thật: **0 xung đột** — chưa văn bản nào viết cả hai kiểu.

    Nên bỏ số 0 đầu là giải một bài toán không tồn tại, mà lại làm dạng lưu lệch dạng công bố.
    """
    assert chuan_hoa("07/2024/TT-NHNN") == "07/2024/TT-NHNN"
    assert chuan_hoa("025/2024/QĐ-SHB") == "025/2024/QĐ-SHB"


# --- 2. Từ chối, không bao giờ cắt cụt ---------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "51/2025/TT",          # ca THẬT sau khi regex cũ cắt cụt — phải từ chối
        "khong phai so hieu",
        "",
        "52/2024",             # thiếu phần loại-cơ quan
        "52/2024/NDCP",        # nhóm B bắt buộc có gạch nối
        "21/2017/TT-",         # ca THẬT: nguồn viết `21/2017/TT- NHNN`, ứng viên dừng ở gạch nối
        "52/2024/-CP",         # thiếu mã loại
        "52/2024/NĐ--CP",      # gạch nối đôi ⇒ có phần rỗng ở giữa
    ],
)
def test_khong_dung_khuon_thi_tra_None(raw):
    assert phan_tich(raw) is None
    assert chuan_hoa(raw) is None


def test_phan_RONG_bi_tu_choi_chu_khong_thanh_khoa_cut():
    """`21/2017/TT-` từng phân tích được với `co_quan=['']` ⇒ khoá cụt `21/2017/TT-`.

    Đúng thứ lớp này sinh ra để chặn: khoá cụt **vẫn join được**, vào nhầm văn bản, và chỉ để
    lại một cảnh báo *"cơ quan '' chưa có trong bảng"* — đọc như một mã lạ cần bổ sung, chứ
    không như một cụm đã hỏng. Nối lại là việc của bộ ĐỌC (`vbpl_luoc_do`), nơi còn nhìn thấy
    phần văn bản đứng sau; ở đây chỉ có mảnh nên không được đoán.
    """
    assert phan_tich("21/2017/TT-") is None
    assert phan_tich("21/2017/TT-NHNN").co_quan == ["NHNN"]


# --- 3. Homoglyph: quy tắc CẤU TRÚC, không phải tra danh sách ----------------


def test_ca_that_cyrillic_duoc_sua_va_noi_ra():
    sh = phan_tich("51/2025/TT-BTС")  # С = U+0421
    assert sh is not None
    assert sh.chuan == "51/2025/TT-BTC" and sh.co_quan == ["BTC"]
    assert len(sh.canh_bao) == 1
    # Cảnh báo phải nêu đích danh codepoint — người sửa nguồn cần biết ký tự nào.
    assert "U+0421" in sh.canh_bao[0] and "CYRILLIC" in sh.canh_bao[0]


def test_homoglyph_bat_duoc_ca_ma_CHUA_co_trong_bang():
    """Đây là chỗ quy tắc cấu trúc mạnh hơn tra danh sách."""
    sh = phan_tich("9/2025/TT-ХYZ")  # Х = U+0425 CYRILLIC HA
    assert sh is not None and sh.co_quan == ["XYZ"]
    assert any("U+0425" in c for c in sh.canh_bao)


def test_bang_homoglyph_chi_chua_cap_that_su_giong_nhau():
    """Thêm một cặp KHÔNG giống nhau là tự cho phép sửa sai thành sai khác."""
    for cu, moi in HOMOGLYPH.items():
        assert len(cu) == len(moi) == 1
        assert moi in "ABCEHIJKMNOPTXYZ", f"{cu!r}→{moi!r} không phải cặp nhìn giống"
        assert ord(cu) > 127


def test_khu_homoglyph_khong_dung_thi_khong_doi():
    s, ghi = khu_homoglyph("NHNN")
    assert s == "NHNN" and ghi == []


def test_ma_hoa_thuong_lan_lon_giu_dung_chinh_ta():
    """`TTg`/`TTr` là chính tả chuẩn — `.upper()` mù sẽ làm hỏng khoá trong im lặng."""
    assert chuan_hoa("123/QĐ-TTg") == "123/QĐ-TTg"
    assert chuan_hoa("123/QĐ-TTG") == "123/QĐ-TTg", "từ vựng phải chốt lại chính tả"
    assert chuan_hoa("45/2025/TTr-BTC") == "45/2025/TTr-BTC"


# --- 4. Tập đóng vs tập mở ---------------------------------------------------


def test_loai_la_thi_canh_bao():
    """`loai` ĐÓNG — luật liệt kê đủ hình thức văn bản."""
    sh = phan_tich("1/2020/ZZ-CP")
    assert sh is not None
    assert any("không thuộc tập đóng" in c for c in sh.canh_bao)


def test_co_quan_la_thi_canh_bao_chu_KHONG_tu_choi():
    """`co_quan` KHÔNG đóng được: 63 UBND tỉnh, doanh nghiệp, cơ quan mới lập."""
    sh = phan_tich("12/2026/TT-XYZ")
    assert sh is not None and sh.co_quan == ["XYZ"]
    assert any("chưa có trong bảng" in c for c in sh.canh_bao)


def test_lien_tich_nhieu_co_quan_hop_le_con_loai_khac_thi_canh_bao():
    assert phan_tich("01/2020/TTLT-BTC-BNV").canh_bao == []
    sh = phan_tich("01/2020/TT-BTC-BNV")
    assert any("không phải loại liên tịch" in c for c in sh.canh_bao)


# --- 5. QPPL đọc được từ chính ký hiệu ---------------------------------------


@pytest.mark.parametrize(
    ("raw", "cho"),
    [
        ("52/2024/NĐ-CP", True),
        ("40/2024/TT-NHNN", True),
        ("59/2020/QH14", True),
        ("123/CT-NHNN", False),      # loại hành chính
        ("38/2007/QĐ-NHNN", None),   # QĐ — không kết luận được từ riêng ký hiệu
        ("123/QĐ-NHNN", None),
    ],
)
def test_qppl_suy_tu_ky_hieu(raw, cho):
    """`QĐ` trả `None` là CỐ Ý: từ 2015 Quyết định của Bộ trưởng không còn là VBQPPL, nhưng
    Quyết định của Thủ tướng/Chủ tịch nước/UBND tỉnh thì vẫn — riêng ký hiệu không đủ để chốt.
    """
    assert phan_tich(raw).qppl is cho


# --- 6. Bảng từ vựng phải tự nhất quán ---------------------------------------


def test_bang_tu_vung_khong_khai_bao_hong():
    raw = json.loads(_BANG.read_text(encoding="utf-8"))
    assert raw["loai"] and raw["co_quan"] and raw["quoc_hoi"]
    # KHÔNG assert `ma.isupper()`: `TTr` (Tờ trình) và `TTg` (Thủ tướng) là chính tả CHUẨN.
    # Chính vì thế `_lam_sach_ma` không được `.upper()` mù mà phải theo từ vựng.
    for ma, v in raw["loai"].items():
        assert ma.isalpha(), ma
        assert v.get("ten"), ma
        assert v.get("qppl") in (True, False, None), ma
    for ma in raw["co_quan"]:
        assert ma.isalpha(), ma
    # Không có hai mã chỉ khác nhau hoa/thường — nếu có thì `_theo_chinh_ta` chọn bừa.
    for bang in ("loai", "co_quan"):
        thap = [m.casefold() for m in raw[bang]]
        assert len(thap) == len(set(thap)), bang
    # Bốn khoá Quốc hội trong nghiên cứu.
    assert set(raw["khoa_quoc_hoi"]) == {"12", "13", "14", "15"}
