"""Test cho bước chuyển bản crawl → CorpusDocument, chạy trên FILE THẬT đã crawl.

Fixture trong `tests/fixtures/vbpl/` là artefact nguyên vẹn của một lần cào thật, không phải
dữ liệu dựng tay: những khuyết tật ở đây (nhãn vbpl chèn vào thân điều, khoản lặp, DOM thiếu
markup, văn bản không có toàn văn) đều là thứ chỉ lộ ra trên dữ liệu thật.

  tt15-2024.raw.json        Thông tư 15/2024/TT-NHNN — bản cào TRƯỚC khi lọc nhiễu
  tt15-2024.prov-nodes.json danh sách phẳng prov-* đọc từ DOM của cùng văn bản đó
  vbhn29-nhnn.raw.json      Văn bản hợp nhất 29/VBHN-NHNN — vbpl không đăng toàn văn
  nd80-2016.raw.json        Nghị định 80/2016/NĐ-CP — văn bản SỬA ĐỔI, có khối trích dẫn
  nd52-2024.noi-dung.txt    trường `noi_dung` nguyên vẹn của 52/2024/NĐ-CP (không có ngoặc)
"""
import json
from pathlib import Path

import pytest

from app.core.schemas import CorpusDocument
from app.ingestion.vbpl import (
    _looks_like_property_table,
    build_provision_tree,
    check_tree_coverage,
    count_provisions,
    count_units,
    doc_id_from_so_hieu,
    file_download_url,
    has_full_text,
    parse_file_leaves,
    quote_spans,
    split_articles,
    strip_amend_noise,
    to_corpus_document,
)

FIXTURES = Path(__file__).parent / "fixtures" / "vbpl"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tt15() -> dict:
    return _load("tt15-2024.raw.json")


@pytest.fixture(scope="module")
def tt15_sach(tt15) -> str:
    return strip_amend_noise(tt15["noi_dung"])[0]


# --- Khuyết tật 4: nhãn vbpl và khoản lặp lọt vào toàn văn ---

def test_bo_dong_nhan_nhung_giu_tieu_de_dieu_that(tt15):
    body, labels, _ = strip_amend_noise(tt15["noi_dung"])
    assert "Điều khoản được sửa đổi, bổ sung" in tt15["noi_dung"]  # nguồn có
    assert not any(
        ln.strip().startswith("Điều khoản được") or ln.strip().startswith("Điều khoản bị")
        for ln in body.split("\n")
    )
    assert len(labels) == 28  # 28 dòng nhãn nằm trong thân điều của TT15
    # "Điều khoản thi hành" là tiêu đề Điều CÓ THẬT — lọc theo tiền tố trần sẽ ăn mất nó
    assert doc_id_from_so_hieu("15/2024/TT-NHNN")  # (giữ import gọn)


def test_giu_tieu_de_dieu_khoan_thi_hanh():
    body, labels, _ = strip_amend_noise(
        "Điều 22. Điều khoản thi hành\nĐiều khoản được thay thế\n1. Có hiệu lực."
    )
    assert "Điều 22. Điều khoản thi hành" in body
    assert [lb["nhan"] for lb in labels] == ["Điều khoản được thay thế"]


def test_khu_khoan_lap_y_het_trong_cung_mot_dieu(tt15, tt15_sach):
    # Điều 19: khoản 1,2,3,8,9 xuất hiện 2 lần, giống hệt từng ký tự
    assert count_units(tt15["noi_dung"])["khoan"] == 102  # trước khi lọc: bị thổi phồng
    assert count_units(tt15_sach)["khoan"] == 97          # sau khi lọc: số thật


def test_khoan_trung_so_nhung_khac_noi_dung_thi_giu_ca_hai_va_canh_bao():
    body, _, warnings = strip_amend_noise(
        "Điều 1. Sửa đổi\n5. Bản cũ của khoản 5.\n5. Bản mới của khoản 5."
    )
    assert body.count("khoản 5") == 2                     # không chọn hộ bản nào
    assert any("khoản 5 xuất hiện 2 lần" in w for w in warnings)


