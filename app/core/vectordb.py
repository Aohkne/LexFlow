"""Kết nối LanceDB — một chỗ duy nhất quyết định cloud hay local.

Có LANCEDB_URI (db://...) + LANCEDB_API_KEY → LanceDB Cloud (máy local/Railway
không giữ dữ liệu). Ngược lại → LanceDB nhúng tại LANCEDB_PATH.
"""
from __future__ import annotations

import lancedb

from app.core.config import settings


def connect():
    if settings.lancedb_cloud_enabled:
        # Cloud thi thoảng trả lỗi transient (reset/5xx) — mặc định 3 lần retry là
        # không đủ cho batch dài; truyền tường minh vì env LANCE_CLIENT_* không
        # chắc tới được process con.
        return lancedb.connect(
            uri=settings.lancedb_uri,
            api_key=settings.lancedb_api_key,
            region=settings.lancedb_region,
            client_config={
                "retry_config": {
                    "retries": 8,
                    "connect_retries": 8,
                    "read_retries": 8,
                    "backoff_factor": 1.0,
                }
            },
        )
    return lancedb.connect(settings.lancedb_path)
