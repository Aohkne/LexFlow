"""Test luồng duyệt văn bản (mock appdb + pipeline — offline)."""
from __future__ import annotations

import time

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from app.core import appdb
from app.core.config import settings
from app.core.schemas import CorpusDocument
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


@pytest.fixture(autouse=True)
def _fresh_corpus_cache():
    """Cache corpus là module-global — xoá giữa các test để không rò rỉ."""
    from app.core import corpus as corpus_store

    corpus_store.invalidate_cache()
    yield
    corpus_store.invalidate_cache()


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

    def fake_ingest_one(doc, rels, tat_ca_docs):
        store["ingested"] = len(doc.articles)
        store["ingested_doc"] = doc.doc_id
        store["ingested_tat_ca"] = [d.doc_id for d in tat_ca_docs]
        return store["ingested"]

    monkeypatch.setattr(pipeline, "ingest_one_doc", fake_ingest_one)
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
        # `DAN_CHIEU` cố ý chọn trung tính: test này canh việc GỘP quan hệ vào canonical,
        # không canh loại quan hệ. Dùng một mã trong 13 mã v0.5 để khỏi ngụ ý câu trả lời
        # cho chuyện TT → NĐ là `QUY_DINH_CHI_TIET_HUONG_DAN` hay `HUONG_DAN_AP_DUNG`.
        json={"relationships": [{"source_doc": "TT99-2026", "target_doc": "ND00-2020", "rel_type": "DAN_CHIEU"}]},
        headers={"Authorization": f"Bearer {_token('admin')}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "approved"
    # canonical mới có cả 2 văn bản + quan hệ mới
    import json as _json
    corpus = _json.loads(fake_store["storage"]["corpus.json"])
    assert {d["doc_id"] for d in corpus["documents"]} == {"ND00-2020", "TT99-2026"}
    assert corpus["relationships"][0]["rel_type"] == "DAN_CHIEU"
    assert fake_store["rows"]["TT99-2026"]["status"] == "approved"
    assert "doc_approve" in fake_store["audit"]
    # Chỉ nạp lại VĂN BẢN VỪA DUYỆT, không nạp lại cả corpus — đây là điều phân biệt
    # đường tăng dần với đường ghi đè. Văn bản cũ ND00-2020 vẫn nằm trong canonical
    # (nên có mặt ở `ingested_tat_ca`) nhưng không bị embed lại.
    assert fake_store["ingested"] == 1
    assert fake_store["ingested_doc"] == "TT99-2026"
    assert set(fake_store["ingested_tat_ca"]) == {"ND00-2020", "TT99-2026"}


def test_approve_khong_co_extracted_bi_400(client, fake_store):
    fake_store["rows"]["X"] = {"doc_id": "X", "extracted": None}
    r = client.post("/documents/X/approve", headers={"Authorization": f"Bearer {_token('admin')}"})
    assert r.status_code == 400


def test_reject(client, fake_store):
    fake_store["rows"]["TT99-2026"] = {"doc_id": "TT99-2026", "status": "pending"}
    r = client.post("/documents/TT99-2026/reject", headers={"Authorization": f"Bearer {_token('admin')}"})
    assert r.status_code == 200
    assert fake_store["rows"]["TT99-2026"]["status"] == "rejected"


# --- API đọc văn bản (GET /documents, GET /documents/{doc_id}) ---

def _seed_canonical(fake_store) -> None:
    import json

    old = {**_DOC, "doc_id": "TT39-2014", "title": "Thông tư cũ", "valid_to": "2024-06-30"}
    corpus = {
        "documents": [_DOC, old],
        "relationships": [{
            "source_doc": "TT99-2026", "target_doc": "TT39-2014", "rel_type": "SUA_DOI_BO_SUNG",
            "anchors": [{"source_article": "Điều 1", "target_article": "Điều 1", "detail": "Sửa khoản 1"}],
        }],
    }
    fake_store["storage"]["corpus.json"] = json.dumps(corpus, ensure_ascii=False).encode("utf-8")


def test_list_documents_staff_thay_status(client, fake_store):
    _seed_canonical(fake_store)
    r = client.get("/documents", headers={"Authorization": f"Bearer {_token('staff')}"})
    assert r.status_code == 200, r.text
    by_id = {d["doc_id"]: d for d in r.json()}
    assert by_id["TT99-2026"]["status"] == "con_hieu_luc"
    assert by_id["TT39-2014"]["status"] == "het_hieu_luc"  # valid_to quá khứ
    assert by_id["TT99-2026"]["n_articles"] == 1


def test_list_documents_thieu_token_401(client, fake_store):
    assert client.get("/documents").status_code == 401


def test_get_document_detail_hai_chieu_quan_he(client, fake_store):
    _seed_canonical(fake_store)
    r = client.get("/documents/TT39-2014", headers={"Authorization": f"Bearer {_token('staff')}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["doc_id"] == "TT39-2014"
    assert len(body["articles"]) == 1
    assert body["relationships_out"] == []
    assert len(body["relationships_in"]) == 1
    anchor = body["relationships_in"][0]["anchors"][0]
    assert anchor["target_article"] == "Điều 1"
    assert body["doc_titles"]["TT99-2026"] == _DOC["title"]


def test_get_document_khong_ton_tai_404(client, fake_store):
    _seed_canonical(fake_store)
    r = client.get("/documents/KHONG-CO", headers={"Authorization": f"Bearer {_token('staff')}"})
    assert r.status_code == 404


def test_storage_loi_fallback_file_local(client, fake_store, monkeypatch):
    def boom(tok, path):
        raise RuntimeError("Storage sập")

    monkeypatch.setattr(appdb, "download_storage", boom)
    r = client.get("/documents", headers={"Authorization": f"Bearer {_token('staff')}"})
    assert r.status_code == 200
    # fallback về data/corpus.real.json đóng gói trong repo (15 văn bản)
    assert len(r.json()) >= 10


# --- Thuộc tính + tải bản gốc ---

def test_get_document_tra_ve_thuoc_tinh(client, fake_store):
    import json

    doc = {
        **_DOC,
        "so_hieu": "99/2026/TT-NHNN",
        "co_quan_ban_hanh": "Ngân hàng Nhà nước Việt Nam",
        "nguoi_ky": "Phạm Tiến Dũng",
        "chuc_danh": "Phó Thống đốc",
        "nganh": "Ngân hàng",
        "linh_vuc": "Thanh tra",
        "ngay_ban_hanh": "2025-12-20",
        "tinh_trang_hieu_luc": "Còn hiệu lực",
        "source_url": "https://vbpl.vn/van-ban/chi-tiet/tt-99-2026--1",
    }
    fake_store["storage"]["corpus.json"] = json.dumps(
        {"documents": [doc], "relationships": []}, ensure_ascii=False
    ).encode("utf-8")

    r = client.get("/documents/TT99-2026", headers={"Authorization": f"Bearer {_token('staff')}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["so_hieu"] == "99/2026/TT-NHNN"
    assert body["nguoi_ky"] == "Phạm Tiến Dũng"
    assert body["tinh_trang_hieu_luc"] == "Còn hiệu lực"
    assert body["source_url"].startswith("https://vbpl.vn/")


def test_get_document_cu_khong_co_thuoc_tinh_van_doc_duoc(client, fake_store):
    # corpus duyệt trước khi có nhóm trường này -> phải trả None, không được 500
    _seed_canonical(fake_store)
    r = client.get("/documents/TT99-2026", headers={"Authorization": f"Bearer {_token('staff')}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["so_hieu"] is None
    assert body["source_url"] is None
    assert body["source_files"] == []


def test_get_document_kem_file_goc_da_upload(client, fake_store):
    _seed_canonical(fake_store)
    fake_store["rows"]["TT99-2026"] = {
        "doc_id": "TT99-2026", "storage_path": "uploads/Thông tư 99.pdf", "status": "approved",
    }
    r = client.get("/documents/TT99-2026", headers={"Authorization": f"Bearer {_token('staff')}"})
    assert r.status_code == 200, r.text
    files = r.json()["source_files"]
    assert len(files) == 1
    assert files[0]["ten"] == "Thông tư 99.pdf"
    assert files[0]["url"] == "/documents/TT99-2026/download"


def test_get_document_tra_ve_cay_dieu_khoan(client, fake_store):
    import json

    doc = {
        **_DOC,
        "provisions": [{
            "id": "c1", "cap": "chuong", "so": "I", "tieu_de": "QUY ĐỊNH CHUNG",
            "con": [{
                "id": "a1", "cap": "dieu", "so": "1", "tieu_de": "Phạm vi",
                "html": "<strong>Thông tư</strong> này quy định.",
                "bi_tac_dong": ["sua_doi_bo_sung"],
                "con": [],
            }],
        }],
    }
    fake_store["storage"]["corpus.json"] = json.dumps(
        {"documents": [doc], "relationships": []}, ensure_ascii=False
    ).encode("utf-8")

    r = client.get("/documents/TT99-2026", headers={"Authorization": f"Bearer {_token('staff')}"})
    assert r.status_code == 200, r.text
    tree = r.json()["provisions"]
    assert tree[0]["cap"] == "chuong" and tree[0]["so"] == "I"
    dieu = tree[0]["con"][0]
    assert dieu["html"] == "<strong>Thông tư</strong> này quy định."
    assert dieu["bi_tac_dong"] == ["sua_doi_bo_sung"]


def test_get_document_chua_co_cay_thi_provisions_rong(client, fake_store):
    _seed_canonical(fake_store)
    r = client.get("/documents/TT99-2026", headers={"Authorization": f"Bearer {_token('staff')}"})
    assert r.status_code == 200
    assert r.json()["provisions"] == []   # trang xem lùi về danh sách Điều phẳng


def test_download_file_goc(client, fake_store):
    fake_store["rows"]["TT99-2026"] = {
        "doc_id": "TT99-2026", "storage_path": "uploads/Thông tư 99.pdf",
    }
    fake_store["storage"]["uploads/Thông tư 99.pdf"] = b"%PDF-1.7 noi dung gia"
    r = client.get(
        "/documents/TT99-2026/download", headers={"Authorization": f"Bearer {_token('staff')}"}
    )
    assert r.status_code == 200, r.text
    assert r.content == b"%PDF-1.7 noi dung gia"
    assert r.headers["content-type"] == "application/pdf"
    # tên file có dấu -> phải mã hoá theo RFC 5987, không được rơi mất dấu
    assert "filename*=UTF-8''" in r.headers["content-disposition"]
    assert "99.pdf" in r.headers["content-disposition"]


def test_download_khi_chua_co_file_goc_404(client, fake_store):
    fake_store["rows"]["TT99-2026"] = {"doc_id": "TT99-2026", "storage_path": None}
    r = client.get(
        "/documents/TT99-2026/download", headers={"Authorization": f"Bearer {_token('staff')}"}
    )
    assert r.status_code == 404


def test_approve_lam_moi_cache_doc(client, fake_store):
    _seed_canonical(fake_store)
    # đọc trước để cache
    client.get("/documents", headers={"Authorization": f"Bearer {_token('staff')}"})
    fake_store["rows"]["TT99-2026"] = {"doc_id": "TT99-2026", "extracted": _DOC, "status": "pending"}
    r = client.post(
        "/documents/TT99-2026/approve",
        json={"document": {**_DOC, "title": "Đã sửa tên"}},
        headers={"Authorization": f"Bearer {_token('admin')}"},
    )
    assert r.status_code == 200, r.text
    r2 = client.get("/documents", headers={"Authorization": f"Bearer {_token('staff')}"})
    titles = {d["doc_id"]: d["title"] for d in r2.json()}
    assert titles["TT99-2026"] == "Đã sửa tên"  # cache đã invalidate sau approve


def test_approve_doc_id_ban_bi_chan_truoc_khi_ghi_storage(client, fake_store):
    """`doc_id` đi vào chuỗi điều kiện của `delete` — chặn ở cửa, và chặn TRƯỚC khi ghi."""
    xau = {**_DOC, "doc_id": "TT99'; drop --"}
    fake_store["rows"]["TT99-2026"] = {"doc_id": "TT99-2026", "extracted": xau, "status": "pending"}

    r = client.post(
        "/documents/TT99-2026/approve",
        headers={"Authorization": f"Bearer {_token('admin')}"},
    )
    assert r.status_code == 422, r.text
    assert "corpus.json" not in fake_store["storage"], "không được ghi canonical rồi mới từ chối"
    assert fake_store["rows"]["TT99-2026"]["status"] == "pending"


def test_approve_nap_hong_thi_502_va_giu_pending(client, fake_store, monkeypatch):
    """Canonical đã ghi mà chỉ mục chưa — phải nói ra, và để status ở pending để bấm lại."""
    import app.ingestion.pipeline as pipeline

    def no(doc, rels, tat_ca_docs):
        raise RuntimeError("LanceDB Cloud từ chối")

    monkeypatch.setattr(pipeline, "ingest_one_doc", no)
    fake_store["rows"]["TT99-2026"] = {"doc_id": "TT99-2026", "extracted": _DOC, "status": "pending"}

    r = client.post(
        "/documents/TT99-2026/approve",
        headers={"Authorization": f"Bearer {_token('admin')}"},
    )
    assert r.status_code == 502, r.text
    assert "duyệt lại" in r.json()["detail"]
    assert fake_store["rows"]["TT99-2026"]["status"] == "pending"
    assert "corpus.json" in fake_store["storage"], "canonical đã ghi — thông báo phải nói đúng thế"
    # Lỗi mà không để lại dấu vết thì lượt duyệt hỏng biến mất khỏi lịch sử: bảng vẫn
    # `pending`, `audit_log` không có gì, và không ai truy được là đã có người bấm.
    assert "doc_approve_failed" in fake_store["audit"]


def test_approve_khong_doc_duoc_canonical_thi_502_chu_khong_de_ban_dong_goi_len(
    client, fake_store, monkeypatch
):
    """Đọc-sửa-GHI không được fail-open.

    `load_canonical` nuốt lỗi Storage rồi rơi về `data/corpus.real.json` đóng gói trong image
    — đúng cho đường ĐỌC (thà bản cũ còn hơn trắng trang), nhưng ở đây bản 26 văn bản ấy sẽ
    được ghi đè lên `corpus.json` thật, xoá sạch mọi văn bản đã duyệt trước đó mà không một
    dòng lỗi. Câu "bấm lại vô hại" chỉ đúng khi lượt đọc này trả canonical thật.
    """
    import json

    goc = json.dumps(
        {"documents": [{**_DOC, "doc_id": "ND00-2020", "title": "Đã duyệt hôm qua"}],
         "relationships": []},
        ensure_ascii=False,
    ).encode("utf-8")
    fake_store["storage"]["corpus.json"] = goc
    fake_store["rows"]["TT99-2026"] = {"doc_id": "TT99-2026", "extracted": _DOC, "status": "pending"}

    def boom(tok, path):
        raise RuntimeError("Storage timeout")

    monkeypatch.setattr(appdb, "download_storage", boom)

    r = client.post(
        "/documents/TT99-2026/approve",
        headers={"Authorization": f"Bearer {_token('admin')}"},
    )
    assert r.status_code == 502, r.text
    assert fake_store["storage"]["corpus.json"] == goc, "canonical thật không được đụng tới"
    assert fake_store["rows"]["TT99-2026"]["status"] == "pending"
    assert fake_store["ingested"] == 0, "chưa đọc được canonical thì không được nạp gì"
    assert "doc_approve_failed" in fake_store["audit"]


# --- Nạp thẳng bản đã crawl từ vbpl (không qua extractor) ---

#: File thật trong repo, không bịa: 3 điều, 3 nút cây, có bảng thuộc tính và char_span.
_FILE_CRAWL = (
    "data/raw/vbpl/corpus/"
    "thong-tu-21-2026-tt-nhnn-sua-doi-bo-sung-dieu-15-thong-tu-so-15-2024-tt-nhnn-quy.json"
)


def _cam_extractor(monkeypatch):
    """Bắt quả tang nếu extractor chạy — chạy là mất provisions/so_hieu/char_span."""
    import app.ingestion.extract as extract_mod

    def _no(*_a, **_kw):
        raise AssertionError("extract_document chạy trên file đã đúng khuôn CorpusDocument")

    monkeypatch.setattr(extract_mod, "extract_document", _no)


def test_upload_json_da_crawl_giu_nguyen_cay_va_thuoc_tinh(client, fake_store, monkeypatch):
    """Bản crawl giàu hơn hẳn bản extract — đẩy nó qua regex + Gemini là vứt hết rồi đoán lại."""
    from pathlib import Path

    _cam_extractor(monkeypatch)
    noi_dung = Path(_FILE_CRAWL).read_bytes()

    r = client.post(
        "/documents/upload",
        files={"file": (Path(_FILE_CRAWL).name, noi_dung, "application/json")},
        headers={"Authorization": f"Bearer {_token('admin')}"},
    )

    assert r.status_code == 200, r.text
    assert r.json()["doc_id"] == "TT21-2026"
    luu = fake_store["rows"]["TT21-2026"]["extracted"]
    assert luu["so_hieu"] == "21/2026/TT-NHNN"
    assert len(luu["provisions"]) == 3, "cây điều khoản phải sống sót"
    assert luu["co_quan_ban_hanh"] == "Ngân hàng Nhà nước Việt Nam"
    assert luu["articles"][0]["char_start"] == 958, "char_span phải giữ nguyên từng con số"


def test_upload_json_hong_thi_422_chu_khong_roi_ve_extractor(client, fake_store, monkeypatch):
    """Rơi về extractor là biến một file hỏng thành văn bản trông như thật với vài điều rỗng."""
    _cam_extractor(monkeypatch)

    r = client.post(
        "/documents/upload",
        files={"file": ("hong.json", b'{"doc_id": "TT99-2026"}', "application/json")},
        headers={"Authorization": f"Bearer {_token('admin')}"},
    )

    assert r.status_code == 422, r.text
    assert "title" in r.text, "phải nói rõ thiếu trường nào, không nuốt lý do"
    assert fake_store["rows"] == {}, "không được tạo bản ghi pending cho file hỏng"


def test_upload_json_doc_id_ban_bi_chan(client, fake_store, monkeypatch):
    """`doc_id` chảy vào chuỗi điều kiện của `tbl.delete` ở bước duyệt — chặn từ cửa vào."""
    import json

    _cam_extractor(monkeypatch)
    xau = json.dumps({**_DOC, "doc_id": "TT99'; --"}, ensure_ascii=False).encode("utf-8")

    r = client.post(
        "/documents/upload",
        files={"file": ("xau.json", xau, "application/json")},
        headers={"Authorization": f"Bearer {_token('admin')}"},
    )

    assert r.status_code == 422, r.text
    assert fake_store["rows"] == {}


def test_upload_pdf_van_di_duong_extractor(client, fake_store, monkeypatch):
    """Đường cũ không được đụng: văn bản nội bộ SHB không có trang vbpl để cào."""
    import app.ingestion.extract as extract_mod

    duoi_da_thay: list[str] = []

    def _gia(path, source="external"):
        duoi_da_thay.append(path.suffix)
        return CorpusDocument.model_validate(_DOC)

    monkeypatch.setattr(extract_mod, "extract_document", _gia)

    r = client.post(
        "/documents/upload",
        files={"file": ("quy-dinh.pdf", b"%PDF-1.7 gia", "application/pdf")},
        headers={"Authorization": f"Bearer {_token('admin')}"},
    )

    assert r.status_code == 200, r.text
    assert duoi_da_thay == [".pdf"], "file không phải .json vẫn phải qua extractor"
    assert fake_store["rows"]["TT99-2026"]["status"] == "pending"
