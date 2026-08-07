# Overlay dưới-văn-bản (Điều/Khoản/Điểm) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dựng lớp phủ thưa cấp Điều/Khoản/Điểm — cạnh tác động con↔con với lời văn mới có
xuất xứ span — và bộ định tuyến sau truy hồi, hoàn toàn offline (JSONL), theo spec
`docs/superpowers/specs/2026-08-05-overlay-duoi-van-ban-design.md`.

**Architecture:** Hai tầng — cạnh văn bản giữ nguyên; tầng con chỉ có node/cạnh cho đơn vị
bị chạm. P1 đọc mệnh lệnh tác động từ văn bản sửa (`tac_dong.py`), P2 dựng overlay + bản
hiện hành (`hien_hanh.py`), P3 định tuyến chunk→khoá→3 nhánh (`dinh_tuyen.py`).

**Tech Stack:** Python 3.12 · pydantic v2 · pytest · dữ liệu `data/raw/vbpl/{corpus,raw}` ·
tái dùng `app/ontology/{parser,citation}.py`, `app/ingestion/{bac_cau,vbpl_corpus}.py`.

## Global Constraints

- Mọi file ghi bằng `write_text(encoding="utf-8")` — KHÔNG shell redirect (PowerShell đổi encoding, lệch char_span).
- KHÔNG sửa `noi_dung`/`articles[].text`; khuyết tật nguồn → `canh_bao`, không nắn.
- KHÔNG đụng Neo4j/LanceDB/web (P4 chờ user gật riêng).
- Trục thời gian: chỉ-hiện-tại; mọi cạnh vẫn mang `valid_from` (mở đường as-of).
- Quét mệnh đề pháp lý luôn `re.IGNORECASE` (bài học "Bãi bỏ" viết hoa đầu khoản).
- Commit message TIẾNG ANH, Conventional Commits, mỗi task một commit; `uv run pytest -q` + `uv run ruff check .` xanh trước mỗi commit.
- Test chạy offline; test cần dữ liệu thật thì `skipif` theo `tho_theo_so_hieu` (nếp `tests/test_bac_cau.py`).
- Số đo nghiệm thu ghi DỰ ĐOÁN trước khi chạy; lệch thì tìm nguyên nhân, không chỉnh số cho khớp.

---

### Task 1: Schema `CanhTacDong` + nhận diện thao tác từ câu lệnh

**Files:**
- Create: `app/ontology/tac_dong.py`
- Test: `tests/test_tac_dong.py`

**Interfaces:**
- Produces: `class CanhTacDong(BaseModel)` — fields: `nguon: str`, `dich: str`,
  `thao_tac: Literal["sua_doi","bo_sung","bai_bo","thay_phu_luc","thay_cum_tu"]`,
  `loi_van_moi: tuple[int, int] | None`, `valid_from: str | None`, `menh_lenh: str`,
  `canh_bao: list[str]` (default []).
- Produces: `def thao_tac_tu_cau(cau: str) -> str | None` — đọc ĐỘNG TỪ MỞ ĐẦU mệnh lệnh.

- [ ] **Step 1: Viết test đỏ**

```python
"""Bộ đọc mệnh lệnh tác động: điều của văn bản sửa → cạnh con↔con. Offline."""
from __future__ import annotations

import pytest

from app.ontology.tac_dong import CanhTacDong, thao_tac_tu_cau


@pytest.mark.parametrize(
    ("cau", "cho"),
    [
        ("Sửa đổi, bổ sung điểm b (ii) khoản 4 Điều 11", "sua_doi"),
        ("sửa đổi khoản 2 như sau:", "sua_doi"),
        ("Bãi bỏ điểm c khoản 7.", "bai_bo"),           # viết hoa đầu khoản — ca TT22
        ("bãi bỏ Điều 16, Điều 17, Điều 18", "bai_bo"),
        ("Bổ sung khoản 3 Điều 32", "bo_sung"),
        ("Thay thế Phụ lục kèm theo Thông tư 40/2024/TT-NHNN", "thay_phu_luc"),
        ("Thay thế cụm từ “Cơ quan Thanh tra, giám sát ngân hàng”", "thay_cum_tu"),
        ("Tổ chức thực hiện", None),                     # không phải mệnh lệnh tác động
        ("Trách nhiệm thi hành", None),
    ],
)
def test_thao_tac_tu_cau(cau, cho):
    assert thao_tac_tu_cau(cau) == cho


def test_sua_doi_bo_sung_gop_ve_sua_doi():
    """'Sửa đổi, bổ sung X' là MỘT thao tác ghi đè lời văn — không tách đôi."""
    assert thao_tac_tu_cau("Sửa đổi, bổ sung một số điểm, khoản của Điều 18") == "sua_doi"


def test_canh_mang_du_truong_va_mac_dinh():
    c = CanhTacDong(nguon="41/2025/TT-NHNN#than/dieu_8",
                    dich="40/2024/TT-NHNN#than/dieu_24#khoan_4",
                    thao_tac="bai_bo", menh_lenh="Bãi bỏ khoản 4 Điều 24")
    assert c.loi_van_moi is None and c.valid_from is None and c.canh_bao == []
```