def test_nhan_da_loc_duoc_giu_lai_trong_dieu_khoan_bi_tac_dong(tt15):
    _, labels, _ = strip_amend_noise(tt15["noi_dung"])
    assert {lb["dieu"] for lb in labels} >= {"3", "19"}
    assert all(lb["nhan"].startswith("Điều khoản ") for lb in labels)


# --- Khuyết tật 1: articles[] mất đánh số và tiêu đề điều ---

def test_articles_sinh_tu_toan_van_giu_nguyen_danh_so(tt15_sach):
    arts = split_articles(tt15_sach)
    assert len(arts) == 23
    dieu2 = next(a for a in arts if a["article"] == "Điều 2")
    assert dieu2["text"].startswith("Đối tượng áp dụng\n1. Tổ chức cung ứng dịch vụ")
    assert "\na) Ngân hàng Nhà nước Việt Nam" in dieu2["text"]
    assert "\nb) Ngân hàng thương mại" in dieu2["text"]


def test_articles_dat_dung_moc_nghiem_thu(tt15_sach):
    arts = split_articles(tt15_sach)
    assert count_units(tt15_sach) == {"dieu": 23, "khoan": 97, "diem": 57}
    assert sum(1 for a in arts if a["chapter"]) == 23      # đủ 23/23


def test_articles_la_lat_cat_nguyen_van_cua_toan_van(tt15_sach):
    """Bất biến xuất xứ mức ký tự: noi_dung[start:end] == text."""
    for a in split_articles(tt15_sach):
        assert tt15_sach[a["char_start"] : a["char_end"]] == a["text"]


def test_chuong_muc_lay_duoc_ca_tieu_de_nhieu_dong(tt15_sach):
    arts = {a["article"]: a for a in split_articles(tt15_sach)}
    assert arts["Điều 1"]["chapter"] == "Chương I. QUY ĐỊNH CHUNG"
    assert arts["Điều 7"]["section"] == "Mục 1. DỊCH VỤ THANH TOÁN QUA NGÂN HÀNG NHÀ NƯỚC"
    assert arts["Điều 22"]["chapter"] == "Chương IV. ĐIỀU KHOẢN THI HÀNH"  # nguồn viết hoa


def test_phu_luc_khong_phai_than_van_ban():
    """Phụ lục là biểu mẫu và có "Điều 1..7" của riêng nó — đếm vào là thổi phồng số điều."""
    body = "Điều 1. Phạm vi\n1. Nội dung.\nPHỤ LỤC\nĐiều 1. Cấp đổi Giấy phép\n1. Tên."
    assert count_units(body) == {"dieu": 1, "khoan": 1, "diem": 0}
    assert len(split_articles(body)) == 1


# --- Khối trích dẫn của văn bản sửa đổi ---

@pytest.fixture(scope="module")
def nd80() -> dict:
    return _load("nd80-2016.raw.json")


@pytest.fixture(scope="module")
def nd52_noi_dung() -> str:
    return (FIXTURES / "nd52-2024.noi-dung.txt").read_text(encoding="utf-8")


def test_khoan_trung_so_voi_doan_trich_thi_khong_canh_bao(nd80):
    """ND80 Điều 1: khoản 5,6,7,8 xuất hiện 2 lần, nhưng là HAI VĂN BẢN.

    Bản trong ngoặc là khoản của 101/2012/NĐ-CP được chép vào, bản ngoài ngoặc là khoản của
    chính ND80. Không có gì để người đọc quyết — cảnh báo ở đây là việc rà soát giả, và vài
    lần như thế là người ta ngừng đọc cảnh báo thật.
    """
    _, _, warnings = strip_amend_noise(nd80["noi_dung"])
    assert not [w for w in warnings if "xuất hiện 2 lần" in w]


