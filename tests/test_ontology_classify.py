"""Test tầng phân loại đơn vị (Test A/B/C) — offline, không gọi Gemini.

Trọng tâm là các lỗi ĐÃ GẶP THẬT khi chạy classifier trên corpus, không phải các
tình huống tưởng tượng: bẫy "phải" phi-deontic, cực của cổng, phạm vi hiệu lực
theo Điều, và viện dẫn mơ hồ không được phép sinh khoá node.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ontology.classify import (
    UnitCtx,
    classify_dieu_unit,
    classify_khoan,
    classify_unit,
    deontic_groups,
    detect_gate,
    find_alias,
)
from app.ontology.extractor import build_premise_record
from app.ontology.parser import khoan_de_trich, parse_dieu

_DIR = Path("data/fixtures")


@pytest.fixture(scope="module")
def index():
    return json.loads((_DIR / "_index.json").read_text(encoding="utf-8"))


def _dieu(index, name):
    p = _DIR / name
    if not p.exists():
        pytest.skip(f"chưa sinh fixture {name}")
    return parse_dieu(p.read_text(encoding="utf-8"), index[name])


def _khoan(index, name, so):
    d = _dieu(index, name)
    return d, next(k for k in khoan_de_trich(d) if k.so_hien_thi == so)


# --- Bộ 5 case bắt buộc của đề bài ----------------------------------------


def test_case1_doi_tuong_ap_dung_ra_premise(index):
    """ND52 Điều 2: 4 khoản → premise/vai_tro, khoản 4 kèm bí danh "khách hàng".

    Đây là chỗ lệch với `roles.classify_dieu`, vốn xếp cả Điều là meta_cu. Hai
    phán quyết ở hai CẤP khác nhau và cả hai đều đúng — xem
    docs/ONTOLOGY-CLASSIFY.md §2.
    """
    dieu = _dieu(index, "ND52-2024-dieu2.txt")
    verdicts = [classify_khoan(k, dieu) for k in khoan_de_trich(dieu)]
    assert len(verdicts) == 4
    assert all(v.type == "premise" and v.premise_kind == "vai_tro" for v in verdicts)
    assert verdicts[3].alias == "khách hàng"
    assert [v.alias for v in verdicts[:3]] == [None, None, None]


def test_case1_alias_span_round_trip_ve_dieu_text(index):
    """Bí danh phải cắt lại được từ `dieu.text` — sai gốc offset là hỏng cả registry."""
    dieu = _dieu(index, "ND52-2024-dieu2.txt")
    k4 = next(k for k in khoan_de_trich(dieu) if k.so_hien_thi == "4")
    v = classify_khoan(k4, dieu)
    a, b = v.alias_span
    assert dieu.text[a:b] == "khách hàng"


def test_case2_hieu_luc_ra_meta_cu_cong_thoi_gian(index):
    dieu, k = _khoan(index, "ND52-2024-dieu37.txt", "1")
    v = classify_khoan(k, dieu)
    assert v.type == "meta_cu"
    assert v.gates[0].kind == "thoi_gian"
    assert v.gates[0].pham_vi == "van_ban"
    assert v.gates[0].suy_ra_duoc


def test_case2_bat_ca_hai_bien_the_tu_ngay():
    """Luật thật viết "từ ngày"; đề bài viết "kể từ ngày". Không gán chết một biến thể."""
    ctx = UnitCtx(dieu_id="52/2024/NĐ-CP#than/dieu_37", dieu_so=37,
                  dieu_so_hien_thi="37", dieu_tieu_de="Hiệu lực thi hành", khoan_so="1")
    for cau in (
        "Nghị định này có hiệu lực thi hành từ ngày 01 tháng 7 năm 2024.",
        "Nghị định này có hiệu lực thi hành kể từ ngày 01 tháng 7 năm 2024.",
    ):
        assert classify_unit(cau, ctx).type == "meta_cu"


def test_case3_dieu_22_khoan_2_la_actor_cu(index):
    dieu, k = _khoan(index, "ND52-2024-dieu22.txt", "2")
    v = classify_khoan(k, dieu)
    assert v.type == "actor_cu"
    assert v.gates == []  # actor-CU không mang cổng
    assert len(k.diem) == 8


def test_case4_tiet_long_trong_diem_van_la_actor_cu(index):
    dieu, k = _khoan(index, "TT17-2024-dieu16.txt", "2")
    v = classify_khoan(k, dieu)
    assert v.type == "actor_cu"
    diem_b = next(d for d in k.diem if d.so_hien_thi == "b")
    assert len(diem_b.tiet) >= 2


def test_case5_pham_vi_muc_ra_meta_cu_nhung_khong_suy_ra_duoc():
    """Câu GIẢ ĐỊNH của đề bài. Nhận đúng là cổng, và khai thẳng là chưa quy được
    về khoá node — parser không có cấp Mục."""
    cau = ("Quy định tại Mục này chỉ áp dụng đối với tổ chức đã được Ngân hàng Nhà "
           "nước cấp Giấy phép hoạt động cung ứng dịch vụ trung gian thanh toán.")
    v = classify_unit(cau, UnitCtx(dieu_id="52/2024/NĐ-CP#than/dieu_20", dieu_so=20,
                                   dieu_so_hien_thi="20",
                                   dieu_tieu_de="Điều kiện cung ứng dịch vụ", khoan_so="1"))
    assert v.type == "meta_cu"
    g = v.gates[0]
    assert (g.kind, g.pham_vi) == ("chu_the", "muc")
    assert g.suy_ra_duoc is False
    assert v.warnings  # sự thiếu hụt phải hiện ra, không im lặng


def test_case5_chu_duoc_bi_dong_khong_bien_thanh_actor_cu():
    """"đã ĐƯỢC cấp Giấy phép" là bị động, không phải trao quyền — nếu Test A đọc
    nhầm thì câu phạm vi bị xếp thành nghĩa vụ."""
    cau = "Quy định tại Mục này chỉ áp dụng đối với tổ chức đã được cấp Giấy phép."
    v = classify_unit(cau, UnitCtx(dieu_tieu_de="Điều kiện", dieu_so_hien_thi="20"))
    assert v.type == "meta_cu"


# --- Bẫy "phải" phi-deontic (6/94 đơn vị bị gán nhầm trước khi sửa) ---------


@pytest.mark.parametrize(
    "cau",
    [
        "Tổ chức cung ứng dịch vụ trung gian thanh toán là tổ chức không phải là ngân hàng.",
        "…tính toán kết quả số tiền phải thu, phải trả sau khi bù trừ giữa các bên.",
        "…giới hạn giá trị đối với khoản chênh lệch bù trừ phải trả của thành viên.",
    ],
)
def test_phai_phi_deontic_khong_tinh_la_nghia_vu(cau):
    assert "nghia_vu" not in deontic_groups(cau)


def test_phai_that_van_bat_duoc():
    assert "nghia_vu" in deontic_groups("Tổ chức phải báo cáo Ngân hàng Nhà nước.")


def test_dinh_nghia_co_phai_van_o_lai_premise(index):
    """ND52 Điều 3 khoản 5/15 và TT40 Điều 3 khoản 7/9/13 — định nghĩa chứa "phải"."""
    for name, sos in [("ND52-2024-dieu3.txt", ["5", "15"]),
                      ("TT40-2024-dieu3.txt", ["7", "9", "13"])]:
        dieu = _dieu(index, name)
        for so in sos:
            k = next(k for k in khoan_de_trich(dieu) if k.so_hien_thi == so)
            v = classify_khoan(k, dieu)
            assert v.type == "premise", f"{name} khoản {so} → {v.type}"
            assert v.premise_kind == "dinh_nghia"


def test_tieu_de_premise_khong_bi_tinh_thai_lat_am_tham():
    """Nếu một định nghĩa CÓ nghĩa vụ thật, giữ premise theo tiêu đề nhưng phải kêu."""
    cau = "Báo cáo định kỳ là báo cáo mà tổ chức phải gửi Ngân hàng Nhà nước hằng quý."
    v = classify_unit(cau, UnitCtx(dieu_tieu_de="Giải thích từ ngữ", dieu_so_hien_thi="3"))
    assert v.type == "premise"
    assert any("cần người đọc soi lại" in w for w in v.warnings)


# --- Cổng: cực, phạm vi, và cái không suy ra được --------------------------


def test_cong_phu_dinh_khong_bi_doc_thanh_trao_pham_vi(index):
    """TT40 Điều 26 khoản 2: "Quy định tại khoản 1 Điều này KHÔNG áp dụng đối với…".

    Bỏ sót chữ "không" là đảo ngược hiệu lực của cả khoản 1.
    """
    dieu, k = _khoan(index, "TT40-2024-dieu26.txt", "2")
    v = classify_khoan(k, dieu)
    assert v.type == "meta_cu"
    g = v.gates[0]
    assert g.phu_dinh is True
    assert g.targets == ["40/2024/TT-NHNN#than/dieu_26#khoan_1"]


def test_hieu_luc_theo_dieu_khong_bi_thoi_thanh_ca_van_ban(index):
    """TT40 Điều 52 khoản 2: hiệu lực riêng cho Điều 11,12,13,14,35 và khoản 4 Điều 47."""
    dieu, k = _khoan(index, "TT40-2024-dieu52.txt", "2")
    g = classify_khoan(k, dieu).gates[0]
    assert g.pham_vi != "van_ban"
    assert "40/2024/TT-NHNN#than/dieu_11" in g.targets
    # "…Điều 35, khoản 4 Điều 47" — trước khi sửa văn phạm citation.py, "khoản 4"
    # bị nuốt thành "Điều 4".
    assert "40/2024/TT-NHNN#than/dieu_47#khoan_4" in g.targets
    assert "40/2024/TT-NHNN#than/dieu_4" not in g.targets


def test_ngoai_tru_khong_bi_tron_vao_pham_vi_phu(index):
    """TT40 Điều 52 khoản 1: "…trừ trường hợp quy định tại khoản 2,3,4,5 Điều này"."""
    dieu, k = _khoan(index, "TT40-2024-dieu52.txt", "1")
    g = classify_khoan(k, dieu).gates[0]
    assert g.pham_vi == "van_ban" and g.targets == []
    assert "40/2024/TT-NHNN#than/dieu_52#khoan_2" in g.ngoai_tru


def test_vien_dan_mo_ho_khong_sinh_khoa_sai(index):
    """TT40 Điều 52 khoản 3: "khoản 2 Điều 17, Điều 18, Điều 19…".

    Cách đọc đúng là khoản 2 CHỈ của Điều 17. Văn phạm hiện tại không phân biệt
    được ⇒ phải bỏ, không được phát ra `dieu_18#khoan_2`.
    """
    dieu, k = _khoan(index, "TT40-2024-dieu52.txt", "3")
    g = classify_khoan(k, dieu).gates[0]
    assert g.suy_ra_duoc is False
    assert not any("dieu_18#khoan_2" in t for t in g.targets)
    assert g.ghi_chu


def test_van_ban_khac_thi_khong_giai_vien_dan(index):
    """TT40 Điều 52 khoản 6 bãi bỏ TT39/TT20 — "Điều 2" ở đó thuộc văn bản KHÁC."""
    dieu, k = _khoan(index, "TT40-2024-dieu52.txt", "6")
    g = classify_khoan(k, dieu).gates[0]
    assert g.suy_ra_duoc is False
    assert g.targets == [] and g.ngoai_tru == []


def test_cong_muc_dieu_gop_thanh_cong_chu_the(index):
    """Cả Điều "Đối tượng áp dụng" gộp lại VẪN là cổng — chỉ từng khoản mới là premise."""
    dieu = _dieu(index, "ND52-2024-dieu2.txt")
    v = classify_dieu_unit(dieu)
    assert v.type == "meta_cu"
    assert v.gates[0].kind == "chu_the" and v.gates[0].pham_vi == "van_ban"


# --- Bí danh + sổ đăng ký premise ------------------------------------------


@pytest.mark.parametrize(
    "cau,mong_doi",
    [
        ("… (sau đây gọi là khách hàng).", "khách hàng"),
        ("… (sau đây viết tắt là TCPHT).", "TCPHT"),
        ("… (sau đây gọi chung là thẻ).", "thẻ"),
        ("… (gọi tắt là Giấy phép).", "Giấy phép"),
        ("Không có bí danh nào ở đây.", None),
    ],
)
def test_find_alias(cau, mong_doi):
    got = find_alias(cau)
    assert (got[0] if got else None) == mong_doi


def test_premise_record_giu_nguyen_khoi_va_span(index):
    dieu = _dieu(index, "ND52-2024-dieu2.txt")
    k4 = next(k for k in khoan_de_trich(dieu) if k.so_hien_thi == "4")
    v = classify_khoan(k4, dieu)
    pr = build_premise_record(k4, dieu, v, gop_vao_gate=dieu.id)
    assert pr.type == "premise"
    assert pr.premise_kind == "vai_tro"
    a, b = pr.char_span
    assert dieu.text[a:b] == pr.raw_text  # khối văn bản giữ nguyên, không diễn giải
    assert pr.alias == "khách hàng"
    assert pr.gop_vao_gate == dieu.id


def test_premise_record_pham_vi_dieu_khong_chia_khoan(index):
    """ND52 Điều 1 không chẻ khoản — vẫn phải ra được một bản ghi registry."""
    dieu = _dieu(index, "ND52-2024-dieu1.txt")
    k = khoan_de_trich(dieu)[0]
    v = classify_khoan(k, dieu)
    assert v.type == "premise" and v.premise_kind == "pham_vi"
    assert build_premise_record(k, dieu, v).id == k.id


# --- Hợp đồng của `detect_gate` -------------------------------------------


def test_actor_cu_thuong_khong_co_cong(index):
    dieu, k = _khoan(index, "ND52-2024-dieu23.txt", "1")
    assert detect_gate(k.text, UnitCtx(dieu_id=dieu.id, dieu_so_hien_thi="23")) is None
