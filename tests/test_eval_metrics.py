"""Metric truy hồi của bài báo SBV-LawGraph (§5.3) — ghim công thức, khớp nhãn và ca biên.

Metric sai là kiểu lỗi im lặng nhất trong repo này: nó không làm hỏng câu trả lời nào, chỉ làm
mọi kết luận rút ra từ bảng kết quả sai. Nên các ca ở đây tính tay trước, viết số vào test, rồi
mới so với hàm — không lấy đầu ra của hàm làm kỳ vọng.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval import bo_cau_hoi, metrics


# ---------------------------------------------------------------- khớp nhãn


def test_khop_tien_to_khong_duoc_nham_dieu_3_voi_dieu_30():
    """Ranh giới là dấu cách. Corpus thật có đủ cặp Điều 3 / Điều 30..39 để nhầm hằng ngày."""
    assert metrics.trung("TT40-2024::Điều 3 Khoản 1-6", "TT40-2024::Điều 3")
    assert metrics.trung("TT40-2024::Điều 3 (phần 2)", "TT40-2024::Điều 3")
    assert not metrics.trung("TT40-2024::Điều 30", "TT40-2024::Điều 3")


def test_khop_hai_chieu_giua_hai_do_min_khac_nhau():
    """Nhãn vàng cấp khoản vs chunk cấp điều: điều được trả về CHỨA khoản vàng ⇒ trúng."""
    assert metrics.trung("TT40-2024::Điều 12", "TT40-2024::Điều 12 Khoản 1")
    assert metrics.trung("TT40-2024::Điều 12 Khoản 1", "TT40-2024::Điều 12")


def test_khac_van_ban_thi_khong_trung_du_nhan_dieu_giong_het():
    assert not metrics.trung("TT17-2024::Điều 12", "TT40-2024::Điều 12")


def test_khoa_dieu_gom_cac_manh_cua_mot_dieu_ve_mot_khoa():
    manh = [
        {"doc_id": "TT40-2024", "article": "Điều 12 Khoản 1-3"},
        {"doc_id": "TT40-2024", "article": "Điều 12 Khoản 4-6"},
        {"doc_id": "TT40-2024", "article": "Điều 12 (phần 2)"},
    ]
    assert {metrics.khoa_dieu(m) for m in manh} == {"TT40-2024::Điều 12"}


def test_khoa_dieu_giu_nguyen_nhan_la():
    """Nhãn không mở đầu bằng "Điều N" thì không gom — thà khoá lạ còn hơn gộp nhầm."""
    assert metrics.khoa_dieu({"doc_id": "X", "article": "Phụ lục I"}) == "X::Phụ lục I"


# ---------------------------------------------------------------- công thức


def test_trung_o_hang_1_thi_moi_metric_dat_tran():
    r = metrics.do_mot_cau(["A", "B", "C"], ["A"], k=1)
    assert r == {"recall": 1.0, "precision": 1.0, "rr": 1.0, "f2": 1.0}


def test_khong_trung_gi_thi_ve_0_chu_khong_bien_mat():
    r = metrics.do_mot_cau(["X", "Y"], ["A"], k=2)
    assert r == {"recall": 0.0, "precision": 0.0, "rr": 0.0, "f2": 0.0}


def test_precision_chia_cho_k_chu_khong_phai_so_ket_qua_tra_ve():
    """P@5 với 1/1 kết quả đúng là 0.2, không phải 1.0 — mẫu số là k theo đúng bài báo."""
    r = metrics.do_mot_cau(["A"], ["A"], k=5)
    assert r["precision"] == pytest.approx(0.2)
    assert r["recall"] == 1.0


def test_nhieu_nhan_vang_hon_k_thi_recall_bi_tran_boi_k():
    """|R| = 3 nhưng k = 2 ⇒ recall tối đa 2/3. Ca này bắt lỗi lấy nhầm mẫu số."""
    r = metrics.do_mot_cau(["A", "B", "C"], ["A", "B", "C"], k=2)
    assert r["recall"] == pytest.approx(2 / 3)
    assert r["precision"] == 1.0
    # F2 = 5·1·(2/3) / (4·1 + 2/3) = 3.3333 / 4.6667
    assert r["f2"] == pytest.approx(5 * (2 / 3) / (4 + 2 / 3))


def test_rr_bang_0_khi_ket_qua_dung_nam_ngoai_top_k():
    """Trúng ở hạng 3 nhưng đo tại k=2 ⇒ RR = 0, không phải 1/3."""
    assert metrics.do_mot_cau(["X", "Y", "A"], ["A"], k=2)["rr"] == 0.0
    assert metrics.do_mot_cau(["X", "Y", "A"], ["A"], k=5)["rr"] == pytest.approx(1 / 3)


def test_khu_trung_truoc_khi_cat_top_k():
    """Ba mảnh cùng một điều chỉ chiếm MỘT hạng — nếu không, P@k tụt vì văn bản dài."""
    khoa = ["D::Điều 1", "D::Điều 1", "D::Điều 1", "D::Điều 9"]
    assert metrics.do_mot_cau(khoa, ["D::Điều 9"], k=2)["rr"] == pytest.approx(1 / 2)


def test_f2_nghieng_ve_recall():
    """F2 phải thưởng recall hơn precision — đảo hai giá trị cho ra số khác nhau."""
    assert metrics.f2(0.2, 1.0) > metrics.f2(1.0, 0.2)
    assert metrics.f2(0.0, 0.0) == 0.0


def test_nhan_vang_rong_thi_ve_0_chu_khong_chia_cho_0():
    assert metrics.do_mot_cau(["A"], [], k=5)["recall"] == 0.0


def test_tong_hop_bao_ca_hai_duong_tinh_f2():
    """`f2` tính từ hai trung bình (so với bài báo), `f2_macro` là trung bình F2 từng câu."""
    theo_cau = [
        metrics.do_mot_cau(["A"], ["A"], k=1),
        metrics.do_mot_cau(["X"], ["A"], k=1),
    ]
    g = metrics.tong_hop(theo_cau)
    assert g["recall"] == pytest.approx(0.5)
    assert g["mrr"] == pytest.approx(0.5)
    assert g["f2"] == pytest.approx(metrics.f2(0.5, 0.5))
    assert g["f2_macro"] == pytest.approx(0.5)


def test_tong_hop_rong_khong_no():
    assert metrics.tong_hop([])["mrr"] == 0.0


# ---------------------------------------------------------------- loader


def test_bo_36_cau_hien_co_chay_nguyen_trang(tmp_path):
    """Tương thích ngược: chỉ có `expected_doc` ⇒ `relevant_docs` suy ra một phần tử."""
    p = tmp_path / "q.jsonl"
    p.write_text(
        json.dumps({"query": "hỏi gì đó", "expected_doc": "TT40-2024"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (c,) = bo_cau_hoi.nap(p)
    assert c.relevant_docs == ("TT40-2024",)
    assert c.relevant_articles == ()


def test_nhan_dieu_thieu_dau_hai_cham_bi_tu_choi(tmp_path):
    p = tmp_path / "q.jsonl"
    p.write_text(
        json.dumps(
            {"query": "x", "relevant_docs": ["A"], "relevant_articles": ["Điều 12"]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with pytest.raises(bo_cau_hoi.LoiBoCauHoi, match="::"):
        bo_cau_hoi.nap(p)


def test_dong_hong_nem_loi_chu_khong_bi_bo_qua(tmp_path):
    p = tmp_path / "q.jsonl"
    p.write_text('{"query": "ok", "expected_doc": "A"}\n{khong-phai-json}\n', encoding="utf-8")
    with pytest.raises(bo_cau_hoi.LoiBoCauHoi):
        bo_cau_hoi.nap(p)


def test_thieu_query_nem_loi(tmp_path):
    p = tmp_path / "q.jsonl"
    p.write_text('{"expected_doc": "A"}\n', encoding="utf-8")
    with pytest.raises(bo_cau_hoi.LoiBoCauHoi, match="query"):
        bo_cau_hoi.nap(p)


def test_nap_duoc_bo_cau_hoi_that_trong_repo():
    """Ghim rằng `eval/questions.jsonl` hợp lệ theo định dạng đã chốt — không phải chỉ tmp file."""
    p = Path("eval/questions.jsonl")
    if not p.exists():  # pragma: no cover — repo sạch luôn có file này
        pytest.skip("thiếu eval/questions.jsonl")
    cau = bo_cau_hoi.nap(p)
    assert len(cau) == 36
    assert all(c.relevant_docs for c in cau)
