"""Kết nối LanceDB — một chỗ duy nhất quyết định cloud hay local.

Có LANCEDB_URI (db://...) + LANCEDB_API_KEY → LanceDB Cloud (máy local/Railway
không giữ dữ liệu). Ngược lại → LanceDB nhúng tại LANCEDB_PATH.
"""
from __future__ import annotations

import lancedb

from app.core.config import settings


def connect():
    if settings.lancedb_cloud_enabled:
        return lancedb.connect(
            uri=settings.lancedb_uri,
            api_key=settings.lancedb_api_key,
            region=settings.lancedb_region,
        )
    return lancedb.connect(settings.lancedb_path)
