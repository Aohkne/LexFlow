"""Canh tính toàn vẹn của bộ fixture — offline.

Fixture là nền của mọi char_span nên phải commit và phải đúng: đổi một ký tự là
mọi offset trong bộ nhãn lệch theo.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.ontology.parser import khoan_de_trich, parse_dieu

_DIR = Path("data/fixtures")
_INDEX = _DIR / "_index.json"
_MOJIBAKE_RE = re.compile(r"Ä‘|á»|áº|Ã¡|Ã´|Æ°|â€")


@pytest.fixture(scope="module")
def index() -> dict[str, str]:
    return json.loads(_INDEX.read_text(encoding="utf-8"))


def test_moi_fixture_deu_co_trong_index(index):
    files = {p.name for p in _DIR.glob("*.txt")}
    assert files, "chưa sinh fixture nào"
    assert files == set(index), f"lệch: {files ^ set(index)}"


def test_so_hieu_khop_ten_file(index):
    """Test hồi quy cho bug ĐÃ GẶP THẬT: dò số hiệu trong THÂN Điều bắt nhầm.

    Mọi Thông tư trong corpus đều trích dẫn "52/2024/NĐ-CP", nên regex chạy trên
    thân Điều gán 7/10 fixture thành 52/2024/NĐ-CP — khoá node KG sai IM LẶNG.
    Số hiệu phải được chốt lúc sinh fixture (đọc header văn bản gốc) và tra lại
    từ _index.json, không bao giờ dò lại.
    """
    for name, so_hieu in index.items():
        prefix = name.split("-dieu")[0]  # "TT40-2024" / "ND52-2024"
        so, nam = re.match(r"[A-ZĐ]+(\d+)-(\d{4})", prefix).groups()
        assert so_hieu.startswith(f"{so}/{nam}/"), f"{name}: {so_hieu} không khớp {prefix}"


def test_fixture_parse_duoc_va_round_trip(index):
    for name, so_hieu in index.items():
        text = (_DIR / name).read_text(encoding="utf-8")
        dieu = parse_dieu(text, so_hieu)
        # 25/267 điều trong corpus KHÔNG chẻ khoản (thân là một đoạn liền), nên
        # `dieu.khoan` rỗng là hợp lệ. Cái phải luôn có là khoản-để-trích, nếu
        # không thì cả điều bị bỏ qua im lặng.
        assert khoan_de_trich(dieu), f"{name}: không có gì để trích"
        assert dieu.id.startswith(f"{so_hieu}#than/dieu_")
        for k in dieu.khoan:
            assert text[k.start : k.end] == k.text, f"{name} khoản {k.so_hien_thi}"
            for d in k.diem:
                assert text[d.start : d.end] == d.text, f"{name} điểm {d.so_hien_thi}"


def test_fixture_khong_mojibake_va_khong_bom():
    for p in _DIR.glob("*.txt"):
        raw = p.read_bytes()
        assert not raw.startswith(b"\xef\xbb\xbf"), f"{p.name}: có BOM"
        assert not _MOJIBAKE_RE.search(raw.decode("utf-8")), f"{p.name}: mojibake"


def test_fixture_da_sach_rac_bien_tap():
    for p in _DIR.glob("*.txt"):
        text = p.read_text(encoding="utf-8")
        assert "Phân tích" not in text, p.name
        assert "Đang cập nhật" not in text, p.name


def test_dieu_khong_che_khoan_van_trich_duoc(index):
    """Test hồi quy: ND52 Điều 1 là một đoạn liền, `dieu.khoan` rỗng.

    Trước khi có `khoan_de_trich`, `for k in dieu.khoan` chạy 0 lần ⇒ cả điều bị
    bỏ qua không một lời báo. 25/267 điều trong corpus ở dạng này.
    """
    name = "ND52-2024-dieu1.txt"
    if name not in index:
        pytest.skip("chưa sinh fixture Điều 1")
    text = (_DIR / name).read_text(encoding="utf-8")
    dieu = parse_dieu(text, index[name])
    assert dieu.khoan == []
    ks = khoan_de_trich(dieu)
    assert len(ks) == 1
    k = ks[0]
    assert k.id == dieu.id  # không bịa ra "khoản 1" không tồn tại
    assert k.so_hien_thi == ""
    assert text[k.start : k.end] == k.text
    assert "Nghị định này quy định" in k.text
    assert dieu.tieu_de not in k.text  # tiêu đề nằm ngoài thân


def test_du_quy_mo_toi_thieu(index):
    """docs/ROADMAP-SPRINT.md liệt eval >=30 case vào nhóm không được cắt."""
    total = sum(
        len(parse_dieu((_DIR / n).read_text(encoding="utf-8"), s).khoan)
        for n, s in index.items()
    )
    assert total >= 30, f"mới có {total} khoản"
