"""Trình xem toàn văn: đánh dấu ở MỨC KHOẢN, không chỉ mức điều."""
from pathlib import Path

import pytest

from app.knowledge.lop_phu import DUONG_DAN_MAC_DINH, tac_dong_cua_van_ban

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


def test_mang_theo_loi_van_moi_va_menh_lenh(tmp_path):
    """Bảng đối chiếu cần chữ, không chỉ cần cờ trạng thái."""
    from app.knowledge.lop_phu import tai_lop_phu

    p = tmp_path / "lop_phu.json"
    p.write_text(_goi().model_dump_json(), encoding="utf-8")
    tai_lop_phu.cache_clear()
    ra = tac_dong_cua_van_ban("TT40-2024", "2026-08-06", tai_lop_phu(str(p)))
    tai_lop_phu.cache_clear()

    theo_nhan = {(t.article, t.khoan): t for t in ra}
    sua = theo_nhan[("Điều 8", "7")]
    assert sua.thao_tac == "sua_doi"
    assert sua.menh_lenh == "Sửa đổi khoản 7 Điều 8 như sau:"
    assert sua.loi_van_moi == '"7. Hạn mức mới là 200 triệu đồng."'

    # Bãi bỏ thì KHÔNG có lời văn thay thế — để trống chứ không bịa một chuỗi rỗng.
    bai_bo = theo_nhan[("Điều 9", None)]
    assert bai_bo.thao_tac == "bai_bo"
    assert bai_bo.loi_van_moi is None


@pytest.mark.skipif(
    not Path(DUONG_DAN_MAC_DINH).exists(),
    reason=f"chưa dựng artefact lớp phủ {DUONG_DAN_MAC_DINH}",
)
def test_artefact_that_co_du_chu_cho_bang_doi_chieu():
    """Chạy trên chính artefact đã đóng gói từ corpus đã cào, không phải gói mẫu.

    Bảo vệ đúng điều trình xem dựa vào: mọi lần chạm KHÔNG phải bãi bỏ đều phải có lời văn mới.
    Thiếu chữ thì modal đối chiếu chỉ còn một nửa, mà hỏng kiểu đó im lặng — trang vẫn dựng.
    """
    from app.knowledge.lop_phu import tai_lop_phu

    tai_lop_phu.cache_clear()
    lp = tai_lop_phu()
    assert lp is not None, "artefact có mà nạp không được"

    doc_ids = {d for d in lp.so_hieu_theo_doc}
    tat_ca = [t for d in doc_ids for t in tac_dong_cua_van_ban(d, "2026-08-06", lp)]
    tai_lop_phu.cache_clear()

    assert tat_ca, "artefact thật mà không văn bản nào bị chạm — nghi artefact rỗng"
    thieu = [
        t
        for t in tat_ca
        if t.thao_tac not in (None, "bai_bo") and not t.loi_van_moi
    ]
    assert not thieu, f"{len(thieu)} lần chạm không phải bãi bỏ mà thiếu lời văn mới: {thieu[:3]}"


def test_van_ban_khong_bi_cham_tra_rong(tmp_path):
    from app.knowledge.lop_phu import tai_lop_phu

    p = tmp_path / "lop_phu.json"
    p.write_text(_goi().model_dump_json(), encoding="utf-8")
    tai_lop_phu.cache_clear()
    lp = tai_lop_phu(str(p))
    assert tac_dong_cua_van_ban("TT41-2025", "2026-08-06", lp) == []
    tai_lop_phu.cache_clear()
