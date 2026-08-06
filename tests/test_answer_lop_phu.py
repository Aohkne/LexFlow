"""Đường trả lời có lớp phủ: nhãn vào prompt, trạng thái vào citation."""
from unittest.mock import patch

from app.core.schemas import ChatRequest
from app.knowledge.lop_phu import ChuThichHieuLuc
from app.reasoning.answer import _citations, _prepare

_CHUNKS = [
    {
        "id": "TT40-2024::Điều 8 Khoản 7",
        "doc_id": "TT40-2024",
        "doc_title": "Thông tư 40/2024",
        "doc_type": "thong_tu",
        "article": "Điều 8 Khoản 7",
        "text": "Hạn mức cũ.",
        "valid_from": "2024-07-01",
        "valid_to": "",
        "superseded": False,
    }
]
_CT = {
    "TT40-2024::Điều 8 Khoản 7": ChuThichHieuLuc(
        nhanh="nen_da_sua",
        trang_thai="da_sua",
        trich_dan_dung_chu="TT40-2024 Điều 8 Khoản 7 (đã sửa bởi TT41-2025 Điều 1 Khoản 2)",
        khoa_goc="40/2024/TT-NHNN#than/dieu_8#khoan_7",
        khoa_dich="40/2024/TT-NHNN#than/dieu_8#khoan_7",
        sua_boi_doc_id="TT41-2025",
        sua_boi_article="Điều 1 Khoản 2",
        ban_hien_hanh='"7. Hạn mức mới là 200 triệu đồng."',
    )
}


def test_prompt_mang_nhan_va_ban_hien_hanh():
    with (
        patch("app.reasoning.answer.hybrid_search", return_value=_CHUNKS),
        patch("app.reasoning.answer.chu_thich_ket_qua", return_value=(_CHUNKS, _CT)),
        patch("app.core.config.settings.graph_augment", False),
    ):
        chunks, ct, system, prompt = _prepare(ChatRequest(query="hạn mức?"))
    assert "đã sửa bởi TT41-2025 Điều 1 Khoản 2" in prompt
    assert "Bản hiện hành" in prompt and "200 triệu" in prompt
    assert ct == _CT


def test_citation_mang_trang_thai():
    cits = _citations(_CHUNKS, _CT)
    assert cits[0].trang_thai == "da_sua"
    assert cits[0].sua_boi_doc_id == "TT41-2025"
    assert "200 triệu" in cits[0].ban_hien_hanh


def test_citation_khong_co_chu_thich_van_hop_le():
    cits = _citations(_CHUNKS, {})
    assert cits[0].trang_thai is None and cits[0].ban_hien_hanh is None


def test_co_tat_thi_khong_goi_lop_phu():
    with (
        patch("app.reasoning.answer.hybrid_search", return_value=_CHUNKS),
        patch("app.core.config.settings.graph_augment", False),
        patch("app.core.config.settings.overlay_router", False),
        patch("app.reasoning.answer.chu_thich_ket_qua") as gia,
    ):
        _chunks, ct, _system, _prompt = _prepare(ChatRequest(query="hạn mức?"))
    gia.assert_not_called()
    assert ct == {}
