# Nối lớp phủ dưới-văn-bản vào sản phẩm — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Câu trả lời trên web không còn trích khoản đã bị bãi bỏ, và khi khoản đã bị sửa thì
chỉ đúng sang lời văn mới kèm bản hiện hành.

**Architecture:** Lớp phủ được **đóng gói lúc build** thành một artefact tự chứa
(`data/overlay/lop_phu.json`) vì span `loi_van_moi` chỉ giải được từ `data/raw/vbpl/` vốn
gitignored. Runtime đọc artefact qua **một cổng duy nhất** (`app/knowledge/lop_phu.py`) bọc
`dinh_tuyen` + `phien_ban_hien_hanh`; `answer.py`/`review.py` chú thích kết quả retrieval
**sau** khi tìm, không đổi gì trong LanceDB. Neo4j nhận bản sao node/cạnh chỉ để xem.

**Tech Stack:** Python 3.12 · pydantic v2 · pytest · LanceDB 0.34 · Neo4j 5 (Aura) ·
FastAPI · Next.js 16 · uv · ruff

## Global Constraints

- **Không sửa `noi_dung` và `articles[].text`.** Khuyết tật của nguồn báo vào `canh_bao`, không nắn.
- **Không bịa khoá, không bịa chữ.** Không giải được ⇒ `None` + cảnh báo có địa chỉ, không đoán gần đúng.
- **Bất biến char_span:** `loi_van_moi_text` phải là lát cắt nguyên văn `noi_dung[char_start:char_end]` — không strip, không chuẩn hoá khoảng trắng.
- **Fail-open:** artefact thiếu/hỏng, Neo4j chết, LanceDB lỗi ⇒ trả kết quả chưa chú thích, KHÔNG ném lỗi ra người dùng.
- **Không đổi ngưỡng chunking** (`_MAX_CHUNK = 2000` trong `app/ingestion/pipeline.py`) — đổi là vỡ bộ nhãn 13/13 đã đo.
- **Test không được phụ thuộc `data/raw/vbpl/`** (gitignored, không có trên CI). Dùng fixture tự dựng hoặc `eval/overlay/canh_tac_dong.jsonl` (tracked).
- **Commit chỉ các file mình tạo/sửa**, liệt kê tường minh: `git add <path> <path>`. **Tuyệt đối không** `git add -A`, `git add .`, `git commit -a`. Repo có nhiều file dở tay của người dùng (`anotate/`, `app/ingestion/vbpl.py`, `.vscode/`, `docs/*.xlsx`, `eval/ontology/html/`, `research/crawl_list.txt`, `pyproject.toml`, `uv.lock`, `research/schema-kg-v05.html`) — commit nhầm là hỏng cây làm việc của họ.
- **Commit message tiếng Anh**, Conventional Commits, kết bằng `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- **Ghi file bằng công cụ Write/Edit** (UTF-8), không dùng shell redirect — PowerShell mã hoá lại và làm lệch char_span.
- Trước khi commit: `uv run pytest -q` và `uv run ruff check .` phải xanh. Nền hiện tại: **555 test**.

---

### Task 1: Đóng gói lớp phủ thành artefact tự chứa

**Files:**
- Create: `app/ontology/dong_goi.py`
- Test: `tests/test_dong_goi.py`

**Interfaces:**
- Consumes: `app.ontology.tac_dong.CanhTacDong`, `doc_tac_dong(thu_muc) -> (list[CanhTacDong], list[str])`; `app.ingestion.vbpl_corpus.file_da_chuyen_khuon(thu_muc) -> list[Path]`, `duong_dan_toan_van(p) -> Path`
- Produces:
  - `class CanhGoi(BaseModel)` — `nguon, dich, thao_tac, valid_from, loi_van_moi, loi_van_moi_text, xuat_xu_doc_id, xuat_xu_article, menh_lenh`; method `thanh_canh() -> CanhTacDong`
  - `class GoiLopPhu(BaseModel)` — `sinh_luc: str`, `so_hieu_theo_doc: dict[str, str]`, `canh: list[CanhGoi]`
  - `boi_dap(canh, ban_do, doc_id_theo_so_hieu) -> tuple[list[CanhGoi], list[str]]` — hàm THUẦN
  - `dong_goi(thu_muc: Path, corpus_path: Path, ngay: str) -> tuple[GoiLopPhu, list[str]]`

`ban_do` là `dict[so_hieu, tuple[noi_dung, articles]]`; `articles` là list dict có
`article`/`char_start`/`char_end`.

- [ ] **Step 1: Write the failing test**

Tạo `tests/test_dong_goi.py`:

```python
"""Đóng gói cạnh tác động thành artefact tự chứa — giải span thành chữ, không bịa."""
from app.ontology.dong_goi import CanhGoi, GoiLopPhu, boi_dap
from app.ontology.tac_dong import CanhTacDong

_NOI_DUNG = 'Điều 1. Sửa đổi\n1. Sửa khoản 2 như sau:\n"2. Lời văn mới."\nĐiều 2. Hiệu lực\n'
_ARTICLES = [
    {"article": "Điều 1", "char_start": 0, "char_end": 63},
    {"article": "Điều 2", "char_start": 63, "char_end": len(_NOI_DUNG)},
]
_SPAN = (_NOI_DUNG.index('"2.'), _NOI_DUNG.index('mới."') + len('mới."'))


def _canh(**kw) -> CanhTacDong:
    goc = dict(
        nguon="41/2025/TT-NHNN#than/dieu_1#khoan_1",
        dich="40/2024/TT-NHNN#than/dieu_5#khoan_2",
        thao_tac="sua_doi",
        loi_van_moi=_SPAN,
        valid_from="2025-07-01",
        menh_lenh="Sửa khoản 2 như sau:",
    )
    return CanhTacDong(**{**goc, **kw})


_BAN_DO = {"41/2025/TT-NHNN": (_NOI_DUNG, _ARTICLES)}
_DOC_ID = {"41/2025/TT-NHNN": "TT41-2025"}


def test_giai_span_thanh_chu_nguyen_van():
    ra, cb = boi_dap([_canh()], _BAN_DO, _DOC_ID)
    assert cb == []
    assert ra[0].loi_van_moi_text == _NOI_DUNG[_SPAN[0]:_SPAN[1]]
    assert ra[0].loi_van_moi_text.startswith('"2.')  # nguyên văn, không strip dấu ngoặc
    assert ra[0].xuat_xu_doc_id == "TT41-2025"
    assert ra[0].xuat_xu_article == "Điều 1"


def test_thieu_toan_van_thi_bao_chu_khong_bia():
    ra, cb = boi_dap([_canh()], {}, _DOC_ID)
    assert ra[0].loi_van_moi_text is None
    assert len(cb) == 1 and "41/2025/TT-NHNN" in cb[0]


def test_span_ngoai_pham_vi_thi_bao():
    ra, cb = boi_dap([_canh(loi_van_moi=(10, 9_999))], _BAN_DO, _DOC_ID)
    assert ra[0].loi_van_moi_text is None
    assert len(cb) == 1 and "9999" in cb[0].replace(" ", "")


def test_bai_bo_khong_co_loi_van_moi_thi_khong_canh_bao():
    ra, cb = boi_dap([_canh(thao_tac="bai_bo", loi_van_moi=None)], _BAN_DO, _DOC_ID)
    assert ra[0].loi_van_moi_text is None and cb == []


def test_thanh_canh_quay_ve_dung_CanhTacDong():
    c = boi_dap([_canh()], _BAN_DO, _DOC_ID)[0][0].thanh_canh()
    assert isinstance(c, CanhTacDong)
    assert (c.nguon, c.dich, c.thao_tac, c.loi_van_moi) == (
        "41/2025/TT-NHNN#than/dieu_1#khoan_1",
        "40/2024/TT-NHNN#than/dieu_5#khoan_2",
        "sua_doi",
        _SPAN,
    )


def test_goi_lop_phu_round_trip_json():
    goi = GoiLopPhu(
        sinh_luc="2026-08-06",
        so_hieu_theo_doc={"TT41-2025": "41/2025/TT-NHNN"},
        canh=boi_dap([_canh()], _BAN_DO, _DOC_ID)[0],
    )
    lai = GoiLopPhu.model_validate_json(goi.model_dump_json())
    assert lai.canh[0].loi_van_moi == _SPAN  # tuple sống sót qua JSON
    assert lai.canh[0].loi_van_moi_text == goi.canh[0].loi_van_moi_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dong_goi.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.ontology.dong_goi'`

- [ ] **Step 3: Write the implementation**

Tạo `app/ontology/dong_goi.py`:

```python
"""Đóng gói lớp phủ thành artefact TỰ CHỨA cho runtime.

Vì sao phải đóng gói thay vì để runtime tự giải: `loi_van_moi` là span vào `noi_dung` của
văn bản sửa, mà `noi_dung` chỉ nằm ở `data/raw/vbpl/raw/` — thư mục **gitignored**. Một
checkout sạch hay một image Cloud Run không có gì để giải. Nên giải một lần ở đây, ghi chữ
đã giải vào artefact tracked, và runtime không bao giờ chạm `raw/`.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from app.ingestion.vbpl_corpus import duong_dan_toan_van, file_da_chuyen_khuon
from app.ontology.tac_dong import CanhTacDong, doc_tac_dong


class CanhGoi(BaseModel):
    """Cạnh tác động + chữ đã giải sẵn, đủ để runtime làm việc mà không cần `raw/`."""

    nguon: str
    dich: str
    thao_tac: str
    valid_from: str | None = None
    loi_van_moi: tuple[int, int] | None = None
    #: Lát cắt NGUYÊN VĂN `noi_dung[char_start:char_end]` — không strip, không chuẩn hoá.
    loi_van_moi_text: str | None = None
    #: Điều của văn bản SỬA chứa khối lời văn mới (cấp ĐIỀU, vì `articles[]` chỉ tới điều).
    xuat_xu_doc_id: str | None = None
    xuat_xu_article: str | None = None
    menh_lenh: str

    def thanh_canh(self) -> CanhTacDong:
        """Quay về `CanhTacDong` để dùng lại nguyên luật của `hien_hanh`/`dinh_tuyen`."""
        return CanhTacDong(
            nguon=self.nguon,
            dich=self.dich,
            thao_tac=self.thao_tac,
            loi_van_moi=self.loi_van_moi,
            valid_from=self.valid_from,
            menh_lenh=self.menh_lenh,
        )


class GoiLopPhu(BaseModel):
    sinh_luc: str
    #: `doc_id` → `so_hieu`, đúng chiều `dinh_tuyen.khoa_tu_chunk_id` cần.
    so_hieu_theo_doc: dict[str, str]
    canh: list[CanhGoi]


def _dieu_chua_span(articles: list[dict], span: tuple[int, int]) -> str | None:
    a0, b0 = span
    for a in articles:
        cs, ce = a.get("char_start"), a.get("char_end")
        if isinstance(cs, int) and isinstance(ce, int) and cs <= a0 and b0 <= ce:
            return a.get("article")
    return None


def boi_dap(
    canh: list[CanhTacDong],
    ban_do: dict[str, tuple[str, list[dict]]],
    doc_id_theo_so_hieu: dict[str, str],
) -> tuple[list[CanhGoi], list[str]]:
    """Cạnh → cạnh-đã-bồi-đắp + cảnh báo. Hàm THUẦN (không I/O) để test được không cần `raw/`."""
    ra: list[CanhGoi] = []
    canh_bao: list[str] = []
    for c in canh:
        text: str | None = None
        xx_doc: str | None = None
        xx_art: str | None = None
        if c.loi_van_moi is not None:
            sh = c.nguon.split("#", 1)[0]
            muc = ban_do.get(sh)
            if muc is None:
                canh_bao.append(
                    f"{sh}: thiếu toàn văn để giải span {c.loi_van_moi} — bỏ lời văn mới"
                )
            else:
                noi_dung, articles = muc
                a0, b0 = c.loi_van_moi
                if 0 <= a0 < b0 <= len(noi_dung):
                    text = noi_dung[a0:b0]
                    xx_art = _dieu_chua_span(articles, c.loi_van_moi)
                    xx_doc = doc_id_theo_so_hieu.get(sh)
                else:
                    canh_bao.append(
                        f"{sh}: span {c.loi_van_moi} ngoài phạm vi noi_dung "
                        f"({len(noi_dung)} ký tự) — bỏ lời văn mới"
                    )
        ra.append(
            CanhGoi(
                nguon=c.nguon,
                dich=c.dich,
                thao_tac=c.thao_tac,
                valid_from=c.valid_from,
                loi_van_moi=c.loi_van_moi,
                loi_van_moi_text=text,
                xuat_xu_doc_id=xx_doc,
                xuat_xu_article=xx_art,
                menh_lenh=c.menh_lenh,
            )
        )
    return ra, canh_bao


def _ban_do_toan_van(thu_muc: Path) -> dict[str, tuple[str, list[dict]]]:
    """`so_hieu` → (`noi_dung` thô, `articles` có char_start/char_end). Chỉ dùng lúc build."""
    ra: dict[str, tuple[str, list[dict]]] = {}
    for p in file_da_chuyen_khuon(thu_muc):
        try:
            corpus = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        so_hieu = corpus.get("so_hieu")
        p_tho = duong_dan_toan_van(p)
        if not so_hieu or not p_tho.exists():
            continue
        try:
            tho = json.loads(p_tho.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        ra[so_hieu] = (tho.get("noi_dung") or "", corpus.get("articles") or [])
    return ra


def dong_goi(thu_muc: Path, corpus_path: Path, ngay: str) -> tuple[GoiLopPhu, list[str]]:
    canh, canh_bao = doc_tac_dong(thu_muc)
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    so_hieu_theo_doc = {
        d["doc_id"]: d["so_hieu"]
        for d in corpus.get("documents", [])
        if d.get("doc_id") and d.get("so_hieu")
    }
    doc_id_theo_so_hieu = {v: k for k, v in so_hieu_theo_doc.items()}
    boi, cb = boi_dap(canh, _ban_do_toan_van(thu_muc), doc_id_theo_so_hieu)
    return (
        GoiLopPhu(sinh_luc=ngay, so_hieu_theo_doc=so_hieu_theo_doc, canh=boi),
        canh_bao + cb,
    )


def main() -> None:
    import datetime

    goi, canh_bao = dong_goi(
        Path("data/raw/vbpl"),
        Path("data/corpus.real.json"),
        datetime.date.today().isoformat(),
    )
    dich = Path("data/overlay/lop_phu.json")
    dich.parent.mkdir(parents=True, exist_ok=True)
    dich.write_text(goi.model_dump_json(indent=1), encoding="utf-8")

    co_span = sum(1 for c in goi.canh if c.loi_van_moi is not None)
    giai_duoc = sum(1 for c in goi.canh if c.loi_van_moi_text is not None)
    print(f"cạnh:            {len(goi.canh)}")
    print(f"có lời văn mới:  {co_span}")
    print(f"giải được chữ:   {giai_duoc}")
    print(f"cảnh báo:        {len(canh_bao)}")
    print(f"ghi -> {dich} ({dich.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_dong_goi.py -q`
Expected: PASS, 6 passed

- [ ] **Step 5: Sinh artefact thật và đối chứng với JSONL**

Run: `$env:PYTHONIOENCODING="utf-8"; uv run python -m app.ontology.dong_goi`
Rồi kiểm số cạnh khớp nguồn:

```powershell
uv run python -c "import json,pathlib; g=json.loads(pathlib.Path('data/overlay/lop_phu.json').read_text(encoding='utf-8')); n=sum(1 for _ in open('eval/overlay/canh_tac_dong.jsonl',encoding='utf-8')); print(len(g['canh']), n, len(g['canh'])==n)"
```

Expected: in ra `178 178 True`. Nếu KHÔNG khớp: **dừng, báo DONE_WITH_CONCERNS** kèm hai con
số — nghĩa là `doc_tac_dong` cho kết quả khác lần chạy 05/08, phải điều tra chứ không chỉnh test.

- [ ] **Step 6: Run full suite + lint**

Run: `uv run pytest -q ; uv run ruff check .`
Expected: 561 passed, ruff sạch

- [ ] **Step 7: Commit**

```bash
git add app/ontology/dong_goi.py tests/test_dong_goi.py data/overlay/lop_phu.json
git commit -F - <<'EOF'
feat(overlay): pack impact edges into a self-contained runtime artefact

Resolve loi_van_moi spans to text at build time; raw/ is gitignored so
runtime can never do it.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

### Task 2: Cổng runtime — chú thích một chunk

**Files:**
- Create: `app/knowledge/lop_phu.py`
- Modify: `app/ontology/dinh_tuyen.py` (thêm trường `canh` vào `KetQuaTuyen`)
- Test: `tests/test_lop_phu.py`

**Interfaces:**
- Consumes: `GoiLopPhu`, `CanhGoi` (Task 1); `dinh_tuyen(chunk_id, span_chunk, canh, so_hieu_theo_doc, hom_nay) -> KetQuaTuyen | None`; `phien_ban_hien_hanh(khoa, canh, hom_nay) -> PhienBanHienHanh`; `khoa_tu_chunk_id(chunk_id, so_hieu_theo_doc)`
- Produces:
  - `class ChuThichHieuLuc(BaseModel)` — `nhanh: str`, `trang_thai: Literal["nguyen_ven","da_sua","bi_bai_bo","la_loi_sua"]`, `trich_dan_dung_chu: str`, `khoa_goc: str`, `khoa_dich: str | None`, `sua_boi_doc_id: str | None`, `sua_boi_article: str | None`, `ban_hien_hanh: str | None`, `xuat_xu_doc_id: str | None`, `xuat_xu_article: str | None`
  - `tai_lop_phu(duong_dan: str = "data/overlay/lop_phu.json") -> LopPhuRuntime | None` (lru_cache)
  - `chu_thich_chunk(chunk: dict, as_of: str, lp: LopPhuRuntime | None = None) -> ChuThichHieuLuc | None`

`KetQuaTuyen` nhận thêm `canh: CanhTacDong | None = None` — cạnh CHỦ đã quyết định nhánh.
Không có nó thì `lop_phu` phải mô phỏng lại luật chọn cạnh của `dinh_tuyen` (kể cả nhánh
sâu-hơn) — đúng kiểu chép luật lần hai mà cả tháng 8 tránh.

- [ ] **Step 1: Write the failing test**

Tạo `tests/test_lop_phu.py`:

```python
"""Cổng runtime của lớp phủ: chunk retrieval → chú thích hiệu lực cấp khoản."""
import json

import pytest

from app.knowledge.lop_phu import ChuThichHieuLuc, chu_thich_chunk, tai_lop_phu
from app.ontology.dong_goi import CanhGoi, GoiLopPhu

_MOI = '"7. Hạn mức mới là 200 triệu đồng."'


def _goi() -> GoiLopPhu:
    return GoiLopPhu(
        sinh_luc="2026-08-06",
        so_hieu_theo_doc={"TT40-2024": "40/2024/TT-NHNN", "TT41-2025": "41/2025/TT-NHNN"},
        canh=[
            CanhGoi(
                nguon="41/2025/TT-NHNN#than/dieu_1#khoan_2",
                dich="40/2024/TT-NHNN#than/dieu_8#khoan_7",
                thao_tac="sua_doi",
                valid_from="2025-07-01",
                loi_van_moi=(100, 100 + len(_MOI)),
                loi_van_moi_text=_MOI,
                xuat_xu_doc_id="TT41-2025",
                xuat_xu_article="Điều 1",
                menh_lenh="Sửa đổi khoản 7 Điều 8 như sau:",
            ),
            CanhGoi(
                nguon="41/2025/TT-NHNN#than/dieu_2",
                dich="40/2024/TT-NHNN#than/dieu_9",
                thao_tac="bai_bo",
                valid_from="2025-07-01",
                menh_lenh="Bãi bỏ Điều 9.",
            ),
        ],
    )


