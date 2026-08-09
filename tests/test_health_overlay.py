"""`/health` phải nói được lớp phủ có nạp hay không.

Lớp phủ fail-open có chủ đích — artefact hỏng thì `tai_lop_phu` trả `None` và chat vẫn chạy,
vì lớp phủ làm câu trả lời ĐÚNG HƠN chứ không phải điều kiện để có câu trả lời. Cái giá của
lựa chọn đó là nó **hỏng lặng lẽ**: thiếu `data/overlay/lop_phu.json` trong image thì badge
hiệu lực biến mất khỏi toàn sản phẩm mà `/health` vẫn `"status": "ok"`, và cách duy nhất để
biết là tự đi hỏi một câu rồi đoán qua kết quả.

Ba ca dưới ghim đúng hợp đồng đó. Lưu ý HTTP **luôn 200**: `/health` là tín hiệu cho người
đọc sau mỗi deploy (`docs/ROADMAP-SPRINT.md`), không phải probe của Cloud Run — đổi nó thành
mã lỗi là biến một cảnh báo thành một sự cố triển khai.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.knowledge import lop_phu
from app.main import app


@pytest.fixture
def client():
    lop_phu.tai_lop_phu.cache_clear()
    yield TestClient(app)
    lop_phu.tai_lop_phu.cache_clear()


def test_artefact_that_thi_bao_so_canh(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["overlay"]["bat"] is True
    assert body["overlay"]["nap"] is True
    assert body["overlay"]["so_canh"] == 178
    assert body["overlay"]["sinh_luc"] == "2026-08-06"


def test_thieu_artefact_thi_degraded_nhung_van_200(client, monkeypatch, tmp_path):
    """Đây là ca cả tính năng sinh ra để bắt."""
    monkeypatch.setattr(lop_phu, "DUONG_DAN_MAC_DINH", str(tmp_path / "khong-co.json"))
    lop_phu.tai_lop_phu.cache_clear()

    r = client.get("/health")
    assert r.status_code == 200, "degraded là cảnh báo, không phải sự cố triển khai"
    body = r.json()
    assert body["status"] == "degraded"
    assert body["overlay"]["nap"] is False
    assert body["overlay"].get("so_canh") in (0, None)


def test_tat_bang_co_thi_khong_phai_degraded(client, monkeypatch):
    """Tắt chủ động khác với hỏng — không được báo động vì một lựa chọn cấu hình."""
    monkeypatch.setattr(settings, "overlay_router", False)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["overlay"] == {"bat": False}


def test_log_khoi_dong_noi_so_canh(caplog):
    """Dòng log lúc boot là thứ đọc được trong Cloud Run logs mà không phải gọi `/health`."""
    from app import main

    # Mức INFO phải THỰC SỰ đi ra được. Chỉ kiểm caplog là chưa đủ: caplog tự gắn handler
    # riêng nên vẫn xanh kể cả khi ngoài đời dòng log rơi vào hư không (đúng ca gặp 09/08 —
    # uvicorn chỉ cấu hình `uvicorn.*`, `app.*` không có handler nào).
    assert main.logger.isEnabledFor(20), "logger app.* không bật INFO ⇒ log boot mất hút"

    lop_phu.tai_lop_phu.cache_clear()
    with caplog.at_level("INFO", logger="app.main"):
        main._bao_lop_phu()
    assert "178 cạnh" in caplog.text
    assert "2026-08-06" in caplog.text


def test_log_khoi_dong_canh_bao_khi_thieu_artefact(caplog, monkeypatch, tmp_path):
    from app import main

    monkeypatch.setattr(lop_phu, "DUONG_DAN_MAC_DINH", str(tmp_path / "khong-co.json"))
    lop_phu.tai_lop_phu.cache_clear()
    with caplog.at_level("WARNING", logger="app.main"):
        main._bao_lop_phu()
    assert "KHÔNG nạp được" in caplog.text
    lop_phu.tai_lop_phu.cache_clear()


def test_tinh_trang_khong_ton_them_luot_doc_dia(monkeypatch, tmp_path):
    """`tinh_trang` phải dùng lại cache của `tai_lop_phu`, không tự mở file lần nữa."""
    lop_phu.tai_lop_phu.cache_clear()
    lop_phu.tinh_trang()

    def _cam(*_a, **_k):
        raise AssertionError("đọc lại đĩa — cache của tai_lop_phu không được dùng")

    monkeypatch.setattr("pathlib.Path.read_text", _cam)
    assert lop_phu.tinh_trang()["nap"] is True
    lop_phu.tai_lop_phu.cache_clear()
