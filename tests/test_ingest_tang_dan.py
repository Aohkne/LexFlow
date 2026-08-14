"""Ingest tăng dần: chỉ embed và ghi văn bản thật sự đổi.

Bảng giả ở đây KHÔNG mock hàm đang thử — nó mô phỏng đúng những lời gọi LanceDB mà `pipeline`
được phép dùng, rồi để hàm thật chạy trên đó. Mock `_doc_can_nap` rồi khẳng định nó đúng thì
chứng minh được gì; cùng lý do đã ghi ở `tests/test_lay_chunk_tien_to.py`.

Vân tay so CẢ HÀNG trừ `vector`, không phải mình `text`. Luật hết hiệu lực thì cái đổi là
`valid_to`/`superseded` — đúng hai trường bộ lọc `as_of` đọc. So mỗi `text` thì văn bản vừa
chết bị coi là "không đổi" và hệ thống tiếp tục trả nó, không lỗi, không cảnh báo.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from app.ingestion import pipeline

_CORPUS_REAL = Path("data/corpus.real.json")

_LOC_ID_RE = re.compile(r"^id IN \((.*)\)$")

_COT = [
    "id", "doc_id", "doc_title", "doc_type", "source",
    "article", "text", "valid_from", "valid_to", "superseded",
]


@dataclass
class _Truong:
    name: str


@dataclass
class _ChiMucGia:
    name: str
    num_indexed_rows: int
    index_type: str = "FTS"


class _TruyVanGia:
    """Chỉ hiểu đúng cú pháp mà `_doc_can_nap` được phép dùng."""

    def __init__(self, hang: list[dict]) -> None:
        self._hang = hang
        self._cot: list[str] | None = None
        self._gioi_han: int | None = None

    def select(self, cot: list[str]):
        self._cot = list(cot)
        return self

    def where(self, dieu_kien: str):
        m = re.match(r"^doc_id IN \((.*)\)$", dieu_kien)
        assert m, f"cú pháp where lạ, cloud có thể không nhận: {dieu_kien!r}"
        ids = {s.strip()[1:-1] for s in m.group(1).split(", ")}
        self._hang = [r for r in self._hang if r.get("doc_id") in ids]
        return self

    def limit(self, n: int):
        self._gioi_han = n
        return self

    def to_list(self) -> list[dict]:
        ra = self._hang[: self._gioi_han] if self._gioi_han else list(self._hang)
        if self._cot is None:
            return [dict(r) for r in ra]
        return [{k: r[k] for k in self._cot} for r in ra]


class _MergeGia:
    def __init__(self, bang: "_BangGia") -> None:
        self._bang = bang

    def when_matched_update_all(self):
        return self

    def when_not_matched_insert_all(self):
        return self

    def execute(self, rows: list[dict]) -> None:
        self._bang.nhat_ky.append(f"merge_insert:{len(rows)}")
        for r in rows:
            self._bang.hang[r["id"]] = dict(r)


@dataclass
class _BangGia:
    """Bảng LanceDB giả: đủ đọc cho `_doc_can_nap`, đủ ghi cho `write_lancedb`."""

    hang: dict[str, dict]
    co_index: bool = True
    #: Số hàng index FTS báo là đã phủ. `None` = phủ đủ. Đặt số nhỏ hơn để dựng ca index chạy sau.
    index_phu: int | None = None
    #: Index KHÔNG PHẢI FTS (vd. BTREE của T25) — có mặt để ghim `_cho_index` không đụng tới nó.
    index_khac: _ChiMucGia | None = None
    nhat_ky: list[str] = field(default_factory=list)

    @property
    def schema(self) -> list[_Truong]:
        return [_Truong(k) for k in [*_COT, "vector"]]

    def count_rows(self) -> int:
        return len(self.hang)

    def search(self, *a, **kw) -> _TruyVanGia:
        return _TruyVanGia([dict(r) for r in self.hang.values()])

    def list_indices(self) -> list[_ChiMucGia]:
        if not self.co_index:
            return []
        phu = len(self.hang) if self.index_phu is None else self.index_phu
        ra = [_ChiMucGia("text_idx", phu)]
        if self.index_khac is not None:
            ra.append(self.index_khac)
        return ra

    def wait_for_index(self, ten, *a, **kw) -> None:
        self.nhat_ky.append(f"wait_for_index:{','.join(ten)}")

    def merge_insert(self, khoa: str) -> _MergeGia:
        assert khoa == "id", f"khoá merge phải là id, không phải {khoa!r}"
        return _MergeGia(self)

    def delete(self, dieu_kien: str) -> None:
        m = _LOC_ID_RE.match(dieu_kien)
        assert m, f"cú pháp delete lạ, cloud có thể không nhận: {dieu_kien!r}"
        ids = {s.strip()[1:-1].replace("''", "'") for s in m.group(1).split(", ")}
        self.nhat_ky.append(f"delete:{len(ids)}")
        for i in ids:
            self.hang.pop(i, None)

    def create_fts_index(self, cot: str, replace: bool = False, **kw) -> None:
        # Ghi cả `kw`: đây là chỗ `_FTS_OPTS` có thể rơi rụng mà không ca nào thấy, vì index
        # sai tham số vẫn dựng được và vẫn trả kết quả — chỉ là kết quả khác.
        self.nhat_ky.append(f"create_fts_index:replace={replace}:opts={sorted(kw)}")


def _hang(doc_id: str, article: str, text: str, valid_to: str = "") -> dict:
    return {
        "id": f"{doc_id}::{article}", "doc_id": doc_id, "doc_title": f"VB {doc_id}",
        "doc_type": "Thông tư", "source": "vbpl", "article": article, "text": text,
        "valid_from": "2024-01-01", "valid_to": valid_to, "superseded": False,
    }


def _bang(rows: list[dict]) -> _BangGia:
    return _BangGia(hang={r["id"]: {**r, "vector": [0.0]} for r in rows})


# --- phát hiện thay đổi ---------------------------------------------------------------------

def test_khong_doi_thi_khong_doc_nao_can_nap():
    rows = [_hang("A", "Điều 1", "x"), _hang("B", "Điều 1", "y")]
    can_nap, du, _ = pipeline._doc_can_nap(_bang(rows), rows)
    assert can_nap == set()
    assert du == set()


def test_doi_text_thi_doc_do_can_nap():
    cu = [_hang("A", "Điều 1", "x"), _hang("B", "Điều 1", "y")]
    moi = [_hang("A", "Điều 1", "x ĐÃ SỬA"), _hang("B", "Điều 1", "y")]
    can_nap, _, _ = pipeline._doc_can_nap(_bang(cu), moi)
    assert can_nap == {"A"}


def test_doi_valid_to_ma_text_y_nguyen_van_can_nap():
    """Luật hết hiệu lực đổi `valid_to` chứ không đổi chữ — so mỗi text là bỏ sót đúng ca này."""
    cu = [_hang("A", "Điều 1", "x")]
    moi = [_hang("A", "Điều 1", "x", valid_to="2026-01-01")]
    can_nap, _, _ = pipeline._doc_can_nap(_bang(cu), moi)
    assert can_nap == {"A"}


def test_doc_moi_hoan_toan_thi_can_nap():
    cu = [_hang("A", "Điều 1", "x")]
    moi = [*cu, _hang("MOI", "Điều 1", "z")]
    can_nap, du, _ = pipeline._doc_can_nap(_bang(cu), moi)
    assert can_nap == {"MOI"}
    assert du == set()


def test_doc_co_trong_bang_ma_khong_co_trong_corpus_la_du():
    cu = [_hang("A", "Điều 1", "x"), _hang("BI_GO", "Điều 1", "y")]
    moi = [_hang("A", "Điều 1", "x")]
    can_nap, du, _ = pipeline._doc_can_nap(_bang(cu), moi)
    assert can_nap == set()
    assert du == {"BI_GO"}


def test_tra_ve_id_cu_de_khoi_quet_bang_lan_hai():
    cu = [_hang("A", "Điều 1", "x"), _hang("A", "Điều 2", "x2")]
    can_nap, _, id_cu = pipeline._doc_can_nap(_bang(cu), cu)
    assert id_cu["A"] == {"A::Điều 1", "A::Điều 2"}
    assert can_nap == set()


def test_bang_rong_thi_moi_doc_deu_can_nap():
    moi = [_hang("A", "Điều 1", "x")]
    can_nap, du, id_cu = pipeline._doc_can_nap(_bang([]), moi)
    assert can_nap == {"A"}
    assert du == set() and id_cu == {}


def test_van_tay_khong_dung_cot_vector():
    """Vector là HỆ QUẢ của text — đưa nó vào vân tay là so 768 float để biết điều text đã nói."""
    assert "vector" not in pipeline._cot_du_lieu(_bang([_hang("A", "Điều 1", "x")]))


# --- ghi tăng dần ---------------------------------------------------------------------------

@pytest.fixture
def khong_goi_mang(monkeypatch):
    """Đếm số hàng đi qua embedding. Gọi Gemini trong test là hỏng, không phải chậm."""
    da_embed: list[int] = []

    def _gia(rows):
        da_embed.append(len(rows))
        for r in rows:
            r["vector"] = [0.0]

    monkeypatch.setattr(pipeline, "_embed_rows", _gia)
    return da_embed


def _noi_bang(monkeypatch, bang: _BangGia) -> None:
    """Bắt `vectordb.connect()` trả về DB giả đã có sẵn bảng.

    `open_table` THẲNG LÀ phép dò bảng tồn tại — không liệt kê bảng rồi so tên (xem lý do ở
    docstring nhánh `except ValueError` trong `write_lancedb`).
    """

    class _DbGia:
        def open_table(self, ten):
            assert ten == pipeline.LANCEDB_TABLE
            return bang

    monkeypatch.setattr(pipeline.vectordb, "connect", lambda: _DbGia())


def test_khong_doi_gi_thi_khong_embed_hang_nao(monkeypatch, khong_goi_mang, capsys):
    rows = [_hang("A", "Điều 1", "x")]
    bang = _bang(rows)
    _noi_bang(monkeypatch, bang)

    n_ghi, n_tong = pipeline.write_lancedb(rows)

    assert khong_goi_mang == [], "corpus không đổi mà vẫn gọi embedding"
    assert (n_ghi, n_tong) == (0, 1)
    assert not [x for x in bang.nhat_ky if x.startswith("merge_insert")]
    assert "Không văn bản nào đổi" in capsys.readouterr().out


def test_chi_embed_va_ghi_doc_da_doi(monkeypatch, khong_goi_mang):
    cu = [_hang("A", "Điều 1", "x"), _hang("B", "Điều 1", "y")]
    moi = [_hang("A", "Điều 1", "x ĐÃ SỬA"), _hang("B", "Điều 1", "y")]
    bang = _bang(cu)
    _noi_bang(monkeypatch, bang)

    n_ghi, n_tong = pipeline.write_lancedb(moi)

    assert khong_goi_mang == [1], "chỉ 1 chunk của A được embed"
    assert (n_ghi, n_tong) == (1, 2)
    assert bang.hang["A::Điều 1"]["text"] == "x ĐÃ SỬA"
    assert bang.hang["B::Điều 1"]["text"] == "y"


def test_che_ra_it_manh_hon_thi_id_mo_coi_bi_xoa(monkeypatch, khong_goi_mang):
    """`merge_insert` chỉ biết id ta đưa vào — nhãn cũ không còn phải bị xoá riêng.

    Ca thật: `label` suy từ nội dung, nên chẻ lại có thể sinh ít mảnh hơn (T2 thêm hậu tố
    `(2)` đã đổi cả tập nhãn của TT23-2019). Không xoá thì nhãn cũ nằm lại vĩnh viễn — chunk
    ma, vẫn được truy hồi, vẫn được trích dẫn.
    """
    cu = [_hang("A", "Điều 1 Khoản 1", "p"), _hang("A", "Điều 1 Khoản 2", "q")]
    moi = [_hang("A", "Điều 1", "p q")]
    bang = _bang(cu)
    _noi_bang(monkeypatch, bang)

    pipeline.write_lancedb(moi)

    assert set(bang.hang) == {"A::Điều 1"}
    assert "delete:2" in bang.nhat_ky


def test_doc_du_thi_nem_chu_khong_xoa(monkeypatch, khong_goi_mang):
    cu = [_hang("A", "Điều 1", "x"), _hang("BI_GO", "Điều 1", "y")]
    moi = [_hang("A", "Điều 1", "x")]
    bang = _bang(cu)
    _noi_bang(monkeypatch, bang)

    with pytest.raises(pipeline.DocDuTrongBang) as e:
        pipeline.write_lancedb(moi)

    assert e.value.doc_ids == ["BI_GO"]
    assert "BI_GO::Điều 1" in bang.hang, "ném rồi mà vẫn xoá — mất dữ liệu"
    assert khong_goi_mang == [], "ném rồi mà vẫn đốt embedding"


def test_co_co_xoa_doc_du_thi_moi_xoa(monkeypatch, khong_goi_mang):
    cu = [_hang("A", "Điều 1", "x"), _hang("BI_GO", "Điều 1", "y")]
    moi = [_hang("A", "Điều 1", "x")]
    bang = _bang(cu)
    _noi_bang(monkeypatch, bang)

    n_ghi, n_tong = pipeline.write_lancedb(moi, xoa_doc_du=True)

    assert set(bang.hang) == {"A::Điều 1"}
    assert (n_ghi, n_tong) == (0, 1)


def test_co_ep_nap_lai_du_van_tay_khop(monkeypatch, khong_goi_mang):
    rows = [_hang("A", "Điều 1", "x"), _hang("B", "Điều 1", "y")]
    bang = _bang(rows)
    _noi_bang(monkeypatch, bang)

    n_ghi, _ = pipeline.write_lancedb(rows, ep=frozenset({"A"}))

    assert khong_goi_mang == [1] and n_ghi == 1


def test_ep_doc_khong_co_trong_corpus_thi_canh_bao(monkeypatch, khong_goi_mang, capsys):
    rows = [_hang("A", "Điều 1", "x")]
    _noi_bang(monkeypatch, _bang(rows))

    pipeline.write_lancedb(rows, ep=frozenset({"KHONG-CO"}))

    assert "KHONG-CO" in capsys.readouterr().out
    # Rủi ro thật không phải ở chữ cảnh báo — là doc ẢO lọt vào `can_nap` rồi bị embed dù
    # không có hàng nào của nó trong `rows`. Bộ lọc đúng là `ep & co_that`, không phải `ep` trần.
    assert khong_goi_mang == []


def test_bang_chua_ton_tai_thi_dung_duong_cu(monkeypatch, khong_goi_mang):
    """Lần đầu (máy mới, local, CI) không có bảng để so — phải dựng như trước.

    `open_table` ném `ValueError("Table 'x' was not found")` — đo trực tiếp trên backend local
    (embedded) trong `.venv`, xem docstring nhánh `except ValueError` trong `write_lancedb`.
    """
    da_tao: list[str] = []

    class _DbTrong:
        def open_table(self, ten):
            raise ValueError(f"Table '{ten}' was not found")

        def create_table(self, ten, data):
            da_tao.append(f"{ten}:{len(data)}")
            return _bang(data)

    monkeypatch.setattr(pipeline.vectordb, "connect", lambda: _DbTrong())
    rows = [_hang("A", "Điều 1", "x")]

    n_ghi, n_tong = pipeline.write_lancedb(rows)

    assert da_tao == [f"{pipeline.LANCEDB_TABLE}:1"]
    assert (n_ghi, n_tong) == (1, 1)
    assert khong_goi_mang == [1]


def test_loi_khac_luc_mo_bang_thi_nem_chu_khong_hieu_nham_la_bang_chua_co(
    monkeypatch, khong_goi_mang
):
    """Một `ValueError` KHÔNG chứa "not found" không được hiểu nhầm thành "bảng chưa tồn tại".

    Nếu bắt mọi `ValueError` bất kể thông điệp, một lỗi mở bảng vì lý do khác (đối số sai, phản
    hồi hỏng, ...) sẽ lặng lẽ chảy xuống `_tao_bang_moi` → ghi đè cả bảng thật. Đây đúng loại
    thảm hoạ mà `except ValueError` hẹp phải chặn.
    """

    class _DbLoi:
        def open_table(self, ten):
            raise ValueError("phản hồi JSON hỏng")

    monkeypatch.setattr(pipeline.vectordb, "connect", lambda: _DbLoi())
    rows = [_hang("A", "Điều 1", "x")]

    with pytest.raises(ValueError, match="phản hồi JSON hỏng"):
        pipeline.write_lancedb(rows)

    assert khong_goi_mang == [], "lỗi mở bảng mà vẫn embed — bị hiểu nhầm thành bảng chưa có"


def test_loi_not_found_ve_bang_khac_thi_nem_chu_khong_tao_bang_moi(monkeypatch, khong_goi_mang):
    """`ValueError` chứa "not found" nhưng KHÔNG PHẢI về bảng `chunks` — vd lỗi cột trong `select`.

    Bộ lọc cũ chỉ soi chữ "not found" nên nuốt luôn ca này rồi ghi đè cả bảng thật. Bộ lọc mới
    đòi khớp đúng thông điệp `table '<tên bảng>' was not found` mà lancedb thật ném
    (`.venv/Lib/site-packages/lancedb/db.py:1849`, hàm `drop_table`, cùng khung với `open_table`).
    """

    class _DbLoiCot:
        def open_table(self, ten):
            raise ValueError("Column 'x' was not found")

        def create_table(self, *a, **kw):
            raise AssertionError("không được dựng bảng mới khi lỗi không phải về bảng chunks")

    monkeypatch.setattr(pipeline.vectordb, "connect", lambda: _DbLoiCot())
    rows = [_hang("A", "Điều 1", "x")]

    with pytest.raises(ValueError, match="Column 'x' was not found"):
        pipeline.write_lancedb(rows)

    assert khong_goi_mang == [], "lỗi cột mà vẫn embed — bị hiểu nhầm thành bảng chưa có"


def test_mang_chap_chon_luc_mo_bang_thi_nem_chu_khong_tao_bang_moi(monkeypatch, khong_goi_mang):
    """Lỗi mạng thoáng qua (không phải `ValueError`) lúc mở bảng cũng phải ném, không rơi về
    `_tao_bang_moi`. Đây là ca cụ thể mà reviewer nêu: mạng chập chờn không được hiểu thành
    "bảng chưa tồn tại" rồi ghi đè + đốt tiền embed cả bảng.
    """

    class _DbMangLoi:
        def open_table(self, ten):
            raise RuntimeError("mạng chập chờn")

    monkeypatch.setattr(pipeline.vectordb, "connect", lambda: _DbMangLoi())
    rows = [_hang("A", "Điều 1", "x")]

    with pytest.raises(RuntimeError, match="mạng chập chờn"):
        pipeline.write_lancedb(rows)

    assert khong_goi_mang == [], "lỗi mạng mà vẫn embed — bị hiểu nhầm thành bảng chưa có"


def test_id_co_nhay_don_khong_lam_vo_bo_loc():
    """Nhãn điều đến từ văn bản luật — một dấu nháy lọt vào là câu lọc SQL vỡ."""
    assert pipeline._loc_id(["A::Điều 1", "B::Đi'ều"]) == "id IN ('A::Điều 1', 'B::Đi''ều')"


def test_quet_bang_hong_thi_nem_chu_khong_roi_ve_ghi_de(monkeypatch, khong_goi_mang):
    """Mạng trục trặc KHÔNG được biến thành ghi đè cả bảng.

    Rơi về `create_table(mode="overwrite")` cho "an toàn" nghĩa là một lần rớt kết nối thoáng
    qua thành hoá đơn embedding 661 chunk — mà kết quả cuối vẫn đúng, nên không ai biết. Đây là
    loại dự phòng phải CỐ Ý không viết.
    """
    rows = [_hang("A", "Điều 1", "x")]
    bang = _bang(rows)

    def _no(*a, **kw):
        raise RuntimeError("LanceDB Cloud lỗi")

    bang.search = _no
    _noi_bang(monkeypatch, bang)

    with pytest.raises(RuntimeError, match="LanceDB Cloud lỗi"):
        pipeline.write_lancedb(rows)

    assert khong_goi_mang == [], "quét hỏng mà vẫn embed — đúng cái đang phòng"
    assert not any("create_fts_index" in x for x in bang.nhat_ky)


def test_chay_lai_lan_hai_khong_embed_gi_them(monkeypatch, khong_goi_mang):
    """Tính bình ổn: chết giữa chừng rồi chạy lại phải tự lành, không nạp lại vô hạn."""
    cu = [_hang("A", "Điều 1", "x")]
    moi = [_hang("A", "Điều 1", "x ĐÃ SỬA")]
    bang = _bang(cu)
    _noi_bang(monkeypatch, bang)

    pipeline.write_lancedb(moi)
    assert khong_goi_mang == [1]

    pipeline.write_lancedb(moi)
    assert khong_goi_mang == [1], "lượt hai vẫn embed ⇒ vân tay không khớp lại được sau khi ghi"


# --- index FTS ------------------------------------------------------------------------------

def test_bang_da_co_index_thi_khong_dung_lai(monkeypatch, khong_goi_mang):
    """Dựng lại index mỗi lượt là reindex toàn bảng — đắt hơn chính thứ đang tiết kiệm."""
    monkeypatch.setattr(pipeline.settings, "lancedb_uri", "db://x")
    monkeypatch.setattr(pipeline.settings, "lancedb_api_key", "k")
    cu = [_hang("A", "Điều 1", "x")]
    moi = [_hang("A", "Điều 1", "x ĐÃ SỬA")]
    bang = _bang(cu)
    _noi_bang(monkeypatch, bang)

    pipeline.write_lancedb(moi)

    assert not any("create_fts_index" in x for x in bang.nhat_ky)
    assert "wait_for_index:text_idx" in bang.nhat_ky


@pytest.mark.parametrize("cloud_enabled", [True, False])
def test_bang_chua_co_index_thi_dung(monkeypatch, khong_goi_mang, cloud_enabled):
    """Bảng chưa có index thì dựng rồi thoát (không gọi wait), áp cho cả cloud lẫn local."""
    cu = [_hang("A", "Điều 1", "x")]
    moi = [_hang("A", "Điều 1", "x ĐÃ SỬA")]
    bang = _bang(cu)
    bang.co_index = False
    _noi_bang(monkeypatch, bang)

    # Ghim cấu hình để không phụ thuộc .env của máy đang chạy
    if cloud_enabled:
        monkeypatch.setattr(pipeline.settings, "lancedb_uri", "db://x")
        monkeypatch.setattr(pipeline.settings, "lancedb_api_key", "k")
    else:
        monkeypatch.setattr(pipeline.settings, "lancedb_uri", "/tmp/local.db")
        monkeypatch.setattr(pipeline.settings, "lancedb_api_key", "")

    pipeline.write_lancedb(moi)

    assert any("create_fts_index" in x for x in bang.nhat_ky)
    assert sum("create_fts_index" in x for x in bang.nhat_ky) == 1  # không dựng đúp
    assert "wait_for_index" not in str(bang.nhat_ky)  # thoát sớm, không gọi wait


def test_bang_co_index_local_thi_dung_lai(monkeypatch, khong_goi_mang):
    """LanceDB nhúng KHÔNG tự đưa hàng mới vào index FTS — phải dựng lại toàn bộ.

    Chờ ở bản nhúng là chờ một thứ không bao giờ tới, nên thay vào đó dựng lại thẳng
    (replace=True). Cục bộ chỉ tốn CPU, không tốn API, nên có thể dựng lại mỗi lần.
    """
    monkeypatch.setattr(pipeline.settings, "lancedb_uri", "/tmp/local.db")
    monkeypatch.setattr(pipeline.settings, "lancedb_api_key", "")
    cu = [_hang("A", "Điều 1", "x")]
    moi = [_hang("A", "Điều 1", "x ĐÃ SỬA")]
    bang = _bang(cu)
    _noi_bang(monkeypatch, bang)

    pipeline.write_lancedb(moi)

    # Phải gọi create_fts_index với replace=True
    assert any("create_fts_index:replace=True" in x for x in bang.nhat_ky)
    # Phải không gọi wait_for_index
    assert "wait_for_index" not in str(bang.nhat_ky)


def test_index_phu_thieu_hang_thi_canh_bao(monkeypatch, khong_goi_mang, capsys):
    """Hàng chưa vào index là hàng nhánh BM25 mù — im lặng ở đây là nửa hybrid chết."""
    monkeypatch.setattr(pipeline.settings, "lancedb_uri", "db://x")
    monkeypatch.setattr(pipeline.settings, "lancedb_api_key", "k")
    cu = [_hang("A", "Điều 1", "x")]
    moi = [_hang("A", "Điều 1", "x ĐÃ SỬA"), _hang("B", "Điều 1", "y")]
    bang = _bang(cu)
    bang.index_phu = 1  # index đứng yên ở 1 hàng dù bảng sắp có 2
    _noi_bang(monkeypatch, bang)

    pipeline.write_lancedb(moi)

    ra = capsys.readouterr().out
    assert "CẢNH BÁO" in ra and "1/2" in ra


def test_index_khong_phai_fts_thi_khong_cho_khong_canh_bao(monkeypatch, khong_goi_mang, capsys):
    """T25 (`docs/TASKLIST.md`) đề xuất `create_scalar_index("doc_id")` — index thứ hai đó phủ
    chậm hơn FTS là chuyện bình thường của BTREE/ANN, không phải nhánh BM25 bị mù. `_cho_index`
    phải không chờ nó (chờ nhầm thứ) và không kêu cảnh báo (kêu oan mỗi lượt chạy mãi mãi).
    """
    monkeypatch.setattr(pipeline.settings, "lancedb_uri", "db://x")
    monkeypatch.setattr(pipeline.settings, "lancedb_api_key", "k")
    cu = [_hang("A", "Điều 1", "x")]
    moi = [_hang("A", "Điều 1", "x ĐÃ SỬA")]
    bang = _bang(cu)
    # BTREE trên doc_id, phủ CHỈ 0/1 hàng — nếu `_cho_index` không lọc theo `index_type` thì
    # ca này sẽ chờ nhầm (`wait_for_index` gồm cả "doc_id_idx") và in cảnh báo "0/1" mãi mãi.
    bang.index_khac = _ChiMucGia("doc_id_idx", 0, index_type="BTREE")
    _noi_bang(monkeypatch, bang)

    pipeline.write_lancedb(moi)

    assert bang.nhat_ky == ["merge_insert:1", "wait_for_index:text_idx"]
    assert "doc_id_idx" not in ",".join(bang.nhat_ky)
    assert "CẢNH BÁO" not in capsys.readouterr().out


# --- ingest_docs ----------------------------------------------------------------------------

def test_ingest_docs_chuyen_tiep_co_xuong_write(monkeypatch):
    """Cờ phải đi hết đường xuống; nuốt mất thì `--doc` im lặng không làm gì."""
    from app.core.schemas import CorpusDocument

    nhan: dict = {}

    def _gia(rows, ep=frozenset(), xoa_doc_du=False):
        nhan.update(ep=ep, xoa_doc_du=xoa_doc_du)
        return len(rows), 99

    monkeypatch.setattr(pipeline, "write_lancedb", _gia)
    monkeypatch.setattr(pipeline.settings, "neo4j_uri", "")
    monkeypatch.setattr(pipeline.settings, "neo4j_password", "")

    docs = [
        CorpusDocument.model_validate({
            "doc_id": "A", "title": "VB A", "doc_type": "Thông tư", "source": "vbpl",
            "valid_from": "2024-01-01", "so_hieu": "1/2024/TT-NHNN",
            "articles": [{"article": "Điều 1", "text": "Nội dung."}],
        })
    ]

    n_ghi, n_tong = pipeline.ingest_docs(docs, [], ep=frozenset({"A"}), xoa_doc_du=True)

    assert nhan == {"ep": frozenset({"A"}), "xoa_doc_du": True}
    assert (n_ghi, n_tong) == (1, 99)


def test_ingest_docs_mac_dinh_khong_ep_khong_xoa(monkeypatch):
    """`app/api/documents.py` gọi trần — mặc định phải không bao giờ xoá được gì."""
    from app.core.schemas import CorpusDocument

    nhan: dict = {}

    def _gia(rows, ep=frozenset(), xoa_doc_du=False):
        nhan.update(ep=ep, xoa_doc_du=xoa_doc_du)
        return len(rows), 1

    monkeypatch.setattr(pipeline, "write_lancedb", _gia)
    monkeypatch.setattr(pipeline.settings, "neo4j_uri", "")
    monkeypatch.setattr(pipeline.settings, "neo4j_password", "")

    docs = [
        CorpusDocument.model_validate({
            "doc_id": "A", "title": "VB A", "doc_type": "Thông tư", "source": "vbpl",
            "valid_from": "2024-01-01", "so_hieu": "1/2024/TT-NHNN",
            "articles": [{"article": "Điều 1", "text": "Nội dung."}],
        })
    ]
    pipeline.ingest_docs(docs, [])

    assert nhan == {"ep": frozenset(), "xoa_doc_du": False}


# --- CLI ------------------------------------------------------------------------------------

def test_cli_doc_lap_lai_duoc_va_mac_dinh_khong_xoa():
    from app.ingestion.__main__ import phan_tich

    a = phan_tich(["data/corpus.real.json", "--doc", "TT66-2025", "--doc", "TT23-2019"])
    assert a.corpus == "data/corpus.real.json"
    assert set(a.doc) == {"TT66-2025", "TT23-2019"}
    assert a.xoa_doc_du is False


def test_cli_khong_tham_so_thi_giu_mac_dinh_cu():
    from app.ingestion.__main__ import phan_tich

    a = phan_tich([])
    assert a.corpus == "data/corpus.sample.json"
    assert a.doc == [] and a.xoa_doc_du is False


def test_cli_bat_duoc_co_xoa():
    from app.ingestion.__main__ import phan_tich

    assert phan_tich(["c.json", "--xoa-doc-du"]).xoa_doc_du is True


# --- bất biến id (latent, chưa vỡ trên corpus thật hôm nay) ---------------------------------

@pytest.mark.skipif(not _CORPUS_REAL.exists(), reason="thiếu data/corpus.real.json")
def test_build_chunks_sinh_id_duy_nhat_tren_corpus_that():
    """`_doc_can_nap` gom vân tay vào `set()` theo `doc_id` — an toàn CHỈ KHI id duy nhất trong
    một văn bản. `_lam_duy_nhat` chỉ khử trùng nhãn TRONG một lần chẻ của MỘT điều, không phải
    across `doc.articles`; hai điều khác nhau sinh trùng nhãn (hiếm, nhưng không cấm) sẽ cho
    cùng `id = f"{doc_id}::{label}"` → `moi[doc]` giữ 2 vân tay trong khi bảng chỉ có 1 hàng cho
    id đó → `cu != moi` MÃI MÃI → văn bản đó bị re-embed toàn bộ ở mọi lượt chạy, im lặng.

    Đường `overwrite` cũ miễn nhiễm (ghi đè theo id trùng cũng chỉ giữ 1 bản). Ca thật hôm nay
    sạch (xác nhận dưới) — test này CHỈ ghim bất biến, không tự sửa `build_chunks`.
    """
    docs, _ = pipeline.load_corpus(_CORPUS_REAL)
    rows = pipeline.build_chunks(docs)
    ids = [r["id"] for r in rows]
    trung = {i for i in ids if ids.count(i) > 1}
    assert trung == set(), f"id trùng trong build_chunks: {sorted(trung)}"


def test_moi_lan_dung_index_deu_mang_fts_opts(monkeypatch, khong_goi_mang):
    """Index dựng thiếu tham số vẫn chạy và vẫn trả kết quả — chỉ là kết quả KHÁC.

    `_FTS_OPTS` giữ `stem=False` và `remove_stop_words=False` vì `ascii_folding` bỏ dấu TRƯỚC
    khi lọc, nên `thẻ`/`số`/`tổ` thành `the`/`so`/`to` và rơi đúng vào danh sách stop-word
    tiếng Anh. Rơi mất tham số ở đây là gài lại quả mìn đó.
    """
    cu = [_hang("A", "Điều 1", "x")]
    moi = [_hang("A", "Điều 1", "x ĐÃ SỬA")]
    bang = _bang(cu)
    bang.co_index = False          # ép đi vào nhánh dựng index
    _noi_bang(monkeypatch, bang)

    pipeline.write_lancedb(moi)

    dung = [x for x in bang.nhat_ky if x.startswith("create_fts_index")]
    assert dung, "không có lời gọi dựng index nào để kiểm"
    for x in dung:
        assert f"opts={sorted(pipeline._FTS_OPTS)}" in x, f"thiếu _FTS_OPTS: {x}"


# --- tầng ghi dùng chung ---------------------------------------------------------------------

def test_ghi_chunk_thay_tai_cho_khong_dung_van_ban_khac(khong_goi_mang):
    bang = _bang([_hang("A", "Điều 1", "x"), _hang("B", "Điều 1", "y")])
    id_cu = {"A": {"A::Điều 1"}}
    moi = [_hang("A", "Điều 1", "x ĐÃ SỬA")]

    n = pipeline._ghi_chunk(bang, {"A"}, moi, id_cu)

    assert n == 1
    assert bang.hang["A::Điều 1"]["text"] == "x ĐÃ SỬA"
    assert bang.hang["B::Điều 1"]["text"] == "y", "văn bản ngoài phạm vi bị đụng"


def test_ghi_chunk_van_ban_rong_thi_xoa_het_chunk_cu(khong_goi_mang):
    """Admin xoá hết Điều rồi bấm duyệt — chunk cũ PHẢI biến khỏi bảng đang phục vụ.

    Bản trước của `ingest_one_doc` về sớm khi `rows` rỗng, và đó là lỗi: truy hồi vẫn trả đúng
    đoạn văn vừa bị xoá trong khi API trả 200 `approved`. Ở đây ca đó không cần cờ riêng — nó
    là luật mồ côi với `rows` rỗng.
    """
    bang = _bang([_hang("A", "Điều 1", "x"), _hang("A", "Điều 2", "x2"), _hang("B", "Điều 1", "y")])
    id_cu = {"A": {"A::Điều 1", "A::Điều 2"}}

    n = pipeline._ghi_chunk(bang, {"A"}, [], id_cu)

    assert n == 0
    assert set(bang.hang) == {"B::Điều 1"}
    assert khong_goi_mang == [], "không có hàng nào để embed mà vẫn gọi embedding"


def test_ghi_chunk_che_ra_it_manh_hon_thi_xoa_mo_coi(khong_goi_mang):
    bang = _bang([_hang("A", "Điều 1 Khoản 1", "p"), _hang("A", "Điều 1 Khoản 2", "q")])
    id_cu = {"A": {"A::Điều 1 Khoản 1", "A::Điều 1 Khoản 2"}}

    pipeline._ghi_chunk(bang, {"A"}, [_hang("A", "Điều 1", "p q")], id_cu)

    assert set(bang.hang) == {"A::Điều 1"}


def test_id_dang_co_chi_doc_dung_pham_vi(khong_goi_mang):
    bang = _bang([_hang("A", "Điều 1", "x"), _hang("A", "Điều 2", "x2"), _hang("B", "Điều 1", "y")])

    ra = pipeline._id_dang_co(bang, {"A"})

    assert ra == {"A": {"A::Điều 1", "A::Điều 2"}}


def test_id_dang_co_tu_choi_doc_id_ban():
    """`doc_id` đi vào vị từ `where` — đây là biên tin cậy, kiểm ở tầng này chứ không tin caller."""
    bang = _bang([_hang("A", "Điều 1", "x")])
    with pytest.raises(ValueError, match="doc_id không hợp lệ"):
        pipeline._id_dang_co(bang, {"A' OR '1'='1"})