- [ ] **Step 2: Chạy xác nhận đỏ** — `uv run pytest tests/test_tac_dong.py -q` → FAIL (ModuleNotFoundError).

- [ ] **Step 3: Cài tối thiểu**

```python
"""Mệnh lệnh tác động trong văn bản sửa đổi → cạnh con↔con của lớp phủ.

Vì sao đọc ĐỘNG TỪ MỞ ĐẦU chứ không tìm từ khoá trong cả câu: câu lệnh luật luôn mở đầu
bằng động từ ("Sửa đổi…", "Bãi bỏ…", "Bổ sung…"), còn giữa câu có thể nhắc thao tác khác
("…đã được sửa đổi bởi…" là mô tả, không phải lệnh). IGNORECASE bắt buộc: mệnh đề đứng
đầu khoản viết hoa — grep thường đã một lần bỏ sót câu bãi bỏ của TT22 (05/08).

Thứ tự khớp có chủ đích: `thay_cum_tu`/`thay_phu_luc` trước `sua_doi` — "Thay thế cụm từ"
cũng bắt đầu bằng "Thay thế"; `bo_sung` sau `sua_doi` — "Sửa đổi, bổ sung" là một thao tác
ghi đè lời văn, chỉ khi đứng một mình "Bổ sung" mới là thêm mới.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

_BANG_THAO_TAC: list[tuple[str, str]] = [
    (r"thay\s*thế\s+cụm\s+từ", "thay_cum_tu"),
    (r"thay\s*thế\s+(?:một\s+số\s+)?phụ\s+lục", "thay_phu_luc"),
    (r"bãi\s+bỏ", "bai_bo"),
    (r"sửa\s+đổi", "sua_doi"),
    (r"bổ\s+sung", "bo_sung"),
]


class CanhTacDong(BaseModel):
    """Một mệnh lệnh tác động: đơn vị NGUỒN (văn bản sửa) chạm đơn vị ĐÍCH (văn bản nền)."""

    nguon: str
    dich: str
    thao_tac: Literal["sua_doi", "bo_sung", "bai_bo", "thay_phu_luc", "thay_cum_tu"]
    #: span trong `noi_dung` của văn bản SỬA — xuất xứ lời văn mới; bãi bỏ thì None.
    loi_van_moi: tuple[int, int] | None = None
    valid_from: str | None = None
    menh_lenh: str
    canh_bao: list[str] = Field(default_factory=list)


def thao_tac_tu_cau(cau: str) -> str | None:
    dau = cau.strip()
    for mau, ma in _BANG_THAO_TAC:
        if re.match(mau, dau, re.IGNORECASE):
            return ma
    return None
```

- [ ] **Step 4: Chạy xanh** — `uv run pytest tests/test_tac_dong.py -q` → PASS.
- [ ] **Step 5: `uv run ruff check .` rồi commit** — `feat(ontology): impact-command verbs and the CanhTacDong edge schema`

---

### Task 2: Giải đích — số hiệu nền của điều + viện dẫn → khoá node

**Files:**
- Modify: `app/ontology/tac_dong.py`
- Test: `tests/test_tac_dong.py` (thêm)

**Interfaces:**
- Consumes: `app.ingestion.vbpl_luoc_do.so_hieu_tu_tieu_de(tieu_de) -> tuple[str | None, list[str]]`;
  `app.ontology.citation.parse_citations(text) -> list[CitationRef]`,
  `app.ontology.citation.to_node_ids(ref, ctx_so_hieu, ctx_dieu=None, ctx_khoan=None) -> list[str]`.
- Produces: `def so_hieu_nen(tieu_de_dieu: str, mac_dinh: str) -> str` — số hiệu văn bản nền
  của MỘT điều (ND16 mỗi điều sửa một nghị định khác nhau); `def dich_tu_menh_lenh(menh_lenh: str,
  so_hieu_nen: str, ctx_dieu: str | None) -> tuple[list[str], list[str]]` → (khoá đích, cảnh báo).

- [ ] **Step 1: Test đỏ**

