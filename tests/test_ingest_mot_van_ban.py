"""Nạp lại MỘT văn bản: chỉ đụng chunk của nó, không ghi đè cả bảng.

`write_lancedb` gọi `create_table(mode="overwrite")` — mỗi lần duyệt một văn bản là ghi đè
cả bảng đang phục vụ trong lúc người dùng đang tra, và embed lại toàn bộ chunk không hề đổi
(đo 10/08: 661 chunk ≈ 52s, so với 23 chunk ≈ 1,8s của một thông tư). Đường duyệt cần một
lối khác.
"""
from __future__ import annotations

import re
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.schemas import CorpusDocument, Relationship
from app.ingestion import pipeline


class _FakeTable:
    """Bảng giả khoá theo `id` — khớp `_ghi_chunk`, vốn xoá bằng `id IN (…)` chứ không phải
    `doc_id = …`. Giữ `deleted` để ca test còn khẳng định được phạm vi xoá."""

    def __init__(self, rows=None):
        self.hang = {r["id"]: dict(r) for r in (rows or [])}
        self.deleted: list[str] = []
        self.so_lan_dung_fts = 0
        self.so_lan_wait_for_index = 0

    # --- đọc ---
    @property
    def schema(self):
        return [SimpleNamespace(name=k) for k in ("id", "doc_id", "text", "vector")]

    def count_rows(self) -> int:
        return len(self.hang)

    def search(self, *a, **kw):
        return _FakeTruyVan(list(self.hang.values()))

    def list_indices(self):
        return [SimpleNamespace(name="text_idx", index_type="FTS", num_indexed_rows=len(self.hang))]

    def wait_for_index(self, ten, **kw) -> None:
        self.so_lan_wait_for_index += 1

    # --- ghi ---
    def delete(self, where: str) -> None:
        self.deleted.append(where)
        m = re.match(r"^id IN \((.*)\)$", where)
        assert m, f"cú pháp delete lạ, cloud có thể không nhận: {where!r}"
        for i in {s.strip()[1:-1].replace("''", "'") for s in m.group(1).split(", ")}:
            self.hang.pop(i, None)

    def merge_insert(self, khoa: str):
        assert khoa == "id", f"khoá merge phải là id, không phải {khoa!r}"
        return _FakeMerge(self)

    def add(self, rows) -> None:
        raise AssertionError("tầng ghi dùng merge_insert, không phải add")

    def create_fts_index(self, cot: str, **kw) -> None:
        self.so_lan_dung_fts += 1


class _FakeTruyVan:
    def __init__(self, hang): self._hang, self._cot, self._gioi_han = hang, None, None

    def where(self, dieu_kien: str):
        m = re.match(r"^doc_id IN \((.*)\)$", dieu_kien)
        assert m, f"cú pháp where lạ: {dieu_kien!r}"
        ids = {s.strip()[1:-1] for s in m.group(1).split(", ")}
        self._hang = [r for r in self._hang if r.get("doc_id") in ids]
        return self

    def select(self, cot):
        self._cot = list(cot)
        return self

    def limit(self, n):
        self._gioi_han = n
        return self

    def to_list(self):
        ra = self._hang[: self._gioi_han] if self._gioi_han else list(self._hang)
        if self._cot is None:
            return [dict(r) for r in ra]
        return [{k: r[k] for k in self._cot} for r in ra]


class _FakeMerge:
    def __init__(self, bang): self._bang = bang
    def when_matched_update_all(self): return self
    def when_not_matched_insert_all(self): return self
    def execute(self, rows) -> None:
        for r in rows:
            self._bang.hang[r["id"]] = dict(r)


