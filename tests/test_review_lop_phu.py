"""Đối chiếu tuân thủ không được lấy điều luật đã bị bãi bỏ ở cấp khoản làm căn cứ."""
from unittest.mock import patch

from app.knowledge.lop_phu import ChuThichHieuLuc
from app.reasoning.review import _review_article

_SONG = {
    "id": "TT40-2024::Điều 3", "doc_id": "TT40-2024", "doc_title": "Thông tư 40/2024",
    "doc_type": "thong_tu", "article": "Điều 3", "text": "Quy định còn hiệu lực.",
    "valid_from": "2024-07-01", "valid_to": "", "superseded": False,
}
_CHET = {**_SONG, "id": "TT40-2024::Điều 9", "article": "Điều 9", "text": "Quy định đã bỏ."}
_CT = {
    "TT40-2024::Điều 9": ChuThichHieuLuc(
        nhanh="nen_da_sua", trang_thai="bi_bai_bo",
        trich_dan_dung_chu="TT40-2024 Điều 9 (đã bị bãi bỏ bởi TT41-2025 Điều 2)",
        khoa_goc="40/2024/TT-NHNN#than/dieu_9",
        khoa_dich="40/2024/TT-NHNN#than/dieu_9",
        sua_boi_doc_id="TT41-2025", sua_boi_article="Điều 2",
    )
}


def test_can_cu_bi_bai_bo_bi_loai_khoi_doi_chieu():
    ghi = {}

    def _gia_judge(prompt: str) -> dict:
        ghi["prompt"] = prompt
        return {"verdict": "pass", "legal_chunk_id": "TT40-2024::Điều 3", "title": "ok",
                "summary": "", "internal_quote": "", "legal_quote": "", "suggestion": None}

    with (
        patch("app.reasoning.review.search_in_docs", return_value=[_CHET, _SONG]),
        patch("app.reasoning.review.chu_thich_ket_qua", return_value=([_SONG], _CT)),
        patch("app.reasoning.review._judge", side_effect=_gia_judge),
    ):
        f = _review_article("Điều 1", "nội dung nội bộ", ["TT40-2024"], "2026-08-06")

    assert "TT40-2024::Điều 9" not in ghi["prompt"]  # căn cứ chết không vào prompt
    assert f.legal_doc_id == "TT40-2024" and "Điều 3" in (f.legal_ref or "")


def test_can_cu_da_sua_thi_legal_live_van_dung_nhung_co_ghi_chu():
    ct = {
        "TT40-2024::Điều 3": ChuThichHieuLuc(
            nhanh="nen_da_sua", trang_thai="da_sua",
            trich_dan_dung_chu="TT40-2024 Điều 3 (đã sửa bởi TT41-2025 Điều 1)",
            khoa_goc="40/2024/TT-NHNN#than/dieu_3", khoa_dich="40/2024/TT-NHNN#than/dieu_3",
            sua_boi_doc_id="TT41-2025", sua_boi_article="Điều 1",
        )
    }
    with (
        patch("app.reasoning.review.search_in_docs", return_value=[_SONG]),
        patch("app.reasoning.review.chu_thich_ket_qua", return_value=([_SONG], ct)),
        patch("app.reasoning.review._judge", return_value={
            "verdict": "pass", "legal_chunk_id": "TT40-2024::Điều 3", "title": "ok",
            "summary": "", "internal_quote": "", "legal_quote": "", "suggestion": None}),
    ):
        f = _review_article("Điều 1", "nội dung nội bộ", ["TT40-2024"], "2026-08-06")
    assert f.legal_live is True
    assert "đã sửa bởi TT41-2025" in (f.legal_ref or "")
