"""Dò nút bị treo nhầm cha trong cây điều khoản (`check_unit_sequence`).

Kiểu hỏng này KHÔNG làm lệch tổng số đơn vị, nên `check_tree_coverage` mù hoàn toàn với nó:
ở 15/2024/TT-NHNN Điều 15, nguồn đẩy hai đoạn `b)` xuống sau `c)` của khoản 2 nên cả hai cùng
bám khoản 2, khoản 1 mất điểm b — tổng số Điểm vẫn đúng.
"""
import json
from pathlib import Path

import pytest

from app.ingestion.vbpl import check_unit_sequence

CORPUS = Path("data/raw/vbpl/corpus")


def _diem(*sos):
    return [{"cap": "diem", "so": s, "con": []} for s in sos]


def _khoan(so, *diem):
    return {"cap": "khoan", "so": so, "con": list(diem)}


def _dieu(so, *khoan):
    return {"cap": "dieu", "so": so, "con": list(khoan)}


def test_trung_so_thi_bao():
    ra = check_unit_sequence([_dieu("15", _khoan("2", *_diem("a", "c", "b", "b")))])
    assert any("trùng số" in c and "'b'" in c for c in ra)


def test_dut_quang_don_thuan_thi_IM_LANG():
    """40/2024 Điều 37 khoản 1 đi a…e, g, i — toàn văn nguồn vốn không có `h)`.

    Bắt cả đứt quãng là biến một cách đánh số của người soạn thành lỗi.
    """
    cay = [_dieu("37", _khoan("1", *_diem("a", "b", "c", "d", "đ", "e", "g", "i")))]
    assert check_unit_sequence(cay) == []


def test_vang_o_khoan_nay_va_trung_o_khoan_khac_thi_bao():
    """Hai mảnh rời thì im, ghép lại mới thành bằng chứng nút bị treo nhầm cha."""
    cay = [
        _dieu(
            "15",
            _khoan("1", *_diem("a", "c")),
            _khoan("2", *_diem("a", "c", "b", "b")),
        )
    ]
    ra = check_unit_sequence(cay)
    assert any("vắng ở khoản 1" in c and "'b'" in c for c in ra)


def test_hau_to_khong_bi_coi_la_nguoc_thu_tu():
    """"đ1" là cách chèn thêm hợp lệ, không phải dãy đi ngược."""
    assert check_unit_sequence([_dieu("9", _khoan("2", *_diem("d", "đ", "đ1", "e")))]) == []


@pytest.mark.skipif(not CORPUS.is_dir(), reason=f"chưa có corpus đã cào tại {CORPUS}")
def test_tren_corpus_that():
    """Chạy trên chính corpus đã cào: bắt đúng ca thật, và KHÔNG bắt ca hợp lệ."""
    theo_doc = {}
    for f in CORPUS.rglob("*.json"):
        j = json.loads(f.read_text(encoding="utf-8"))
        if j.get("provisions"):
            theo_doc[j["doc_id"]] = check_unit_sequence(j["provisions"])
    assert theo_doc, "corpus có mà không văn bản nào có cây điều khoản"

    # Ca thật đã soi DOM xác nhận (15/2024 Điều 15): phải bắt được.
    assert any(
        "dieu_15" in c for c in theo_doc.get("TT15-2024", [])
    ), f"bỏ sót ca đã biết ở TT15-2024: {theo_doc.get('TT15-2024')}"

    # Ca hợp lệ (40/2024 Điều 37 khoản 1 thiếu chữ `h` vì nguồn vốn không có): phải im.
    assert not [
        c for c in theo_doc.get("TT40-2024", []) if "dieu_37" in c
    ], "báo động giả ở TT40-2024 Điều 37 — đứt quãng đơn thuần là hợp lệ"
