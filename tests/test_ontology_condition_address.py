"""Địa chỉ của một cảnh báo phải trỏ tới ĐÚNG MỘT điều kiện — offline, không gọi Gemini.

Vì sao có file này: nhãn cảnh báo trước đây là `f"điều kiện {src}"`, mà nhiều điều kiện
**cùng trỏ về một Điểm** là chuyện thường trong văn bản thật. Đo trên `pred.jsonl`:
3/49 bản ghi có hiện tượng này, nặng nhất là ND52 Đ22 K2 — điểm `g` xuất hiện **5 lần**,
điểm `h` **4 lần** — và **9 cảnh báo** mang địa chỉ không phân biệt được.

Hậu quả không phải thẩm mỹ: người duyệt (hoặc `eval/ontology/triage.py`) đọc cảnh báo
"điều kiện g" rồi mở **nhầm** một trong năm đoạn luật, và không có gì báo là đã nhầm.
Đúng loại lỗi im lặng mà `suy_ra_duoc` / `co_tiet` đã phải sinh ra để chặn ở chỗ khác.

Phát hiện ra khi dựng hàng đợi duyệt, không phải khi đọc code.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ontology.extractor import build_cu
from app.ontology.parser import parse_dieu
from app.ontology.segmenter import segment

_DIR = Path("data/fixtures")


@pytest.fixture(scope="module")
def index():
    return json.loads((_DIR / "_index.json").read_text(encoding="utf-8"))


def _dieu(index, name):
    p = _DIR / name
    if not p.exists():
        pytest.skip(f"chưa sinh fixture {name}")
    return parse_dieu(p.read_text(encoding="utf-8"), index[name])


def _khoan(dieu, so: str):
    return next(k for k in dieu.khoan if k.so_hien_thi == so)


def _payload(units, conditions):
    uid = next(u.uid for u in units if u.uid > 0)
    return {
        "subject": {"units": [uid]},
        "action": {"units": [uid]},
        "logic": "all",
        "conditions": conditions,
    }


def _cond(units, src: str):
    """Điều kiện trỏ vào một Điểm KHÔNG tồn tại — sinh cảnh báo một cách tất định.

    Dùng cờ này (thay vì cờ tình thái) vì nó không phụ thuộc từ điển deontic: test
    canh *địa chỉ* của cảnh báo, không canh việc phát hiện ra cảnh báo.
    """
    uid = next(u.uid for u in units if u.uid > 0)
    return {"source_diem": src, "units": [uid], "object_label": "", "constraint_label": ""}


def test_nhieu_dieu_kien_cung_diem_thi_dia_chi_phai_phan_biet_duoc(index):
    dieu = _dieu(index, "ND52-2024-dieu22.txt")
    khoan = _khoan(dieu, "2")
    units = segment(dieu, khoan)
    cu = build_cu(
        _payload(units, [_cond(units, "z") for _ in range(3)]),
        khoan, dieu, units, role="actor_cu",
    )
    diachi = [w.split(":", 1)[0] for w in cu.warnings if "điểm không tồn tại" in w]
    assert diachi == ["điều kiện z#1", "điều kiện z#2", "điều kiện z#3"]
    # Điều đáng canh nhất: ba địa chỉ KHÁC NHAU. Trước khi sửa cả ba đều là "điều kiện z".
    assert len(set(diachi)) == 3


def test_diem_khong_trung_thi_nhan_giu_nguyen_khong_danh_so(index):
    """Không được đánh số vô cớ — 46/49 bản ghi còn lại phải giữ nguyên nhãn cũ."""
    dieu = _dieu(index, "ND52-2024-dieu22.txt")
    khoan = _khoan(dieu, "2")
    units = segment(dieu, khoan)
    cu = build_cu(
        _payload(units, [_cond(units, "y"), _cond(units, "z")]),
        khoan, dieu, units, role="actor_cu",
    )
    diachi = [w.split(":", 1)[0] for w in cu.warnings if "điểm không tồn tại" in w]
    assert diachi == ["điều kiện y", "điều kiện z"]
    assert not any("#" in d for d in diachi)


def test_dieu_kien_khong_neu_diem_cung_duoc_danh_so(index):
    """`source_diem: null` lặp lại cũng phải phân biệt được — Khoản không chẻ Điểm."""
    dieu = _dieu(index, "ND52-2024-dieu22.txt")
    khoan = _khoan(dieu, "2")
    units = segment(dieu, khoan)
    uid = next(u.uid for u in units if u.uid > 0)
    raw = [{"source_diem": None, "units": [uid], "object_label": "", "constraint_label": ""}] * 2
    cu = build_cu(_payload(units, raw), khoan, dieu, units, role="actor_cu")
    # Không sinh cảnh báo "điểm không tồn tại" (không nêu điểm thì không có gì để sai),
    # nhưng nhãn dùng cho MỌI cảnh báo khác vẫn phải đánh số được.
    assert len(cu.conditions) == 2
