# Đánh giá trên bộ test SBV-LawGraph — kế hoạch triển khai

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chuyển 100 câu của bộ test SBV-LawGraph thành bộ câu hỏi eval của LexFlow, chạy đo trên 29 câu corpus phủ được, và ghi kết quả kèm hệ số quy về 100 câu.

**Architecture:** Một bộ chuyển đổi mới `eval/chuyen_sbv.py` sinh hai file JSONL — `bo_sbv.jsonl` (29 câu có nhãn, chạy được ngay bằng benchmark hiện có) và `bo_sbv_khong_can_cu.jsonl` (71 câu negative sạch, để dành cho T17). Không sửa `metrics.py`, `bo_cau_hoi.py` hay `run_benchmark.py`: bảng 100 câu suy bằng phép nhân chứ không chạy.

**Tech Stack:** Python 3.12 · uv · pytest · ruff. Không thêm dependency nào.

**Spec:** `docs/superpowers/specs/2026-08-12-danh-gia-bo-sbv-design.md`

## Global Constraints

- Chạy test: `uv run pytest -q`. Lint: `uv run ruff check .`. Cả hai phải sạch trước mỗi commit.
- Commit theo `docs/COMMIT-CONVENTION.md`: Conventional Commits, **message tiếng Anh**.
- Không tải model HF về máy; mọi thứ dùng cloud/API.
- Không sinh câu hỏi và không gán nhãn tay — mọi nhãn suy từ file nguồn + corpus.
- `TRONG_SO_THUA = 0.1` **không đổi** trong đợt này, kể cả khi sweep hold-out nói khác (luật đã chốt ở spec).
- Nhãn vàng cấp điều dùng đúng quy ước `metrics.khoa_dieu`: `"{doc_id}::Điều N"`.
- Ruff cấm tên biến `l` (E741) — đã vấp hai lần ở `chuyen_tvpl.py`.
- Đường dẫn nguồn: `data/evaluate/svb_graph/sbv_testset_tvpl.json`. Corpus: `data/corpus.real.json`.

---

### Task 1: `tach_nhan` — tách nhãn `"12/2022/tt-nhnn_3"`

**Files:**
- Create: `eval/chuyen_sbv.py`
- Test: `tests/test_chuyen_sbv.py`

**Interfaces:**
- Consumes: `eval.chuyen_tvpl.chuan_so_hieu(s: str) -> str`
- Produces: `tach_nhan(nhan: str) -> tuple[str, str]` trả `(số hiệu đã chuẩn hoá, số điều)`; ngoại lệ `NhanHong(ValueError)`

- [ ] **Step 1: Write the failing test**

Tạo `tests/test_chuyen_sbv.py`:

```python
"""Ghim phép chuyển bộ test SBV-LawGraph → bộ câu hỏi eval.

Nhãn sinh ra là suy diễn từ file nguồn + corpus, không phải nhãn người — sai ở đây không làm
test nào đỏ, chỉ làm bảng kết quả sai một cách trông rất bình thường.
"""
from __future__ import annotations

import pytest

from eval.chuyen_sbv import NhanHong, tach_nhan


def test_tach_tu_phai_khong_phai_tu_trai():
    """Hậu tố là SỐ ĐIỀU. Tách từ trái thì "…_21" ra "2" và nhãn trỏ nhầm điều."""
    assert tach_nhan("08/2023/tt-nhnn_21") == ("08/2023/TT-NHNN", "21")


def test_chu_thuong_duoc_viet_hoa_de_khop_corpus():
    """Nhãn SBV viết thường hoàn toàn; corpus ghi số hiệu viết hoa."""
    assert tach_nhan("40/2024/tt-nhnn_18") == ("40/2024/TT-NHNN", "18")


def test_bo_dau_de_khop_nghi_dinh():
    """Corpus ghi "NĐ-CP", bộ SBV ghi "nd-cp"."""
    assert tach_nhan("52/2024/nd-cp_3")[0] == "52/2024/ND-CP"


def test_so_dieu_co_chu_cai():
    assert tach_nhan("40/2024/tt-nhnn_12a") == ("40/2024/TT-NHNN", "12a")


def test_thieu_gach_duoi_thi_nem():
    with pytest.raises(NhanHong):
        tach_nhan("12/2022/tt-nhnn")


def test_hau_to_khong_phai_so_thi_nem():
    """Nhãn hỏng là lỗi ĐỊNH DẠNG, khác câu ngoài phạm vi — không được nuốt im lặng."""
    with pytest.raises(NhanHong):
        tach_nhan("12/2022/tt-nhnn_dieu-ba")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_chuyen_sbv.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'eval.chuyen_sbv'`

- [ ] **Step 3: Write minimal implementation**

Tạo `eval/chuyen_sbv.py`:

