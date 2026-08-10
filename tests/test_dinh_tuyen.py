from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.ingestion.pipeline import build_chunks, load_corpus
from app.ontology.dinh_tuyen import _cite_nhieu, dinh_tuyen, khoa_tu_chunk_id
from app.ontology.tac_dong import CanhTacDong

_SH = {"TT40-2024": "40/2024/TT-NHNN", "TT41-2025": "41/2025/TT-NHNN"}
_CANH = [CanhTacDong(nguon="41/2025/TT-NHNN#than/dieu_1#khoan_1",
                     dich="40/2024/TT-NHNN#than/dieu_8#khoan_7",
                     thao_tac="sua_doi", menh_lenh="x", loi_van_moi=(1000, 1500),
                     valid_from="2025-11-05")]


def test_khoa_tu_chunk_id():
    assert khoa_tu_chunk_id("TT40-2024::Điều 8 Khoản 7", _SH) == \
        "40/2024/TT-NHNN#than/dieu_8#khoan_7"
    assert khoa_tu_chunk_id("TT40-2024::Điều 8", _SH) == "40/2024/TT-NHNN#than/dieu_8"
    assert khoa_tu_chunk_id("LA-J::Điều 1", _SH) is None  # doc lạ → không bịa


def test_ba_nhanh():
    v = dinh_tuyen("TT40-2024::Điều 1", None, _CANH, _SH, "2026-08-05")
    assert v.nhanh == "nguyen_ven"
    v = dinh_tuyen("TT40-2024::Điều 8 Khoản 7", None, _CANH, _SH, "2026-08-05")
    assert v.nhanh == "nen_da_sua" and v.khoa_dich == "40/2024/TT-NHNN#than/dieu_8#khoan_7"
    v = dinh_tuyen("TT41-2025::Điều 1 Khoản 1", (900, 1200), _CANH, _SH, "2026-08-05")
    assert v.nhanh == "trich_trong_van_ban_sua"
    assert "TT40-2024" in v.trich_dan_dung_chu and "sửa bởi" in v.trich_dan_dung_chu


# --- Review round 1, important: nhánh 2 "sâu hơn khoá" phải dùng ĐÚNG luật cạnh-chết của
# `phien_ban_hien_hanh` (qua route công khai `phien_ban_hien_hanh(nguon, ...)`), không tự
# lọc valid_from một mình — cạnh A sửa N#Điều5#Khoản2 (sâu hơn chunk "Điều 5") do S1#Điều9
# phát ra; cạnh B bãi bỏ chính S1#Điều9 từ 2026-01-01. Sau ngày đó, cạnh A phải coi là chết.
_SH_SAU_HON = {"ND": "N"}
_CANH_SAU_HON = [
    CanhTacDong(nguon="S1#than/dieu_9", dich="N#than/dieu_5#khoan_2",
                thao_tac="sua_doi", menh_lenh="x", valid_from="2025-01-01"),
    CanhTacDong(nguon="S2#than/dieu_1", dich="S1#than/dieu_9",
                thao_tac="bai_bo", menh_lenh="x", valid_from="2026-01-01"),
]


def test_nhanh_2_sau_hon_khoa_chet_theo_nguon_bi_bai_bo():
    v_sau = dinh_tuyen("ND::Điều 5", None, _CANH_SAU_HON, _SH_SAU_HON, "2026-08-05")
    assert v_sau.nhanh == "nguyen_ven"  # cạnh A chết: nguồn S1#Điều9 đã bị B bãi bỏ

    v_truoc = dinh_tuyen("ND::Điều 5", None, _CANH_SAU_HON, _SH_SAU_HON, "2025-06-01")
    assert v_truoc.nhanh == "nen_da_sua"  # trước ngày B áp, cạnh A còn sống
    assert v_truoc.khoa_dich == "N#than/dieu_5#khoan_2"


