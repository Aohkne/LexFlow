"""Test xác thực Supabase JWT (không gọi mạng)."""
from __future__ import annotations

import time

import jwt as pyjwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core import auth
from app.core.config import settings

SECRET = "test-secret-0123456789-0123456789-xx"


def _token(secret: str = SECRET, role: str | None = "admin", exp_offset: int = 3600) -> str:
    claims = {
        "sub": "user-1",
        "email": "a@b.c",
        "aud": "authenticated",
        "exp": int(time.time()) + exp_offset,
        "app_metadata": {"role": role} if role else {},
    }
    return pyjwt.encode(claims, secret, algorithm="HS256")


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_dev_mode_khong_cau_hinh_supabase(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", "")
    user = auth.get_current_user(credentials=None)
    assert user.role == "admin"  # dev fallback


def test_thieu_token_bi_401(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", SECRET)
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user(credentials=None)
    assert exc.value.status_code == 401


def test_token_hop_le_doc_duoc_role(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", SECRET)
    user = auth.get_current_user(credentials=_creds(_token(role="admin")))
    assert user.id == "user-1"
    assert user.role == "admin"


def test_token_khong_co_role_mac_dinh_staff(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", SECRET)
    user = auth.get_current_user(credentials=_creds(_token(role=None)))
    assert user.role == "staff"


def test_token_sai_secret_bi_401(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", SECRET)
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user(credentials=_creds(_token(secret="sai-secret-0123456789-0123456789")))
    assert exc.value.status_code == 401


def test_token_het_han_bi_401(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", SECRET)
    with pytest.raises(HTTPException) as exc:
        auth.get_current_user(credentials=_creds(_token(exp_offset=-60)))
    assert exc.value.status_code == 401


def test_require_admin_chan_staff():
    with pytest.raises(HTTPException) as exc:
        auth.require_admin(auth.AuthUser(id="u", email="e", role="staff"))
    assert exc.value.status_code == 403
