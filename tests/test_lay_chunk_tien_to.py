"""Tra chunk theo TIỀN TỐ điều — id cấp điều không tồn tại khi điều bị chẻ theo khoản.

Fix wave 06/08, IMPORTANT 2. `chu_thich_ket_qua` dựng id `"{doc}::{Điều N}"` để kéo lời văn
mới về, nhưng `app/ingestion/pipeline.py` mint id là `"{doc}::{label}"` với `label` thành
`"Điều N Khoản a-b"` / `"Điều N (phần k)"` cho mọi điều dài hơn `_MAX_CHUNK = 2000`. Đo trên
`data/overlay/lop_phu.json` + `data/corpus.real.json`: **31 trong 40** cạnh cần đường kéo này
trỏ vào một điều KHÔNG có id cấp điều (ND80-2016 Điều 1 = 6058 ký tự, TT30-2016 Điều 1 = 5346,
Điều 3 = 4113…). Tra đúng id ⇒ khớp 0 hàng ⇒ fail-open nuốt.

Test này KHÔNG mock hàm tra: nó dựng một BẢNG giả từ **id thật** sinh bởi `build_chunks` trên
`data/corpus.real.json` (tracked), rồi bắt `_open_table` trả về bảng đó. Mock đúng cái đang
hỏng thì chứng minh được gì — đó chính là cách khuyết tật này sống sót qua mười vòng review.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.ingestion.pipeline import build_chunks, load_corpus
from app.knowledge import retrieval

_CORPUS_REAL = Path("data/corpus.real.json")
pytestmark = pytest.mark.skipif(
    not _CORPUS_REAL.exists(), reason="thiếu data/corpus.real.json"
)

_WHERE_RE = re.compile(r"^doc_id IN \((.*)\)$")


class _TruyVanGia:
    """Chỉ hiểu đúng cú pháp `where` mà `lay_chunk_theo_tien_to` được phép dùng."""

    def __init__(self, hang: list[dict]) -> None:
        self._hang = hang
        self._gioi_han: int | None = None

    def where(self, dieu_kien: str):
        m = _WHERE_RE.match(dieu_kien)
        assert m, f"cú pháp where lạ, LanceDB Cloud có thể không nhận: {dieu_kien!r}"
        ids = {s.strip().strip("'") for s in m.group(1).split(",")}
        self._hang = [r for r in self._hang if r.get("doc_id") in ids]
        return self

    def limit(self, n: int):
        self._gioi_han = n
        return self

    def to_list(self) -> list[dict]:
        return self._hang[: self._gioi_han] if self._gioi_han else list(self._hang)


class _BangGia:
    def __init__(self, hang: list[dict]) -> None:
        self._hang = hang

    def search(self, *a, **kw):
        return _TruyVanGia(list(self._hang))


@pytest.fixture
def bang_that(monkeypatch):
    """Bảng giả mang ĐÚNG hình dạng id của corpus thật (không có cột vector — không cần)."""
    docs, _rels = load_corpus(_CORPUS_REAL)
    hang = [
        {k: v for k, v in r.items() if k != "vector"} for r in build_chunks(docs)
    ]
    monkeypatch.setattr(retrieval, "_open_table", lambda: _BangGia(hang))
    return hang


def test_dieu_bi_che_theo_khoan_van_tra_duoc(bang_that):
    """ND80-2016 Điều 1 (6058 ký tự) không có id `"ND80-2016::Điều 1"` — tiền tố phải khớp."""
    assert not any(r["id"] == "ND80-2016::Điều 1" for r in bang_that)  # tiền đề của ca này
    ra = retrieval.lay_chunk_theo_tien_to(["ND80-2016::Điều 1"])
    assert ra, "điều bị chẻ theo khoản mà tra ra rỗng — đúng lỗi đang sửa"
    assert all(r["doc_id"] == "ND80-2016" for r in ra)
    assert all(r["article"].startswith("Điều 1 ") for r in ra)


def test_khong_khop_dieu_khac_co_cung_tien_to_chu_so(bang_that):
    """`"Điều 1"` KHÔNG được khớp `"Điều 10"`/`"Điều 12"` — ranh giới phải là dấu cách."""
    ra = retrieval.lay_chunk_theo_tien_to(["TT66-2025::Điều 1"], moi_tien_to=99)
    nhan = {r["article"] for r in ra}
    assert nhan, "TT66-2025 Điều 1 phải có ít nhất một chunk"
    assert all(n == "Điều 1" or n.startswith("Điều 1 ") for n in nhan)
    assert not any(re.match(r"^Điều 1\d", n) for n in nhan)


def test_dieu_ngan_van_khop_chinh_xac(bang_that):
    ra = retrieval.lay_chunk_theo_tien_to(["TT41-2025::Điều 13"])
    assert [r["id"] for r in ra] == ["TT41-2025::Điều 13"]


def test_cat_so_manh_moi_dieu(bang_that):
    """Điều dài cho nhiều mảnh — lấy có hạn, không nhồi cả điều vào prompt."""
    nhieu = retrieval.lay_chunk_theo_tien_to(["TT66-2025::Điều 12"], moi_tien_to=99)
    assert len(nhieu) > 2  # TT66-2025 Điều 12 = 7217 ký tự ⇒ nhiều mảnh
    it = retrieval.lay_chunk_theo_tien_to(["TT66-2025::Điều 12"])
    assert len(it) == retrieval._TOI_DA_MANH_MOI_DIEU
    # Lấy theo thứ tự nhãn TỰ NHIÊN, không theo thứ tự bảng trả về.
    assert [r["article"] for r in it] == [r["article"] for r in nhieu][: len(it)]


def test_tien_to_la_thi_tra_rong_khong_nem(bang_that):
    assert retrieval.lay_chunk_theo_tien_to([]) == []
    assert retrieval.lay_chunk_theo_tien_to(["khong-co-dau-hai-cham"]) == []
    assert retrieval.lay_chunk_theo_tien_to(["LA-XYZ::Điều 1"]) == []


def test_bang_hong_thi_fail_open(monkeypatch):
    def _no():
        raise RuntimeError("LanceDB Cloud lỗi")

    monkeypatch.setattr(retrieval, "_open_table", _no)
    assert retrieval.lay_chunk_theo_tien_to(["ND80-2016::Điều 1"]) == []