```python
"""Chuyển bộ test của bài báo SBV-LawGraph thành bộ câu hỏi eval của LexFlow.

Nguồn: `data/evaluate/svb_graph/sbv_testset_tvpl.json` — 100 câu, nhãn dạng
`"12/2022/tt-nhnn_3"` = số hiệu + số điều, tức **nhãn cấp điều trên 100% câu**.

Sinh HAI file, không gán nhãn tay dòng nào:

| File | Nội dung | Ai dùng |
|---|---|---|
| `eval/bo_sbv.jsonl` | câu mà corpus phủ đủ văn bản | `run_benchmark.py`, `quet_trong_so.py` |
| `eval/bo_sbv_khong_can_cu.jsonl` | câu dẫn văn bản corpus KHÔNG có | T17 (ngưỡng τ), chưa chạy |

**File thứ hai KHÔNG chạy được bằng `run_benchmark`** — nó không có nhãn vàng nên mọi mức IR bỏ
qua nó (`run_benchmark._tong_hop_ir`). Chạy rồi tưởng hệ điểm 0 là đọc sai. Nó là dữ liệu cho
T17: câu hỏi mà câu trả lời đúng là "không đủ căn cứ".

Chạy:
    uv run python eval/chuyen_sbv.py
    uv run python -u eval/run_benchmark.py --bo eval/bo_sbv.jsonl
"""
from __future__ import annotations

import re

from eval.chuyen_tvpl import chuan_so_hieu

_SO_DIEU = re.compile(r"^\d+[a-zđ]?$")


class NhanHong(ValueError):
    """Nhãn không đúng dạng `{số hiệu}_{số điều}`.

    Ném chứ không bỏ qua: nhãn hỏng là lỗi định dạng của file nguồn, khác hẳn "câu này dẫn văn
    bản ngoài corpus". Trộn hai thứ vào một nhánh bỏ-qua là cách mất dữ liệu êm nhất.
    """


def tach_nhan(nhan: str) -> tuple[str, str]:
    """`"12/2022/tt-nhnn_3"` → `("12/2022/TT-NHNN", "3")`.

    Tách từ **phải** (`rpartition`): hậu tố là số điều, số hiệu ở trước và bản thân nó chứa dấu
    gạch. Tách từ trái thì `"08/2023/tt-nhnn_21"` ra `"2"`.

    Số hiệu đi qua `chuan_so_hieu` ở dạng **thô, chữ thường**. Ở đó regex cắt đuôi slug
    (`^\\d+/\\d{4}/[A-ZĐ]+…`) sẽ KHÔNG khớp chuỗi thường, nên hàm rơi vào nhánh dự phòng
    `.upper().replace("Đ","D")` — và đó đúng là điều ta cần, vì định dạng SBV **không có đuôi
    slug** để cắt. Đừng "sửa" bằng cách viết hoa trước khi gọi: đuôi slug viết hoa lên thì regex
    nuốt luôn nó, đúng lỗi đã gặp 11/08. Cũng đừng thêm `re.IGNORECASE` vào regex đó vì cùng lý do.
    """
    so_hieu, sep, so_dieu = nhan.rpartition("_")
    if not sep or not _SO_DIEU.match(so_dieu):
        raise NhanHong(f"nhãn {nhan!r} không đúng dạng {{số hiệu}}_{{số điều}}")
    return chuan_so_hieu(so_hieu), so_dieu
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_chuyen_sbv.py -q`
Expected: PASS — 6 passed

Rồi `uv run ruff check .` → "All checks passed!"

- [ ] **Step 5: Commit**

```bash
git add eval/chuyen_sbv.py tests/test_chuyen_sbv.py
git commit -m "feat(eval): parse SBV-LawGraph article labels"
```

---

### Task 2: `dieu_co_that` — bắt nhãn trỏ vào điều corpus không có

**Files:**
- Modify: `eval/chuyen_sbv.py`
- Test: `tests/test_chuyen_sbv.py`

**Interfaces:**
- Produces: `dieu_co_that(corpus: dict) -> dict[str, set[str]]` — `doc_id` → tập **số điều** (chuỗi, ví dụ `{"18", "23"}`)

Kiểm này `chuyen_tvpl.py` không có. Nhãn `Điều 99` của một văn bản chỉ có 54 điều làm recall câu đó vĩnh viễn 0, và ta sẽ đọc thành "hệ dở" thay vì "nhãn sai".

- [ ] **Step 1: Write the failing test**

Thêm vào `tests/test_chuyen_sbv.py`:

```python
from eval.chuyen_sbv import dieu_co_that  # thêm vào dòng import sẵn có


def _corpus() -> dict:
    """Bốn văn bản đủ để dựng mọi ca: còn hiệu lực, đã hết hiệu lực, điều bị chẻ khoản."""
    return {
        "documents": [
            {"doc_id": "TT40-2024", "so_hieu": "40/2024/TT-NHNN",
             "valid_from": "2024-07-17", "valid_to": None,
             "articles": [{"article": "Điều 18", "text": ""},
                          {"article": "Điều 23 Khoản 1-3", "text": ""},
                          {"article": "Điều 23 Khoản 4-6", "text": ""}]},
            {"doc_id": "TT17-2024", "so_hieu": "17/2024/TT-NHNN",
             "valid_from": "2024-07-01", "valid_to": None,
             "articles": [{"article": "Điều 17", "text": ""}]},
            {"doc_id": "ND52-2024", "so_hieu": "52/2024/NĐ-CP",
             "valid_from": "2024-07-01", "valid_to": None,
             "articles": [{"article": "Điều 3", "text": ""}]},
            {"doc_id": "TT23-2014", "so_hieu": "23/2014/TT-NHNN",
             "valid_from": "2014-10-15", "valid_to": "2024-07-01",
             "articles": [{"article": "Điều 5", "text": ""}]},
        ],
        "relationships": [],
    }


def test_dieu_co_that_gom_theo_so_dieu():
    assert dieu_co_that(_corpus())["TT40-2024"] == {"18", "23"}


def test_dieu_bi_che_khoan_van_tinh_la_co():
    """`pipeline._split_khoan` chẻ điều dài thành "Điều 23 Khoản 1-3" — nhãn vàng vẫn là "Điều 23".

    Nếu kiểm bằng so khớp nhãn nguyên văn thì mọi điều dài đều bị coi là không tồn tại.
    """
    assert "23" in dieu_co_that(_corpus())["TT40-2024"]


def test_van_ban_khong_co_dieu_nao_thi_tap_rong():
    corpus = {"documents": [{"doc_id": "X", "so_hieu": "1/2020/TT-NHNN", "articles": []}],
              "relationships": []}
    assert dieu_co_that(corpus) == {"X": set()}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_chuyen_sbv.py -q`