class _FakeDB:
    def __init__(self, bang: dict[str, _FakeTable]):
        self.bang = bang
        self.da_goi_table_names = False

    def table_names(self):
        # Không còn ai được phép gọi: phép dò giờ là `open_table`. Cờ này để ca test NÓI RA
        # điều đó thay vì im lặng chấp nhận.
        self.da_goi_table_names = True
        return list(self.bang)

    def list_tables(self):
        # Ghim finding critical fix round 1 (10/08): `list_tables()` ném HttpError 400 thật
        # trên LanceDB Cloud của dự án — "PgCatalog::open_database() requires a table name".
        raise AssertionError(
            "ingest_one_doc không được gọi list_tables() — nó 400 thật trên LanceDB Cloud"
        )

    def open_table(self, ten: str) -> _FakeTable:
        if ten not in self.bang:
            # Đúng loại và đúng thông điệp lancedb ném thật — đo 13/08 trên CẢ nhúng lẫn cloud,
            # đo lại 14/08 trên DB tạm. Chuỗi do lõi Rust ném, không có dòng Python để trỏ;
            # xem khối chú thích ở nhánh `except ValueError` của `write_lancedb`.
            raise ValueError(f"Table '{ten}' was not found")
        return self.bang[ten]

    def create_table(self, ten: str, data) -> _FakeTable:
        # KHÔNG nhận `**kw`: nuốt kwargs thì một lượt hồi quy đưa `mode="overwrite"` trở lại sẽ
        # đi qua đây trong im lặng. Chữ ký hẹp khiến nó `TypeError` — giống bảng giả anh em ở
        # `test_ingest_tang_dan.py`. Và ném khi trùng tên vì lancedb thật ném (`ValueError:
        # Table 'chunks' already exists`, đo 14/08): đó CHÍNH LÀ tính chất "hỏng ồn ào" mà
        # `_tao_bang_moi` dựa vào khi bỏ `mode="overwrite"` — bảng giả ghi đè êm ru thì test
        # không còn kiểm được điều nó tưởng đang kiểm.
        if ten in self.bang:
            raise ValueError(f"Table '{ten}' already exists")
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
    # `db` dựng MỘT LẦN ở đây rồi đóng gói vào lambda — không phải `lambda: _FakeDB({...})`,
    # thứ tạo một đối tượng MỚI mỗi lần `connect()` được gọi. Ca dò bảng cần `connect()` trả
    # về CÙNG một `_FakeDB` mỗi lần, để cờ `da_goi_table_names` đọc từ bên ngoài phản ánh đúng
    # lời gọi `ingest_one_doc` làm bên trong.
    db = _FakeDB({pipeline.LANCEDB_TABLE: t})
    monkeypatch.setattr("app.core.vectordb.connect", lambda: db)
    monkeypatch.setattr(pipeline, "_embed_rows", lambda rows: None)
    # Neo4j tắt: Task 3 mới đụng tới nhánh đó
    monkeypatch.setattr(pipeline.settings, "neo4j_uri", "")
    monkeypatch.setattr(pipeline.settings, "neo4j_password", "")
    return t


def test_chi_dung_chunk_cua_van_ban_duoc_nap(bang):
    n = pipeline.ingest_one_doc(_doc("TT99-2026"), [], [_doc("TT99-2026")])
    assert n == 1
    # TT99-2026 chưa có chunk nào trong bảng trước đó ⇒ không id nào mồ côi, `delete` không
    # chạy. Ghim TÍNH CHẤT (không xoá lố sang chunk văn bản khác) thay vì đếm lệnh xoá.
    assert bang.deleted == []
    con_lai = {r["doc_id"] for r in bang.hang.values()}
    assert con_lai == {"TT01-2020", "TT02-2021", "TT99-2026"}


def test_ingest_one_doc_khong_cho_khong_dung_lai_index_tren_duong_bang_da_ton_tai(bang):
    """Ruling finding #1: `_cho_index` bị đưa RA KHỎI `_ghi_chunk`; `ingest_one_doc` không gọi nó.

    Chờ index ở đường `/approve` là đổi một khiếm khuyết TẠM THỜI (13 giây mù BM25, đã đo, đã
    chấp nhận) lấy một lượt CHỜ đồng bộ chặn HTTP — đúng thứ việc tách `_cho_index` ra khỏi
    `_ghi_chunk` sinh ra để tránh. Ca này ĐỎ trên bản trước khi sửa finding #1 (khi `_ghi_chunk`
    còn gọi `_cho_index(tbl)` ở bước cuối) qua `so_lan_dung_fts`, KHÔNG qua `so_lan_wait_for_index`:
    fixture để `lancedb_uri` rỗng ⇒ `lancedb_cloud_enabled` False (`app/core/config.py:64-65`) ⇒
    `_cho_index` dừng ở nhánh nhúng `create_fts_index(replace=True)` và không bao giờ tới
    `wait_for_index`. Vẫn khẳng định CẢ HAI bộ đếm là cố ý — nhánh nào chạy tuỳ môi trường, mà
    kết luận "đường duyệt không đụng index" thì phải đúng ở cả hai.
    """
    pipeline.ingest_one_doc(_doc("TT99-2026"), [], [_doc("TT99-2026")])
    assert bang.so_lan_wait_for_index == 0
    assert bang.so_lan_dung_fts == 0


def test_nap_hai_lan_thi_thay_chu_khong_nhan_doi(bang):
    pipeline.ingest_one_doc(_doc("TT99-2026"), [], [_doc("TT99-2026")])
    pipeline.ingest_one_doc(_doc("TT99-2026", "Nội dung đã sửa."), [], [_doc("TT99-2026")])
    cua_no = [r for r in bang.hang.values() if r["doc_id"] == "TT99-2026"]
    # Nhãn "Điều 1" không đổi giữa hai lượt ⇒ `merge_insert` khớp theo id và THAY tại chỗ,
    # không phải delete+add nữa — nhưng tính chất phải giữ nguyên: một hàng, nội dung mới nhất.
    assert len(cua_no) == 1, "merge_insert khớp theo id phải thay chứ không nhân đôi hàng"
    assert cua_no[0]["text"] == "Nội dung đã sửa."