@pytest.fixture
def lp(tmp_path):
    p = tmp_path / "lop_phu.json"
    p.write_text(_goi().model_dump_json(), encoding="utf-8")
    tai_lop_phu.cache_clear()
    ra = tai_lop_phu(str(p))
    yield ra
    tai_lop_phu.cache_clear()


def _chunk(cid: str, text: str = "nội dung nền") -> dict:
    return {"id": cid, "doc_id": cid.partition("::")[0], "text": text}


def test_nguyen_ven(lp):
    ct = chu_thich_chunk(_chunk("TT40-2024::Điều 3"), "2026-08-06", lp)
    assert ct.trang_thai == "nguyen_ven" and ct.ban_hien_hanh is None


def test_da_sua_co_ban_hien_hanh_va_xuat_xu(lp):
    ct = chu_thich_chunk(_chunk("TT40-2024::Điều 8 Khoản 7"), "2026-08-06", lp)
    assert ct.trang_thai == "da_sua"
    assert ct.ban_hien_hanh == _MOI
    assert (ct.sua_boi_doc_id, ct.sua_boi_article) == ("TT41-2025", "Điều 1 Khoản 2")
    assert (ct.xuat_xu_doc_id, ct.xuat_xu_article) == ("TT41-2025", "Điều 1")


def test_bi_bai_bo(lp):
    ct = chu_thich_chunk(_chunk("TT40-2024::Điều 9"), "2026-08-06", lp)
    assert ct.trang_thai == "bi_bai_bo"
    assert "đã bị bãi bỏ bởi" in ct.trich_dan_dung_chu
    assert ct.ban_hien_hanh is None  # bãi bỏ thì KHÔNG có bản hiện hành


def test_chua_toi_ngay_hieu_luc_thi_van_nguyen_ven(lp):
    ct = chu_thich_chunk(_chunk("TT40-2024::Điều 8 Khoản 7"), "2025-01-01", lp)
    assert ct.trang_thai == "nguyen_ven"


def test_nhanh_3_nhan_dien_bang_chu_khong_can_toa_do(lp):
    """Chunk của văn bản SỬA mang đúng khối lời văn mới → trích dẫn về đúng chủ (TT40)."""
    ct = chu_thich_chunk(
        _chunk("TT41-2025::Điều 1", f"Sửa đổi khoản 7 Điều 8 như sau:\n{_MOI}"),
        "2026-08-06",
        lp,
    )
    assert ct.trang_thai == "la_loi_sua"
    assert ct.khoa_dich == "40/2024/TT-NHNN#than/dieu_8#khoan_7"
    assert "TT40-2024" in ct.trich_dan_dung_chu


def test_chunk_van_ban_la_tra_None(lp):
    assert chu_thich_chunk(_chunk("LA-XYZ::Điều 1"), "2026-08-06", lp) is None


def test_artefact_hong_thi_fail_open(tmp_path):
    p = tmp_path / "hong.json"
    p.write_text("{ không phải json", encoding="utf-8")
    tai_lop_phu.cache_clear()
    assert tai_lop_phu(str(p)) is None
    assert chu_thich_chunk(_chunk("TT40-2024::Điều 9"), "2026-08-06", tai_lop_phu(str(p))) is None
    tai_lop_phu.cache_clear()


def test_artefact_thieu_thi_fail_open(tmp_path):
    tai_lop_phu.cache_clear()
    assert tai_lop_phu(str(tmp_path / "khong-co.json")) is None
    tai_lop_phu.cache_clear()


def test_artefact_that_tai_duoc():
    """Artefact do Task 1 sinh phải nạp được và cho ra cạnh."""
    tai_lop_phu.cache_clear()
    lp = tai_lop_phu()
    tai_lop_phu.cache_clear()
    assert lp is not None and len(lp.canh) == 178
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lop_phu.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.knowledge.lop_phu'`

- [ ] **Step 3: Thêm cạnh chủ vào `KetQuaTuyen`**

Trong `app/ontology/dinh_tuyen.py`, sửa lớp:

```python
class KetQuaTuyen(BaseModel):
    """Kết quả định tuyến một chunk: nhánh đọc + khoá gốc/khoá đích + trích dẫn cho người đọc."""

    nhanh: Literal["nguyen_ven", "nen_da_sua", "trich_trong_van_ban_sua"]
    khoa_goc: str
    khoa_dich: str | None
    trich_dan_dung_chu: str
    #: Cạnh đã QUYẾT ĐỊNH nhánh này (None ở nhánh nguyên vẹn). Người gọi cần biết chính xác
    #: cạnh nào để tra lời văn mới mà không phải mô phỏng lại luật chọn cạnh ở đây.
    canh: CanhTacDong | None = None
```

Rồi điền `canh=` ở cả bốn chỗ `return KetQuaTuyen(...)`:
- nhánh 3 → `canh=c`
- nhánh 2 rộng-hơn-hoặc-bằng → `canh=c`
- nhánh 2 sâu-hơn → `canh=sau_hon`
- nhánh 1 → để mặc định (không truyền)

- [ ] **Step 4: Viết `app/knowledge/lop_phu.py`**

```python
"""Cổng DUY NHẤT giữa sản phẩm và lớp phủ dưới-văn-bản.

`answer.py`/`review.py`/`api` không gọi thẳng `dinh_tuyen`/`phien_ban_hien_hanh`: đường nóng
cần đúng một chỗ để đọc, để tắt bằng cờ, và để hỏng một cách vô hại. Mọi lỗi ở đây (artefact
thiếu, JSON hỏng, văn bản lạ) đều trả `None` — lớp phủ làm câu trả lời ĐÚNG HƠN, nó không
phải điều kiện để có câu trả lời.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from app.ingestion.vbpl_corpus import doc_id_theo_corpus
from app.ontology.dinh_tuyen import dinh_tuyen, khoa_tu_chunk_id
from app.ontology.dong_goi import CanhGoi, GoiLopPhu
from app.ontology.hien_hanh import phien_ban_hien_hanh
from app.ontology.tac_dong import CanhTacDong
from app.ontology.tac_dong import _DICH_RE as _KHOA_RE  # cùng cách dinh_tuyen.py đã mượn

DUONG_DAN_MAC_DINH = "data/overlay/lop_phu.json"


class ChuThichHieuLuc(BaseModel):
    """Đơn vị luật của một chunk, đọc tại `as_of`, thì sao."""

    nhanh: str
    trang_thai: Literal["nguyen_ven", "da_sua", "bi_bai_bo", "la_loi_sua"]
    trich_dan_dung_chu: str
    khoa_goc: str
    khoa_dich: str | None = None
    sua_boi_doc_id: str | None = None
    sua_boi_article: str | None = None
    #: Lời văn mới NGUYÊN VĂN — chỉ điền khi sửa đổi thay TRỌN đơn vị của chunk.
    ban_hien_hanh: str | None = None
    xuat_xu_doc_id: str | None = None
    xuat_xu_article: str | None = None


@dataclass
class LopPhuRuntime:
    canh: list[CanhTacDong]
    goi_theo_canh: dict[tuple, CanhGoi]
    so_hieu_theo_doc: dict[str, str]


def _khoa_canh(c: CanhTacDong | CanhGoi) -> tuple:
    return (c.nguon, c.dich, c.thao_tac, c.valid_from, c.loi_van_moi)


@lru_cache(maxsize=4)
def tai_lop_phu(duong_dan: str = DUONG_DAN_MAC_DINH) -> LopPhuRuntime | None:
    """Nạp artefact một lần. Hỏng/thiếu ⇒ None (fail-open), không ném lỗi."""
    try:
        goi = GoiLopPhu.model_validate_json(Path(duong_dan).read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    # Chuyển MỘT LẦN rồi dùng lại đúng danh sách đó: `dinh_tuyen` kiểm `c in pb.cac_lan`
    # bằng so sánh giá trị pydantic — chuyển lại lần hai vẫn đúng, nhưng chuyển mỗi lượt hỏi
    # là phí và dễ lệch nếu sau này thêm trường không so được.
    canh = [c.thanh_canh() for c in goi.canh]
    return LopPhuRuntime(
        canh=canh,
        goi_theo_canh={_khoa_canh(c): c for c in goi.canh},
        so_hieu_theo_doc=goi.so_hieu_theo_doc,
    )


def tach_khoa(khoa: str) -> tuple[str | None, str | None]:
    """Khoá overlay → (`doc_id`, nhãn kiểu `"Điều 1 Khoản 2"`). Không giải được ⇒ (None, None)."""
    m = _KHOA_RE.match(khoa)
    if not m:
        return None, None
    nhan = f"Điều {m.group('dieu')}"
    if m.group("khoan"):
        nhan += f" Khoản {m.group('khoan')}"
    if m.group("diem"):
        nhan += f" Điểm {m.group('diem')}"
    return doc_id_theo_corpus(m.group("sh")), nhan


def _span_loi_van(chunk: dict, lp: LopPhuRuntime) -> tuple[int, int] | None:
    """Chunk này CÓ PHẢI là khối lời văn mới của một cạnh không — so bằng CHỮ.

    `dinh_tuyen` nhận `span_chunk` (toạ độ trong `noi_dung`), nhưng hàng LanceDB không mang
    toạ độ ký tự, và thêm toạ độ vào chunk nghĩa là đổi ingest + re-embed toàn bộ. Chữ đã đủ:
    nếu lời văn mới nằm trong chunk (hoặc ngược lại, khi chunk bị chẻ nhỏ hơn khối trích) thì
    chunk chính là khối đó. Trả span CỦA CHÍNH CẠNH ĐÓ để `dinh_tuyen` tự giao và giữ trọn
    luật trích dẫn (cổng cạnh-chết) bên trong nó.
    """
    doc_id = (chunk.get("id") or "").partition("::")[0]
    so_hieu = lp.so_hieu_theo_doc.get(doc_id)
    text = chunk.get("text") or ""
    if so_hieu is None or not text:
        return None
    for c in lp.canh:
        if c.loi_van_moi is None or c.nguon.split("#", 1)[0] != so_hieu:
            continue
        g = lp.goi_theo_canh.get(_khoa_canh(c))
        lv = g.loi_van_moi_text if g else None
        if lv and (lv in text or text in lv):
            return c.loi_van_moi
    return None


def chu_thich_chunk(
    chunk: dict, as_of: str, lp: LopPhuRuntime | None = None
) -> ChuThichHieuLuc | None:
    lp = lp if lp is not None else tai_lop_phu()
    if lp is None:
        return None
    chunk_id = chunk.get("id") or ""
    if khoa_tu_chunk_id(chunk_id, lp.so_hieu_theo_doc) is None:
        return None
    kq = dinh_tuyen(chunk_id, _span_loi_van(chunk, lp), lp.canh, lp.so_hieu_theo_doc, as_of)
    if kq is None:
        return None

    if kq.nhanh == "trich_trong_van_ban_sua":
        trang_thai: Literal["nguyen_ven", "da_sua", "bi_bai_bo", "la_loi_sua"] = "la_loi_sua"
    elif kq.nhanh == "nguyen_ven":
        trang_thai = "nguyen_ven"
    else:
        # Nhánh 2 có hai đường: rộng-hơn-hoặc-bằng (đọc được trạng thái thẳng từ
        # `phien_ban_hien_hanh`) và sâu-hơn (cạnh sửa một điểm BÊN TRONG khoản — khoản chưa bị
        # bãi bỏ, nên trạng thái là `da_sua` dù cạnh đó là `bai_bo` cấp điểm).
        pb = phien_ban_hien_hanh(kq.khoa_goc, lp.canh, as_of)
        trang_thai = pb.trang_thai if pb.trang_thai != "nguyen_ven" else "da_sua"

    sua_boi_doc = sua_boi_art = ban_hien_hanh = xx_doc = xx_art = None
    if kq.canh is not None:
        sua_boi_doc, sua_boi_art = tach_khoa(kq.canh.nguon)
        g = lp.goi_theo_canh.get(_khoa_canh(kq.canh))
        if g is not None:
            xx_doc, xx_art = g.xuat_xu_doc_id, g.xuat_xu_article
            # Chỉ khi sửa đổi thay TRỌN đơn vị của chunk mới được coi lời văn mới là "bản hiện
            # hành" của nó. Cạnh sâu hơn (sửa một điểm bên trong) hay `bo_sung`/`thay_cum_tu`
            # thì lời văn mới KHÔNG phải toàn bộ đơn vị — dán vào là bịa.
            if (
                kq.nhanh == "nen_da_sua"
                and kq.canh.thao_tac == "sua_doi"
                and kq.canh.dich == kq.khoa_goc
            ):
                ban_hien_hanh = g.loi_van_moi_text

    return ChuThichHieuLuc(
        nhanh=kq.nhanh,
        trang_thai=trang_thai,
        trich_dan_dung_chu=kq.trich_dan_dung_chu,
        khoa_goc=kq.khoa_goc,
        khoa_dich=kq.khoa_dich,
        sua_boi_doc_id=sua_boi_doc,
        sua_boi_article=sua_boi_art,
        ban_hien_hanh=ban_hien_hanh,
        xuat_xu_doc_id=xx_doc,
        xuat_xu_article=xx_art,
    )
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_lop_phu.py tests/test_dinh_tuyen.py -q`
Expected: PASS — 9 + 8 passed (test_dinh_tuyen cũ không được đỏ)