Expected: FAIL — `ImportError: cannot import name 'dieu_co_that'`

- [ ] **Step 3: Write minimal implementation**

Thêm vào `eval/chuyen_sbv.py`, ngay dưới `_SO_DIEU`:

```python
_DIEU_TRONG_NHAN = re.compile(r"^Điều\s+(\d+[a-zđ]?)")
```

và thêm hàm sau `tach_nhan`:

```python
def dieu_co_that(corpus: dict) -> dict[str, set[str]]:
    """`doc_id` → tập **số điều** có thật trong corpus.

    Gom về số điều chứ không giữ nhãn nguyên văn: `pipeline._split_khoan` chẻ một điều dài thành
    `"Điều 23 Khoản 1-3"` / `"Điều 23 Khoản 4-6"`, nên so khớp nguyên văn sẽ coi mọi điều dài là
    không tồn tại và loại sạch những câu hỏi đáng giá nhất.
    """
    ra: dict[str, set[str]] = {}
    for d in corpus["documents"]:
        so: set[str] = set()
        for a in d.get("articles", []):
            m = _DIEU_TRONG_NHAN.match(a.get("article", ""))
            if m:
                so.add(m.group(1))
        ra[d["doc_id"]] = so
    return ra
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_chuyen_sbv.py -q`
Expected: PASS — 9 passed. Rồi `uv run ruff check .` sạch.

- [ ] **Step 5: Commit**

```bash
git add eval/chuyen_sbv.py tests/test_chuyen_sbv.py
git commit -m "feat(eval): index which articles the corpus actually holds"
```

---

### Task 3: `chuyen` — chia 100 câu thành hai bộ

**Files:**
- Modify: `eval/chuyen_sbv.py`
- Modify: `eval/chuyen_tvpl.py` (đổi tên `_truoc` → `truoc_mot_ngay`)
- Test: `tests/test_chuyen_sbv.py`

**Interfaces:**
- Consumes: `eval.chuyen_tvpl.tra_cuu(corpus) -> (dict[str,str], dict[str,tuple[str,str]], dict[str,str])` · `cua_so(doc_ids, hieu_luc) -> tuple[str,str] | None` · `XA = "9999-12-31"` · `truoc_mot_ngay(ngay: str) -> str`
- Produces: `chuyen(rows: list[dict], corpus: dict, hom_nay: str) -> tuple[list[dict], list[dict], Counter]` — `(bộ dùng được, bộ không căn cứ, lý do bị loại)`

`_truoc` đang là tên riêng tư nhưng nay dùng ở hai module, nên đổi thành công khai. Không test nào tham chiếu nó (`tests/test_chuyen_tvpl.py` chỉ import `chuan_so_hieu, chuyen, cua_so, tra_cuu`), nên đổi tên là thao tác an toàn — nhưng vẫn phải chạy lại toàn bộ suite.

- [ ] **Step 1: Đổi tên `_truoc` trong `eval/chuyen_tvpl.py`**

Sửa định nghĩa (dòng 96-98):

```python
def truoc_mot_ngay(ngay: str) -> str:
    """Ngày cuối cùng nhãn vàng còn đúng — `valid_to` là mốc **mở**, nên phải lùi một ngày."""
    return (date.fromisoformat(ngay) - timedelta(days=1)).isoformat()
```

và chỗ gọi duy nhất (trong `chuyen`, dòng 144):

```python
            "as_of": truoc_mot_ngay(den) if den != XA else hom_nay,
```

Run: `uv run pytest tests/test_chuyen_tvpl.py -q`
Expected: PASS — 13 passed (đổi tên không đổi hành vi)

- [ ] **Step 2: Write the failing test**

Thêm vào `tests/test_chuyen_sbv.py`:

