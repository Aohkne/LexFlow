"""Xác thực Supabase JWT + phân quyền role (admin / staff).

Supabase GoTrue phát JWT cho frontend; backend chỉ verify:
- Project cũ (legacy): HS256 với SUPABASE_JWT_SECRET.
- Project mới: JWT signing keys → verify qua JWKS endpoint của SUPABASE_URL.

Chưa cấu hình Supabase → dev mode: trả user giả role admin để dev/test offline.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

_bearer = HTTPBearer(auto_error=False)

_JWKS_PATH = "/auth/v1/.well-known/jwks.json"


@dataclass(frozen=True)
class AuthUser:
    id: str
    email: str
    role: str  # "admin" | "staff"
    token: str = ""  # JWT gốc — dùng gọi PostgREST với RLS của chính user


_DEV_USER = AuthUser(id="dev", email="dev@local", role="admin")


@lru_cache
def _jwks_client() -> jwt.PyJWKClient:
    return jwt.PyJWKClient(settings.supabase_url.rstrip("/") + _JWKS_PATH)


def _decode(token: str) -> dict[str, Any]:
    # Token của Supabase có aud="authenticated" — không dùng aud để phân quyền nên bỏ verify
    options = {"verify_aud": False}
    if settings.supabase_jwt_secret:
        return jwt.decode(
            token, settings.supabase_jwt_secret, algorithms=["HS256"], options=options
        )
    key = _jwks_client().get_signing_key_from_jwt(token).key
    return jwt.decode(token, key, algorithms=["ES256", "RS256"], options=options)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> AuthUser:
    if not settings.supabase_auth_enabled:
        return _DEV_USER
    if credentials is None:
        raise HTTPException(status_code=401, detail="Thiếu Bearer token")
    try:
        claims = _decode(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Token không hợp lệ: {exc}") from exc
    app_meta = claims.get("app_metadata") or {}
    return AuthUser(
        id=claims.get("sub", ""),
        email=claims.get("email", ""),
        role=app_meta.get("role", "staff"),
        token=credentials.credentials,
    )


def require_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Yêu cầu quyền admin")
    return user