def test_bang_chua_ton_tai_thi_tao_kem_chi_muc_fts(monkeypatch):
    db = _FakeDB({})
    monkeypatch.setattr("app.core.vectordb.connect", lambda: db)
    monkeypatch.setattr(pipeline, "_embed_rows", lambda rows: None)
    monkeypatch.setattr(pipeline.settings, "neo4j_uri", "")
    monkeypatch.setattr(pipeline.settings, "neo4j_password", "")

    pipeline.ingest_one_doc(_doc("TT99-2026"), [], [_doc("TT99-2026")])

    t = db.bang[pipeline.LANCEDB_TABLE]
    assert len(t.hang) == 1
    assert t.so_lan_dung_fts == 1, "bảng mới mà không dựng chỉ mục thì nhánh BM25 chết lặng"


def test_ingest_one_doc_khong_goi_table_names_cung_khong_goi_list_tables(bang, monkeypatch):
    """Phép dò bảng là `open_table`, không phải liệt kê rồi so tên.

    `list_tables()` ném HttpError 400 thật trên LanceDB Cloud của dự án (đo 10/08);
    `table_names()` thì deprecated và có phân trang, nên "không thấy tên" lẫn với "bảng không
    tồn tại" — mà nhánh sau dẫn thẳng tới dựng đè bảng đang phục vụ. `open_table` tránh cả hai.
    """
    db = pipeline.vectordb.connect()
    pipeline.ingest_one_doc(_doc("TT99-2026"), [], [_doc("TT99-2026")])
    assert db.da_goi_table_names is False


def test_loi_tam_thoi_luc_mo_bang_thi_nem_chu_khong_dung_de_bang_moi(monkeypatch):
    """Trục trặc mạng KHÔNG được hiểu thành "bảng chưa có" rồi dựng đè bảng thật.

    `ValueError` là built-in dùng cho vô số lý do; bắt trần nó là mở đúng cánh cửa này.
    """
    class _DbHong:
        def open_table(self, ten):
            raise ValueError("connection reset by peer")
        def create_table(self, *a, **kw):
            raise AssertionError("không được dựng bảng mới khi lỗi chưa chắc là thiếu bảng")

    monkeypatch.setattr("app.core.vectordb.connect", lambda: _DbHong())
    monkeypatch.setattr(pipeline, "_embed_rows", lambda rows: None)
    monkeypatch.setattr(pipeline.settings, "neo4j_uri", "")
    monkeypatch.setattr(pipeline.settings, "neo4j_password", "")

    with pytest.raises(ValueError, match="connection reset"):
        pipeline.ingest_one_doc(_doc("TT99-2026"), [], [_doc("TT99-2026")])


def test_loi_not_found_ve_bang_khac_thi_nem_chu_khong_tao_bang_moi(monkeypatch):
    """`ValueError` chứa "not found" nhưng KHÔNG PHẢI về bảng `chunks` thì phải ném lên.

    Bộ lọc cũ chỉ soi chữ "not found" nên nuốt luôn ca này rồi ghi đè cả bảng thật; bộ lọc mới
    đòi khớp cả tên bảng.

    Thông điệp trong test là ca DỰNG, không phải ca đã thấy: trên lancedb 0.34.0 chưa đo được
    `ValueError` nào khác từ `open_table` mà chứa "not found" (`select` sai cột ném
    `RuntimeError: lance error: ... No field named nope.` — khác lớp, không lọt vào `except`).
    Ca này ghim HÀNH VI của bộ lọc trước một tập thông điệp không liệt kê hết được, chứ không
    tái hiện một lỗi thật.
    """
    class _DbLoiCot:
        def open_table(self, ten):
            raise ValueError("Column 'x' was not found")
        def create_table(self, *a, **kw):
            raise AssertionError("không được dựng bảng mới khi lỗi không phải về bảng chunks")

    monkeypatch.setattr("app.core.vectordb.connect", lambda: _DbLoiCot())
    monkeypatch.setattr(pipeline, "_embed_rows", lambda rows: None)
    monkeypatch.setattr(pipeline.settings, "neo4j_uri", "")
    monkeypatch.setattr(pipeline.settings, "neo4j_password", "")

    with pytest.raises(ValueError, match="Column 'x' was not found"):
        pipeline.ingest_one_doc(_doc("TT99-2026"), [], [_doc("TT99-2026")])


