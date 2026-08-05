"""Cầu **số hiệu → doc_id** và **node rỗng**. Offline, không chạm Neo4j.

Vì sao cần cầu: nguồn chính thống khoá bằng số hiệu (`52/2024/NĐ-CP`), corpus khoá bằng
`doc_id` (`ND52-2024`). Và không có cầu thì hỏng **trong im lặng**, không phải hỏng có tiếng:
`push_corpus` viết `MATCH (a:Document {doc_id}), (b:Document {doc_id})` rồi mới `MERGE`, mà
Cypher `MATCH` không khớp thì cả câu không chạy — 35 cạnh đọc từ vbpl sẽ tạo ra **0 cạnh và
0 lỗi**. Test ở đây canh chính xác ba chỗ dễ hỏng lặng lẽ: bịa `doc_id`, chọn bừa khi trùng
số hiệu, và để node rỗng lọt vào đường truy hồi.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.schemas import CorpusDocument, DocumentMeta, Relationship
from app.ingestion.bac_cau import (
    MUC_UU_TIEN,
    bang_so_hieu,
    quy_ve_doc_id,
    tach_rong,
    thieu_toan_van,
)
from app.ingestion.pipeline import load_corpus
from app.ingestion.vbpl_corpus import tho_theo_so_hieu
from app.ingestion.vbpl_luoc_do import doc_luoc_do, tieu_de_theo_so_hieu

#: Tra theo số hiệu, KHÔNG theo đường dẫn cứng — xem `tho_theo_so_hieu`. Đường dẫn cứng đã ba
#: lần đổi và mỗi lần lại lặng lẽ chuyển cả nhóm test này sang skip.
_GOC = Path("data/raw/vbpl")
_ND52, _TT40 = "52/2024/NĐ-CP", "40/2024/TT-NHNN"


def _tho(so_hieu: str) -> dict:
    return json.loads(tho_theo_so_hieu(_GOC)[so_hieu].read_text(encoding="utf-8"))


def _thieu(*so_hieu: str) -> bool:
    bang = tho_theo_so_hieu(_GOC)
    return any(s not in bang for s in so_hieu)


def _vb(doc_id: str, so_hieu: str | None = None) -> DocumentMeta:
    return DocumentMeta(doc_id=doc_id, title=doc_id, doc_type="Thông tư", so_hieu=so_hieu)


def _canh(src: str, tgt: str, ma: str = "CAN_CU") -> Relationship:
    return Relationship(source_doc=src, target_doc=tgt, rel_type=ma)


# --- 1. Bảng bắc cầu ----------------------------------------------------------


def test_bang_bo_qua_van_ban_khong_khai_so_hieu():
    bang, cb = bang_so_hieu([_vb("A", "1/2020/TT-NHNN"), _vb("B")])
    assert bang == {"1/2020/TT-NHNN": "A"} and cb == []


def test_trung_so_hieu_thi_KHONG_anh_xa_va_bao_ra():
    """Hai văn bản cùng số hiệu là **dữ liệu sai**, không phải ca cần đoán."""
    bang, cb = bang_so_hieu([_vb("A", "1/2020/TT-NHNN"), _vb("B", "1/2020/TT-NHNN")])
    assert bang == {}, "chọn bừa một cái là gieo lỗi vào mọi cạnh dùng số hiệu đó"
    assert len(cb) == 1 and "'A'" in cb[0] and "'B'" in cb[0]


# --- 2. Quy cạnh về doc_id ----------------------------------------------------


def test_dau_mut_co_trong_corpus_thi_quy_ve_doc_id():
    docs = [_vb("ND52-2024", "52/2024/NĐ-CP"), _vb("TT40-2024", "40/2024/TT-NHNN")]
    canh, rong, cb = quy_ve_doc_id([_canh("40/2024/TT-NHNN", "52/2024/NĐ-CP")], docs)
    assert (canh[0].source_doc, canh[0].target_doc) == ("TT40-2024", "ND52-2024")
    assert rong == [] and cb == []


def test_canh_da_khoa_bang_doc_id_thi_giu_nguyen():
    """Corpus hiện tại khoá bằng `doc_id` — hàm này phải chạy được mà không đổi gì."""
    docs = [_vb("ND52-2024", "52/2024/NĐ-CP"), _vb("TT40-2024", "40/2024/TT-NHNN")]
    canh, rong, cb = quy_ve_doc_id([_canh("TT40-2024", "ND52-2024")], docs)
    assert (canh[0].source_doc, canh[0].target_doc) == ("TT40-2024", "ND52-2024")
    assert rong == [] and cb == []


def test_dau_mut_chua_co_thi_thanh_NODE_RONG_giu_nguyen_so_hieu():
    """Node rỗng lấy CHÍNH số hiệu làm `doc_id` — không bịa `ND16-2019`.

    Bịa thì đến lúc crawl thật, văn bản có thể mang `doc_id` khác và sinh ra **hai node cho
    một văn bản** — đúng kiểu hỏng mà `HUONG_DAN` đã gây ra một lần.
    """
    docs = [_vb("ND52-2024", "52/2024/NĐ-CP")]
    canh, rong, _ = quy_ve_doc_id([_canh("52/2024/NĐ-CP", "16/2019/NĐ-CP", "BAI_BO")], docs)
    assert canh[0].target_doc == "16/2019/NĐ-CP"
    assert [v.so_hieu for v in rong] == ["16/2019/NĐ-CP"]
    assert rong[0].doc_type == "Nghị định", "doc_type suy từ mã loại trong chính số hiệu"


def test_dau_mut_khong_doc_duoc_thanh_so_hieu_thi_bao_chu_khong_dung_node_rong():
    """Dựng node rỗng cho một chuỗi chưa quy được về khoá là **nhân bản cái sai**."""
    canh, rong, cb = quy_ve_doc_id([_canh("A", "một thứ không phải số hiệu")], [])
    assert rong == []
    assert len(cb) == 2 and all("không đọc được thành số hiệu" in c for c in cb)


def test_tieu_de_di_theo_node_rong():
    """Không có tiêu đề thì trên đồ thị nó chỉ là một dãy số — không ai biết đó là gì."""
    _, rong, _ = quy_ve_doc_id(
        [_canh("52/2024/NĐ-CP", "16/2019/NĐ-CP")],
        [_vb("ND52-2024", "52/2024/NĐ-CP")],
        {"16/2019/NĐ-CP": "Nghị định số 16/2019/NĐ-CP Sửa đổi..."},
    )
    assert rong[0].title.startswith("Nghị định số 16/2019")


def test_node_rong_khong_phai_CorpusDocument():
    """Kiểu riêng để chỗ nào nhận nhầm thì hỏng LÚC DỊCH, không phải lúc người dùng đọc."""
    _, rong, _ = quy_ve_doc_id([_canh("A", "16/2019/NĐ-CP")], [_vb("A", "1/2020/TT-NHNN")])
    assert not isinstance(rong[0], CorpusDocument)
    assert not isinstance(rong[0], DocumentMeta)


def test_tach_rong_giu_dung_van_ban_co_dieu_khoan():
    docs = [
        CorpusDocument(doc_id="A", title="A", doc_type="Thông tư", articles=[]),
        CorpusDocument(
            doc_id="B", title="B", doc_type="Thông tư",
            articles=[{"article": "Điều 1", "text": "x"}],
        ),
    ]
    assert [d.doc_id for d in tach_rong(docs)] == ["B"]


# --- 3. Danh sách cần crawl ---------------------------------------------------


def test_uu_tien_theo_HONG_CAI_GI_chu_khong_theo_so_canh():
    """Đo trên dữ liệu thật: 30/30 đầu mút treo đều đúng **1 cạnh** ⇒ xếp theo số cạnh là
    xếp theo một cột hằng số. Thiếu một văn bản `BAI_BO` làm hổng ca kiểm chứng §6.2, còn
    thiếu một văn bản `CAN_CU` thì chỉ mất phần xuất xứ."""
    docs = [_vb("ND52-2024", "52/2024/NĐ-CP")]
    rels = [
        _canh("52/2024/NĐ-CP", "1/2020/TT-NHNN", "CAN_CU"),
        _canh("52/2024/NĐ-CP", "2/2020/TT-NHNN", "BAI_BO"),
        _canh("52/2024/NĐ-CP", "3/2020/TT-NHNN", "THAY_THE"),
    ]
    assert [d.so_hieu for d in thieu_toan_van(rels, docs)] == [
        "2/2020/TT-NHNN", "3/2020/TT-NHNN", "1/2020/TT-NHNN"
    ]


def test_moi_quan_he_deu_co_muc_uu_tien():
    """Thêm quan hệ mới vào `REL_TYPES` mà quên xếp mức thì nó tụt xuống cuối trong im lặng."""
    from app.core.schemas import REL_TYPES

    assert set(MUC_UU_TIEN) == set(REL_TYPES)


def test_ghi_ro_vai_cua_van_ban_con_thieu():
    docs = [_vb("ND52-2024", "52/2024/NĐ-CP")]
    ds = thieu_toan_van([_canh("52/2024/NĐ-CP", "16/2019/NĐ-CP", "BAI_BO")], docs)
    assert ds[0].quan_he == [("BAI_BO", "đích")], "bị bãi bỏ khác hẳn đi bãi bỏ cái khác"


# --- 4. Trên dữ liệu THẬT -----------------------------------------------------


@pytest.mark.skipif(_thieu(_ND52), reason="chưa crawl bản ghi vbpl của ND52")
def test_corpus_that_cong_luoc_do_that():
    """Con số đóng lại toàn bộ việc này: 57 cạnh vào, 32 nối hai văn bản có toàn văn,
    25 nối vào node rỗng, **0 cạnh bị mất**.

    Trước đợt nạp 05/08 là 48/18/30. Số học của bước nạp phải khớp từng phần: +9 cạnh
    curated mới (48→57), 5 văn bản rời tập node rỗng vì đã có toàn văn (30→25: ND16, ND80,
    TT22, TT41, TT66), và 18 + 9 cạnh mới + 5 cạnh vbpl vừa đủ hai đầu = 32."""
    docs, rels_corpus = load_corpus("data/corpus.real.json")
    mau = _tho(_ND52)
    canh_vbpl, _ = doc_luoc_do(mau)
    rels = rels_corpus + canh_vbpl
    canh, rong, cb = quy_ve_doc_id(rels, docs, tieu_de_theo_so_hieu(mau))

    assert len(rels) == 57 and len(canh) == 57, "không cạnh nào được phép rơi"
    assert len(rong) == 25
    assert cb == []

    co = {d.doc_id for d in docs}
    assert sum(1 for c in canh if c.source_doc in co and c.target_doc in co) == 32


def test_moi_van_ban_corpus_deu_khai_so_hieu():
    """Thiếu `so_hieu` là văn bản đó đứng ngoài cầu — cạnh trỏ tới nó thành node rỗng TRÙNG."""
    docs, _ = load_corpus("data/corpus.real.json")
    assert [d.doc_id for d in docs if not d.so_hieu] == []


@pytest.mark.skipif(_thieu(_ND52), reason="chưa crawl bản ghi vbpl của ND52")
def test_ca_BAI_BO_that_da_vao_corpus():
    """Tiền thân của test này canh một cái chặn: ND16/2019 là instance `BAI_BO` duy nhất có
    thật mà corpus chưa có toàn văn, nên truy vấn §6.2 (*khoảng trống lập pháp*) trả rỗng.
    Nó được viết để **đỏ đúng ngày ND16 được nạp** — ngày đó là 05/08, và đây là mặt sau
    của nó: cái chặn phải BIẾN MẤT, kèm cạnh `BAI_BO` mang neo `Điều 3`.
    """
    docs, rels_corpus = load_corpus("data/corpus.real.json")
    mau = _tho(_ND52)
    canh_vbpl, _ = doc_luoc_do(mau)
    ds = thieu_toan_van(rels_corpus + canh_vbpl, docs, tieu_de_theo_so_hieu(mau))
    assert all(d.so_hieu != "16/2019/NĐ-CP" for d in ds), "ND16 đã có toàn văn, hết thiếu"

    bai_bo = [r for r in rels_corpus if r.rel_type == "BAI_BO"]
    assert [(r.source_doc, r.target_doc) for r in bai_bo] == [("ND52-2024", "ND16-2019")]
    assert [(a.source_article, a.target_article) for a in bai_bo[0].anchors] == [
        ("Điều 37", "Điều 3")
    ], "bãi bỏ MỘT PHẦN: đúng Điều 3 (phần sửa ND101), ND16 sống các điều còn lại"


@pytest.mark.skipif(_thieu(_ND52, "66/2025/TT-NHNN"),
                    reason="cần bản ghi vbpl của cả ND52 và TT66")
def test_mot_luoc_do_KHONG_du_de_biet_van_ban_da_bi_sua_chua():
    """Lược đồ của một văn bản chỉ chứa quan hệ **với chính nó** — và điều đó che mất sự thật.

    Ca phát hiện ra bài học này (TT41/2025 qua lược đồ TT40) đã được nạp vào corpus 05/08 nên
    hết dùng làm bằng chứng; ca thay thế cùng hình dạng: trong lược đồ NĐ52, `34/2024/TT-NHNN`
    chỉ hiện ra là văn bản *quy định chi tiết* (ưu tiên 2). Thêm lược đồ của **TT66/2025** thì
    nó lộ ra là văn bản **bị sửa đổi** — và còn bị `THAY_THE` — ưu tiên nhảy lên 1.

    Test này khoá lại kết luận rút ra từ đó: **crawl từng văn bản corpus**, không chỉ đầu mút.
    """
    docs, rels_corpus = load_corpus("data/corpus.real.json")

    # Neo vào ĐÚNG hai văn bản, không phải cả thư mục: thư mục lớn dần theo mỗi đợt crawl, và
    # một test đổi kết quả theo số file thì không còn kiểm được điều nó định kiểm.
    chi_nd52, _ = doc_luoc_do(_tho(_ND52))
    tt66, _ = doc_luoc_do(_tho("66/2025/TT-NHNN"))

    ds1 = {d.so_hieu: d for d in thieu_toan_van(rels_corpus + chi_nd52, docs)}
    assert [m for m, _ in ds1["34/2024/TT-NHNN"].quan_he] == ["QUY_DINH_CHI_TIET_HUONG_DAN"]
    assert ds1["34/2024/TT-NHNN"].uu_tien == 2, "một lược đồ ⇒ tưởng chỉ là văn bản hướng dẫn"

    ds2 = {d.so_hieu: d for d in thieu_toan_van(rels_corpus + chi_nd52 + tt66, docs)}
    assert "SUA_DOI_BO_SUNG" in [m for m, _ in ds2["34/2024/TT-NHNN"].quan_he]
    assert ds2["34/2024/TT-NHNN"].uu_tien == 1, "hai lược đồ ⇒ hoá ra nó BỊ SỬA ĐỔI"


@pytest.mark.skipif(_thieu(_ND52), reason="chưa crawl bản ghi vbpl của ND52")
def test_homoglyph_duoc_sua_o_KHOA_nhung_giu_nguyen_o_TIEU_DE():
    """Khoá phải sạch để join đúng; tiêu đề là **bản gốc**, sửa nó là sửa dữ liệu nguồn."""
    td = tieu_de_theo_so_hieu(_tho(_ND52))
    assert "51/2025/TT-BTC" in td
    assert "TT-BTС" in td["51/2025/TT-BTC"], "С Cyrillic (U+0421) còn nguyên trong tiêu đề"
