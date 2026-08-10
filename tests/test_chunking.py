"""Test tách chunk mức Khoản cho điều dài.

Nhánh dự phòng (điều dài mà `_KHOAN_RE` không bắt được cấu trúc) từng cắt cửa sổ ký tự
CỨNG — `text[i:i+2000]` — nên vết cắt rơi vào giữa câu, giữa từ. Ca thật duy nhất trong
`data/corpus.real.json` là **TT66-2025 Điều 6** (4313 ký tự): một điều *sửa đổi* đánh số ở
cấp điểm/tiểu mục (`đ)`, `(i)`…`(vii)`, `- `) chứ không phải khoản, và nó nằm trên đường
nóng của lớp phủ (cạnh `66/2025/TT-NHNN#than/dieu_6 → 34/2024/TT-NHNN#…#diem_đ`), nên chữ
kéo vào prompt mở đầu bằng nửa câu.

Hai lớp phòng thủ được ghim ở đây:

* **ranh giới dòng/câu** — vết cắt không bao giờ nằm giữa từ hay giữa câu;
* **thang bậc cấu trúc** — thử điểm → tiểu mục → gạch đầu dòng trước khi chịu thua.

Nhãn vẫn là `(phần k)` ở cả hai lớp: `đ)`/`(i)` trong một điều sửa đổi là chữ TRÍCH của
văn bản bị sửa, gắn nhãn `"Điểm đ"` cho chúng là khai man địa chỉ pháp lý.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from app.ingestion.pipeline import _MAX_CHUNK, _split_khoan, build_chunks, load_corpus

_CORPUS_REAL = Path("data/corpus.real.json")


def _dong(text: str) -> set[str]:
    """Tập dòng đã chuẩn hoá khoảng trắng — để đối chiếu ranh giới cắt."""
    return {" ".join(ln.split()) for ln in text.split("\n") if ln.strip()}


def test_dieu_ngan_giu_nguyen():
    out = _split_khoan("Điều 1", "Nội dung ngắn.")
    assert out == [("Điều 1", "Nội dung ngắn.")]


def test_dieu_dai_tach_theo_khoan():
    khoan = [f"{i}. Nội dung khoản {i}. " + "x" * 700 for i in range(1, 7)]
    text = "Tiêu đề điều\n" + "\n".join(khoan)
    out = _split_khoan("Điều 26", text)
    assert len(out) > 1
    assert all(len(t) <= _MAX_CHUNK + 800 for _, t in out)
    # nhãn có dải khoản, phần mở đầu dính khoản đầu
    assert out[0][0].startswith("Điều 26 Khoản 1")
    assert "Tiêu đề điều" in out[0][1]
    # không mất nội dung
    joined = "\n".join(t for _, t in out)
    for i in range(1, 7):
        assert f"Nội dung khoản {i}" in joined


def test_dieu_dai_khong_co_khoan_cat_cua_so():
    text = "một đoạn rất dài không có cấu trúc khoản " * 200
    out = _split_khoan("Điều 3", text)
    assert len(out) >= 2
    assert out[0][0] == "Điều 3 (phần 1)"


# ---------- B: ranh giới dòng / câu / từ ----------


def test_cua_so_khong_bao_gio_cat_giua_tu():
    """Một dòng dài, không dấu câu: vẫn phải cắt ở khoảng trắng."""
    text = "một đoạn rất dài không có cấu trúc khoản " * 200
    out = _split_khoan("Điều 3", text)
    assert " ".join(t for _, t in out).split() == text.split(), "ghép lại phải đúng chuỗi từ gốc"
    for _, t in out:
        assert t == t.strip()
        assert not t.startswith("ạn") and not t.endswith("khoả"), "cắt giữa từ"


def test_cua_so_cat_o_ranh_gioi_cau_khi_co_dau_cau():
    cau = "Đây là câu số {} trong một đoạn văn rất dài không hề có cấu trúc khoản nào cả. "
    text = "".join(cau.format(i) for i in range(1, 60))
    out = _split_khoan("Điều 4", text)
    assert len(out) >= 2
    for _, t in out:
        assert t.endswith("."), f"mảnh không kết thúc ở ranh giới câu: {t[-60:]!r}"


def test_cua_so_giu_tron_dong():
    """Nhiều dòng ngắn: mỗi mảnh phải gồm TRỌN các dòng gốc, không xé dòng làm đôi."""
    goc = "\n".join(f"Dòng số {i}: " + "nội dung " * 20 for i in range(1, 40))
    out = _split_khoan("Điều 5", goc)
    assert len(out) >= 2
    hop_le = _dong(goc)
    for _, t in out:
        assert _dong(t) <= hop_le, "mảnh chứa dòng không nguyên vẹn"


# ---------- A: thang bậc cấu trúc ----------


def test_thang_bac_diem_va_tieu_muc():
    """Dựng lại đúng hình dạng TT66-2025 Điều 6: mệnh lệnh sửa + `đ)` + `(i)`…"""
    text = "\n".join(
        [
            "Sửa đổi, bổ sung điểm đ khoản 2 Điều 9",
            "“đ) Đối với trường hợp đề nghị cấp bổ sung vào Giấy phép: " + "chi tiết " * 30,
        ]
        + [f"({s}) Tài liệu thứ {s} kèm theo hồ sơ: " + "mô tả " * 60 for s in ("i", "ii", "iii", "iv", "v")]
    )
    assert len(text) > _MAX_CHUNK
    out = _split_khoan("Điều 6", text)

    assert len(out) >= 2
    assert [n for n, _ in out] == [f"Điều 6 (phần {i + 1})" for i in range(len(out))]
    hop_le = _dong(text)
    for _, t in out:
        assert _dong(t) <= hop_le, "thang bậc phải cắt ở ranh giới dòng"
    assert _dong("\n".join(t for _, t in out)) == hop_le, "mất dòng"


def test_thang_bac_gach_dau_dong():
    text = "Mở đầu điều.\n" + "\n".join(
        f"- Gạch đầu dòng thứ {i}: " + "nội dung " * 40 for i in range(1, 12)
    )
    assert len(text) > _MAX_CHUNK
    out = _split_khoan("Điều 7", text)
    assert len(out) >= 2
    hop_le = _dong(text)
    for _, t in out:
        assert _dong(t) <= hop_le


# ---------- Ca thật trên corpus ----------


@pytest.mark.skipif(not _CORPUS_REAL.exists(), reason="thiếu data/corpus.real.json")
def test_TT66_dieu_6_khong_con_cat_giua_cau():
    docs, _ = load_corpus(_CORPUS_REAL)
    d = next(x for x in docs if x.doc_id == "TT66-2025")
    a = next(y for y in d.articles if y.article == "Điều 6")
    assert len(a.text) > _MAX_CHUNK  # tiền đề của ca này

    out = _split_khoan(a.article, a.text)
    hop_le = _dong(a.text)
    for nhan, t in out:
        assert _dong(t) <= hop_le, f"{nhan} cắt giữa dòng — đúng lỗi đang sửa"
    assert _dong("\n".join(t for _, t in out)) == hop_le, "mất nội dung"


# ---------- Nhãn phải định danh được đúng một chunk ----------


def _dieu_danh_so_lap_lai() -> str:
    """Hình dạng `TT23-2019 Điều 1`: một điều SỬA ĐỔI chép nguyên văn nhiều điều của văn bản
    bị sửa, nên số khoản khởi động lại nhiều lần trong cùng một điều."""
    khoi = []
    for lan in range(1, 4):
        khoi.append(f"Sửa đổi Điều {lan * 5} như sau:")
        khoi += [f"{i}. Khối {lan} khoản {i}. " + "nội dung " * 90 for i in range(1, 4)]
    return "\n".join(khoi)


def test_nhan_trung_trong_mot_dieu_duoc_danh_so_phan_biet():
    out = _split_khoan("Điều 1", _dieu_danh_so_lap_lai())
    nhan = [n for n, _ in out]
    assert len(nhan) == len(set(nhan)), f"nhãn trùng ⇒ hai chunk khác nhau cùng một id: {nhan}"
    assert any("(2)" in n for n in nhan), "phải có hậu tố phân biệt, không phải đổi cách chẻ"


def test_nhan_dai_khoan_khong_bao_gio_nguoc():
    """`"Khoản 18-1"` nói dối: nó tuyên bố một dải từ 18 đến 1."""
    out = _split_khoan("Điều 1", _dieu_danh_so_lap_lai())
    for nhan, _ in out:
        if " Khoản " not in nhan:
            continue
        dai = nhan.split(" Khoản ")[-1].split(" (")[0]
        if "-" not in dai:
            continue
        dau, cuoi = dai.split("-")
        assert int(dau) < int(cuoi), f"nhãn dải ngược: {nhan!r}"


@pytest.mark.skipif(not _CORPUS_REAL.exists(), reason="thiếu data/corpus.real.json")
def test_khong_chunk_nao_trung_id_tren_corpus_that():
    """Bất biến toàn corpus. `id` là khoá của mọi thứ phía sau: `_rrf` gom kết quả vào dict
    theo `id`, nên hai chunk trùng id thì một cái bị nuốt và trích dẫn trỏ tới một địa chỉ có
    nhiều nội dung khác nhau. Đo 09/08 trước khi sửa: 5 id trùng, 7 hàng đụng nhau, toàn bộ ở
    TT23-2019.
    """
    docs, _ = load_corpus(_CORPUS_REAL)
    rows = build_chunks(docs)
    dem = Counter(r["id"] for r in rows)
    trung = {k: v for k, v in dem.items() if v > 1}
    assert not trung, "id trùng:\n" + "\n".join(f"  {k} x{v}" for k, v in trung.items())


@pytest.mark.skipif(not _CORPUS_REAL.exists(), reason="thiếu data/corpus.real.json")
def test_moi_chunk_deu_gom_tron_dong_cua_dieu():
    """Bất biến toàn corpus: không chunk nào chứa một dòng bị xé.

    Ghim cả hai nhánh (khoản và dự phòng) cùng lúc — nhánh nào lỡ quay về cắt ký tự cứng
    thì ca này đỏ, không cần biết văn bản nào gây ra.
    """
    docs, _ = load_corpus(_CORPUS_REAL)
    theo_dieu = {
        f"{d.doc_id}::{a.article}": _dong(a.text) for d in docs for a in d.articles
    }
    xau: list[str] = []
    for r in build_chunks(docs):
        goc = theo_dieu.get(f"{r['doc_id']}::{r['article'].split(' Khoản ')[0].split(' (phần ')[0]}")
        if goc is None:
            continue
        thua = _dong(r["text"]) - goc
        if thua:
            xau.append(f"{r['id']}: {sorted(thua)[0][:80]!r}")
    assert not xau, "chunk chứa dòng bị xé:\n" + "\n".join(xau[:10])