```python
from app.ontology.tac_dong import dich_tu_menh_lenh, so_hieu_nen


def test_so_hieu_nen_tu_tieu_de_dieu_kieu_ND16():
    """ND16 mỗi điều sửa một nghị định KHÁC — số hiệu nền đọc từ tiêu đề điều."""
    td = ("Sửa đổi, bổ sung, bãi bỏ một số điều của Nghị định số 101/2012/NĐ-CP "
          "ngày 07 tháng 5 năm 2012 của Chính phủ về thanh toán không dùng tiền mặt")
    assert so_hieu_nen(td, mac_dinh="?") == "101/2012/NĐ-CP"


def test_so_hieu_nen_roi_ve_mac_dinh_khi_tieu_de_khong_neu():
    """TT41 tiêu đề điều chỉ ghi 'Sửa đổi, bổ sung một số khoản của Điều 9' — nền là TT40."""
    assert so_hieu_nen("Sửa đổi, bổ sung một số khoản của Điều 9",
                       mac_dinh="40/2024/TT-NHNN") == "40/2024/TT-NHNN"


def test_dich_diem_du_ngu_canh_dieu():
    """'Bãi bỏ điểm c khoản 7.' không nêu Điều — Điều lấy từ tiêu đề điều lệnh (ctx)."""
    khoa, cb = dich_tu_menh_lenh("Bãi bỏ điểm c khoản 7.", "40/2024/TT-NHNN", ctx_dieu="8")
    assert khoa == ["40/2024/TT-NHNN#than/dieu_8#khoan_7#diem_c"] and cb == []


def test_dich_nhieu_dieu_mot_cau():
    khoa, _ = dich_tu_menh_lenh("Bãi bỏ Điều 16, Điều 17, Điều 18 Thông tư số 41/2025/TT-NHNN",
                                "41/2025/TT-NHNN", ctx_dieu=None)
    assert khoa == ["41/2025/TT-NHNN#than/dieu_16", "41/2025/TT-NHNN#than/dieu_17",
                    "41/2025/TT-NHNN#than/dieu_18"]


def test_khong_giai_duoc_thi_bao_ra_khong_doan():
    khoa, cb = dich_tu_menh_lenh("Sửa đổi một số nội dung khác.", "40/2024/TT-NHNN", None)
    assert khoa == [] and len(cb) == 1
```

- [ ] **Step 2: Chạy đỏ** — FAIL (ImportError).

- [ ] **Step 3: Cài**

```python
from app.ingestion.vbpl_luoc_do import so_hieu_tu_tieu_de
from app.ontology.citation import parse_citations, to_node_ids


def so_hieu_nen(tieu_de_dieu: str, mac_dinh: str) -> str:
    """Văn bản nền của MỘT điều lệnh. ND16 là lý do hàm này tồn tại: năm điều, năm nghị
    định nền khác nhau — lấy theo văn bản thì gán nhầm cả năm."""
    sh, _ = so_hieu_tu_tieu_de(tieu_de_dieu)
    return sh or mac_dinh


def dich_tu_menh_lenh(
    menh_lenh: str, so_hieu_nen: str, ctx_dieu: str | None
) -> tuple[list[str], list[str]]:
    """Câu lệnh → khoá node đích trong không gian văn bản NỀN.

    Dùng lại citation.py nguyên vẹn — nó đã thuộc 23 ca tiết của corpus. Không giải được
    thì BÁO chứ không đoán: một khoá sai trỏ vào node thật khác là kiểu hỏng im lặng nhất.
    """
    refs = parse_citations(menh_lenh)
    ra: list[str] = []
    for r in refs:
        for khoa in to_node_ids(r, ctx_so_hieu=so_hieu_nen, ctx_dieu=ctx_dieu):
            if khoa not in ra:
                ra.append(khoa)
    if ra:
        return ra, []
    return [], [f"không giải được đích từ mệnh lệnh: {menh_lenh[:80]!r}"]
```

Lưu ý cho người cài: nếu `to_node_ids` với câu "Bãi bỏ Điều 16, Điều 17, Điều 18…" trả một
ref nhiều `dieu` — kiểm bằng chính test trên; nếu tách nhiều ref thì vòng for đã gom đủ.
Nếu ref mang `van_ban` trùng `so_hieu_nen` thì khoá vẫn đúng không gian nền — thêm assert
trong test nếu thấy lệch.

- [ ] **Step 4: Chạy xanh** — `uv run pytest tests/test_tac_dong.py -q`.
- [ ] **Step 5: ruff + commit** — `feat(ontology): resolve impact targets into base-document node keys`

---

### Task 3: `canh_tu_dieu` — điều lệnh → danh sách cạnh, gắn khối trích dẫn

**Files:**
- Modify: `app/ontology/tac_dong.py`
- Test: `tests/test_tac_dong.py` (thêm)

**Interfaces:**
- Consumes: `app.ontology.parser.parse_dieu(text, so_hieu) -> DieuNode` (`.tieu_de`,
  `.khoan[]` với `.so_hien_thi/.start/.end/.text`), Task 1–2.
- Produces: `def canh_tu_dieu(nhan_dieu: str, text_dieu: str, char_start: int, so_hieu_sua: str,
  mac_dinh_nen: str, khoi_trich: list[tuple[int, int]], valid_from: str | None) -> list[CanhTacDong]`
  — `char_start` là vị trí `text_dieu` trong `noi_dung` văn bản sửa; `khoi_trich` là các span
  `trich_dan` (toạ độ `noi_dung`).

Quy tắc thiết kế (ghi vào docstring khi cài):
1. Điều không chẻ khoản (TT41 Đ8 "Bãi bỏ khoản 4 Điều 24"): cả thân điều là MỘT mệnh lệnh.
2. Điều chẻ khoản: MỖI khoản là một mệnh lệnh; `ctx_dieu` lấy từ tiêu đề điều
   (qua `parse_citations(tieu_de)` — ref nội bộ có `.dieu`).
