"""Chấm `review.py`: ba mức verdict, và `not_assessed` không phải là sai.

Bộ nhãn cố ý nhỏ — 5 vi phạm cài sẵn + 2 mục đối chứng. 7 mục còn lại của 4 văn bản SHB không
có nhãn vì chưa ai phát biểu verdict đúng cho chúng; tự gán rồi tự chấm là tự chấm bài mình.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_NGUON = Path("eval/cham_tuan_thu.py")
_VANG = Path("eval/tuan_thu_vang.jsonl")
pytestmark = pytest.mark.skipif(not _NGUON.exists(), reason="thiếu eval/cham_tuan_thu.py")


def _nap():
    spec = importlib.util.spec_from_file_location("cham_tuan_thu", _NGUON)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_VANG_GIA = [
    {"noi_bo": "A::Mục 1", "verdict": "violation", "mo_ta": "vi phạm"},
    {"noi_bo": "B::Mục 2", "verdict": "pass", "mo_ta": "đối chứng"},
]


def test_warning_la_nua_dung_o_ca_hai_chieu():
    """Gộp `warning` vào đúng hay sai đều bóp méo — nó là nửa đúng ở cả hai phía."""
    x = _nap().xep_loai
    assert x("violation", "warning") == "nua_dung"
    assert x("pass", "warning") == "nua_dung"
    assert x("violation", "violation") == "dung"
    assert x("violation", "pass") == "sai"
    assert x("pass", "violation") == "sai"


def test_not_assessed_dung_rieng_khong_tinh_la_sai():
    """"Không biết" khác "đạt" — đó là thiết kế có chủ đích của review.py."""
    mod = _nap()
    assert mod.xep_loai("violation", "not_assessed") == "chua_danh_gia"
    kq = mod.cham(_VANG_GIA, {"A::Mục 1": "not_assessed", "B::Mục 2": "pass"})
    assert (kq["sai"], kq["chua_danh_gia"], kq["dung"]) == (0, 1, 1)
    assert kq["ty_le_dung"] == 1.0, "mẫu số phải loại ca chưa đánh giá, như review._score làm"


def test_thieu_phan_dinh_bi_loai_khoi_mau_so_chu_khong_cham_sai():
    kq = _nap().cham(_VANG_GIA, {"A::Mục 1": "violation"})
    assert kq["thieu_phan_dinh"] == ["B::Mục 2"]
    assert kq["n_cham"] == 1
    assert kq["sai"] == 0


def test_bo_sot_vi_pham_tach_rieng_khoi_moi_loi_khac():
    """Nói "đạt" về một quy định trái luật — đúng thứ sản phẩm sinh ra để chặn."""
    mod = _nap()
    kq = mod.cham(_VANG_GIA, {"A::Mục 1": "pass", "B::Mục 2": "violation"})
    assert kq["sai"] == 2
    nguy = mod.bo_sot_vi_pham(kq)
    assert [x["noi_bo"] for x in nguy] == ["A::Mục 1"], "chỉ ca nói đạt về vi phạm mới vào đây"


@pytest.mark.skipif(not _VANG.exists(), reason="thiếu eval/tuan_thu_vang.jsonl")
def test_bo_vang_that_tro_dung_muc_co_that():
    corpus = json.loads(Path("data/corpus.real.json").read_text(encoding="utf-8"))
    co = {f"{d['doc_id']}::{a['article']}" for d in corpus["documents"] for a in d["articles"]}
    vang = _nap().doc_vang()
    thieu = [c["noi_bo"] for c in vang if c["noi_bo"] not in co]
    assert not thieu, f"nhãn vàng trỏ vào mục không có trong corpus: {thieu}"
    assert all(c["verdict"] in ("violation", "warning", "pass") for c in vang)
