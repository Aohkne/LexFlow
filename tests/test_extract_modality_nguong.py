"""ActorCU nhận modality + nguong tất định khi build từ JSON của LLM."""
from app.ontology.extractor import build_actor_cu
from app.ontology.parser import parse_dieu
from app.ontology.segmenter import segment

_TEXT = (
    "Điều 9. Hạn mức giao dịch\n"
    "1. Tổ chức cung ứng dịch vụ không được cho phép giao dịch vượt hạn mức "
    "không quá 100 triệu đồng mỗi tháng đối với một khách hàng cá nhân."
)


def _dieu_va_khoan():
    dieu = parse_dieu(_TEXT, "99/2024/TT-TEST")
    khoan = dieu.khoan[0]
    return dieu, khoan, segment(dieu, khoan)


def test_actor_cu_mang_modality_va_nguong():
    dieu, khoan, units = _dieu_va_khoan()
    # units[0] = tiêu đề Điều; đơn vị thân khoản bắt đầu từ 1
    data = {
        "subject": {"units": [1], "label": "Tổ chức cung ứng dịch vụ"},
        "action": {"units": [1], "label": "không cho phép giao dịch vượt hạn mức"},
        "logic": "all",
        "conditions": [],
    }
    cu = build_actor_cu(data, khoan, dieu, units)
    assert cu.modality == "cam"  # "không được" trong action.text đã neo
    assert len(cu.nguong) == 1
    assert (cu.nguong[0].so, cu.nguong[0].huong) == ("100", "toi_da")
    # span của nguong phải nằm trong dieu.text và round-trip đúng chữ
    s, e = cu.nguong[0].span
    assert cu.nguong[0].text == dieu.text[s:e].strip()


def test_khong_ro_nhung_khoan_co_rang_buoc_cung_thi_canh_bao():
    dieu, khoan, units = _dieu_va_khoan()
    # action neo vào tiêu đề Điều (unit 0) — text không mang dấu hiệu nào
    data = {
        "subject": {"units": [1], "label": "Tổ chức"},
        "action": {"units": [0], "label": "hạn mức giao dịch"},
        "conditions": [],
    }
    cu = build_actor_cu(data, khoan, dieu, units)
    assert cu.modality == "khong_ro"
    assert any(w.startswith("tinh_thai_kho:") for w in cu.warnings)