3. Khối trích thuộc mệnh lệnh nào: khối `[a,b)` gắn vào khoản-lệnh có khoảng `noi_dung`
   `[char_start + k.start - d, char_start + k.end - d)` chứa nó, với `d = len(nhan_dieu) + 2`
   (bù prefix `f"{nhan_dieu}. "` đưa vào `parse_dieu`). Nhiều khối trong một mệnh lệnh ⇒
   span gộp `(min_start, max_end)` + cảnh báo nếu chúng không liền kề.
4. Mệnh lệnh `sua_doi`/`bo_sung` mà KHÔNG có khối trích ⇒ cạnh vẫn tạo, `loi_van_moi=None`
   + cảnh báo (thiếu lời văn mới là khuyết tật đáng thấy, không phải lý do vứt cạnh).
5. Text đưa vào `parse_citations` là phần NGOÀI khối trích của mệnh lệnh (mask bằng
   `trong_trich_dan` của parser hoặc cắt theo `khoi_trich`) — viện dẫn bên trong lời văn
   mới là của văn bản nền, không phải đích của lệnh.

- [ ] **Step 1: Test đỏ** (fixture tự dựng, mô phỏng đúng khuôn TT41)

```python
from app.ontology.tac_dong import canh_tu_dieu

_DIEU_LENH = (
    "Sửa đổi, bổ sung một số điểm của Điều 8\n"
    "1. Sửa đổi điểm a khoản 1 như sau:\n"
    "“a) Quy định mới cho điểm a.”\n"
    "2. Bãi bỏ điểm c khoản 7.\n"
)


def _khoi_trich_cua(text: str, char_start: int) -> list[tuple[int, int]]:
    a = char_start + text.index("“")
    b = char_start + text.index("”") + 1
    return [(a, b)]


def test_canh_tu_dieu_che_khoan():
    cs = 1000  # vị trí giả định trong noi_dung
    canh = canh_tu_dieu("Điều 1", _DIEU_LENH, cs, "41/2025/TT-NHNN", "40/2024/TT-NHNN",
                        _khoi_trich_cua(_DIEU_LENH, cs), valid_from="2025-11-05")
    assert [c.thao_tac for c in canh] == ["sua_doi", "bai_bo"]
    assert canh[0].dich == "40/2024/TT-NHNN#than/dieu_8#khoan_1#diem_a"
    assert canh[1].dich == "40/2024/TT-NHNN#than/dieu_8#khoan_7#diem_c"  # ctx Điều 8 từ tiêu đề
    assert canh[0].nguon == "41/2025/TT-NHNN#than/dieu_1#khoan_1"
    assert canh[0].loi_van_moi is not None and canh[1].loi_van_moi is None
    assert all(c.valid_from == "2025-11-05" for c in canh)


def test_canh_tu_dieu_khong_che_khoan():
    canh = canh_tu_dieu("Điều 8", "Bãi bỏ khoản 4 Điều 24", 5000,
                        "41/2025/TT-NHNN", "40/2024/TT-NHNN", [], valid_from="2025-11-05")
    assert len(canh) == 1
    assert canh[0].nguon == "41/2025/TT-NHNN#than/dieu_8"
    assert canh[0].dich == "40/2024/TT-NHNN#than/dieu_24#khoan_4"


def test_sua_doi_thieu_khoi_trich_thi_canh_bao_khong_vut():
    canh = canh_tu_dieu("Điều 2", "Sửa đổi khoản 3 Điều 9 như sau:", 0,
                        "41/2025/TT-NHNN", "40/2024/TT-NHNN", [], None)
    assert len(canh) == 1 and canh[0].loi_van_moi is None
    assert any("lời văn mới" in c for c in canh[0].canh_bao)
```

- [ ] **Step 2: Chạy đỏ.**
- [ ] **Step 3: Cài `canh_tu_dieu`** theo 5 quy tắc trên (dùng `parse_dieu(f"{nhan_dieu}. {text_dieu}", so_hieu_sua)` để chẻ khoản-lệnh; `thao_tac_tu_cau` cho từng mệnh lệnh; mệnh lệnh không có thao_tac → bỏ qua, không cạnh).
- [ ] **Step 4: Chạy xanh.**
- [ ] **Step 5: ruff + commit** — `feat(ontology): impact edges from one amending article, quote blocks attached`

---

### Task 4: Đối chứng + CLI chạy cả thư mục — nghiệm thu P1

**Files:**
- Modify: `app/ontology/tac_dong.py` (thêm `doi_chung`, `doc_tac_dong`, `__main__` qua `app/ontology/tac_dong.py` chạy bằng `python -m`)
- Test: `tests/test_tac_dong.py` (thêm)
- Output: `eval/overlay/canh_tac_dong.jsonl` + `eval/overlay/doi_chung.txt`

**Interfaces:**
- Consumes: `app.ingestion.vbpl_corpus.tho_theo_so_hieu(Path) -> dict[str, Path]`,
  `file_da_chuyen_khuon(Path)`; corpus file có `articles[].char_start`, top-level `trich_dan`
  (list `{char_start, char_end}`), raw file có `noi_dung` + `dieu_khoan_bi_tac_dong`
  (list `{dieu, cap?, so?, phan_loai: list, ...}`).
