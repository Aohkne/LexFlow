"""Test cho phần parse thuần của tool vbpl.vn — không chạm mạng/trình duyệt.

Dữ liệu vào là bản chụp thật từ Thông tư 15/2024/TT-NHNN (tab Thuộc tính và Lược đồ).
"""
from pathlib import Path

from app.ingestion.vbpl import (
    _dedupe_amendments,
    build_provision_tree,
    classify_badge,
    clean_body,
    count_provisions,
    default_out_dir,
    group_relations,
    parse_property_rows,
    parse_relations,
    sanitize_inline,
    sitemap_cache_dir,
    slug_for,
    split_heading,
    to_corpus_document,
)


def _n(cls, text, **kw):
    return {"cls": cls, "text": text, "id": kw.get("id"), "parent_id": kw.get("parent_id"),
            "hidden": kw.get("hidden", False), "amend_type": kw.get("amend_type"),
            "amend_badges": kw.get("amend_badges", [])}


# Bản chụp thu nhỏ theo đúng cách vbpl.vn dựng DOM: tiêu đề Chương bị tách làm 2 thẻ
# cùng class, thẻ sau trỏ parent-id về thẻ đầu; nội dung Điều nằm ở prov-content riêng.
PROV_NODES = [
    _n("prov-chapter", "Chương I", id="c1"),
    _n("prov-chapter", "QUY ĐỊNH CHUNG", id="c1_1", parent_id="c1"),
    _n("prov-article", "Điều 1. Phạm vi điều chỉnh", id="a1"),
    _n("prov-content", "Thông tư này quy định về cung ứng dịch vụ thanh toán.", parent_id="a1"),
    _n("prov-article", "Điều 2. Đối tượng áp dụng", id="a2"),
    _n("prov-clause", "1. Tổ chức cung ứng dịch vụ thanh toán.", id="k1"),
    _n("prov-clause", "2. Ngân hàng, chi nhánh ngân hàng nước ngoài.", id="k2",
       amend_type="10:x", amend_badges=["Điều khoản được sửa đổi, bổ sung"]),
    _n("prov-item", "a) Ngân hàng thương mại.", id="d1"),
    _n("prov-item", "b) Chi nhánh ngân hàng nước ngoài.", id="d2"),
    _n("prov-chapter", "Chương II", id="c2"),
    _n("prov-article", "Điều 3. Giải thích từ ngữ", id="a3"),
]

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


RELATION_ITEMS = [
    {"idx": 0, "title": "Thông tư số 38/2019/TT-NHNN", "category": "Văn bản được thay thế",
     "direction": "outgoing", "url": "https://vbpl.vn/van-ban/chi-tiet/tt-38-2019--140177"},
    {"idx": 1, "title": "Thông tư số 46/2014/TT-NHNN", "category": "Văn bản được thay thế",
     "direction": "outgoing", "url": "https://vbpl.vn/van-ban/chi-tiet/tt-46-2014--46835"},
    {"idx": 2, "title": "Thông tư số 30/2016/TT-NHNN", "category": "Văn bản bị bãi bỏ",
     "direction": "outgoing", "url": "https://vbpl.vn/van-ban/chi-tiet/tt-30-2016--123"},
    {"idx": 3, "title": "Thông tư 21/2026/TT-NHNN", "category": "Văn bản sửa đổi bổ sung",
     "direction": "incoming", "url": "https://vbpl.vn/van-ban/chi-tiet/tt-21-2026--456"},
]


def test_group_relations_keeps_direction_category_and_url():
    rel = group_relations(RELATION_ITEMS)
    thay_the = rel["outgoing"]["Văn bản được thay thế"]
    assert [x["title"] for x in thay_the] == [
        "Thông tư số 38/2019/TT-NHNN",
        "Thông tư số 46/2014/TT-NHNN",
    ]
    assert thay_the[0]["url"].endswith("140177")
    assert rel["outgoing"]["Văn bản bị bãi bỏ"][0]["title"] == "Thông tư số 30/2016/TT-NHNN"
    assert rel["incoming"]["Văn bản sửa đổi bổ sung"][0]["url"].endswith("456")


def test_group_relations_surfaces_items_with_no_category():
    rel = group_relations([{"idx": 0, "title": "Văn bản lạ", "category": None,
                           "direction": "outgoing", "url": None}])
    # không được nuốt im lặng — phải lộ ra dưới nhóm riêng
    assert rel["outgoing"]["(không rõ nhóm)"] == [{"title": "Văn bản lạ", "url": None}]


