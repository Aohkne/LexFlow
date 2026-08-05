from app.ontology.hien_hanh import DonViOverlay, dung_overlay
from app.ontology.tac_dong import CanhTacDong


def _c(nguon, dich, thao_tac="sua_doi"):
    return CanhTacDong(nguon=nguon, dich=dich, thao_tac=thao_tac, menh_lenh="x")


def test_dung_overlay_dedup_va_gan_doc_id():
    canh = [
        _c("41/2025/TT-NHNN#than/dieu_1", "40/2024/TT-NHNN#than/dieu_8#khoan_1"),
        _c("41/2025/TT-NHNN#than/dieu_1", "40/2024/TT-NHNN#than/dieu_8#khoan_2"),
        _c("22/2026/TT-NHNN#than/dieu_6", "41/2025/TT-NHNN#than/dieu_16", "bai_bo"),
    ]
    nodes: dict[str, DonViOverlay] = {n.khoa: n for n in dung_overlay(canh)}
    assert len(nodes) == 5  # 2 nguon + 3 dich, dieu_1 khong nhan doi
    assert nodes["40/2024/TT-NHNN#than/dieu_8#khoan_1"].doc_id == "TT40-2024"
    assert nodes["41/2025/TT-NHNN#than/dieu_1"].vai == "nguon_lenh"


def test_vua_nguon_vua_dich_thi_la_dich():
    """TT41 D16 phat lenh sua TT40 NHUNG chinh no bi TT22 bai — vai 'bi tac dong' thang."""
    canh = [
        _c("41/2025/TT-NHNN#than/dieu_16", "40/2024/TT-NHNN#than/dieu_41"),
        _c("22/2026/TT-NHNN#than/dieu_6", "41/2025/TT-NHNN#than/dieu_16", "bai_bo"),
    ]
    nodes: dict[str, DonViOverlay] = {n.khoa: n for n in dung_overlay(canh)}
    assert nodes["41/2025/TT-NHNN#than/dieu_16"].vai == "dich_bi_tac_dong"