def test_doan_trich_khong_bi_cat_khoi_toan_van(nd80):
    """Ngoặc là của chính đạo luật: giữ nguyên từng ký tự, chỉ dùng để BIẾT, không để cắt."""
    body, _, _ = strip_amend_noise(nd80["noi_dung"])
    assert body == nd80["noi_dung"]
    assert "5. Chủ tài khoản thanh toán" in body       # bản được chép — còn
    assert "5. Sửa đổi điểm b khoản 2 Điều 12" in body  # khoản của ND80 — còn


def test_moc_doi_chieu_bo_dong_trong_ngoac_con_so_bao_ra_thi_khong(nd80):
    body = nd80["noi_dung"]
    assert count_units(body)["khoan"] == 14                        # số báo ra: giữ nguyên
    assert count_units(body, ngoai_trich_dan=True)["khoan"] == 10  # mốc đối chiếu với cây


def test_cay_nd80_khong_con_bi_bao_la_thieu(nd80):
    """Trước sửa: "cây thiếu 4 Khoản (10/14)" — nói ngược, 10 mới là số đúng."""
    tree = nd80["cay_dieu_khoan"]
    assert count_provisions(tree)["khoan"] == 10
    assert not [w for w in check_tree_coverage(tree, nd80["noi_dung"]) if "Khoản" in w]


def test_van_ban_khong_co_ngoac_thi_khong_doi_gi(nd52_noi_dung):
    """52/2024/NĐ-CP không có dấu ngoặc kép nào — hai phép đếm phải trùng khít."""
    assert quote_spans(nd52_noi_dung) == []
    assert count_units(nd52_noi_dung) == count_units(nd52_noi_dung, ngoai_trich_dan=True)
    assert count_units(nd52_noi_dung) == {"dieu": 38, "khoan": 153, "diem": 102}


def test_quote_spans_la_lat_cat_that_cua_toan_van(nd80):
    body = nd80["noi_dung"]
    spans = quote_spans(body)
    assert spans, "ND80 là văn bản sửa đổi, phải có khối trích dẫn"
    for sp in spans:
        doan = body[sp["char_start"] : sp["char_end"]]
        assert doan[0] in '"“' and doan[-1] in '"”'
    assert any("5. Chủ tài khoản thanh toán" in body[s["char_start"] : s["char_end"]] for s in spans)


# --- Khuyết tật 2: cây provisions thiếu nút ---

def test_cay_bam_sat_toan_van_tren_du_lieu_that(tt15_sach):
    nodes = _load("tt15-2024.prov-nodes.json")
    tree = build_provision_tree(nodes)
    dem = count_provisions(tree)
    assert dem["dieu"] == 23
    assert dem["diem"] == 57
    # Bản chụp nút phẳng này lấy TRƯỚC khi `_JS_PROVISION_NODES` biết bù dòng Khoản không có
    # thẻ, nên vẫn còn thiếu 1 Khoản. Cào lại bây giờ ra 97; giữ bản chụp cũ ở đây để còn một
    # ca lệch thật mà kiểm tra `check_tree_coverage`.
    assert dem["khoan"] == 96
    assert check_tree_coverage(tree, tt15_sach) == [
        "lệch Khoản giữa cây điều khoản và toàn văn: cây 96, toàn văn 97 — chưa biết bên nào "
        "đúng, phải soi DOM (nguồn có khi bỏ markup một dòng khiến cây thiếu, có khi render "
        "khối sửa đổi 2 lần khiến toàn văn dư)"
    ]


def test_check_tree_coverage_len_tieng_khi_lech():
    tree = build_provision_tree([
        {"cls": "prov-article", "text": "Điều 1. Phạm vi", "id": "a", "parent_id": None,
         "hidden": False, "amend_type": None, "amend_badges": []},
    ])
    warnings = check_tree_coverage(tree, "Điều 1. Phạm vi\n1. Một.\n2. Hai.")
    assert len(warnings) == 1
    assert warnings[0].startswith("lệch Khoản giữa cây điều khoản và toàn văn: cây 0, toàn văn 2")
    # Không được khẳng định bên nào sai: ở 34/2024 Điều 23 chính toàn văn mới là bên dư.
    assert "cây điều khoản thiếu" not in warnings[0]


