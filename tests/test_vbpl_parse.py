"""Test cho phần parse thuần của tool vbpl.vn — không chạm mạng/trình duyệt.

Dữ liệu vào là bản chụp thật từ Thông tư 15/2024/TT-NHNN (tab Thuộc tính và Lược đồ).
"""
from app.ingestion.vbpl import (
    _dedupe_amendments,
    classify_badge,
    clean_body,
    parse_property_rows,
    parse_relations,
)

# Bảng Thuộc tính có 2 ô mỗi hàng, mỗi ô là "<nhãn>\n<giá trị>".
PROP_ROWS = [
    ["Số hiệu\n15/2024/TT-NHNN", "Loại văn bản\nThông tư"],
    ["Ngành\nNgân hàng", "Ngày ban hành\n28/06/2024"],
    ["Lĩnh vực\nThanh tra", "Ngày có hiệu lực\n01/07/2024"],
    ["Tình trạng hiệu lực\nHết hiệu lực một phần", "Ngày hết hiệu lực\n--"],
    ["Cơ quan ban hành\nNgân hàng Nhà nước Việt Nam"],
    ["Chức danh\nPhó Thống đốc", "Người ký\nPhạm Tiến Dũng"],
]

LUOC_DO = """Lược đồ
Văn bản được hướng dẫn áp dụng (0)
--
Văn bản được thay thế (2)
Thông tư số 38/2019/TT-NHNN Quy định về việc cung ứng dịch vụ thanh toán
Thông tư số 46/2014/TT-NHNN Hướng dẫn về dịch vụ thanh toán không dùng tiền mặt
Văn bản bị bãi bỏ (1)
Thông tư số 30/2016/TT-NHNN Sửa đổi, bổ sung một số Thông tư
Căn cứ ban hành (2)
Luật Bưu chính số 49/2010/QH12
Nghị định số 52/2024/NĐ-CP quy định về thanh toán không dung tiền mặt
VĂN BẢN ĐANG XEM
Thông tư số 15/2024/TT-NHNN Quy định về cung ứng dịch vụ thanh toán
Văn bản hợp nhất (1)
Văn bản hợp nhất số 26/VBHN-NHNN Quy định về cung ứng dịch vụ thanh toán
Văn bản sửa đổi bổ sung (2)
Thông tư số 30/2025/TT-NHNN Sửa đổi, bổ sung của thông tư số 15/2024/TT-NHNN
Thông tư 21/2026/TT-NHNN Sửa đổi, bổ sung Điều 15 Thông tư số 15/2024/TT-NHNN
Văn bản thay thế (0)
--
"""


def test_parse_property_rows_maps_labels_to_keys():
    props = parse_property_rows(PROP_ROWS)
    assert props["so_hieu"] == "15/2024/TT-NHNN"
    assert props["loai_van_ban"] == "Thông tư"
    assert props["tinh_trang_hieu_luc"] == "Hết hiệu lực một phần"
    assert props["nguoi_ky"] == "Phạm Tiến Dũng"
    assert props["co_quan_ban_hanh"] == "Ngân hàng Nhà nước Việt Nam"


def test_parse_property_rows_treats_dash_as_empty():
    # "--" trên trang nghĩa là chưa có, không phải giá trị chuỗi "--"
    assert parse_property_rows(PROP_ROWS)["ngay_het_hieu_luc"] == ""


def test_parse_property_rows_ignores_unknown_labels():
    props = parse_property_rows([["Nhãn lạ\ngiá trị", "Số hiệu\n01/2020/TT-XYZ"]])
    assert props == {"so_hieu": "01/2020/TT-XYZ"}


def test_parse_relations_splits_the_two_directions():
    rel = parse_relations(LUOC_DO)
    # nửa trên: văn bản NÀY tác động lên văn bản khác
    assert rel["outgoing"]["Văn bản được thay thế"] == [
        "Thông tư số 38/2019/TT-NHNN Quy định về việc cung ứng dịch vụ thanh toán",
        "Thông tư số 46/2014/TT-NHNN Hướng dẫn về dịch vụ thanh toán không dùng tiền mặt",
    ]
    assert len(rel["outgoing"]["Văn bản bị bãi bỏ"]) == 1
    assert len(rel["outgoing"]["Căn cứ ban hành"]) == 2
    # nửa dưới: văn bản khác tác động lên văn bản NÀY
    assert len(rel["incoming"]["Văn bản sửa đổi bổ sung"]) == 2
    assert "21/2026/TT-NHNN" in rel["incoming"]["Văn bản sửa đổi bổ sung"][1]


def test_parse_relations_keeps_empty_categories_empty():
    rel = parse_relations(LUOC_DO)
    assert rel["outgoing"]["Văn bản được hướng dẫn áp dụng"] == []
    assert rel["incoming"]["Văn bản thay thế"] == []


def test_parse_relations_does_not_bleed_past_the_count():
    # "Văn bản hợp nhất (1)" chỉ được lấy đúng 1 dòng, không nuốt mục kế tiếp
    rel = parse_relations(LUOC_DO)
    assert len(rel["incoming"]["Văn bản hợp nhất"]) == 1


def test_classify_badge_known_and_unknown():
    assert classify_badge("Điều khoản được sửa đổi, bổ sung") == "sua_doi_bo_sung"
    assert classify_badge("Điều khoản được thay thế") == "thay_the"
    assert classify_badge("Điều khoản được bổ sung") == "bo_sung"
    # nhãn chưa gặp phải lộ ra để biết mà bổ sung, không được nuốt im lặng
    assert classify_badge("Điều khoản được xyz") == "khac:Điều khoản được xyz"


def test_dedupe_amendments_prefers_the_labelled_copy():
    # DOM chứa mỗi khối 2 lần: bản chưa gắn nhãn và bản có nhãn, cùng `type`
    raw = [
        {"type_code": "10:aaa", "badges": [], "article": "Điều 18.", "text": "x"},
        {"type_code": "10:aaa", "badges": ["Điều khoản được sửa đổi, bổ sung"],
         "article": "Điều 18.", "text": "x"},
        {"type_code": "12:bbb", "badges": ["Điều khoản được thay thế"],
         "article": "Điều 7.", "text": "y"},
    ]
    out = _dedupe_amendments(raw)
    assert len(out) == 2
    assert {b["type_code"] for b in out} == {"10:aaa", "12:bbb"}
    assert all(b["badges"] for b in out)


def test_dedupe_amendments_drops_blocks_that_never_got_a_label():
    raw = [{"type_code": "10:ccc", "badges": [], "article": None, "text": "z"}]
    assert _dedupe_amendments(raw) == []


def test_clean_body_cuts_ui_noise_before_the_last_download_tab():
    main_text = "\n".join([
        "TRANG CHỦ", "Nội dung", "Thuộc tính", "Tải về",
        "Còn hiệu lực", "Ngày có hiệu lực:", "01/07/2024",
        "Nội dung", "Thuộc tính", "Tải về",
        "Điều 1. Phạm vi điều chỉnh", "Thông tư này quy định...",
    ])
    body, status, valid_from = clean_body(main_text)
    assert status == "Còn hiệu lực"
    assert valid_from == "01/07/2024"
    assert body.startswith("Điều 1.")
    assert "TRANG CHỦ" not in body