- Produces: `def doc_tac_dong(thu_muc: Path) -> tuple[list[CanhTacDong], list[str]]` — quét mọi
  văn bản sửa có toàn văn; `def doi_chung(canh: list[CanhTacDong], muc: list[dict],
  so_hieu_nen: str) -> list[str]` — so HAI CHIỀU với `dieu_khoan_bi_tac_dong` của văn bản nền.

Đối chứng hai chiều, so ở CẤP ĐIỀU của đích (mục `dieu_khoan_bi_tac_dong` cấp dưới điều dạng
`{dieu: "Điều 8", cap: "diem", so: "a"}` so bằng (điều, cap, so); mục cấp điều so bằng số điều):
- cạnh mình có mà danh sách nguồn không ghi → `"[+] {dich} không có trong dieu_khoan_bi_tac_dong"`;
- mục nguồn ghi mà mình không sinh cạnh → `"[-] {dieu} nguồn ghi {phan_loai} mà không có cạnh"`.
Lệch KHÔNG phải lỗi dừng — in có địa chỉ để người đọc soi.

- [ ] **Step 1: Test đỏ cho `doi_chung`** (fixture nhỏ tự dựng: 2 cạnh + 3 mục nguồn, một khớp,
  một [+], một [-]; assert đúng 2 dòng lệch, đúng tiền tố).

```python
from app.ontology.tac_dong import CanhTacDong, doi_chung


def test_doi_chung_hai_chieu():
    canh = [
        CanhTacDong(nguon="S#than/dieu_1", dich="N#than/dieu_8#khoan_1#diem_a",
                    thao_tac="sua_doi", menh_lenh="x"),
        CanhTacDong(nguon="S#than/dieu_2", dich="N#than/dieu_99", thao_tac="bai_bo",
                    menh_lenh="y"),
    ]
    muc = [
        {"dieu": "Điều 8", "cap": "diem", "so": "a", "phan_loai": ["sua_doi_bo_sung"]},
        {"dieu": "Điều 24", "cap": "khoan", "so": "4", "phan_loai": ["bai_bo"]},
    ]
    lech = doi_chung(canh, muc, so_hieu_nen="N")
    assert len(lech) == 2
    assert any(x.startswith("[+]") and "dieu_99" in x for x in lech)
    assert any(x.startswith("[-]") and "Điều 24" in x for x in lech)
```

- [ ] **Step 2: Chạy đỏ.**
- [ ] **Step 3: Cài `doi_chung` + `doc_tac_dong` + `main`.** `doc_tac_dong`: duyệt
  `file_da_chuyen_khuon`, chọn văn bản sửa = có ≥1 điều mà `thao_tac_tu_cau(tiêu đề điều
  hoặc dòng đầu thân)` khác None; với mỗi điều lệnh gọi `canh_tu_dieu` (khối trích lấy từ
  `trich_dan` cấp văn bản, lọc theo khoảng của điều); `valid_from` từ trường corpus.
  `main` in bảng: mỗi văn bản sửa — số điều lệnh, số cạnh, số cảnh báo; chạy `doi_chung`
  với từng văn bản NỀN trong corpus; ghi `eval/overlay/canh_tac_dong.jsonl` (mỗi dòng một
  cạnh, `model_dump_json`) và `eval/overlay/doi_chung.txt` bằng `write_text(encoding="utf-8")`.
- [ ] **Step 4: Test tích hợp trên dữ liệu thật** (skipif thiếu): TT41 → dự đoán ≥25 cạnh
  (27 điều, Đ26/Đ27 không phải lệnh); ca thật khoá cứng: tồn tại cạnh
  `41/2025/TT-NHNN#than/dieu_8` -bai_bo→ `40/2024/TT-NHNN#than/dieu_24#khoan_4`; TT22 Đ6 sinh
  3 cạnh bai_bo vào `41/2025/TT-NHNN#than/dieu_16..18`; mọi `loi_van_moi` (a,b) đều nằm trong
  một khối `trich_dan` và `noi_dung[a] == '“'` hoặc `'"'`.
- [ ] **Step 5: Chạy `uv run python -m app.ontology.tac_dong`**, đọc bảng phủ + `doi_chung.txt`,
  ghi số thật vào docstring test tích hợp (số đo được, KHÔNG chỉnh code cho khớp dự đoán mù).
  Nghiệm thu P1: ≥90% mục `dieu_khoan_bi_tac_dong` của TT40/TT15/TT34 có cạnh khớp.
- [ ] **Step 6: ruff + full pytest + commit** — `feat(ontology): impact reader over the full corpus, cross-checked against vbpl impact lists`

---

### Task 5: `DonViOverlay` + dựng overlay từ cạnh

**Files:**
- Create: `app/ontology/hien_hanh.py`
- Test: `tests/test_hien_hanh.py`