def test_group_relations_keeps_title_when_url_is_missing():
    rel = group_relations([{"idx": 0, "title": "Không mở được", "category": "Căn cứ ban hành",
                            "direction": "outgoing", "url": None}])
    assert rel["outgoing"]["Căn cứ ban hành"] == [{"title": "Không mở được", "url": None}]


def test_group_relations_on_empty_input_has_both_directions():
    assert group_relations([]) == {"outgoing": {}, "incoming": {}}


# --- sanitize_inline: HTML tu site ngoai, whitelist phai hep ---

def test_sanitize_inline_keeps_emphasis():
    assert sanitize_inline("<strong>Điều 1</strong>. Phạm vi") == "<strong>Điều 1</strong>. Phạm vi"
    assert sanitize_inline("<em>a</em> và <b>b</b>") == "<em>a</em> và <b>b</b>"
    assert sanitize_inline("dòng 1<br/>dòng 2") == "dòng 1<br>dòng 2"


def test_sanitize_inline_strips_every_attribute():
    # style/class/id của vbpl phải rụng hết, nếu không sẽ chọi với theme
    got = sanitize_inline('<strong style="color:red" class="x" id="y">Điều 1</strong>')
    assert got == "<strong>Điều 1</strong>"


def test_sanitize_inline_unwraps_unknown_tags_but_keeps_their_text():
    assert sanitize_inline('<span style="font-size:14px">Nội dung</span>') == "Nội dung"
    assert sanitize_inline("<div><p>Một</p><p>Hai</p></div>") == "MộtHai"


def test_sanitize_inline_removes_script_and_event_handlers():
    assert "script" not in sanitize_inline("<script>alert(1)</script>Chữ")
    assert sanitize_inline('<b onclick="alert(1)">Chữ</b>') == "<b>Chữ</b>"
    assert sanitize_inline('<a href="javascript:alert(1)">Bấm</a>') == "Bấm"


def test_sanitize_inline_escapes_raw_angle_brackets():
    # chữ "<" trong văn bản luật phải thành &lt;, không được biến thành thẻ
    assert sanitize_inline("số tiền &lt; 5 triệu") == "số tiền &lt; 5 triệu"
    assert "<b>" not in sanitize_inline("dùng ký hiệu &lt;b&gt; trong hợp đồng")


def test_sanitize_inline_closes_unbalanced_tags():
    assert sanitize_inline("<strong>chưa đóng") == "<strong>chưa đóng</strong>"


def test_sanitize_inline_on_empty_or_markup_only():
    assert sanitize_inline("") == ""
    assert sanitize_inline("<span></span>") == ""
    assert sanitize_inline("<b>   </b>") == ""


def test_split_heading_pulls_the_number_out():
    assert split_heading("dieu", "Điều 7. Dịch vụ thanh toán") == ("7", "Dịch vụ thanh toán")
    assert split_heading("chuong", "Chương III") == ("III", "")
    assert split_heading("muc", "Mục 2") == ("2", "")
    assert split_heading("khoan", "1. Tổ chức cung ứng dịch vụ.") == (
        "1", "Tổ chức cung ứng dịch vụ.")
    assert split_heading("diem", "a) Ngân hàng thương mại.") == ("a", "Ngân hàng thương mại.")


def test_split_heading_leaves_unrecognised_text_alone():
    assert split_heading("dieu", "Không phải tiêu đề") == (None, "Không phải tiêu đề")


def test_build_provision_tree_nests_by_level():
    tree = build_provision_tree(PROV_NODES)
    assert [c["so"] for c in tree] == ["I", "II"]
    ch1 = tree[0]
    assert ch1["tieu_de"] == "QUY ĐỊNH CHUNG"          # 2 thẻ tiêu đề đã gộp lại
    assert [a["so"] for a in ch1["con"]] == ["1", "2"]
    dieu2 = ch1["con"][1]
    assert [k["so"] for k in dieu2["con"]] == ["1", "2"]
    # Điểm nằm dưới Khoản, không phải dưới Điều
    assert [d["so"] for d in dieu2["con"][1]["con"]] == ["a", "b"]


def test_build_provision_tree_attaches_content_to_its_article():
    tree = build_provision_tree(PROV_NODES)
    dieu1 = tree[0]["con"][0]
    assert dieu1["tieu_de"] == "Phạm vi điều chỉnh"
    assert "cung ứng dịch vụ thanh toán" in dieu1["text"]