def test_bang_chua_co_van_len_do_thi(monkeypatch):
    """Bảng CHƯA TỒN TẠI + văn bản có điều ⇒ `push_one_doc` vẫn phải được gọi.

    Lỗ có thật trong bản đầu của lần rút này (fix round 2, do coordinator phát hiện): nhánh
    "chưa có bảng" `return` sớm, nhảy cóc qua khối Neo4j cho MỌI văn bản đi qua đường đó — không
    chỉ văn bản rỗng. Lần ingest đầu trên một môi trường mới (bảng LanceDB chưa tồn tại) dựng
    được bảng nhưng đồ thị không bao giờ biết văn bản này tồn tại, mà API vẫn trả 200 approved.
    `_bat_push_one_doc` (định nghĩa dưới) tự bật `neo4j_uri`/`neo4j_password`.
    """
    monkeypatch.setattr("app.core.vectordb.connect", lambda: _FakeDB({}))
    monkeypatch.setattr(pipeline, "_embed_rows", lambda rows: None)
    ghi = _bat_push_one_doc(monkeypatch)

    pipeline.ingest_one_doc(_doc("TT99-2026"), [], [_doc("TT99-2026")])

    assert ghi["doc"].doc_id == "TT99-2026", "push_one_doc phải chạy dù bảng LanceDB vừa mới dựng"


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


# --- Cái gì được TRUYỀN XUỐNG push_one_doc (lọc cạnh, node rỗng, văn bản 0 điều) ---


def _bat_push_one_doc(monkeypatch) -> dict:
    """Bắt tham số truyền xuống `push_one_doc`. Thân hàm có ca riêng ở cuối file."""
    ghi: dict = {}
    monkeypatch.setattr(pipeline.settings, "neo4j_uri", "neo4j+s://test")
    monkeypatch.setattr(pipeline.settings, "neo4j_password", "test")
    monkeypatch.setattr(
        "app.knowledge.graph.push_one_doc",
        lambda doc, rels, rong=None, canh_vao=None, dau_mut_that=None: ghi.update(
            doc=doc, rels=rels, rong=rong, canh_vao=canh_vao, dau_mut_that=dau_mut_that
        ),
    )
    return ghi


def test_canh_di_vao_nhap_luc_duyet_van_toi_do_thi(bang, monkeypatch):
    """`approve_document` nhận `relationships` tự do — không gì buộc `source_doc == doc_id`.

    Cạnh đi vào nhập ở ô JSON của admin vào được `corpus.json` và hiện trên `/docs/[docId]`;
    lọc theo mỗi `source_doc` là nó lặng lẽ không bao giờ tới Neo4j. `push_corpus` (đường CLI)
    thì dựng nó.
    """
    ghi = _bat_push_one_doc(monkeypatch)
    doc, khac, dich = _doc("TT99-2026"), _doc("TT01-2020"), _doc("TT02-2021")
    vao = Relationship(source_doc="TT01-2020", target_doc="TT99-2026", rel_type="SUA_DOI_BO_SUNG")
    ra = Relationship(source_doc="TT99-2026", target_doc="TT02-2021", rel_type="DAN_CHIEU")

    pipeline.ingest_one_doc(doc, [vao, ra], [doc, khac, dich])

    assert [(c.source_doc, c.target_doc) for c in ghi["rels"]] == [("TT99-2026", "TT02-2021")]
    assert [(c.source_doc, c.target_doc) for c in ghi["canh_vao"]] == [("TT01-2020", "TT99-2026")]


def test_nguon_ngoai_corpus_cua_canh_di_vao_duoc_dung_node_rong(bang, monkeypatch):
    ghi = _bat_push_one_doc(monkeypatch)
    doc = _doc("TT99-2026")
    vao = Relationship(source_doc="52/2024/NĐ-CP", target_doc="TT99-2026", rel_type="BAI_BO")

    pipeline.ingest_one_doc(doc, [vao], [doc])

    assert [v.so_hieu for v in ghi["rong"]] == ["52/2024/NĐ-CP"], (
        "_merge_canh khớp hai đầu bằng MATCH — thiếu node nguồn thì Cypher bỏ qua cả câu "
        "trong im lặng, đúng kiểu hỏng phải đọc mới thấy"
    )


