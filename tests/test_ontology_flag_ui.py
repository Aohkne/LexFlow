"""Test trang duyệt CỜ — phần Python (dựng thẻ, neo span, tra địa chỉ về điều kiện).

Phần JavaScript (nút phán quyết, localStorage) không test được ở đây vì repo không có
trình chạy test cho web — cùng giới hạn đã ghi ở `test_ontology_review_ui.py`.

Điều đáng canh nhất KHÔNG phải là trang có mở được, mà là **span tô sáng có trỏ đúng
chỗ không**. Tô sai chỗ thì người duyệt vẫn bấm được nút, vẫn thấy hợp lý, và phán quyết
sai đi thẳng vào `flag_verdicts.jsonl` mà không gì báo — đúng loại lỗi im lặng mà cả
pipeline này sinh ra để chặn.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from eval.ontology.flag_ui import EXPORT, _locate, build_payload, render, to_jsonl

_MOJIBAKE_RE = re.compile(r"Ä‘|á»|áº|Ã¡|Ã´|Æ°|â€")
_PRED = Path("eval/ontology/pred.jsonl")

pytestmark = pytest.mark.skipif(not _PRED.exists(), reason="chưa sinh pred.jsonl")


@pytest.fixture(scope="module")
def payload():
    return build_payload(max_tier=4)


def test_co_the_cho_duyet_va_khong_rong(payload):
    assert payload["cards"], "không dựng được thẻ nào"
    assert all(c["key"] and c["id"] and c["warning"] for c in payload["cards"])


def test_span_to_sang_tro_dung_chu_cua_luat(payload):
    """`khoan_text[span]` phải là lát cắt thật, không lệch và không tràn."""
    n = 0
    for c in payload["cards"]:
        if not c["span"]:
            continue
        a, b = c["span"]
        assert 0 <= a <= b <= len(c["khoan_text"]), f"span tràn ở {c['id']} · {c['field']}"
        assert c["khoan_text"][a:b].strip(), f"span rỗng ở {c['id']} · {c['field']}"
        n += 1
    assert n, "không thẻ nào có span — trang sẽ không tô sáng được gì"


def test_khong_con_co_diem_khong_ton_tai(payload):
    """Cờ đông nhất cũ (19 cờ / 13 bản ghi) phải BIẾN MẤT, không phải bị ẩn đi.

    Trước đây trang này gom chúng thành một mục "lỗi hệ thống" để người duyệt khỏi quyết
    19 lần cho cùng một khuyết tật. Nay `source_diem` suy từ nhãn parser
    (`docs/ONTOLOGY-POC.md` §14d) nên cờ đó không sinh ra được nữa — và chỗ gom cũng đã
    gỡ. Canh cả hai vế: không cờ nào trong hàng đợi, và mã nguồn không còn sinh chuỗi đó.
    """
    lot = [c for c in payload["cards"] if "điểm không tồn tại" in c["warning"]]
    assert not lot, f"cờ lẽ ra đã bị xoá tận gốc: {[c['id'] for c in lot]}"
    src = Path("app/ontology/extractor.py").read_text(encoding="utf-8")
    assert "điểm không tồn tại" not in src


def test_dia_chi_khong_ro_diem_van_mo_ra_duoc_chu_cua_luat(payload):
    """19/102 điều kiện nay mang `source_diem is None` — chúng KHÔNG được thành cờ mù.

    Nhãn địa chỉ của chúng là "(không rõ điểm)", một chuỗi không bao giờ bằng `None`, nên
    thiếu phép ánh xạ ngược thì đúng những cờ đó hiện ra mà không kèm đoạn luật nào.
    """
    from eval.ontology.triage import KHONG_RO_DIEM

    mu = [
        c for c in payload["cards"]
        if KHONG_RO_DIEM in c["field"] and not c["span"] and not c.get("candidates")
    ]
    assert not mu, f"cờ không tra ra được chữ của luật: {[c['field'] for c in mu]}"


def test_dia_chi_mo_ho_thi_khong_lang_le_lay_cai_dau():
    """Nhiều điều kiện cùng `source_diem` ⇒ phải trả candidates, KHÔNG đoán."""
    row = {
        "conditions": [
            {"source_diem": "b", "text": "vế một", "grounding": {"char_span": [0, 6]}},
            {"source_diem": "b", "text": "vế hai", "grounding": {"char_span": [7, 13]}},
        ]
    }
    loc = _locate(row, "điều kiện b.constraint_label")
    assert loc["span"] is None, "không được chọn bừa một span khi địa chỉ mơ hồ"
    assert loc["candidates"] == ["vế một", "vế hai"]


def test_nhan_da_danh_so_thi_tro_dung_mot_dieu_kien():
    row = {
        "conditions": [
            {"source_diem": "b", "text": "vế một", "object_label": "L1",
             "grounding": {"char_span": [0, 6]}},
            {"source_diem": "b", "text": "vế hai", "object_label": "L2",
             "grounding": {"char_span": [7, 13]}},
        ]
    }
    loc = _locate(row, "điều kiện b#2.object_label")
    assert loc["span"] == [7, 13]
    assert loc["label"] == "L2"
    assert loc["candidates"] == []


def test_xuat_jsonl_dung_hop_dong(payload):
    rows = [{**c, "verdict": "dung", "note": ""} for c in payload["cards"][:2]]
    body = to_jsonl(rows)
    for line in body.strip().splitlines():
        assert sorted(json.loads(line)) == sorted(EXPORT)


def test_html_nhung_duoc_va_khong_mojibake(payload, tmp_path):
    html = render(payload, can_save=False)
    assert "__DATA__" not in html and "__CAN_SAVE__" not in html
    # `</` trong dữ liệu phải được thoát, nếu không một chuỗi chứa "</script>" đóng
    # sớm thẻ script và trang vỡ im lặng.
    assert "</script>" not in html.split("<script>")[1].split("render();")[0]
    p = tmp_path / "flags.html"
    p.write_text(html, encoding="utf-8")
    assert not _MOJIBAKE_RE.search(p.read_text(encoding="utf-8"))
