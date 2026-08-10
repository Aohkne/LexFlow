"""Conflict Detector: đừng vứt cảnh báo chỉ vì mô hình trích dẫn CHÍNH XÁC HƠN nhãn chunk.

Ca thật, đo 10/08 trên benchmark 06/08 (`conflict_recall 6/7`). Câu hỏi *"Số dư tối đa trên thẻ
trả trước vô danh là bao nhiêu?"* có mâu thuẫn cài sẵn:

    SHB-QD-THE-2023 Mục 6.1     số dư tối đa 20 (hai mươi) triệu đồng
    TT18-2024 Điều 13 khoản 4   "…không được quá 05 (năm) triệu đồng"

Loại trừ từng khả năng: truy hồi lấy **đủ cả hai phía**; bỏ sót **5/5 lần** nên không phải
nhiễu; gọi thẳng `chat_json` với **đúng prompt hiện tại** thì bắt được **3/3**. Thủ phạm nằm ở
hậu xử lý: mô hình trả `id_b = "TT18-2024::Điều 13 Khoản 4"` — địa chỉ chi tiết hơn nhãn chunk
`"TT18-2024::Điều 13"` — và `by_id.get()` không khớp nên `continue`, **bỏ trong im lặng**.
"""
from __future__ import annotations

import logging

import pytest

from app.reasoning import conflict


def _chunk(cid: str, source: str, text: str) -> dict:
    doc_id, _, article = cid.partition("::")
    return {
        "id": cid, "doc_id": doc_id, "doc_title": doc_id,
        "article": article, "source": source, "text": text,
    }


@pytest.fixture
def hai_phia() -> list[dict]:
    return [
        _chunk("SHB-QD-THE-2023::Mục 6.1", "internal",
               "Thẻ trả trước vô danh do SHB phát hành có số dư tối đa 20 triệu đồng."),
        _chunk("TT18-2024::Điều 13", "external",
               "4. …đảm bảo số dư tại mọi thời điểm trên một thẻ trả trước vô danh "
               "không được quá 05 (năm) triệu đồng Việt Nam…"),
    ]


def _gia_lap(monkeypatch, conflicts: list[dict]) -> None:
    monkeypatch.setattr(conflict, "chat_json", lambda *a, **k: {"conflicts": conflicts})


def test_id_chi_tiet_hon_nhan_chunk_van_duoc_giu(monkeypatch, hai_phia):
    """Đây là ca đang làm hỏng `conflict_recall`."""
    _gia_lap(monkeypatch, [{
        "id_a": "SHB-QD-THE-2023::Mục 6.1",
        "id_b": "TT18-2024::Điều 13 Khoản 4",  # chi tiết hơn nhãn chunk
        "explanation": "Nội bộ 20 triệu, luật trần 5 triệu.",
        "severity": "critical",
    }])

    ra = conflict.detect_conflicts(hai_phia)

    assert len(ra) == 1, "cảnh báo đúng bị vứt vì mô hình trích dẫn chuẩn hơn nhãn chunk"
    assert ra[0].severity == "critical"
    assert {ra[0].article_a, ra[0].article_b} == {"Mục 6.1", "Điều 13"}, (
        "phải quy về ĐÚNG chunk có thật, không giữ nhãn mô hình tự đặt"
    )


def test_khong_khop_nham_dieu_khac_cung_tien_to_chu_so(monkeypatch):
    """`Điều 1` KHÔNG được nuốt `Điều 13` — ranh giới phải là dấu cách."""
    chunks = [
        _chunk("TT18-2024::Điều 1", "external", "Phạm vi điều chỉnh."),
        _chunk("SHB-QD-THE-2023::Mục 6.1", "internal", "Số dư tối đa 20 triệu."),
    ]
    _gia_lap(monkeypatch, [{
        "id_a": "SHB-QD-THE-2023::Mục 6.1",
        "id_b": "TT18-2024::Điều 13 Khoản 4",  # không có chunk nào tương ứng
        "explanation": "…", "severity": "warning",
    }])

    assert conflict.detect_conflicts(chunks) == []


def test_id_khong_giai_duoc_thi_ghi_log_chu_khong_nuot(monkeypatch, hai_phia, caplog):
    """Bỏ một cảnh báo có thể đúng, nhưng phải để lại dấu vết.

    Chính vì im lặng mà khuyết tật này sống sót qua một vòng benchmark: số 6/7 nằm đó nhiều
    ngày, không log, không ai biết cảnh báo bị vứt ở đâu.
    """
    _gia_lap(monkeypatch, [{
        "id_a": "VAN-BAN-LA::Điều 1", "id_b": "TT18-2024::Điều 13",
        "explanation": "…", "severity": "warning",
    }])

    with caplog.at_level(logging.WARNING, logger="app.reasoning.conflict"):
        ra = conflict.detect_conflicts(hai_phia)

    assert ra == []
    assert "VAN-BAN-LA::Điều 1" in caplog.text


def test_chi_giu_cap_noi_bo_voi_luat(monkeypatch, hai_phia):
    """Cặp luật↔luật bị loại — đúng ưu tiên mà đầu module tuyên bố từ đầu.

    Đo 10/08 (7 ca có mâu thuẫn + 20 ca không): recall giữ nguyên **7/7** ở mọi chính sách lọc,
    còn số ca âm bị báo rơi từ **8/20 xuống 4/20** — đúng bằng con số `gemini-2.5-pro` đạt
    được, nhưng trên `flash-lite`, tức rẻ hơn 21,7 lần.
    """
    chunks = hai_phia + [
        _chunk("TT30-2016::Điều 1 Khoản 6-7", "external", "Thời hạn tra soát 45 ngày."),
    ]
    _gia_lap(monkeypatch, [
        {"id_a": "TT18-2024::Điều 13", "id_b": "TT30-2016::Điều 1 Khoản 6-7",
         "explanation": "Hai thông tư lệch thời hạn.", "severity": "critical"},
        {"id_a": "SHB-QD-THE-2023::Mục 6.1", "id_b": "TT18-2024::Điều 13",
         "explanation": "Nội bộ 20 triệu, luật trần 5 triệu.", "severity": "critical"},
    ])

    ra = conflict.detect_conflicts(chunks)
    assert len(ra) == 1
    assert {ra[0].article_a, ra[0].article_b} == {"Mục 6.1", "Điều 13"}

    # Tắt cờ thì lấy lại cả cặp luật↔luật — dùng cho rà soát văn bản pháp quy.
    assert len(conflict.detect_conflicts(chunks, chi_noi_bo_voi_luat=False)) == 2


def test_duoi_hai_van_ban_thi_khong_goi_llm(monkeypatch):
    """Giữ nguyên: một văn bản thì không thể tự mâu thuẫn với chính nó ở tầng này."""
    def _no(*_a, **_k):
        raise AssertionError("không được gọi LLM khi chỉ có một văn bản")

    monkeypatch.setattr(conflict, "chat_json", _no)
    assert conflict.detect_conflicts([_chunk("A::Điều 1", "external", "x")]) == []