def test_nguon_that_cua_canh_di_vao_duoc_dung_node_that_chu_khong_phai_node_rong(
    bang, monkeypatch
):
    """Nguồn là văn bản THẬT trong corpus nhưng có thể chưa lên đồ thị.

    Xảy ra khi lượt duyệt trước chạy lúc `neo4j_enabled` tắt, hoặc Aura rớt giữa chừng (ca
    `SessionExpired` có thật 10/08). Khi đó `_merge_canh` không khớp được vế `MATCH` bên nguồn
    và Cypher bỏ cả câu trong im lặng — cạnh không bao giờ tồn tại, mà `ingest_one_doc` vẫn in
    ra như đã ghi. Nó phải được `_merge_doc` (`co_toan_van=true`), KHÔNG phải `VanBanRong`:
    node rỗng cho văn bản đã có toàn văn là phá bất biến của `bac_cau`.
    """
    ghi = _bat_push_one_doc(monkeypatch)
    doc, nguon = _doc("TT99-2026"), _doc("TT01-2020")
    vao = Relationship(source_doc="TT01-2020", target_doc="TT99-2026", rel_type="SUA_DOI_BO_SUNG")

    pipeline.ingest_one_doc(doc, [vao], [doc, nguon])

    assert [d.doc_id for d in ghi["dau_mut_that"]] == ["TT01-2020"]
    assert ghi["rong"] == [], "TT01-2020 có toàn văn — dựng node rỗng cho nó là nói dối đồ thị"
    assert [(c.source_doc, c.target_doc) for c in ghi["canh_vao"]] == [("TT01-2020", "TT99-2026")]


def test_dich_that_cua_canh_di_ra_cung_duoc_dung_node(bang, monkeypatch):
    """Chiều ĐI RA hở y hệt chiều đi vào, và đó là lý do lọc ở chỗ dùng chung cho cả hai.

    `_merge_canh` bỏ câu trong im lặng khi **bất kỳ** vế `MATCH` nào không khớp — không riêng
    vế nguồn. Duyệt TT99-2026 có `DAN_CHIEU → TT02-2021` trong khi TT02-2021 là văn bản thật
    đã duyệt từ trước nhưng chưa lên đồ thị thì cạnh đi ra cũng biến mất không tiếng động.
    """
    ghi = _bat_push_one_doc(monkeypatch)
    doc, dich = _doc("TT99-2026"), _doc("TT02-2021")
    ra = Relationship(source_doc="TT99-2026", target_doc="TT02-2021", rel_type="DAN_CHIEU")

    pipeline.ingest_one_doc(doc, [ra], [doc, dich])

    assert [d.doc_id for d in ghi["dau_mut_that"]] == ["TT02-2021"]
    assert ghi["rong"] == []
    assert [(c.source_doc, c.target_doc) for c in ghi["rels"]] == [("TT99-2026", "TT02-2021")]


def test_canh_khong_quy_duoc_dau_mut_thi_keu_len_chu_khong_im_lang(bang, monkeypatch, capsys):
    """Đầu mút không phải `doc_id` trong corpus, cũng không đọc được thành số hiệu.

    Không có node nào dựng được cho nó, nên cạnh này Neo4j sẽ bỏ trong im lặng. Loại nó ra và
    NÓI RA, để số cạnh in ở dòng tổng kết là số đã ghi thật chứ không phải số đã thử.
    """
    ghi = _bat_push_one_doc(monkeypatch)
    doc = _doc("TT99-2026")
    hong = Relationship(source_doc="nguồn nào đó", target_doc="TT99-2026", rel_type="BAI_BO")
    tot = Relationship(source_doc="52/2024/NĐ-CP", target_doc="TT99-2026", rel_type="DAN_CHIEU")

    pipeline.ingest_one_doc(doc, [hong, tot], [doc])

    assert [c.source_doc for c in ghi["canh_vao"]] == ["52/2024/NĐ-CP"]
    ra = capsys.readouterr().out
    assert "nguồn nào đó" in ra and "bỏ cạnh" in ra
    assert "0 cạnh đi ra + 1 cạnh đi vào" in ra, "số cạnh phải đếm cái ĐÃ GHI, không phải đã thử"


def test_van_ban_khong_con_dieu_nao_van_xoa_chunk_cu_va_len_do_thi(bang, monkeypatch):
    """0 điều là ca có thật (admin xoá hết Điều trong ô JSON, hoặc extract ra rỗng).

    Về sớm ở đó bỏ qua CẢ `delete` LẪN Neo4j, rồi vẫn trả 200 `approved`: truy hồi tiếp tục
    phục vụ đúng đoạn văn vừa bị xoá, và đồ thị không bao giờ biết văn bản này tồn tại.
    """
    bang.hang["TT99-2026::Điều 1"] = {
        "id": "TT99-2026::Điều 1", "doc_id": "TT99-2026", "text": "bản cũ",
    }
    ghi = _bat_push_one_doc(monkeypatch)
    trong = _doc("TT99-2026").model_copy(update={"articles": []})

    n = pipeline.ingest_one_doc(trong, [], [trong])

    assert n == 0
    # Ghim TÍNH CHẤT chứ không ghim chuỗi: vị từ đổi từ `doc_id = …` sang `id IN (…)` khi tầng
    # ghi dùng chung với `write_lancedb`. Cái phải đúng mãi là phạm vi, không phải cú pháp.
    assert len(bang.deleted) == 1
    assert all("TT99-2026::" in x for x in bang.deleted[0].split(", ")), bang.deleted
    assert sorted(r["doc_id"] for r in bang.hang.values()) == ["TT01-2020", "TT02-2021"]
    assert ghi["doc"].doc_id == "TT99-2026", "node phải lên đồ thị dù không có chunk nào"


