"""Test bóc viện dẫn — offline. Mọi câu mẫu lấy NGUYÊN VĂN từ corpus thật."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.ontology.citation import parse_citations, to_node_ids

_CTX = "17/2024/TT-NHNN"


def _one(text: str):
    refs = parse_citations(text)
    assert len(refs) == 1, [r.raw for r in refs]
    return refs[0]


# --- hậu tố tiết: điều spec bỏ sót -----------------------------------------


def test_giu_hau_to_tiet_khong_nuot_im_lang():
    """Văn phạm spec `(điểm <chữ cái>\\s+)?` sẽ khớp "điểm b" rồi bỏ "(i)".

    Bỏ im lặng nghĩa là giải viện dẫn về đích RỘNG HƠN thực tế mà không báo gì.
    """
    r = _one("quy định tại điểm b(i) khoản này mà vẫn không đủ")
    assert [(d.diem, d.tiet) for d in r.diem] == [("b", "i")]
    assert r.co_tiet


def test_tiet_co_khoang_trang_va_nhieu_dich():
    r = _one("theo quy định tại điểm c (i) khoản 2 Điều này, tỷ lệ ký quỹ là 100%")
    assert [(d.diem, d.tiet) for d in r.diem] == [("c", "i")]

    r2 = _one("quy định tại điểm a(ii), b(ii) và b(iii) khoản này dưới hình thức")
    assert [(d.diem, d.tiet) for d in r2.diem] == [("a", "ii"), ("b", "ii"), ("b", "iii")]


def test_tiet_khong_vao_khoa_node_nhung_khong_mat():
    """Đã chốt không địa chỉ hoá tiết — nhưng phải biết viện dẫn hẹp hơn node."""
    r = _one("quy định tại điểm b(i) khoản này")
    ids = to_node_ids(r, _CTX, ctx_dieu="16", ctx_khoan="1")
    assert ids == ["17/2024/TT-NHNN#than/dieu_16#khoan_1#diem_b"]
    assert "tiet" not in ids[0]
    assert r.co_tiet  # sự thật "hẹp hơn" vẫn còn để bên gọi xử lý


def test_gop_dich_trung_khi_khac_nhau_o_tiet():
    r = _one("quy định tại điểm b(ii) và b(iii) khoản 2 Điều 5")
    assert to_node_ids(r, _CTX) == ["17/2024/TT-NHNN#than/dieu_5#khoan_2#diem_b"]


# --- nhiều đích trong một câu ----------------------------------------------


def test_danh_sach_diem_khong_an_chu_diem_va_va():
    """Bẫy: tách chữ cái ngây thơ sẽ lấy `đ`,`i`,`m` từ chữ "điểm" và `v` từ "và"."""
    r = _one(
        "ngoài các điều kiện quy định tại điểm a, điểm b, điểm c, điểm d "
        "và điểm đ khoản 2 Điều này"
    )
    assert [d.diem for d in r.diem] == ["a", "b", "c", "d", "đ"]
    assert r.khoan == ["2"]


def test_danh_sach_diem_viet_tat():
    r = _one("quy định tại điểm c, d, đ khoản 1 Điều 12 Nghị định này")
    assert [d.diem for d in r.diem] == ["c", "d", "đ"]


def test_nhieu_khoan():
    r = _one("theo quy định tại khoản 2, 3 Điều 12 Thông tư này và:")
    assert r.khoan == ["2", "3"]
    assert len(to_node_ids(r, _CTX)) == 2


# --- tự tham chiếu ---------------------------------------------------------


def test_khoan_nay_thieu_ngu_canh_thi_tra_rong_chu_khong_no_ra():
    """Trả "Điều 16" cho câu viết "điểm b(i) khoản này" là mở rộng đích lặng lẽ."""
    r = _one("quy định tại điểm b(i) khoản này")
    assert r.khoan_self
    assert to_node_ids(r, _CTX, ctx_dieu="16") == []  # thiếu ctx_khoan → rỗng
    assert to_node_ids(r, _CTX, ctx_dieu="16", ctx_khoan="1")


def test_dieu_nay_dung_ngu_canh():
    r = _one("quy định tại khoản 4 Điều này")
    assert r.dieu_self and r.noi_bo
    assert to_node_ids(r, _CTX, ctx_dieu="22") == ["17/2024/TT-NHNN#than/dieu_22#khoan_4"]


# --- văn bản ngoài + độ tin cậy --------------------------------------------


def test_so_hieu_van_ban_ngoai():
    r = _one("quy định tại khoản 2 Điều 22 Nghị định 52/2024/NĐ-CP")
    assert r.van_ban == "52/2024/NĐ-CP"
    assert not r.noi_bo and r.do_tin_cay == "trung_binh"
    assert to_node_ids(r, _CTX) == ["52/2024/NĐ-CP#than/dieu_22#khoan_2"]


def test_hau_to_chu_tren_dieu():
    r = _one("quy định tại Điều 15a của Thông tư số 40/2024/TT-NHNN")
    assert r.dieu == ["15a"]
    assert to_node_ids(r, _CTX) == ["40/2024/TT-NHNN#than/dieu_15a"]


def test_noi_bo_tin_cay_cao_hon():
    """SCHEMA_KG §2.b: đích không phải phân giải tên văn bản thì chắc chắn hơn."""
    assert _one("khoản 2 Điều này").do_tin_cay == "cao"
    assert _one("khoản 2 Điều 22 Nghị định 52/2024/NĐ-CP").do_tin_cay == "trung_binh"


# --- dương tính giả: phần đắt nhất -----------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "mở tài khoản thanh toán của khách hàng tại ngân hàng",  # "tài khoản" x69
        "đáp ứng điều kiện cung ứng dịch vụ và điều chỉnh hạn mức",  # "điều" thường
        "tại điểm nhận được lệnh chuyển tiền, ngân hàng phục vụ",  # "điểm" thường
        "số dư tài khoản đảm bảo thanh toán",
        "Điều khoản thi hành",
    ],
)
def test_khong_bat_chu_thuong(text):
    assert parse_citations(text) == []


def test_chu_dieu_phai_viet_hoa():
    """Spec: `Điều` viết hoa, `khoản`/`điểm` viết thường — đó là dấu phân biệt."""
    assert parse_citations("điều 22 của luật này") == []
    assert parse_citations("Điều 22") != []


# --- chạy trên corpus thật --------------------------------------------------


def test_bao_phu_corpus_that():
    """Chạy trên toàn corpus: không nổ, và bắt được đúng 29 viện dẫn có tiết.

    Bốn mốc: 4 (cả 4 của TT23/2019) → 17 (nạp đợt 1, 05/08: TT41 +5, TT66 +8) → 23 (nạp đợt 2:
    TT30-2025 +3, TT34 +2, TT38 +1) → 29 (nạp 23 văn bản bộ SBV, 14/08: TT57-2024 +5, TT50-2024 +1).
    Toàn bộ số tăng đến từ thông tư sửa đổi nhắm vào tiết (`điểm b (ii) khoản 4 Điều 11`…),
    tức viện dẫn hẹp hơn node đến từ chính loại văn bản mà tầng địa chỉ hoá phải đỡ được.
    """
    corpus = Path("data/corpus.real.json")
    if not corpus.exists():
        pytest.skip("chưa có corpus thật")
    c = json.loads(corpus.read_text(encoding="utf-8"))
    blob = "\n".join(a["text"] for d in c["documents"] for a in d.get("articles", []))
    refs = parse_citations(blob)
    assert len(refs) > 400
    co_tiet = [r for r in refs if r.co_tiet]
    assert len(co_tiet) == 29, [r.raw for r in co_tiet]
    # Mọi span phải cắt đúng chuỗi gốc.
    for r in refs:
        assert blob[r.span[0] : r.span[1]] == r.raw
    # Không được bắt nhầm "tài khoản ..."
    assert not any(re.search(r"tài\s+khoản", r.raw) for r in refs)
