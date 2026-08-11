"""Bóc ràng buộc định lượng tất định — ghép dấu hiệu dinh_luong với số liền kề."""
from app.ontology.modality import boc_nguong


def test_khong_qua_tien():
    ns, ws = boc_nguong("hạn mức không quá 100 triệu đồng mỗi tháng")
    assert ws == []
    assert len(ns) == 1
    n = ns[0]
    assert (n.so, n.huong, n.don_vi) == ("100", "toi_da", "triệu đồng")
    assert "không quá 100 triệu đồng" in n.text


def test_cham_nhat_ngay_lam_viec():
    ns, _ = boc_nguong("hoàn trả chậm nhất 05 ngày làm việc")
    assert (ns[0].so, ns[0].huong, ns[0].don_vi) == ("5", "toi_da", "ngày làm việc")


def test_tro_len_dau_hieu_dung_sau():
    ns, _ = boc_nguong("khách hàng đủ 15 tuổi trở lên")
    assert (ns[0].so, ns[0].huong, ns[0].don_vi) == ("15", "toi_thieu", "tuổi")


def test_phan_tram():
    ns, _ = boc_nguong("duy trì tối thiểu 50% số dư")
    assert (ns[0].so, ns[0].huong, ns[0].don_vi) == ("50", "toi_thieu", "%")


def test_so_khong_dau_hieu_khong_thanh_nguong():
    # số điều khoản / viện dẫn không phải ngưỡng
    ns, ws = boc_nguong("quy định tại khoản 2 Điều 5 Nghị định này")
    assert ns == [] and ws == []


def test_dau_hieu_khong_so_bao_bo_sot():
    ns, ws = boc_nguong("hoàn trả trong thời hạn do các bên thỏa thuận")
    assert ns == []
    assert len(ws) == 1 and "nguong_bo_sot" in ws[0]


def test_offset_span():
    ns, _ = boc_nguong("không quá 20 triệu đồng", offset=100)
    s, e = ns[0].span
    assert s >= 100 and "không quá 20 triệu đồng"[s - 100 : e - 100] == ns[0].text
