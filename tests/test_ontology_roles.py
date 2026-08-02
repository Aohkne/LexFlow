"""Test phân loại vai premise / meta_cu / actor_cu — offline, không gọi Gemini.

Vì sao cần lớp này: pipeline trước mặc định MỌI Khoản đều là Compliance Unit. Đo
trên corpus thì 40/278 điều (14.4%) không phải vậy, và bộ fixture cũ không có điều
nào loại đó nên đường này chưa từng được thử.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ontology.parser import parse_dieu
from app.ontology.roles import classify_dieu, classify_document, is_van_ban_sua_doi
from app.ontology.schema import DieuNode

_DIR = Path("data/fixtures")
_INDEX = _DIR / "_index.json"


def _fake(so_goc: int, tieu_de: str, so_hau_to: int = 0) -> DieuNode:
    return DieuNode(
        id=f"01/2024/TT-X#than/dieu_{so_goc}", so_hien_thi=str(so_goc), so_goc=so_goc,
        so_hau_to=so_hau_to, start=0, end=1, text="x", tieu_de=tieu_de,
    )


# --- bảng tiêu đề ----------------------------------------------------------


@pytest.mark.parametrize(
    ("tieu_de", "role"),
    [
        ("Phạm vi điều chỉnh", "premise"),
        ("Giải thích từ ngữ", "premise"),
        ("Giải thích thuật ngữ", "premise"),
        ("Đối tượng áp dụng", "meta_cu"),
        ("Hiệu lực thi hành", "meta_cu"),
        ("Điều khoản chuyển tiếp", "meta_cu"),
        ("Hạn mức thẻ", "actor_cu"),
    ],
)
def test_bang_tieu_de(tieu_de, role):
    v = classify_dieu(_fake(9, tieu_de))
    assert v.role == role
    assert v.nguon in {"tieu_de", "mac_dinh"}


def test_trach_nhiem_thi_hanh_la_actor_cu_khong_phai_meta():
    """Bẫy: khớp chữ "thi hành" nên dễ bị xếp nhầm vào nhóm hiệu lực.

    Điều này giao nghĩa vụ thật ("Bộ trưởng… chịu trách nhiệm thi hành") nên là
    actor-CU. Khảo sát đầu tiên của tôi xếp nhầm — test này canh.
    """
    assert classify_dieu(_fake(38, "Trách nhiệm thi hành")).role == "actor_cu"
    assert classify_dieu(_fake(3, "Trách nhiệm tổ chức thực hiện")).role == "actor_cu"
    # còn "Hiệu lực thi hành" thì vẫn phải là meta
    assert classify_dieu(_fake(37, "Hiệu lực thi hành")).role == "meta_cu"


# --- quy ước vị trí --------------------------------------------------------


def test_vi_tri_chi_dung_khi_tieu_de_khong_khop():
    """Điều 1 = phạm vi, Điều 2 = đối tượng áp dụng — tri thức miền."""
    v1 = classify_dieu(_fake(1, "Tiêu đề lạ không khớp khuôn nào"))
    assert v1.role == "premise" and v1.nguon == "vi_tri"
    assert any("VỊ TRÍ" in w for w in v1.warnings)

    v2 = classify_dieu(_fake(2, "Tiêu đề lạ khác"))
    assert v2.role == "meta_cu" and v2.nguon == "vi_tri"


def test_tieu_de_thang_vi_tri_khi_bat_dong():
    """Đo được tiêu đề đúng hơn vị trí ⇒ lấy tiêu đề, nhưng phải cảnh báo."""
    v = classify_dieu(_fake(1, "Đối tượng áp dụng"))
    assert v.role == "meta_cu" and v.nguon == "tieu_de"
    assert any("lấy theo tiêu đề" in w for w in v.warnings)


def test_van_ban_sua_doi_tat_luat_vi_tri():
    """Ngoại lệ THẬT trong corpus: TT20-2016 và TT23-2019.

    Điều 1 của chúng là "Sửa đổi, bổ sung một số điều của Thông tư…", không phải
    phạm vi điều chỉnh. Áp luật vị trí sẽ gán nhầm thành premise.
    """
    assert is_van_ban_sua_doi("Sửa đổi, bổ sung một số điều của Thông tư 39/2014")
    assert not is_van_ban_sua_doi("Phạm vi điều chỉnh")

    lạ = _fake(1, "Tiêu đề lạ")
    assert classify_dieu(lạ, van_ban_sua_doi=False).role == "premise"
    assert classify_dieu(lạ, van_ban_sua_doi=True).role == "actor_cu"


def test_dieu_co_hau_to_khong_theo_quy_uoc_vi_tri():
    """"Điều 1a" là điều chèn thêm, không phải điều đầu văn bản."""
    v = classify_dieu(_fake(1, "Tiêu đề lạ", so_hau_to=1))
    assert v.nguon == "mac_dinh" and v.role == "actor_cu"


def test_classify_document_tu_do_van_ban_sua_doi():
    docs = [_fake(1, "Sửa đổi, bổ sung một số điều của Thông tư 39/2014"),
            _fake(2, "Tiêu đề lạ")]
    verdicts = classify_document(docs)
    assert verdicts[1].role == "actor_cu"  # không bị gán meta_cu theo vị trí


# --- chạy trên fixture thật ------------------------------------------------


def test_fixture_that_phan_loai_dung_va_khong_can_llm():
    index = json.loads(_INDEX.read_text(encoding="utf-8"))
    mong_doi = {
        "ND52-2024-dieu1.txt": "premise",
        "ND52-2024-dieu2.txt": "meta_cu",
        "ND52-2024-dieu3.txt": "premise",
        "ND52-2024-dieu22.txt": "actor_cu",
        "TT40-2024-dieu3.txt": "premise",
        "TT40-2024-dieu25.txt": "actor_cu",
    }
    for name, role in mong_doi.items():
        path = _DIR / name
        if not path.exists():
            pytest.skip(f"chưa sinh fixture {name}")
        dieu = parse_dieu(path.read_text(encoding="utf-8"), index[name])
        # allow_llm mặc định False → nếu cần LLM mới phân loại được thì test hỏng
        v = classify_dieu(dieu)
        assert v.role == role, f"{name}: {v.role} (tiêu đề {dieu.tieu_de!r})"
