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
