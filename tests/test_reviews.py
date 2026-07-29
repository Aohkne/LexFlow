"""Test POST /reviews (mock retrieval + LLM — offline, dev mode không Supabase)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.reasoning import review as review_mod

_LEGAL_CHUNK = {
    "id": "TT40-2024#dieu-26",
    "doc_id": "TT40-2024",
    "doc_title": "Thông tư 40/2024",
    "doc_type": "Thông tư",
    "article": "Điều 26",
    "text": "Tổng hạn mức giao dịch qua Ví điện tử tối đa là 100 triệu đồng/tháng.",
    "valid_from": "2024-07-01",
    "valid_to": "",
}


@pytest.fixture
def client(monkeypatch):
    # Dev mode: không Supabase → auth no-op, corpus đọc từ file đóng gói
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_jwt_secret", "")
    return TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_corpus_cache():
    from app.core import corpus as corpus_store

    corpus_store.invalidate_cache()
    yield
    corpus_store.invalidate_cache()


@pytest.fixture
def mock_llm(monkeypatch):
    calls = {"search": [], "judge": []}

    def fake_search(query, doc_ids, **kw):
        calls["search"].append((query[:40], tuple(doc_ids)))
        return [_LEGAL_CHUNK]

    def fake_judge(prompt, system=None, **kw):
        calls["judge"].append(prompt[:40])
        return {
            "verdict": "violation",
            "title": "Hạn mức vượt trần",
            "summary": "Nội bộ 150tr > trần 100tr.",
            "internal_quote": "hạn mức 150 triệu",
            "legal_chunk_id": "TT40-2024#dieu-26",
            "legal_quote": "tối đa là 100 triệu đồng/tháng",
            "suggestion": "Hạ hạn mức về 100 triệu.",
        }

    monkeypatch.setattr(review_mod, "search_in_docs", fake_search)
    monkeypatch.setattr(review_mod, "chat_json", fake_judge)
    return calls


def test_review_tra_findings_va_diem(client, mock_llm):
    resp = client.post(
        "/reviews",
        json={"internal_doc_id": "SHB-QD-VI-2023", "against_doc_ids": ["TT40-2024"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["internal_doc_id"] == "SHB-QD-VI-2023"
    # SHB-QD-VI-2023 có 3 điều → 3 findings, mỗi điều 1 lần retrieval + 1 lần LLM
    assert len(body["findings"]) == 3
    assert len(mock_llm["search"]) == 3
    # Self-consistency: mỗi điều phán định 2 lần (verdict trùng → không cần lần 3)
    assert len(mock_llm["judge"]) == 6
    assert all(f["verdict"] == "violation" for f in body["findings"])
    assert body["counts"] == {"violation": 3, "warning": 0, "pass": 0, "not_assessed": 0}
    assert body["score"] == 0  # toàn violation
    f = body["findings"][0]
    assert f["legal_ref"] == "Thông tư 40/2024 — Điều 26"
    assert f["legal_live"] is True
    # Phạm vi đối chiếu được truyền xuống retrieval
    assert mock_llm["search"][0][1] == ("TT40-2024",)


def test_review_khong_chon_pham_vi_mac_dinh_external(client, mock_llm):
    resp = client.post("/reviews", json={"internal_doc_id": "SHB-QD-VI-2023"})
    assert resp.status_code == 200
    against = resp.json()["against_doc_ids"]
    assert "TT40-2024" in against
    assert all(not d.startswith("SHB-") for d in against)  # không đối chiếu với nội bộ


def test_review_khong_tim_thay_can_cu_thi_not_assessed(client, monkeypatch):
    """Không có căn cứ → not_assessed, KHÔNG phải pass — tài liệu lạc đề không được 100 điểm."""
    monkeypatch.setattr(review_mod, "search_in_docs", lambda *a, **kw: [])
    monkeypatch.setattr(
        review_mod, "chat_json",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("không được gọi LLM")),
    )
    resp = client.post(
        "/reviews",
        json={"internal_doc_id": "SHB-CS-PHI-2024", "against_doc_ids": ["TT40-2024"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert all(f["verdict"] == "not_assessed" for f in body["findings"])
    assert body["score"] == 0  # không điều nào được đối chiếu → không có điểm
    assert body["counts"]["not_assessed"] == len(body["findings"])


def test_score_loai_not_assessed_khoi_mau_so():
    from app.core.schemas import ReviewFinding

    findings = [
        ReviewFinding(verdict="pass", article="Điều 1", title="t"),
        ReviewFinding(verdict="not_assessed", article="Điều 2", title="t"),
        ReviewFinding(verdict="not_assessed", article="Điều 3", title="t"),
    ]
    # 1 điều đối chiếu được và pass → 100, hai điều not_assessed không kéo tụt
    assert review_mod._score(findings) == 100


def test_judge_bat_dong_thi_lay_da_so(monkeypatch):
    """2 lần đầu khác verdict → gọi lần 3, lấy đa số."""
    answers = iter(
        [{"verdict": "violation"}, {"verdict": "pass"}, {"verdict": "violation"}]
    )
    calls = []
    monkeypatch.setattr(
        review_mod, "chat_json", lambda *a, **kw: calls.append(1) or next(answers)
    )
    assert review_mod._judge("prompt")["verdict"] == "violation"
    assert len(calls) == 3


def test_review_verdict_la_bay_ve_warning(client, monkeypatch):
    monkeypatch.setattr(review_mod, "search_in_docs", lambda *a, **kw: [_LEGAL_CHUNK])
    monkeypatch.setattr(review_mod, "chat_json", lambda *a, **kw: {"verdict": "unknown-xyz"})
    resp = client.post(
        "/reviews",
        json={"internal_doc_id": "SHB-CS-PHI-2024", "against_doc_ids": ["TT40-2024"]},
    )
    assert resp.status_code == 200
    assert all(f["verdict"] == "warning" for f in resp.json()["findings"])


def test_review_404_doc_la(client):
    resp = client.post("/reviews", json={"internal_doc_id": "KHONG-TON-TAI"})
    assert resp.status_code == 404


def test_review_400_khi_khong_phai_noi_bo(client):
    resp = client.post("/reviews", json={"internal_doc_id": "TT40-2024"})
    assert resp.status_code == 400


def test_review_404_pham_vi_chua_doc_la(client):
    resp = client.post(
        "/reviews",
        json={"internal_doc_id": "SHB-QD-VI-2023", "against_doc_ids": ["MA-KHONG-CO"]},
    )
    assert resp.status_code == 404
