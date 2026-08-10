"""Lưới an toàn cho MỌI ca test: chặn hạ tầng thật (LanceDB Cloud + Neo4j Aura).

Vì sao có file này (fix round 1, Task 4, 10/08): lượt RED của TDD trong `test_documents.py`
vá `pipeline.ingest_one_doc` bằng tên hàm — đúng nếp TDD. Nhưng khi tên vá và tên mã sản
xuất thực sự gọi bị LỆCH NHAU (đúng cái RED cố ý tạo ra), lời gọi rơi thẳng xuống
`vectordb.connect()` / `graph.session()` thật, và request đó đã ghi một thông tư bịa
(`TT99-2026`) thẳng vào LanceDB Cloud + Neo4j Aura đang phục vụ. Không phép kiểm nào bắt
được vì cả hai chỉ vá đúng cái tên chúng nghĩ sẽ được gọi.

Fixture `autouse=True` dưới đây chặn NGAY tầng thấp nhất — hai cửa duy nhất mọi đường ingest/
retrieval/graph đi qua để chạm hạ tầng thật — thay vì tin ca test nào cũng nhớ vá đúng chỗ.
Ca test nào cần bảng/driver giả vẫn tự `monkeypatch.setattr(...)` hoặc `unittest.mock.patch`
đè lên như nếp sẵn có trong repo (`tests/test_ingest_mot_van_ban.py`, `tests/test_push_overlay.py`)
— vì các lệnh đó chạy SAU fixture này trong cùng một `monkeypatch`, nên đè lên vẫn có tác dụng.
"""
from __future__ import annotations

import pytest


def _cham_lancedb_that(*_a, **_k):
    raise RuntimeError(
        "test chạm LanceDB Cloud thật — hãy vá app.core.vectordb.connect trong ca test này"
    )


def _cham_neo4j_that(*_a, **_k):
    raise RuntimeError(
        "test chạm Neo4j Aura thật — hãy vá app.knowledge.graph.session trong ca test này"
    )


@pytest.fixture(autouse=True)
def _chan_ha_tang_that(monkeypatch):
    monkeypatch.setattr("app.core.vectordb.connect", _cham_lancedb_that)
    monkeypatch.setattr("app.knowledge.graph.session", _cham_neo4j_that)
    # Supabase là hạ tầng thứ ba, và là nơi chứa đúng dữ liệu luồng duyệt ghi vào (bảng
    # `legal_documents`, bucket `legal-docs`). Không chặn được bằng hàm-ném-lỗi như hai cái
    # trên vì nó là chuỗi cấu hình, nhưng URL rỗng làm `appdb.enabled()` trả False và mọi
    # đường Supabase tự dừng — ca test nào cần thì tự đặt lại URL rồi vá `appdb` như
    # `tests/test_documents.py` đang làm. Không đặt dòng này thì `.env` của máy phát triển
    # trỏ thẳng vào project thật.
    monkeypatch.setattr("app.core.config.settings.supabase_url", "")
    yield