def test_build_provision_tree_marks_amended_nodes():
    tree = build_provision_tree(PROV_NODES)
    khoan1, khoan2 = tree[0]["con"][1]["con"]
    assert khoan1["bi_tac_dong"] is None
    assert khoan2["bi_tac_dong"] == ["sua_doi_bo_sung"]


def test_build_provision_tree_starts_a_new_chapter_cleanly():
    tree = build_provision_tree(PROV_NODES)
    assert [a["so"] for a in tree[1]["con"]] == ["3"]


def test_split_heading_accepts_uppercase_headings():
    # trang viết cả "Chương IV" lẫn "CHƯƠNG IV" — cả hai phải ra số chương
    assert split_heading("chuong", "CHƯƠNG IV ĐIỀU KHOẢN THI HÀNH") == (
        "IV", "ĐIỀU KHOẢN THI HÀNH")
    assert split_heading("dieu", "ĐIỀU 5. Tên điều") == ("5", "Tên điều")


def test_build_provision_tree_drops_the_pre_amendment_copy():
    # ban cu (display:none) lap lai y het khoan dang hieu luc -> khong duoc dem 2 lan
    nodes = [
        _n("prov-article", "Điều 18. Quyền của tổ chức", id="a18"),
        _n("prov-clause", "4. Bản đang hiệu lực.", id="k4",
           amend_badges=["Điều khoản được sửa đổi, bổ sung"]),
        _n("prov-clause", "4. Bản trước khi sửa đổi.", id="k4old", hidden=True),
    ]
    dieu = build_provision_tree(nodes)[0]
    assert len(dieu["con"]) == 1
    assert dieu["con"][0]["text"] == "Bản đang hiệu lực."


def test_build_provision_tree_creates_articles_that_live_inside_amendment_blocks():
    # Điều 19 không có thẻ prov-article: tiêu đề nằm trong khối sửa đổi (tu_sinh)
    nodes = [
        _n("prov-article", "Điều 18. Quyền của tổ chức", id="a18"),
        _n("prov-clause", "1. Khoản của Điều 18.", id="k18"),
        _n("prov-article", "Điều 19. Trách nhiệm của tổ chức",
           amend_badges=["Điều khoản được sửa đổi, bổ sung"]),
        _n("prov-clause", "1. Khoản của Điều 19.", id="k19"),
    ]
    tree = build_provision_tree(nodes)
    assert [d["so"] for d in tree] == ["18", "19"]
    # khoản sau tiêu đề mới phải thuộc Điều 19, không treo vào Điều 18
    assert tree[1]["con"][0]["text"] == "Khoản của Điều 19."
    assert len(tree[0]["con"]) == 1


def test_build_provision_tree_merges_a_repeated_article_heading():
    # cùng khối sửa đổi xuất hiện 2 lượt trong DOM -> chỉ một nút Điều
    nodes = [
        _n("prov-article", "Điều 15. Quy trình chấp thuận"),
        _n("prov-clause", "1. Quy trình chấp thuận.", id="k1"),
        _n("prov-article", "Điều 15. Quy trình chấp thuận",
           amend_badges=["Điều khoản được sửa đổi, bổ sung"]),
        _n("prov-clause", "2. Quy trình gia hạn.", id="k2"),
    ]
    tree = build_provision_tree(nodes)
    assert len(tree) == 1
    assert [k["so"] for k in tree[0]["con"]] == ["1", "2"]
    # nhãn từ lượt sau vẫn được giữ lại
    assert tree[0]["bi_tac_dong"] == ["sua_doi_bo_sung"]


def test_count_provisions_counts_every_level():
    assert count_provisions(build_provision_tree(PROV_NODES)) == {
        "chuong": 2, "dieu": 3, "khoan": 2, "diem": 2,
    }


def test_build_provision_tree_on_empty_input():
    assert build_provision_tree([]) == []


# --- CorpusDocument ---

