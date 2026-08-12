"""Policy Graph in-memory: nạp JSONL, cạnh REFERS_TO, closure."""
import json

import pytest

from app.compliance.policy_graph import PolicyGraph, dieu_prefix


def _field(text="phải báo cáo"):
    return {"text": text, "label": "", "issues": [],
            "grounding": {"units": [1], "char_span": [0, len(text)], "status": "unit",
                          "quote": ""}}


def _actor(id, refs=(), modality="nghia_vu", errors=()):
    return {"type": "actor_cu", "id": id, "references": list(refs),
            "references_hep_hon": False, "warnings": [], "errors": list(errors),
            "subject": _field("Tổ chức"), "subject_source": "explicit",
            "action": _field(), "logic": "all", "conditions": [],
            "modality": modality, "nguong": [], "fixture": "x.txt"}


@pytest.fixture
def pg(tmp_path):
    rows = [
        _actor("A/1#than/dieu_5#khoan_1", refs=["A/1#than/dieu_6"]),
        _actor("A/1#than/dieu_6#khoan_1", modality="mien_tru"),
        _actor("A/1#than/dieu_7#khoan_1", errors=["bịa số"]),  # phải bị loại
    ]
    (tmp_path / "pred.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    (tmp_path / "premise.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "khainiem.jsonl").write_text("", encoding="utf-8")
    return PolicyGraph.load(tmp_path)


def test_loai_ban_ghi_loi(pg):
    assert "A/1#than/dieu_7#khoan_1" not in pg.cu


def test_cu_cua_dieu(pg):
    assert [c.id for c in pg.cu_cua_dieu("A/1", "5")] == ["A/1#than/dieu_5#khoan_1"]


def test_lang_gieng_hai_chieu(pg):
    # 5→6 khai trong references; từ 6 nhìn ngược cũng phải thấy 5
    assert [c.id for c in pg.lang_gieng("A/1#than/dieu_6#khoan_1")] == [
        "A/1#than/dieu_5#khoan_1"]


def test_closure_va_mien_tru(pg):
    ids = [c.id for c in pg.closure("A/1#than/dieu_5#khoan_1")]
    assert "A/1#than/dieu_6#khoan_1" in ids
    assert [c.id for c in pg.mien_tru_trong(ids)] == ["A/1#than/dieu_6#khoan_1"]


def test_dieu_prefix():
    assert dieu_prefix("A/1#than/dieu_22#khoan_2#diem_b") == "A/1#than/dieu_22"
