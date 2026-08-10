"""Nạp lại MỘT văn bản: chỉ đụng chunk của nó, không ghi đè cả bảng.

`write_lancedb` gọi `create_table(mode="overwrite")` — mỗi lần duyệt một văn bản là ghi đè
cả bảng đang phục vụ trong lúc người dùng đang tra, và embed lại toàn bộ chunk không hề đổi
(đo 10/08: 661 chunk ≈ 52s, so với 23 chunk ≈ 1,8s của một thông tư). Đường duyệt cần một
lối khác.
"""
from __future__ import annotations

import pytest

from app.core.schemas import CorpusDocument
from app.ingestion import pipeline


class _FakeTable:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.deleted: list[str] = []
        self.so_lan_dung_fts = 0

    def delete(self, where: str) -> None:
        self.deleted.append(where)
        self.rows = [r for r in self.rows if f"doc_id = '{r['doc_id']}'" != where]

    def add(self, rows) -> None:
        self.rows.extend(rows)

    def create_fts_index(self, cot: str, **kw) -> None:
        self.so_lan_dung_fts += 1


class _FakeDB:
    def __init__(self, bang: dict[str, _FakeTable]):
        self.bang = bang

    def table_names(self):
        return list(self.bang)

    def list_tables(self):
        # Ghim finding critical fix round 1 (10/08): `list_tables()` ném HttpError 400 thật
        # trên LanceDB Cloud của dự án — "PgCatalog::open_database() requires a table name".
        # `ingest_one_doc` PHẢI dùng `table_names()`. Nếu ca này đỏ, ai đó vừa đổi ngược lại.
        raise AssertionError(
            "ingest_one_doc không được gọi list_tables() — nó 400 thật trên LanceDB Cloud, "
            "dùng table_names() thay vào đó"
        )

    def open_table(self, ten: str) -> _FakeTable:
        return self.bang[ten]

    def create_table(self, ten: str, data) -> _FakeTable:
        self.bang[ten] = _FakeTable(data)
        return self.bang[ten]


def _doc(doc_id: str, text: str = "Nội dung.") -> CorpusDocument:
    return CorpusDocument.model_validate(
        {
            "doc_id": doc_id,
            "title": f"Văn bản {doc_id}",
            "doc_type": "Thông tư",
            "source": "external",
            "valid_from": "2026-01-01",
            "articles": [{"article": "Điều 1", "text": text}],
        }
    )


@pytest.fixture
def bang(monkeypatch) -> _FakeTable:
    """Bảng LanceDB giả, đã có sẵn chunk của hai văn bản khác."""
    co_san = [
        {"id": "TT01-2020::Điều 1", "doc_id": "TT01-2020", "text": "a"},
        {"id": "TT02-2021::Điều 1", "doc_id": "TT02-2021", "text": "b"},
    ]
    t = _FakeTable(co_san)
    monkeypatch.setattr("app.core.vectordb.connect", lambda: _FakeDB({pipeline.LANCEDB_TABLE: t}))
    monkeypatch.setattr(pipeline, "_embed_rows", lambda rows: None)
    # Neo4j tắt: Task 3 mới đụng tới nhánh đó
    monkeypatch.setattr(pipeline.settings, "neo4j_uri", "")
    monkeypatch.setattr(pipeline.settings, "neo4j_password", "")
    return t


def test_chi_dung_chunk_cua_van_ban_duoc_nap(bang):
    n = pipeline.ingest_one_doc(_doc("TT99-2026"), [], [_doc("TT99-2026")])
    assert n == 1
    assert bang.deleted == ["doc_id = 'TT99-2026'"]
    con_lai = {r["doc_id"] for r in bang.rows}
    assert con_lai == {"TT01-2020", "TT02-2021", "TT99-2026"}


