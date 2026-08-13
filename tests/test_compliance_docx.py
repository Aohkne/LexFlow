"""Đọc docx bằng stdlib: đoạn văn, comment, và đoạn nào neo comment nào."""
import zipfile

import pytest

from app.compliance.docx_doc import doc_docx, doc_numbering

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

_DOCUMENT = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="{_W}"><w:body>
<w:p><w:r><w:t>Điều 1. Phạm vi</w:t></w:r></w:p>
<w:p><w:commentRangeStart w:id="7"/><w:r><w:t>Bên B thanh toán trong 3 ngày.</w:t></w:r>
<w:commentRangeEnd w:id="7"/></w:p>
<w:p><w:r><w:t>Điều 2. Phí</w:t></w:r></w:p>
</w:body></w:document>"""

_COMMENTS = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:comments xmlns:w="{_W}">
<w:comment w:id="7" w:author="Pháp chế" w:date="2026-05-12T10:40:00Z">
<w:p><w:r><w:t>Nên là ngày làm việc.</w:t></w:r></w:p></w:comment>
</w:comments>"""

_CONTENT_TYPES = (
    '<?xml version="1.0"?><Types '
    'xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>'
)


@pytest.fixture
def docx(tmp_path):
    p = tmp_path / "mini.docx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("word/document.xml", _DOCUMENT)
        z.writestr("word/comments.xml", _COMMENTS)
    return p


def test_doc_du_doan_va_comment(docx):
    doan, binh_luan = doc_docx(docx)
    assert [d.text for d in doan] == [
        "Điều 1. Phạm vi", "Bên B thanh toán trong 3 ngày.", "Điều 2. Phí",
    ]
    assert doan[1].comment_ids == ["7"] and doan[0].comment_ids == []
    assert binh_luan[0].author == "Pháp chế"
    assert binh_luan[0].text == "Nên là ngày làm việc."


def test_docx_khong_comment(tmp_path):
    p = tmp_path / "trong.docx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("word/document.xml", _DOCUMENT)
    doan, binh_luan = doc_docx(p)
    assert len(doan) == 3 and binh_luan == []


_DOCUMENT_KHONG_DONG = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="{_W}"><w:body>
<w:p><w:r><w:t>Điều 1. Phạm vi</w:t></w:r></w:p>
<w:p><w:commentRangeStart w:id="9"/><w:r><w:t>Bên B thanh toán trong 3 ngày.</w:t></w:r></w:p>
<w:p><w:r><w:t>Điều 2. Phí</w:t></w:r></w:p>
</w:body></w:document>"""


def test_docx_comment_range_khong_dong(tmp_path):
    p = tmp_path / "khong_dong.docx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("word/document.xml", _DOCUMENT_KHONG_DONG)
    with pytest.warns(UserWarning, match="không đóng"):
        doan, binh_luan = doc_docx(p)
    assert doan[0].comment_ids == []
    assert doan[1].comment_ids == ["9"]
    assert doan[2].comment_ids == ["9"]  # leak fail-open: đoạn sau start đều bị neo


def test_doan_van_mang_num_id_va_doc_numbering_doc_lvltext(tmp_path):
    """DoanVan lộ numId/ilvl thô; doc_numbering đọc lvlText cấp 0 từ numbering.xml —
    dùng cho heading đánh số tự động (số không nằm trong text chạy)."""
    doc = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="{_W}"><w:body>
<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="5"/></w:numPr></w:pPr>
<w:r><w:t>Phạm vi</w:t></w:r></w:p>
<w:p><w:r><w:t>Nội dung.</w:t></w:r></w:p>
</w:body></w:document>"""
    numbering = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:numbering xmlns:w="{_W}">
<w:abstractNum w:abstractNumId="5"><w:lvl w:ilvl="0"><w:lvlText w:val="ĐIỀU %1."/></w:lvl></w:abstractNum>
<w:num w:numId="5"><w:abstractNumId w:val="5"/></w:num>
</w:numbering>"""
    p = tmp_path / "num.docx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("word/document.xml", doc)
        z.writestr("word/numbering.xml", numbering)
    doan, _ = doc_docx(p)
    assert doan[0].num_id == "5" and doan[0].ilvl == "0"
    assert doan[1].num_id is None
    assert doc_numbering(p) == {"5": "ĐIỀU %1."}