def test_to_corpus_document_lay_doc_id_tu_so_hieu():
    doc = to_corpus_document({
        "url": "https://vbpl.vn/van-ban/chi-tiet/tt-15--168089",
        "title": "Thông tư 15/2024/TT-NHNN của Ngân hàng Nhà nước",
        "trang_thai": "Hết hiệu lực một phần",
        "ngay_hieu_luc": "2024-07-01",
        "thuoc_tinh": {
            "so_hieu": "15/2024/TT-NHNN", "loai_van_ban": "Thông tư",
            "nganh": "Ngân hàng", "linh_vuc": "Thanh tra",
            "ngay_ban_hanh": "28/06/2024", "ngay_het_hieu_luc": "",
            "co_quan_ban_hanh": "Ngân hàng Nhà nước Việt Nam",
            "chuc_danh": "Phó Thống đốc", "nguoi_ky": "Phạm Tiến Dũng",
            "tinh_trang_hieu_luc": "Hết hiệu lực một phần",
        },
        "cay_dieu_khoan": build_provision_tree(PROV_NODES),
        "noi_dung": "Điều 1. Phạm vi\nnội dung\nĐiều 2. Đối tượng\n1. Tổ chức.",
    })
    assert doc["doc_id"] == "TT15-2024"             # đúng quy ước corpus
    assert doc["doc_type"] == "Thông tư"
    assert doc["ngay_ban_hanh"] == "2024-06-28"     # dd/mm/yyyy -> ISO
    assert doc["valid_to"] is None                  # "" nghĩa là chưa hết hiệu lực
    assert doc["source_url"].startswith("https://vbpl.vn/")
    assert len(doc["articles"]) == 2 and len(doc["provisions"]) == 2


def test_to_corpus_document_thieu_so_hieu_thi_lui_ve_slug():
    doc = to_corpus_document({
        "url": "https://vbpl.vn/van-ban/chi-tiet/quyet-dinh-la--999",
        "title": "Quyết định lạ", "thuoc_tinh": {}, "cay_dieu_khoan": [],
    })
    assert doc["doc_id"] == "quyet-dinh-la--999"    # không bao giờ được rỗng
    assert doc["so_hieu"] is None


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


# --- Thu muc dich: khong duoc phu thuoc cwd ---
def test_thu_muc_dich_mac_dinh_khong_doi_theo_cwd(tmp_path, monkeypatch):
    """Mặc định neo vào gốc repo, nên `cd` đi đâu cũng ghi về đúng một chỗ.

    Đây là lỗi thật đã xảy ra: cùng một lệnh chạy từ hai checkout anh em ghi ra hai
    thư mục khác nhau, và bản crawl "biến mất" mất cả một lượt đi tìm.
    """
    monkeypatch.delenv("LEXFLOW_VBPL_OUT", raising=False)
    truoc = default_out_dir()
    monkeypatch.chdir(tmp_path)
    assert default_out_dir() == truoc
    assert truoc.is_absolute()
    assert truoc.parts[-3:] == ("data", "raw", "vbpl")


def test_bien_moi_truong_de_len_thu_muc_dich(tmp_path, monkeypatch):
    monkeypatch.setenv("LEXFLOW_VBPL_OUT", str(tmp_path / "kho"))
    assert default_out_dir() == tmp_path / "kho"
    # Cache sitemap đi theo artefact — một biến điều khiển cả hai, không tách ra được.
    assert sitemap_cache_dir() == tmp_path / "kho" / ".sitemap_cache"


def test_bien_moi_truong_rong_thi_coi_nhu_khong_dat(monkeypatch):
    """`$env:LEXFLOW_VBPL_OUT = ""` là cách tắt biến quen tay trên PowerShell — không được
    hiểu thành Path("") tức là cwd."""
    monkeypatch.setenv("LEXFLOW_VBPL_OUT", "   ")
    assert default_out_dir().parts[-3:] == ("data", "raw", "vbpl")


def test_crawl_list_khong_co_hai_url_trung_slug():
    """Hai URL khác nhau mà ra cùng slug thì văn bản sau ĐÈ LÊN văn bản trước, im lặng.

    Rủi ro thật: slug bị cắt còn 80 ký tự, mà tên văn bản NHNN hay trùng nhau ở đoạn đầu
    rất dài. Từ khi `data/raw/vbpl/raw/` không còn được version, danh sách này là nguồn tái
    tạo duy nhất — một vụ đè nhau ở đây là mất hẳn một văn bản.
    """
    danh_sach = Path(__file__).resolve().parents[1] / "research" / "crawl_list.txt"
    urls = [
        ln.strip()
        for ln in danh_sach.read_text(encoding="utf-8-sig").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    slugs = [slug_for(u) for u in urls]
    trung = {s for s in slugs if slugs.count(s) > 1}
    assert not trung, f"slug trùng nhau: {trung}"
    assert len(urls) == len(set(urls))