**Interfaces:**
- Consumes: `CanhTacDong` (Task 1), `app.ingestion.vbpl_corpus.doc_id_theo_corpus(so_hieu)`.
- Produces: `class DonViOverlay(BaseModel)` — `khoa: str`, `doc_id: str | None`,
  `vai: Literal["nguon_lenh","dich_bi_tac_dong"]`; `def dung_overlay(canh: list[CanhTacDong])
  -> list[DonViOverlay]` — mỗi đầu mút một node, dedup theo khoá, vai gộp nếu một khoá vừa
  là nguồn vừa là đích (giữ "dich_bi_tac_dong" — ca TT41 Đ16 vừa phát lệnh vừa bị TT22 bãi).

- [ ] **Step 1: Test đỏ**

```python
from app.ontology.hien_hanh import DonViOverlay, dung_overlay
from app.ontology.tac_dong import CanhTacDong


def _c(nguon, dich, thao_tac="sua_doi"):
    return CanhTacDong(nguon=nguon, dich=dich, thao_tac=thao_tac, menh_lenh="x")


def test_dung_overlay_dedup_va_gan_doc_id():
    canh = [
        _c("41/2025/TT-NHNN#than/dieu_1", "40/2024/TT-NHNN#than/dieu_8#khoan_1"),
        _c("41/2025/TT-NHNN#than/dieu_1", "40/2024/TT-NHNN#than/dieu_8#khoan_2"),
        _c("22/2026/TT-NHNN#than/dieu_6", "41/2025/TT-NHNN#than/dieu_16", "bai_bo"),
    ]
    nodes = {n.khoa: n for n in dung_overlay(canh)}
    assert len(nodes) == 5  # 2 nguồn + 3 đích, dieu_1 không nhân đôi
    assert nodes["40/2024/TT-NHNN#than/dieu_8#khoan_1"].doc_id == "TT40-2024"
    assert nodes["41/2025/TT-NHNN#than/dieu_1"].vai == "nguon_lenh"


def test_vua_nguon_vua_dich_thi_la_dich():
    """TT41 Đ16 phát lệnh sửa TT40 NHƯNG chính nó bị TT22 bãi — vai 'bị tác động' thắng."""
    canh = [
        _c("41/2025/TT-NHNN#than/dieu_16", "40/2024/TT-NHNN#than/dieu_41"),
        _c("22/2026/TT-NHNN#than/dieu_6", "41/2025/TT-NHNN#than/dieu_16", "bai_bo"),
    ]
    nodes = {n.khoa: n for n in dung_overlay(canh)}
    assert nodes["41/2025/TT-NHNN#than/dieu_16"].vai == "dich_bi_tac_dong"
```

- [ ] **Step 2: Chạy đỏ.** — **Step 3: Cài** (`doc_id` = `doc_id_theo_corpus(khoa.split("#")[0])`).
- [ ] **Step 4: Chạy xanh.** — **Step 5: ruff + commit** — `feat(ontology): sparse overlay nodes derived from impact edges`

---

### Task 6: `phien_ban_hien_hanh` — áp cạnh theo thời gian, luật cạnh-chết

**Files:**
- Modify: `app/ontology/hien_hanh.py`
- Test: `tests/test_hien_hanh.py` (thêm)

**Interfaces:**
- Produces: `class PhienBanHienHanh(BaseModel)` — `khoa: str`,
  `trang_thai: Literal["nguyen_ven","da_sua","bi_bai_bo"]`,
  `cac_lan: list[CanhTacDong]` (đã lọc + sort theo `valid_from`);
  `def phien_ban_hien_hanh(khoa: str, canh: list[CanhTacDong], hom_nay: str)
  -> PhienBanHienHanh`.

Ba luật (docstring khi cài):
1. Chỉ áp cạnh `valid_from ≤ hom_nay` (chỉ-hiện-tại; as-of sau này = đổi tham số).
2. **Luật cạnh-chết:** cạnh bị VÔ HIỆU nếu tồn tại cạnh `bai_bo` khác có `dich` là **tiền tố
   điều-nguồn** của nó (`nguon` bắt đầu bằng `dich_bai_bo`) và `valid_from` ≤ `hom_nay`
   — ca thật: TT22 bãi Đ16/17/18 TT41 ⇒ mọi cạnh phát từ ba điều đó không được áp.
3. Cạnh khớp `khoa` khi `dich == khoa` HOẶC `dich` là tiền tố của `khoa` (bãi cả điều thì
   khoản con cũng chết) — so tiền tố theo ranh `#` để `dieu_1` không nuốt `dieu_11`.

- [ ] **Step 1: Test đỏ**