```python
from eval.chuyen_sbv import chuyen  # thêm vào dòng import sẵn có

HOM_NAY = "2026-08-12"


def _cau(arts: list[str], qid: int = 1) -> dict:
    return {
        "question_id": qid,
        "question": "câu hỏi thử",
        "url": "https://thuvienphapluat.vn/hoi-dap-phap-luat/x.html",
        "relevant_articles": arts,
        "reference_answer": "trả lời tham chiếu",
    }


def test_cau_du_van_ban_vao_bo_dung_duoc():
    dung, kcc, bo = chuyen([_cau(["40/2024/tt-nhnn_18"])], _corpus(), HOM_NAY)
    assert len(dung) == 1 and not kcc and not bo
    assert dung[0]["relevant_articles"] == ["TT40-2024::Điều 18"]
    assert dung[0]["relevant_docs"] == ["TT40-2024"]
    assert dung[0]["expected_doc"] == "TT40-2024"
    assert dung[0]["question_id"] == 1


def test_cau_ngoai_corpus_vao_bo_khong_can_cu():
    dung, kcc, bo = chuyen([_cau(["12/2022/tt-nhnn_3"])], _corpus(), HOM_NAY)
    assert not dung and not bo
    assert kcc[0]["van_ban_thieu"] == ["12/2022/TT-NHNN"]
    assert "relevant_docs" not in kcc[0] and "relevant_articles" not in kcc[0]


def test_dieu_khong_ton_tai_thi_loai_va_dem_rieng():
    """Nhãn trỏ vào Điều 99 của văn bản chỉ có Điều 18/23 ⇒ recall vĩnh viễn 0, phải loại."""
    dung, kcc, bo = chuyen([_cau(["40/2024/tt-nhnn_99"])], _corpus(), HOM_NAY)
    assert not dung and not kcc
    assert bo["nhãn trỏ vào điều không có trong corpus"] == 1


def test_dieu_bi_che_khoan_khong_bi_loai():
    """Corpus giữ "Điều 23 Khoản 1-3"; nhãn vàng là "Điều 23" — vẫn phải nhận."""
    dung, _, bo = chuyen([_cau(["40/2024/tt-nhnn_23"])], _corpus(), HOM_NAY)
    assert len(dung) == 1 and not bo


def test_nhieu_dieu_cung_mot_van_ban():
    dung, _, _ = chuyen([_cau(["40/2024/tt-nhnn_18", "40/2024/tt-nhnn_23"])], _corpus(), HOM_NAY)
    assert dung[0]["relevant_articles"] == ["TT40-2024::Điều 18", "TT40-2024::Điều 23"]
    assert dung[0]["relevant_docs"] == ["TT40-2024"]


def test_as_of_la_hom_nay_khi_moi_van_ban_con_hieu_luc():
    dung, _, _ = chuyen([_cau(["40/2024/tt-nhnn_18"])], _corpus(), HOM_NAY)
    assert dung[0]["as_of"] == HOM_NAY
    assert dung[0]["cua_so"] == ["2024-07-17", None]


def test_as_of_lui_mot_ngay_khi_cua_so_dong():
    """TT23-2014 chết 2024-07-01; `valid_to` là mốc MỞ nên ngày cuối còn đúng là 30/06."""
    dung, _, _ = chuyen([_cau(["23/2014/tt-nhnn_5"])], _corpus(), HOM_NAY)
    assert dung[0]["as_of"] == "2024-06-30"


def test_khong_sinh_must_not_doc():
    """Bộ này không có mặt lỗi thời để đo; sinh `must_not_doc` sẽ làm stale_avoidance giả."""
    dung, _, _ = chuyen([_cau(["40/2024/tt-nhnn_18"])], _corpus(), HOM_NAY)
    assert "must_not_doc" not in dung[0]


def test_khong_mang_reference_answer_sang_file_nhan():
    """Giữ file nhãn sạch; Correctness sẽ join lại theo `question_id`."""
    dung, _, _ = chuyen([_cau(["40/2024/tt-nhnn_18"])], _corpus(), HOM_NAY)
    assert "reference_answer" not in dung[0]


def test_khong_mat_cau_nao():
    rows = [
        _cau(["40/2024/tt-nhnn_18"], qid=1),
        _cau(["12/2022/tt-nhnn_3"], qid=2),
        _cau(["40/2024/tt-nhnn_99"], qid=3),
        _cau([], qid=4),
    ]
    dung, kcc, bo = chuyen(rows, _corpus(), HOM_NAY)
    assert len(dung) + len(kcc) + sum(bo.values()) == len(rows)


def test_cau_khong_co_nhan_bi_loai():
    dung, kcc, bo = chuyen([_cau([])], _corpus(), HOM_NAY)
    assert not dung and not kcc and bo["không có nhãn"] == 1
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_chuyen_sbv.py -q`
Expected: FAIL — `ImportError: cannot import name 'chuyen'`

- [ ] **Step 4: Write minimal implementation**

Sửa dòng import ở đầu `eval/chuyen_sbv.py`:

```python
from __future__ import annotations

import re
from collections import Counter

from eval.chuyen_tvpl import XA, chuan_so_hieu, cua_so, tra_cuu, truoc_mot_ngay
```

Thêm vào cuối file:

