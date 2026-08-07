"""Test extractor văn bản (regex tách điều — offline, không gọi Gemini)."""
from __future__ import annotations

import json

from app.core.schemas import CorpusDocument
from app.ingestion.extract import merge_into_corpus, so_hieu_trong, split_articles

_SAMPLE = """
Mục lục
Tải về
CHÍNH PHỦ
CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Số: 52/2024/NĐ-CP
Chương I QUY ĐỊNH CHUNG
Điều 1. Phạm vi điều chỉnh
Nghị định này quy định về hoạt động thanh toán.
Nội dung tham chiếu Điều 3 Luật Các tổ chức tín dụng không phải điều mới.
Điều 2. Đối tượng áp dụng
Khoản 1. Tổ chức cung ứng dịch vụ.
Khoản 2. Người sử dụng dịch vụ.
Chương II
Điều 3. Giải thích từ ngữ
Ví điện tử là phương tiện lưu trữ tiền điện tử.
TM. CHÍNH PHỦ
THỦ TƯỚNG
Danh sách văn bản liên quan không được lấy.
"""


def test_split_articles_tach_dung_dieu():
    arts = split_articles(_SAMPLE)
    assert [a.article for a in arts] == ["Điều 1", "Điều 2", "Điều 3"]
    # tiêu đề điều nằm đầu text
    assert arts[0].text.startswith("Phạm vi điều chỉnh")
    # tham chiếu chéo "Điều 3 Luật..." không tách thành điều mới
    assert "tham chiếu" in arts[0].text
    # dòng Chương bị loại, chữ ký cắt sạch
    assert "Chương" not in arts[1].text
    assert "THỦ TƯỚNG" not in arts[2].text
    assert "văn bản liên quan" not in arts[2].text


def test_so_hieu_trong_van_ban():
    assert so_hieu_trong("Số: 52/2024/NĐ-CP") == "52/2024/NĐ-CP"
    assert so_hieu_trong("Thông tư 40/2024/TT-NHNN quy định") == "40/2024/TT-NHNN"
    assert so_hieu_trong("ngày 15/5/2024 ban hành") is None, "ngày tháng không phải số hiệu"


def test_so_hieu_khong_con_bi_cat_cut_boi_homoglyph():
    """Khuôn cũ (`[A-ZĐ]+(?:-[A-ZĐ]+)+`) gặp `С` Cyrillic thì lùi lại, im lặng cắt cụt.

    Một khoá cụt tệ hơn không có khoá: `51/2025/TT` vẫn join được — vào nhầm văn bản.
    """
    assert so_hieu_trong("Số: 51/2025/TT-BTС") == "51/2025/TT-BTC"  # С = U+0421


def test_so_hieu_hanh_chinh_khong_co_nam():
    """Khuôn cũ đòi `\\d{4}/` nên bỏ sót TRỌN nhóm hành chính, không một tiếng nào."""
    assert so_hieu_trong("Số: 123/QĐ-NHNN") == "123/QĐ-NHNN"


def test_merge_into_corpus_thay_theo_doc_id(tmp_path):
    out = tmp_path / "corpus.json"
    doc = CorpusDocument(doc_id="TT40-2024", title="TT 40 cũ", doc_type="Thông tư", articles=[])
    merge_into_corpus(doc, out)
    # merge lần 2 cùng doc_id → thay chứ không nhân đôi; relationships giữ nguyên
    data = json.loads(out.read_text(encoding="utf-8"))
    data["relationships"] = [{"source_doc": "TT40-2024", "target_doc": "X", "rel_type": "THAY_THE"}]
    out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    doc2 = CorpusDocument(doc_id="TT40-2024", title="TT 40 mới", doc_type="Thông tư", articles=[])
    merge_into_corpus(doc2, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["documents"]) == 1
    assert data["documents"][0]["title"] == "TT 40 mới"
    assert data["relationships"][0]["rel_type"] == "THAY_THE"