# --- Thân hàm `push_one_doc`: kiểm Cypher PHÁT RA, không kiểm "tên nào được gọi" ---
#
# Hai ca `_gia_lap_graph` ở trên vá chính `push_one_doc`, nên chúng chỉ khẳng định
# `ingest_one_doc` gọi đúng TÊN — thân hàm không ca nào chạm tới. Đó đúng hình dạng của sự cố
# `list_tables()`: một bản giả tự đồng ý với giả định của chính nó. Các ca dưới chạy thân hàm
# thật trên session giả và đọc chuỗi Cypher nó phát ra, theo nếp `tests/test_push_overlay.py`.


def _phat_cypher(doc, rels, rong=None, canh_vao=None, dau_mut_that=None, ids_rong=()):
    """Chạy `push_one_doc` thật trên session giả → (danh sách câu Cypher, danh sách lời gọi).

    `ids_rong` là thứ câu đầu của `don_node_rong_da_co_toan_van` trả về, tức **chọn nhánh**
    của hàm dọn: rỗng = không có node rỗng nào phải dọn (nó về ngay), có phần tử = nhánh dời
    cạnh + `DETACH DELETE`. Phải đặt tường minh: `MagicMock` trần cho `ids` là một MagicMock
    *truthy*, tức bản giả tự chọn nhánh hộ mình — đúng hình dạng sự cố `list_tables()`.
    """
    from app.knowledge import graph

    phien = MagicMock()
    phien.run.return_value.single.return_value = {"ids": list(ids_rong)}
    with patch("app.knowledge.graph.session") as mo:
        mo.return_value.__enter__.return_value = phien
        graph.push_one_doc(doc, rels, rong, canh_vao, dau_mut_that)
    return [c.args[0] for c in phien.run.call_args_list], phien.run.call_args_list


def _cau_xoa(cypher: list[str]) -> str:
    """Câu xoá cạnh ĐI RA của chính văn bản — phải có đúng một, ở BẤT KỲ nhánh nào.

    Lọc theo đúng mẫu chứ không theo `"DELETE"`: nhánh có node rỗng phải dọn của
    `don_node_rong_da_co_toan_van()` phát thêm 26 câu `DELETE e` và một `DETACH DELETE rong`,
    nên bộ lọc rộng chỉ cho ra "đúng một" nhờ `ids_rong` mặc định rỗng ép hàm dọn về sớm —
    tức một khẳng định đúng nhờ bản giả chọn nhánh hộ. (`"DELETE r"` cũng không đủ: nó khớp
    luôn `DETACH DELETE rong`.)
    """
    xoa = [c for c in cypher if c.rstrip().endswith("]->(:Document) DELETE r")]
    assert len(xoa) == 1, f"chỉ được đúng một câu xoá cạnh đi ra, thấy {len(xoa)}: {xoa}"
    return xoa[0]


def _xoa_trang(cypher: list[str]) -> list[str]:
    """Câu `DETACH DELETE` KHÔNG neo vào một danh sách id cụ thể — tức xoá theo nhãn."""
    return [c for c in cypher if "DETACH DELETE" in c and "$ids" not in c]


def test_push_one_doc_chi_xoa_canh_di_ra_cua_chinh_no():
    cypher, goi = _phat_cypher(_doc("TT99-2026"), [])

    xoa = _cau_xoa(cypher)
    assert xoa.startswith("MATCH (a:Document {doc_id: $doc_id})-[r")
    assert "]->(:Document) DELETE r" in xoa, (
        "mẫu phải neo cả hai đầu vào :Document và chỉ DELETE r — `DETACH DELETE` hay mẫu "
        "không neo đầu kia sẽ cuốn theo cạnh THUOC của lớp phủ"
    )
    # Qua `_cau_xoa` chứ không lọc `"DELETE" in c`: ở nhánh có việc dọn, bộ lọc rộng bắt thêm
    # 27 câu nữa và vế phải thành `["TT99-2026"] + [None]*27`. Đúng loại lỗi cả lượt này đi sửa.
    assert goi[cypher.index(xoa)].kwargs["doc_id"] == "TT99-2026"
    # Câu cũ ở đây khẳng định `"DETACH DELETE" not in cypher`, và nó **sai khi nói chung**:
    # `don_node_rong_da_co_toan_van()` chạy ở cuối mỗi lượt và nhánh CÓ node rỗng của nó phát
    # ra `DETACH DELETE rong` thật. Câu ấy chỉ đúng vì `ids_rong` mặc định rỗng ép hàm về sớm —
    # tức nó khẳng định về một nhánh nó không bao giờ đi qua, đúng lỗi đã mắc hai lần.
    # Tính chất thật sự tách `push_one_doc` khỏi `push_corpus` là: KHÔNG có lượt xoá theo nhãn.
    # `MATCH (d:Document) DETACH DELETE d` cuốn theo mọi cạnh chạm mọi văn bản, kể cả `THUOC`
    # phát từ `(:DonVi)`. Nhánh dọn node rỗng có ca riêng bên dưới canh phạm vi của nó.
    assert _xoa_trang(cypher) == [], (
        "xoá theo nhãn (không neo `$ids`) là thứ đường nạp một văn bản sinh ra để tránh"
    )


