"""Đối chiếu tuân thủ không được lấy điều luật đã bị bãi bỏ ở cấp khoản làm căn cứ."""
from unittest.mock import patch

from app.knowledge.lop_phu import ChuThichHieuLuc
from app.reasoning.review import NOT_ASSESSED, _review_article

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


def test_pham_vi_against_ids_duoc_truyen_xuong_lop_phu():
    """Fix wave 06/08, IMPORTANT 3: chunk lớp phủ kéo thêm vào `by_id` có thể làm `_judge`
    đặt `legal_doc_id` ra NGOÀI phạm vi đối chiếu — chặn ngay ở chỗ kéo."""
    with (
        patch("app.reasoning.review.search_in_docs", return_value=[_SONG]),
        patch("app.reasoning.review.chu_thich_ket_qua", return_value=([_SONG], {})) as gia,
        patch("app.reasoning.review._judge", return_value={
            "verdict": "pass", "legal_chunk_id": "TT40-2024::Điều 3", "title": "ok",
            "summary": "", "internal_quote": "", "legal_quote": "", "suggestion": None}),
    ):
        _review_article("Điều 1", "nội dung nội bộ", ["TT40-2024", "TT41-2025"], "2026-08-06")
    assert gia.call_args.kwargs["pham_vi"] == {"TT40-2024", "TT41-2025"}


def test_moi_can_cu_deu_bi_bai_bo_thi_khong_phan_dinh():
    """Fallback của chu_thich_ket_qua trả nguyên danh sách khi loại hết — /reviews không được
    coi đó là "còn căn cứ để phán": phải dừng ở not_assessed, không tốn lượt gọi LLM."""
    with (
        patch("app.reasoning.review.search_in_docs", return_value=[_CHET]),
        patch("app.reasoning.review.chu_thich_ket_qua", return_value=([_CHET], _CT)),
        patch("app.reasoning.review._judge") as gia_judge,
    ):
        f = _review_article("Điều 1", "nội dung nội bộ", ["TT40-2024"], "2026-08-06")

    gia_judge.assert_not_called()
    assert f.verdict == NOT_ASSESSED
    assert "TT40-2024 Điều 9 (đã bị bãi bỏ bởi TT41-2025 Điều 2)" in f.summary
