"""Trình xem toàn văn: đánh dấu ở MỨC KHOẢN, không chỉ mức điều."""
from app.knowledge.lop_phu import tac_dong_cua_van_ban

from tests.test_lop_phu import _goi  # tái dùng gói mẫu


def test_liet_ke_don_vi_bi_cham(tmp_path):
    from app.knowledge.lop_phu import tai_lop_phu

    p = tmp_path / "lop_phu.json"
    p.write_text(_goi().model_dump_json(), encoding="utf-8")
    tai_lop_phu.cache_clear()
    lp = tai_lop_phu(str(p))
    ra = tac_dong_cua_van_ban("TT40-2024", "2026-08-06", lp)
    tai_lop_phu.cache_clear()

    theo_nhan = {(t.article, t.khoan): t for t in ra}
    assert theo_nhan[("Điều 8", "7")].trang_thai == "da_sua"
    assert theo_nhan[("Điều 8", "7")].boi_doc_id == "TT41-2025"
    assert theo_nhan[("Điều 9", None)].trang_thai == "bi_bai_bo"


def test_van_ban_khong_bi_cham_tra_rong(tmp_path):
    from app.knowledge.lop_phu import tai_lop_phu

    p = tmp_path / "lop_phu.json"
    p.write_text(_goi().model_dump_json(), encoding="utf-8")
    tai_lop_phu.cache_clear()
    lp = tai_lop_phu(str(p))
    assert tac_dong_cua_van_ban("TT41-2025", "2026-08-06", lp) == []
    tai_lop_phu.cache_clear()
