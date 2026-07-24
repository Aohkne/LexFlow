"""Tracing phải là no-op hoàn toàn khi chưa cấu hình Langfuse (mặc định CI/dev)."""
from __future__ import annotations

from app.core import tracing
from app.core.config import settings


def test_mac_dinh_tat_tracing():
    assert not settings.langfuse_enabled


def test_observe_noop_giu_nguyen_ham():
    @tracing.observe(name="x", as_type="generation")
    def f(a, b=1):
        return a + b

    assert f(2, b=3) == 5
    assert f.__name__ == "f"  # không bị wrap


def test_observe_noop_voi_generator():
    @tracing.observe(name="g", transform_to_string="".join)
    def gen():
        yield "a"
        yield "b"

    assert list(gen()) == ["a", "b"]


def test_update_va_shutdown_noop():
    tracing.update_generation(model="gemini-2.5-flash")  # không raise
    tracing.shutdown()  # không raise