```python
def chuyen(
    rows: list[dict], corpus: dict, hom_nay: str
) -> tuple[list[dict], list[dict], Counter]:
    """100 câu nguồn → (bộ dùng được, bộ không căn cứ, đếm lý do bị loại).

    Ba nhánh, và ba nhánh đó phải cộng lại đúng bằng số câu vào — kiểm ở `main()`. Một câu biến
    mất im lặng làm mẫu số nhỏ đi mà bảng vẫn trông bình thường.
    """
    so_hieu2id, hieu_luc, _ = tra_cuu(corpus)
    co_that = dieu_co_that(corpus)
    dung: list[dict] = []
    khong_can_cu: list[dict] = []
    bo: Counter = Counter()

    for r in rows:
        cap = [tach_nhan(a) for a in (r.get("relevant_articles") or [])]
        if not cap:
            bo["không có nhãn"] += 1
            continue

        labs = {lab for lab, _ in cap}
        thieu = sorted(labs - set(so_hieu2id))
        if thieu:
            # Negative sạch: không văn bản nào trong câu này có mặt trong corpus. Câu trả lời
            # đúng là "không đủ căn cứ" — dữ liệu cho T17, không phải câu bị hỏng.
            khong_can_cu.append({
                "query": r["question"],
                "question_id": r["question_id"],
                "van_ban_thieu": thieu,
                "nguon": "sbv",
            })
            continue

        docs = sorted({so_hieu2id[lab] for lab in labs})
        cs = cua_so(docs, hieu_luc)
        if cs is None:
            bo["các văn bản không cùng hiệu lực (cửa sổ rỗng)"] += 1
            continue
        tu, den = cs

        if any(sd not in co_that[so_hieu2id[lab]] for lab, sd in cap):
            bo["nhãn trỏ vào điều không có trong corpus"] += 1
            continue

        dung.append({
            "query": r["question"],
            "question_id": r["question_id"],
            "group": "sbv",
            "nguon": "sbv",
            # Tính từ cửa sổ chứ không hard-code hôm nay: khi một trong các văn bản bị thay thế,
            # `as_of` tự lùi về ngày cuối cửa sổ thay vì lặng lẽ sai.
            "as_of": truoc_mot_ngay(den) if den != XA else hom_nay,
            "cua_so": [tu, None if den == XA else den],
            "expected_doc": docs[0],
            "relevant_docs": docs,
            "relevant_articles": sorted(
                {f"{so_hieu2id[lab]}::Điều {sd}" for lab, sd in cap}
            ),
            # KHÔNG có `must_not_doc`: bộ này không có mặt lỗi thời nào để đo, nên
            # `stale_avoidance` sẽ bằng 1.0 và rỗng nghĩa — ghi rõ cạnh bảng, đừng tạo nhãn giả.
        })

    return dung, khong_can_cu, bo
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_chuyen_sbv.py -q`
Expected: PASS — 20 passed

Rồi cả suite: `uv run pytest -q` (phải xanh, gồm 13 test của `test_chuyen_tvpl.py` sau khi đổi tên) và `uv run ruff check .` sạch.

- [ ] **Step 6: Commit**

```bash
git add eval/chuyen_sbv.py eval/chuyen_tvpl.py tests/test_chuyen_sbv.py
git commit -m "feat(eval): split the SBV test set into usable and no-basis halves"
```

---

### Task 4: `main()` — sinh hai file, kiểm bất biến

**Files:**
- Modify: `eval/chuyen_sbv.py`
- Create (sinh ra): `eval/bo_sbv.jsonl`, `eval/bo_sbv_khong_can_cu.jsonl`

**Interfaces:**
- Produces: hai file JSONL. `bo_sbv.jsonl` đọc được bằng `eval.bo_cau_hoi.nap()` không ném.

- [ ] **Step 1: Viết `main()`**

Thay **toàn bộ** khối import ở đầu `eval/chuyen_sbv.py` bằng khối này (ruff repo này không bật
isort nên thứ tự không bị chặn, nhưng viết sẵn cho khỏi đoán):

```python
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

from eval.chuyen_tvpl import XA, chuan_so_hieu, cua_so, tra_cuu, truoc_mot_ngay
```

rồi thêm ngay dưới khối đó:

```python
GOC = Path(__file__).resolve().parent.parent
NGUON = GOC / "data/evaluate/svb_graph/sbv_testset_tvpl.json"
CORPUS = GOC / "data/corpus.real.json"
RA_DUNG = GOC / "eval/bo_sbv.jsonl"
RA_KHONG_CAN_CU = GOC / "eval/bo_sbv_khong_can_cu.jsonl"
```

và vào cuối file:

```python
def _ghi(duong_dan: Path, rows: list[dict]) -> None:
    duong_dan.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )


def main() -> None:
    rows = json.loads(NGUON.read_text(encoding="utf-8"))
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    dung, khong_can_cu, bo = chuyen(rows, corpus, date.today().isoformat())

    con = len(dung) + len(khong_can_cu) + sum(bo.values())
    if con != len(rows):
        raise AssertionError(f"mất câu: vào {len(rows)}, ra {con}")

    _ghi(RA_DUNG, dung)
    _ghi(RA_KHONG_CAN_CU, khong_can_cu)

    print(f"nguồn: {len(rows)} câu")
    print(f"  → {RA_DUNG.name}: {len(dung)} câu")
    print(f"  → {RA_KHONG_CAN_CU.name}: {len(khong_can_cu)} câu (negative, KHÔNG chạy benchmark)")
    if bo:
        print("bỏ:")
        for ly_do, n in bo.most_common():
            print(f"  {n:4d}  {ly_do}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Chạy và kiểm con số**

Run: `$env:PYTHONIOENCODING="utf-8"; uv run python eval/chuyen_sbv.py`

Expected — đúng ba con số này, đã đo trước ở giai đoạn brainstorm:

```
nguồn: 100 câu
  → bo_sbv.jsonl: 29 câu
  → bo_sbv_khong_can_cu.jsonl: 71 câu (negative, KHÔNG chạy benchmark)
