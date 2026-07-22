"""Cấu hình tập trung, đọc từ biến môi trường / file .env."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Tên bảng LanceDB (dùng chung giữa ingestion & knowledge)
LANCEDB_TABLE = "chunks"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Gemini
    gemini_api_key: str = ""
    gemini_chat_model: str = "gemini-2.5-flash"
    gemini_reasoning_model: str = "gemini-2.5-pro"
    gemini_embed_model: str = "gemini-embedding-001"

    # Neo4j Aura
    neo4j_uri: str = ""
    neo4j_username: str = "neo4j"
    neo4j_password: str = ""

    # Paths
    lancedb_path: str = "data/lancedb"
    data_raw_path: str = "data/raw"

    # CORS
    frontend_origin: str = "http://localhost:3000"

    @property
    def neo4j_enabled(self) -> bool:
        return bool(self.neo4j_uri and self.neo4j_password)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
