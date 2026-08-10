"""Nạp lại MỘT văn bản: chỉ đụng chunk của nó, không ghi đè cả bảng.

`write_lancedb` gọi `create_table(mode="overwrite")` — mỗi lần duyệt một văn bản là ghi đè
cả bảng đang phục vụ trong lúc người dùng đang tra, và embed lại toàn bộ chunk không hề đổi
(đo 10/08: 661 chunk ≈ 52s, so với 23 chunk ≈ 1,8s của một thông tư). Đường duyệt cần một
lối khác.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.schemas import CorpusDocument, Relationship
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


# --- Cái gì được TRUYỀN XUỐNG push_one_doc (lọc cạnh, node rỗng, văn bản 0 điều) ---


def _bat_push_one_doc(monkeypatch) -> dict:
    """Bắt tham số truyền xuống `push_one_doc`. Thân hàm có ca riêng ở cuối file."""
    ghi: dict = {}
    monkeypatch.setattr(pipeline.settings, "neo4j_uri", "neo4j+s://test")
    monkeypatch.setattr(pipeline.settings, "neo4j_password", "test")
    monkeypatch.setattr(
        "app.knowledge.graph.push_one_doc",
        lambda doc, rels, rong=None, canh_vao=None: ghi.update(
            doc=doc, rels=rels, rong=rong, canh_vao=canh_vao
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


def test_van_ban_khong_con_dieu_nao_van_xoa_chunk_cu_va_len_do_thi(bang, monkeypatch):
    """0 điều là ca có thật (admin xoá hết Điều trong ô JSON, hoặc extract ra rỗng).

    Về sớm ở đó bỏ qua CẢ `delete` LẪN Neo4j, rồi vẫn trả 200 `approved`: truy hồi tiếp tục
    phục vụ đúng đoạn văn vừa bị xoá, và đồ thị không bao giờ biết văn bản này tồn tại.
    """
    bang.rows.append({"id": "TT99-2026::Điều 1", "doc_id": "TT99-2026", "text": "bản cũ"})
    ghi = _bat_push_one_doc(monkeypatch)
    trong = _doc("TT99-2026").model_copy(update={"articles": []})

    n = pipeline.ingest_one_doc(trong, [], [trong])

    assert n == 0
    assert bang.deleted == ["doc_id = 'TT99-2026'"]
    assert [r["doc_id"] for r in bang.rows] == ["TT01-2020", "TT02-2021"]
    assert ghi["doc"].doc_id == "TT99-2026", "node phải lên đồ thị dù không có chunk nào"


# --- Thân hàm `push_one_doc`: kiểm Cypher PHÁT RA, không kiểm "tên nào được gọi" ---
#
# Hai ca `_gia_lap_graph` ở trên vá chính `push_one_doc`, nên chúng chỉ khẳng định
# `ingest_one_doc` gọi đúng TÊN — thân hàm không ca nào chạm tới. Đó đúng hình dạng của sự cố
# `list_tables()`: một bản giả tự đồng ý với giả định của chính nó. Các ca dưới chạy thân hàm
# thật trên session giả và đọc chuỗi Cypher nó phát ra, theo nếp `tests/test_push_overlay.py`.


def _phat_cypher(doc, rels, rong=None, canh_vao=None):
    """Chạy `push_one_doc` thật trên session giả → (danh sách câu Cypher, danh sách lời gọi)."""
    from app.knowledge import graph

    phien = MagicMock()
    # `don_node_rong_da_co_toan_van` đọc kết quả câu đầu của nó. Trả danh sách rỗng = ca
    # thường (không node rỗng nào phải dọn) và nó về ngay. MagicMock trần sẽ cho `ids` là một
    # MagicMock *truthy*, khiến hàm chạy tiếp 26 câu dời cạnh — không giống thật chút nào.
    phien.run.return_value.single.return_value = {"ids": []}
    with patch("app.knowledge.graph.session") as mo:
        mo.return_value.__enter__.return_value = phien
        graph.push_one_doc(doc, rels, rong, canh_vao)
    return [c.args[0] for c in phien.run.call_args_list], phien.run.call_args_list


def _cau_xoa(cypher: list[str]) -> str:
    xoa = [c for c in cypher if "DELETE" in c]
    assert len(xoa) == 1, f"chỉ được đúng một câu xoá, thấy {len(xoa)}: {xoa}"
    return xoa[0]


def test_push_one_doc_chi_xoa_canh_di_ra_cua_chinh_no():
    cypher, goi = _phat_cypher(_doc("TT99-2026"), [])

    xoa = _cau_xoa(cypher)
    assert xoa.startswith("MATCH (a:Document {doc_id: $doc_id})-[r")
    assert "]->(:Document) DELETE r" in xoa, (
        "mẫu phải neo cả hai đầu vào :Document và chỉ DELETE r — `DETACH DELETE` hay mẫu "
        "không neo đầu kia sẽ cuốn theo cạnh THUOC của lớp phủ"
    )
    assert [c.kwargs.get("doc_id") for c in goi if "DELETE" in c.args[0]] == ["TT99-2026"]
    assert "DETACH DELETE" not in " ".join(cypher), (
        "DETACH xoá MỌI cạnh chạm node, kể cả THUOC phát từ (:DonVi) — đó chính là thứ "
        "đường nạp một văn bản sinh ra để tránh"
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
    i_xoa = next(i for i, c in enumerate(cypher) if "DELETE r" in c)
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
    assert cypher[-1] == don[0], "phải chạy SAU khi node thật đã được MERGE"