```

Lệch khỏi 29/71 thì **dừng lại**, đừng chạy tiếp — hoặc corpus đã đổi (kiểm `git log data/corpus.real.json`), hoặc `tach_nhan` sai.

- [ ] **Step 3: Kiểm loader nạp được**

Run:

```powershell
uv run python -c "from eval.bo_cau_hoi import nap; c = nap('eval/bo_sbv.jsonl'); print(len(c), c[0].as_of, c[0].relevant_articles)"
```

Expected: `29 2026-08-12 ('TT40-2024::Điều 18',)` — số câu 29, `as_of` là hôm nay, nhãn điều đúng quy ước `::`.

- [ ] **Step 4: Commit**

```bash
git add eval/chuyen_sbv.py eval/bo_sbv.jsonl eval/bo_sbv_khong_can_cu.jsonl
git commit -m "feat(eval): generate the SBV question sets from the corpus"
```

---

### Task 5: Sweep hold-out — kiểm `TRONG_SO_THUA = 0.1` có overfit không

**Files:** không sửa file nào. Chỉ chạy và ghi số.

Đây là phần trả lời câu hỏi *"0.1 chỉnh trên ba bộ tự dựng, có đúng trên dữ liệu ngoài không"*. Rẻ: truy hồi một lượt mỗi câu rồi quét 6 trọng số trong bộ nhớ, vài phút, không tốn lượt benchmark nào.

- [ ] **Step 1: Chạy sweep**

Run: `$env:PYTHONIOENCODING="utf-8"; uv run python -u eval/quet_trong_so.py --bo eval/bo_sbv.jsonl`

Expected: hai bảng (mức văn bản 29 câu, mức điều 29 câu), mỗi bảng 6 dòng trọng số `0 / 0.1 / 0.25 / 0.5 / 0.75 / 1`, dòng `0.1` có hậu tố `(nay)`.

- [ ] **Step 2: Ghi lại nguyên văn hai bảng**

Chép hai bảng vào ghi chú tạm để Task 7 dán vào `docs/EVAL-IR.md`. **Không đổi `TRONG_SO_THUA`** dù kết quả thế nào — luật đã chốt ở spec: 29 câu với `|R| = 1` thì một câu = 3,4 điểm R@1, quá mỏng để dịch một hằng số sản phẩm.

- [ ] **Step 3: Nếu tối ưu KHÁC 0.1 thì mở mục TASKLIST**

Chỉ làm bước này khi bảng cho thấy một trọng số khác thắng 0.1 ở mức điều. Thêm vào `docs/TASKLIST.md`, cạnh T8:

```markdown
### [ ] T21 · Trọng số nhánh thưa có thể lệch giữa luật đã chết và luật hiện hành

- Sweep trên `eval/bo_sbv.jsonl` (29 câu, luật ĐANG hiệu lực, người ngoài soạn) cho tối ưu
  <ghi trọng số đo được> chứ không phải 0.1 — mà 0.1 được chỉnh trên ba bộ đều thiên về luật
  đã chết. Chưa đổi: 29 câu với |R| = 1 thì một câu = 3,4 điểm R@1.
- Bước đầu: cào 8 văn bản ở T20 để bộ này lên 72/100 câu, quét lại. Còn lệch thì mới đổi.
```

- [ ] **Step 4: Commit (chỉ khi có sửa TASKLIST)**

```bash
git add docs/TASKLIST.md
git commit -m "docs(eval): note the held-out sweep disagrees on the sparse weight"
```

---

### Task 6: Chạy benchmark trên 29 câu

**Files:** sinh `eval/results/<stamp>-bo_sbv.json`

Chạy **tách phiên**: chạy trực tiếp trong terminal của Claude Code bị kill khi đổi phiên, đã mất hai lượt đo ngày 11/08 vì việc này.

- [ ] **Step 1: Viết script chạy nền**

Tạo `<scratchpad>/chay_sbv.ps1`:

```powershell
$env:PYTHONIOENCODING = "utf-8"
Set-Location "D:\Vinuni\VSF\LexFlow-ai"
uv run python -u eval/run_benchmark.py --bo eval/bo_sbv.jsonl *> "$env:TEMP\claude\sbv.log"
"XONG exit=$LASTEXITCODE" | Out-File -Append -Encoding utf8 "$env:TEMP\claude\sbv.log"
```

- [ ] **Step 2: Chạy tách phiên**

```powershell
$p = Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','<scratchpad>\chay_sbv.ps1' -WindowStyle Hidden -PassThru; "PID=$($p.Id)"
```

- [ ] **Step 3: Theo dõi tiến độ**

```powershell
(Select-String -Path "$env:TEMP\claude\sbv.log" -Pattern '^\d+ ' -Encoding utf8).Count
```

Mỗi câu ~60-95 giây ⇒ 29 câu khoảng 30-45 phút. Dòng tiến độ bắt đầu bằng số thứ tự câu (`run_benchmark.py:288`).

- [ ] **Step 4: Kiểm số câu lỗi trước khi tin bảng**

```powershell
Get-Content "$env:TEMP\claude\sbv.log" -Encoding UTF8 | Select-Object -Last 40
```

`HttpError` thoáng qua từ LanceDB Cloud đã làm rơi 7/152 câu ngày 12/08. Với 29 câu, **mỗi câu rơi là 3,4 điểm** — nếu quá 2 câu lỗi thì **chạy lại** thay vì báo số trên mẫu số vá víu.

- [ ] **Step 5: Commit file kết quả**

```bash
git add eval/results/
git commit -m "test(eval): benchmark results on the SBV test set"
```

---

### Task 7: Ghi kết quả vào tài liệu

**Files:**
- Modify: `docs/EVAL-IR.md` (thêm §11 trước §8 hiện tại — đánh lại số mục), `README.md`, `docs/TASKLIST.md`, `docs/WORKLOG.md`

Mục §8-§10 hiện có sẽ dịch xuống thành §9-§11 khi chèn mục mới. Đơn giản hơn: **chèn mục mới thành §8** và dịch ba mục sau xuống, hoặc **thêm vào cuối thành §11**. Chọn thêm vào cuối thành §11 — không phải sửa tham chiếu chéo nào (README trỏ tới "§6–§7", `TASKLIST` trỏ tới "§6", "§7").

- [ ] **Step 1: Thêm §11 vào `docs/EVAL-IR.md`**

Viết vào cuối file, dùng đúng số đo lấy được ở Task 5 và Task 6:

```markdown
## 11. Bộ test của bài báo SBV-LawGraph — đo trên luật đang hiệu lực