def test_check_tree_coverage_im_lang_khi_du(tt15_sach):
    assert check_tree_coverage(build_provision_tree([]), "") == []


# --- Khuyết tật 3: văn bản không có toàn văn ---

def test_bang_thuoc_tinh_khong_duoc_tinh_la_toan_van():
    vbhn = _load("vbhn29-nhnn.raw.json")
    ban_thuoc_tinh = vbhn["noi_dung"]
    assert len(ban_thuoc_tinh) > 100          # phép kiểm theo độ dài sẽ cho qua
    assert not has_full_text(ban_thuoc_tinh)  # nhưng không có dòng "Điều N." nào
    assert _looks_like_property_table(ban_thuoc_tinh)


def test_co_toan_van_false_thi_noi_dung_de_rong_va_co_canh_bao():
    doc = to_corpus_document({
        "url": "https://vbpl.vn/van-ban/chi-tiet/vbhn-29--186078",
        "title": "Văn bản hợp nhất số 29/VBHN-NHNN",
        "noi_dung": "",
        "co_toan_van": False,
        "canh_bao": ["nguồn không đăng toàn văn"],
        "thuoc_tinh": {"so_hieu": "29/VBHN-NHNN", "loai_van_ban": "Văn bản hợp nhất"},
        "cay_dieu_khoan": [],
    })
    assert doc["co_toan_van"] is False
    assert doc["articles"] == []
    assert doc["canh_bao"] == ["nguồn không đăng toàn văn"]


def test_tep_dinh_kem_doc_duoc_ten_va_dung_luong():
    # đúng thứ tự phần tử lá của tab "Tải về" trên vbpl
    leaves = [
        "Tải về",
        "168089_body_content.html", "0.1MB", "14/04/2026 12:39",
        "Thong tu 15.2024.TT.NHNN.pdf", "10.79MB", "14/04/2026 12:39",
    ]
    files = parse_file_leaves(leaves)
    assert files == [
        {"ten": "168089_body_content.html", "kich_thuoc": "0.1MB"},
        {"ten": "Thong tu 15.2024.TT.NHNN.pdf", "kich_thuoc": "10.79MB"},
    ]


def test_url_tai_tep_dung_id_so_trong_url_chi_tiet():
    url = file_download_url(
        "https://vbpl.vn/van-ban/chi-tiet/thong-tu-so-15-2024--168089",
        "Thong tu 15.2024.TT.NHNN.pdf",
    )
    assert url.endswith("/vbpl/168089/Thong%20tu%2015.2024.TT.NHNN.pdf/download")
    assert file_download_url("https://vbpl.vn/van-ban/chi-tiet/khong-co-id", "a.pdf") is None


# --- Việc nhỏ (a): doc_id theo đúng quy ước corpus ---

@pytest.mark.parametrize(
    "so_hieu,doc_id",
    [
        ("15/2024/TT-NHNN", "TT15-2024"),
        ("101/2012/NĐ-CP", "ND101-2012"),
        ("52/2024/NĐ-CP", "ND52-2024"),
        ("29/VBHN-NHNN", "VBHN29-NHNN"),   # không có năm → cơ quan làm phần phân biệt
    ],
)
def test_doc_id_from_so_hieu(so_hieu, doc_id):
    assert doc_id_from_so_hieu(so_hieu) == doc_id


# --- Toàn bộ artefact vẫn hợp lệ với schema ---

def test_corpus_document_hop_le_voi_schema(tt15):
    doc = dict(tt15)
    doc["noi_dung"], _, doc["canh_bao"] = strip_amend_noise(tt15["noi_dung"])
    doc["co_toan_van"] = has_full_text(doc["noi_dung"])
    cdoc = CorpusDocument.model_validate(to_corpus_document(doc))
    assert cdoc.doc_id == "TT15-2024"
    assert len(cdoc.articles) == 23
    assert cdoc.co_toan_van is True
    assert cdoc.articles[1].char_start is not None
