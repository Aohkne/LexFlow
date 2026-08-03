"""`source_diem` suy từ parser, không lấy lời khai của LLM — offline, không gọi Gemini.

Vì sao có file này: nhóm cờ đông nhất trong `pred.jsonl` là **19 cờ "điểm không tồn tại"**
trên **13/49 bản ghi**, và cả 13 đều có `khoan.diem == []` — mô hình dùng `a`/`b`/`c` làm
số thứ tự cho các ý trong một đoạn liền. Nhưng parser ĐÃ biết Khoản chẻ những Điểm nào và
đã dán nhãn đó lên từng đơn vị của menu (`Unit.source_diem`), nên cờ kia hỏi người một câu
máy đã có đáp án. Sửa gốc: suy `source_diem` từ chính các đơn vị mô hình chọn.

Xem `docs/ONTOLOGY-POC.md` §14d.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ontology.extractor import KHONG_RO_DIEM, _suy_diem, build_cu
from app.ontology.parser import parse_dieu
from app.ontology.segmenter import segment

_DIR = Path("data/fixtures")


@pytest.fixture(scope="module")
def index():
    return json.loads((_DIR / "_index.json").read_text(encoding="utf-8"))


def _dieu(index, name):
    p = _DIR / name
    if not p.exists():
        pytest.skip(f"chưa sinh fixture {name}")
    return parse_dieu(p.read_text(encoding="utf-8"), index[name])


def _khoan(dieu, so: str):
    return next(k for k in dieu.khoan if k.so_hien_thi == so)


# --- 1. Ba nhánh của phép suy ------------------------------------------------


def test_don_vi_thuoc_mot_diem_thi_lay_diem_do(index):
    dieu = _dieu(index, "ND52-2024-dieu22.txt")
    khoan = _khoan(dieu, "2")
    units = segment(dieu, khoan)
    u = next(x for x in units if x.source_diem == "g")
    # Lời khai cố ý SAI để chứng minh nó không được dùng.
    src, warn = _suy_diem({"source_diem": "a", "units": [u.uid]}, units, khoan)
    assert src == "g" and warn == []


def test_khoan_khong_che_diem_thi_im_lang(index):
    """Ca chiếm trọn 13/13 bản ghi hỏng: parser chắc chắn ⇒ không có gì bàn giao cho người."""
    dieu = _dieu(index, "TT18-2024-dieu9.txt")
    khoan = _khoan(dieu, "1")
    assert not khoan.diem, "fixture đổi rồi — ca này cần Khoản KHÔNG chẻ Điểm"
    units = segment(dieu, khoan)
    u = next(x for x in units if x.uid > 0)
    src, warn = _suy_diem({"source_diem": "b", "units": [u.uid]}, units, khoan)
    assert src is None
    assert warn == [], "Khoản không chẻ Điểm thì lời khai chỉ là số thứ tự — đừng hỏi người"


def test_khoan_co_che_diem_ma_neo_ra_ngoai_thi_bao(index):
    """Ngược lại: có hai đáp án khả dĩ ⇒ máy KHÔNG được tự chọn, phải nói ra."""
    dieu = _dieu(index, "ND52-2024-dieu22.txt")
    khoan = _khoan(dieu, "2")
    assert khoan.diem
    units = segment(dieu, khoan)
    chapeau = next(x for x in units if x.uid > 0 and x.source_diem is None)
    src, warn = _suy_diem({"source_diem": "b", "units": [chapeau.uid]}, units, khoan)
    assert src is None
    assert len(warn) == 1 and "diem_khai_lech" in warn[0]


def test_vat_qua_nhieu_diem_thi_khong_doan(index):
    dieu = _dieu(index, "ND52-2024-dieu22.txt")
    khoan = _khoan(dieu, "2")
    units = segment(dieu, khoan)
    a = next(x for x in units if x.source_diem == "a")
    b = next(x for x in units if x.source_diem == "b")
    src, warn = _suy_diem({"source_diem": "a", "units": [a.uid, b.uid]}, units, khoan)
    assert src is None, "đoán bừa một điểm sẽ giấu mất chuyện neo quá rộng"
    assert len(warn) == 1 and "diem_vat_nhieu_diem" in warn[0]


def test_uid_khong_ton_tai_khong_lam_vo(index):
    """Uid rác đã có đường xử lý riêng (`mất provenance`); phép suy không được nổ trước đó."""
    dieu = _dieu(index, "ND52-2024-dieu22.txt")
    khoan = _khoan(dieu, "2")
    units = segment(dieu, khoan)
    assert _suy_diem({"source_diem": "a", "units": [9999]}, units, khoan)[0] is None


# --- 2. Bất biến trên toàn corpus --------------------------------------------


def test_moi_source_diem_deu_la_diem_co_that(index):
    """Bất biến mạnh nhất: giá trị chỉ sinh từ nhãn parser ⇒ KHÔNG thể là điểm bịa.

    Trước khi sửa, 19/102 điều kiện trong `pred.jsonl` mang điểm không tồn tại.
    """
    n = 0
    for name, so_hieu in json.loads((_DIR / "_index.json").read_text(encoding="utf-8")).items():
        p = _DIR / name
        if not p.exists():
            continue
        dieu = parse_dieu(p.read_text(encoding="utf-8"), so_hieu)
        for khoan in dieu.khoan:
            units = segment(dieu, khoan)
            co_that = {d.so_hien_thi for d in khoan.diem}
            for u in units:
                # Khai bừa một chữ cái cho MỌI đơn vị: kết quả vẫn phải nằm trong tập thật.
                src, _ = _suy_diem({"source_diem": "z", "units": [u.uid]}, units, khoan)
                assert src is None or src in co_that, f"{name} khoản {khoan.so_hien_thi}: {src!r}"
                n += 1
    assert n > 200, f"chỉ quét được {n} đơn vị — nghi fixture hỏng"


def test_di_qua_build_cu_thi_loi_khai_cung_khong_thang(index):
    dieu = _dieu(index, "TT18-2024-dieu13.txt")
    khoan = _khoan(dieu, "4")
    units = segment(dieu, khoan)
    uid = max(u.uid for u in units)
    cu = build_cu(
        {
            "subject": {"units": [uid]}, "action": {"units": [uid]}, "logic": "all",
            "conditions": [{"source_diem": "a", "units": [uid],
                            "object_label": "", "constraint_label": ""}],
        },
        khoan, dieu, units, role="actor_cu",
    )
    assert cu.conditions[0].source_diem is None
    assert not any("điểm không tồn tại" in w for w in cu.warnings)


# --- 3. Nhãn địa chỉ phải tra ngược được -------------------------------------


def test_hang_so_nhan_khong_lech_giua_hai_ben():
    """`triage.py` giữ bản sao vì cố ý chạy được ở dạng đường dẫn trần — canh nó không trôi."""
    from eval.ontology.triage import KHONG_RO_DIEM as ben_eval

    assert ben_eval == KHONG_RO_DIEM


def test_dia_chi_khong_ro_diem_tra_nguoc_ra_dung_dieu_kien():
    """Cảnh báo mang nhãn "(không rõ điểm)#2" phải mở ra đúng điều kiện thứ hai.

    Không ánh xạ ngược thì 19/102 điều kiện hiện cảnh báo mà KHÔNG kèm chữ của luật —
    đúng loại lỗi im lặng mà trang duyệt sinh ra để chặn.
    """
    from eval.ontology.flag_ui import _locate
    from eval.ontology.triage import _field_text

    row = {
        "conditions": [
            {"source_diem": None, "text": "vế một", "object_label": "L1",
             "grounding": {"char_span": [0, 6]}},
            {"source_diem": None, "text": "vế hai", "object_label": "L2",
             "grounding": {"char_span": [7, 13]}},
        ]
    }
    assert _field_text(row, f"điều kiện {KHONG_RO_DIEM}#2") == (["vế hai"], False)
    loc = _locate(row, f"điều kiện {KHONG_RO_DIEM}#2")
    assert loc["span"] == [7, 13] and loc["label"] == "L2"
    # Không có số thứ tự ⇒ mơ hồ ⇒ trả candidates chứ KHÔNG lặng lẽ lấy cái đầu.
    assert _locate(row, f"điều kiện {KHONG_RO_DIEM}")["candidates"] == ["vế một", "vế hai"]
