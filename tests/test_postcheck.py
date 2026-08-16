"""Hậu kiểm câu trả lời (T109 Phase 2). Thuần hàm, không mạng."""
from app.reasoning.postcheck import hau_kiem

_CHUNKS = [{"doc_title": "Thông tư 40/2024/TT-NHNN", "article": "Điều 12 Khoản 1-3"}]
_NF = "Chưa tìm thấy quy định."


def test_trich_dan_khop_thi_sach():
    assert hau_kiem("Theo [Thông tư 40/2024 — Điều 12 Khoản 1] thì...", _CHUNKS, not_found=_NF) == []


def test_khong_trich_dan_thi_bao_thieu():
    assert hau_kiem("Trả lời không kèm căn cứ.", _CHUNKS, not_found=_NF) == ["thiếu_trích_dẫn"]


def test_so_hieu_ngoai_can_cu():
    r = hau_kiem("Xem [Thông tư 99/2099 — Điều 5].", _CHUNKS, not_found=_NF)
    assert r and r[0].startswith("trích_dẫn_ngoài_căn_cứ")


def test_dung_so_hieu_khac_dieu_van_bao():
    # cùng văn bản nhưng dẫn điều KHÔNG có trong chunk → nghi bịa
    r = hau_kiem("Xem [Thông tư 40/2024 — Điều 99].", _CHUNKS, not_found=_NF)
    assert r and r[0].startswith("trích_dẫn_ngoài_căn_cứ")


def test_cau_chua_tim_thay_khong_can_trich_dan():
    assert hau_kiem(_NF, _CHUNKS, not_found=_NF) == []


def test_trich_dan_thieu_so_hieu_thi_bo_qua():
    # không đủ số hiệu để đối chiếu → KHÔNG báo giả
    assert hau_kiem("Theo [Nội bộ — Điều 3] thì...", _CHUNKS, not_found=_NF) == []


def test_dieu_khop_theo_tien_to_khoan():
    # answer dẫn "Điều 12" trần, chunk là "Điều 12 Khoản 1-3" → cùng Điều → khớp
    assert hau_kiem("Theo [Thông tư 40/2024 — Điều 12].", _CHUNKS, not_found=_NF) == []