def test_nap_hai_lan_thi_thay_chu_khong_nhan_doi(bang):
    pipeline.ingest_one_doc(_doc("TT99-2026"), [], [_doc("TT99-2026")])
    pipeline.ingest_one_doc(_doc("TT99-2026", "Nội dung đã sửa."), [], [_doc("TT99-2026")])
    cua_no = [r for r in bang.rows if r["doc_id"] == "TT99-2026"]
    assert len(cua_no) == 1, "delete phải chạy trước add, nếu không chunk cũ nằm lại"
    assert cua_no[0]["text"] == "Nội dung đã sửa."


def test_bang_chua_ton_tai_thi_tao_kem_chi_muc_fts(monkeypatch):
    db = _FakeDB({})
    monkeypatch.setattr("app.core.vectordb.connect", lambda: db)
    monkeypatch.setattr(pipeline, "_embed_rows", lambda rows: None)
    monkeypatch.setattr(pipeline.settings, "neo4j_uri", "")
    monkeypatch.setattr(pipeline.settings, "neo4j_password", "")

    pipeline.ingest_one_doc(_doc("TT99-2026"), [], [_doc("TT99-2026")])

    t = db.bang[pipeline.LANCEDB_TABLE]
    assert len(t.rows) == 1
    assert t.so_lan_dung_fts == 1, "bảng mới mà không dựng chỉ mục thì nhánh BM25 chết lặng"


@pytest.mark.parametrize("xau", ["TT99'; --", "TT 99", "TT99/2026", "", "TT99\n"])
def test_doc_id_ban_bi_chan(xau):
    with pytest.raises(ValueError):
        pipeline.kiem_doc_id(xau)


@pytest.mark.parametrize("tot", ["TT40-2024", "ND101-2012", "SHB.QD_01", "TT23-2019"])
def test_doc_id_that_van_qua(tot):
    assert pipeline.kiem_doc_id(tot) == tot


def test_doc_id_ban_khong_phat_lenh_delete_nao(bang):
    with pytest.raises(ValueError):
        pipeline.ingest_one_doc(_doc("TT99'; --"), [], [])
    assert bang.deleted == [], "phải chặn TRƯỚC khi chạm bảng"


def _gia_lap_graph(monkeypatch) -> list[str]:
    """Ghi lại các bước chạm Neo4j, không gọi Aura thật."""
    da_goi: list[str] = []
    monkeypatch.setattr(pipeline.settings, "neo4j_uri", "neo4j+s://test")
    monkeypatch.setattr(pipeline.settings, "neo4j_password", "test")
    monkeypatch.setattr(
        "app.knowledge.graph.push_one_doc", lambda *a, **k: da_goi.append("push_one_doc")
    )
    monkeypatch.setattr(
        "app.knowledge.graph.push_corpus", lambda *a, **k: da_goi.append("push_corpus")
    )
    monkeypatch.setattr(
        "app.knowledge.graph.push_overlay", lambda goi: (da_goi.append("push_overlay"), (0, 0))[1]
    )
    return da_goi


def test_nap_mot_van_ban_khong_dung_toi_ca_do_thi(bang, monkeypatch):
    da_goi = _gia_lap_graph(monkeypatch)
    pipeline.ingest_one_doc(_doc("TT99-2026"), [], [_doc("TT99-2026")])
    assert da_goi == ["push_one_doc"], (
        "push_corpus mở đầu bằng DETACH DELETE toàn bộ Document — dùng nó ở đây là "
        "xoá sạch 254 cạnh THUOC của lớp phủ để thêm một văn bản"
    )


def test_khong_phai_day_lai_lop_phu(bang, monkeypatch):
    """Hệ quả tốt của việc không DETACH DELETE: THUOC là cạnh ĐI VÀO nên còn nguyên."""
    da_goi = _gia_lap_graph(monkeypatch)
    pipeline.ingest_one_doc(_doc("TT99-2026"), [], [_doc("TT99-2026")])
    assert "push_overlay" not in da_goi