```python
from app.ontology.hien_hanh import phien_ban_hien_hanh
from app.ontology.tac_dong import CanhTacDong


def _c(nguon, dich, thao_tac, vf):
    return CanhTacDong(nguon=nguon, dich=dich, thao_tac=thao_tac, menh_lenh="x",
                       valid_from=vf)


_TT41_SUA = _c("41/2025/TT-NHNN#than/dieu_16", "40/2024/TT-NHNN#than/dieu_41",
               "sua_doi", "2025-11-05")
_TT22_BAI = _c("22/2026/TT-NHNN#than/dieu_6", "41/2025/TT-NHNN#than/dieu_16",
               "bai_bo", "2026-05-19")


def test_nguyen_ven_khi_khong_canh_nao_cham():
    pb = phien_ban_hien_hanh("40/2024/TT-NHNN#than/dieu_1", [_TT41_SUA], "2026-08-05")
    assert pb.trang_thai == "nguyen_ven" and pb.cac_lan == []


def test_canh_chet_khong_duoc_ap():
    """Sau 19/05/2026, sửa đổi của TT41 Đ16 vào TT40 Đ41 KHÔNG còn áp (TT22 đã bãi Đ16)."""
    pb = phien_ban_hien_hanh("40/2024/TT-NHNN#than/dieu_41", [_TT41_SUA, _TT22_BAI],
                             "2026-08-05")
    assert pb.trang_thai == "nguyen_ven"
    # còn TRƯỚC ngày TT22 hiệu lực thì cạnh sống:
    pb_cu = phien_ban_hien_hanh("40/2024/TT-NHNN#than/dieu_41", [_TT41_SUA, _TT22_BAI],
                                "2026-01-01")
    assert pb_cu.trang_thai == "da_sua" and len(pb_cu.cac_lan) == 1


def test_bai_ca_dieu_thi_khoan_con_chet_nhung_khong_nuot_so_dai():
    bai = _c("S#than/dieu_1", "40/2024/TT-NHNN#than/dieu_1", "bai_bo", "2025-01-01")
    assert phien_ban_hien_hanh("40/2024/TT-NHNN#than/dieu_1#khoan_2", [bai],
                               "2026-08-05").trang_thai == "bi_bai_bo"
    assert phien_ban_hien_hanh("40/2024/TT-NHNN#than/dieu_11", [bai],
                               "2026-08-05").trang_thai == "nguyen_ven"  # dieu_1 ≠ dieu_11


def test_canh_tuong_lai_chua_ap():
    assert phien_ban_hien_hanh("40/2024/TT-NHNN#than/dieu_41", [_TT41_SUA],
                               "2025-01-01").trang_thai == "nguyen_ven"
```

- [ ] **Step 2: Chạy đỏ.** — **Step 3: Cài** (helper `_tien_to(khoa_ngan, khoa_dai)` so theo
  ranh `#`; sort `cac_lan` theo `valid_from`; `bi_bai_bo` khi lần áp cuối là `bai_bo`).
- [ ] **Step 4: Chạy xanh + test tích hợp** (skipif): chạy trên `canh_tac_dong.jsonl` thật —
  `40/2024/TT-NHNN#than/dieu_41` hôm nay phải `nguyen_ven` (TT41 Đ16 đã chết), và đếm tổng
  đơn vị `da_sua`/`bi_bai_bo` in ra để ghi vào WORKLOG.
- [ ] **Step 5: ruff + commit** — `feat(ontology): current-version derivation with the dead-edge rule (TT22 repeals TT41 articles)`

---

### Task 7: Định tuyến sau truy hồi — chunk-id → khoá → 3 nhánh

**Files:**
- Create: `app/ontology/dinh_tuyen.py`
- Test: `tests/test_dinh_tuyen.py`

**Interfaces:**
- Consumes: chunk-id dạng `f"{doc_id}::{label}"` với label `"Điều 8"` hoặc `"Điều 8 Khoản 7"`
  (xem `app/ingestion/pipeline.py::build_chunks/_split_khoan`); bảng `doc_id → so_hieu` từ
  corpus (`load_corpus`); `phien_ban_hien_hanh` (Task 6); các span `trich_dan` theo văn bản.
- Produces: `def khoa_tu_chunk_id(chunk_id: str, so_hieu_theo_doc: dict[str, str]) -> str | None`;
  `class KetQuaTuyen(BaseModel)` — `nhanh: Literal["nguyen_ven","nen_da_sua","trich_trong_van_ban_sua"]`,
  `khoa_goc: str`, `khoa_dich: str | None`, `trich_dan_dung_chu: str`;
  `def dinh_tuyen(chunk_id: str, span_chunk: tuple[int, int] | None, canh: list[CanhTacDong],
  so_hieu_theo_doc: dict[str, str], hom_nay: str) -> KetQuaTuyen | None`.

Nhánh 3 nhận diện: chunk thuộc văn bản SỬA và `span_chunk` giao với `loi_van_moi` của một
cạnh phát từ văn bản đó ⇒ `khoa_dich` = `dich` của cạnh, `trich_dan_dung_chu` =
`"{đích} (sửa bởi {nguồn})"` dạng người đọc: `"TT40-2024 Điều 8 Khoản 7 (sửa bởi TT41-2025 Điều 1)"`.

- [ ] **Step 1: Test đỏ**

