"""Kiểm phần thuần của scripts/gop_corpus_tu_staging.py: chuyển đổi + guard trùng."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.gop_corpus_tu_staging import chuyen_article, chuyen_doc, gop


def test_chuyen_article_bo_char_giu_chapter():
    a = {
        "article": "Điều 1", "text": "nội dung", "chapter": "Chương I", "section": "Mục 1",
        "superseded": True, "char_start": 10, "char_end": 99,
    }
    r = chuyen_article(a)
    assert r == {
        "article": "Điều 1", "text": "nội dung",
        "valid_from": None, "valid_to": None, "superseded": True,
        "chapter": "Chương I", "section": "Mục 1",
    }
    assert "char_start" not in r and "char_end" not in r  # bỏ offset thô


def test_chuyen_article_khong_chapter():
    r = chuyen_article({"article": "Điều 2", "text": "x"})
    assert r == {"article": "Điều 2", "text": "x", "valid_from": None, "valid_to": None, "superseded": False}


def test_chuyen_doc_core_field_va_valid_to():
    # còn hiệu lực: valid_to rỗng -> None
    s = {
        "doc_id": "TT64-2024", "title": "T", "doc_type": "Thông tư", "source": "external",
        "valid_from": "2024-01-01", "valid_to": "", "so_hieu": "64/2024/TT-NHNN",
        "articles": [{"article": "Điều 1", "text": "a", "char_start": 0}],
    }
    d = chuyen_doc(s)
    assert list(d.keys()) == [
        "doc_id", "title", "doc_type", "source", "valid_from", "valid_to", "so_hieu", "articles",
    ]
    assert d["valid_to"] is None
    assert "char_start" not in d["articles"][0]


def test_chuyen_doc_giu_valid_to_van_ban_chet():
    s = {
        "doc_id": "TT32-2024", "title": "T", "doc_type": "Thông tư",
        "valid_from": "2024-07-01", "valid_to": "2026-02-15", "so_hieu": "32/2024/TT-NHNN",
        "articles": [],
    }
    assert chuyen_doc(s)["valid_to"] == "2026-02-15"  # văn bản hết hiệu lực toàn bộ: giữ ngày chết


def test_gop_them_moi_va_guard_trung():
    corpus = {"documents": [{"doc_id": "TT40-2024"}]}
    staging = {
        "64/2024/TT-NHNN": {"doc_id": "TT64-2024", "title": "T", "doc_type": "Thông tư",
                            "valid_from": "2024-01-01", "valid_to": "", "so_hieu": "64/2024/TT-NHNN",
                            "articles": []},
        "40/2024/TT-NHNN": {"doc_id": "TT40-2024", "title": "T", "doc_type": "Thông tư",
                            "valid_from": "2024-01-01", "valid_to": "", "so_hieu": "40/2024/TT-NHNN",
                            "articles": []},
    }
    them, bo_qua, khong_thay = gop(corpus, staging, ["64/2024/TT-NHNN", "40/2024/TT-NHNN", "99/2099/TT-NHNN"])
    assert them == ["TT64-2024"]
    assert bo_qua == ["TT40-2024"]          # đã có -> guard
    assert khong_thay == ["99/2099/TT-NHNN"]  # không có staging
    assert len(corpus["documents"]) == 2

    # idempotent: chạy lại không thêm nữa
    them2, bo_qua2, _ = gop(corpus, staging, ["64/2024/TT-NHNN"])
    assert them2 == [] and bo_qua2 == ["TT64-2024"]
    assert len(corpus["documents"]) == 2
