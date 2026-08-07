"""13 quan hệ giữa văn bản là TẬP ĐÓNG — offline, không chạm Neo4j.

Vì sao có file này: bản trước để `REL_TYPES = ["THAY_THE", "SUA_DOI", "HUONG_DAN",
"DAN_CHIEU"]` — bốn tên **tự đặt** — và `rel_type: str` **chưa bao giờ được đối chiếu với
nó**. Hệ quả đo được trên corpus: `HUONG_DAN` sống 4 lần dù nó không phải một quan hệ có
thật; v0.5 §6.3 tách nó làm hai quan hệ mà Điều 53 khoản 2 đối xử khác nhau (`R5` cùng
ngày hiệu lực chỉ áp cho văn bản quy định chi tiết **theo uỷ quyền**). Một chuỗi tự do
không ai canh thì sai lặng lẽ rồi nhân lên.

Cùng bảng đó từng bị **chép ở ba nơi** (`schemas.py`, `answer.py`, `pipeline.py`) nên sửa
một chỗ không kéo theo hai chỗ kia — test cuối file canh đúng chuyện đó.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.schemas import REL_BAT_LOI, REL_TYPES, Relationship, nhan_quan_he
from app.ingestion.kiem_quan_he import DOI_TEN_CO_HOC, soat


# --- 1. Tập đóng, đúng 13, khớp bảng v0.5 §6 ---------------------------------


def test_dung_13_quan_he():
    assert len(REL_TYPES) == 13


def test_ba_ten_cu_khong_con_hop_le():
    """`HUONG_DAN` là cái sai đã sống trong dữ liệu; hai cái kia chỉ sai tên."""
    for cu in ("HUONG_DAN", "SUA_DOI", "TAM_NGUNG"):
        assert cu not in REL_TYPES


def test_moi_ma_deu_co_du_hai_nhan():
    for ma, cap in REL_TYPES.items():
        assert len(cap) == 2, ma
        assert all(x.strip() for x in cap), ma


def test_12_tren_13_cap_theo_khuon_duoc_hoac_bi():
    """v0.5 §6: 12 cặp theo khuôn `X` ⟷ `được X`/`bị X`; đúng MỘT ngoại lệ (`CAN_CU`).

    Canh cả hai chiều: đúng khuôn thì nhiều hơn 12 nghĩa là ngoại lệ bị mất, ít hơn 12
    nghĩa là một cặp bị gõ sai chính tả.
    """
    khuon = re.compile(r"^(được|bị)\s+(.+)$")
    theo, ngoai_le = 0, []
    for ma, (chu_dong, bi_dong) in REL_TYPES.items():
        m = khuon.match(bi_dong)
        if m and m.group(2) == chu_dong:
            theo += 1
        else:
            ngoai_le.append(ma)
    assert theo == 12, f"ngoại lệ: {ngoai_le}"
    assert ngoai_le == ["CAN_CU"]


def test_ba_canh_bat_loi_dung_tien_to_bi():
    """`bị` = can thiệp bất lợi (huỷ/treo); `được` = diễn biến bình thường.

    Ranh giới KHÔNG phải "có chấm dứt hiệu lực hay không" — `THAY_THE` cũng chấm dứt mà
    vẫn mang `được`, vì nó là **kế thừa** chứ không phải **triệt tiêu**.
    """
    assert len(REL_BAT_LOI) == 3
    for ma in REL_BAT_LOI:
        assert REL_TYPES[ma][1].startswith("bị "), ma
    assert REL_TYPES["THAY_THE"][1].startswith("được ")


# --- 2. Chặn ở BIÊN dữ liệu vào ----------------------------------------------


@pytest.mark.parametrize("ma", sorted(REL_TYPES))
def test_moi_ma_hop_le_deu_dung_duoc(ma):
    assert Relationship(source_doc="A", target_doc="B", rel_type=ma).rel_type == ma


@pytest.mark.parametrize("xau", ["HUONG_DAN", "SUA_DOI", "", "thay_the", "BAI BO"])
def test_ma_ngoai_tap_bi_chan(xau):
    with pytest.raises(ValidationError) as e:
        Relationship(source_doc="A", target_doc="B", rel_type=xau)
    # Thông báo phải nêu ĐỦ 13 mã: người sửa dữ liệu cần biết ngay phải điền gì.
    loi = str(e.value)
    assert "13 quan hệ" in loi and "THAY_THE" in loi and "BAI_BO" in loi


def test_nhan_quan_he_hai_chieu():
    assert nhan_quan_he("BAI_BO") == "bãi bỏ"
    assert nhan_quan_he("BAI_BO", bi_dong=True) == "bị bãi bỏ"
    # Mã lạ trả về chính nó — log phải còn đọc được, không nổ.
    assert nhan_quan_he("KHONG_CO") == "KHONG_CO"


# --- 3. Công cụ soát dữ liệu -------------------------------------------------


def test_soat_bat_dung_canh_sai():
    rels = [
        {"source_doc": "A", "target_doc": "B", "rel_type": "THAY_THE"},
        {"source_doc": "C", "target_doc": "D", "rel_type": "SUA_DOI"},
        {"source_doc": "E", "target_doc": "F", "rel_type": "HUONG_DAN"},
    ]
    dem, sai = soat(rels)
    assert dem["THAY_THE"] == 1
    assert [r["rel_type"] for r in sai] == ["SUA_DOI", "HUONG_DAN"]
    # Chỉ gợi ý khi phép đổi tên là CƠ HỌC.
    assert sai[0]["goi_y"] == "SUA_DOI_BO_SUNG"
    assert sai[1]["goi_y"] is None, "HUONG_DAN cần người quyết, KHÔNG được gợi ý"


def test_bang_doi_ten_chi_tro_toi_ma_hop_le():
    for cu, moi in DOI_TEN_CO_HOC.items():
        assert cu not in REL_TYPES, f"{cu!r} vẫn còn hợp lệ thì không phải phép đổi tên"
        assert moi in REL_TYPES


def test_corpus_mau_dung_ma_hop_le():
    """`corpus.sample.json` là dữ liệu MẪU nhưng vẫn phải nói đúng từ vựng."""
    raw = json.loads(Path("data/corpus.sample.json").read_text(encoding="utf-8"))
    _, sai = soat(raw.get("relationships", []))
    assert sai == [], f"corpus mẫu còn mã ngoài tập đóng: {[r['rel_type'] for r in sai]}"


# --- 4. Một nguồn sự thật duy nhất -------------------------------------------


def test_khong_con_bang_nhan_chep_trung():
    """Sửa một chỗ phải kéo theo mọi chỗ — trước đây bảng nhãn bị chép ở ba nơi."""
    for f in ("app/reasoning/answer.py", "app/ingestion/pipeline.py"):
        src = Path(f).read_text(encoding="utf-8")
        assert "nhan_quan_he" in src, f"{f} không dùng nguồn chung"
        assert '"THAY_THE":' not in src, f"{f} còn bảng nhãn chép trùng"


def test_cypher_khoang_trong_dung_canh_co_kieu():
    """Truy vấn *legislative void* (§6.2) chỉ viết được khi cạnh CÓ KIỂU.

    Đọc chính chuỗi Cypher thay vì gọi Neo4j: test phải chạy offline, mà thứ đáng canh là
    câu truy vấn có dùng tên cạnh hay không — với `[:REL]` thì nó không tồn tại.
    """
    from app.knowledge.graph import CYPHER_KHOANG_TRONG

    assert "[:BAI_BO]" in CYPHER_KHOANG_TRONG
    assert "[:THAY_THE]" in CYPHER_KHOANG_TRONG
    assert "NOT" in CYPHER_KHOANG_TRONG
    assert ":REL" not in CYPHER_KHOANG_TRONG
