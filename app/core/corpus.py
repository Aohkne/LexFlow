"""Corpus canonical dùng chung cho luồng duyệt và API đọc văn bản.

Nguồn sự thật: `legal-docs/corpus.json` trên Supabase Storage; fallback về
`data/corpus.real.json` đóng gói trong image (fail-open khi Storage lỗi/RLS chặn).
Cache TTL ngắn để mỗi lượt xem trang không tốn một round-trip Storage.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from app.core import appdb

CANONICAL = "corpus.json"
LOCAL_FALLBACK = Path("data/corpus.real.json")

_CACHE_TTL = 60.0  # giây
_cache: tuple[float, dict] | None = None  # (loaded_at, corpus)


def load_canonical(token: str, strict: bool = False) -> dict:
    """Đọc corpus canonical (không cache): Storage → fallback file local → rỗng.

    `strict=True` dành cho đường ĐỌC-SỬA-GHI (`approve_document`). Ở đó fail-open không phải
    là chịu đựng lỗi mà là **mất dữ liệu**: một lỗi Storage thoáng qua khiến hàm này trả về
    bản 26 văn bản đóng gói trong image, rồi lượt ghi ngay sau đó đè nó lên `corpus.json`
    thật — xoá sạch mọi văn bản đã duyệt trước đó, không một dòng lỗi. Câu "bấm lại vô hại"
    chỉ đúng khi lượt đọc này trả về canonical thật.

    Đường ĐỌC thì ngược lại và giữ nguyên: thà hiện bản đóng gói còn hơn trắng trang.

    Object CHƯA tồn tại (Storage trả 404, hoặc 400 kèm `NoSuchKey`) vẫn rơi về file đóng gói
    kể cả khi `strict` — đó là ca duyệt LẦN ĐẦU, lúc bucket còn rỗng, và là cách corpus khởi
    điểm. Ca này không âm thầm mất dữ liệu được: nếu là quyền hỏng chứ không phải object
    thiếu thì lượt `upload_storage` ngay sau đó cũng hỏng theo, bằng đúng bộ credentials ấy.
    """
    raw = None
    if appdb.enabled():
        try:
            raw = appdb.download_storage(token, CANONICAL)
        except Exception:  # noqa: BLE001 — Storage lỗi mạng/RLS: fail-open về file local
            if strict:
                raise
            raw = None
    if raw is not None:
        return json.loads(raw.decode("utf-8"))
    if LOCAL_FALLBACK.exists():
        return json.loads(LOCAL_FALLBACK.read_text(encoding="utf-8"))
    return {"documents": [], "relationships": []}


def get_corpus_cached(token: str) -> dict:
    """Bản cache của corpus (nội dung không phụ thuộc user — 1 entry toàn cục)."""
    global _cache
    now = time.monotonic()
    if _cache is not None and now - _cache[0] < _CACHE_TTL:
        return _cache[1]
    corpus = load_canonical(token)
    _cache = (now, corpus)
    return corpus


def invalidate_cache() -> None:
    """Gọi sau khi approve ghi corpus mới lên Storage."""
    global _cache
    _cache = None