- [ ] **Step 6: Run full suite + lint**

Run: `uv run pytest -q ; uv run ruff check .`
Expected: 570 passed, ruff sạch

- [ ] **Step 7: Commit**

```bash
git add app/knowledge/lop_phu.py tests/test_lop_phu.py app/ontology/dinh_tuyen.py
git commit -F - <<'EOF'
feat(overlay): runtime gate annotating retrieval hits with clause status

Detect quote-in-amender chunks by text containment since LanceDB rows
carry no char offsets. Fail-open on a missing or broken artefact.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

### Task 3: Chú thích cả danh sách hit + tra chunk theo id

**Files:**
- Modify: `app/knowledge/lop_phu.py` (thêm `chu_thich_ket_qua`)
- Modify: `app/knowledge/retrieval.py` (thêm `lay_chunk_theo_id`)
- Test: `tests/test_lop_phu.py` (thêm ca)

**Interfaces:**
- Consumes: `chu_thich_chunk` (Task 2)
- Produces:
  - `chu_thich_ket_qua(chunks: list[dict], as_of: str, lp=None) -> tuple[list[dict], dict[str, ChuThichHieuLuc]]` — trả (danh sách đã lọc/mở rộng, map `chunk id` → chú thích)
  - `retrieval.lay_chunk_theo_id(ids: list[str]) -> list[dict]`

- [ ] **Step 1: Write the failing test**

Thêm vào `tests/test_lop_phu.py`:

```python
from app.knowledge.lop_phu import chu_thich_ket_qua


def test_loai_hit_bi_bai_bo_nhung_giu_hit_con_lai(lp):
    chunks = [_chunk("TT40-2024::Điều 9"), _chunk("TT40-2024::Điều 3")]
    con, ct = chu_thich_ket_qua(chunks, "2026-08-06", lp)
    assert [c["id"] for c in con] == ["TT40-2024::Điều 3"]
    assert ct["TT40-2024::Điều 9"].trang_thai == "bi_bai_bo"  # vẫn chú thích, chỉ không dùng


def test_loai_het_thi_giu_lai_kem_nhan(lp):
    """Hỏi đúng một điều đã bị bãi bỏ: phải nghe 'đã bị bãi bỏ', không phải 'chưa tìm thấy'."""
    con, ct = chu_thich_ket_qua([_chunk("TT40-2024::Điều 9")], "2026-08-06", lp)
    assert [c["id"] for c in con] == ["TT40-2024::Điều 9"]
    assert ct["TT40-2024::Điều 9"].trang_thai == "bi_bai_bo"


def test_khong_co_lop_phu_thi_tra_nguyen_danh_sach():
    chunks = [_chunk("TT40-2024::Điều 9")]
    con, ct = chu_thich_ket_qua(chunks, "2026-08-06", None)
    assert con == chunks and ct == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_lop_phu.py -q -k chu_thich_ket_qua or loai_hit or loai_het`
Expected: FAIL — `ImportError: cannot import name 'chu_thich_ket_qua'`

- [ ] **Step 3: Thêm `lay_chunk_theo_id` vào `app/knowledge/retrieval.py`**

```python
def lay_chunk_theo_id(ids: list[str]) -> list[dict]:
    """Tra chunk theo id — không tìm kiếm, không embedding.

    Lớp phủ cần kéo đúng chunk mang lời văn mới về; đi qua `hybrid_search` là tốn một lượt
    embedding cho một thứ ta đã biết chính xác địa chỉ. Lỗi (bảng chưa có, cú pháp filter của
    LanceDB Cloud khác) ⇒ trả rỗng: đây là phần THÊM cho câu trả lời, không được làm hỏng nó.
    """
    if not ids:
        return []
    trong = ", ".join("'" + i.replace("'", "''") + "'" for i in ids)
    try:
        return _open_table().search().where(f"id IN ({trong})").limit(len(ids)).to_list()
    except Exception:  # noqa: BLE001 — xem docstring
        return []
```

- [ ] **Step 4: Thêm `chu_thich_ket_qua` vào `app/knowledge/lop_phu.py`**

```python
def chu_thich_ket_qua(
    chunks: list[dict], as_of: str, lp: LopPhuRuntime | None = None
) -> tuple[list[dict], dict[str, ChuThichHieuLuc]]:
    """Chú thích cả mẻ hit: loại cái đã bị bãi bỏ, kéo thêm lời văn mới khi cần.

    Trả `(danh sách dùng để trả lời, map id → chú thích)`. Map giữ CẢ hit đã bị loại — tầng
    trên vẫn cần chữ để nói "điều này đã bị bãi bỏ".
    """
    lp = lp if lp is not None else tai_lop_phu()
    if lp is None:
        return chunks, {}

    ct: dict[str, ChuThichHieuLuc] = {}
    for c in chunks:
        t = chu_thich_chunk(c, as_of, lp)
        if t is not None:
            ct[c["id"]] = t

    con = [c for c in chunks if (t := ct.get(c["id"])) is None or t.trang_thai != "bi_bai_bo"]
    if not con:
        # Loại hết: người hỏi đang hỏi đúng một điều đã bị bãi bỏ. Trả lại kèm nhãn còn thật
        # hơn là "chưa tìm thấy quy định phù hợp".
        con = list(chunks)

    # Kéo lời văn mới về cho hit đã sửa mà KHÔNG có sẵn bản hiện hành (bổ sung, thay cụm từ…).
    co_san = {c["id"] for c in con}
    can_them = sorted(
        {
            f"{t.xuat_xu_doc_id}::{t.xuat_xu_article}"
            for t in ct.values()
            if t.trang_thai == "da_sua"
            and t.ban_hien_hanh is None
            and t.xuat_xu_doc_id
            and t.xuat_xu_article
        }
        - co_san
    )
    if can_them:
        from app.knowledge.retrieval import lay_chunk_theo_id

        con = con + [c for c in lay_chunk_theo_id(can_them) if c["id"] not in co_san]
    return con, ct
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_lop_phu.py -q`
Expected: PASS — 12 passed

- [ ] **Step 6: Run full suite + lint, then commit**

Run: `uv run pytest -q ; uv run ruff check .`

```bash
git add app/knowledge/lop_phu.py app/knowledge/retrieval.py tests/test_lop_phu.py
git commit -F - <<'EOF'
feat(overlay): annotate a whole hit list and fetch chunks by id

