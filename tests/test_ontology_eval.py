"""Test bộ đo ontology — offline, hàm thuần trên dữ liệu giả lập."""
from __future__ import annotations

import json

import pytest

from eval.ontology.make_gold_seed import to_seed
from eval.ontology.run_eval import evaluate, iou, load_jsonl


def _pred(cu_id: str, subj=(0, 10), act=(11, 20), conds=(("a", (21, 30)),), errors=()) -> dict:
    return {
        "id": cu_id,
        "subject": {"grounding": {"char_span": list(subj) if subj else None}},
        "action": {"grounding": {"char_span": list(act) if act else None}},
        "subject_source": "explicit",
        "logic": "all",
        "conditions": [
            {"source_diem": d, "grounding": {"char_span": list(s)}} for d, s in conds
        ],
        "errors": list(errors),
    }


def _gold(cu_id: str, subj=(0, 10), act=(11, 20), conds=(("a", (21, 30)),), **kw) -> dict:
    return {
        "id": cu_id,
        "subject_span": list(subj) if subj else None,
        "action_span": list(act) if act else None,
        "subject_source": "explicit",
        "logic": "all",
        "conditions": [{"source_diem": d, "span": list(s)} for d, s in conds],
        **kw,
    }


def test_khung_duyet_khong_cat_bot_canh_bao():
    """Khung duyệt KHÔNG được cắt bớt cảnh báo — case thật ở TT17 Điều 16 khoản 2.

    Bản ghi đó có 10 cảnh báo; hai dòng giải thích vì sao nó hết lỗi cứng (nhãn mô tả
    chữ ngoài `quote`, `text` không chứa đoạn đang nói tới) nằm ở vị trí 6 và 7. Cắt
    `[:5]` cho gọn thì bản ghi hiện ra là sạch mà lý do nó sạch bị giấu — đúng thứ mà
    cả tầng duyệt này sinh ra để chặn.
    """
    pred = _pred("x")
    pred["warnings"] = [f"cảnh báo {i}" for i in range(10)]
    seed = to_seed(pred)
    assert seed["_may_de_xuat"]["warnings"] == pred["warnings"]


def test_iou():
    assert iou([0, 10], [0, 10]) == 1.0
    assert iou([0, 10], [5, 15]) == pytest.approx(5 / 15)
    assert iou([0, 10], [20, 30]) == 0.0
    assert iou([0, 10], None) == 0.0


def test_khop_hoan_hao():
    s = evaluate({"x": _pred("x")}, {"x": _gold("x")})
    assert s["span_exact"]["value"] == 1.0
    assert s["condition_set"]["f1"] == 1.0
    assert s["logic_accuracy"]["value"] == 1.0
    assert s["hard_error_agreement"]["value"] == 1.0


def test_span_lech_it_van_qua_nguong_iou():
    s = evaluate({"x": _pred("x", subj=(0, 10))}, {"x": _gold("x", subj=(0, 11))})
    assert s["span_exact"]["hit"] == 1  # chỉ action khớp chính xác
    assert s["span_iou_ge_0.8"]["value"] == 1.0  # 10/11 = 0.91 → vẫn đạt


def test_truong_gold_null_bi_loai_khoi_mau_so():
    """Quy ước của repo: `null` = không áp dụng, KHÔNG phải sai (như not_assessed)."""
    s = evaluate({"x": _pred("x")}, {"x": _gold("x", act=None, logic=None)})
    assert s["span_exact"]["total"] == 1  # chỉ chấm subject
    assert s["span_exact"]["skipped"] == 1
    assert s["logic_accuracy"]["total"] == 0
    assert s["logic_accuracy"]["value"] is None  # không có mẫu → không bịa ra 0.0


def test_condition_f1_bat_thua_va_thieu():
    pred = _pred("x", conds=(("a", (21, 30)), ("z", (40, 50))))  # thừa z
    gold = _gold("x", conds=(("a", (21, 30)), ("b", (31, 39))))  # thiếu b
    s = evaluate({"x": pred}, {"x": gold})
    c = s["condition_set"]
    assert (c["tp"], c["fp"], c["fn"]) == (1, 1, 1)
    assert c["f1"] == 0.5


def test_thieu_cu_trong_pred_duoc_bao_cao():
    s = evaluate({}, {"x": _gold("x")})
    assert s["missing_from_pred"] == ["x"]
    assert s["n_scored"] == 0


def test_khop_phan_dinh_loi_cung():
    # Gold đánh dấu case cố tình cài lỗi → pred phải báo lỗi mới tính là khớp.
    s = evaluate({"x": _pred("x", errors=["bịa số"])}, {"x": _gold("x", expect_hard_error=True)})
    assert s["hard_error_agreement"]["value"] == 1.0
    s2 = evaluate({"x": _pred("x")}, {"x": _gold("x", expect_hard_error=True)})
    assert s2["hard_error_agreement"]["value"] == 0.0


def test_load_jsonl_utf8(tmp_path):
    p = tmp_path / "g.jsonl"
    p.write_text(json.dumps(_gold("Điều 22#khoản 2"), ensure_ascii=False) + "\n", encoding="utf-8")
    rows = load_jsonl(p)
    assert "Điều 22#khoản 2" in rows
