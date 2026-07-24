"""Test luồng duyệt văn bản (mock appdb + pipeline — offline)."""
from __future__ import annotations

import time

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from app.core import appdb
from app.core.config import settings
from app.main import app

SECRET = "test-secret-0123456789-0123456789-xx"


def _token(role: str) -> str:
    claims = {
        "sub": "u-admin", "email": "a@b.c", "aud": "authenticated",
        "exp": int(time.time()) + 3600, "app_metadata": {"role": role},
    }
    return pyjwt.encode(claims, SECRET, algorithm="HS256")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", SECRET)
    monkeypatch.setattr(settings, "supabase_url", "https://x.supabase.co")
    monkeypatch.setattr(settings, "supabase_anon_key", "sb_publishable_x")
    return TestClient(app)


@pytest.fixture
def fake_store(monkeypatch):
    """Giả lập Storage + legal_documents + audit trong bộ nhớ."""
    store: dict = {"storage": {}, "rows": {}, "audit": [], "events": 0, "ingested": 0}

    monkeypatch.setattr(appdb, "upload_storage", lambda tok, path, content, ct: store["storage"].__setitem__(path, content))
    monkeypatch.setattr(appdb, "download_storage", lambda tok, path: store["storage"].get(path))
    monkeypatch.setattr(appdb, "insert_document", lambda tok, row: store["rows"].__setitem__(row["doc_id"], row))
    monkeypatch.setattr(appdb, "update_document", lambda tok, doc_id, patch: store["rows"][doc_id].update(patch))
    monkeypatch.setattr(appdb, "get_document", lambda tok, doc_id: store["rows"].get(doc_id))
    monkeypatch.setattr(appdb, "log_audit", lambda tok, uid, action, detail: store["audit"].append(action))
    monkeypatch.setattr(appdb, "record_change_events", lambda tok, events: store.update(events=len(events)) or len(events))

    import app.ingestion.pipeline as pipeline

    def fake_ingest(docs, rels):
        store["ingested"] = sum(len(d.articles) for d in docs)
        return store["ingested"]

    monkeypatch.setattr(pipeline, "ingest_docs", fake_ingest)
    return store


_DOC = {
    "doc_id": "TT99-2026", "title": "Thông tư 99/2026/TT-NHNN thử nghiệm",
    "doc_type": "Thông tư", "source": "external", "valid_from": "2026-01-01",
    "valid_to": None,
    "articles": [{"article": "Điều 1", "text": "Nội dung.", "valid_from": None, "valid_to": None, "superseded": False}],
}


def test_staff_khong_duoc_upload(client):
    r = client.post("/documents/upload", files={"file": ("x.txt", b"abc")},
                    headers={"Authorization": f"Bearer {_token('staff')}"})
    assert r.status_code == 403


def test_approve_merge_vao_canonical(client, fake_store, monkeypatch):
    # canonical hiện có 1 văn bản khác
    import json
    fake_store["storage"]["corpus.json"] = json.dumps(
        {"documents": [{**_DOC, "doc_id": "ND00-2020", "title": "Cũ"}], "relationships": []},
        ensure_ascii=False,
    ).encode("utf-8")
    fake_store["rows"]["TT99-2026"] = {"doc_id": "TT99-2026", "extracted": _DOC, "status": "pending"}

    r = client.post(
        "/documents/TT99-2026/approve",
        json={"relationships": [{"source_doc": "TT99-2026", "target_doc": "ND00-2020", "rel_type": "HUONG_DAN"}]},
        headers={"Authorization": f"Bearer {_token('admin')}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "approved"
    # canonical mới có cả 2 văn bản + quan hệ mới
    import json as _json
    corpus = _json.loads(fake_store["storage"]["corpus.json"])
    assert {d["doc_id"] for d in corpus["documents"]} == {"ND00-2020", "TT99-2026"}
    assert corpus["relationships"][0]["rel_type"] == "HUONG_DAN"
    assert fake_store["rows"]["TT99-2026"]["status"] == "approved"
    assert "doc_approve" in fake_store["audit"]
    assert fake_store["ingested"] == 2  # re-ingest full: 2 văn bản × 1 điều


def test_approve_khong_co_extracted_bi_400(client, fake_store):
    fake_store["rows"]["X"] = {"doc_id": "X", "extracted": None}
    r = client.post("/documents/X/approve", headers={"Authorization": f"Bearer {_token('admin')}"})
    assert r.status_code == 400


def test_reject(client, fake_store):
    fake_store["rows"]["TT99-2026"] = {"doc_id": "TT99-2026", "status": "pending"}
    r = client.post("/documents/TT99-2026/reject", headers={"Authorization": f"Bearer {_token('admin')}"})
    assert r.status_code == 200
    assert fake_store["rows"]["TT99-2026"]["status"] == "rejected"