`data/evaluate/svb_graph/sbv_testset_tvpl.json`: 100 câu hỏi-đáp, nhãn dạng
`"12/2022/tt-nhnn_3"` = số hiệu + số điều, tức **nhãn cấp điều trên 100% câu**. Đây là bộ test
của chính bài báo. `eval/chuyen_sbv.py` chuyển nó sang định dạng ở §4.

Khác ba bộ trước ở ba điểm: (1) hỏi về luật **đang hiệu lực** — TT17-2024, TT18-2024, TT40-2024,
NĐ52-2024 đều còn hiệu lực, trong khi mọi số IR trước nay đo trên luật đã chết từ 2024-07, tức
ca biên; (2) là **dữ liệu ngoài**, dùng làm hold-out kiểm `TRONG_SO_THUA = 0.1` có overfit
không; (3) nhãn cấp điều đầy đủ.

**Phủ corpus:** 29/100 câu dùng được. 27 văn bản được dẫn, corpus có 4. 0 câu có cửa sổ hiệu lực
rỗng, 0 nhãn trỏ vào điều corpus không có. 71 câu còn lại là **negative sạch cả 71** — không câu
nào dẫn lẫn một văn bản corpus có; chúng nằm ở `eval/bo_sbv_khong_can_cu.jsonl` để dành cho T17.

### Vì sao KHÔNG chạy 71 câu kia

71 câu đó dẫn văn bản ngoài corpus nên không kết quả nào khớp được: `recall = precision = rr = 0`
ở **mọi** cột. `metrics.tong_hop` là macro-average, nên thêm 71 số 0 vào trung bình của 29 câu
làm `recall`, `precision`, `mrr` nhân `29/100`. `f2 = 5PR/(4P+R)` cũng vậy: nhân cả `P` và `R`
với `c` cho `5c²PR / c(4P+R) = c · 5PR/(4P+R)`.

Tức **mọi ô của bảng 100 câu = ô tương ứng của bảng 29 câu × 0.29**. Chạy 71 câu tốn ~70 phút để
thu về một hằng số nhân, và vì mọi cột co cùng tỷ lệ, nó không phân biệt được cột nào với cột nào.

Nên khi đặt cạnh Table 3 của bài báo, con số phải đọc là: *trên đúng 100 câu của bài báo, mọi số
của LexFlow phải nhân 0.29 vì corpus thiếu 71/100 văn bản được hỏi.* Con số đó nói về **corpus**,
không nói về truy hồi. Cảnh báo ở §8 vẫn nguyên giá trị.

### Kết quả — `bo_sbv.jsonl`, <N>/29 câu, đo <ngày>

`eval/results/<tên file>`. Index: LanceDB Cloud chưa re-ingest (T1 còn mở). Retrieval p50 <x> ms.

<dán bảng mức văn bản và mức điều từ log>

**Đọc bảng này phải nhớ ba điều:**

- **29/29 câu chỉ dẫn đúng một văn bản.** Ở mức văn bản `R@k` vì thế suy biến thành "đúng văn bản
  có nằm trong top-k không" và không nói thêm gì so với `citation_accuracy`. Số đáng đọc nằm ở
  **mức điều** (26 câu một điều · 2 câu hai điều · 1 câu ba điều).
- **Một câu = 3,4 điểm R@1.** Mọi chênh lệch dưới 0.07 giữa hai cột là chênh lệch của **hai câu**.
- **`stale_avoidance` bằng 1.0 nhưng rỗng nghĩa** — bộ này không có `must_not_doc` vì không có
  mặt lỗi thời nào để đo, nên chỉ số đó mặc định đúng chứ không đo gì. Giống `bo_tvpl_dung_thoi`.

### Sweep hold-out — `TRONG_SO_THUA` trên dữ liệu ngoài

<dán bảng từ `eval/quet_trong_so.py --bo eval/bo_sbv.jsonl`>

<một đoạn: tối ưu có còn ở 0.1 không, và kết luận — KHÔNG đổi hằng số trong đợt này, vì 29 câu
với |R| = 1 quá mỏng để dịch một hằng số sản phẩm>

### Nạp thêm văn bản mở khoá thêm bao nhiêu câu