Drop repealed hits unless that would empty the list, and pull the
amending article only when no current text is packaged.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

### Task 4: Nối vào đường trả lời chat

**Files:**
- Modify: `app/reasoning/answer.py`
- Modify: `app/core/config.py` (thêm cờ `overlay_router`)
- Modify: `app/core/schemas.py` (thêm trường optional vào `Citation`)
- Test: `tests/test_answer_lop_phu.py`

**Interfaces:**
- Consumes: `chu_thich_ket_qua` (Task 3), `ChuThichHieuLuc` (Task 2)
- Produces: `Citation` có thêm `trang_thai: str | None`, `chu_thich: str | None`, `sua_boi_doc_id: str | None`, `sua_boi_article: str | None`, `ban_hien_hanh: str | None`; `settings.overlay_router: bool`

- [ ] **Step 1: Write the failing test**

Tạo `tests/test_answer_lop_phu.py`:

```python
"""Đường trả lời có lớp phủ: nhãn vào prompt, trạng thái vào citation."""
from unittest.mock import patch

from app.core.schemas import ChatRequest
from app.knowledge.lop_phu import ChuThichHieuLuc
from app.reasoning.answer import _citations, _prepare

_CHUNKS = [
    {
        "id": "TT40-2024::Điều 8 Khoản 7",
        "doc_id": "TT40-2024",
        "doc_title": "Thông tư 40/2024",
        "doc_type": "thong_tu",
        "article": "Điều 8 Khoản 7",
        "text": "Hạn mức cũ.",
        "valid_from": "2024-07-01",
        "valid_to": "",
        "superseded": False,
    }
]
_CT = {
    "TT40-2024::Điều 8 Khoản 7": ChuThichHieuLuc(
        nhanh="nen_da_sua",
        trang_thai="da_sua",
        trich_dan_dung_chu="TT40-2024 Điều 8 Khoản 7 (đã sửa bởi TT41-2025 Điều 1 Khoản 2)",
        khoa_goc="40/2024/TT-NHNN#than/dieu_8#khoan_7",
        khoa_dich="40/2024/TT-NHNN#than/dieu_8#khoan_7",
        sua_boi_doc_id="TT41-2025",
        sua_boi_article="Điều 1 Khoản 2",
        ban_hien_hanh='"7. Hạn mức mới là 200 triệu đồng."',
    )
}


def test_prompt_mang_nhan_va_ban_hien_hanh():
    with (
        patch("app.reasoning.answer.hybrid_search", return_value=_CHUNKS),
        patch("app.reasoning.answer.chu_thich_ket_qua", return_value=(_CHUNKS, _CT)),
        patch("app.core.config.settings.graph_augment", False),
    ):
        chunks, ct, system, prompt = _prepare(ChatRequest(query="hạn mức?"))
    assert "đã sửa bởi TT41-2025 Điều 1 Khoản 2" in prompt
    assert "Bản hiện hành" in prompt and "200 triệu" in prompt
    assert ct == _CT


def test_citation_mang_trang_thai():
    cits = _citations(_CHUNKS, _CT)
    assert cits[0].trang_thai == "da_sua"
    assert cits[0].sua_boi_doc_id == "TT41-2025"
    assert "200 triệu" in cits[0].ban_hien_hanh


def test_citation_khong_co_chu_thich_van_hop_le():
    cits = _citations(_CHUNKS, {})
    assert cits[0].trang_thai is None and cits[0].ban_hien_hanh is None


def test_co_tat_thi_khong_goi_lop_phu():
    with (
        patch("app.reasoning.answer.hybrid_search", return_value=_CHUNKS),
        patch("app.core.config.settings.graph_augment", False),
        patch("app.core.config.settings.overlay_router", False),
        patch("app.reasoning.answer.chu_thich_ket_qua") as gia,
    ):
        _chunks, ct, _system, _prompt = _prepare(ChatRequest(query="hạn mức?"))
    gia.assert_not_called()
    assert ct == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_answer_lop_phu.py -q`
Expected: FAIL — `ImportError: cannot import name 'chu_thich_ket_qua' from 'app.reasoning.answer'` (chưa import) và `_prepare` trả 3 phần tử

- [ ] **Step 3: Thêm cờ vào `app/core/config.py`**

Ngay dưới dòng `graph_augment: bool = True`:

```python
    # Lớp phủ dưới-văn-bản: chú thích hiệu lực cấp khoản sau retrieval
    overlay_router: bool = True
```

- [ ] **Step 4: Thêm trường vào `Citation` trong `app/core/schemas.py`**

```python
class Citation(BaseModel):
    doc_id: str
    doc_title: str
    doc_type: str
    article: str
    valid_from: str | None = None
    valid_to: str | None = None
    snippet: str
    # --- Lớp phủ dưới-văn-bản (optional: FE cũ và corpus chưa chú thích vẫn hợp lệ) ---
    #: nguyen_ven | da_sua | bi_bai_bo | la_loi_sua
    trang_thai: str | None = None
    #: Trích dẫn đúng chủ, vd "TT40-2024 Điều 8 Khoản 7 (đã sửa bởi TT41-2025 Điều 1 Khoản 2)"
    chu_thich: str | None = None
    sua_boi_doc_id: str | None = None
    sua_boi_article: str | None = None
    ban_hien_hanh: str | None = None
```

- [ ] **Step 5: Sửa `app/reasoning/answer.py`**

Thêm import:

```python
from app.knowledge.lop_phu import ChuThichHieuLuc, chu_thich_ket_qua
```

Đổi `_format_context`, `_prepare`, `_citations` (chữ ký `_prepare` giờ trả 4 phần tử):

```python
def _format_context(chunks: list[dict], ct: dict[str, ChuThichHieuLuc]) -> str:
    khoi = []
    for c in chunks:
        t = ct.get(c["id"])
        dau = f"[{c['doc_title']} — {c['article']}] (hiệu lực từ {c['valid_from'] or 'N/A'})"
        if t is not None and t.trang_thai != "nguyen_ven":
            dau += f" — {t.trich_dan_dung_chu}"
        than = c["text"]
        if t is not None and t.ban_hien_hanh:
            xx = f"{t.sua_boi_doc_id} {t.sua_boi_article}".strip()
            than += f"\n\nBản hiện hành (theo {xx}):\n{t.ban_hien_hanh}"
        khoi.append(f"{dau}\n{than}")
    return "\n\n".join(khoi)
```

```python
def _prepare(req: ChatRequest) -> tuple[list[dict], dict[str, ChuThichHieuLuc], str, str]:
    """Retrieval (+ graph, + lớp phủ) + dựng prompt. Trả (chunks, chú thích, system, prompt)."""
    as_of = req.as_of or today_iso()
    edges: list[dict] = []
    if req.doc_ids:
        chunks = search_in_docs(
            req.query, req.doc_ids, top_k=req.top_k, as_of=as_of, effective_only=True
        )
    elif settings.graph_augment and settings.neo4j_enabled:
        chunks, edges = graph_augmented_search(
            req.query, top_k=req.top_k, as_of=as_of, effective_only=True
        )
    else:
        chunks = hybrid_search(req.query, top_k=req.top_k, as_of=as_of, effective_only=True)

    ct: dict[str, ChuThichHieuLuc] = {}
    if settings.overlay_router:
        chunks, ct = chu_thich_ket_qua(chunks, as_of)

    system = _CHECKLIST_SYSTEM if req.mode == "checklist" else _QA_SYSTEM
    prompt = (
        f"Câu hỏi/luồng nghiệp vụ: {req.query}\n\n"
        f"Các điều khoản đang hiệu lực (tại {as_of}):\n{_format_context(chunks, ct)}"
    )
    if edges:
        rel_lines = "\n".join(
            f"- {e['src']} {nhan_quan_he(e['rel_type'])} {e['tgt']}"
            + (f" ({e['note']})" if e.get("note") else "")
            for e in edges
        )
        prompt += f"\n\nQuan hệ giữa các văn bản (theo knowledge graph):\n{rel_lines}"
    return chunks, ct, system, prompt
```

```python
def _citations(chunks: list[dict], ct: dict[str, ChuThichHieuLuc]) -> list[Citation]:
    ra = []
    for c in chunks:
        t = ct.get(c["id"])
        ra.append(
            Citation(
                doc_id=c["doc_id"], doc_title=c["doc_title"], doc_type=c["doc_type"],
                article=c["article"], valid_from=c["valid_from"] or None,
                valid_to=c["valid_to"] or None, snippet=c["text"][:280],
                trang_thai=t.trang_thai if t else None,
                chu_thich=t.trich_dan_dung_chu if t else None,
                sua_boi_doc_id=t.sua_boi_doc_id if t else None,
                sua_boi_article=t.sua_boi_article if t else None,
                ban_hien_hanh=t.ban_hien_hanh if t else None,
            )
        )
    return ra
```

Thêm một câu vào `_QA_SYSTEM` (giữ nguyên phần còn lại):

```python
_QA_SYSTEM = (
    "Bạn là trợ lý pháp lý ngân hàng. Trả lời câu hỏi CHỈ dựa trên các điều khoản "
    "được cung cấp (đang hiệu lực). Luôn trích dẫn văn bản + điều/khoản trong ngoặc "
    "vuông, ví dụ [Thông tư 40/2024 — Điều 12 Khoản 1]. Nếu một căn cứ được ghi chú là đã "
    "bị sửa đổi hoặc bãi bỏ, phải nói rõ điều đó và ưu tiên phần 'Bản hiện hành' nếu có — "
    "không trình bày lời văn cũ như đang có hiệu lực. Nếu không đủ căn cứ, nói rõ "
    "là chưa tìm thấy quy định phù hợp. Trả lời bằng tiếng Việt, ngắn gọn, chính xác."
)
```

Cập nhật hai chỗ gọi:

```python
@observe(name="answer.build")
def build_answer(req: ChatRequest) -> ChatResponse:
    chunks, ct, system, prompt = _prepare(req)
    if not chunks:
        return ChatResponse(answer=_NOT_FOUND, citations=[], conflicts=[])
    answer = chat(prompt, system=system)
    return ChatResponse(
        answer=answer, citations=_citations(chunks, ct), conflicts=detect_conflicts(chunks)
    )
```

và trong `stream_answer`: `chunks, ct, system, prompt = _prepare(req)` +
`yield "meta", {"citations": [c.model_dump() for c in _citations(chunks, ct)]}`.

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_answer_lop_phu.py tests/test_stream.py tests/test_core.py -q`
Expected: PASS

- [ ] **Step 7: Run full suite + lint, then commit**

Run: `uv run pytest -q ; uv run ruff check .`

```bash
git add app/reasoning/answer.py app/core/config.py app/core/schemas.py tests/test_answer_lop_phu.py
git commit -F - <<'EOF'
feat(chat): label retrieval hits with clause-level effect in the prompt

Citations now carry status, attribution and the current wording when the
amendment replaces a whole clause. Gated by settings.overlay_router.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

### Task 5: Nối vào màn Kiểm tra tuân thủ

**Files:**
- Modify: `app/reasoning/review.py`
- Test: `tests/test_review_lop_phu.py`

**Interfaces:**
- Consumes: `chu_thich_ket_qua` (Task 3)
- Produces: không có API mới — `_review_article` dùng chunk đã lọc; `ReviewFinding.legal_live` phản ánh cả trạng thái cấp khoản

- [ ] **Step 1: Write the failing test**

Tạo `tests/test_review_lop_phu.py`:

```python
"""Đối chiếu tuân thủ không được lấy điều luật đã bị bãi bỏ ở cấp khoản làm căn cứ."""
from unittest.mock import patch

from app.knowledge.lop_phu import ChuThichHieuLuc
from app.reasoning.review import _review_article

_SONG = {
    "id": "TT40-2024::Điều 3", "doc_id": "TT40-2024", "doc_title": "Thông tư 40/2024",
    "doc_type": "thong_tu", "article": "Điều 3", "text": "Quy định còn hiệu lực.",
    "valid_from": "2024-07-01", "valid_to": "", "superseded": False,
}
_CHET = {**_SONG, "id": "TT40-2024::Điều 9", "article": "Điều 9", "text": "Quy định đã bỏ."}
_CT = {
    "TT40-2024::Điều 9": ChuThichHieuLuc(
        nhanh="nen_da_sua", trang_thai="bi_bai_bo",
        trich_dan_dung_chu="TT40-2024 Điều 9 (đã bị bãi bỏ bởi TT41-2025 Điều 2)",
        khoa_goc="40/2024/TT-NHNN#than/dieu_9",
        khoa_dich="40/2024/TT-NHNN#than/dieu_9",
        sua_boi_doc_id="TT41-2025", sua_boi_article="Điều 2",
    )
}


def test_can_cu_bi_bai_bo_bi_loai_khoi_doi_chieu():
    ghi = {}

    def _gia_judge(prompt: str) -> dict:
        ghi["prompt"] = prompt
        return {"verdict": "pass", "legal_chunk_id": "TT40-2024::Điều 3", "title": "ok",
                "summary": "", "internal_quote": "", "legal_quote": "", "suggestion": None}

    with (
        patch("app.reasoning.review.search_in_docs", return_value=[_CHET, _SONG]),
        patch("app.reasoning.review.chu_thich_ket_qua", return_value=([_SONG], _CT)),
        patch("app.reasoning.review._judge", side_effect=_gia_judge),
    ):
        f = _review_article("Điều 1", "nội dung nội bộ", ["TT40-2024"], "2026-08-06")

    assert "TT40-2024::Điều 9" not in ghi["prompt"]  # căn cứ chết không vào prompt
    assert f.legal_doc_id == "TT40-2024" and "Điều 3" in (f.legal_ref or "")


def test_can_cu_da_sua_thi_legal_live_van_dung_nhung_co_ghi_chu():
    ct = {
        "TT40-2024::Điều 3": ChuThichHieuLuc(
            nhanh="nen_da_sua", trang_thai="da_sua",
            trich_dan_dung_chu="TT40-2024 Điều 3 (đã sửa bởi TT41-2025 Điều 1)",
            khoa_goc="40/2024/TT-NHNN#than/dieu_3", khoa_dich="40/2024/TT-NHNN#than/dieu_3",
            sua_boi_doc_id="TT41-2025", sua_boi_article="Điều 1",
        )
    }
    with (
        patch("app.reasoning.review.search_in_docs", return_value=[_SONG]),
        patch("app.reasoning.review.chu_thich_ket_qua", return_value=([_SONG], ct)),
        patch("app.reasoning.review._judge", return_value={
            "verdict": "pass", "legal_chunk_id": "TT40-2024::Điều 3", "title": "ok",
            "summary": "", "internal_quote": "", "legal_quote": "", "suggestion": None}),
    ):
        f = _review_article("Điều 1", "nội dung nội bộ", ["TT40-2024"], "2026-08-06")
    assert f.legal_live is True
    assert "đã sửa bởi TT41-2025" in (f.legal_ref or "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_review_lop_phu.py -q`
Expected: FAIL — `AttributeError: <module 'app.reasoning.review'> does not have the attribute 'chu_thich_ket_qua'`

- [ ] **Step 3: Sửa `app/reasoning/review.py`**

Thêm import cạnh `from app.knowledge.retrieval import search_in_docs`:

```python
from app.core.config import settings
from app.knowledge.lop_phu import chu_thich_ket_qua
```

Trong `_review_article`, ngay sau lời gọi `search_in_docs` (trước kiểm `if not chunks`):

```python
    ct = {}
    if settings.overlay_router:
        # Không đối chiếu quy định nội bộ với điều luật đã bị bãi bỏ ở cấp khoản — kết luận
        # "vi phạm" dựa trên một căn cứ đã chết là sai nguy hiểm hơn là không kết luận.
        chunks, ct = chu_thich_ket_qua(chunks, as_of)
```

Ở cuối hàm, gắn ghi chú vào `legal_ref`:

```python
    t = ct.get(legal["id"])
    legal_ref = f"{legal['doc_title']} — {legal['article']}"
    if t is not None and t.trang_thai not in (None, "nguyen_ven"):
        legal_ref += f" ({t.trich_dan_dung_chu})"
    return ReviewFinding(
        ...
        legal_ref=legal_ref,
        legal_live=not legal.get("valid_to") and (t is None or t.trang_thai != "bi_bai_bo"),
        ...
    )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_review_lop_phu.py tests/test_reviews.py -q`
Expected: PASS

- [ ] **Step 5: Run full suite + lint, then commit**

```bash
git add app/reasoning/review.py tests/test_review_lop_phu.py
git commit -F - <<'EOF'
fix(review): never cite a repealed clause as compliance grounds

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

### Task 6: Trình xem toàn văn biết khoản nào bị chạm

**Files:**
- Modify: `app/api/documents.py`
- Modify: `app/core/schemas.py` (`DocumentDetail` + `TacDongDonVi`)
- Test: `tests/test_documents_tac_dong.py`

**Interfaces:**
- Consumes: `tai_lop_phu`, `phien_ban_hien_hanh`, `tach_khoa` (Task 2)
- Produces:
  - `class TacDongDonVi(BaseModel)` — `article: str`, `khoan: str | None`, `diem: str | None`, `trang_thai: str`, `boi_doc_id: str | None`, `boi_article: str | None`, `tu_ngay: str | None`
  - `DocumentDetail.tac_dong: list[TacDongDonVi] = []`
  - `app.knowledge.lop_phu.tac_dong_cua_van_ban(doc_id: str, as_of: str, lp=None) -> list[TacDongDonVi]`

- [ ] **Step 1: Write the failing test**

Tạo `tests/test_documents_tac_dong.py`:

```python
"""Trình xem toàn văn: đánh dấu ở MỨC KHOẢN, không chỉ mức điều."""
from app.knowledge.lop_phu import tac_dong_cua_van_ban

from tests.test_lop_phu import _goi  # tái dùng gói mẫu


def test_liet_ke_don_vi_bi_cham(tmp_path):
    from app.knowledge.lop_phu import tai_lop_phu

    p = tmp_path / "lop_phu.json"
    p.write_text(_goi().model_dump_json(), encoding="utf-8")
    tai_lop_phu.cache_clear()
    lp = tai_lop_phu(str(p))
    ra = tac_dong_cua_van_ban("TT40-2024", "2026-08-06", lp)
    tai_lop_phu.cache_clear()

    theo_nhan = {(t.article, t.khoan): t for t in ra}
    assert theo_nhan[("Điều 8", "7")].trang_thai == "da_sua"
    assert theo_nhan[("Điều 8", "7")].boi_doc_id == "TT41-2025"
    assert theo_nhan[("Điều 9", None)].trang_thai == "bi_bai_bo"


def test_van_ban_khong_bi_cham_tra_rong(tmp_path):
    from app.knowledge.lop_phu import tai_lop_phu

    p = tmp_path / "lop_phu.json"
    p.write_text(_goi().model_dump_json(), encoding="utf-8")
    tai_lop_phu.cache_clear()
    lp = tai_lop_phu(str(p))
    assert tac_dong_cua_van_ban("TT41-2025", "2026-08-06", lp) == []
    tai_lop_phu.cache_clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_documents_tac_dong.py -q`
Expected: FAIL — `ImportError: cannot import name 'tac_dong_cua_van_ban'`

- [ ] **Step 3: Thêm `TacDongDonVi` vào `app/core/schemas.py`**

```python
class TacDongDonVi(BaseModel):
    """Một đơn vị (điều/khoản/điểm) của văn bản đang bị một văn bản khác chạm tới."""

    article: str
    khoan: str | None = None
    diem: str | None = None
    #: da_sua | bi_bai_bo
    trang_thai: str
    boi_doc_id: str | None = None
    boi_article: str | None = None
    tu_ngay: str | None = None
