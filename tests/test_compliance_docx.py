"""Đọc docx bằng stdlib: đoạn văn, comment, và đoạn nào neo comment nào."""
import zipfile

import pytest

from app.compliance.docx_doc import doc_docx

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
<w:comment w:id="7" w:author="PPC" w:date="2026-05-12T10:40:00Z">
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
    assert binh_luan[0].author == "PPC"
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
