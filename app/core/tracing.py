"""Langfuse tracing (tuỳ chọn) — quan sát query → chunks → prompt → citation.

Không cấu hình LANGFUSE_PUBLIC_KEY/SECRET_KEY → mọi decorator thành no-op,
dev/test chạy offline không cần mạng. Bật lên là thấy trace lồng nhau:
answer.build → retrieval.hybrid → gemini.chat → conflict.detect.
"""
from __future__ import annotations

from app.core.config import settings

if settings.langfuse_enabled:
    from langfuse import Langfuse, get_client, observe

    # Đăng ký singleton cho get_client() (SDK đọc host/keys từ constructor)
    Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )

    def update_generation(**kwargs) -> None:
        """Gắn metadata (model, usage...) vào generation đang mở."""
        get_client().update_current_generation(**kwargs)

    def shutdown() -> None:
        """Flush hết trace còn trong buffer — gọi khi app tắt (Cloud Run scale-to-zero)."""
        get_client().shutdown()

else:

    def observe(func=None, **_kwargs):  # type: ignore[misc]
        """No-op thay cho langfuse.observe khi chưa cấu hình."""

        def deco(f):
            return f

        return deco(func) if func is not None else deco

    def update_generation(**kwargs) -> None:
        pass

    def shutdown() -> None:
        pass