```

và thêm vào `DocumentDetail`: `tac_dong: list[TacDongDonVi] = []`

- [ ] **Step 4: Thêm `tac_dong_cua_van_ban` vào `app/knowledge/lop_phu.py`**

```python
def tac_dong_cua_van_ban(
    doc_id: str, as_of: str, lp: LopPhuRuntime | None = None
) -> list["TacDongDonVi"]:
    """Mọi đơn vị của `doc_id` đang bị chạm tại `as_of` — cho trình xem toàn văn.

    Đi từ ĐÍCH của cạnh (đơn vị bị tác động) chứ không quét từng điều của văn bản: lớp phủ
    thưa, chỉ đơn vị "có chuyện để nói" mới có mặt, nên duyệt cạnh là đủ và rẻ.
    """
    from app.core.schemas import TacDongDonVi

    lp = lp if lp is not None else tai_lop_phu()
    if lp is None:
        return []
    ra: list[TacDongDonVi] = []
    for khoa in sorted({c.dich for c in lp.canh}):
        d_id, _nhan = tach_khoa(khoa)
        if d_id != doc_id:
            continue
        pb = phien_ban_hien_hanh(khoa, lp.canh, as_of)
        if pb.trang_thai == "nguyen_ven":
            continue
        m = _KHOA_RE.match(khoa)
        if m is None:
            continue
        c = pb.cac_lan[-1]
        boi_doc, boi_art = tach_khoa(c.nguon)
        ra.append(
            TacDongDonVi(
                article=f"Điều {m.group('dieu')}",
                khoan=m.group("khoan"),
                diem=m.group("diem"),
                trang_thai=pb.trang_thai,
                boi_doc_id=boi_doc,
                boi_article=boi_art,
                tu_ngay=c.valid_from,
            )
        )
    return ra
```

- [ ] **Step 5: Nối vào `app/api/documents.py`**

Trong `get_document_detail`, trước `return DocumentDetail(...)`:

```python
    tac_dong = []
    if settings.overlay_router:
        from app.ingestion.versioning import today_iso
        from app.knowledge.lop_phu import tac_dong_cua_van_ban

        tac_dong = tac_dong_cua_van_ban(doc_id, today_iso())
```

và thêm `tac_dong=tac_dong,` vào lời gọi `DocumentDetail(...)`. Thêm
`from app.core.config import settings` nếu chưa có.

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_documents_tac_dong.py tests/test_documents.py -q`
Expected: PASS

- [ ] **Step 7: Run full suite + lint, then commit**

```bash
git add app/api/documents.py app/core/schemas.py app/knowledge/lop_phu.py tests/test_documents_tac_dong.py
git commit -F - <<'EOF'
feat(documents): expose clause-level impacts for the full-text viewer

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

### Task 7: Web — badge trong chat, /review và trình xem

**Files:**
- Modify: `web/lib/api.ts` (kiểu `Citation`, `TacDongDonVi`, `DocumentDetail`)
- Modify: `web/app/(app)/page.tsx` (thẻ nguồn)
- Modify: `web/app/(app)/review/page.tsx` (căn cứ)
- Modify: `web/app/(app)/docs/[docId]/page.tsx` (đánh dấu mức khoản)

**Interfaces:**
- Consumes: trường mới của `Citation` (Task 4), `DocumentDetail.tac_dong` (Task 6)
- Produces: không có API mới

**Không có test tự động cho tầng này** (dự án chưa có bộ test FE). Nghiệm thu bằng
`npm run build` + kiểm bằng mắt trên `npm run dev`. Nếu bạn thấy đây là thiếu sót, **báo vào
report**, đừng tự dựng hạ tầng test FE trong task này.

- [ ] **Step 1: Mở rộng kiểu trong `web/lib/api.ts`**

```typescript
export type Citation = {
  doc_id: string;
  doc_title: string;
  doc_type: string;
  article: string;
  valid_from: string | null;
  valid_to: string | null;
  snippet: string;
  // Lớp phủ dưới-văn-bản (optional — backend cũ không trả)
  trang_thai?: "nguyen_ven" | "da_sua" | "bi_bai_bo" | "la_loi_sua" | null;
  chu_thich?: string | null;
  sua_boi_doc_id?: string | null;
  sua_boi_article?: string | null;
  ban_hien_hanh?: string | null;
};

export type TacDongDonVi = {
  article: string;
  khoan: string | null;
  diem: string | null;
  trang_thai: "da_sua" | "bi_bai_bo";
  boi_doc_id: string | null;
  boi_article: string | null;
  tu_ngay: string | null;
};
```

và thêm `tac_dong?: TacDongDonVi[];` vào `DocumentDetail`.

- [ ] **Step 2: Badge + bản hiện hành trong thẻ nguồn (`web/app/(app)/page.tsx`)**

Thêm component gần `StatusPill`:

```tsx
function OverlayPill({ c }: { c: Citation }) {
  if (!c.trang_thai || c.trang_thai === "nguyen_ven") return null;
  const nhan =
    c.trang_thai === "bi_bai_bo"
      ? "Đã bị bãi bỏ"
      : c.trang_thai === "la_loi_sua"
        ? "Lời văn sửa đổi"
        : "Đã bị sửa đổi";
  const mau = c.trang_thai === "bi_bai_bo" ? "border-red text-red" : "border-accent text-accent-dim";
  return (
    <span className={`rounded border px-2 py-0.5 text-[10px] ${mau}`} title={c.chu_thich ?? ""}>
      {nhan}
      {c.sua_boi_doc_id ? ` · ${c.sua_boi_doc_id} ${c.sua_boi_article ?? ""}` : ""}
    </span>
  );
}
```

Đặt `<OverlayPill c={c} />` ngay sau `<StatusPill live={!c.valid_to} />` trong thẻ nguồn, và
chèn khối bản hiện hành ngay dưới đoạn `<p className="serif …">“{c.snippet}…”</p>`:

```tsx
{c.ban_hien_hanh && (
  <details className="mt-2 rounded-[9px] border border-accent/40 bg-inset px-3 py-2">
    <summary className="cursor-pointer text-[11.5px] font-medium text-accent-hover">
      Bản hiện hành {c.sua_boi_doc_id ? `(theo ${c.sua_boi_doc_id} ${c.sua_boi_article ?? ""})` : ""}
    </summary>
    <p className="serif mt-2 text-sm leading-[1.6] text-fg-strong">{c.ban_hien_hanh}</p>
  </details>
)}
```

- [ ] **Step 3: Ghi chú căn cứ trong `/review`**

`legal_ref` đã mang sẵn ghi chú từ Task 5 nên không cần đổi cấu trúc; chỉ đảm bảo phần render
`legal_ref` không cắt chuỗi (bỏ `truncate`/`line-clamp-1` nếu có trên phần tử đó) và khi
`legal_live === false` thì hiện nhãn đỏ "Căn cứ không còn hiệu lực".

- [ ] **Step 4: Đánh dấu mức khoản trong `docs/[docId]/page.tsx`**

Trong `ContentTab`, thêm tính toán trước `return`:

```tsx
const theoDieu = new Map<string, TacDongDonVi[]>();
for (const t of doc.tac_dong ?? []) {
  const ds = theoDieu.get(t.article) ?? [];
  ds.push(t);
  theoDieu.set(t.article, ds);
}
```

Trong thân mỗi `<section>`, sau hàng badge hiện có:

```tsx
{(theoDieu.get(a.article) ?? []).length > 0 && (
  <ul className="mt-2 space-y-1">
    {(theoDieu.get(a.article) ?? []).map((t, i) => (
      <li key={i} className="text-[11.5px] text-dim">
        <span className={t.trang_thai === "bi_bai_bo" ? "text-red" : "text-accent-dim"}>
          {t.khoan ? `Khoản ${t.khoan}` : "Cả điều"}
          {t.diem ? ` Điểm ${t.diem}` : ""} —{" "}
          {t.trang_thai === "bi_bai_bo" ? "đã bị bãi bỏ" : "đã bị sửa đổi"}
        </span>
        {t.boi_doc_id ? ` bởi ${t.boi_doc_id} ${t.boi_article ?? ""}` : ""}
        {t.tu_ngay ? ` (từ ${t.tu_ngay})` : ""}
      </li>
    ))}
  </ul>
)}
```

- [ ] **Step 5: Build**

Run: `cd web ; npm run build`
Expected: build thành công, không lỗi type

- [ ] **Step 6: Commit**

```bash
git add "web/lib/api.ts" "web/app/(app)/page.tsx" "web/app/(app)/review/page.tsx" "web/app/(app)/docs/[docId]/page.tsx"
git commit -F - <<'EOF'
feat(web): show clause-level status on citations and the viewer

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

### Task 8: Đẩy lớp phủ lên Neo4j (chỉ để xem)

**Files:**
- Modify: `app/knowledge/graph.py`
- Test: `tests/test_push_overlay.py`

**Interfaces:**
- Consumes: `GoiLopPhu` (Task 1), `dung_overlay(canh) -> list[DonViOverlay]` (`app/ontology/hien_hanh.py`)
- Produces: `push_overlay(goi: GoiLopPhu) -> tuple[int, int]` — trả (số node, số cạnh) đã MERGE

- [ ] **Step 1: Write the failing test**

Tạo `tests/test_push_overlay.py`:

```python
"""Đẩy lớp phủ lên Neo4j: MERGE nên chạy hai lần không nhân đôi."""
from unittest.mock import MagicMock, patch

from app.knowledge.graph import push_overlay

from tests.test_lop_phu import _goi


def test_merge_node_va_canh():
    phien = MagicMock()
    with patch("app.knowledge.graph._session") as mo:
        mo.return_value.__enter__.return_value = phien
        n_node, n_canh = push_overlay(_goi())

    assert (n_node, n_canh) == (4, 2)  # 2 nguồn + 2 đích, 2 cạnh
    cypher = " ".join(str(c) for c in phien.run.call_args_list)
    assert "MERGE" in cypher and "CREATE (" not in cypher  # không CREATE trần → không nhân đôi
    assert ":DonVi" in cypher and ":TAC_DONG" in cypher
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_push_overlay.py -q`
Expected: FAIL — `ImportError: cannot import name 'push_overlay'`

