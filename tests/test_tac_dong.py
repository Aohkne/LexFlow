"""Bộ đọc mệnh lệnh tác động: điều của văn bản sửa → cạnh con↔con. Offline (trừ nhóm cuối)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ingestion.vbpl_corpus import duong_dan_toan_van, file_da_chuyen_khuon, tho_theo_so_hieu
from app.ontology.tac_dong import (
    CanhTacDong,
    canh_tu_dieu,
    dich_tu_menh_lenh,
    doc_tac_dong,
    doi_chung,
    so_hieu_nen,
    thao_tac_tu_cau,
)


@pytest.mark.parametrize(
    ("cau", "cho"),
    [
        ("Sửa đổi, bổ sung điểm b (ii) khoản 4 Điều 11", "sua_doi"),
        ("sửa đổi khoản 2 như sau:", "sua_doi"),
        ("Bãi bỏ điểm c khoản 7.", "bai_bo"),           # viết hoa đầu khoản — ca TT22
        ("bãi bỏ Điều 16, Điều 17, Điều 18", "bai_bo"),
        ("Bổ sung khoản 3 Điều 32", "bo_sung"),
        ("Thay thế Phụ lục kèm theo Thông tư 40/2024/TT-NHNN", "thay_phu_luc"),
        ('Thay thế cụm từ "Cơ quan Thanh tra, giám sát ngân hàng"', "thay_cum_tu"),
        ("Tổ chức thực hiện", None),                     # không phải mệnh lệnh tác động
        ("Trách nhiệm thi hành", None),
    ],
)
def test_thao_tac_tu_cau(cau, cho):
    assert thao_tac_tu_cau(cau) == cho


def test_sua_doi_bo_sung_gop_ve_sua_doi():
    """'Sửa đổi, bổ sung X' là MỘT thao tác ghi đè lời văn — không tách đôi."""
    assert thao_tac_tu_cau("Sửa đổi, bổ sung một số điểm, khoản của Điều 18") == "sua_doi"


def test_canh_mang_du_truong_va_mac_dinh():
    c = CanhTacDong(nguon="41/2025/TT-NHNN#than/dieu_8",
                    dich="40/2024/TT-NHNN#than/dieu_24#khoan_4",
                    thao_tac="bai_bo", menh_lenh="Bãi bỏ khoản 4 Điều 24")
    assert c.loi_van_moi is None and c.valid_from is None and c.canh_bao == []


def test_so_hieu_nen_tu_tieu_de_dieu_kieu_ND16():
    """ND16 mỗi điều sửa một nghị định KHÁC — số hiệu nền đọc từ tiêu đề điều."""
    td = ("Sửa đổi, bổ sung, bãi bỏ một số điều của Nghị định số 101/2012/NĐ-CP "
          "ngày 07 tháng 5 năm 2012 của Chính phủ về thanh toán không dùng tiền mặt")
    assert so_hieu_nen(td, mac_dinh="?") == "101/2012/NĐ-CP"


def test_so_hieu_nen_roi_ve_mac_dinh_khi_tieu_de_khong_neu():
    """TT41 tiêu đề điều chỉ ghi 'Sửa đổi, bổ sung một số khoản của Điều 9' — nền là TT40."""
    assert so_hieu_nen("Sửa đổi, bổ sung một số khoản của Điều 9",
                       mac_dinh="40/2024/TT-NHNN") == "40/2024/TT-NHNN"


def test_dich_diem_du_ngu_canh_dieu():
    """'Bãi bỏ điểm c khoản 7.' không nêu Điều — Điều lấy từ tiêu đề điều lệnh (ctx)."""
    khoa, cb = dich_tu_menh_lenh("Bãi bỏ điểm c khoản 7.", "40/2024/TT-NHNN", ctx_dieu="8")
    assert khoa == ["40/2024/TT-NHNN#than/dieu_8#khoan_7#diem_c"] and cb == []


def test_dich_nhieu_dieu_mot_cau():
    khoa, _ = dich_tu_menh_lenh("Bãi bỏ Điều 16, Điều 17, Điều 18 Thông tư số 41/2025/TT-NHNN",
                                "41/2025/TT-NHNN", ctx_dieu=None)
    assert khoa == ["41/2025/TT-NHNN#than/dieu_16", "41/2025/TT-NHNN#than/dieu_17",
                    "41/2025/TT-NHNN#than/dieu_18"]


def test_khong_giai_duoc_thi_bao_ra_khong_doan():
    khoa, cb = dich_tu_menh_lenh("Sửa đổi một số nội dung khác.", "40/2024/TT-NHNN", None)
    assert khoa == [] and len(cb) == 1


_DIEU_LENH = (
    "Sửa đổi, bổ sung một số điểm của Điều 8\n"
    "1. Sửa đổi điểm a khoản 1 như sau:\n"
    "“a) Quy định mới cho điểm a.”\n"
    "2. Bãi bỏ điểm c khoản 7.\n"
)


def _khoi_trich_cua(text: str, char_start: int) -> list[tuple[int, int]]:
    a = char_start + text.index("“")
    b = char_start + text.index("”") + 1
    return [(a, b)]


def test_canh_tu_dieu_che_khoan():
    cs = 1000  # vị trí giả định trong noi_dung
    canh, cb = canh_tu_dieu("Điều 1", _DIEU_LENH, cs, "41/2025/TT-NHNN", "40/2024/TT-NHNN",
                            _khoi_trich_cua(_DIEU_LENH, cs), valid_from="2025-11-05")
    assert [c.thao_tac for c in canh] == ["sua_doi", "bai_bo"]
    assert canh[0].dich == "40/2024/TT-NHNN#than/dieu_8#khoan_1#diem_a"
    assert canh[1].dich == "40/2024/TT-NHNN#than/dieu_8#khoan_7#diem_c"  # ctx Điều 8 từ tiêu đề
    assert canh[0].nguon == "41/2025/TT-NHNN#than/dieu_1#khoan_1"
    assert canh[0].loi_van_moi is not None and canh[1].loi_van_moi is None
    assert all(c.valid_from == "2025-11-05" for c in canh)
    assert cb == []


def test_canh_tu_dieu_khong_che_khoan():
    canh, cb = canh_tu_dieu("Điều 8", "Bãi bỏ khoản 4 Điều 24", 5000,
                            "41/2025/TT-NHNN", "40/2024/TT-NHNN", [], valid_from="2025-11-05")
    assert len(canh) == 1
    assert canh[0].nguon == "41/2025/TT-NHNN#than/dieu_8"
    assert canh[0].dich == "40/2024/TT-NHNN#than/dieu_24#khoan_4"
    assert cb == []


def test_sua_doi_thieu_khoi_trich_thi_canh_bao_khong_vut():
    canh, cb = canh_tu_dieu("Điều 2", "Sửa đổi khoản 3 Điều 9 như sau:", 0,
                            "41/2025/TT-NHNN", "40/2024/TT-NHNN", [], None)
    assert len(canh) == 1 and canh[0].loi_van_moi is None
    assert any("lời văn mới" in c for c in canh[0].canh_bao)
    assert cb == []


def test_dich_khong_giai_duoc_thi_canh_bao_o_cap_dieu_khong_vut_im():
    """Đọc được động từ nhưng không giải được đích ⇒ không cạnh, nhưng KHÔNG im lặng:
    cảnh báo phải trồi lên danh sách cấp điều, nhắc tới đúng câu mệnh lệnh gây lỗi."""
    text_dieu = (
        "Sửa đổi, bổ sung một số điểm của Điều 9\n"
        "1. Sửa đổi một số nội dung khác như sau:\n"
    )
    canh, cb = canh_tu_dieu("Điều 3", text_dieu, 0,
                            "41/2025/TT-NHNN", "40/2024/TT-NHNN", [], None)
    assert canh == []
    assert len(cb) >= 1
    assert any("nội dung khác" in w for w in cb)


def test_khoi_trich_cat_ngang_ranh_menh_lenh_thi_canh_bao():
    """Khối trích chồng lấn ranh hai khoản (không nằm trọn trong khoản nào) ⇒ cảnh báo
    riêng, không âm thầm rớt khỏi cả `loi_van_moi` lẫn danh sách cảnh báo."""
    cs = 1000
    a = cs + _DIEU_LENH.index("“")
    b = cs + _DIEU_LENH.index("2. Bãi bỏ") + len("2. B")  # cắt ngang qua ranh khoản 1/2
    canh, cb = canh_tu_dieu("Điều 1", _DIEU_LENH, cs, "41/2025/TT-NHNN", "40/2024/TT-NHNN",
                            [(a, b)], valid_from="2025-11-05")
    assert any("cắt ngang ranh mệnh lệnh" in w for w in cb)
    # khối cắt ngang bị loại khỏi gộp — khoản 1 không còn loi_van_moi từ khối này
    assert canh[0].loi_van_moi is None


# --- Đối chứng hai chiều với dieu_khoan_bi_tac_dong ----------------------------


def test_doi_chung_hai_chieu():
    canh = [
        CanhTacDong(nguon="S#than/dieu_1", dich="N#than/dieu_8#khoan_1#diem_a",
                    thao_tac="sua_doi", menh_lenh="x"),
        CanhTacDong(nguon="S#than/dieu_2", dich="N#than/dieu_99", thao_tac="bai_bo",
                    menh_lenh="y"),
    ]
    muc = [
        {"dieu": "Điều 8", "cap": "diem", "so": "a", "phan_loai": ["sua_doi_bo_sung"]},
        {"dieu": "Điều 24", "cap": "khoan", "so": "4", "phan_loai": ["bai_bo"]},
    ]
    lech = doi_chung(canh, muc, so_hieu_nen="N")
    assert len(lech) == 2
    assert any(x.startswith("[+]") and "dieu_99" in x for x in lech)
    assert any(x.startswith("[-]") and "Điều 24" in x for x in lech)


# --- Trên dữ liệu THẬT (05/08) --------------------------------------------------

_GOC = Path("data/raw/vbpl")
_CAN = (
    "41/2025/TT-NHNN", "40/2024/TT-NHNN", "22/2026/TT-NHNN",
    "15/2024/TT-NHNN", "34/2024/TT-NHNN",
)


def _thieu(*so_hieu: str) -> bool:
    bang = tho_theo_so_hieu(_GOC)
    return any(s not in bang for s in so_hieu)


@pytest.mark.skipif(_thieu(*_CAN), reason="chưa crawl đủ bản ghi vbpl cho đối chứng tích hợp")
def test_doc_tac_dong_tren_du_lieu_that():
    """Đo thật 05/08 (`uv run python -m app.ontology.tac_dong`) — KHÔNG chỉnh code để khớp
    con số đoán mù trong brief, số dưới đây là số đo được:

    - TT41/2025: 27 điều, 25 điều lệnh (Đ26/Đ27 không phải lệnh), **46 cạnh** — vượt dự đoán
      "≥25 cạnh".
    - Đối chứng hai chiều với `dieu_khoan_bi_tac_dong`: TT40 **90.4%** (75/83 mục khớp), TT15
      **92.5%** (37/40), TT34 **92.1%** (35/38) — cả ba vượt ngưỡng nghiệm thu P1 ≥90%. Phần
      còn lệch chủ yếu là `phan_loai` `'thay_the'` (nằm ngoài 5 thao_tac mà `thao_tac_tu_cau`
      đọc — đó là một lớp phân loại khác của vbpl, "được thay thế", không phải một mệnh lệnh
      sửa/bãi bỏ/bổ sung) và các mệnh lệnh `thay_cum_tu`/`thay_phu_luc` trỏ vào Phụ lục mà
      `citation.py` chưa đọc được tham chiếu — cả hai đều lộ ra qua `canh_bao` "không giải
      được đích", không mất tích im lặng.
    - Mọi `loi_van_moi`: bắt đầu đúng một `char_start` và kết thúc đúng một `char_end` thật
      của `trich_dan`, ký tự đầu là dấu ngoặc kép — đo trên 142/142 cạnh có `loi_van_moi`. Cố
      ý KHÔNG đòi span nằm trong MỘT khối `trich_dan` duy nhất như brief phỏng đoán: 13/142
      là khối GỘP nhiều `trich_dan` không liền kề (đã tự mang cảnh báo "không liền kề" từ
      `canh_tu_dieu`), nên hợp của chúng không nằm trong một khối — biên vẫn đúng, chỉ không
      "một khối" theo nghĩa hẹp.
    """
    canh, _canh_bao = doc_tac_dong(_GOC)

    tt41 = [c for c in canh if c.nguon.startswith("41/2025/TT-NHNN#")]
    assert len(tt41) >= 25

    # Ca khoá cứng 1: TT41 Đ8 -bai_bo-> TT40 Đ24 khoản 4.
    assert any(
        c.nguon == "41/2025/TT-NHNN#than/dieu_8"
        and c.dich == "40/2024/TT-NHNN#than/dieu_24#khoan_4"
        and c.thao_tac == "bai_bo"
        for c in canh
    )

    # Ca khoá cứng 2: TT22 Đ6 khoản 2 sinh 3 cạnh bãi bỏ vào TT41 Đ16/17/18.
    tt22_dich = {
        c.dich for c in canh
        if c.nguon == "22/2026/TT-NHNN#than/dieu_6#khoan_2" and c.thao_tac == "bai_bo"
    }
    assert {
        "41/2025/TT-NHNN#than/dieu_16",
        "41/2025/TT-NHNN#than/dieu_17",
        "41/2025/TT-NHNN#than/dieu_18",
    } <= tt22_dich

    # Mọi `loi_van_moi` neo đúng biên trich_dan thật của văn bản NGUỒN (xem docstring test).
    trich_start: dict[str, set[int]] = {}
    trich_end: dict[str, set[int]] = {}
    noi_dung_theo_sh: dict[str, str] = {}
    for p in file_da_chuyen_khuon(_GOC):
        corpus = json.loads(p.read_text(encoding="utf-8"))
        sh = corpus.get("so_hieu")
        if not sh:
            continue
        p_tho = duong_dan_toan_van(p)
        if not p_tho.exists():
            continue
        tho = json.loads(p_tho.read_text(encoding="utf-8"))
        trich_start[sh] = {t["char_start"] for t in corpus.get("trich_dan") or []}
        trich_end[sh] = {t["char_end"] for t in corpus.get("trich_dan") or []}
        noi_dung_theo_sh[sh] = tho.get("noi_dung") or ""

    checked = 0
    for c in canh:
        if not c.loi_van_moi:
            continue
        sh = c.nguon.split("#", 1)[0]
        a, b = c.loi_van_moi
        assert noi_dung_theo_sh[sh][a] in ("“", '"')
        assert a in trich_start[sh]
        assert b in trich_end[sh]
        checked += 1
    assert checked >= 100

    # Đối chứng hai chiều: ≥90% mục `dieu_khoan_bi_tac_dong` của TT40/TT15/TT34 có cạnh khớp.
    bang = tho_theo_so_hieu(_GOC)
    for sh, toi_thieu_muc in (
        ("40/2024/TT-NHNN", 83), ("15/2024/TT-NHNN", 40), ("34/2024/TT-NHNN", 38),
    ):
        raw = json.loads(bang[sh].read_text(encoding="utf-8"))
        muc = raw.get("dieu_khoan_bi_tac_dong") or []
        assert len(muc) >= toi_thieu_muc
        lech = doi_chung(canh, muc, sh)
        so_lech = sum(1 for x in lech if x.startswith("[-]"))
        ty_le = (len(muc) - so_lech) / len(muc)
        assert ty_le >= 0.90, f"{sh}: chỉ khớp {ty_le:.1%} ({len(muc) - so_lech}/{len(muc)})"
