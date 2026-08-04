"""Bảng phân hoạch: chứng minh connector vô hại — offline, không gọi Gemini.

Vì sao có file này: người duyệt trả lời câu hỏi T2 *"các guard có loại trừ nhau không?"*
bằng *"loại trừ nhau về đối tượng áp dụng"* — nhưng **loại trừ nhau chưa đủ**. Với mỗi tiết
là một yêu cầu có guard:

    AND: (g₁ → c₁) ∧ (g₂ → c₂)        OR: (g₁ ∧ c₁) ∨ (g₂ ∧ c₂)

Hai cách đọc chỉ trùng nhau ở tình huống **có** một guard đúng. Tình huống không guard nào
đúng thì AND ra **miễn trừ** còn OR ra **bất khả thi** — nên điều kiện đúng là **phân hoạch**
(loại trừ nhau **và** phủ hết). Xem `docs/ONTOLOGY-POC.md` §14f.

Thứ đáng canh nhất KHÔNG phải phép chứng minh mà là phép **từ chối** chứng minh: chứng minh
nhầm một miền là phủ hết sẽ lặng lẽ xoá một câu hỏi pháp lý thật khỏi hàng đợi duyệt.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ontology.extractor import build_cu
from app.ontology.parser import parse_dieu
from app.ontology.phan_hoach import chuan_hoa, chung_minh
from app.ontology.segmenter import segment

_DIR = Path("data/fixtures")
_BANG = Path("data/phan_hoach.json")


@pytest.fixture(scope="module")
def index():
    return json.loads((_DIR / "_index.json").read_text(encoding="utf-8"))


def _cu_diem(index, name, khoan_so, diem_so):
    dieu = parse_dieu((_DIR / name).read_text(encoding="utf-8"), index[name])
    khoan = next(k for k in dieu.khoan if k.so_hien_thi == khoan_so)
    units = segment(dieu, khoan)
    uid = next(u.uid for u in units if u.source_diem == diem_so)
    return build_cu(
        {
            "subject": {"units": [uid]}, "action": {"units": [uid]}, "logic": "all",
            "conditions": [{"source_diem": diem_so, "units": [uid],
                            "object_label": "", "constraint_label": ""}],
        },
        khoan, dieu, units, role="actor_cu",
    )


# --- 1. Chứng minh -----------------------------------------------------------


def test_khach_hang_ca_nhan_to_chuc_la_phan_hoach():
    kq = chung_minh("khách hàng", ["cá nhân", "tổ chức"])
    assert kq is not None and kq.du
    assert kq.mien == "chu_the" and kq.thieu == []
    assert kq.can_cu == "17/2024/TT-NHNN#than/dieu_2#khoan_2"


def test_so_khop_bo_qua_hoa_thuong_va_khoang_trang():
    kq = chung_minh("  Khách   Hàng ", ["Cá Nhân", "TỔ CHỨC"])
    assert kq is not None and kq.du


# --- 2. Từ chối chứng minh — phần đáng canh nhất -----------------------------


def test_tai_khoan_thanh_toan_CHUA_phu_het_vi_con_hinh_thuc_chung():
    """Ca thật, tìm ra khi tra căn cứ chứ không khi đọc code.

    TT17 Điều 3 khoản 1 liệt kê **ba** hình thức tài khoản thanh toán: của cá nhân, của
    tổ chức, **và chung**. TT17 Đ16 k2 điểm b chỉ nói tới hai. Nếu bảng khoá thuần theo
    tập giá trị `{cá nhân, tổ chức}` thì ca này bị chứng minh nhầm là đã phủ hết — đó là
    lý do binding phải theo `thuoc_tinh`.
    """
    kq = chung_minh("tài khoản thanh toán", ["cá nhân", "tổ chức"])
    assert kq is not None
    assert not kq.du, "chứng minh nhầm ca này là xoá một câu hỏi pháp lý thật"
    assert kq.thieu == ["chung"]
    assert kq.can_cu == "17/2024/TT-NHNN#than/dieu_3#khoan_1"


def test_cung_tap_gia_tri_nhung_khac_thuoc_tinh_thi_khac_ket_qua():
    """Bất biến chống lại chính giả định ban đầu của thiết kế này."""
    a = chung_minh("khách hàng", ["cá nhân", "tổ chức"])
    b = chung_minh("tài khoản thanh toán", ["cá nhân", "tổ chức"])
    assert a.du is True and b.du is False


def test_thuoc_tinh_chua_khai_tra_None_chu_khong_tra_du_False():
    """`None` = *chưa ai trả lời*; `du=False` = *đã trả lời, và là chưa phủ hết*.

    Gộp hai cái làm một sẽ giấu mất chuyện bảng còn thiếu khai báo.
    """
    assert chung_minh("thẻ", ["thẻ trả trước", "thẻ tín dụng"]) is None
    assert chung_minh("khách hàng cá nhân", ["người Việt Nam"]) is None


def test_guard_trung_gia_tri_thi_khong_ket_luan():
    kq = chung_minh("khách hàng", ["cá nhân", "cá nhân"])
    assert kq is not None and kq.trung_lap and not kq.du


def test_gia_tri_la_ngoai_mien_thi_khong_ket_luan():
    """Guard nêu một giá trị miền không có ⇒ bảng và luật lệch nhau, phải im."""
    kq = chung_minh("khách hàng", ["cá nhân", "tổ chức", "hộ kinh doanh"])
    assert kq is not None and kq.la == ["hộ kinh doanh"] and not kq.du


# --- 3. Đi qua build_cu ------------------------------------------------------


def test_tt17_d16_k1_diem_a_duoc_chung_minh(index):
    cu = _cu_diem(index, "TT17-2024-dieu16.txt", "1", "a")
    c = next(x for x in cu.conditions if x.source_diem == "a")
    assert c.guard_phan_hoach == "chu_the"
    assert c.logic == "unknown", "chứng minh KHÔNG được đụng vào connector"
    w = " ".join(cu.warnings)
    assert "tiet_guard_phan_hoach" in w and "17/2024/TT-NHNN#than/dieu_2#khoan_2" in w
    assert "tiet_semicolon_guard_da_phu" not in w


def test_tt17_d16_k2_diem_b_van_la_cau_hoi_cho_nguoi(index):
    """Người duyệt đánh cờ này là *báo động giả*; bảng phân hoạch nói ngược lại."""
    cu = _cu_diem(index, "TT17-2024-dieu16.txt", "2", "b")
    c = next(x for x in cu.conditions if x.source_diem == "b")
    assert c.guard_phan_hoach is None
    w = " ".join(cu.warnings)
    assert "tiet_guard_thieu_gia_tri" in w and "'chung'" in w
    assert "tiet_guard_phan_hoach" not in w


# --- 4. Bảng dữ liệu phải tự nhất quán ---------------------------------------


def test_bang_phan_hoach_khong_khai_bao_hong():
    raw = json.loads(_BANG.read_text(encoding="utf-8"))
    mien = raw["mien"]
    for m, vals in mien.items():
        assert len(vals) >= 2, f"miền {m!r} chỉ có {len(vals)} giá trị — không phân hoạch được"
        assert len({chuan_hoa(v) for v in vals}) == len(vals), f"miền {m!r} có giá trị trùng"
    for t in raw["thuoc_tinh"]:
        assert t["mien"] in mien, f"{t['ten']!r} trỏ tới miền không tồn tại: {t['mien']!r}"
        # `phu_het` là khẳng định về LUẬT ⇒ bắt buộc phải có trích dẫn kiểm lại được.
        if t.get("phu_het"):
            assert t.get("can_cu"), f"{t['ten']!r} khai phủ hết mà không có căn cứ"
            assert t.get("trich"), f"{t['ten']!r} khai phủ hết mà không trích nguyên văn"


def test_moi_can_cu_deu_tro_toi_khoa_node_dung_dang():
    import re

    raw = json.loads(_BANG.read_text(encoding="utf-8"))
    pat = re.compile(r"^\S+#than/dieu_\d+(#khoan_\d+)?$")
    for t in raw["thuoc_tinh"]:
        if t.get("can_cu"):
            assert pat.match(t["can_cu"]), f"{t['ten']!r}: căn cứ sai dạng {t['can_cu']!r}"


def test_trich_dan_phai_co_that_trong_corpus():
    """Trích dẫn bịa còn tệ hơn không trích: nó tạo cảm giác đã kiểm chứng.

    Đối chiếu từng câu `trich` với `data/corpus.real.json` — nguồn văn bản thật.
    """
    corpus = json.loads(Path("data/corpus.real.json").read_text(encoding="utf-8"))
    docs = corpus if isinstance(corpus, list) else corpus.get("documents", [corpus])
    toan_van = "\n".join(
        " ".join(a.get("text", "").split()) for d in docs for a in d.get("articles", [])
    )
    raw = json.loads(_BANG.read_text(encoding="utf-8"))
    for t in raw["thuoc_tinh"]:
        trich = " ".join(t.get("trich", "").split())
        if trich:
            assert trich in toan_van, f"{t['ten']!r}: trích dẫn không có trong corpus"
