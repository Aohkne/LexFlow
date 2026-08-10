"""Số hiệu → `doc_id`: artefact là nguồn sự thật, không phải quy ước đặt tên.

`dong_goi` đóng băng bảng `so_hieu_theo_doc` vào artefact đúng vì `doc_id` là thứ **corpus tự
đặt**, không suy ra được. Nhưng bốn chỗ trong ngăn xếp lớp phủ vẫn suy lại bằng
`doc_id_theo_corpus` (quy ước `<loại ASCII><số>-<năm>`). Đo 09/08 trên
`data/overlay/lop_phu.json`: **4/26 văn bản lệch** — cả bốn là quy định nội bộ SHB
(`SHB-QD-VI-2023` ↔ `458/2023/QĐ-SHB`, quy ước cho ra `QD458-2023`).

Hôm nay vô hại vì lớp phủ chưa có cạnh nào chạm văn bản nội bộ. Hai loại ca ở đây:

* `tach_khoa` — chỗ `doc_id` sai biến thành link `/docs/{id}` sai trong sản phẩm: **sửa**;
* `test_quy_uoc_va_artefact_khong_duoc_lech` — dây bẫy cho ba chỗ còn lại
  (`hien_hanh.nut_don_vi`, `dinh_tuyen._cite`, `dinh_tuyen._tach_khoa`), nằm sâu trong hàm sắp
  xếp và dựng câu trích nên chưa luồn bảng vào; ngày nào chúng bắt đầu sai thì ca này đỏ.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ingestion.vbpl_corpus import doc_id_theo_corpus
from app.knowledge.lop_phu import tach_khoa, tai_lop_phu
from app.ontology.dong_goi import CanhGoi, GoiLopPhu

_ARTEFACT = Path("data/overlay/lop_phu.json")


@pytest.fixture
def lp_lech_quy_uoc(tmp_path):
    """Artefact có một văn bản mà `doc_id` KHÔNG suy ra được từ số hiệu."""
    goi = GoiLopPhu(
        sinh_luc="2026-08-09",
        so_hieu_theo_doc={
            "TT40-2024": "40/2024/TT-NHNN",
            "SHB-QD-VI-2023": "458/2023/QĐ-SHB",  # quy ước cho ra 'QD458-2023'
        },
        canh=[
            CanhGoi(
                nguon="458/2023/QĐ-SHB#than/dieu_3",
                dich="40/2024/TT-NHNN#than/dieu_26#khoan_1",
                thao_tac="sua_doi",
                valid_from="2025-01-01",
                menh_lenh="Sửa đổi khoản 1 Điều 26 như sau:",
            )
        ],
    )
    p = tmp_path / "lop_phu.json"
    p.write_text(goi.model_dump_json(), encoding="utf-8")
    tai_lop_phu.cache_clear()
    yield tai_lop_phu(str(p))
    tai_lop_phu.cache_clear()


def test_bang_artefact_thang_quy_uoc(lp_lech_quy_uoc):
    """Văn bản đặt tên lệch quy ước vẫn phải ra đúng `doc_id` của corpus."""
    # tiền đề: đây đúng là ca mà quy ước trả lời khác artefact
    assert doc_id_theo_corpus("458/2023/QĐ-SHB") == "QD458-2023"

    doc_id, nhan = tach_khoa("458/2023/QĐ-SHB#than/dieu_3", lp_lech_quy_uoc)
    assert doc_id == "SHB-QD-VI-2023", "suy theo quy ước ⇒ link /docs/QD458-2023 trỏ vào hư không"
    assert nhan == "Điều 3"


def test_so_hieu_ngoai_corpus_tra_none_chu_khong_bia(lp_lech_quy_uoc):
    """Văn bản ngoài corpus: không có `doc_id` nào đúng, nên phải nói KHÔNG BIẾT.

    Bản cũ suy theo quy ước ra `ND135-2015` — một mã không có trong corpus, nhưng trông y hệt
    một mã thật, nên phía web dựng link `/docs/ND135-2015` và người dùng nhận trang trống.
    """
    doc_id, nhan = tach_khoa("135/2015/NĐ-CP#than/dieu_14#khoan_4", lp_lech_quy_uoc)
    assert doc_id is None
    assert nhan == "Điều 14 Khoản 4", "không giải được doc_id thì vẫn phải giữ được nhãn"


def test_khoa_hong_van_tra_doi_none(lp_lech_quy_uoc):
    assert tach_khoa("không-phải-khoá", lp_lech_quy_uoc) == (None, None)


@pytest.mark.skipif(not _ARTEFACT.exists(), reason="thiếu data/overlay/lop_phu.json")
def test_quy_uoc_va_artefact_khong_duoc_lech():
    """DÂY BẪY cho ba chỗ còn suy `doc_id` theo quy ước.

    `hien_hanh.nut_don_vi` (thuộc tính node Neo4j), `dinh_tuyen._cite` và
    `dinh_tuyen._tach_khoa` (câu trích + khoá sắp xếp) chưa nhận bảng của artefact. Chúng đúng
    **chừng nào** mọi văn bản có mặt trong lớp phủ còn đặt tên theo quy ước. Ca này canh đúng
    điều kiện đó: đỏ nghĩa là đã tới lúc luồn bảng vào cả ba, không phải sửa ca test.
    """
    goi = json.loads(_ARTEFACT.read_text(encoding="utf-8"))
    doc_id_theo_so_hieu = {sh: d for d, sh in goi["so_hieu_theo_doc"].items()}
    trong_lop_phu = {
        c[dau].split("#", 1)[0] for c in goi["canh"] for dau in ("nguon", "dich")
    }

    lech = [
        (sh, doc_id_theo_so_hieu[sh], doc_id_theo_corpus(sh))
        for sh in sorted(trong_lop_phu & set(doc_id_theo_so_hieu))
        if doc_id_theo_corpus(sh) != doc_id_theo_so_hieu[sh]
    ]
    assert not lech, (
        "Văn bản trong lớp phủ có doc_id không suy được từ số hiệu:\n"
        + "\n".join(f"  {sh}: artefact={a!r} nhưng quy ước={b!r}" for sh, a, b in lech)
        + "\n⇒ luồn `doc_id_theo_so_hieu` của artefact vào hien_hanh.nut_don_vi, "
        "dinh_tuyen._cite và dinh_tuyen._tach_khoa."
    )
