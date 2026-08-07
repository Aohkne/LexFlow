"""Khối TRÍCH DẪN trong văn bản sửa đổi — đánh số bên trong là của văn bản BỊ sửa.

Vì sao có file này: một văn bản sửa đổi chép nguyên văn nội dung mới vào giữa hai dấu ngoặc
kép, và phần chép mang đánh số của văn bản kia. Không phân biệt thì khoá
`80/2016/NĐ-CP#than/dieu_1#khoan_5` trỏ vào **hai thứ khác nhau** — một trong hai thực chất là
nội dung của ND101 — tức đúng kiểu nhập nhằng mà cả lớp khoá này sinh ra để chặn.

Ca thật dùng để canh là ND80 Điều 1: đếm phẳng ra 14 khoản, thật ra **10 của ND80 + 4 của
ND101**, và cây `provisions` của nguồn cũng nói 10.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ingestion.vbpl_corpus import file_da_chuyen_khuon
from app.ontology.parser import parse_dieu, trong_trich_dan

_GOC = Path("data/raw/vbpl")


def _tim(so_hieu: str):
    for p in file_da_chuyen_khuon(_GOC):
        m = json.loads(p.read_text(encoding="utf-8"))
        if m.get("so_hieu") == so_hieu:
            return m
    return None


# --- 1. Mặt nạ: ba loại ngoặc, và lối lui khi nguồn viết lệch -----------------


def test_ba_loai_ngoac():
    """`"` đảo trạng thái, `“` mở, `”` đóng. Cả ba đều gặp trong lô đã crawl."""
    assert trong_trich_dan('a"b"c')[:5] == [False, True, True, True, False]
    assert trong_trich_dan("a“b”c")[:5] == [False, True, True, True, False]


def test_chinh_ky_tu_ngoac_duoc_coi_la_TRONG():
    """Để dòng mở đầu bằng ngoặc (`"4. Tổ chức…`) cũng bị coi là trong khối."""
    assert trong_trich_dan('"4. X"')[0] is True


def test_ngoac_LECH_thi_bo_luat_chu_khong_doan():
    """Đoán chỗ đóng khi nguồn viết thiếu ngoặc sẽ nuốt phần còn lại của Điều.

    Hỏng nặng hơn hẳn cái nó định sửa, và hỏng im lặng. Không chắc thì làm như cũ.
    """
    assert not any(trong_trich_dan('mở " mà không đóng'))
    assert not any(trong_trich_dan("mở “ mà không đóng"))


def test_mat_na_co_o_BIEN_cho_dong_rong_cuoi():
    """`_line_offsets` sinh một dòng rỗng có `start == len(text)` khi text kết thúc bằng \\n.

    Thiếu ô này thì `parse_dieu` ném `IndexError` — đã xảy ra thật khi viết luật này.
    """
    for t in ('a"b"c', "không có ngoặc", 'ngoặc " lệch'):
        assert len(trong_trich_dan(t)) == len(t) + 1
    parse_dieu('Điều 1. Tiêu đề\n1. Nội dung "trích".\n', "01/2026/TT-TEST")


# --- 2. Ca thật: ND80 Điều 1 --------------------------------------------------


@pytest.mark.skipif(_tim("80/2016/NĐ-CP") is None, reason="chưa crawl ND80/2016")
def test_ND80_dieu_1_ve_dung_10_khoan_khop_cay_nguon():
    m = _tim("80/2016/NĐ-CP")
    t = next(a["text"] for a in m["articles"] if a["article"] == "Điều 1")
    d = parse_dieu(f"Điều 1. {t}", "80/2016/NĐ-CP")

    assert [k.so_hien_thi for k in d.khoan] == [str(i) for i in range(1, 11)]
    cay = [c["so"] for c in m["provisions"][0]["con"] if c["cap"] == "khoan"]
    assert [k.so_hien_thi for k in d.khoan] == cay, "phải khớp cây provisions của nguồn"


@pytest.mark.skipif(_tim("80/2016/NĐ-CP") is None, reason="chưa crawl ND80/2016")
def test_khoi_trich_dan_O_LAI_trong_khoan_me_chu_khong_bi_vut():
    """Bỏ khoản-giả KHÁC hẳn bỏ chữ. Nội dung được chép là *thứ khoản này sửa thành*, và
    không có nó thì khoản 1 chỉ còn câu lệnh trống nghĩa."""
    m = _tim("80/2016/NĐ-CP")
    t = next(a["text"] for a in m["articles"] if a["article"] == "Điều 1")
    k1 = parse_dieu(f"Điều 1. {t}", "80/2016/NĐ-CP").khoan[0]

    assert k1.text.startswith("1. Sửa đổi, bổ sung khoản 4, 5, 6, 7, 8 Điều 4 như sau:")
    assert "Chủ tài khoản thanh toán" in k1.text, "khoản 5 của ND101 phải còn trong text"
    assert "Dịch vụ ví điện tử là" in k1.text, "khoản 8 của ND101 phải còn trong text"


@pytest.mark.skipif(_tim("80/2016/NĐ-CP") is None, reason="chưa crawl ND80/2016")
def test_char_span_van_dung_sau_khi_bo_khoan_gia():
    m = _tim("80/2016/NĐ-CP")
    t = next(a["text"] for a in m["articles"] if a["article"] == "Điều 1")
    goc = f"Điều 1. {t}"
    d = parse_dieu(goc, "80/2016/NĐ-CP")
    for k in d.khoan:
        assert goc[k.start : k.end] == k.text, k.so_hien_thi


# --- 3. Điểm và tiết trong ngoặc cũng không được cấp địa chỉ ------------------


def test_diem_trong_ngoac_khong_thanh_diem_cua_khoan_nay():
    t = (
        'Điều 1. Sửa đổi\n'
        '1. Sửa đổi điểm a, b khoản 2 Điều 15 như sau:\n'
        '"a) Có giấy phép thành lập;\n'
        'b) Có phương án kinh doanh."\n'
        '2. Khoản thật của văn bản này.\n'
        'a) Điểm thật của khoản 2.\n'
    )
    d = parse_dieu(t, "01/2026/TT-TEST")
    assert [k.so_hien_thi for k in d.khoan] == ["1", "2"]
    assert d.khoan[0].diem == [], "a) b) trong ngoặc là của văn bản BỊ sửa"
    assert [x.so_hien_thi for x in d.khoan[1].diem] == ["a"]
    assert "Có giấy phép thành lập" in d.khoan[0].text


def test_tiet_trong_ngoac_cung_vay():
    t = (
        'Điều 1. Sửa đổi\n'
        '1. Sửa đổi điểm a khoản 1 Điều 9 như sau:\n'
        '"a) Tổ chức phải:\n'
        '(i) Lưu bản sao giấy tờ;\n'
        '(ii) Lưu trong 05 năm."\n'
    )
    d = parse_dieu(t, "01/2026/TT-TEST")
    assert d.khoan[0].diem == []
    assert "(i) Lưu bản sao giấy tờ" in d.khoan[0].text


# --- 4. Văn bản KHÔNG sửa đổi phải không đổi kết quả --------------------------


@pytest.mark.skipif(_tim("52/2024/NĐ-CP") is None, reason="chưa crawl ND52/2024")
def test_van_ban_goc_khong_bi_luat_nay_dung_toi():
    """ND52 không có khối trích dẫn nào — con số phải y hệt trước khi thêm luật."""
    m = _tim("52/2024/NĐ-CP")
    kh = di = 0
    for a in m["articles"]:
        d = parse_dieu(f"{a['article']}. {a['text']}", "52/2024/NĐ-CP")
        kh += len(d.khoan)
        di += sum(len(k.diem) for k in d.khoan)
    assert (len(m["articles"]), kh, di) == (38, 153, 102)


def test_ngoac_giua_cau_khong_lam_hong_khoan_ke_tiep():
    """Trích dẫn ngắn nằm gọn trong một dòng là chuyện thường, không được ảnh hưởng gì."""
    t = (
        'Điều 1. Giải thích\n'
        '1. "Khách hàng" là tổ chức, cá nhân mở tài khoản.\n'
        '2. "Ngân hàng" là tổ chức tín dụng.\n'
    )
    d = parse_dieu(t, "01/2026/TT-TEST")
    assert [k.so_hien_thi for k in d.khoan] == ["1", "2"]