def test_xoa_canh_liet_ke_13_ma_chu_khong_dung_mau_tran():
    """`[r]` trần cuốn theo mọi loại cạnh `Document→Document`, kể cả loại thêm sau này."""
    from app.knowledge import graph

    xoa = _cau_xoa(_phat_cypher(_doc("TT99-2026"), [])[0])
    assert f"-[r{graph._MOI_CANH}]->" in xoa


def test_merge_node_truoc_khi_xoa_canh_va_truoc_moi_canh():
    """Thứ tự là bất biến, không phải thẩm mỹ.

    `_merge_canh` khớp CẢ HAI đầu bằng `MATCH`. Ở lượt duyệt đầu tiên node văn bản chưa tồn
    tại, nên `_merge_doc` mà rơi xuống sau vòng dựng cạnh thì mọi cạnh đi ra im lặng không
    được tạo — không lỗi, không cảnh báo.
    """
    ra = Relationship(source_doc="TT99-2026", target_doc="TT02-2021", rel_type="DAN_CHIEU")
    cypher, _ = _phat_cypher(_doc("TT99-2026"), [ra])

    i_node = next(i for i, c in enumerate(cypher) if "MERGE (n:Document" in c)
    # `"DELETE r" in c` khớp luôn `DETACH DELETE rong`; ở đây nó đúng chỉ nhờ `next()` lấy
    # phần tử đầu. Dùng `_cau_xoa` để khỏi phải may.
    i_xoa = cypher.index(_cau_xoa(cypher))
    i_canh = next(i for i, c in enumerate(cypher) if "MERGE (a)-[e:" in c)
    assert i_node < i_xoa < i_canh


def test_canh_di_vao_duoc_merge_chu_khong_bi_xoa():
    vao = Relationship(source_doc="TT01-2020", target_doc="TT99-2026", rel_type="SUA_DOI_BO_SUNG")
    ra = Relationship(source_doc="TT99-2026", target_doc="TT02-2021", rel_type="DAN_CHIEU")

    cypher, goi = _phat_cypher(_doc("TT99-2026"), [ra], None, [vao])

    canh = [c for c in goi if "MERGE (a)-[e:" in c.args[0]]
    assert [(c.kwargs["src"], c.kwargs["tgt"]) for c in canh] == [
        ("TT99-2026", "TT02-2021"),
        ("TT01-2020", "TT99-2026"),
    ], "cạnh đi vào phải được MERGE SAU khi cạnh đi ra đã dựng lại xong"
    # Vẫn đúng một câu xoá, và nó neo nguồn vào `$doc_id` ⇒ cạnh do văn bản KHÁC phát ra
    # không bị đụng, quyền sở hữu vẫn thuộc văn bản kia.
    assert _cau_xoa(cypher).startswith("MATCH (a:Document {doc_id: $doc_id})-[r")


def test_don_node_rong_chay_o_cuoi_moi_luot_nap():
    """Node rỗng cũ (khoá theo `so_hieu`) phải được thay bằng node thật (khoá theo `doc_id`).

    Không dọn thì một văn bản có HAI node: node rỗng giữ hết cạnh đi vào cũ, `related_docs()`
    lọc `co_toan_van=false` ra nên các quan hệ ấy biến mất khỏi truy hồi, và `thieu_toan_van()`
    vẫn kê văn bản vừa duyệt vào danh sách cần crawl.
    """
    cypher, _ = _phat_cypher(_doc("TT99-2026"), [])

    don = [c for c in cypher if "rong.co_toan_van = false" in c and "that.so_hieu" in c]
    assert len(don) == 1, "push_one_doc phải gọi don_node_rong_da_co_toan_van()"
    # "câu cuối cùng" là tính chất của nhánh KHÔNG có gì để dọn (`ids_rong` rỗng ⇒ hàm về
    # ngay). Thứ đúng ở mọi nhánh: nó chạy sau khi node thật và mọi cạnh đã dựng xong — dọn
    # trước thì chưa có node thật nào để dời cạnh sang. Nhánh còn lại có ca riêng bên dưới.
    i_dung = [i for i, c in enumerate(cypher) if "MERGE (n:Document" in c or "MERGE (a)-[e:" in c]
    assert cypher.index(don[0]) > max(i_dung)