Tham lam trên 100 câu: `+94/2025/NĐ-CP` → 37, `+26/2024/TT-NHNN` → 44, `+61/2024/TT-NHNN` → 50,
`+64/2024/TT-NHNN` → 56, `+21/2024/TT-NHNN` → 61, `+58/2024/TT-NHNN` → 66, `+50/2024/TT-NHNN` →
69, `+32/2024/TT-NHNN` → 72. Ba văn bản sát phạm vi thanh toán: 64/2024 (Open API), 21/2024
(eKYC), 94/2025 (sandbox cho vay ngang hàng). Năm cái còn lại là ngân hàng nói chung — cào chúng
là **mở rộng sản phẩm**, không phải bổ sung dữ liệu. Xem T20.
```

- [ ] **Step 2: Thêm một đoạn vào `README.md`**

Chèn ngay sau bảng trước/sau trọng số (mục "Benchmark"), trước dòng `Cách đo, mẫu số và các cảnh báo`:

```markdown
**Bộ test của bài báo** — 100 câu SBV-LawGraph, corpus phủ 29 (`eval/bo_sbv.jsonl`, đo <ngày>).
Đây là bộ duy nhất hỏi về luật **đang hiệu lực**; ba bộ trên đều hỏi về luật đã chết từ 2024-07.
71 câu còn lại dẫn văn bản corpus không có ⇒ mọi cột ăn 0, nên bảng trên đúng 100 câu của bài báo
chỉ là bảng 29 câu **× 0.29** — con số đó nói về corpus, không nói về truy hồi (`docs/EVAL-IR.md` §11).
```

- [ ] **Step 3: Cập nhật `docs/TASKLIST.md`**

Sửa T17 (ngưỡng τ) — thêm vào cuối phần mô tả:

```markdown
- **Đã có bộ negative** (12/08): `eval/bo_sbv_khong_can_cu.jsonl` — 71 câu hỏi về luật hiện hành
  mà corpus không có, câu trả lời đúng là "không đủ căn cứ". Lấy thêm được **157 câu** cùng loại
  từ bộ TVPL (`data/evaluate/eval_filtered_clean.jsonl`) bằng cách thêm một file ra thứ ba vào
  `eval/chuyen_tvpl.py` — chưa làm vì T17 chưa bắt đầu.
- **Hai bộ khác LOẠI, đừng trộn rồi báo một tỷ lệ:** 71 câu SBV hỏi về luật **hiện hành** corpus
  thiếu; 157 câu TVPL hỏi về luật **đã chết trước 2024** corpus thiếu. Bộ SBV khó hơn — chủ đề
  của nó (Open API, eKYC, cho thuê tài chính) đủ gần thanh toán để truy hồi trả về văn bản trông
  rất hợp lý.
```

Sửa T20 — thêm nguồn thứ hai:

```markdown
- **Bộ SBV cũng chờ 8 văn bản này** (đo 12/08): cào đủ đưa `bo_sbv.jsonl` từ 29 → 72/100 câu.
  Thứ tự lợi nhất: `94/2025/NĐ-CP` · `26/2024/TT-NHNN` · `61/2024/TT-NHNN` · `64/2024/TT-NHNN` ·
  `21/2024/TT-NHNN` · `58/2024/TT-NHNN` · `50/2024/TT-NHNN` · `32/2024/TT-NHNN`.
```

- [ ] **Step 4: Thêm mục hôm nay vào `docs/WORKLOG.md`**

Mục mới trên cùng (dưới dấu `---` đầu tiên), theo đúng khuôn Done/Decision/Ship/Next của file. Phải có: số phủ 29/100 · kết quả mức điều · kết luận sweep hold-out · lý do không chạy 71 câu · bộ negative cho T17.

- [ ] **Step 5: Kiểm và commit**

```powershell
uv run ruff check .
uv run pytest -q
```

```bash
git add docs/EVAL-IR.md README.md docs/TASKLIST.md docs/WORKLOG.md
git commit -m "docs(eval): report results on the SBV-LawGraph test set"
git push origin feat/ai
```

---

## Kiểm chứng cuối

- [ ] `uv run ruff check .` → "All checks passed!"
- [ ] `uv run pytest -q` → xanh, gồm 20 test mới trong `tests/test_chuyen_sbv.py`
- [ ] `eval/bo_sbv.jsonl` có đúng 29 dòng, `eval/bo_sbv_khong_can_cu.jsonl` đúng 71 dòng, tổng = 100
- [ ] **Đối chiếu tay một câu.** `question_id` 4 của bộ nguồn là *"Hồ sơ mở ví điện tử gồm những giấy tờ gì?"*, nhãn `TT40-2024::Điều 18`. In top-20 của câu đó và tính `R@1` bằng tay:

```powershell
uv run python -c "from app.knowledge.retrieval import hybrid_search; from eval.metrics import khoa_dieu; [print(i, khoa_dieu(h)) for i, h in enumerate(hybrid_search('Hồ sơ mở ví điện tử gồm những giấy tờ gì?', top_k=20), 1)]"
```

  `R@1 = 1` nếu dòng đầu là `TT40-2024::Điều 18`, ngược lại `0`. So với ô `R@1` cột LexFlow hybrid trong log — lệch nghĩa là tầng đo đang đọc sai dữ liệu, dừng lại và tìm nguyên nhân trước khi ghi số vào tài liệu.
- [ ] **Gate hồi quy không đổi:** `eval/questions.jsonl` vẫn `stale_avoidance` 36/36. Đợt này không sửa file nào trong `app/`, nên nếu gate đỏ thì nguyên nhân nằm ngoài kế hoạch này.