```python
from app.ontology.dinh_tuyen import dinh_tuyen, khoa_tu_chunk_id
from app.ontology.tac_dong import CanhTacDong

_SH = {"TT40-2024": "40/2024/TT-NHNN", "TT41-2025": "41/2025/TT-NHNN"}
_CANH = [CanhTacDong(nguon="41/2025/TT-NHNN#than/dieu_1#khoan_1",
                     dich="40/2024/TT-NHNN#than/dieu_8#khoan_7",
                     thao_tac="sua_doi", menh_lenh="x", loi_van_moi=(1000, 1500),
                     valid_from="2025-11-05")]


def test_khoa_tu_chunk_id():
    assert khoa_tu_chunk_id("TT40-2024::Điều 8 Khoản 7", _SH) == \
        "40/2024/TT-NHNN#than/dieu_8#khoan_7"
    assert khoa_tu_chunk_id("TT40-2024::Điều 8", _SH) == "40/2024/TT-NHNN#than/dieu_8"
    assert khoa_tu_chunk_id("LA-J::Điều 1", _SH) is None  # doc lạ → không bịa


def test_ba_nhanh():
    v = dinh_tuyen("TT40-2024::Điều 1", None, _CANH, _SH, "2026-08-05")
    assert v.nhanh == "nguyen_ven"
    v = dinh_tuyen("TT40-2024::Điều 8 Khoản 7", None, _CANH, _SH, "2026-08-05")
    assert v.nhanh == "nen_da_sua" and v.khoa_dich == "40/2024/TT-NHNN#than/dieu_8#khoan_7"
    v = dinh_tuyen("TT41-2025::Điều 1 Khoản 1", (900, 1200), _CANH, _SH, "2026-08-05")
    assert v.nhanh == "trich_trong_van_ban_sua"
    assert "TT40-2024" in v.trich_dan_dung_chu and "sửa bởi" in v.trich_dan_dung_chu
```

- [ ] **Step 2: Chạy đỏ.** — **Step 3: Cài** (label parse bằng regex
  `^Điều\s+(\d+[a-zđ]?)(?:\s+Khoản\s+(\S+))?$`; nhánh 2 qua `phien_ban_hien_hanh`;
  nhánh 3 kiểm giao span).
- [ ] **Step 4: Chạy xanh.** — **Step 5: ruff + commit** — `feat(ontology): post-retrieval router (intact / amended-base / quoted-in-amender)`

---

### Task 8: Bộ câu hỏi gắn nhãn + tổng nghiệm thu + tài liệu

**Files:**
- Create: `eval/overlay/cau_hoi_nhan.jsonl` (≥10 dòng
  `{"chunk_id": …, "span": …, "nhanh_dung": …, "ghi_chu": …}` — gắn nhãn TAY khi thực thi,
  phủ cả 3 nhánh; bắt buộc có: một chunk TT34 nền chứa "Cơ quan Thanh tra, giám sát ngân
  hàng" (nhãn `nen_da_sua` — lời mới của TT66 là nơi duy nhất có "Cục Quản lý, giám sát tổ
  chức tín dụng"), một chunk trong khối trích TT41, một chunk ND52 nguyên vẹn)
- Test: `tests/test_dinh_tuyen.py` (thêm test đọc file nhãn, chạy `dinh_tuyen`, assert 100% khớp nhãn; skipif thiếu dữ liệu)
- Modify: `docs/KG-CONFORMANCE-v05.md` (mục mới: overlay P1–P3 với số đo thật),
  `docs/WORKLOG.md` (mục ngày, format sẵn có)

- [ ] **Step 1: Sinh nhãn** — chạy `build_chunks` trên corpus thật, chọn ≥10 chunk, gắn nhãn tay vào JSONL (đọc từng chunk, KHÔNG gắn theo kết quả của `dinh_tuyen`).
- [ ] **Step 2: Test đỏ→xanh** — viết test đọc nhãn + assert; nếu có ca sai, đó là bug định tuyến: sửa code (quy trình systematic-debugging), không sửa nhãn trừ khi nhãn sai thật (ghi lý do vào `ghi_chu`).
- [ ] **Step 3: Tổng kiểm** — `uv run pytest -q` (dự đoán: 517 + ~25 test mới, 0 đỏ) · `uv run ruff check .` · `uv run python -m app.ontology --classify data/fixtures` GIỮ `94 đơn vị: 45/9/40`.
- [ ] **Step 4: Cập nhật hai tài liệu** với số đo thật (số cạnh, % khớp đối chứng, số đơn vị da_sua/bi_bai_bo, kết quả bộ nhãn).
- [ ] **Step 5: Commit** — `feat(ontology): labeled routing eval; overlay P1-P3 measured and documented`

---

## Self-review đã chạy

- Spec coverage: P1→Task 1-4, P2→Task 5-6, P3→Task 7-8, ngoài-phạm-vi (thay_cum_tu chỉ là
  một giá trị Literal, không áp; as-of chỉ là tham số `hom_nay`) — khớp.
- Không còn placeholder; mọi bước code có code thật.
- Kiểu nhất quán: `CanhTacDong` dùng xuyên Task 1→7; `loi_van_moi: tuple[int,int] | None`
  thống nhất; chữ ký `phien_ban_hien_hanh(khoa, canh, hom_nay)` giữ nguyên ở Task 6 và 7.
