"""Guard của một nút phải DUY NHẤT, và không được mượn guard của tiết con.

Vì sao có file này — một lỗi ĐANG SỐNG trong `pred.jsonl`, tìm ra khi đối chiếu tầng Điểm
với tầng tiết chứ không khi đọc code:

    TT17 Đ16 k1 điểm a   guard tại ĐIỂM : ('khách hàng', 'cá nhân')
                         tiết (i)       : ('khách hàng', 'cá nhân')
                         tiết (ii)      : ('khách hàng', 'tổ chức')

`hop_guard` là AND dọc đường đi ⇒ tiết (ii) nhận `cá nhân ∧ tổ chức`, một guard **không đối
tượng nào thoả**. Cả **2/2** điều kiện có guard ở hai tầng đều hỏng như vậy.

Hai nguyên nhân độc lập, nên hai nhóm test:

1. `tach_guard` đọc TOÀN VĂN Điểm, gặp cụm của tiết (i) trước rồi trả nó — bản đầu lấy
   *cụm đầu tiên*. Sửa: nhiều cụm khác nhau ⇒ **không chọn hộ**, báo `guard_nhieu_cum`.
2. `extractor` truyền `diem_node.text` vào. Sửa: Điểm CÓ tiết thì đọc trên **câu bao trùm**
   (`chapeau_cua_diem`) — cùng ranh giới `chapeau_logic` đã dựng cho phép nối.

Một trong hai thôi thì chưa đủ: chỉ sửa (2) mà giữ "lấy cụm đầu" thì điểm b — chapeau chứa
HAI cụm ngoặc gắn vào hai danh ngữ — vẫn nhận nhầm một guard trong im lặng.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ontology.extractor import build_cu
from app.ontology.parser import chapeau_cua_diem, hop_guard, parse_dieu, tach_guard
from app.ontology.segmenter import segment

_DIR = Path("data/fixtures")


@pytest.fixture(scope="module")
def index():
    return json.loads((_DIR / "_index.json").read_text(encoding="utf-8"))


def _diem(index, name, khoan_so, diem_so):
    dieu = parse_dieu((_DIR / name).read_text(encoding="utf-8"), index[name])
    khoan = next(k for k in dieu.khoan if k.so_hien_thi == khoan_so)
    return dieu, khoan, next(d for d in khoan.diem if d.so_hien_thi == diem_so)


# --- 1. Nhiều cụm khác nhau ⇒ không chọn hộ ----------------------------------


def test_hai_cum_khac_nhau_thi_khong_tra_guard_nao(index):
    """Đọc toàn văn Điểm a: hai tiết mang hai guard đối lập ⇒ phải TỪ CHỐI, không lấy cụm đầu."""
    _, _, d = _diem(index, "TT17-2024-dieu16.txt", "1", "a")
    g, w = tach_guard(d.text, d.start)
    assert g is None, "lấy cụm đầu ⇒ Điểm nhận guard 'cá nhân', tiết (ii) thành bất khả thi"
    assert "guard_nhieu_cum" in w
    assert "'cá nhân'" in w and "'tổ chức'" in w


def test_cung_mot_guard_lap_lai_van_duoc_nhan(index):
    """Chỉ đếm các cặp KHÁC nhau — lặp lại cùng một guard không phải mâu thuẫn."""
    text = "Đối với khách hàng là cá nhân, tổ chức làm X; đối với khách hàng là cá nhân, làm Y."
    g, w = tach_guard(text, 0)
    assert g is not None and (g[0], g[1]) == ("khách hàng", "cá nhân")
    assert w == ""


def test_mot_cum_duy_nhat_van_chay_nhu_cu(index):
    """Ca vàng của B22 không được đổi — TT18 Đ13 k4, Khoản không chẻ Điểm."""
    dieu = parse_dieu((_DIR / "TT18-2024-dieu13.txt").read_text(encoding="utf-8"),
                      index["TT18-2024-dieu13.txt"])
    khoan = next(k for k in dieu.khoan if k.so_hien_thi == "4")
    g, w = tach_guard(khoan.text, khoan.start)
    assert g is not None and (g[0], g[1]) == ("thẻ", "thẻ trả trước")
    assert w == ""


# --- 2. Guard của Điểm đọc trên CÂU BAO TRÙM ---------------------------------


@pytest.mark.parametrize(
    ("khoan_so", "diem_so"),
    [("1", "a"), ("2", "b")],  # đúng 2/2 ca từng sinh guard bất khả thi
)
def test_guard_tiet_khong_bi_nang_len_thanh_guard_cua_diem(index, khoan_so, diem_so):
    dieu, khoan, d = _diem(index, "TT17-2024-dieu16.txt", khoan_so, diem_so)
    assert d.tiet, "ca này cần Điểm CÓ tiết"
    # Trên câu bao trùm: không có guard nào của riêng Điểm.
    g_ch, _ = tach_guard(chapeau_cua_diem(d), d.start)
    assert g_ch is None

    units = segment(dieu, khoan)
    uid = next(u.uid for u in units if u.source_diem == diem_so)
    cu = build_cu(
        {
            "subject": {"units": [uid]}, "action": {"units": [uid]}, "logic": "all",
            "conditions": [{"source_diem": diem_so, "units": [uid],
                            "object_label": "", "constraint_label": ""}],
        },
        khoan, dieu, units, role="actor_cu",
    )
    c = next(x for x in cu.conditions if x.source_diem == diem_so)
    assert c.ap_dung_khi is None, "guard của tiết bị nâng lên tầng Điểm"
    # …nhưng guard của từng tiết PHẢI còn nguyên.
    assert [s.ap_dung_khi.gia_tri for s in c.sub] == ["cá nhân", "tổ chức"]


def test_khong_con_guard_bat_kha_thi_tren_toan_corpus(index):
    """Bất biến: AND dọc đường đi không bao giờ ra hai giá trị KHÁC nhau của cùng thuộc tính.

    Đây là hình dạng của chính lỗi đã tìm ra, viết thành một phép quét — nó bắt được cả
    những ca tương lai mà hôm nay corpus chưa có.
    """
    n = 0
    for name, so_hieu in json.loads((_DIR / "_index.json").read_text(encoding="utf-8")).items():
        p = _DIR / name
        if not p.exists():
            continue
        dieu = parse_dieu(p.read_text(encoding="utf-8"), so_hieu)
        for k in dieu.khoan:
            for d in k.diem:
                src = chapeau_cua_diem(d) if d.tiet else d.text
                g_diem, _ = tach_guard(src, d.start)
                for t in d.tiet:
                    g_tiet, _ = tach_guard(t.text, t.start)
                    duong_di = hop_guard(g_diem, g_tiet)
                    n += 1
                    theo_tt: dict[str, str] = {}
                    for g in duong_di:
                        cu = theo_tt.setdefault(g[0], g[1])
                        assert cu == g[1], (
                            f"{name} k{k.so_hien_thi} điểm {d.so_hien_thi} tiết ({t.marker}): "
                            f"guard bất khả thi {g[0]!r} = {cu!r} ∧ {g[1]!r}"
                        )
    assert n >= 10, f"chỉ quét được {n} đường đi — nghi fixture hỏng"


def test_khoan_khong_che_diem_van_doc_tren_ca_khoan(index):
    """Ranh giới chỉ áp cho Điểm CÓ tiết — đừng thu hẹp nhầm ca TT18 Đ13 k4 của B22."""
    dieu = parse_dieu((_DIR / "TT18-2024-dieu13.txt").read_text(encoding="utf-8"),
                      index["TT18-2024-dieu13.txt"])
    khoan = next(k for k in dieu.khoan if k.so_hien_thi == "4")
    assert not khoan.diem
    units = segment(dieu, khoan)
    uid = max(u.uid for u in units)
    cu = build_cu(
        {
            "subject": {"units": [uid]}, "action": {"units": [uid]}, "logic": "all",
            "conditions": [{"source_diem": None, "units": [uid],
                            "object_label": "", "constraint_label": ""}],
        },
        khoan, dieu, units, role="actor_cu",
    )
    g = cu.conditions[0].ap_dung_khi
    assert g is not None and (g.thuoc_tinh, g.gia_tri) == ("thẻ", "thẻ trả trước")


# --- 3. Dấu ')' là dấu kết của cụm -------------------------------------------


def test_guard_trong_ngoac_don_tach_duoc_sau_khi_dung_o_dau_dong():
    """`(đối với khách hàng là cá nhân)` — không dừng ở ')' thì `_GUARD_XAU` loại vì có ngoặc."""
    text = "Thông tin sinh trắc học của chủ tài khoản (đối với khách hàng là cá nhân) với:"
    g, w = tach_guard(text, 0)
    assert g is not None and (g[0], g[1]) == ("khách hàng", "cá nhân")
    assert text[g[3] : g[4]] == g[2], "raw_text phải round-trip đúng char_span"
