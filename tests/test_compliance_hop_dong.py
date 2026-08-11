"""Cắt hợp đồng docx thành điều — nhận 'Điều N' lẫn 'ĐIỀU N'."""
import zipfile

from app.compliance.hop_dong import dieu_chua_doan, parse_hop_dong, to_corpus_document

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_CONTENT_TYPES = (
    '<?xml version="1.0"?><Types '
    'xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>'
)


def _mini_docx(tmp_path, paragraphs):
    body = "".join(f"<w:p><w:r><w:t>{t}</w:t></w:r></w:p>" for t in paragraphs)
    doc = (f'<?xml version="1.0"?><w:document xmlns:w="{_W}">'
           f"<w:body>{body}</w:body></w:document>")
    p = tmp_path / "hd.docx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("word/document.xml", doc)
    return p


def _mini_docx_so(tmp_path, items, lvltext="ĐIỀU %1."):
    """items: list[(text, num_id|None, ilvl|None)] — tái tạo heading đánh số tự động
    của Word (numPr trỏ vào numbering.xml có lvlText "ĐIỀU %1."), số không nằm trong
    text chạy — đúng cấu trúc thấy trên 2 hợp đồng thật (docs/compliance/*.docx)."""
    def p_xml(text, num_id, ilvl):
        ppr = ""
        if num_id is not None:
            ppr = (f'<w:pPr><w:numPr><w:ilvl w:val="{ilvl or 0}"/>'
                   f'<w:numId w:val="{num_id}"/></w:numPr></w:pPr>')
        return f"<w:p>{ppr}<w:r><w:t>{text}</w:t></w:r></w:p>"

    body = "".join(p_xml(*it) for it in items)
    doc = (f'<?xml version="1.0"?><w:document xmlns:w="{_W}">'
           f"<w:body>{body}</w:body></w:document>")
    num_ids = sorted({it[1] for it in items if it[1] is not None})
    nums_xml = "".join(
        f'<w:num w:numId="{n}"><w:abstractNumId w:val="{n}"/></w:num>' for n in num_ids
    )
    abs_xml = "".join(
        f'<w:abstractNum w:abstractNumId="{n}">'
        f'<w:lvl w:ilvl="0"><w:lvlText w:val="{lvltext}"/></w:lvl>'
        f"</w:abstractNum>" for n in num_ids
    )
    numbering = (f'<?xml version="1.0"?><w:numbering xmlns:w="{_W}">'
                 f"{abs_xml}{nums_xml}</w:numbering>")
    p = tmp_path / "hd.docx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("word/document.xml", doc)
        z.writestr("word/numbering.xml", numbering)
    return p


def test_cat_dieu(tmp_path):
    p = _mini_docx(tmp_path, [
        "HỢP ĐỒNG DỊCH VỤ", "Điều 1. Phạm vi", "Nội dung phạm vi.",
        "ĐIỀU 2: Phí dịch vụ", "Mức phí do hai bên thỏa thuận.",
    ])
    hd = parse_hop_dong(p)
    assert [d.so for d in hd.dieu] == ["1", "2"]
    assert hd.dieu[0].tieu_de == "Phạm vi"
    assert "Nội dung phạm vi." in hd.dieu[0].text
    assert hd.dieu[1].doan == (3, 5)


def test_map_doan_sang_dieu(tmp_path):
    p = _mini_docx(tmp_path, ["Điều 1. A", "thân điều 1", "Điều 2. B", "thân điều 2"])
    hd = parse_hop_dong(p)
    assert dieu_chua_doan(hd, 1).so == "1"
    assert dieu_chua_doan(hd, 3).so == "2"


def test_to_corpus_document(tmp_path):
    p = _mini_docx(tmp_path, ["Điều 1. A", "thân"])
    doc = to_corpus_document(parse_hop_dong(p))
    assert doc.articles[0].article == "Điều 1"
    assert "thân" in doc.articles[0].text


def test_dieu_danh_so_tu_dong_numpr(tmp_path):
    """Heading đánh số tự động (numPr) — số nằm trong numbering.xml, không trong text
    chạy. ilvl=1 trên cùng numId là khoản lồng bên trong, không phải điều mới."""
    p = _mini_docx_so(tmp_path, [
        ("HỢP ĐỒNG DỊCH VỤ", None, None),
        ("Phạm vi", 5, 0),
        ("Nội dung phạm vi.", None, None),
        ("Chi tiết mục con.", 5, 1),
        ("Phí dịch vụ", 5, 0),
        ("Mức phí do hai bên thỏa thuận.", None, None),
    ])
    hd = parse_hop_dong(p)
    assert [d.so for d in hd.dieu] == ["1", "2"]
    assert hd.dieu[0].tieu_de == "Phạm vi"


def test_so_dieu_lien_tuc_qua_nhieu_numid(tmp_path):
    """Word thường tạo numId mới mỗi lần dán/sửa (không phải khởi động lại mục lục
    thật) — vẫn phải đếm liên tục 1..N theo thứ tự tài liệu."""
    p = _mini_docx_so(tmp_path, [
        ("A", 3, 0), ("thân 1", None, None),
        ("B", 3, 0), ("thân 2", None, None),
        ("C", 9, 0), ("thân 3", None, None),
    ])
    hd = parse_hop_dong(p)
    assert [d.so for d in hd.dieu] == ["1", "2", "3"]


def test_dong_bo_bo_dem_khi_gap_so_thu_cong(tmp_path):
    """Heading gõ tay 'Điều 4.' xen giữa các heading tự động phải đồng bộ lại bộ đếm,
    khớp với ca thật (HD_DVThuHoCoLK.docx: 1 heading gõ tay giữa các heading numPr)."""
    p = _mini_docx_so(tmp_path, [
        ("A", 7, 0), ("thân 1", None, None),
        ("B", 7, 0), ("thân 2", None, None),
        ("Điều 4. C", None, None), ("thân 3", None, None),
        ("D", 7, 0), ("thân 4", None, None),
    ])
    hd = parse_hop_dong(p)
    assert [d.so for d in hd.dieu] == ["1", "2", "4", "5"]


def test_so_thu_cong_lac_hau_khong_keo_lui_bo_dem(tmp_path):
    """Số gõ tay lạc hậu hơn bộ đếm (lỗi soạn thảo, ca thật HD_DVThuHoCoLK.docx: 1
    heading 'Điều 4.' ở vị trí thứ 26) không được kéo lùi và làm trùng số hàng loạt."""
    p = _mini_docx_so(tmp_path, [
        ("A", 1, 0), ("thân 1", None, None),
        ("B", 1, 0), ("thân 2", None, None),
        ("C", 1, 0), ("thân 3", None, None),
        ("Điều 1. D", None, None),  # lạc hậu: bộ đếm đã ở 3
        ("thân 4", None, None),
        ("E", 1, 0), ("thân 5", None, None),
    ])
    hd = parse_hop_dong(p)
    assert [d.so for d in hd.dieu] == ["1", "2", "3", "1", "4"]


def test_khong_nham_dieu_kien_hay_dan_chieu_thanh_dieu_moi(tmp_path):
    """'Điều kiện ...' (không có số) và dẫn chiếu giữa câu không được coi là điều mới."""
    p = _mini_docx(tmp_path, [
        "Điều 1. A",
        "Điều kiện áp dụng như sau.",
        "Xem thêm quy định tại Điều 5 Nghị định 01.",
        "Điều 2. B",
    ])
    hd = parse_hop_dong(p)
    assert [d.so for d in hd.dieu] == ["1", "2"]
