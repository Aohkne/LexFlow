"""Bổ sung anchors + thuộc tính vào canonical trên Storage (thuần offline)."""
from __future__ import annotations

from scripts.sync_corpus_storage import sync_anchors, sync_thuoc_tinh


def _local() -> dict:
    return {
        "documents": [
            {
                "doc_id": "TT40-2024",
                "title": "Thông tư 40/2024/TT-NHNN",
                "articles": [{"article": "Điều 1", "text": "bản curate tay"}],
                "so_hieu": "40/2024/TT-NHNN",
                "co_quan_ban_hanh": "Ngân hàng Nhà nước Việt Nam",
                "nguoi_ky": "Phạm Tiến Dũng",
                "provisions": [{"cap": "dieu", "so": "1", "con": []}],
                "source_files": [{"ten": "TT40.pdf"}],
                "linh_vuc": "",  # rỗng ⇒ không ghi đè
            }
        ],
        "relationships": [
            {
                "source_doc": "TT41-2025",
                "target_doc": "TT40-2024",
                "rel_type": "sua_doi",
                "anchors": ["Điều 1 Khoản 2"],
            }
        ],
    }


def _canonical() -> dict:
    return {
        "documents": [
            {
                "doc_id": "TT40-2024",
                "title": "Thông tư 40/2024/TT-NHNN",
                "articles": [{"article": "Điều 1", "text": "bản đã duyệt trên Storage"}],
                "so_hieu": "40/2024/TT-NHNN",
                "linh_vuc": "Thanh tra",
            },
            {"doc_id": "TT99-2099", "title": "Duyệt qua /admin, chưa vào corpus commit"},
        ],
        "relationships": [
            {"source_doc": "TT41-2025", "target_doc": "TT40-2024", "rel_type": "sua_doi"}
        ],
    }


def test_bo_sung_thuoc_tinh_khong_dung_toan_van() -> None:
    canonical = _canonical()
    changed = sync_thuoc_tinh(canonical, _local())

    doc = canonical["documents"][0]
    assert changed == {
        "TT40-2024": ["co_quan_ban_hanh", "nguoi_ky", "provisions", "source_files"]
    }
    assert doc["co_quan_ban_hanh"] == "Ngân hàng Nhà nước Việt Nam"
    assert doc["source_files"] == [{"ten": "TT40.pdf"}]
    # toàn văn trên canonical là bản đã duyệt — không được thay bằng bản local
    assert doc["articles"][0]["text"] == "bản đã duyệt trên Storage"
    # trường rỗng bên local không xoá giá trị canonical đang có
    assert doc["linh_vuc"] == "Thanh tra"


def test_van_ban_chi_co_tren_canonical_khong_bi_xoa() -> None:
    canonical = _canonical()
    sync_thuoc_tinh(canonical, _local())
    assert [d["doc_id"] for d in canonical["documents"]] == ["TT40-2024", "TT99-2099"]
    assert canonical["documents"][1] == _canonical()["documents"][1]


def test_sync_lai_lan_hai_khong_bao_thay_doi() -> None:
    canonical = _canonical()
    sync_thuoc_tinh(canonical, _local())
    assert sync_thuoc_tinh(canonical, _local()) == {}


def test_anchors_chi_dien_khi_canonical_con_thieu() -> None:
    canonical = _canonical()
    assert sync_anchors(canonical, _local()) == 1
    assert canonical["relationships"][0]["anchors"] == ["Điều 1 Khoản 2"]
    assert sync_anchors(canonical, _local()) == 0


def test_mo_ta_token_doc_duoc_email_va_han() -> None:
    import base64
    import json
    import time

    from scripts.sync_corpus_storage import _mo_ta_token

    payload = {"email": "admin@x.com", "exp": int(time.time()) + 1800}
    than = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    mo_ta = _mo_ta_token(f"eyJhbGciOiJIUzI1NiJ9.{than}.chu-ky-gia")
    assert "admin@x.com" in mo_ta
    assert "còn 29 phút" in mo_ta or "còn 30 phút" in mo_ta

    het = {"email": "admin@x.com", "exp": int(time.time()) - 60}
    than = base64.urlsafe_b64encode(json.dumps(het).encode()).decode().rstrip("=")
    assert "ĐÃ HẾT HẠN" in _mo_ta_token(f"eyJ.{than}.x")
    assert "không đọc được payload" in _mo_ta_token("khong-phai-jwt")


def test_ma_loi_storage_phan_biet_thieu_object_voi_rls_chan() -> None:
    import httpx

    from scripts.sync_corpus_storage import _ma_loi_storage

    thieu = httpx.Response(400, json={"statusCode": "404", "code": "NoSuchKey"})
    chan = httpx.Response(400, json={"statusCode": "404", "code": "NoSuchBucket"})
    assert _ma_loi_storage(thieu) == "NoSuchKey"
    assert _ma_loi_storage(chan) == "NoSuchBucket"
    assert _ma_loi_storage(httpx.Response(400, text="<html>proxy</html>")) is None