# --- Review round 2, F1: nhãn GỘP nhiều khoản không được mint khoá khoản bịa -------------
#
# `"Điều 8 Khoản 1-6"` không phải một khoản thật — không cho ra `#khoan_1-6` mà rơi về khoá
# CẤP ĐIỀU `#than/dieu_8`, để `_canh_deeper_ap_duoc` (nhánh 2, chiều sâu hơn) dò tiếp được
# cạnh sửa/bãi một khoản/điểm BÊN TRONG điều đó. Dùng dữ liệu THẬT (data/corpus.real.json +
# eval/overlay/canh_tac_dong.jsonl) vì hai ca này (điểm a khoản 5 sửa bởi TT41, khoản 4 bãi
# bỏ bởi TT41) chỉ xảy ra ở corpus thật, không đáng dựng lại bằng fixture giả.


def test_nhan_gop_khoan_khong_bia_khoa_khoan():
    assert khoa_tu_chunk_id("TT40-2024::Điều 8 Khoản 1-6", _SH) == "40/2024/TT-NHNN#than/dieu_8"
    assert khoa_tu_chunk_id("TT40-2024::Điều 24 Khoản 1-4", _SH) == "40/2024/TT-NHNN#than/dieu_24"
    # Cắt cửa sổ ký tự vẫn ngoài phạm vi — không bịa khoá cho dạng đó.
    assert khoa_tu_chunk_id("TT40-2024::Điều 8 (phần 2)", _SH) is None


def test_hau_to_phan_biet_ro_ve_khoa_cap_dieu_chu_khong_rot():
    """Nhãn `"… Khoản 2 (2)"` — hậu tố do `_split_khoan` thêm khi một điều chứa nhiều khối
    đánh số lặp lại (điều sửa đổi chép nguyên văn nhiều điều của văn bản bị sửa).

    Hai điều phải đúng cùng lúc. Một, KHÔNG được trả `None`: cả hai regex nhãn đều neo `$`,
    nên nếu không xử hậu tố thì chunk rơi khỏi mọi cạnh tác động **trong im lặng** — đúng loại
    hỏng mà cả `_NHAN_GOP_KHOAN_RE` sinh ra để chặn. Hai, KHÔNG được mint khoá khoản: số `2`
    trong nhãn ấy là khoản của một văn bản KHÁC đang được trích, không định danh khoản nào
    của chính văn bản này. Nên rơi về khoá cấp điều, y như nhãn gộp.
    """
    assert khoa_tu_chunk_id("TT40-2024::Điều 8 Khoản 2 (2)", _SH) == "40/2024/TT-NHNN#than/dieu_8"
    assert khoa_tu_chunk_id("TT40-2024::Điều 8 (2)", _SH) == "40/2024/TT-NHNN#than/dieu_8"
    # `(phần 2)` vẫn là dạng khác và vẫn ngoài phạm vi — hậu tố phân biệt chỉ là `(số)`.
    assert khoa_tu_chunk_id("TT40-2024::Điều 8 (phần 2)", _SH) is None


