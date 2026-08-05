from __future__ import annotations

from app.ontology.dinh_tuyen import dinh_tuyen, khoa_tu_chunk_id
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
