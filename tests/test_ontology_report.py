"""Test trang HTML kiểm span — đặc biệt là kỷ luật encoding.

Encoding ở đây là vấn đề ĐÚNG/SAI: char_span đếm theo Unicode code point, nếu file
bị ghi/đọc sai codec thì `đ` thành 2 ký tự và MỌI offset phía sau lệch hết.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.ontology.extractor import build_cu
from app.ontology.parser import parse_dieu
from app.ontology.report import render
from app.ontology.segmenter import segment

_FIXTURE = Path("data/fixtures/ND52-2024-dieu22.txt")
_SO_HIEU = "52/2024/NĐ-CP"

# Chữ ký mojibake: UTF-8 bị đọc bằng cp1252 → "Điều" thành "Ä.iá»u", "đ" thành "Ä‘".
_MOJIBAKE_RE = re.compile(r"Ä‘|á»|áº|Ã¡|Ã´|Æ°|â€")


@pytest.fixture(scope="module")
def dieu():
    return parse_dieu(_FIXTURE.read_text(encoding="utf-8"), _SO_HIEU)


@pytest.fixture(scope="module")
def cu(dieu):
    k2 = dieu.khoan[1]
    units = segment(dieu, k2)
    data = {
        "subject": {"units": [2], "quote": "Tổ chức không phải là ngân hàng",
                    "label": "tổ chức không phải ngân hàng", "source": "explicit"},
        "action": {"units": [2], "quote": "được Ngân hàng Nhà nước cấp Giấy phép", "label": ""},
        "logic": "all",
        "conditions": [
            {"source_diem": "đ", "units": [13], "object_label": "bản thuyết minh",
             "constraint_label": "an toàn hệ thống thông tin cấp độ 3"},
        ],
    }
    return build_cu(data, k2, dieu, units)


def test_html_giu_nguyen_tieng_viet_qua_vong_ghi_doc(tmp_path, cu, dieu):
    """Ghi bằng write_text(encoding='utf-8') rồi đọc lại phải nguyên vẹn."""
    out = tmp_path / "report.html"
    out.write_text(render(cu, dieu), encoding="utf-8")

    html = out.read_text(encoding="utf-8")
    assert "Điều 22" in html
    assert "đ) Có Bản thuyết minh" in html  # điểm đ — chữ hay bị nuốt nhất
    assert "Tổ chức không phải là ngân hàng" in html
    assert not _MOJIBAKE_RE.search(html), "phát hiện chữ ký mojibake trong HTML"


def test_html_khai_bao_charset(cu, dieu):
    """Bytes đúng mà thiếu thẻ này thì browser vẫn đoán sai và hiện mojibake."""
    html = render(cu, dieu)
    assert '<meta charset="utf-8">' in html
    assert html.startswith("<!doctype html>")


def test_byte_tren_dia_dung_utf8(tmp_path, cu, dieu):
    out = tmp_path / "report.html"
    out.write_text(render(cu, dieu), encoding="utf-8")
    raw = out.read_bytes()
    assert "Điều".encode() in raw
    assert not raw.startswith(b"\xef\xbb\xbf")  # không BOM


def test_span_duoc_to_dung_cho(cu, dieu):
    html = render(cu, dieu)
    a, b = cu.subject.grounding.char_span
    assert f">{dieu.text[a:b]}</mark>" in html


def test_escape_html_trong_van_ban():
    """Văn bản luật có thể chứa < > &; không được để lọt thành thẻ."""
    from app.ontology.report import _render_text

    out = _render_text("mức phí < 5% & phù hợp", [(0, 8, "subject", "s")])
    assert "&lt;" in out and "&amp;" in out
    assert "<script" not in out


def test_source_diem_van_duoc_escape_trong_ten_hang(dieu):
    """Tên hàng có thẻ <b> cố ý cho phần tiết, nhưng dữ liệu LLM thì không được."""
    from app.ontology.extractor import build_cu
    from app.ontology.report import _rows

    k2 = dieu.khoan[1]
    units = segment(dieu, k2)
    cu = build_cu(
        {"subject": {"units": [1]}, "action": {"units": [1]}, "logic": "all",
         "conditions": [{"source_diem": "<img src=x onerror=alert(1)>", "units": [3]}]},
        k2, dieu, units,
    )
    html = _rows(cu)
    assert "<img" not in html
    assert "&lt;img" in html


def test_bao_cao_loi_cung_hien_ro(dieu):
    k2 = dieu.khoan[1]
    units = segment(dieu, k2)
    bad = build_cu(
        {"subject": {"units": [2], "label": "phải đáp ứng đầy đủ các điều kiện"},
         "action": {"units": [2], "label": ""}, "logic": "all", "conditions": []},
        k2, dieu, units,
    )
    html = render(bad, dieu)
    assert "lỗi cứng" in html
    assert "err-box" in html
