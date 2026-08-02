"""Hợp đồng của modality guard khi `quote` thu hẹp span — offline, không gọi Gemini.

Bối cảnh đo được, KHÔNG phải giả định. Quét toàn bộ 296 nhãn không rỗng trong
`eval/ontology/pred.jsonl` tìm từ mang nghĩa vụ/cấm đoán ("phải", "phải được", "cần",
"bắt buộc", "có nghĩa vụ", "không được", "cấm") có trong NHÃN mà không có trong SPAN
đã neo: đúng **1** lần trên 296 — TT17 Điều 16 khoản 2 điểm c. Và cụm đó **có** trong
văn bản gốc, nguyên văn, ngay trong chính điểm c mà mô hình đã chọn:

    "Các thông tin, dữ liệu PHẢI ĐƯỢC lưu trữ an toàn, bảo mật, ĐƯỢC sao lưu dự
     phòng, đảm bảo tính đầy đủ, toàn vẹn của dữ liệu…"           (đơn vị [13])

Mô hình chọn units [6…14] = TRỌN điểm c, rồi dùng `quote` thu hẹp span về câu đầu.
Guard so nhãn với span đã hẹp ⇒ kết luận "bịa nhóm nghia_vu". Đó là **báo nhầm**:
không có chuyện bịa, chỉ có `quote` thu hẹp sai chỗ. Vì vậy KHÔNG dựng thêm danh sách
từ khoá deontic song song — phép đo nói tần suất bịa thật trên corpus này là 0/296, và
một danh sách từ khoá thứ hai sẽ trôi lệch khỏi `MODALITY` mà không bắt thêm được gì.

Ranh giới phải giữ: TT40 Điều 52 khoản 6 nhìn thì giống nhưng KHÁC hẳn — ở đó bao lồi
CŨNG không chứa cái mô hình viết (nó chỉ chọn đúng 1 trong 5 đơn vị của điểm a). Đó là
trích thiếu đơn vị thật ⇒ phải giữ nguyên lỗi cứng.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ontology.extractor import build_cu
from app.ontology.modality import modality_delta, relax_absence
from app.ontology.parser import parse_dieu
from app.ontology.schema import Gate
from app.ontology.segmenter import hull, segment

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


# --- 1. `relax_absence`: nới cái gì, cố ý KHÔNG nới cái gì --------------------


def test_bia_that_van_la_bia_khi_bang_chung_khong_he_co():
    """Bằng chứng rộng ra mà vẫn không có dấu hiệu đó ⇒ không được hạ mức."""
    d = modality_delta("tổ chức phải nộp báo cáo", "tổ chức nộp báo cáo")
    assert d.invented_groups == ["nghia_vu"]
    out, notes = relax_absence(d, "tổ chức phải nộp báo cáo", "tổ chức nộp báo cáo hằng năm")
    assert out.hard_error and out.invented_groups == ["nghia_vu"]
    assert notes == []


def test_ha_muc_khi_cum_nam_nguyen_van_trong_bang_chung():
    claim = "phải được lưu trữ an toàn"
    span = "Lưu trữ, bảo quản đầy đủ đối với các tài liệu"
    evidence = span + " Các thông tin, dữ liệu phải được lưu trữ an toàn, bảo mật"
    d = modality_delta(claim, span)
    assert d.hard_error and d.invented_groups == ["nghia_vu"]
    out, notes = relax_absence(d, claim, evidence)
    assert not out.hard_error and out.invented_groups == []
    assert any("thu hẹp sai chỗ" in n for n in notes)


def test_ha_muc_ca_so_bi_bao_bia():
    claim = "trong thời hạn 30 ngày"
    span = "báo cáo cho Ngân hàng Nhà nước"
    d = modality_delta(claim, span)
    assert d.added_numbers == ["30"]
    out, notes = relax_absence(d, claim, span + " trong thời hạn 30 ngày làm việc")
    assert out.added_numbers == [] and not out.hard_error
    assert any("bịa số 30" in n for n in notes)


def test_khong_noi_condition_to_obligation():
    """Cố ý KHÔNG nới cáo buộc BIẾN ĐỔI — nó NGƯỢC ĐƠN ĐIỆU theo độ rộng nguồn.

    Nguồn càng rộng thì "mất dấu hiệu điều kiện" càng dễ đúng một cách vô nghĩa: một
    Điểm dài luôn có 'khi/nếu' ở mệnh đề mà bản tóm tắt không nhắc. Nới cả gói là đổi
    một báo nhầm này lấy một báo nhầm khác. Đây là case ĐO ĐƯỢC ở TT17 Điều 16 khoản 2
    điểm c: nới ra bao lồi thì hết `invented_groups` nhưng lại nổ `condition_to_obligation`.
    """
    claim = "tổ chức phải nộp báo cáo"
    span = "khi nộp báo cáo"
    d = modality_delta(claim, span)
    assert d.condition_to_obligation and d.hard_error
    out, _ = relax_absence(d, claim, span + " thì phải kèm tài liệu")
    # `invented_groups` hết vì bằng chứng có "phải", nhưng cáo buộc BIẾN ĐỔI vẫn nguyên.
    assert out.invented_groups == []
    assert out.condition_to_obligation and out.hard_error


def test_khong_co_cao_buoc_vang_mat_thi_khong_lam_gi():
    d = modality_delta("nộp báo cáo", "nộp báo cáo")
    out, notes = relax_absence(d, "nộp báo cáo", "nộp báo cáo đầy đủ")
    assert notes == [] and out == d


# --- 2. Case THẬT: TT17 Điều 16 khoản 2 --------------------------------------

# Chép NGUYÊN VĂN từ `eval/ontology/pred.jsonl` (bản sinh ngày 2026-08-02, trước khi
# sửa guard) — tái hiện lỗi THẬT, không phải input giả định. `units` [6…14] là trọn
# điểm c; `quote` thu hẹp về đúng câu đầu của điểm đó.
_TT17_K2 = {
    "logic": "all",
    "subject": {"units": [1], "quote": "Ngân hàng, chi nhánh ngân hàng nước ngoài",
                "label": "Ngân hàng, chi nhánh ngân hàng nước ngoài", "source": "explicit"},
    "action": {
        "units": [1],
        "quote": "tự quyết định biện pháp, hình thức, công nghệ phục vụ việc mở tài "
                 "khoản thanh toán bằng phương tiện điện tử, tự chịu rủi ro phát sinh "
                 "(nếu có) và phải đáp ứng tối thiểu các yêu cầu sau",
        "label": "tự quyết định biện pháp, hình thức, công nghệ mở tài khoản thanh toán "
                 "điện tử, chịu rủi ro và đáp ứng yêu cầu",
    },
    "conditions": [
        {
            "source_diem": "c",
            "units": [6, 7, 8, 9, 10, 11, 12, 13, 14],
            "quote": "Lưu trữ, bảo quản đầy đủ, chi tiết đối với các tài liệu, thông "
                     "tin, dữ liệu nhận biết khách hàng trong quá trình mở, sử dụng "
                     "tài khoản thanh toán bằng phương tiện điện tử",
            "object_label": "Các tài liệu, thông tin, dữ liệu nhận biết khách hàng "
                            "trong quá trình mở, sử dụng tài khoản thanh toán điện tử",
            "constraint_label": "phải được lưu trữ an toàn, bảo mật, sao lưu dự phòng, "
                                "đảm bảo tính đầy đủ, toàn vẹn, thực hiện theo quy định "
                                "phòng, chống rửa tiền và giao dịch điện tử",
        }
    ],
}


@pytest.fixture(scope="module")
def tt17_k2(index):
    dieu = _dieu(index, "TT17-2024-dieu16.txt")
    khoan = _khoan(dieu, "2")
    return dieu, khoan, segment(dieu, khoan)


def test_cum_phai_duoc_co_that_trong_bang_chung_mo_hinh_da_chon(tt17_k2):
    """Nền của cả file: chứng minh KHÔNG có chuyện bịa, trước khi nói về guard."""
    dieu, _, units = tt17_k2
    span = hull(units, [6, 7, 8, 9, 10, 11, 12, 13, 14])
    evidence = dieu.text[span[0] : span[1]]
    assert "phải được lưu trữ an toàn, bảo mật" in evidence
    # …và KHÔNG có trong lát cắt mà `quote` thu hẹp về — đây đúng là chỗ guard trượt.
    assert "phải được" not in _TT17_K2["conditions"][0]["quote"]


def test_tt17_k2_het_loi_cung_va_neu_dich_danh_ly_do(tt17_k2):
    dieu, khoan, units = tt17_k2
    cu = build_cu(_TT17_K2, khoan, dieu, units, role="actor_cu")
    assert cu.errors == [], cu.errors
    assert cu.ok
    # Hạ mức KHÔNG được im lặng: phải nêu đích danh cụm bị hạ và hệ quả cho `text`.
    assert any("hạ mức 'bịa ràng buộc nhóm nghia_vu'" in w for w in cu.warnings)
    assert any("thu hẹp sai chỗ" in w for w in cu.warnings)


def test_tt17_k2_text_van_khong_chua_doan_nhan_mo_ta(tt17_k2):
    """Hạ mức KHÔNG phải là "đã ổn": span vẫn hẹp hơn cái nhãn đang nói tới.

    Đây chính là điều cảnh báo phải làm cho người duyệt thấy — bỏ cảnh báo đi thì bản
    ghi trông sạch trong khi `text` và `constraint_label` vẫn nói về hai đoạn khác nhau.
    """
    dieu, khoan, units = tt17_k2
    cu = build_cu(_TT17_K2, khoan, dieu, units, role="actor_cu")
    c = next(c for c in cu.conditions if c.source_diem == "c")
    assert "phải được lưu trữ" in c.constraint_label
    assert "phải được lưu trữ" not in c.text


# --- 3. Ranh giới: TT40 Điều 52 khoản 6 KHÔNG được hưởng phép nới -------------

# Lỗi cứng cũ của K6 KHÔNG được chữa bằng cách nới guard — nó được chữa ở tầng tách:
# điểm a từng bị vỡ thành 5 đơn vị nên bao lồi thật sự không chứa các số đó, và guard
# báo đúng. Nay điểm a là MỘT đơn vị (test canh ở `test_ontology_segmenter.py`), mô hình
# neo trọn Điểm và bản ghi sạch. Dict dưới đây chép nguyên văn từ `pred.jsonl` SAU khi
# sửa tầng tách.
_TT40_K6 = {
    "logic": "unknown",
    "subject": {"units": []},
    "action": {"units": [3], "quote": "hết hiệu lực kể từ ngày Thông tư này có hiệu lực thi hành",
               "label": "hết hiệu lực"},
    "conditions": [
        {
            "source_diem": "a",
            "units": [5],
            "quote": "Điều 9a và khoản 4 Điều 11 đã được sửa đổi, bổ sung theo Thông tư "
                     "số 23/2019/TT-NHNN có hiệu lực thi hành đến hết ngày 14 tháng 8 "
                     "năm 2024",
            "object_label": "Điều 9a và khoản 4 Điều 11",
            "constraint_label": "có hiệu lực thi hành đến hết ngày 14 tháng 8 năm 2024",
        }
    ],
}


def test_tt40_k6_sach_nho_sua_TANG_TACH_chu_khong_nho_noi_guard(index):
    dieu = _dieu(index, "TT40-2024-dieu52.txt")
    khoan = _khoan(dieu, "6")
    units = segment(dieu, khoan)
    # Bao lồi nay CHỨA các số mà nhãn nói tới — không còn gì để mà kết tội.
    span = hull(units, [5])
    evidence = dieu.text[span[0] : span[1]]
    for tok in ("Điều 9a", "khoản 4 Điều 11", "23/2019/TT-NHNN"):
        assert tok in evidence, tok
    cu = build_cu(
        _TT40_K6, khoan, dieu, units, role="meta_cu",
        gates=[Gate(kind="thoi_gian", pham_vi="van_ban", suy_ra_duoc=True)],
    )
    assert cu.errors == [], cu.errors
    # Và nó sạch mà KHÔNG cần phép nới — không có cảnh báo hạ mức nào.
    assert not any("hạ mức" in w for w in cu.warnings), cu.warnings


# Case thật CÒN LẠI có lỗi cứng, giữ để canh phép nới không thành lối thoát: mô hình
# đổi *"Điều này"* thành *"Điều 26"*. Suy ra đúng, nhưng số 26 không nằm trong đoạn
# được viện dẫn — và bao lồi cũng không có nó, nên `relax_absence` không cứu.
_TT40_D26_K2 = {
    "logic": "any",
    "subject": {"units": [1], "quote": "Quy định tại khoản 1 Điều này",
                "label": "Quy định tại khoản 1 Điều 26", "source": "explicit"},
    "action": {"units": [1], "quote": "không áp dụng đối với", "label": "không áp dụng"},
    "conditions": [],
}


def test_noi_khong_cuu_duoc_so_khong_co_trong_bao_loi(index):
    """Canh ranh giới: `relax_absence` chỉ bỏ cáo buộc SAI, không bỏ cáo buộc đúng."""
    dieu = _dieu(index, "TT40-2024-dieu26.txt")
    khoan = _khoan(dieu, "2")
    units = segment(dieu, khoan)
    assert "Điều 26" not in dieu.text[hull(units, [1])[0] : hull(units, [1])[1]]
    cu = build_cu(_TT40_D26_K2, khoan, dieu, units, role="actor_cu")
    assert any("bịa số" in e and "26" in e for e in cu.errors), cu.errors
    assert not cu.ok