def test_don_node_rong_nhanh_co_viec_doi_canh_xong_moi_xoa_va_xoa_dung_pham_vi():
    """Nhánh CÓ node rỗng phải dọn — nhánh mà `push_one_doc` chạy thật trên production.

    Ca ở trên chỉ chạy nhánh rỗng (`ids == []`, hàm về ngay), nên mọi khẳng định về `DETACH
    DELETE` của nó nói về một đoạn mã chưa từng được chạy. Đây là nhánh thật: 13 mã × 2 hướng
    dời cạnh sang node thật, RỒI mới xoá node rỗng — đảo thứ tự là `DETACH` cuốn theo đúng
    những cạnh vừa định cứu.
    """
    from app.core.schemas import REL_TYPES

    cypher, goi = _phat_cypher(_doc("TT99-2026"), [], ids_rong=["52/2024/NĐ-CP"])

    xoa = _cau_xoa(cypher)
    assert xoa.startswith("MATCH (a:Document {doc_id: $doc_id})-[r"), (
        "nhánh dọn không được làm đổi câu xoá cạnh đi ra của chính văn bản"
    )
    # Cùng khẳng định với ca nhánh rỗng, chạy ở đây để nó được kiểm ở CẢ HAI nhánh.
    assert goi[cypher.index(xoa)].kwargs["doc_id"] == "TT99-2026"
    doi = [i for i, c in enumerate(cypher) if "MERGE (" in c and "DELETE e" in c]
    assert len(doi) == 2 * len(REL_TYPES), (
        "phải dời cả hai hướng của cả 13 mã — bỏ sót mã nào là mất cạnh đó khi xoá node rỗng"
    )
    i_xoa = next(i for i, c in enumerate(cypher) if "DETACH DELETE rong" in c)
    assert max(doi) < i_xoa, "dời cạnh xong mới được xoá"
    assert i_xoa == len(cypher) - 1

    # Phạm vi xoá: đúng danh sách id do câu đầu trả về, không phải một lượt quét nhãn.
    assert _xoa_trang(cypher) == []
    ids = goi[i_xoa].kwargs["ids"]
    assert ids == ["52/2024/NĐ-CP"]
    # KHÔNG khẳng định `"TT99-2026" not in ids` ở đây: `ids` chỉ là thứ bản giả vọng lại từ
    # `ids_rong`, nên câu đó không bao giờ đỏ được — nó nói về bản giả, không về mã. Thứ THẬT
    # sự giữ văn bản đang duyệt ngoài danh sách xoá là câu sinh ra `$ids`: nó lọc
    # `rong.co_toan_van = false`, mà `_merge_doc` vừa đặt `co_toan_van=true` cho văn bản này.
    # Cùng lý do, node mang cạnh `THUOC` không lọt vào: `dung_overlay` lấy `doc_id` từ
    # `doc_id_theo_corpus`, tức luôn là văn bản CÓ trong corpus — mà `quy_ve_doc_id` không bao
    # giờ dựng node rỗng cho một `doc_id` đã có trong corpus.
    assert any("rong.co_toan_van = false" in c and "collect(DISTINCT rong.doc_id)" in c
               for c in cypher)
    assert all(goi[i].kwargs["ids"] == ids for i in doi), "mọi câu dời cạnh phải cùng phạm vi"


def test_dau_mut_that_duoc_merge_truoc_khi_dung_canh():
    """Cạnh đi vào từ một văn bản thật chưa lên đồ thị: node nguồn phải được MERGE trước.

    `_merge_canh` khớp hai đầu bằng `MATCH`; thiếu node nguồn thì Cypher bỏ cả câu trong im
    lặng — cạnh không tồn tại mà không ai biết.
    """
    nguon = _doc("TT01-2020")
    vao = Relationship(source_doc="TT01-2020", target_doc="TT99-2026", rel_type="SUA_DOI_BO_SUNG")

    cypher, goi = _phat_cypher(_doc("TT99-2026"), [], None, [vao], [nguon])

    merge_nguon = [
        i for i, c in enumerate(goi)
        if "MERGE (n:Document" in c.args[0] and c.kwargs.get("doc_id") == "TT01-2020"
    ]
    assert len(merge_nguon) == 1, "node nguồn phải được dựng đúng một lần"
    assert "n.co_toan_van=true" in cypher[merge_nguon[0]], (
        "nguồn có toàn văn ⇒ node THẬT; dựng node rỗng cho nó là phá bất biến của bac_cau"
    )
    i_canh = next(i for i, c in enumerate(cypher) if "MERGE (a)-[e:" in c)
    assert merge_nguon[0] < i_canh
