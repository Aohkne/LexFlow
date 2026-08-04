"""Lược đồ vbpl.vn → 13 cạnh v0.5. Offline, đọc `data/raw/vbpl/sample.json`.

Điều đáng canh nhất là **chiều mũi tên**, và nó do `outgoing`/`incoming` quyết định chứ
không do nhãn: cặp #8 của v0.5 (*căn cứ ban hành* ⟷ *áp dụng*) bất quy tắc, hai nhãn không
chung gốc từ, nên suy chiều từ chữ nghĩa của nhãn là sai. Đúng nhóm đó lại là nhóm chứa
bốn Thông tư mà corpus từng gán nhầm `HUONG_DAN`.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from app.core.schemas import REL_TYPES
from app.ingestion.vbpl_luoc_do import (
    MA_THEO_NHAN,
    chuan_hoa_nhan,
    doc_luoc_do,
    so_hieu_tu_tieu_de,
)

_SAMPLE = Path("data/raw/vbpl/sample.json")
pytestmark = pytest.mark.skipif(not _SAMPLE.exists(), reason="chưa có mẫu vbpl")


@pytest.fixture(scope="module")
def mau():
    return json.loads(_SAMPLE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ket_qua(mau):
    return doc_luoc_do(mau)


# --- 1. Bảng nhãn suy từ REL_TYPES, không gõ tay -----------------------------


def test_26_nhan_van_phan_biet_duoc_sau_chuan_hoa():
    """`chuan_hoa_nhan` bỏ dấu phẩy — phải chắc phép đó KHÔNG gộp nhầm hai quan hệ."""
    tat = [chuan_hoa_nhan(n) for cap in REL_TYPES.values() for n in cap]
    assert len(tat) == len(set(tat)) == 26
    assert len(MA_THEO_NHAN) == 26


def test_bang_nhan_chi_tro_toi_ma_trong_tap_dong():
    assert set(MA_THEO_NHAN.values()) == set(REL_TYPES)


# --- 2. Chiều mũi tên do outgoing/incoming quyết định ------------------------


def test_outgoing_thi_van_ban_dang_xem_la_dau_nguon(ket_qua):
    canh, _ = ket_qua
    thay_the = [c for c in canh if c.rel_type == "THAY_THE"]
    assert thay_the, "mẫu phải có nhóm 'Văn bản được thay thế' ở outgoing"
    for c in thay_the:
        assert c.source_doc == "52/2024/NĐ-CP"
    assert {c.target_doc for c in thay_the} == {"80/2016/NĐ-CP", "101/2012/NĐ-CP"}


def test_incoming_thi_van_ban_dang_xem_la_dau_dich(ket_qua):
    canh, _ = ket_qua
    qd = [c for c in canh if c.rel_type == "QUY_DINH_CHI_TIET_HUONG_DAN"]
    assert len(qd) == 1
    assert qd[0].source_doc == "34/2024/TT-NHNN"
    assert qd[0].target_doc == "52/2024/NĐ-CP"


def test_cap_bat_quy_tac_CAN_CU_ra_dung_hai_chieu(ket_qua):
    """Cặp #8: hai nhãn KHÔNG chung gốc từ ⇒ suy chiều từ chữ nghĩa là sai.

    `outgoing "Căn cứ ban hành"` (ND52 căn cứ các Luật) và
    `incoming "Văn bản áp dụng"` (các Thông tư căn cứ ND52) là **cùng một mã**, ngược chiều.
    """
    canh, _ = ket_qua
    cc = [c for c in canh if c.rel_type == "CAN_CU"]
    ra = [c for c in cc if c.source_doc == "52/2024/NĐ-CP"]
    vao = [c for c in cc if c.target_doc == "52/2024/NĐ-CP"]
    assert len(ra) == 10, "outgoing 'Căn cứ ban hành' — 10 Luật"
    assert len(vao) == 20, "incoming 'Văn bản áp dụng' — 20 Thông tư"
    assert all("QH" in c.target_doc or "NĐ-CP" in c.target_doc for c in ra)


# --- 3. Ca đã sửa sai: bốn Thông tư KHÔNG phải quan hệ hướng dẫn -------------


@pytest.mark.parametrize("tt", ["15/2024/TT-NHNN", "17/2024/TT-NHNN",
                                "18/2024/TT-NHNN", "40/2024/TT-NHNN"])
def test_bon_thong_tu_la_CAN_CU_khong_phai_huong_dan(ket_qua, tt):
    """Corpus từng gán `HUONG_DAN → ND52` cho cả bốn. Nguồn chính thống nói khác.

    Cả bốn nằm ở `incoming / "Văn bản áp dụng"` — nhãn bị động của `CAN_CU` — chứ KHÔNG
    nằm ở `"Văn bản quy định chi tiết, hướng dẫn thi hành"` (nhóm đó chỉ có TT 34/2024).
    """
    canh, _ = ket_qua
    hop = [c for c in canh if c.source_doc == tt and c.target_doc == "52/2024/NĐ-CP"]
    assert len(hop) == 1
    assert hop[0].rel_type == "CAN_CU"
    assert hop[0].rel_type != "QUY_DINH_CHI_TIET_HUONG_DAN"


def test_co_instance_BAI_BO_that(ket_qua):
    """Ca kiểm chứng §6.2 (*legislative void*) hiện rỗng vì corpus có 0 `BAI_BO`.

    Nguồn vbpl CÓ: ND52 bãi bỏ ND 16/2019. Tức truy vấn đó sẽ có dữ liệu khi chuyển nguồn,
    chứ không phải một câu hỏi vĩnh viễn không trả lời được.
    """
    canh, _ = ket_qua
    bb = [c for c in canh if c.rel_type == "BAI_BO"]
    assert len(bb) == 1
    assert bb[0].source_doc == "52/2024/NĐ-CP"
    assert bb[0].target_doc == "16/2019/NĐ-CP"


# --- 4. Không đoán, không im lặng --------------------------------------------


def test_mau_that_khong_sinh_canh_bao_nao(ket_qua):
    _, cb = ket_qua
    assert cb == [], f"còn nhãn/số hiệu chưa quy được: {cb}"


def test_nhan_la_thi_bao_ra_chu_khong_bo_im_lang():
    mau = {
        "thuoc_tinh": {"so_hieu": "52/2024/NĐ-CP"},
        "luoc_do": {"outgoing": {"Văn bản chưa từng thấy": [{"title": "Luật số 1/2020/QH14"}]},
                    "incoming": {}},
    }
    canh, cb = doc_luoc_do(mau)
    assert canh == []
    assert len(cb) == 1 and "không thuộc 13 quan hệ" in cb[0]


def test_khong_doc_duoc_so_hieu_thi_bao_ra():
    mau = {
        "thuoc_tinh": {"so_hieu": "52/2024/NĐ-CP"},
        "luoc_do": {"outgoing": {"Văn bản được thay thế": [{"title": "Một văn bản không số"}]},
                    "incoming": {}},
    }
    canh, cb = doc_luoc_do(mau)
    assert canh == []
    assert len(cb) == 1 and "không đọc được số hiệu" in cb[0]


@pytest.mark.parametrize(
    ("tieu_de", "cho"),
    [
        ("Nghị định số 101/2012/NĐ-CP Về thanh toán không dùng tiền mặt", "101/2012/NĐ-CP"),
        ("Luật Phòng, chống rửa tiền số 14/2022/QH15", "14/2022/QH15"),
        ("Thông tư số 40/2024/TT-NHNN Quy định về hoạt động", "40/2024/TT-NHNN"),
        ("Quyết định số 38/2007/QĐ-NHNN", "38/2007/QĐ-NHNN"),
        ("Không có số hiệu nào cả", None),
    ],
)
def test_trich_so_hieu(tieu_de, cho):
    assert so_hieu_tu_tieu_de(tieu_de) == cho


def test_moi_canh_deu_dung_ma_trong_tap_dong(ket_qua):
    canh, _ = ket_qua
    assert Counter(c.rel_type for c in canh).keys() <= set(REL_TYPES)
    assert len(canh) == 35
