"""Tracing phải là no-op hoàn toàn khi không có key Langfuse.

Máy dev có thể có key thật trong .env → test tự reload module với settings rỗng
thay vì giả định môi trường.
"""
from __future__ import annotations

import importlib

import pytest

from app.core.config import settings


@pytest.fixture
def noop_tracing(monkeypatch):
    monkeypatch.setattr(settings, "langfuse_public_key", "")
    monkeypatch.setattr(settings, "langfuse_secret_key", "")
    import app.core.tracing as tracing

    importlib.reload(tracing)
    yield tracing
    monkeypatch.undo()
    importlib.reload(tracing)  # khôi phục theo .env thật của máy


def test_khong_co_key_thi_tat(noop_tracing):
    assert not settings.langfuse_enabled


def test_observe_noop_giu_nguyen_ham(noop_tracing):
    @noop_tracing.observe(name="x", as_type="generation")
    def f(a, b=1):
        return a + b

    assert f(2, b=3) == 5
    assert f.__name__ == "f"  # không bị wrap


def test_observe_noop_voi_generator(noop_tracing):
    @noop_tracing.observe(name="g", transform_to_string="".join)
    def gen():
        yield "a"
        yield "b"

    assert list(gen()) == ["a", "b"]


def test_update_va_shutdown_noop(noop_tracing):
    noop_tracing.update_generation(model="gemini-2.5-flash")  # không raise
    noop_tracing.shutdown()  # không raise
