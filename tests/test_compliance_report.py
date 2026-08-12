"""Recall trên gold phap_ly + render báo cáo 3 cột + CLI end-to-end offline."""
from __future__ import annotations

import json

from app.compliance import er_triples, gate, judge
from app.compliance import hypernym as hypernym_mod
from app.compliance.report import tinh_recall
from tests.test_compliance_hop_dong import _mini_docx
from tests.test_compliance_policy_graph import _actor

_GOLD = [
    {"dieu_hop_dong": "3", "loai": "phap_ly", "trong_corpus": True,
     "van_ban": ["52/2024/NĐ-CP"], "comment_id": "13"},
    {"dieu_hop_dong": "9", "loai": "phap_ly", "trong_corpus": False,
     "van_ban": ["254/2026/NĐ-CP"], "comment_id": "8"},   # ngoài corpus → loại khỏi mẫu số
    {"dieu_hop_dong": "1", "loai": "van_phong", "trong_corpus": False,
     "van_ban": [], "comment_id": "7"},                    # không phải phap_ly → bỏ
]


def test_recall_dung_mau_so():
    # đường mới bắt được điều 3, viện dẫn đúng văn bản
    moi = {"3": [{"verdict": "vi_pham", "cu_id": "52/2024/NĐ-CP#than/dieu_3#khoan_15"}]}
    r = tinh_recall(_GOLD, moi)
    assert (r["mau_so"], r["bat_duoc"], r["ngoai_pham_vi"]) == (1, 1, 1)


def test_bat_sai_van_ban_khong_tinh():
    moi = {"3": [{"verdict": "vi_pham", "cu_id": "40/2024/TT-NHNN#than/dieu_25#khoan_1"}]}
    assert tinh_recall(_GOLD, moi)["bat_duoc"] == 0


def test_tuan_thu_khong_tinh_la_bat():
    moi = {"3": [{"verdict": "tuan_thu", "cu_id": "52/2024/NĐ-CP#than/dieu_3#khoan_15"}]}
    assert tinh_recall(_GOLD, moi)["bat_duoc"] == 0


def test_bo_sot_ghi_comment_id():
    r = tinh_recall(_GOLD, {})
    assert r["bo_sot"] == ["13"]


_CU_ID = "A/1#than/dieu_1#khoan_1"


def _chunk_dieu_1():
    return {"id": "DOC-A::Điều 1", "doc_id": "DOC-A", "article": "Điều 1",
            "doc_title": "A", "text": "…", "valid_from": "", "valid_to": ""}


def test_cli_end_to_end_offline(tmp_path, monkeypatch):
    """Fake toàn bộ LLM + retrieval; --bo-duong-cu bỏ hẳn đường cũ (run_review)."""
    docx = _mini_docx(tmp_path, [
        "Điều 1. Phí dịch vụ",
        "Bên B thanh toán phí dịch vụ trong 05 ngày.",
    ])

    cu_dir = tmp_path / "ontology"
    cu_dir.mkdir()
    (cu_dir / "pred.jsonl").write_text(
        json.dumps(_actor(_CU_ID)), encoding="utf-8")
    (cu_dir / "premise.jsonl").write_text("", encoding="utf-8")
    (cu_dir / "khainiem.jsonl").write_text("", encoding="utf-8")

    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text(json.dumps({
        "documents": [{
            "doc_id": "DOC-A", "so_hieu": "A/1", "title": "Văn bản A",
            "doc_type": "Nghị định", "source": "external", "articles": [],
        }],
        "relationships": [],
    }), encoding="utf-8")

    gold_path = tmp_path / "gold.jsonl"
    gold_path.write_text(json.dumps({
        "dieu_hop_dong": "1", "loai": "phap_ly", "trong_corpus": True,
        "van_ban": ["A/1"], "comment_id": "c1", "comment_text": "phải khớp Điều 1",
    }, ensure_ascii=False) + "\n", encoding="utf-8")

    # retrieval + hiệu lực — module-local trong app.compliance.gate
    monkeypatch.setattr(gate, "search_in_docs", lambda *a, **k: [_chunk_dieu_1()])
    monkeypatch.setattr(gate, "chu_thich_ket_qua", lambda c, *a, **k: (c, {}))

    # ER-triple — chỉ chấp nhận cụm từ nguyên văn trong điều
    monkeypatch.setattr(er_triples, "chat_json", lambda *a, **k: {"triples": [
        {"chu_the": "Bên B", "hanh_vi": "thanh toán", "doi_tuong": "phí dịch vụ"},
    ]})

    # Hypernym — khai_niem/premise rỗng nên tv.ung_vien() luôn rỗng, chat_json
    # không được gọi; embed_query phải mock để không bắn lưới thật.
    monkeypatch.setattr(hypernym_mod, "embed_query", lambda t: [0.0])
    monkeypatch.setattr(hypernym_mod, "embed_documents", lambda ts: [[0.0] for _ in ts])

    def _khong_duoc_goi(*_a, **_k):
        raise AssertionError("không được gọi LLM khi ứng viên hypernym rỗng")

    monkeypatch.setattr(hypernym_mod, "chat_json", _khong_duoc_goi)

    # Judge — đồng thuận 2 phiếu vi_pham ngay từ vòng đầu
    monkeypatch.setattr(judge, "chat_json", lambda *a, **k: {"phan_quyet": [
        {"cu_id": _CU_ID, "verdict": "vi_pham", "can_cu": "vượt ngưỡng",
         "quote_hop_dong": "phí dịch vụ", "quote_luat": "…"},
    ]})

    import app.compliance.__main__ as main_mod

    def _khong_duoc_goi_run_review(*_a, **_k):
        raise AssertionError("--bo-duong-cu phải bỏ hẳn run_review")

    monkeypatch.setattr(main_mod, "run_review", _khong_duoc_goi_run_review)

    out_path = tmp_path / "bao_cao.md"
    ra = main_mod.main([
        str(docx), "--against", "DOC-A", "--corpus", str(corpus_path),
        "--gold", str(gold_path), "--out", str(out_path),
        "--as-of", "2026-08-12", "--cu-dir", str(cu_dir), "--bo-duong-cu",
    ])

    assert ra == out_path
    text = out_path.read_text(encoding="utf-8")
    assert "| Điều | Gold | Đường cũ | Đường mới |" in text
    assert "## Recall" in text
    assert "vi_pham" in text and _CU_ID in text
    # gold điều 1 khớp đúng văn bản A/1 → bắt được, mẫu số 1
    assert "Mẫu số" in text
