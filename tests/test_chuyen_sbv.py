"""Ghim phép chuyển bộ test SBV-LawGraph → bộ câu hỏi eval.

Nhãn sinh ra là suy diễn từ file nguồn + corpus, không phải nhãn người — sai ở đây không làm
test nào đỏ, chỉ làm bảng kết quả sai một cách trông rất bình thường.
"""
from __future__ import annotations

import pytest

from eval.chuyen_sbv import NhanHong, chuyen, dieu_co_that, tach_nhan


def test_tach_tu_phai_khong_phai_tu_trai():
    """Hậu tố là SỐ ĐIỀU. Tách từ trái thì "…_21" ra "2" và nhãn trỏ nhầm điều."""
    assert tach_nhan("08/2023/tt-nhnn_21") == ("08/2023/TT-NHNN", "21")


def test_chu_thuong_duoc_viet_hoa_de_khop_corpus():
    """Nhãn SBV viết thường hoàn toàn; corpus ghi số hiệu viết hoa."""
    assert tach_nhan("40/2024/tt-nhnn_18") == ("40/2024/TT-NHNN", "18")


def test_bo_dau_de_khop_nghi_dinh():
    """Corpus ghi "NĐ-CP", bộ SBV ghi "nd-cp"."""
    assert tach_nhan("52/2024/nd-cp_3")[0] == "52/2024/ND-CP"


def test_so_dieu_co_chu_cai():
    assert tach_nhan("40/2024/tt-nhnn_12a") == ("40/2024/TT-NHNN", "12a")


def test_thieu_gach_duoi_thi_nem():
    with pytest.raises(NhanHong):
        tach_nhan("12/2022/tt-nhnn")


def test_hau_to_khong_phai_so_thi_nem():
    """Nhãn hỏng là lỗi ĐỊNH DẠNG, khác câu ngoài phạm vi — không được nuốt im lặng."""
    with pytest.raises(NhanHong):
        tach_nhan("12/2022/tt-nhnn_dieu-ba")


def _corpus() -> dict:
    """Bốn văn bản đủ để dựng mọi ca: còn hiệu lực, đã hết hiệu lực, điều bị chẻ khoản."""
    return {
        "documents": [
            {"doc_id": "TT40-2024", "so_hieu": "40/2024/TT-NHNN",
             "valid_from": "2024-07-17", "valid_to": None,
             "articles": [{"article": "Điều 18", "text": ""},
                          {"article": "Điều 23 Khoản 1-3", "text": ""},
                          {"article": "Điều 23 Khoản 4-6", "text": ""}]},
            {"doc_id": "TT17-2024", "so_hieu": "17/2024/TT-NHNN",
             "valid_from": "2024-07-01", "valid_to": None,
             "articles": [{"article": "Điều 17", "text": ""}]},
            {"doc_id": "ND52-2024", "so_hieu": "52/2024/NĐ-CP",
             "valid_from": "2024-07-01", "valid_to": None,
             "articles": [{"article": "Điều 3", "text": ""}]},
            {"doc_id": "TT23-2014", "so_hieu": "23/2014/TT-NHNN",
             "valid_from": "2014-10-15", "valid_to": "2024-07-01",
             "articles": [{"article": "Điều 5", "text": ""}]},
        ],
        "relationships": [],
    }


def test_dieu_co_that_gom_theo_so_dieu():
    assert dieu_co_that(_corpus())["TT40-2024"] == {"18", "23"}


def test_dieu_bi_che_khoan_van_tinh_la_co():
    """`pipeline._split_khoan` chẻ điều dài thành "Điều 23 Khoản 1-3" — nhãn vàng vẫn là "Điều 23".

    Nếu kiểm bằng so khớp nhãn nguyên văn thì mọi điều dài đều bị coi là không tồn tại.
    """
    assert "23" in dieu_co_that(_corpus())["TT40-2024"]


def test_van_ban_khong_co_dieu_nao_thi_tap_rong():
    corpus = {"documents": [{"doc_id": "X", "so_hieu": "1/2020/TT-NHNN", "articles": []}],
              "relationships": []}
    assert dieu_co_that(corpus) == {"X": set()}


HOM_NAY = "2026-08-12"


def _cau(arts: list[str], qid: int = 1) -> dict:
    return {
        "question_id": qid,
        "question": "câu hỏi thử",
        "url": "https://thuvienphapluat.vn/hoi-dap-phap-luat/x.html",
        "relevant_articles": arts,
        "reference_answer": "trả lời tham chiếu",
    }


def test_cau_du_van_ban_vao_bo_dung_duoc():
    dung, kcc, bo = chuyen([_cau(["40/2024/tt-nhnn_18"])], _corpus(), HOM_NAY)
    assert len(dung) == 1 and not kcc and not bo
    assert dung[0]["relevant_articles"] == ["TT40-2024::Điều 18"]
    assert dung[0]["relevant_docs"] == ["TT40-2024"]
    assert dung[0]["expected_doc"] == "TT40-2024"
    assert dung[0]["question_id"] == 1


