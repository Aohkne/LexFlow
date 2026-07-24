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

    # Supabase (Postgres + Auth + Storage)
    supabase_url: str = ""
    supabase_jwt_secret: str = ""  # legacy HS256 — để trống nếu project dùng JWT signing keys (JWKS)
    supabase_anon_key: str = ""

    # Redis / hàng đợi tác vụ nền (ARQ) — để trống ở local dev
    redis_url: str = ""

    # LanceDB — local path (mặc định) hoặc Cloud khi có URI db:// + API key
    lancedb_path: str = "data/lancedb"
    lancedb_uri: str = ""
    lancedb_api_key: str = ""
    lancedb_region: str = "us-east-1"

    # Langfuse (LLM tracing) — để trống = tắt tracing
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # Paths
    data_raw_path: str = "data/raw"

    # CORS
    frontend_origin: str = "http://localhost:3000"

    @property
    def neo4j_enabled(self) -> bool:
        return bool(self.neo4j_uri and self.neo4j_password)

    @property
    def lancedb_cloud_enabled(self) -> bool:
        return self.lancedb_uri.startswith("db://") and bool(self.lancedb_api_key)

    @property
    def supabase_auth_enabled(self) -> bool:
        return bool(self.supabase_url or self.supabase_jwt_secret)

    @property
    def queue_enabled(self) -> bool:
        return bool(self.redis_url)

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
