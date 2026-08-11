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
