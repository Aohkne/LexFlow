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

from app.ingestion import pipeline

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


class _TruyVanGia:
    """Chỉ hiểu đúng cú pháp mà `_doc_can_nap` được phép dùng."""

    def __init__(self, hang: list[dict]) -> None:
        self._hang = hang
        self._cot: list[str] | None = None
        self._gioi_han: int | None = None

    def select(self, cot: list[str]):
        self._cot = list(cot)
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
        return [_ChiMucGia("text_idx", phu)]

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

    def create_fts_index(self, cot: str, **kw) -> None:
        self.nhat_ky.append("create_fts_index")


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
