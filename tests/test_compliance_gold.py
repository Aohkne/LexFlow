"""Bóc nhãn vàng từ comment pháp lý trong docx."""
from __future__ import annotations

from eval.compliance.lam_gold import chuan_hoa, loai_so_bo


def test_chuan_hoa_van_noi():
    # Đo thật trong brainstorm: không chuẩn hoá thì parse_citations bắt 0/95 comment
    assert "Nghị định 52/2024/NĐ-CP" in chuan_hoa("theo NĐ 52/2024/NĐ-CP")
    assert "Thông tư 18/2024/TT-NHNN" in chuan_hoa("khoản 24 điều 3 TT 18/2024/TT-NHNN")
    assert "Điều 3" in chuan_hoa("khoản 24 điều 3")
    assert "TT-NHNN" in chuan_hoa("TT 64/2024/TT_NHNN")


def test_loai_so_bo():
    assert loai_so_bo(["52/2024/NĐ-CP#than/dieu_3"], "bổ sung theo NĐ 52") == "phap_ly"
    assert loai_so_bo([], "đối chiếu mẫu HĐ khung theo quy định nội bộ") == "noi_bo"
    assert loai_so_bo([], "Đơn vị làm rõ nội dung này") == "lam_ro"
    assert loai_so_bo([], "Bỏ từ Thẻ để tránh nhầm lẫn") == "van_phong"