- [ ] **Step 3: Đọc `app/knowledge/graph.py` để theo đúng khuôn `push_corpus`**

Run: `uv run python -c "import inspect, app.knowledge.graph as g; print(inspect.getsource(g.push_corpus))"`

Dùng đúng cách mở session/driver mà `push_corpus` đang dùng (tên helper có thể khác `_session`
— nếu khác, **sửa test cho khớp tên thật** rồi ghi vào report, đừng đổi khuôn của module).

- [ ] **Step 4: Viết `push_overlay`**

```python
def push_overlay(goi: "GoiLopPhu") -> tuple[int, int]:
    """Đẩy node/cạnh lớp phủ lên Neo4j — chỉ để XEM, không nằm trên đường trả lời.

    `MERGE` trên `khoa` nên chạy lại nhiều lần không nhân đôi. Cạnh `TAC_DONG` khoá theo bộ
    ba (nguồn, đích, thao_tac) — cùng một cặp đơn vị có thể vừa bị sửa vừa bị bãi bỏ ở hai
    thời điểm khác nhau, gộp chung thành một cạnh là mất thông tin.
    """
    from app.ontology.hien_hanh import dung_overlay

    canh = [c.thanh_canh() for c in goi.canh]
    nodes = dung_overlay(canh)
    with _session() as s:
        for n in nodes:
            s.run(
                "MERGE (d:DonVi {khoa: $khoa}) SET d.doc_id = $doc_id, d.vai = $vai",
                khoa=n.khoa, doc_id=n.doc_id, vai=n.vai,
            )
            if n.doc_id:
                s.run(
                    "MATCH (d:DonVi {khoa: $khoa}) MATCH (v:Document {doc_id: $doc_id}) "
                    "MERGE (d)-[:THUOC]->(v)",
                    khoa=n.khoa, doc_id=n.doc_id,
                )
        for c in canh:
            s.run(
                "MATCH (a:DonVi {khoa: $nguon}) MATCH (b:DonVi {khoa: $dich}) "
                "MERGE (a)-[r:TAC_DONG {thao_tac: $thao_tac}]->(b) "
                "SET r.valid_from = $valid_from",
                nguon=c.nguon, dich=c.dich, thao_tac=c.thao_tac, valid_from=c.valid_from,
            )
    return len(nodes), len(canh)
```

- [ ] **Step 5: Run tests + lint, then commit**

Run: `uv run pytest tests/test_push_overlay.py -q ; uv run pytest -q ; uv run ruff check .`

```bash
git add app/knowledge/graph.py tests/test_push_overlay.py
git commit -F - <<'EOF'
feat(graph): merge overlay units and impact edges into Neo4j

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

### Task 9: Nạp thật + deploy + verify prod — **CONTROLLER TỰ LÀM, KHÔNG GIAO SUBAGENT**

Task này ghi đè dữ liệu production và không hoàn tác được bằng `git revert`.

- [ ] **Step 1: Sao lưu corpus canonical đang có trên Storage**

```powershell
uv run python -c "from app.core import corpus as c; import json,pathlib; p=pathlib.Path('data/backup'); p.mkdir(exist_ok=True); d=c.get_corpus_cached(None); pathlib.Path('data/backup/corpus-truoc-p4.json').write_text(json.dumps(d,ensure_ascii=False,indent=1),encoding='utf-8'); print(len(d.get('documents',[])),'văn bản đã lưu')"
```

Không tải được (thiếu token) ⇒ **dừng, hỏi người dùng**, không ghi đè mù.

- [ ] **Step 2: Đối chiếu văn bản chỉ có ở bản cũ**

```powershell
uv run python -c "import json,pathlib; cu=json.loads(pathlib.Path('data/backup/corpus-truoc-p4.json').read_text(encoding='utf-8')); moi=json.loads(pathlib.Path('data/corpus.real.json').read_text(encoding='utf-8')); a={d['doc_id'] for d in cu.get('documents',[])}; b={d['doc_id'] for d in moi.get('documents',[])}; print('chỉ có ở bản cũ:', sorted(a-b)); print('chỉ có ở bản mới:', sorted(b-a))"
```

Có văn bản chỉ ở bản cũ ⇒ báo người dùng danh sách trước khi tiếp.

- [ ] **Step 3: Ingest corpus 26 văn bản**

```powershell
$env:PYTHONIOENCODING="utf-8"; uv run python -m app.ingestion data/corpus.real.json
```

Ghi lại số chunk in ra.

- [ ] **Step 4: Đẩy lớp phủ lên Neo4j**

```powershell
uv run python -c "import json,pathlib; from app.ontology.dong_goi import GoiLopPhu; from app.knowledge.graph import push_overlay; g=GoiLopPhu.model_validate_json(pathlib.Path('data/overlay/lop_phu.json').read_text(encoding='utf-8')); print(push_overlay(g))"
```

Aura đang pause (DNS không phân giải) ⇒ resume trên console rồi chạy lại.

- [ ] **Step 5: Deploy Cloud Run + Vercel**

Theo đúng quy trình đã dùng ở các đợt trước trong `docs/WORKLOG.md`.

- [ ] **Step 6: Verify prod**

- `/health` xanh
- Hỏi một khoản **đã bị bãi bỏ** → câu trả lời phải nói rõ đã bị bãi bỏ, không trình bày như đang hiệu lực
- Hỏi một khoản **đã bị sửa** → thẻ nguồn có badge + khối "Bản hiện hành"
- Mở `/docs/TT40-2024` → khoản bị sửa được đánh dấu

---

### Task 10: Đo delta ON/OFF + cập nhật tài liệu

**Files:**
- Modify: `eval/run_benchmark.py`
- Modify: `eval/overlay/cau_hoi_nhan.jsonl` (mở rộng lên ≥20 dòng)
- Modify: `docs/KG-CONFORMANCE-v05.md`, `docs/WORKLOG.md`

- [ ] **Step 1: Ghi DỰ ĐOÁN trước khi chạy**

Viết vào phần nháp của report: số hit bị loại vì bãi bỏ, số hit được nắn trích dẫn, và
stale-avoidance dự kiến so với 36/36 của 24/07. Ghi TRƯỚC khi chạy — chạy rồi mới ghi thì
không còn là dự đoán.

- [ ] **Step 2: Thêm cột router ON/OFF vào `eval/run_benchmark.py`**

Chạy mỗi câu hai lần: một lần `settings.overlay_router = True`, một lần `False`; ghi cả hai
vào `eval/results/<ngày>.json` cùng số câu mà hai cột khác nhau.

- [ ] **Step 3: Mở rộng bộ nhãn lên ≥20 dòng**

Thêm ca vào `eval/overlay/cau_hoi_nhan.jsonl`, phải có: ≥1 ca nhãn khoản-gộp, ≥1 ca cạnh chết
(TT41 Đ16), ≥1 ca `bo_sung` (không có bản hiện hành).

- [ ] **Step 4: Chạy và ghi số thật**

```powershell
$env:PYTHONIOENCODING="utf-8"; uv run python eval/run_benchmark.py
```

- [ ] **Step 5: Cập nhật tài liệu bằng số ĐÃ ĐO**

`docs/KG-CONFORMANCE-v05.md` (khối P4) và `docs/WORKLOG.md` (mục 06/08). Ghi cả chỗ dự đoán
sai so với dữ liệu, nếu có.

- [ ] **Step 6: Commit**

```bash
git add eval/run_benchmark.py eval/overlay/cau_hoi_nhan.jsonl docs/KG-CONFORMANCE-v05.md docs/WORKLOG.md eval/results
git commit -F - <<'EOF'
docs(overlay): measure router on/off delta and sync the conformance notes

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
EOF
```

---

## Self-Review

**Spec coverage** — mọi mục của spec có task tương ứng: artefact (T1) · cổng runtime (T2) ·
chú thích danh sách + tra theo id (T3) · answer + cờ + Citation (T4) · review (T5) ·
`/documents/{id}` (T6) · ba mặt web (T7) · Neo4j (T8) · ingest/deploy (T9) · benchmark + docs
(T10).

**Chỗ lệch spec có chủ đích:** spec viết `chu_thich_ket_qua` **loại** hit `bi_bai_bo`; plan
làm rõ ca "loại hết thì giữ lại kèm nhãn" thành hành vi có test riêng (T3 Step 1).

**Type consistency** — `ChuThichHieuLuc` dùng chung tên trường ở T2/T3/T4/T5;
`trang_thai` nhận đúng bốn giá trị `nguyen_ven|da_sua|bi_bai_bo|la_loi_sua` ở cả Python và
TypeScript; `tach_khoa` trả `(doc_id, nhãn)` dùng ở T2 và T6; `KetQuaTuyen.canh` thêm ở T2
được T2 đọc ngay.

**Rủi ro đã biết, không giấu:**
- `tbl.search().where(...)` đã thử trên LanceDB 0.34 **local**; trên LanceDB **Cloud** chưa
  thử — nên `lay_chunk_theo_id` bọc `try/except` trả rỗng (T3 Step 3).
- Nhãn `xuat_xu_article` ở cấp ĐIỀU, trong khi chunk có thể mang nhãn gộp
  (`"Điều 1 Khoản 1-6"`) ⇒ tra theo id sẽ trượt. Đây là lý do `ban_hien_hanh` (chữ đóng sẵn
  trong artefact) mới là đường chính, còn kéo chunk chỉ là đường phụ.
- `test_artefact_that_tai_duoc` (T2) phụ thuộc artefact do T1 sinh ra và đã commit — nếu T1
  chưa commit artefact thì test này đỏ.