def test_cau_ngoai_corpus_vao_bo_khong_can_cu():
    dung, kcc, bo = chuyen([_cau(["12/2022/tt-nhnn_3"])], _corpus(), HOM_NAY)
    assert not dung and not bo
    assert kcc[0]["van_ban_thieu"] == ["12/2022/TT-NHNN"]
    assert "relevant_docs" not in kcc[0] and "relevant_articles" not in kcc[0]


def test_cau_mot_phan_trong_corpus_khong_vao_bo_nao():
    """Câu dẫn cả văn bản trong corpus lẫn ngoài corpus không phải negative sạch (câu này có
    căn cứ thật) và cũng chưa đủ căn cứ để vào bo_sbv.jsonl — phải đếm riêng, không lẫn vào
    file nào cả."""
    dung, kcc, bo = chuyen(
        [_cau(["40/2024/tt-nhnn_18", "12/2022/tt-nhnn_3"])], _corpus(), HOM_NAY
    )
    assert not dung and not kcc
    assert bo["một phần trong corpus"] == 1


def test_dieu_khong_ton_tai_thi_loai_va_dem_rieng():
    """Nhãn trỏ vào Điều 99 của văn bản chỉ có Điều 18/23 ⇒ recall vĩnh viễn 0, phải loại."""
    dung, kcc, bo = chuyen([_cau(["40/2024/tt-nhnn_99"])], _corpus(), HOM_NAY)
    assert not dung and not kcc
    assert bo["nhãn trỏ vào điều không có trong corpus"] == 1


def test_dieu_bi_che_khoan_khong_bi_loai():
    """Corpus giữ "Điều 23 Khoản 1-3"; nhãn vàng là "Điều 23" — vẫn phải nhận."""
    dung, _, bo = chuyen([_cau(["40/2024/tt-nhnn_23"])], _corpus(), HOM_NAY)
    assert len(dung) == 1 and not bo


def test_nhieu_dieu_cung_mot_van_ban():
    dung, _, _ = chuyen([_cau(["40/2024/tt-nhnn_18", "40/2024/tt-nhnn_23"])], _corpus(), HOM_NAY)
    assert dung[0]["relevant_articles"] == ["TT40-2024::Điều 18", "TT40-2024::Điều 23"]
    assert dung[0]["relevant_docs"] == ["TT40-2024"]


def test_as_of_la_hom_nay_khi_moi_van_ban_con_hieu_luc():
    dung, _, _ = chuyen([_cau(["40/2024/tt-nhnn_18"])], _corpus(), HOM_NAY)
    assert dung[0]["as_of"] == HOM_NAY
    assert dung[0]["cua_so"] == ["2024-07-17", None]


def test_as_of_lui_mot_ngay_khi_cua_so_dong():
    """TT23-2014 chết 2024-07-01; `valid_to` là mốc MỞ nên ngày cuối còn đúng là 30/06."""
    dung, _, _ = chuyen([_cau(["23/2014/tt-nhnn_5"])], _corpus(), HOM_NAY)
    assert dung[0]["as_of"] == "2024-06-30"


def test_khong_sinh_must_not_doc():
    """Bộ này không có mặt lỗi thời để đo; sinh `must_not_doc` sẽ làm stale_avoidance giả."""
    dung, _, _ = chuyen([_cau(["40/2024/tt-nhnn_18"])], _corpus(), HOM_NAY)
    assert "must_not_doc" not in dung[0]


def test_khong_mang_reference_answer_sang_file_nhan():
    """Giữ file nhãn sạch; Correctness sẽ join lại theo `question_id`."""
    dung, _, _ = chuyen([_cau(["40/2024/tt-nhnn_18"])], _corpus(), HOM_NAY)
    assert "reference_answer" not in dung[0]


def test_khong_mat_cau_nao():
    rows = [
        _cau(["40/2024/tt-nhnn_18"], qid=1),
        _cau(["12/2022/tt-nhnn_3"], qid=2),
        _cau(["40/2024/tt-nhnn_99"], qid=3),
        _cau([], qid=4),
        _cau(["40/2024/tt-nhnn_18", "12/2022/tt-nhnn_3"], qid=5),
    ]
    dung, kcc, bo = chuyen(rows, _corpus(), HOM_NAY)
    assert len(dung) + len(kcc) + sum(bo.values()) == len(rows)


def test_cau_khong_co_nhan_bi_loai():
    dung, kcc, bo = chuyen([_cau([])], _corpus(), HOM_NAY)
    assert not dung and not kcc and bo["không có nhãn"] == 1
