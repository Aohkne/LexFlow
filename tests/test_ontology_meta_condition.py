"""Θ có cấu trúc cho meta-CU cổng thời gian — offline, không gọi Gemini.

Chốt câu hỏi mở của `docs/ONTOLOGY-CLASSIFY.md` §6 mục 7: giữ schema 4-tuple, cho ô
điều kiện mang **object có cấu trúc** thay vì tách meta-CU ra schema riêng.

Hai nhóm test, hai mối lo khác nhau:

1. **`detect_dieu_kien_cong`** — mốc ngày có được tách đúng và neo đúng không. Toàn bộ
   tầng này là REGEX, không có LLM, nên test được tất định.
2. **`conditions_khong_ap_dung` + `build_cu`** — ô `conditions` có bị lấp bừa nữa
   không. Dữ liệu đầu vào là **chính output mô hình đã quan sát được** trong
   `eval/ontology/pred.jsonl`, không phải input giả định.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ontology.classify import classify_khoan, detect_dieu_kien_cong
from app.ontology.extractor import (
    build_cu,
    build_prompt,
    conditions_khong_ap_dung,
    grounding_report,
)
from app.ontology.parser import parse_dieu
from app.ontology.schema import DieuKienCong, Gate
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


# --- 1. Tách mốc ngày: tất định, neo đúng, không lan --------------------------


@pytest.mark.parametrize(
    ("khoan_so", "ngay"),
    [("1", "2024-07-17"), ("2", "2024-08-15"), ("3", "2024-10-01"),
     ("4", "2025-01-01"), ("5", "2025-07-01")],
)
def test_moc_ngay_cua_tt40_dieu52(index, khoan_so, ngay):
    dieu = _dieu(index, "TT40-2024-dieu52.txt")
    v = classify_khoan(_khoan(dieu, khoan_so), dieu)
    assert v.type == "meta_cu"
    d = v.dieu_kien_cong
    assert d is not None and d.ngay == ngay and d.moc == "bat_dau"


def test_span_round_trip_ve_dieu_text(index):
    """Span phải quy về `dieu.text` — quên rebase `+ khoan.start` là lệch im lặng."""
    dieu = _dieu(index, "TT40-2024-dieu52.txt")
    for so in ("1", "2", "3", "4", "5", "6"):
        d = classify_khoan(_khoan(dieu, so), dieu).dieu_kien_cong
        a, b = d.char_span
        assert dieu.text[a:b] == d.raw_text, f"khoản {so}"


def test_span_khong_lan_sang_nua_cau_pham_vi(index):
    """Đúng cái lỗi đang có: mô hình neo vào nửa câu phạm vi rồi gắn nhãn bằng nửa
    câu ngày. Span do regex tách chỉ chứa mệnh đề hiệu lực, không dính danh sách."""
    dieu = _dieu(index, "TT40-2024-dieu52.txt")
    d = classify_khoan(_khoan(dieu, "2"), dieu).dieu_kien_cong
    a, b = d.char_span
    assert "Điều 11" not in dieu.text[a:b]
    assert "Quy định tại" not in dieu.text[a:b]
    assert "15 tháng 8 năm 2024" in dieu.text[a:b]


def test_den_het_ngay_la_moc_ket_thuc():
    """Bẫy đảo ngữ nghĩa: TT40 Đ52 k6 điểm a viết "…ĐẾN HẾT ngày 14 tháng 8 năm 2024".

    Nhét ngày này vào một ô đọc ra là "ngày bắt đầu có hiệu lực" là lật ngược hiệu
    lực — cùng loại lỗi mà `Gate.phu_dinh` đã sinh ra để chặn.
    """
    d = detect_dieu_kien_cong("có hiệu lực thi hành đến hết ngày 14 tháng 8 năm 2024")
    assert d.moc == "ket_thuc" and d.ngay == "2024-08-14"

    d2 = detect_dieu_kien_cong("Thông tư này có hiệu lực thi hành từ ngày 15 tháng 8 năm 2024")
    assert d2.moc == "bat_dau" and d2.ngay == "2024-08-15"


def test_het_hieu_luc_cung_la_moc_ket_thuc(index):
    """TT40 Đ52 k6 chapeau: "…hết hiệu lực kể từ ngày Thông tư này có hiệu lực"."""
    dieu = _dieu(index, "TT40-2024-dieu52.txt")
    d = classify_khoan(_khoan(dieu, "6"), dieu).dieu_kien_cong
    assert d.moc == "ket_thuc"
    # KHÔNG có ngày tuyệt đối — mốc nêu bằng viện dẫn tương đối. Đây là "không có
    # ngày", khác hẳn "có ngày mà đọc hỏng", nên phải nói rõ chứ không im lặng None.
    assert d.ngay is None
    assert "tương đối" in d.ghi_chu


def test_ngay_khong_hop_le_thi_noi_khac_di():
    d = detect_dieu_kien_cong("có hiệu lực thi hành từ ngày 31 tháng 2 năm 2024")
    assert d.ngay is None
    assert "không hợp lệ" in d.ghi_chu and "tương đối" not in d.ghi_chu


def test_khong_overload_suy_ra_duoc(index):
    """Hai cờ độc lập: K3 có viện dẫn phân phối không giải được (`suy_ra_duoc=False`)
    trong khi mốc ngày parse hoàn hảo. Gộp chung một cờ là mất khả năng biết cái nào
    hỏng."""
    dieu = _dieu(index, "TT40-2024-dieu52.txt")
    v = classify_khoan(_khoan(dieu, "3"), dieu)
    assert v.gates[0].suy_ra_duoc is False
    assert v.dieu_kien_cong.ngay == "2024-10-01"


def test_khong_gan_moc_ngay_cho_cong_chu_the(index):
    """TT40 Đ26 k2 là cổng chủ thể — không có mốc thời gian nào để gắn."""
    dieu = _dieu(index, "TT40-2024-dieu26.txt")
    v = classify_khoan(_khoan(dieu, "2"), dieu)
    assert v.gates[0].kind == "chu_the"
    assert v.dieu_kien_cong is None


def test_dieu_khoan_bai_bo_khong_co_moc_rieng(index):
    """ND52 Đ37 k2 "thay thế cho Nghị định…" vẫn là cổng thời gian, nhưng mốc của nó
    là mốc của chính văn bản, không nằm trong đơn vị ⇒ không được bịa ra một ngày."""
    dieu = _dieu(index, "ND52-2024-dieu37.txt")
    v = classify_khoan(_khoan(dieu, "2"), dieu)
    assert v.gates[0].kind == "thoi_gian"
    assert v.dieu_kien_cong is None


# --- 2. `conditions` rỗng khi mệnh đề hiệu lực không chẻ Điểm -----------------


def _gate_tg():
    return Gate(kind="thoi_gian", pham_vi="van_ban", suy_ra_duoc=True)


def _llm(units, conditions):
    uid = next(u.uid for u in units if u.uid > 0)
    return {"subject": {"units": []}, "action": {"units": [uid]},
            "logic": "all", "conditions": conditions}


def test_rule_doi_ca_hai_ve(index):
    """Vế "Khoản không chẻ Điểm" là BẮT BUỘC, không chỉ là cổng thời gian."""
    dieu = _dieu(index, "TT40-2024-dieu52.txt")
    for so in ("3", "4", "5"):
        assert conditions_khong_ap_dung("meta_cu", [_gate_tg()], _khoan(dieu, so))
    # k6 cũng là cổng thời gian nhưng CÓ điểm a/b mang mốc hết hiệu lực riêng cho
    # từng quy định của TT39/2014 — xoá chúng là mất thông tin thật.
    k6 = _khoan(dieu, "6")
    assert k6.diem
    assert not conditions_khong_ap_dung("meta_cu", [_gate_tg()], k6)


def test_rule_khong_bat_cho_actor_cu_va_cong_chu_the(index):
    dieu = _dieu(index, "TT40-2024-dieu52.txt")
    k3 = _khoan(dieu, "3")
    assert not conditions_khong_ap_dung("actor_cu", [_gate_tg()], k3)
    assert not conditions_khong_ap_dung(
        "meta_cu", [Gate(kind="chu_the", pham_vi="muc")], k3
    )
    # meta-CU chưa xác định được cổng: không có căn cứ nào để miễn.
    assert not conditions_khong_ap_dung("meta_cu", [], k3)


# Output THẬT của mô hình cho TT40 Đ52 khoản 3, chép từ eval/ontology/pred.jsonl.
# Nó neo vào nửa câu phạm vi rồi gắn nhãn bằng nửa câu ngày — modality guard bắt
# thành lỗi cứng "bịa số không có trong nguồn: 1, 10, 2024".
_K3_THAT = [{
    "source_diem": "a",
    "units": [1],
    "object_label": "Quy định tại khoản 2 Điều 17, Điều 18, Điều 19, Điều 20, "
                    "Điều 21, Điều 22, Điều 23, Điều 28 (trừ quy định tại khoản 3) "
                    "Thông tư này",
    "constraint_label": "có hiệu lực thi hành từ ngày 01 tháng 10 năm 2024",
}]


def test_bo_dieu_kien_ma_va_het_loi_cung(index):
    dieu = _dieu(index, "TT40-2024-dieu52.txt")
    k3 = _khoan(dieu, "3")
    units = segment(dieu, k3)
    v = classify_khoan(k3, dieu)
    cu = build_cu(_llm(units, _K3_THAT), k3, dieu, units,
                  role="meta_cu", gates=v.gates, dieu_kien_cong=v.dieu_kien_cong)
    assert cu.conditions == []
    assert cu.ok, cu.errors
    assert cu.logic == "unknown"
    # Mốc ngày KHÔNG mất theo: nó đã được tách tất định ở bước phân loại.
    assert cu.dieu_kien_cong.ngay == "2024-10-01"


def test_bo_thi_phai_noi_da_bo_cai_gi(index):
    """Bỏ trong im lặng thì nhìn bản ghi lại tưởng mô hình đã trả rỗng ngay từ đầu."""
    dieu = _dieu(index, "TT40-2024-dieu52.txt")
    k3 = _khoan(dieu, "3")
    units = segment(dieu, k3)
    cu = build_cu(_llm(units, _K3_THAT), k3, dieu, units,
                  role="meta_cu", gates=[_gate_tg()])
    w = " ".join(cu.warnings)
    assert "bỏ 1 'điều kiện'" in w
    assert "01 tháng 10 năm 2024" in w


def test_khoan_co_diem_thi_giu_nguyen_dieu_kien(index):
    """Rule không được bắn nhầm sang k6 — điểm a/b ở đó là điều kiện thật."""
    dieu = _dieu(index, "TT40-2024-dieu52.txt")
    k6 = _khoan(dieu, "6")
    units = segment(dieu, k6)
    uid_a = next(u.uid for u in units if u.source_diem == "a")
    cu = build_cu(_llm(units, [{"source_diem": "a", "units": [uid_a]}]),
                  k6, dieu, units, role="meta_cu", gates=[_gate_tg()])
    assert len(cu.conditions) == 1
    assert cu.conditions[0].source_diem == "a"


def test_prompt_bao_mo_hinh_tra_conditions_rong(index):
    dieu = _dieu(index, "TT40-2024-dieu52.txt")
    k3, k6 = _khoan(dieu, "3"), _khoan(dieu, "6")
    p3 = build_prompt(k3, dieu, segment(dieu, k3), role="meta_cu", gates=[_gate_tg()])
    p6 = build_prompt(k6, dieu, segment(dieu, k6), role="meta_cu", gates=[_gate_tg()])
    assert '"conditions": []' in p3
    assert '"conditions": []' not in p6


# --- 3. Chỗ hổng và ranh giới phải hiện ra ------------------------------------


def test_cong_thoi_gian_khong_co_moc_thi_canh_bao(index):
    dieu = _dieu(index, "ND52-2024-dieu37.txt")
    k = dieu.khoan[1]
    units = segment(dieu, k)
    cu = build_cu(_llm(units, []), k, dieu, units, role="meta_cu", gates=[_gate_tg()])
    assert any("chưa tách được mốc ngày" in w for w in cu.warnings)


def test_actor_cu_khong_duoc_mang_dieu_kien_cong(index):
    """Trước đây bị bỏ âm thầm kèm một cảnh báo; nay `ActorCU` KHÔNG CÓ ô đó.

    Truyền vào là sai ở chỗ gọi, không phải dữ liệu bẩn cần dọn — nên nổ ngay.
    """
    dieu = _dieu(index, "ND52-2024-dieu37.txt")
    k = dieu.khoan[0]
    units = segment(dieu, k)
    with pytest.raises(ValueError, match="không được mang điều kiện cổng"):
        build_cu(_llm(units, []), k, dieu, units,
                 dieu_kien_cong=DieuKienCong(kind="thoi_gian", ngay="2024-07-01"))


def test_bao_cao_neo_hien_moc_la_tat_dinh(index):
    """Span này do regex của TA tính — không cùng thang đo exact/unit/invalid."""
    dieu = _dieu(index, "TT40-2024-dieu52.txt")
    k3 = _khoan(dieu, "3")
    units = segment(dieu, k3)
    v = classify_khoan(k3, dieu)
    cu = build_cu(_llm(units, []), k3, dieu, units,
                  role="meta_cu", gates=v.gates, dieu_kien_cong=v.dieu_kien_cong)
    row = next(r for r in grounding_report(cu) if r["field"] == "dieu_kien_cong")
    assert row["status"] == "tat_dinh"
    assert row["char_span"] == tuple(v.dieu_kien_cong.char_span)


def test_trang_kiem_hien_moc_va_o_trong_co_chu_y(index):
    from app.ontology.report import render

    dieu = _dieu(index, "TT40-2024-dieu52.txt")
    k3 = _khoan(dieu, "3")
    units = segment(dieu, k3)
    v = classify_khoan(k3, dieu)
    html = render(
        build_cu(_llm(units, _K3_THAT), k3, dieu, units,
                 role="meta_cu", gates=v.gates, dieu_kien_cong=v.dieu_kien_cong),
        dieu,
    )
    assert "<td>dieu_kien_cong</td>" in html
    assert "2024-10-01" in html
    # Ô conditions rỗng phải THẤY ĐƯỢC, không được biến mất khỏi bảng.
    assert "<td>conditions</td>" in html