@pytest.mark.skipif(
    not Path("data/corpus.real.json").exists()
    or not Path("eval/overlay/canh_tac_dong.jsonl").exists(),
    reason="thiếu data/corpus.real.json hoặc eval/overlay/canh_tac_dong.jsonl",
)
def test_nhan_gop_khoan_route_nen_da_sua_tren_corpus_that():
    docs, _rels = load_corpus(Path("data/corpus.real.json"))
    so_hieu_theo_doc = {d.doc_id: d.so_hieu for d in docs}
    canh = [
        CanhTacDong.model_validate_json(line)
        for line in Path("eval/overlay/canh_tac_dong.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    # TT40 Đ8 Khoản 1-6 gộp — chứa khoản 5 (điểm a bị SỬA bởi TT41 Đ1 Khoản 1) — trước khi
    # sửa "\S+" -> "\d+[a-zđ]?" chunk này rớt khỏi mọi cạnh (mint "#khoan_1-6" không tồn tại).
    v = dinh_tuyen("TT40-2024::Điều 8 Khoản 1-6", None, canh, so_hieu_theo_doc, "2026-08-05")
    assert v is not None and v.nhanh == "nen_da_sua"

    # TT40 Đ24 Khoản 1-4 gộp — chứa khoản 4 (bị BÃI BỎ bởi TT41 Đ8) — cùng lỗi, khác điều/thao
    # tác (kèm F3: câu trích phải nói "bãi bỏ", không "sửa bởi").
    v = dinh_tuyen("TT40-2024::Điều 24 Khoản 1-4", None, canh, so_hieu_theo_doc, "2026-08-05")
    assert v is not None and v.nhanh == "nen_da_sua"
    assert v.khoa_dich == "40/2024/TT-NHNN#than/dieu_24#khoan_4"
    assert "đã bị bãi bỏ bởi" in v.trich_dan_dung_chu
    assert "TT41-2025" in v.trich_dan_dung_chu


# --- Review round 2, F3: nhánh 2 chiều-sâu-hơn phải nói ĐÚNG thao tác (bãi bỏ ≠ sửa) -----

_CANH_SAU_HON_BAI_BO = [
    CanhTacDong(nguon="S1#than/dieu_9#khoan_2", dich="N#than/dieu_5#khoan_3#diem_c",
                thao_tac="bai_bo", menh_lenh="x", valid_from="2025-01-01"),
]


def test_nhanh_2_sau_hon_bai_bo_khong_noi_sua_boi():
    v = dinh_tuyen("ND::Điều 5", None, _CANH_SAU_HON_BAI_BO, _SH_SAU_HON, "2026-08-05")
    assert v.nhanh == "nen_da_sua"
    assert "đã bị bãi bỏ bởi" in v.trich_dan_dung_chu
    assert "sửa bởi" not in v.trich_dan_dung_chu


# --- Review round 2, F2: nhánh 3 (trích trong văn bản sửa) phải gate qua hiệu lực hôm nay --
#
# TT41-2025 Đ16 sửa TT40 Đ41 (valid_from 2025-11-05); chính Đ16 đó bị TT22-2026 Đ6 Khoản 2
# bãi bỏ từ 2026-05-19 (luật cạnh-chết). Span vẫn khớp `loi_van_moi` của cạnh TT41 Đ16 →
# TT40 Đ41 dù cạnh đó có còn áp được hay không — chỉ câu trích dẫn phải đổi theo hôm_nay.

_SH_NHANH3 = {"S": "S", "T": "T", "U": "U"}
_CANH_NHANH3 = [
    CanhTacDong(nguon="T#than/dieu_16", dich="S#than/dieu_41",
                thao_tac="sua_doi", menh_lenh="x", loi_van_moi=(100, 200),
                valid_from="2025-11-05"),
    CanhTacDong(nguon="U#than/dieu_6#khoan_2", dich="T#than/dieu_16",
                thao_tac="bai_bo", menh_lenh="y", valid_from="2026-05-19"),
]


def test_nhanh_3_gate_hieu_luc_hom_nay():
    # Trước ngày TT22 bãi Đ16 TT41 áp được: cạnh còn sống, câu trích "sửa bởi" bình thường.
    v_truoc = dinh_tuyen("T::Điều 16", (120, 180), _CANH_NHANH3, _SH_NHANH3, "2026-01-01")
    assert v_truoc.nhanh == "trich_trong_van_ban_sua"
    assert v_truoc.trich_dan_dung_chu == "S Điều 41 (sửa bởi T Điều 16)"

    # Sau ngày đó: cạnh chết theo luật cạnh-chết dù span vẫn khớp — câu trích phải nói rõ
    # đã hết hiệu lực và chỉ ra ai bãi bỏ.
    v_sau = dinh_tuyen("T::Điều 16", (120, 180), _CANH_NHANH3, _SH_NHANH3, "2026-08-05")
    assert v_sau.nhanh == "trich_trong_van_ban_sua"
    assert "không còn áp dụng" in v_sau.trich_dan_dung_chu
    assert "đã bị bãi bỏ bởi U Điều 6 Khoản 2" in v_sau.trich_dan_dung_chu
    assert "từng được sửa bởi T Điều 16" in v_sau.trich_dan_dung_chu


# --- Fix wave 06/08, CRITICAL 1: nhánh 3 phải kể ĐỦ mọi đích chia chung một khối trích ----
#
# Đo trên `data/overlay/lop_phu.json` (178 cạnh): 46 CẶP cạnh cùng văn bản sửa có span giao
# nhau, 17 nhóm (văn bản, lời văn) trùng khít. Lấy cạnh ĐẦU TIÊN rồi nói như sự thật nghĩa là
# giấu phần còn lại — với một sản phẩm pháp lý, trích dẫn tự tin mà thiếu đích là hỏng nặng
# hơn không trích. Hai ca dưới đây dựng lại bằng fixture (không đụng `data/raw/vbpl/`).

# Ca 1 — MỘT khối trích, NĂM đích trong CÙNG văn bản nền: `80/2016/NĐ-CP` span (1071, 2386)
# là lời văn mới của khoản 4, 5, 6, 7 và 8 Điều 4 `101/2012/NĐ-CP`.
_SH_ND80 = {"ND80-2016": "80/2016/NĐ-CP", "ND101-2012": "101/2012/NĐ-CP"}
_CANH_ND80 = [
    CanhTacDong(
        nguon="80/2016/NĐ-CP#than/dieu_1#khoan_1",
        dich=f"101/2012/NĐ-CP#than/dieu_4#khoan_{k}",
        thao_tac="sua_doi", menh_lenh="x", loi_van_moi=(1071, 2386), valid_from="2016-07-01",
    )
    for k in (4, 5, 6, 7, 8)
]

# Ca 2 — MỘT khối trích, hai đích ở HAI văn bản nền khác nhau: `16/2019/NĐ-CP` span
# (7121, 7445) trỏ cả `10/2010/NĐ-CP` Điều 7 lẫn `57/2016/NĐ-CP` Điều 1.
_SH_ND16 = {"ND16-2019": "16/2019/NĐ-CP"}
_CANH_ND16 = [
    CanhTacDong(nguon="16/2019/NĐ-CP#than/dieu_4", dich="10/2010/NĐ-CP#than/dieu_7",
                thao_tac="sua_doi", menh_lenh="x", loi_van_moi=(7121, 7445),
                valid_from="2019-03-20"),
    CanhTacDong(nguon="16/2019/NĐ-CP#than/dieu_4", dich="57/2016/NĐ-CP#than/dieu_1",
                thao_tac="sua_doi", menh_lenh="x", loi_van_moi=(7121, 7445),
                valid_from="2019-03-20"),
]


def test_nhanh_3_ke_du_nam_khoan_cung_van_ban():
    v = dinh_tuyen("ND80-2016::Điều 1 Khoản 1", (1071, 2386), _CANH_ND80, _SH_ND80, "2026-08-05")
    assert v.nhanh == "trich_trong_van_ban_sua"
    assert v.trich_dan_dung_chu == (
        "ND101-2012 Điều 4 Khoản 4, 5, 6, 7, 8 (sửa bởi ND80-2016 Điều 1 Khoản 1)"
    )
    # `khoa_dich` giữ MỘT giá trị chính, chọn tất định (nhỏ nhất theo khoá).
    assert v.khoa_dich == "101/2012/NĐ-CP#than/dieu_4#khoan_4"


def test_nhanh_3_ke_du_hai_van_ban_nen_khac_nhau():
    v = dinh_tuyen("ND16-2019::Điều 4", (7121, 7445), _CANH_ND16, _SH_ND16, "2026-08-05")
    assert v.nhanh == "trich_trong_van_ban_sua"
    assert "ND10-2010 Điều 7" in v.trich_dan_dung_chu
    assert "ND57-2016 Điều 1" in v.trich_dan_dung_chu


def test_nhanh_3_chi_ke_canh_con_ap_duoc():
    """Cạnh chết (nguồn phát đã bị bãi bỏ) không được kể vào danh sách đích còn hiệu lực."""
    canh = [
        *_CANH_ND16,
        CanhTacDong(nguon="99/2026/NĐ-CP#than/dieu_1", dich="16/2019/NĐ-CP#than/dieu_4",
                    thao_tac="bai_bo", menh_lenh="y", valid_from="2026-01-01"),
    ]
    sh = {**_SH_ND16, "ND99-2026": "99/2026/NĐ-CP"}
    v = dinh_tuyen("ND16-2019::Điều 4", (7121, 7445), canh, sh, "2026-08-05")
    assert v.nhanh == "trich_trong_van_ban_sua"
    # Cả hai cạnh đều chết ⇒ vẫn phải kể ĐỦ hai đích, nhưng nói rõ là không còn áp dụng.
    assert "từng được sửa bởi" in v.trich_dan_dung_chu
    assert "đã bị bãi bỏ bởi ND99-2026 Điều 1" in v.trich_dan_dung_chu
    assert "ND10-2010 Điều 7" in v.trich_dan_dung_chu
    assert "ND57-2016 Điều 1" in v.trich_dan_dung_chu


def test_nhanh_3_gop_diem_cung_khoan_theo_thu_tu_bang_chu_cai_viet():
    """Ca thật ND80-2016 Điều 1 Khoản 8 → ND101-2012 Điều 15 Khoản 2 điểm a, b, đ, e, g, h.

    Không lặp `"Khoản 2"` trước mỗi điểm, và `"đ"` phải đứng TRƯỚC `"e"` (bảng chữ cái tiếng
    Việt), không phải sau `"h"` như thứ tự Unicode.
    """
    canh = [
        CanhTacDong(nguon="80/2016/NĐ-CP#than/dieu_1#khoan_8",
                    dich=f"101/2012/NĐ-CP#than/dieu_15#khoan_2#diem_{d}",
                    thao_tac="sua_doi", menh_lenh="x", loi_van_moi=(3806, 5760),
                    valid_from="2016-07-01")
        for d in ("h", "đ", "a", "g", "e", "b")  # cố tình xáo thứ tự đầu vào
    ]
    v = dinh_tuyen("ND80-2016::Điều 1 Khoản 8", (3806, 5760), canh, _SH_ND80, "2026-08-05")
    assert v.trich_dan_dung_chu == (
        "ND101-2012 Điều 15 Khoản 2 Điểm a, b, đ, e, g, h "
        "(sửa bởi ND80-2016 Điều 1 Khoản 8)"
    )


# --- Re-review 07/08: gộp danh sách KHÔNG được thu hẹp phạm vi -----------------------------
#
# Luật của cả `_cite_nhieu`: khi hai cạnh trong cùng nhóm nói về cùng một đơn vị ở hai ĐỘ SÂU
# khác nhau, in ra cấp RỘNG hơn. Nói "Khoản 2" trong khi thật ra chỉ sửa điểm b là phiền; nói
# "Điểm b" trong khi thật ra sửa cả Khoản 2 là SAI PHẠM VI — cùng loại lỗi CRITICAL 1.

_D7 = "15/2024/TT-NHNN#than/dieu_7"


def test_cite_nhieu_khong_thu_hep_ca_khoan_thanh_diem():
    """Cạnh trỏ CẢ khoản đứng chung nhóm với cạnh trỏ điểm ⇒ phải in cấp khoản."""
    assert _cite_nhieu([f"{_D7}#khoan_2", f"{_D7}#khoan_2#diem_b"]) == "TT15-2024 Điều 7 Khoản 2"


def test_cite_nhieu_khong_thu_hep_ca_dieu_thanh_khoan():
    """Cùng luật ở một cấp trên — đã đúng sẵn, giữ làm chốt chặn hồi quy."""
    assert _cite_nhieu([_D7, f"{_D7}#khoan_2"]) == "TT15-2024 Điều 7"
    assert _cite_nhieu([_D7, f"{_D7}#khoan_2#diem_b"]) == "TT15-2024 Điều 7"


def test_cite_nhieu_khoan_khac_van_giu_diem_rieng():
    """Nới rộng chỉ áp cho ĐÚNG khoản có cạnh bare — khoản khác vẫn kể điểm của nó."""
    assert _cite_nhieu(
        [f"{_D7}#khoan_2", f"{_D7}#khoan_2#diem_b", f"{_D7}#khoan_3#diem_a"]
    ) == "TT15-2024 Điều 7 Khoản 2, Khoản 3 Điểm a"


def test_nhanh_3_nhom_span_that_khong_thu_hep_pham_vi():
    """Ca THẬT: `30/2025/TT-NHNN` span (5197, 5346) mang ba cạnh — cả Khoản 2 Điều 7
    `15/2024/TT-NHNN` lẫn hai điểm b, đ bên trong nó. Câu trích phải nói CẢ KHOẢN."""
    canh = [
        CanhTacDong(nguon="30/2025/TT-NHNN#than/dieu_3#khoan_4", dich=dich,
                    thao_tac="sua_doi", menh_lenh="x", loi_van_moi=(5197, 5346),
                    valid_from="2025-07-01")
        for dich in (f"{_D7}#khoan_2", f"{_D7}#khoan_2#diem_b", f"{_D7}#khoan_2#diem_đ")
    ]
    sh = {"TT30-2025": "30/2025/TT-NHNN", "TT15-2024": "15/2024/TT-NHNN"}
    v = dinh_tuyen("TT30-2025::Điều 3 Khoản 4", (5197, 5346), canh, sh, "2026-08-05")
    assert v.trich_dan_dung_chu == (
        "TT15-2024 Điều 7 Khoản 2 (sửa bởi TT30-2025 Điều 3 Khoản 4)"
    )
    assert "Điểm" not in v.trich_dan_dung_chu  # không thu hẹp xuống hai điểm
    # `khoa_dich` (máy đọc) vốn đã đúng — giữ nguyên, câu chữ nay khớp với nó.
    assert v.khoa_dich == f"{_D7}#khoan_2"


def test_cite_nhieu_cat_danh_sach_khong_bao_gio_bo_muc_rong_hon():
    """Mục RỘNG hơn luôn sắp trước theo `_sap` nên không bị trần `_TOI_DA_KE_DICH` cắt mất."""
    khoas = [_D7] + [f"{_D7}#khoan_{i}" for i in range(1, 20)]
    assert _cite_nhieu(khoas).startswith("TT15-2024 Điều 7")
    assert "Khoản" not in _cite_nhieu(khoas).split(" và ")[0]


def test_nhanh_3_danh_sach_dai_thi_cat_va_noi_ro_da_cat():
    """Không bao giờ cắt trong im lặng — cắt thì phải nói là đã cắt."""
    canh = [
        CanhTacDong(nguon="80/2016/NĐ-CP#than/dieu_1#khoan_1",
                    dich=f"101/2012/NĐ-CP#than/dieu_{d}", thao_tac="sua_doi", menh_lenh="x",
                    loi_van_moi=(1071, 2386), valid_from="2016-07-01")
        for d in range(1, 21)
    ]
    v = dinh_tuyen("ND80-2016::Điều 1 Khoản 1", (1071, 2386), canh, _SH_ND80, "2026-08-05")
    assert "đơn vị khác" in v.trich_dan_dung_chu
    assert "đã rút gọn" in v.trich_dan_dung_chu


# --- Bộ câu hỏi gắn nhãn TAY trên dữ liệu THẬT (Task 8) --------------------------------
#
# `eval/overlay/cau_hoi_nhan.jsonl` gắn nhãn bằng cách ĐỌC từng chunk + cạnh liên quan
# (không chạy `dinh_tuyen` trước rồi chép lại — xem `ghi_chu` của từng dòng để thấy lý lẽ
# pháp lý/toạ độ span). `hom_nay` CỐ ĐỊNH "2026-08-05" cho toàn bộ file nhãn — sau
# `valid_from` lớn nhất trong `canh_tac_dong.jsonl` (2026-05-19) nên mọi cạnh đều đã áp.

_CORPUS_REAL = Path("data/corpus.real.json")
_CANH_TAC_DONG_JSONL = Path("eval/overlay/canh_tac_dong.jsonl")
_CAU_HOI_NHAN_JSONL = Path("eval/overlay/cau_hoi_nhan.jsonl")
_HOM_NAY = "2026-08-05"


@pytest.mark.skipif(
    not (_CORPUS_REAL.exists() and _CANH_TAC_DONG_JSONL.exists() and _CAU_HOI_NHAN_JSONL.exists()),
    reason="thiếu data/corpus.real.json, eval/overlay/canh_tac_dong.jsonl hoặc "
    "eval/overlay/cau_hoi_nhan.jsonl",
)
def test_bo_cau_hoi_nhan_khop_100_phan_tram():
    docs, _rels = load_corpus(_CORPUS_REAL)
    so_hieu_theo_doc = {d.doc_id: d.so_hieu for d in docs}
    chunk_theo_id = {c["id"]: c for c in build_chunks(docs)}

    canh = [
        CanhTacDong.model_validate_json(line)
        for line in _CANH_TAC_DONG_JSONL.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    hang = [
        json.loads(line)
        for line in _CAU_HOI_NHAN_JSONL.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(hang) >= 10

    nhanh_thay = {"nguyen_ven", "nen_da_sua", "trich_trong_van_ban_sua"}
    assert {h["nhanh_dung"] for h in hang} == nhanh_thay  # phủ đủ cả 3 nhánh

    sai: list[str] = []
    for h in hang:
        # Chunk phải thật sự có trong corpus — nhãn không được trỏ vào một id bịa.
        assert h["chunk_id"] in chunk_theo_id, f"chunk lạ: {h['chunk_id']}"

        span = tuple(h["span"]) if h["span"] is not None else None
        v = dinh_tuyen(h["chunk_id"], span, canh, so_hieu_theo_doc, _HOM_NAY)
        assert v is not None, f"không định tuyến được: {h['chunk_id']}"
        if v.nhanh != h["nhanh_dung"]:
            sai.append(f"{h['chunk_id']}: nhãn={h['nhanh_dung']!r} nhưng dinh_tuyen={v.nhanh!r}")

        # Trường tuỳ chọn (review round 2, F5): dòng nào có ghi kỳ vọng một đoạn trong câu
        # trích dẫn thì phải kiểm luôn — không chỉ đúng NHÁNH mà còn đúng CHỮ người đọc thấy.
        trich_dan_chua = h.get("trich_dan_chua")
        if trich_dan_chua is not None and trich_dan_chua not in v.trich_dan_dung_chu:
            sai.append(
                f"{h['chunk_id']}: trích dẫn thiếu {trich_dan_chua!r} — "
                f"thực tế={v.trich_dan_dung_chu!r}"
            )

    assert not sai, "\n".join(sai)
    print(f"\n[cau_hoi_nhan] {len(hang)}/{len(hang)} khớp nhãn tại hôm_nay={_HOM_NAY}")
