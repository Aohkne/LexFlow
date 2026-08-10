"""Ghim phép chuyển bộ TVPL → bộ câu hỏi eval.

Nhãn của hai bộ sinh ra là suy diễn từ corpus, không phải nhãn người — sai ở đây không làm test
nào đỏ, chỉ làm bảng kết quả sai một cách trông rất bình thường. Nên mọi bước suy diễn đều phải
có ca ghim: cắt số hiệu, giao khoảng hiệu lực, mốc `as_of`, và điều kiện loại câu.
"""
from __future__ import annotations

from eval.chuyen_tvpl import chuan_so_hieu, chuyen, cua_so, tra_cuu

HOM_NAY = "2026-08-10"


def _corpus() -> dict:
    return {
        "documents": [
            {"doc_id": "TT23-2014", "so_hieu": "23/2014/TT-NHNN",
             "valid_from": "2014-10-15", "valid_to": "2024-07-01", "articles": []},
            {"doc_id": "TT17-2024", "so_hieu": "17/2024/TT-NHNN",
             "valid_from": "2024-07-01", "valid_to": None, "articles": []},
            {"doc_id": "ND101-2012", "so_hieu": "101/2012/NĐ-CP",
             "valid_from": "2013-03-26", "valid_to": "2024-07-01", "articles": []},
            {"doc_id": "ND52-2024", "so_hieu": "52/2024/NĐ-CP",
             "valid_from": "2024-07-01", "valid_to": None, "articles": []},
        ],
        "relationships": [
            {"source_doc": "TT17-2024", "target_doc": "TT23-2014", "rel_type": "THAY_THE"},
            {"source_doc": "ND52-2024", "target_doc": "ND101-2012", "rel_type": "THAY_THE"},
        ],
    }


def _cau(labels_articles: list[tuple[str, str | None]], oid: int = 1) -> dict:
    return {
        "questionoid": oid,
        "question": "câu hỏi thử",
        "category": ["Tài khoản thanh toán"],
        "reference_parsed": [
            {"law_label": lab, "article": art, "is_topic_tag_page": False}
            for lab, art in labels_articles
        ],
    }


# --- chuẩn hoá số hiệu ---------------------------------------------------------------------

def test_cat_duoi_slug_truoc_khi_viet_hoa():
    """Đuôi slug là chữ thường; viết hoa trước thì không phân biệt được với ký hiệu cơ quan."""
    assert chuan_so_hieu("23/2014/TT-NHNN-huong-dan-mo-su-dung") == "23/2014/TT-NHNN"


def test_giu_nguyen_so_hieu_sach():
    assert chuan_so_hieu("40/2024/TT-NHNN") == "40/2024/TT-NHNN"


def test_bo_dau_de_khop_nghi_dinh():
    """Corpus ghi "NĐ-CP" còn slug URL ghi "ND-CP"."""
    assert chuan_so_hieu("101/2012/NĐ-CP") == chuan_so_hieu("101/2012/ND-CP")


# --- cửa sổ hiệu lực -----------------------------------------------------------------------

def test_cua_so_la_giao_cua_cac_khoang():
    _, hieu_luc, _ = tra_cuu(_corpus())
    assert cua_so(["TT23-2014", "ND101-2012"], hieu_luc) == ("2014-10-15", "2024-07-01")


def test_cua_so_rong_khi_khong_cung_hieu_luc():
    """TT23-2014 chết đúng lúc TT17-2024 sinh ⇒ chưa từng cùng hiệu lực."""
    _, hieu_luc, _ = tra_cuu(_corpus())
    assert cua_so(["TT23-2014", "TT17-2024"], hieu_luc) is None


def test_ke_thua_chi_nhan_khi_duy_nhat():
    """Hai văn bản cùng thay thế một văn bản thì không suy được cái nào kế thừa."""
    c = _corpus()
    c["relationships"].append(
        {"source_doc": "ND52-2024", "target_doc": "TT23-2014", "rel_type": "THAY_THE"}
    )
    _, _, ke_thua = tra_cuu(c)
    assert "TT23-2014" not in ke_thua
    assert ke_thua["ND101-2012"] == "ND52-2024"


# --- chuyển đổi ----------------------------------------------------------------------------

def test_as_of_lui_mot_ngay_vi_valid_to_la_moc_mo():
    dung_thoi, _, _ = chuyen([_cau([("23/2014/TT-NHNN-huong", "Dieu 11")])], _corpus(), HOM_NAY)
    assert dung_thoi[0]["as_of"] == "2024-06-30"
    assert dung_thoi[0]["cua_so"] == ["2014-10-15", "2024-07-01"]


def test_nhan_dieu_duoc_phuc_hoi_dau():
    dung_thoi, _, _ = chuyen([_cau([("23/2014/TT-NHNN", "Dieu 11")])], _corpus(), HOM_NAY)
    assert dung_thoi[0]["relevant_articles"] == ["TT23-2014::Điều 11"]


def test_bo_hien_nay_dao_nhan_va_khong_co_muc_dieu():
    """Cấp văn bản suy được từ THAY_THE; cấp điều thì không — suy xuống đó là bịa."""
    _, hien_nay, _ = chuyen([_cau([("23/2014/TT-NHNN", "Dieu 11")])], _corpus(), HOM_NAY)
    assert hien_nay[0]["relevant_docs"] == ["TT17-2024"]
    assert hien_nay[0]["must_not_doc"] == "TT23-2014"
    assert "relevant_articles" not in hien_nay[0]


def test_loai_cau_dan_van_ban_ngoai_corpus():
    dung_thoi, hien_nay, bo = chuyen([_cau([("09/2020/TT-NHNN", "Dieu 4")])], _corpus(), HOM_NAY)
    assert dung_thoi == [] and hien_nay == []
    assert bo["dẫn văn bản ngoài corpus"] == 1


def test_loai_cau_chi_tro_trang_chu_de():
    cau = _cau([("23/2014/TT-NHNN", "Dieu 11")])
    cau["reference_parsed"][0]["is_topic_tag_page"] = True
    dung_thoi, _, bo = chuyen([cau], _corpus(), HOM_NAY)
    assert dung_thoi == []
    assert bo["không dẫn văn bản nào"] == 1


def test_luat_con_hieu_luc_khong_vao_bo_hien_nay():
    """Không có mặt lỗi thời để đo thì câu đó không thuộc bộ "hiện nay"."""
    dung_thoi, hien_nay, bo = chuyen([_cau([("17/2024/TT-NHNN", "Dieu 5")])], _corpus(), HOM_NAY)
    assert len(dung_thoi) == 1 and hien_nay == []
    assert dung_thoi[0]["as_of"] == HOM_NAY
    assert bo["luật còn hiệu lực, không có mặt lỗi thời để đo"] == 1


def test_cau_nhieu_van_ban_gop_nhan_va_lay_giao_cua_so():
    dung_thoi, hien_nay, _ = chuyen(
        [_cau([("23/2014/TT-NHNN", "Dieu 11"), ("101/2012/ND-CP", "Dieu 3")])], _corpus(), HOM_NAY
    )
    assert dung_thoi[0]["relevant_docs"] == ["ND101-2012", "TT23-2014"]
    assert dung_thoi[0]["relevant_articles"] == ["ND101-2012::Điều 3", "TT23-2014::Điều 11"]
    assert dung_thoi[0]["as_of"] == "2024-06-30"
    assert hien_nay[0]["relevant_docs"] == ["ND52-2024", "TT17-2024"]
