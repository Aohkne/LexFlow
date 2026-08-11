# GraphCompliance POC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nối tầng chuẩn tắc (`app/ontology/`) vào một đường Compliance Check chạy được
đầu-cuối trên 2 hợp đồng thật có comment pháp lý, đo recall so với đường `review.py` cũ.

**Architecture:** Policy Graph in-memory từ JSONL (schema mở rộng: `modality` 6 nhãn VN +
`Nguong` tất định) → Context Graph từ điều-hợp-đồng (ER-triple LLM + hypernym map trên
`KhaiNiem`) → Compliance Gate tất định (retrieval lai sẵn có + gate meta-CU + nở REFERS_TO)
→ judge CU-plan self-consistency + vòng override `mien_tru`. Spec đã duyệt:
`docs/superpowers/specs/2026-08-11-graphcompliance-poc-design.md`.

**Tech Stack:** Python 3.12, pydantic, stdlib `zipfile`/`xml.etree` (đọc docx — KHÔNG thêm
thư viện), Gemini qua `app.core.llm` (`chat_json`, `embed_documents`, `embed_query`),
LanceDB qua `app.knowledge.retrieval.search_in_docs` (chỉ đọc).

## Global Constraints

- **Không commit dữ liệu hợp đồng thật**: `docs/compliance/` và `eval/compliance/*.jsonl`
  phải nằm trong `.gitignore` (Task 7 thêm) TRƯỚC mọi lần chạy sinh dữ liệu. Không dán
  nguyên văn hợp đồng vào commit message / tài liệu.
- **Không ghi LanceDB Cloud / Neo4j Aura / Supabase, không deploy** — POC chỉ đọc.
- Test **không gọi mạng**: fake LLM bằng `monkeypatch.setattr(module, "chat_json", ...)`
  (mẫu ở `tests/test_reviews.py:61`); docx fixture tự dựng bằng `zipfile`, không chứa chữ
  hợp đồng thật.
- Mỗi task: `uv run pytest -q` xanh (hiện 797 passed) + `uv run ruff check .` sạch rồi mới
  commit. Commit message tiếng Anh theo `docs/COMMIT-CONVENTION.md`, kết bằng
  `Co-Authored-By: Claude <noreply@anthropic.com>`.
- Chạy script console: `$env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH='.'` (Windows).
- File do code ghi: luôn `write_text(..., encoding="utf-8")`, không bao giờ redirect shell.
- Giữ kỷ luật repo: regex/tra cứu làm được thì KHÔNG hỏi LLM; mọi cáo buộc từ LLM phải neo
  được về chữ gốc; ca không khớp schema → cờ cảnh báo, KHÔNG ép, KHÔNG tự chế class mới
  (giao thức "ca lạ" trong spec).

---

### Task 1: Mở rộng từ điển tình thái + `gan_modality`

**Files:**
- Modify: `app/ontology/modality.py` (từ điển `MODALITY` :22-31, thêm hàm cuối file)
- Test: `tests/test_ontology_modality_gan.py` (mới)

**Interfaces:**
- Consumes: `MODALITY`, `_MODALITY_RE`, `_PHRASE_GROUP`, `_WORD_RE` có sẵn trong module.
- Produces: `gan_modality(text: str) -> str` trả một trong
  `{"nghia_vu","cam","cho_phep","chi_duoc","mien_tru","khong_ro"}`. Task 3 và Task 12 dùng.
  Hai nhóm mới trong `MODALITY`: `chi_duoc`, `mien_tru`.

- [ ] **Step 1: Viết test fail**

```python
"""Gán nhãn tình thái tất định cho ActorCU — 6 nhãn VN, không hỏi LLM."""
from app.ontology.modality import gan_modality


def test_sau_nhan_co_ban():
    assert gan_modality("Ngân hàng phải cung cấp thông tin") == "nghia_vu"
    assert gan_modality("không được thu phí ngoài biểu phí") == "cam"
    assert gan_modality("khách hàng được quyền tra soát") == "cho_phep"
    assert gan_modality("chỉ được thu phí khi đã niêm yết") == "chi_duoc"
    assert gan_modality("không phải bồi thường thiệt hại") == "mien_tru"
    assert gan_modality("danh sách đơn vị chấp nhận thanh toán") == "khong_ro"


def test_chi_duoc_thang_duoc():
    # BẪY: "chỉ được" chứa "được" — khớp dài nhất trước phải thắng
    assert gan_modality("chỉ được cung ứng dịch vụ khi có Giấy phép") == "chi_duoc"


def test_khong_phai_la_khong_phai_mien_tru():
    # "không phải LÀ" = phủ định danh xưng, không phải miễn trừ nghĩa vụ
    assert gan_modality("tổ chức không phải là ngân hàng phải đăng ký") == "nghia_vu"


def test_uu_tien_cam_truoc():
    # Câu vừa có "phải" vừa có "không được" → cấm thắng (khắt khe hơn)
    assert gan_modality("phải niêm yết và không được thu thêm") == "cam"


def test_duoc_mien():
    assert gan_modality("được miễn phí dịch vụ trong 12 tháng") == "mien_tru"
```

- [ ] **Step 2: Chạy để thấy fail**

Run: `uv run pytest tests/test_ontology_modality_gan.py -v`
Expected: FAIL — `ImportError: cannot import name 'gan_modality'`

- [ ] **Step 3: Cài đặt tối thiểu**

Trong `MODALITY` (giữ nguyên 5 nhóm cũ, thêm 2 — thứ tự trong nhóm không quan trọng,
regex đã sắp giảm dần theo độ dài):

```python
    "chi_duoc": ["chỉ được phép", "chỉ được"],
    "mien_tru": ["không bắt buộc", "được miễn", "không phải"],
```

Cuối file thêm:

```python
# --- Gán nhãn tình thái cho ActorCU (POC GraphCompliance) ----------------------

#: Thứ tự ưu tiên khi một đoạn chứa nhiều nhóm: nhóm khắt khe hơn thắng.
#: "cam" trước "chi_duoc": câu cấm thường kèm vế cho phép có điều kiện.
_UU_TIEN = ("cam", "chi_duoc", "mien_tru", "nghia_vu", "cho_phep")


def gan_modality(text: str) -> str:
    """Nhãn tình thái của MỘT trường đã neo — tất định, chỉ từ điển.

    "không phải là" bị loại: đó là phủ định danh xưng ("không phải là ngân hàng"),
    không phải miễn trừ nghĩa vụ. Kiểm từ liền sau, cùng cách `_hard_deu_co_can_cu`
    xét cặp (dấu hiệu + từ liền sau).
    """
    low = text.lower()
    groups: set[str] = set()
    for m in _MODALITY_RE.finditer(low):
        g = _PHRASE_GROUP[m.group(1)]
        if g == "mien_tru" and m.group(1) == "không phải":
            sau = _WORD_RE.search(low, m.end())
            if sau and sau.group() == "là":
                continue
        groups.add(g)
    return next((g for g in _UU_TIEN if g in groups), "khong_ro")
```

- [ ] **Step 4: Chạy test mới + TOÀN BỘ suite**

Run: `uv run pytest tests/test_ontology_modality_gan.py -v` → PASS.
Run: `uv run pytest -q` — **chú ý**: thêm nhóm vào `MODALITY` đổi hành vi
`find_markers`/`modality_delta` ("chỉ được" trước đây khớp "được"/nhóm `cho_phep`, giờ
thành nhóm `chi_duoc`; "không phải"/"được miễn" trước đây không khớp gì). Nếu test guard
hiện có đỏ: đọc từng ca — kỳ vọng cũ dựa trên nhóm cũ thì CẬP NHẬT kỳ vọng (ghi rõ trong
commit message); logic guard sai thật thì sửa logic. KHÔNG thêm `chi_duoc`/`mien_tru` vào
`_HARD_GROUPS` trong task này (đổi hành vi guard là việc khác, chưa có dữ liệu đo).

- [ ] **Step 5: ruff + commit**

```bash
uv run ruff check .
git add app/ontology/modality.py tests/test_ontology_modality_gan.py
git commit -m "feat(ontology): deterministic 6-label Vietnamese deontic modality"
```

---

### Task 2: `Nguong` + `boc_nguong` tất định

**Files:**
- Modify: `app/ontology/schema.py` (thêm class `Nguong` ngay trước `class Grounding`, ~:88)
- Modify: `app/ontology/modality.py` (thêm `boc_nguong` cuối file)
- Test: `tests/test_ontology_nguong.py` (mới)

**Interfaces:**
- Produces: `class Nguong(BaseModel)` với `so: str`, `don_vi: str | None`,
  `huong: Literal["toi_thieu","toi_da","khong_ro"]`, `text: str`, `span: tuple[int,int]`.
  `boc_nguong(text: str, offset: int = 0) -> tuple[list[Nguong], list[str]]` — phần tử 2
  là cảnh báo `nguong_bo_sot`. Task 3 gắn vào `ActorCU`, Task 12 đưa vào prompt judge.

- [ ] **Step 1: Viết test fail**

```python
"""Bóc ràng buộc định lượng tất định — ghép dấu hiệu dinh_luong với số liền kề."""
from app.ontology.modality import boc_nguong


def test_khong_qua_tien():
    ns, ws = boc_nguong("hạn mức không quá 100 triệu đồng mỗi tháng")
    assert ws == []
    assert len(ns) == 1
    n = ns[0]
    assert (n.so, n.huong, n.don_vi) == ("100", "toi_da", "triệu đồng")
    assert "không quá 100 triệu đồng" in n.text


def test_cham_nhat_ngay_lam_viec():
    ns, _ = boc_nguong("hoàn trả chậm nhất 05 ngày làm việc")
    assert (ns[0].so, ns[0].huong, ns[0].don_vi) == ("5", "toi_da", "ngày làm việc")


def test_tro_len_dau_hieu_dung_sau():
    ns, _ = boc_nguong("khách hàng đủ 15 tuổi trở lên")
    assert (ns[0].so, ns[0].huong, ns[0].don_vi) == ("15", "toi_thieu", "tuổi")


def test_phan_tram():
    ns, _ = boc_nguong("duy trì tối thiểu 50% số dư")
    assert (ns[0].so, ns[0].huong, ns[0].don_vi) == ("50", "toi_thieu", "%")


def test_so_khong_dau_hieu_khong_thanh_nguong():
    # số điều khoản / viện dẫn không phải ngưỡng
    ns, ws = boc_nguong("quy định tại khoản 2 Điều 5 Nghị định này")
    assert ns == [] and ws == []


def test_dau_hieu_khong_so_bao_bo_sot():
    ns, ws = boc_nguong("hoàn trả trong thời hạn do các bên thỏa thuận")
    assert ns == []
    assert len(ws) == 1 and "nguong_bo_sot" in ws[0]


def test_offset_span():
    ns, _ = boc_nguong("không quá 20 triệu đồng", offset=100)
    s, e = ns[0].span
    assert s >= 100 and "không quá 20 triệu đồng"[s - 100 : e - 100] == ns[0].text
```

- [ ] **Step 2: Chạy để thấy fail**

Run: `uv run pytest tests/test_ontology_nguong.py -v`
Expected: FAIL — `ImportError: cannot import name 'boc_nguong'`

- [ ] **Step 3: Cài đặt**

`schema.py` (trước `Grounding`):

```python
class Nguong(BaseModel):
    """Một ràng buộc định lượng, bóc TẤT ĐỊNH từ text đã neo — không hỏi LLM.

    Đứng riêng với `DieuKienCong`: bên đó trả lời "quy định này áp dụng chưa"
    (gate, mốc ngày), bên này trả lời "hành vi này vượt mức chưa" (nghĩa vụ, số).
    """

    so: str  # chuẩn hoá như find_numbers: "05" → "5"
    don_vi: str | None
    huong: Literal["toi_thieu", "toi_da", "khong_ro"]
    text: str  # cụm gốc bao trùm dấu hiệu + số + đơn vị
    span: tuple[int, int]  # neo vào text nguồn (cộng offset khi bóc từ field)
```

`modality.py` (cuối file; import `Nguong` từ `app.ontology.schema` sẽ tạo vòng —
`schema.py` KHÔNG import modality nên import một chiều `modality → schema` là an toàn,
kiểm bằng `uv run python -c "import app.ontology.modality"`):

```python
_HUONG = {
    "tối thiểu": "toi_thieu", "ít nhất": "toi_thieu", "trở lên": "toi_thieu",
    "tối đa": "toi_da", "nhiều nhất": "toi_da", "không quá": "toi_da",
    "chậm nhất": "toi_da", "trở xuống": "toi_da", "trong thời hạn": "toi_da",
}
_DAU_HIEU_SAU = {"trở lên", "trở xuống"}  # đứng SAU con số: "15 tuổi trở lên"
_CUA_SO = 40  # số phải nằm trong 40 ký tự quanh dấu hiệu
_DINH_LUONG_RE = re.compile(
    r"(?<![\wÀ-ỹ])(" + "|".join(
        re.escape(p) for p in sorted(MODALITY["dinh_luong"], key=len, reverse=True)
    ) + r")(?![\wÀ-ỹ])"
)
_DON_VI_RE = re.compile(r"[ \t]*([%\wÀ-ỹ][\wÀ-ỹ% ]{0,28})")


def _don_vi_sau_so(text: str, num_end: int) -> str | None:
    m = _DON_VI_RE.match(text, num_end)
    if not m:
        return None
    dv = m.group(1)
    # cắt dấu hiệu đứng sau ("tuổi trở lên" → "tuổi") và từ nối
    dv = re.split(r"\b(?:trở lên|trở xuống|và|hoặc|mỗi|/)\b", dv)[0].strip(" .,;")
    return dv or None


def boc_nguong(text: str, offset: int = 0):
    """→ (list[Nguong], list[cảnh báo]). Dấu hiệu dinh_luong không ghép được số
    trong cửa sổ → cảnh báo `nguong_bo_sot` (giao thức "ca lạ": không ép, không im lặng)."""
    from app.ontology.schema import Nguong

    low = text.lower()
    ra: list[Nguong] = []
    canh_bao: list[str] = []
    da_dung: set[int] = set()  # vị trí số đã ghép — một số không thành hai ngưỡng
    for m in _DINH_LUONG_RE.finditer(low):
        dau_hieu = m.group(1)
        if dau_hieu in _DAU_HIEU_SAU:
            cua_so = [n for n in _NUM_RE.finditer(text, max(0, m.start() - _CUA_SO), m.start())]
            num = cua_so[-1] if cua_so else None
        else:
            num = _NUM_RE.search(text, m.end(), m.end() + _CUA_SO)
        if num is None:
            canh_bao.append(f"nguong_bo_sot: dấu hiệu {dau_hieu!r} không ghép được số")
            continue
        if num.start() in da_dung:
            continue  # "tối thiểu 15 tuổi trở lên" — hai dấu hiệu, một ngưỡng
        da_dung.add(num.start())
        don_vi = _don_vi_sau_so(text, num.end())
        start = min(m.start(), num.start())
        end = num.end() + (len(don_vi) + 1 if don_vi else 0)
        ra.append(Nguong(
            so=_norm_num(num.group()),
            don_vi=don_vi,
            huong=_HUONG.get(dau_hieu, "khong_ro"),
            text=text[start:end].strip(),
            span=(offset + start, offset + end),
        ))
    return ra, canh_bao
```

- [ ] **Step 4: Chạy test — chỉnh cửa sổ/regex đến khi PASS cả 7 ca**

Run: `uv run pytest tests/test_ontology_nguong.py -v` → PASS.
Run: `uv run pytest -q` → không đỏ thêm test nào (hàm mới, chưa ai gọi).

- [ ] **Step 5: ruff + commit**

```bash
uv run ruff check .
git add app/ontology/schema.py app/ontology/modality.py tests/test_ontology_nguong.py
git commit -m "feat(ontology): Nguong threshold record extracted deterministically"
```

---

### Task 3: Gắn `modality` + `nguong` vào `ActorCU` trong extractor

**Files:**
- Modify: `app/ontology/schema.py` — `class ActorCU` (:310-330) thêm 2 field
- Modify: `app/ontology/extractor.py` — `build_actor_cu` (:548-593)
- Test: `tests/test_extract_modality_nguong.py` (mới)

**Interfaces:**
- Consumes: `gan_modality`, `boc_nguong` (Task 1-2); `build_actor_cu(data, khoan, dieu,
  units) -> ActorCU` hiện có — **không gọi LLM, test offline được** (docstring :551).
- Produces: `ActorCU.modality: str = "khong_ro"`, `ActorCU.nguong: list[Nguong]`.
  Cảnh báo mới trong `ActorCU.warnings`: tiền tố `"tinh_thai_kho:"` và `"nguong_bo_sot:"`.

- [ ] **Step 1: Viết test fail** — dựng `DieuNode` bằng `parse_dieu` như các test extractor
  hiện có (xem mẫu dựng data trong `tests/test_extract.py`; đề bài dùng text tự chế):

```python
"""ActorCU nhận modality + nguong tất định khi build từ JSON của LLM."""
from app.ontology.extractor import build_actor_cu
from app.ontology.parser import parse_dieu
from app.ontology.segmenter import segment

_TEXT = (
    "Điều 9. Hạn mức giao dịch\n"
    "1. Tổ chức cung ứng dịch vụ không được cho phép giao dịch vượt hạn mức "
    "không quá 100 triệu đồng mỗi tháng đối với một khách hàng cá nhân."
)


def _dieu_va_khoan():
    dieu = parse_dieu(_TEXT, "99/2024/TT-TEST")
    khoan = dieu.khoan[0]
    return dieu, khoan, segment(dieu, khoan)


def test_actor_cu_mang_modality_va_nguong():
    dieu, khoan, units = _dieu_va_khoan()
    # units[0] = tiêu đề Điều; đơn vị thân khoản bắt đầu từ 1
    data = {
        "subject": {"units": [1], "label": "Tổ chức cung ứng dịch vụ"},
        "action": {"units": [1], "label": "không cho phép giao dịch vượt hạn mức"},
        "logic": "all",
        "conditions": [],
    }
    cu = build_actor_cu(data, khoan, dieu, units)
    assert cu.modality == "cam"  # "không được" trong action.text đã neo
    assert len(cu.nguong) == 1
    assert (cu.nguong[0].so, cu.nguong[0].huong) == ("100", "toi_da")
    # span của nguong phải nằm trong dieu.text và round-trip đúng chữ
    s, e = cu.nguong[0].span
    assert cu.nguong[0].text == dieu.text[s:e].strip()


def test_khong_ro_nhung_khoan_co_rang_buoc_cung_thi_canh_bao():
    dieu, khoan, units = _dieu_va_khoan()
    # action neo vào tiêu đề Điều (unit 0) — text không mang dấu hiệu nào
    data = {
        "subject": {"units": [1], "label": "Tổ chức"},
        "action": {"units": [0], "label": "hạn mức giao dịch"},
        "conditions": [],
    }
    cu = build_actor_cu(data, khoan, dieu, units)
    assert cu.modality == "khong_ro"
    assert any(w.startswith("tinh_thai_kho:") for w in cu.warnings)
```

- [ ] **Step 2: Chạy để thấy fail**

Run: `uv run pytest tests/test_extract_modality_nguong.py -v`
Expected: FAIL — `AttributeError: 'ActorCU' object has no attribute 'modality'`
(hoặc AssertionError nếu pydantic bỏ qua — cả hai đều là fail đúng).

- [ ] **Step 3: Cài đặt**

`schema.py`, trong `ActorCU` sau `conditions`:

```python
    # Tình thái + ngưỡng — GÁN TẤT ĐỊNH ở build_actor_cu từ text đã neo, không phải
    # lời khai của LLM. 6 nhãn VN thay cho must/must_not/may: "chỉ được…khi" và
    # miễn trừ nghĩa vụ bị 3 nhãn Tây đọc ngược nghĩa. Xem spec 2026-08-11.
    modality: Literal[
        "nghia_vu", "cam", "cho_phep", "chi_duoc", "mien_tru", "khong_ro"
    ] = "khong_ro"
    nguong: list[Nguong] = Field(default_factory=list)
```

`extractor.py`: đầu file thêm import `boc_nguong, gan_modality, groups_in` từ
`app.ontology.modality`. Trong `build_actor_cu`, sau khi có `conditions` và trước
`return ActorCU(...)`:

```python
    modality = gan_modality(action.text)
    khoan_text = dieu.text[khoan.start:khoan.end]
    if modality == "khong_ro" and groups_in(khoan_text) & {"nghia_vu", "cam", "chi_duoc"}:
        warnings.append(
            "tinh_thai_kho: action không mang dấu hiệu tình thái nhưng khoản có "
            "ràng buộc cứng — cần người xem lại field action"
        )
    nguong = []
    fields = [(action.text, action.grounding.char_span)] + [
        (c.text, c.grounding.char_span) for c in conditions
    ]
    for f_text, span in fields:
        ns, ws = boc_nguong(f_text, offset=span[0] if span else 0)
        nguong += ns
        warnings += ws
```

rồi thêm `modality=modality, nguong=nguong,` vào lời gọi `ActorCU(...)`.

- [ ] **Step 4: Chạy test + toàn suite**

Run: `uv run pytest tests/test_extract_modality_nguong.py -v` → PASS.
Run: `uv run pytest -q` → các test extractor cũ vẫn xanh (field mới có default, JSONL cũ
đọc lại vẫn hợp lệ).

- [ ] **Step 5: ruff + commit**

```bash
uv run ruff check .
git add app/ontology/schema.py app/ontology/extractor.py tests/test_extract_modality_nguong.py
git commit -m "feat(ontology): ActorCU carries deterministic modality and thresholds"
```

---

### Task 4: Kiểm corpus + sinh fixture + trích CU targeted (chạy thật, có LLM)

**Files:**
- Không sửa code (trừ khi Step 1 lộ thiếu — khi đó DỪNG, hỏi chủ repo).
- Sinh: `data/fixtures/*.txt` mới, `eval/ontology/pred.jsonl` + `premise.jsonl` +
  `khainiem.jsonl` (ghi đè bằng bản schema mới).

**Interfaces:**
- Consumes: CLI `python -m app.ontology --from-html ... --dieu ...` và `--batch` (có sẵn,
  xem `app/ontology/__main__.py:3-11`).
- Produces: `eval/ontology/pred.jsonl` trong đó actor-CU có `modality` + `nguong` — đầu
  vào của Task 8.

- [ ] **Step 1: Kiểm giả định corpus (chỉ đọc)** — NĐ52 và TT18 có trong LanceDB không:

```powershell
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH='.'
uv run python -c "
from app.knowledge.retrieval import search_in_docs
for q, ids in [('phương tiện thanh toán', ['ND52-2024']), ('đại lý thanh toán', ['TT18-2024'])]:
    hits = search_in_docs(q, ids, top_k=2)
    print(ids[0], '->', len(hits), 'chunk', [h['id'] for h in hits])
"
```

Expected: mỗi văn bản ≥1 chunk. Nếu 0 chunk cho văn bản nào → **DỪNG task, báo chủ repo**
(re-ingest là ghi cloud, cần phê duyệt) — các task 5-7 vẫn làm tiếp được, Task 11+ thì chưa.
Ghi kết quả kiểm (số chunk từng văn bản) vào message commit của Step 4.

- [ ] **Step 2: Sinh fixture cho các Điều được pháp lý viện dẫn** (chưa gọi LLM):

```powershell
uv run python -m app.ontology --from-html data/raw/ND52-2024.html --dieu 3
uv run python -m app.ontology --from-html data/raw/TT18-2024.html --dieu 3
uv run python -m app.ontology --from-html data/raw/TT15-2024.html --dieu 3
```

(Danh sách Điều chốt theo `gold.jsonl` sau Task 7 — nếu comment trỏ Điều khác thì sinh
thêm đúng Điều đó. TT40 Điều 25 đã có fixture từ trước.) Expected: mỗi lệnh in cây
`Điều N …` và ghi `data/fixtures/<stem>-dieuN.txt`.

- [ ] **Step 3: Trích lại toàn bộ fixture với schema mới** (GỌI LLM — cần GEMINI_API_KEY;
  ~2 lượt/khoản, tổng ước < 100 lượt):

```powershell
uv run python -m app.ontology --batch data/fixtures --out eval/ontology/pred.jsonl
```

Expected: dòng cuối `[ontology] Đã ghi eval/ontology/pred.jsonl — N CU (M meta_cu), K có lỗi cứng`
với N ≥ 49 (12 Điều cũ + Điều mới). Đọc lướt stdout: các cảnh báo `tinh_thai_kho:` /
`nguong_bo_sot:` chính là "ca lạ" — GHI LẠI danh sách để báo chủ repo, không tự xử.

- [ ] **Step 4: Kiểm nhanh sản phẩm + commit** (JSONL trong `eval/ontology/` là artefact
  đã track từ trước — commit được, KHÔNG chứa dữ liệu hợp đồng):

```powershell
uv run python -c "
import json, collections
rows = [json.loads(l) for l in open('eval/ontology/pred.jsonl', encoding='utf-8')]
actor = [r for r in rows if r['type'] == 'actor_cu']
print(len(rows), 'CU |', collections.Counter(r['modality'] for r in actor))
print('có nguong:', sum(1 for r in actor if r['nguong']))
"
```

Expected: phân bố modality không dồn hết vào `khong_ro` (nếu 100% `khong_ro` → hook Task 3
không chạy — quay lại kiểm). Sau đó:

```bash
uv run pytest -q; uv run ruff check .
git add data/fixtures eval/ontology/pred.jsonl eval/ontology/premise.jsonl eval/ontology/khainiem.jsonl
git commit -m "data(ontology): re-extract CUs with modality/thresholds, add cited articles"
```

---

### Task 5: Đọc docx — đoạn văn + comment + neo (`docx_doc.py`)

**Files:**
- Create: `app/compliance/__init__.py` (rỗng), `app/compliance/docx_doc.py`
- Test: `tests/test_compliance_docx.py` (mới)

**Interfaces:**
- Produces:

```python
class DoanVan(BaseModel):
    idx: int                 # thứ tự đoạn trong body
    text: str
    comment_ids: list[str]   # comment đang neo TẠI đoạn này

class BinhLuan(BaseModel):
    id: str
    author: str
    date: str | None
    text: str

def doc_docx(path: Path) -> tuple[list[DoanVan], list[BinhLuan]]
```

  Task 6 dùng `DoanVan` để cắt điều; Task 7 dùng cả hai để dựng gold.

- [ ] **Step 1: Viết test fail** — fixture docx TỰ DỰNG bằng zipfile (không chữ hợp đồng thật):

```python
"""Đọc docx bằng stdlib: đoạn văn, comment, và đoạn nào neo comment nào."""
import zipfile

import pytest

from app.compliance.docx_doc import doc_docx

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

_DOCUMENT = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="{_W}"><w:body>
<w:p><w:r><w:t>Điều 1. Phạm vi</w:t></w:r></w:p>
<w:p><w:commentRangeStart w:id="7"/><w:r><w:t>Bên B thanh toán trong 3 ngày.</w:t></w:r>
<w:commentRangeEnd w:id="7"/></w:p>
<w:p><w:r><w:t>Điều 2. Phí</w:t></w:r></w:p>
</w:body></w:document>"""

_COMMENTS = f"""<?xml version="1.0" encoding="UTF-8"?>
<w:comments xmlns:w="{_W}">
<w:comment w:id="7" w:author="PPC" w:date="2026-05-12T10:40:00Z">
<w:p><w:r><w:t>Nên là ngày làm việc.</w:t></w:r></w:p></w:comment>
</w:comments>"""

_CONTENT_TYPES = (
    '<?xml version="1.0"?><Types '
    'xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>'
)


@pytest.fixture
def docx(tmp_path):
    p = tmp_path / "mini.docx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("word/document.xml", _DOCUMENT)
        z.writestr("word/comments.xml", _COMMENTS)
    return p


def test_doc_du_doan_va_comment(docx):
    doan, binh_luan = doc_docx(docx)
    assert [d.text for d in doan] == [
        "Điều 1. Phạm vi", "Bên B thanh toán trong 3 ngày.", "Điều 2. Phí",
    ]
    assert doan[1].comment_ids == ["7"] and doan[0].comment_ids == []
    assert binh_luan[0].author == "PPC"
    assert binh_luan[0].text == "Nên là ngày làm việc."


def test_docx_khong_comment(tmp_path):
    p = tmp_path / "trong.docx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("word/document.xml", _DOCUMENT)
    doan, binh_luan = doc_docx(p)
    assert len(doan) == 3 and binh_luan == []
```

- [ ] **Step 2: Chạy để thấy fail** — `ModuleNotFoundError: app.compliance`.

- [ ] **Step 3: Cài đặt** (`app/compliance/docx_doc.py`):

```python
"""Đọc .docx bằng stdlib — đoạn văn, comment pháp lý, và neo comment→đoạn.

Chỉ zipfile + xml.etree, không python-docx: nhu cầu là text + comment anchor,
thêm thư viện cho việc regex 2 tag là vi phạm ladder.
Neo ở MỨC ĐOẠN VĂN: commentRangeStart/End có thể cắt giữa run, nhưng gold chỉ cần
biết comment thuộc đoạn nào → điều nào của hợp đồng.
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from pydantic import BaseModel

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class DoanVan(BaseModel):
    idx: int
    text: str
    comment_ids: list[str] = []


class BinhLuan(BaseModel):
    id: str
    author: str
    date: str | None = None
    text: str


def _text_cua(el: ET.Element) -> str:
    return " ".join("".join(t.itertext()) for t in el.iter(f"{_W}t")).strip()


def doc_docx(path: Path) -> tuple[list[DoanVan], list[BinhLuan]]:
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        binh_luan: list[BinhLuan] = []
        if "word/comments.xml" in z.namelist():
            croot = ET.fromstring(z.read("word/comments.xml"))
            for c in croot.findall(f"{_W}comment"):
                binh_luan.append(BinhLuan(
                    id=c.get(f"{_W}id") or "",
                    author=c.get(f"{_W}author") or "",
                    date=c.get(f"{_W}date"),
                    text=_text_cua(c),
                ))
    doan: list[DoanVan] = []
    dang_mo: set[str] = set()  # comment range mở vắt qua nhiều đoạn
    for p in root.iter(f"{_W}p"):
        ids = set(dang_mo)
        for el in p.iter():
            if el.tag == f"{_W}commentRangeStart":
                cid = el.get(f"{_W}id") or ""
                ids.add(cid)
                dang_mo.add(cid)
            elif el.tag == f"{_W}commentRangeEnd":
                dang_mo.discard(el.get(f"{_W}id") or "")
        text = _text_cua(p)
        if text:
            doan.append(DoanVan(idx=len(doan), text=text, comment_ids=sorted(ids)))
    return doan, binh_luan
```

- [ ] **Step 4: PASS + chạy thử trên file thật** (kiểm mắt, không ghi gì):

```powershell
uv run python -c "
from pathlib import Path
from app.compliance.docx_doc import doc_docx
for f in Path('docs/compliance').glob('*.docx'):
    doan, bl = doc_docx(f)
    neo = sum(1 for d in doan if d.comment_ids)
    print(f.name, '->', len(doan), 'đoạn,', len(bl), 'comment,', neo, 'đoạn có neo')
"
```

Expected: 46 và 50 comment (đã đo trong brainstorm); số đoạn có neo > 0.

- [ ] **Step 5: ruff + commit**

```bash
git add app/compliance/__init__.py app/compliance/docx_doc.py tests/test_compliance_docx.py
git commit -m "feat(compliance): stdlib docx reader with comment anchors"
```

---

### Task 6: Parse hợp đồng thành điều (`hop_dong.py`)

**Files:**
- Create: `app/compliance/hop_dong.py`
- Test: `tests/test_compliance_hop_dong.py`

**Interfaces:**
- Consumes: `doc_docx`, `DoanVan` (Task 5); `CorpusDocument`, `Article` từ
  `app.core.schemas` (Article có `article: str`, `text: str` — :132-136).
- Produces:

```python
class DieuHopDong(BaseModel):
    so: str          # "1"
    tieu_de: str     # "Phạm vi"
    text: str        # toàn văn điều (gồm dòng tiêu đề)
    doan: tuple[int, int]  # [start, end) chỉ số đoạn văn trong docx

class HopDong(BaseModel):
    ten: str         # tên file gốc, làm doc_id đường cũ
    dieu: list[DieuHopDong]

def parse_hop_dong(path: Path) -> HopDong
def to_corpus_document(hd: HopDong) -> CorpusDocument   # chạy đường cũ run_review
def dieu_chua_doan(hd: HopDong, idx: int) -> DieuHopDong | None  # Task 7 map comment→điều
```

- [ ] **Step 1: Test fail** — dùng lại fixture builder của Task 5 (đưa `_mini_docx(tmp_path,
  paragraphs)` thành helper trong test file này, tự dựng docx với các đoạn):

```python
"""Cắt hợp đồng docx thành điều — nhận 'Điều N' lẫn 'ĐIỀU N'."""
import zipfile

from app.compliance.hop_dong import dieu_chua_doan, parse_hop_dong, to_corpus_document

_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_CONTENT_TYPES = (
    '<?xml version="1.0"?><Types '
    'xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>'
)


def _mini_docx(tmp_path, paragraphs):
    body = "".join(f"<w:p><w:r><w:t>{t}</w:t></w:r></w:p>" for t in paragraphs)
    doc = (f'<?xml version="1.0"?><w:document xmlns:w="{_W}">'
           f"<w:body>{body}</w:body></w:document>")
    p = tmp_path / "hd.docx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("word/document.xml", doc)
    return p


def test_cat_dieu(tmp_path):
    p = _mini_docx(tmp_path, [
        "HỢP ĐỒNG DỊCH VỤ", "Điều 1. Phạm vi", "Nội dung phạm vi.",
        "ĐIỀU 2: Phí dịch vụ", "Mức phí do hai bên thỏa thuận.",
    ])
    hd = parse_hop_dong(p)
    assert [d.so for d in hd.dieu] == ["1", "2"]
    assert hd.dieu[0].tieu_de == "Phạm vi"
    assert "Nội dung phạm vi." in hd.dieu[0].text
    assert hd.dieu[1].doan == (3, 5)


def test_map_doan_sang_dieu(tmp_path):
    p = _mini_docx(tmp_path, ["Điều 1. A", "thân điều 1", "Điều 2. B", "thân điều 2"])
    hd = parse_hop_dong(p)
    assert dieu_chua_doan(hd, 1).so == "1"
    assert dieu_chua_doan(hd, 3).so == "2"


def test_to_corpus_document(tmp_path):
    p = _mini_docx(tmp_path, ["Điều 1. A", "thân"])
    doc = to_corpus_document(parse_hop_dong(p))
    assert doc.articles[0].article == "Điều 1"
    assert "thân" in doc.articles[0].text
```

- [ ] **Step 2: Chạy để thấy fail** — ImportError.

- [ ] **Step 3: Cài đặt**

```python
"""Cắt hợp đồng docx thành điều — đầu vào runtime của pipeline GraphCompliance.

Tách khỏi phần gold (eval/compliance/lam_gold.py): cắm hợp đồng mới không kéo
theo phần nhãn. Đề mục thấy trong 2 hợp đồng mẫu: "Điều N." / "ĐIỀU N:".
"""
from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel

from app.compliance.docx_doc import doc_docx
from app.core.schemas import Article, CorpusDocument

_DIEU_RE = re.compile(r"^\s*(?:Điều|ĐIỀU)\s+(\d+)\s*[.:]?\s*(.*)$")


class DieuHopDong(BaseModel):
    so: str
    tieu_de: str
    text: str
    doan: tuple[int, int]


class HopDong(BaseModel):
    ten: str
    dieu: list[DieuHopDong]


def parse_hop_dong(path: Path) -> HopDong:
    doan, _ = doc_docx(path)
    moc: list[tuple[int, str, str]] = []  # (idx đoạn, số, tiêu đề)
    for d in doan:
        m = _DIEU_RE.match(d.text)
        if m:
            moc.append((d.idx, m.group(1), m.group(2).strip()))
    ra: list[DieuHopDong] = []
    for i, (idx, so, tieu_de) in enumerate(moc):
        end = moc[i + 1][0] if i + 1 < len(moc) else len(doan)
        text = "\n".join(d.text for d in doan[idx:end])
        ra.append(DieuHopDong(so=so, tieu_de=tieu_de, text=text, doan=(idx, end)))
    return HopDong(ten=path.stem, dieu=ra)


def dieu_chua_doan(hd: HopDong, idx: int) -> DieuHopDong | None:
    return next((d for d in hd.dieu if d.doan[0] <= idx < d.doan[1]), None)


def to_corpus_document(hd: HopDong) -> CorpusDocument:
    """Cầu sang đường cũ: run_review nhận CorpusDocument."""
    return CorpusDocument(
        doc_id=hd.ten,
        title=hd.ten,
        articles=[
            Article(article=f"Điều {d.so}", text=d.text) for d in hd.dieu
        ],
    )
```

Lưu ý: nếu `CorpusDocument` đòi field bắt buộc khác (chạy test sẽ lộ) thì bổ sung đúng
field tối thiểu pydantic yêu cầu, không bịa giá trị có nghĩa.

- [ ] **Step 4: PASS cả file test + toàn suite.**

- [ ] **Step 5: ruff + commit**

```bash
git add app/compliance/hop_dong.py tests/test_compliance_hop_dong.py
git commit -m "feat(compliance): split contract docx into articles"
```

---

### Task 7: `.gitignore` + script bóc nhãn vàng (`lam_gold.py`)

**Files:**
- Modify: `.gitignore` (thêm 2 dòng)
- Create: `eval/compliance/lam_gold.py`
- Test: `tests/test_compliance_gold.py`

**Interfaces:**
- Consumes: `doc_docx`, `dieu_chua_doan`, `parse_hop_dong` (Task 5-6);
  `parse_citations`, `to_node_ids` (`app/ontology/citation.py` — `CitationRef` có
  `van_ban`, `dieu`, `khoan`).
- Produces: `eval/compliance/gold.jsonl` (GITIGNORE — không commit), mỗi dòng:

```json
{"file": "HD_x.docx", "comment_id": "7", "author": "…", "dieu_hop_dong": "1",
 "anchor_text": "…", "comment_text": "…", "refs": ["52/2024/NĐ-CP#than/dieu_3"],
 "van_ban": ["52/2024/NĐ-CP"], "loai": "phap_ly", "trong_corpus": true}
```

  Hàm tái dụng được (test import từ script): `chuan_hoa(text) -> str`,
  `loai_so_bo(refs, text) -> str`, `boc_gold(docx_path, so_hieu_corpus) -> list[dict]`.

- [ ] **Step 1: `.gitignore` TRƯỚC TIÊN** — thêm 2 dòng (đặt cạnh các dòng ignore dữ liệu
  hiện có, xem file để chọn chỗ):

```
docs/compliance/
eval/compliance/*.jsonl
```

Kiểm: `git check-ignore docs/compliance/HD_DVThuHoCoLK.docx` in ra đường dẫn (= đã chặn).
Commit riêng ngay: `git add .gitignore; git commit -m "chore: never commit real contract data"`.

- [ ] **Step 2: Test fail** cho phần thuần (chuẩn hoá + phân loại + refs):

```python
"""Bóc nhãn vàng từ comment pháp lý trong docx."""
from eval.compliance.lam_gold import chuan_hoa, loai_so_bo


def test_chuan_hoa_van_noi():
    # Đo thật trong brainstorm: không chuẩn hoá thì parse_citations bắt 0/95 comment
    assert "Nghị định 52/2024/NĐ-CP" in chuan_hoa("theo NĐ 52/2024/NĐ-CP")
    assert "Thông tư 18/2024/TT-NHNN" in chuan_hoa("khoản 24 điều 3 TT 18/2024/TT-NHNN")
    assert "Điều 3" in chuan_hoa("khoản 24 điều 3")
    assert "TT-NHNN" in chuan_hoa("TT 64/2024/TT_NHNN")


def test_loai_so_bo():
    assert loai_so_bo(["52/2024/NĐ-CP#than/dieu_3"], "bổ sung theo NĐ 52") == "phap_ly"
    assert loai_so_bo([], "đối chiếu mẫu HĐ khung do PPC ban hành") == "noi_bo"
    assert loai_so_bo([], "Đơn vị làm rõ nội dung này") == "lam_ro"
    assert loai_so_bo([], "Bỏ từ Thẻ để tránh nhầm lẫn") == "van_phong"
```

(`eval/` chưa chắc là package — nếu import fail vì thiếu `__init__.py`, thêm
`eval/__init__.py` + `eval/compliance/__init__.py` rỗng, cùng cách các test
`eval/ontology` hiện có đang làm — xem `tests/` hiện tại để theo đúng nếp.)

- [ ] **Step 3: Cài đặt** (`eval/compliance/lam_gold.py`):

```python
"""Bóc comment pháp lý từ docx thành gold.jsonl — nhãn người đầu tiên của dự án.

Chạy:  uv run python eval/compliance/lam_gold.py
Ghi:   eval/compliance/gold.jsonl  (GITIGNORE — chứa nguyên văn hợp đồng thật)

Lớp `chuan_hoa` chỉ sống ở đây: comment là văn nói ("NĐ 52", "điều 3"),
citation.py lõi đo ni cho văn luật chuẩn — không nới lõi.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.compliance.docx_doc import doc_docx
from app.compliance.hop_dong import dieu_chua_doan, parse_hop_dong
from app.ontology.citation import parse_citations, to_node_ids

#: Văn bản có mặt trong corpus LanceDB — đối chiếu Task 4 Step 1. Cập nhật tay khi corpus đổi.
SO_HIEU_CORPUS = {"52/2024/NĐ-CP", "40/2024/TT-NHNN", "15/2024/TT-NHNN", "18/2024/TT-NHNN"}

_NOI_BO_RE = re.compile(r"NVQĐ|HĐ khung|PPC ban hành|quy định nội bộ", re.I)
_LAM_RO_RE = re.compile(r"làm rõ|xác nhận|lưu ý|xin ý kiến", re.I)


def chuan_hoa(text: str) -> str:
    text = re.sub(r"\bNĐ\s+(?=\d)", "Nghị định ", text)
    text = re.sub(r"\bTT\s+(?=\d)", "Thông tư ", text)
    text = text.replace("TT_NHNN", "TT-NHNN")
    text = re.sub(r"\bđiều\b", "Điều", text)
    return text


def loai_so_bo(refs: list[str], text: str) -> str:
    if refs:
        return "phap_ly"
    if _NOI_BO_RE.search(text):
        return "noi_bo"
    if _LAM_RO_RE.search(text):
        return "lam_ro"
    return "van_phong"


def _refs_cua(comment_text: str) -> tuple[list[str], list[str]]:
    """→ (khoá node, số hiệu văn bản). Chỉ nhận ref có van_ban tường minh —
    comment không có ngữ cảnh 'Điều này' để suy."""
    khoa, vb = [], []
    for r in parse_citations(chuan_hoa(comment_text)):
        if not r.van_ban:
            continue
        vb.append(r.van_ban)
        khoa += to_node_ids(r, ctx_so_hieu=r.van_ban)
    return sorted(set(khoa)), sorted(set(vb))


def boc_gold(docx_path: Path, so_hieu_corpus: set[str] = SO_HIEU_CORPUS) -> list[dict]:
    doan, binh_luan = doc_docx(docx_path)
    hd = parse_hop_dong(docx_path)
    neo: dict[str, list[int]] = {}
    for d in doan:
        for cid in d.comment_ids:
            neo.setdefault(cid, []).append(d.idx)
    rows = []
    for bl in binh_luan:
        if not bl.text:
            continue
        idxs = neo.get(bl.id, [])
        dieu = dieu_chua_doan(hd, idxs[0]) if idxs else None
        refs, vb = _refs_cua(bl.text)
        rows.append({
            "file": docx_path.name,
            "comment_id": bl.id,
            "author": bl.author,
            "dieu_hop_dong": dieu.so if dieu else None,
            "anchor_text": " ".join(doan[i].text for i in idxs)[:500],
            "comment_text": bl.text,
            "refs": refs,
            "van_ban": vb,
            "loai": loai_so_bo(refs, bl.text),
            "trong_corpus": bool(vb) and all(v in so_hieu_corpus for v in vb),
        })
    return rows


if __name__ == "__main__":
    out = Path("eval/compliance/gold.jsonl")
    rows: list[dict] = []
    for f in sorted(Path("docs/compliance").glob("*.docx")):
        rows += boc_gold(f)
    out.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    n = {t: sum(1 for r in rows if r["loai"] == t) for t in
         ("phap_ly", "noi_bo", "lam_ro", "van_phong")}
    print(f"[gold] {out}: {len(rows)} comment — {n}")
```

- [ ] **Step 4: PASS test + chạy thật:**

```powershell
uv run python eval/compliance/lam_gold.py
```

Expected: `~95 comment`, nhóm `phap_ly` ≥ 6 (các comment có viện dẫn đo được trong
brainstorm). `git status` KHÔNG hiện `gold.jsonl` (đã ignore từ Step 1).

- [ ] **Step 5: TRÌNH CHỦ REPO DUYỆT NHÃN** — in bảng `loai` cho 95 dòng (id + 80 ký tự
  đầu comment + loai sơ bộ), chủ repo sửa dòng nào sai → sửa trực tiếp `gold.jsonl`
  (file local). Đây là cổng人 — KHÔNG tự đi tiếp khi chưa có phản hồi.

- [ ] **Step 6: ruff + commit** (chỉ script + test — KHÔNG jsonl):

```bash
git add eval/compliance/lam_gold.py tests/test_compliance_gold.py
git commit -m "feat(eval): extract first human gold labels from lawyer docx comments"
```

---

### Task 8: Policy Graph in-memory (`policy_graph.py`)

**Files:**
- Create: `app/compliance/policy_graph.py`
- Test: `tests/test_compliance_policy_graph.py`

**Interfaces:**
- Consumes: `ActorCU`, `MetaCU`, `PremiseRecord`, `KhaiNiem` (`app/ontology/schema.py`);
  JSONL do Task 4 sinh (mỗi dòng có key thừa `fixture` — bỏ qua bằng
  `model_validate` với `extra` mặc định của pydantic là ignore? — KHÔNG: kiểm config model;
  nếu strict thì `pop("fixture")` trước khi validate).
- Produces:

```python
class PolicyGraph:
    cu: dict[str, ActorCU | MetaCU]        # theo id, CHỈ bản ghi ok (errors rỗng)
    khai_niem: list[KhaiNiem]
    premise: list[PremiseRecord]

    @classmethod
    def load(cls, thu_muc: Path = Path("eval/ontology")) -> "PolicyGraph"
    def cu_cua_dieu(self, so_hieu: str, so_dieu: str) -> list[ActorCU | MetaCU]
    def lang_gieng(self, cu_id: str) -> list[ActorCU | MetaCU]   # REFERS_TO 2 chiều, 1 hop
    def closure(self, cu_id: str, sau: int = 2) -> list[ActorCU | MetaCU]
    def mien_tru_trong(self, ids: list[str]) -> list[ActorCU]    # modality == "mien_tru"

def dieu_prefix(khoa: str) -> str   # "52/…#than/dieu_22#khoan_2" → "52/…#than/dieu_22"
```

- [ ] **Step 1: Test fail** — dựng JSONL nhỏ trong `tmp_path` bằng dict tối thiểu hợp lệ
  (dựa đúng schema: ActorCU cần `id`, `subject`, `action` với `GroundedField{text, grounding:
  {units, char_span, status}}`):

```python
"""Policy Graph in-memory: nạp JSONL, cạnh REFERS_TO, closure."""
import json

import pytest

from app.compliance.policy_graph import PolicyGraph, dieu_prefix


def _field(text="phải báo cáo"):
    return {"text": text, "label": "", "issues": [],
            "grounding": {"units": [1], "char_span": [0, len(text)], "status": "unit",
                          "quote": ""}}


def _actor(id, refs=(), modality="nghia_vu", errors=()):
    return {"type": "actor_cu", "id": id, "references": list(refs),
            "references_hep_hon": False, "warnings": [], "errors": list(errors),
            "subject": _field("Tổ chức"), "subject_source": "explicit",
            "action": _field(), "logic": "all", "conditions": [],
            "modality": modality, "nguong": [], "fixture": "x.txt"}


@pytest.fixture
def pg(tmp_path):
    rows = [
        _actor("A/1#than/dieu_5#khoan_1", refs=["A/1#than/dieu_6"]),
        _actor("A/1#than/dieu_6#khoan_1", modality="mien_tru"),
        _actor("A/1#than/dieu_7#khoan_1", errors=["bịa số"]),  # phải bị loại
    ]
    (tmp_path / "pred.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    (tmp_path / "premise.jsonl").write_text("", encoding="utf-8")
    (tmp_path / "khainiem.jsonl").write_text("", encoding="utf-8")
    return PolicyGraph.load(tmp_path)


def test_loai_ban_ghi_loi(pg):
    assert "A/1#than/dieu_7#khoan_1" not in pg.cu


def test_cu_cua_dieu(pg):
    assert [c.id for c in pg.cu_cua_dieu("A/1", "5")] == ["A/1#than/dieu_5#khoan_1"]


def test_lang_gieng_hai_chieu(pg):
    # 5→6 khai trong references; từ 6 nhìn ngược cũng phải thấy 5
    assert [c.id for c in pg.lang_gieng("A/1#than/dieu_6#khoan_1")] == [
        "A/1#than/dieu_5#khoan_1"]


def test_closure_va_mien_tru(pg):
    ids = [c.id for c in pg.closure("A/1#than/dieu_5#khoan_1")]
    assert "A/1#than/dieu_6#khoan_1" in ids
    assert [c.id for c in pg.mien_tru_trong(ids)] == ["A/1#than/dieu_6#khoan_1"]


def test_dieu_prefix():
    assert dieu_prefix("A/1#than/dieu_22#khoan_2#diem_b") == "A/1#than/dieu_22"
```

- [ ] **Step 2: fail** — ImportError.

- [ ] **Step 3: Cài đặt** — điểm cần đúng: (1) cạnh nối theo **tiền tố Điều** (references
  có thể trỏ tới `#khoan_x#diem_y`, CU id là mức khoản — quy cả hai về `dieu_prefix` rồi
  nối CU nào nằm trong prefix đó); (2) đọc JSONL bỏ dòng rỗng; (3) `pop("fixture", None)`
  trước validate; (4) bản ghi `errors` không rỗng thì bỏ (kỷ luật `GroundedUnit.ok`,
  schema.py:301-307).

```python
"""Policy Graph in-memory từ eval/ontology/*.jsonl — 49+ node thì dict thuần là đủ.

Chuyển Neo4j khi độ phủ lớn (quyết định spec 11/08). Bản ghi có lỗi cứng
(errors ≠ []) bị loại ngay từ load — downstream không bao giờ thấy chúng.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import TypeAdapter

from app.ontology.schema import ActorCU, ComplianceUnit, KhaiNiem, MetaCU, PremiseRecord

_CU_ADAPTER: TypeAdapter = TypeAdapter(ComplianceUnit)
_DIEU_RE = re.compile(r"^(.+?#than/dieu_[0-9a-z]+)")


def dieu_prefix(khoa: str) -> str:
    m = _DIEU_RE.match(khoa)
    return m.group(1) if m else khoa


def _doc_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    ra = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            d.pop("fixture", None)
            ra.append(d)
    return ra


class PolicyGraph:
    def __init__(self, cu, premise, khai_niem):
        self.cu: dict[str, ComplianceUnit] = {c.id: c for c in cu}
        self.premise: list[PremiseRecord] = premise
        self.khai_niem: list[KhaiNiem] = khai_niem
        # kề nhau theo tiền tố Điều, hai chiều
        self._theo_dieu: dict[str, list[str]] = {}
        for cid in self.cu:
            self._theo_dieu.setdefault(dieu_prefix(cid), []).append(cid)
        self._ke: dict[str, set[str]] = {cid: set() for cid in self.cu}
        for cid, c in self.cu.items():
            for ref in c.references:
                for dich in self._theo_dieu.get(dieu_prefix(ref), []):
                    if dich != cid:
                        self._ke[cid].add(dich)
                        self._ke[dich].add(cid)

    @classmethod
    def load(cls, thu_muc: Path = Path("eval/ontology")) -> "PolicyGraph":
        cu = [_CU_ADAPTER.validate_python(d) for d in _doc_jsonl(thu_muc / "pred.jsonl")]
        cu = [c for c in cu if c.ok]
        premise = [PremiseRecord.model_validate(d)
                   for d in _doc_jsonl(thu_muc / "premise.jsonl")]
        kn = [KhaiNiem.model_validate(d) for d in _doc_jsonl(thu_muc / "khainiem.jsonl")]
        return cls(cu, premise, kn)

    def cu_cua_dieu(self, so_hieu: str, so_dieu: str):
        return [self.cu[i] for i in self._theo_dieu.get(
            f"{so_hieu}#than/dieu_{so_dieu}", [])]

    def lang_gieng(self, cu_id: str):
        return [self.cu[i] for i in sorted(self._ke.get(cu_id, ()))]

    def closure(self, cu_id: str, sau: int = 2):
        tham: set[str] = {cu_id}
        bien = {cu_id}
        for _ in range(sau):
            bien = {j for i in bien for j in self._ke.get(i, ())} - tham
            tham |= bien
        return [self.cu[i] for i in sorted(tham - {cu_id})]

    def mien_tru_trong(self, ids):
        return [c for i in ids if isinstance(c := self.cu.get(i), ActorCU)
                and c.modality == "mien_tru"]
```

(Nếu `PremiseRecord`/`KhaiNiem` validate fail vì key thừa khác — xử cùng cách
`pop`; chạy `PolicyGraph.load()` trên `eval/ontology` thật ở Step 4 để chắc.)

- [ ] **Step 4: PASS test + nạp thử dữ liệu thật:**

```powershell
uv run python -c "
from app.compliance.policy_graph import PolicyGraph
pg = PolicyGraph.load()
print(len(pg.cu), 'CU |', len(pg.premise), 'premise |', len(pg.khai_niem), 'khái niệm')
"
```

Expected: số CU = số dòng ok trong pred.jsonl Task 4 (in ra để đối chiếu, không đoán).

- [ ] **Step 5: ruff + commit**

```bash
git add app/compliance/policy_graph.py tests/test_compliance_policy_graph.py
git commit -m "feat(compliance): in-memory policy graph with REFERS_TO closure"
```

---

### Task 9: ER-triple từ điều hợp đồng (`er_triples.py`)

**Files:**
- Create: `app/compliance/er_triples.py`
- Test: `tests/test_compliance_er_triples.py`

**Interfaces:**
- Consumes: `chat_json(prompt, *, system=..., temperature=0.0) -> dict` (`app.core.llm`).
- Produces:

```python
class Triple(BaseModel):
    chu_the: str    # phải xuất hiện nguyên văn (không phân biệt hoa thường) trong text
    hanh_vi: str
    doi_tuong: str

def trich_triples(text: str) -> tuple[list[Triple], list[str]]  # (triples, cảnh báo)
```

- [ ] **Step 1: Test fail** (fake `chat_json` theo mẫu `tests/test_conflict.py:43`):

```python
"""ER-triple S–A–O từ điều hợp đồng; entity phải nằm nguyên văn trong text."""
from app.compliance import er_triples


def test_giu_triple_hop_le_bo_triple_bia(monkeypatch):
    monkeypatch.setattr(er_triples, "chat_json", lambda *a, **k: {"triples": [
        {"chu_the": "Bên B", "hanh_vi": "thanh toán", "doi_tuong": "phí dịch vụ"},
        {"chu_the": "Ngân hàng Nhà nước", "hanh_vi": "cấp", "doi_tuong": "Giấy phép"},
    ]})
    triples, canh_bao = er_triples.trich_triples(
        "Bên B thanh toán phí dịch vụ trong 05 ngày.")
    assert [t.chu_the for t in triples] == ["Bên B"]  # NHNN không có trong text → bỏ
    assert len(canh_bao) == 1 and "không nằm trong" in canh_bao[0]


def test_json_hong_tra_rong(monkeypatch):
    monkeypatch.setattr(er_triples, "chat_json", lambda *a, **k: {"sai": 1})
    triples, canh_bao = er_triples.trich_triples("Bên A cung cấp dịch vụ.")
    assert triples == [] and canh_bao == []
```

- [ ] **Step 2: fail.** — ImportError.

- [ ] **Step 3: Cài đặt**

```python
"""Trích (chủ thể, hành vi, đối tượng) từ MỘT điều hợp đồng — LLM, temp 0.

Kỷ luật chống bịa như extractor: chủ thể/đối tượng phải nằm NGUYÊN VĂN trong
text (so không phân biệt hoa thường); không thì bỏ triple + cảnh báo. `hanh_vi`
được diễn giải tự do (động từ thường bị biến đổi ngữ pháp) — không kiểm.
"""
from __future__ import annotations

from pydantic import BaseModel

from app.core.llm import chat_json

_SYSTEM = (
    "Trích các bộ ba (chủ thể, hành vi, đối tượng) từ một điều khoản hợp đồng "
    "tiếng Việt. Chủ thể và đối tượng phải CHÉP NGUYÊN VĂN cụm từ trong điều khoản, "
    "không viết lại. Chỉ trả JSON: "
    '{"triples": [{"chu_the": "...", "hanh_vi": "...", "doi_tuong": "..."}]}'
)


class Triple(BaseModel):
    chu_the: str
    hanh_vi: str
    doi_tuong: str


def trich_triples(text: str) -> tuple[list[Triple], list[str]]:
    data = chat_json(f"Điều khoản:\n{text}", system=_SYSTEM, temperature=0.0)
    low = text.lower()
    ra: list[Triple] = []
    canh_bao: list[str] = []
    for raw in data.get("triples") or []:
        try:
            t = Triple.model_validate(raw)
        except Exception:  # noqa: BLE001 — JSON LLM tuỳ tiện, bỏ phần tử hỏng là đủ
            continue
        thieu = [x for x in (t.chu_the, t.doi_tuong) if x.lower() not in low]
        if thieu:
            canh_bao.append(f"bỏ triple: {thieu[0]!r} không nằm trong điều khoản")
            continue
        ra.append(t)
    return ra, canh_bao
```

- [ ] **Step 4: PASS + toàn suite.**
- [ ] **Step 5: ruff + commit**

```bash
git add app/compliance/er_triples.py tests/test_compliance_er_triples.py
git commit -m "feat(compliance): grounded SAO triple extraction for context graph"
```

---

### Task 10: Hypernym map entity → thuật ngữ luật (`hypernym.py`)

**Files:**
- Create: `app/compliance/hypernym.py`
- Test: `tests/test_compliance_hypernym.py`

**Interfaces:**
- Consumes: `PolicyGraph` (Task 8 — `khai_niem: list[KhaiNiem]` với `thuat_ngu`,
  `dinh_nghia`; `premise` với `alias` nếu có); `embed_documents(texts) -> list[list[float]]`,
  `embed_query(text) -> list[float]`, `chat_json` (`app.core.llm`).
- Produces:

```python
class DeXuat(BaseModel):
    entity: str
    hypernym: str        # thuật ngữ luật
    do_tin: float        # LLM khai, [0,1]
    manh: bool           # True = chống lưng bằng premise/khái niệm (STRONG của paper)

class TuVungLuat:
    @classmethod
    def tu_policy_graph(cls, pg, embed=embed_documents) -> "TuVungLuat"
    def ung_vien(self, entity_vec: list[float], top_m: int = 3) -> list[str]

def map_hypernym(entities: list[str], tv: TuVungLuat,
                 nguong_tin: float = 0.5) -> dict[str, DeXuat | None]
```

- [ ] **Step 1: Test fail** — fake cả embed lẫn chat_json (vector 2 chiều tự chế đủ để
  kiểm cosine):

```python
"""Hypernym mapping: cosine trên KhaiNiem + LLM xác nhận, dưới ngưỡng thì thôi."""
from app.compliance import hypernym
from app.compliance.hypernym import TuVungLuat, map_hypernym


class _PG:
    class _KN:
        def __init__(self, t):
            self.thuat_ngu = t
            self.dinh_nghia = f"định nghĩa {t}"

    khai_niem = [_KN("dịch vụ cổng thanh toán điện tử"), _KN("đại lý thanh toán")]
    premise = []


def _tv():
    # embed fake: từ đầu tiên quyết định vector
    vecs = {"dịch": [1.0, 0.0], "đại": [0.0, 1.0]}
    return TuVungLuat.tu_policy_graph(
        _PG(), embed=lambda ts: [vecs[t.split()[0]] for t in ts])


def test_map_qua_nguong(monkeypatch):
    monkeypatch.setattr(hypernym, "embed_query", lambda t: [1.0, 0.0])
    monkeypatch.setattr(hypernym, "chat_json", lambda *a, **k: {
        "hypernym": "dịch vụ cổng thanh toán điện tử", "do_tin": 0.9})
    ra = map_hypernym(["cổng thanh toán PAYX"], _tv())
    assert ra["cổng thanh toán PAYX"].hypernym == "dịch vụ cổng thanh toán điện tử"


def test_duoi_nguong_khong_ep(monkeypatch):
    monkeypatch.setattr(hypernym, "embed_query", lambda t: [1.0, 0.0])
    monkeypatch.setattr(hypernym, "chat_json", lambda *a, **k: {
        "hypernym": "dịch vụ cổng thanh toán điện tử", "do_tin": 0.2})
    assert map_hypernym(["thuật ngữ lạ"], _tv())["thuật ngữ lạ"] is None


def test_hypernym_ngoai_ung_vien_bi_bo(monkeypatch):
    monkeypatch.setattr(hypernym, "embed_query", lambda t: [1.0, 0.0])
    monkeypatch.setattr(hypernym, "chat_json", lambda *a, **k: {
        "hypernym": "thuật ngữ LLM bịa", "do_tin": 0.99})
    assert map_hypernym(["x"], _tv())["x"] is None
```

- [ ] **Step 2: fail.**

- [ ] **Step 3: Cài đặt**

```python
"""Map entity hợp đồng → thuật ngữ luật, dùng chính Policy Graph làm từ vựng H.

Đúng paper §3.2 (policy-guided normalization) nhưng thu nhỏ: 36 KhaiNiem + alias
premise → ~40 vector, cosine in-memory là đủ, không cần LanceDB. LLM chỉ XÁC NHẬN
trong danh sách ứng viên đóng — trả tên ngoài danh sách coi như không map.
"""
from __future__ import annotations

import math

from pydantic import BaseModel

from app.core.llm import chat_json, embed_documents, embed_query

_SYSTEM = (
    "Cho một cụm từ trong hợp đồng và các thuật ngữ pháp lý ứng viên (kèm định nghĩa). "
    "Chọn thuật ngữ bao trùm đúng cụm từ đó, hoặc trả null nếu không cái nào đúng. "
    'Chỉ trả JSON: {"hypernym": "<thuật ngữ hoặc null>", "do_tin": 0.0-1.0}'
)


class DeXuat(BaseModel):
    entity: str
    hypernym: str
    do_tin: float
    manh: bool


def _cosine(a: list[float], b: list[float]) -> float:
    tich = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return tich / (na * nb) if na and nb else 0.0


class TuVungLuat:
    def __init__(self, muc: list[tuple[str, str, bool]], vec: list[list[float]]):
        self._muc = muc  # (thuật ngữ, định nghĩa, manh)
        self._vec = vec

    @classmethod
    def tu_policy_graph(cls, pg, embed=embed_documents) -> "TuVungLuat":
        muc = [(k.thuat_ngu, k.dinh_nghia, True) for k in pg.khai_niem]
        muc += [(p.alias, "", True) for p in pg.premise if getattr(p, "alias", "")]
        vec = embed([f"{t}: {d}" if d else t for t, d, _ in muc]) if muc else []
        return cls(muc, vec)

    def ung_vien(self, entity_vec: list[float], top_m: int = 3):
        diem = sorted(
            ((_cosine(entity_vec, v), m) for v, m in zip(self._vec, self._muc)),
            key=lambda x: -x[0],
        )
        return [m for _, m in diem[:top_m]]


def map_hypernym(entities, tv: TuVungLuat, nguong_tin: float = 0.5):
    ra: dict[str, DeXuat | None] = {}
    for e in entities:
        uv = tv.ung_vien(embed_query(e))
        if not uv:
            ra[e] = None
            continue
        listing = "\n".join(f"- {t}" + (f": {d}" if d else "") for t, d, _ in uv)
        data = chat_json(
            f"Cụm từ trong hợp đồng: {e!r}\nỨng viên:\n{listing}",
            system=_SYSTEM, temperature=0.0,
        )
        ten = data.get("hypernym")
        tin = float(data.get("do_tin") or 0)
        khop = next((m for m in uv if m[0] == ten), None)
        ra[e] = (
            DeXuat(entity=e, hypernym=ten, do_tin=tin, manh=khop[2])
            if khop and tin >= nguong_tin else None
        )
    return ra
```

(`PremiseRecord.alias` — kiểm field này tồn tại bằng
`uv run python -c "from app.ontology.schema import PremiseRecord; print('alias' in PremiseRecord.model_fields)"`;
nếu không có thì bỏ dòng alias, chỉ dùng KhaiNiem.)

- [ ] **Step 4: PASS + toàn suite.**
- [ ] **Step 5: ruff + commit**

```bash
git add app/compliance/hypernym.py tests/test_compliance_hypernym.py
git commit -m "feat(compliance): policy-guided hypernym mapping over KhaiNiem"
```

---

### Task 11: Compliance Gate (`gate.py`)

**Files:**
- Create: `app/compliance/gate.py`
- Test: `tests/test_compliance_gate.py`

**Interfaces:**
- Consumes: `search_in_docs(query, doc_ids, top_k, as_of, effective_only) -> list[dict]`
  (chunk có `id="{doc_id}::{label}"`, `doc_id`, `article` như "Điều 5" hoặc
  "Điều 5, Khoản 2" — xem `app/ingestion/pipeline.py:195-218`); `chu_thich_ket_qua(chunks,
  as_of, pham_vi)` (`app.knowledge.lop_phu`); `PolicyGraph` (Task 8); `DeXuat` (Task 10);
  `MetaCU.gates: list[Gate]` (`Gate.kind/pham_vi/targets/suy_ra_duoc/phu_dinh`),
  `MetaCU.dieu_kien_cong: DieuKienCong | None` (`ngay`, `moc`).
- Produces:

```python
class PlanItem(BaseModel):
    cu: ActorCU
    ly_do: str                       # "retrieval Điều 5" | "subject khớp 'đại lý thanh toán'" | "REFERS_TO từ …"
    gate_chua_xac_quyet: bool = False

class CUPlan(BaseModel):
    items: list[PlanItem]
    ghi_chu: list[str]               # meta-CU đã chặn gì / gate nào không xác quyết được

def lap_cu_plan(text_dieu_hd: str, hypernyms: list[DeXuat], pg: PolicyGraph,
                against_ids: list[str], as_of: str,
                so_hieu_cua: dict[str, str]) -> CUPlan
# so_hieu_cua: doc_id LanceDB → số hiệu ("ND52-2024" → "52/2024/NĐ-CP"), dựng ở Task 13
# từ load_corpus (app/ingestion/pipeline.py:21) — CorpusDocument có so_hieu (schemas.py:118).
```

- [ ] **Step 1: Test fail** — fake `search_in_docs` + `chu_thich_ket_qua` trong module gate
  (monkeypatch tên đã import), PolicyGraph dựng tay như Task 8:

```python
"""Compliance Gate: retrieval → CU ứng viên → meta-CU chặn → CU plan. Tất định."""
from app.compliance import gate
from app.compliance.gate import lap_cu_plan
from tests.test_compliance_policy_graph import _actor  # dựng CU dict tối thiểu

# … dựng PolicyGraph với: actor-CU tại A/1 Điều 5; meta-CU cổng thời gian
# dieu_kien_cong(ngay="2027-01-01", moc="bat_dau") targets Điều 5 …


def test_chan_theo_moc_ngay_chua_hieu_luc(monkeypatch):
    monkeypatch.setattr(gate, "search_in_docs", lambda *a, **k: [
        {"id": "DOC-A::Điều 5", "doc_id": "DOC-A", "article": "Điều 5",
         "doc_title": "A", "text": "…", "valid_from": "", "valid_to": ""}])
    monkeypatch.setattr(gate, "chu_thich_ket_qua", lambda c, *a, **k: (c, {}))
    plan = lap_cu_plan("điều hợp đồng", [], _pg_voi_cong_thoi_gian(),
                       ["DOC-A"], as_of="2026-08-11", so_hieu_cua={"DOC-A": "A/1"})
    # mốc bắt đầu 2027 > as_of 2026 → CU Điều 5 bị chặn, ghi chú nêu lý do
    assert plan.items == []
    assert any("2027-01-01" in g for g in plan.ghi_chu)


def test_gate_khong_xac_quyet_thi_fail_open(monkeypatch):
    # meta-CU cổng lanh_tho (không đánh giá được) → CU vẫn vào plan + cờ
    ...
    assert plan.items[0].gate_chua_xac_quyet is True


def test_subject_khop_hypernym_duoc_them(monkeypatch):
    # retrieval không trả gì, nhưng subject CU chứa "đại lý thanh toán" =
    # hypernym của một entity hợp đồng → vẫn vào plan với ly_do "subject khớp…"
    ...
```

(Viết đủ 3 test với PolicyGraph dựng tay — mẫu `_actor` tái dùng từ Task 8, thêm helper
`_meta(id, gates, dieu_kien_cong)` cùng kiểu; meta-CU cần `menh_de` = `_field(...)`.)

- [ ] **Step 2: fail.**

- [ ] **Step 3: Cài đặt** — khung:

```python
"""Compliance Gate — phần TẤT ĐỊNH đứng trước judge, đúng thứ tự paper:
meta-CU đánh giá trước, actor-CU mới vào plan.

Fail-open có chủ đích: gate không xác quyết được (lanh_tho/khac/suy_ra_duoc=False)
thì GIỮ CU + cờ `gate_chua_xac_quyet` — mục tiêu POC là recall trên điểm pháp lý
đã đánh dấu, thà judge thừa còn hơn gate nuốt. Cùng triết lý fail-open của lớp
phủ (lop_phu.py:36).
"""
from __future__ import annotations

import re

from pydantic import BaseModel

from app.compliance.hypernym import DeXuat
from app.compliance.policy_graph import PolicyGraph, dieu_prefix
from app.knowledge.lop_phu import chu_thich_ket_qua
from app.knowledge.retrieval import search_in_docs
from app.ontology.schema import ActorCU, MetaCU

_SO_DIEU_RE = re.compile(r"Điều\s+(\d+[a-z]?)")
_TOP_K = 8


class PlanItem(BaseModel):
    cu: ActorCU
    ly_do: str
    gate_chua_xac_quyet: bool = False


class CUPlan(BaseModel):
    items: list[PlanItem]
    ghi_chu: list[str]
```

Thân `lap_cu_plan` theo 4 bước spec — mã phải xử đúng các nhánh:

1. `chunks = search_in_docs(text_dieu_hd, against_ids, top_k=_TOP_K, as_of=as_of,
   effective_only=True)` rồi `chunks, ct = chu_thich_ket_qua(chunks, as_of,
   pham_vi=set(against_ids))`; loại chunk `ct[id].trang_thai == "bi_bai_bo"` (mẫu
   review.py:120-134).
2. Ứng viên theo Điều: `so_hieu_cua[c["doc_id"]]` + `_SO_DIEU_RE.search(c["article"])`
   → `pg.cu_cua_dieu(...)`. Ứng viên theo subject: mọi `ActorCU` trong `pg.cu` mà
   `h.hypernym.lower() in (cu.subject.text + " " + cu.subject.label).lower()` với h trong
   hypernyms. Nở 1 hop: `pg.lang_gieng(cu.id)`. Ghi `ly_do` theo nguồn vào.
3. Meta-CU trong tập ứng viên (và meta-CU cùng Điều với actor-CU ứng viên): với mỗi
   `Gate`: `kind == "thoi_gian"` và có `dieu_kien_cong.ngay` → chặn được tất định:
   `moc == "bat_dau" and ngay > as_of` hoặc `moc == "ket_thuc" and ngay <= as_of` ⇒ mọi
   actor-CU có `dieu_prefix(id)` nằm trong `gates[].targets` (so bằng tiền tố) bị LOẠI,
   ghi chú `f"meta {m.id} chặn …: mốc {moc} {ngay}"`. `kind == "chu_the"`: nếu
   `targets` giao với hypernym set → giữ (khớp); `phu_dinh=True` và khớp → loại. Mọi
   nhánh còn lại (lanh_tho, khac, suy_ra_duoc=False, thiếu ngày) → không loại,
   `gate_chua_xac_quyet=True` cho các CU trong targets.
4. Khử trùng lặp theo `cu.id` (giữ ly_do đầu tiên), chỉ nhận `ActorCU` vào `items`
   (meta-CU không bao giờ bị judge — đúng định nghĩa).

- [ ] **Step 4: PASS 3 test + toàn suite.**
- [ ] **Step 5: ruff + commit**

```bash
git add app/compliance/gate.py tests/test_compliance_gate.py
git commit -m "feat(compliance): deterministic compliance gate producing CU plans"
```

---

### Task 12: Judge CU plan + vòng override (`judge.py`)

**Files:**
- Create: `app/compliance/judge.py`
- Test: `tests/test_compliance_judge.py`

**Interfaces:**
- Consumes: `chat_json`; `CUPlan`, `PlanItem` (Task 11); `PolicyGraph.closure`,
  `PolicyGraph.mien_tru_trong` (Task 8).
- Produces:

```python
class PhanQuyet(BaseModel):
    cu_id: str
    verdict: str          # tuan_thu | vi_pham | thieu_thong_tin | khong_ap_dung
    can_cu: str           # 1-2 câu
    quote_hop_dong: str
    quote_luat: str
    override: str | None = None   # căn cứ miễn trừ nếu verdict bị lật

def phan_dinh(text_dieu_hd: str, plan: CUPlan, pg: PolicyGraph) -> list[PhanQuyet]
```

- [ ] **Step 1: Test fail:**

```python
"""Judge CU plan: self-consistency 2+1 theo từng CU, vi_pham → thử override mien_tru."""
from app.compliance import judge as judge_mod
from app.compliance.judge import phan_dinh

# _plan_mot_cu(): CUPlan 1 item từ _actor của Task 8; _pg(): PolicyGraph có CU mien_tru
# nối REFERS_TO với CU trong plan.


def _vote(verdict):
    return {"phan_quyet": [{"cu_id": "A/1#than/dieu_5#khoan_1", "verdict": verdict,
                            "can_cu": "x", "quote_hop_dong": "", "quote_luat": ""}]}


def test_dong_thuan_hai_phieu(monkeypatch):
    calls = []
    monkeypatch.setattr(judge_mod, "chat_json",
                        lambda *a, **k: calls.append(1) or _vote("tuan_thu"))
    ra = phan_dinh("text", _plan_mot_cu(), _pg_rong())
    assert ra[0].verdict == "tuan_thu" and len(calls) == 2  # không cần phiếu 3


def test_bat_dong_lay_da_so(monkeypatch):
    votes = iter([_vote("vi_pham"), _vote("tuan_thu"), _vote("tuan_thu")])
    monkeypatch.setattr(judge_mod, "chat_json", lambda *a, **k: next(votes))
    assert phan_dinh("text", _plan_mot_cu(), _pg_rong())[0].verdict == "tuan_thu"


def test_vi_pham_co_mien_tru_thi_lat(monkeypatch):
    votes = iter([_vote("vi_pham"), _vote("vi_pham"),
                  {"ap_dung": True, "ly_do": "được miễn theo Điều 6"}])
    monkeypatch.setattr(judge_mod, "chat_json", lambda *a, **k: next(votes))
    ra = phan_dinh("text", _plan_mot_cu(), _pg_co_mien_tru())
    assert ra[0].verdict == "tuan_thu" and "Điều 6" in ra[0].override


def test_verdict_la_khong_hop_le_ve_thieu_thong_tin(monkeypatch):
    monkeypatch.setattr(judge_mod, "chat_json", lambda *a, **k: _vote("xyz"))
    assert phan_dinh("text", _plan_mot_cu(), _pg_rong())[0].verdict == "thieu_thong_tin"
```

- [ ] **Step 2: fail.**

- [ ] **Step 3: Cài đặt** — điểm cốt:

```python
_VERDICTS = {"tuan_thu", "vi_pham", "thieu_thong_tin", "khong_ap_dung"}
_SYSTEM = (
    "Bạn là chuyên gia pháp chế ngân hàng. Đối chiếu MỘT điều khoản hợp đồng với "
    "danh sách Compliance Unit (CU) trích từ luật. Với TỪNG CU trả verdict:\n"
    "- vi_pham: hợp đồng TRÁI với CU (chú ý modality: 'cam' mà hợp đồng cho làm; "
    "'chi_duoc' mà hợp đồng làm ngoài điều kiện; 'nghia_vu' mà hợp đồng gạt bỏ).\n"
    "- tuan_thu: phù hợp, hoặc hợp đồng CHẶT HƠN luật.\n"
    "- khong_ap_dung: CU không liên quan điều khoản này.\n"
    "- thieu_thong_tin: không đủ dữ kiện kết luận. CẤM suy từ im lặng.\n"
    "CU có trường 'nguong': PHẢI so trực tiếp số trong hợp đồng với số của ngưỡng "
    "(cùng đơn vị mới so; 'toi_da' nghĩa là hợp đồng vượt số đó = vi_pham).\n"
    'Chỉ trả JSON: {"phan_quyet": [{"cu_id": "...", "verdict": "...", '
    '"can_cu": "...", "quote_hop_dong": "...", "quote_luat": "..."}]}'
)
```

Prompt liệt kê từng CU: `id`, `modality`, `action.text`, `nguong` (so+don_vi+huong),
`conditions[].text` rút gọn 200 ký tự, cờ `gate_chua_xac_quyet` nếu có. Self-consistency
đúng mẫu `review.py._judge` (:77-89) nhưng đa số tính **theo từng cu_id**: 2 phiếu; tồn
tại cu_id bất đồng → phiếu 3; per-CU lấy verdict xuất hiện ≥ 2 lần, không có → `thieu_thong_tin`.
Verdict lạ → `thieu_thong_tin` (khác review.py dùng warning — ở đây "không biết" phải
khác "đạt"). Override: với mỗi `vi_pham` → `pg.mien_tru_trong([c.id for c in
pg.closure(cu_id)])`; không rỗng → 1 lượt `chat_json` với `_SYSTEM_OVERRIDE` hỏi đúng một
câu (liệt kê CU miễn trừ kèm `action.text`), JSON `{"ap_dung": bool, "ly_do": str}`;
`ap_dung=True` → verdict thành `tuan_thu`, `override=ly_do`. CU thiếu trong phiếu trả về
→ `thieu_thong_tin`, can_cu "LLM bỏ sót CU này".

- [ ] **Step 4: PASS 4 test + toàn suite.**
- [ ] **Step 5: ruff + commit**

```bash
git add app/compliance/judge.py tests/test_compliance_judge.py
git commit -m "feat(compliance): CU-plan judge with self-consistency and exemption override"
```

---

### Task 13: Báo cáo side-by-side + CLI (`report.py`, `__main__.py`)

**Files:**
- Create: `app/compliance/report.py`, `app/compliance/__main__.py`
- Test: `tests/test_compliance_report.py`

**Interfaces:**
- Consumes: mọi module Task 5-12; `run_review(internal, against_ids, as_of) ->
  ReviewResponse` (`app.reasoning.review:169`); `load_corpus`
  (`app.ingestion.pipeline:21` — trả `(list[CorpusDocument], list[Relationship])`, dùng
  dựng `so_hieu_cua = {d.doc_id: d.so_hieu}`).
- Produces:
  - `report.py`: `tinh_recall(gold_rows, phan_quyet_theo_dieu) -> dict` và
    `render_md(hd, gold_rows, cu, moi) -> str` — thuần, test được;
  - CLI: `python -m app.compliance <docx> --against ND52-2024 TT18-2024 …
    --corpus <đường dẫn corpus cho load_corpus> [--gold eval/compliance/gold.jsonl]
    [--out eval/compliance/bao_cao_<ten>.md] [--as-of YYYY-MM-DD] [--cu-dir eval/ontology]
    [--bo-duong-cu]` (cờ cuối để chạy nhanh không gọi run_review).

- [ ] **Step 1: Test fail cho phần thuần:**

```python
"""Recall trên gold phap_ly + render báo cáo 3 cột."""
from app.compliance.report import tinh_recall

_GOLD = [
    {"dieu_hop_dong": "3", "loai": "phap_ly", "trong_corpus": True,
     "van_ban": ["52/2024/NĐ-CP"], "comment_id": "13"},
    {"dieu_hop_dong": "9", "loai": "phap_ly", "trong_corpus": False,
     "van_ban": ["254/2026/NĐ-CP"], "comment_id": "8"},   # ngoài corpus → loại khỏi mẫu số
    {"dieu_hop_dong": "1", "loai": "van_phong", "trong_corpus": False,
     "van_ban": [], "comment_id": "7"},                    # không phải phap_ly → bỏ
]


def test_recall_dung_mau_so():
    # đường mới bắt được điều 3, viện dẫn đúng văn bản
    moi = {"3": [{"verdict": "vi_pham", "cu_id": "52/2024/NĐ-CP#than/dieu_3#khoan_15"}]}
    r = tinh_recall(_GOLD, moi)
    assert (r["mau_so"], r["bat_duoc"], r["ngoai_pham_vi"]) == (1, 1, 1)


def test_bat_sai_van_ban_khong_tinh():
    moi = {"3": [{"verdict": "vi_pham", "cu_id": "40/2024/TT-NHNN#than/dieu_25#khoan_1"}]}
    assert tinh_recall(_GOLD, moi)["bat_duoc"] == 0


def test_tuan_thu_khong_tinh_la_bat():
    moi = {"3": [{"verdict": "tuan_thu", "cu_id": "52/2024/NĐ-CP#than/dieu_3#khoan_15"}]}
    assert tinh_recall(_GOLD, moi)["bat_duoc"] == 0
```

- [ ] **Step 2: fail.**

- [ ] **Step 3: Cài đặt** — `tinh_recall`: mẫu số = gold `loai=="phap_ly" and trong_corpus`;
  "bắt được" = tồn tại phán quyết tại đúng `dieu_hop_dong` với `verdict in {"vi_pham",
  "thieu_thong_tin"}` và `cu_id` bắt đầu bằng một trong `van_ban` của dòng gold. Trả thêm
  `bo_sot: list[comment_id]`. `render_md`: bảng mỗi điều — cột gold (comment + loai), cột
  đường cũ (`ReviewFinding.verdict/title`), cột đường mới (từng PhanQuyet: verdict, cu_id,
  can_cu, override); cuối file khối "Recall" + khối "Ca lạ" (gom cảnh báo `nguong_bo_sot`/
  `tinh_thai_kho`/`bỏ triple` phát sinh trong lần chạy). `__main__.py`: argparse, luồng =
  parse_hop_dong → (đường cũ: `run_review(to_corpus_document(hd), against, as_of)` trừ khi
  `--bo-duong-cu`) → PolicyGraph.load(cu_dir) + TuVungLuat + so_hieu_cua từ load_corpus →
  per điều: trich_triples → map_hypernym → lap_cu_plan → phan_dinh → gom → render_md →
  `write_text(encoding="utf-8")` (file .md nằm trong `eval/compliance/` → cần thêm dòng
  `eval/compliance/*.md` vào `.gitignore` — chứa nguyên văn hợp đồng).

- [ ] **Step 4: PASS + smoke offline** — chạy CLI với monkeypatch không được (ngoài pytest);
  smoke bằng docx mini của test: thêm test tích hợp `test_cli_end_to_end_offline` fake
  toàn bộ LLM + retrieval qua monkeypatch, gọi `app.compliance.__main__.main([...])` với
  docx mini trong tmp_path, assert file .md sinh ra có bảng và khối Recall.

- [ ] **Step 5: ruff + commit** (nhớ `.gitignore` bổ sung `eval/compliance/*.md`):

```bash
git add app/compliance/report.py app/compliance/__main__.py tests/test_compliance_report.py .gitignore
git commit -m "feat(compliance): side-by-side report CLI with recall against gold labels"
```

---

### Task 14: Chạy POC thật trên 2 hợp đồng + tổng kết

**Files:**
- Sinh (local, không commit): `eval/compliance/bao_cao_*.md`
- Modify: `docs/TASKLIST.md` (cập nhật T26), `docs/WORKLOG.md` (mục hôm chạy)

- [ ] **Step 1: Chạy cả 2 hợp đồng** (GỌI LLM — ước ~50 điều hợp đồng × 3-4 lượt ≈ 200 lượt;
  chạy tuần tự từng file để dễ dừng):

```powershell
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH='.'
uv run python -m app.compliance "docs/compliance/HD_DVThuHoCoLK.docx" `
  --against ND52-2024 TT18-2024 TT15-2024 TT40-2024 --corpus <đường dẫn Task 13 đã chốt> `
  --gold eval/compliance/gold.jsonl --out eval/compliance/bao_cao_thu_ho.md
uv run python -m app.compliance "docs/compliance/260511_PAYFAC_HD MAU_Dự thảo 1-2.docx" `
  --against ND52-2024 TT18-2024 TT15-2024 TT40-2024 --corpus <như trên> `
  --gold eval/compliance/gold.jsonl --out eval/compliance/bao_cao_payfac.md
```

Expected: mỗi lệnh in tiến trình từng điều và kết thúc bằng bảng recall. Lỗi giữa chừng →
dùng skill systematic-debugging, KHÔNG che bằng try/except.

- [ ] **Step 2: Đọc 2 báo cáo, tổng hợp trình chủ repo:** recall đường mới vs đường cũ trên
  các comment phap_ly trong corpus; danh sách bỏ sót (comment nào, vì sao — thiếu CU? gate
  chặn nhầm? judge sai?); danh sách "ca lạ" (`nguong_bo_sot`/`tinh_thai_kho` từ Task 4 +
  cảnh báo runtime). KHÔNG kết luận "hơn/kém" ngoài số đo được.

- [ ] **Step 3: Ghi sổ:** cập nhật `docs/TASKLIST.md` — T26 thêm dòng trạng thái POC (số
  recall hai đường, link spec/plan, các ca lạ chờ chốt schema); `docs/WORKLOG.md` mục
  hôm chạy (Ship/Done/Decision). Đo lại số liệu trong chính lượt viết — không chép từ trí nhớ.

- [ ] **Step 4: Kiểm cuối + commit docs:**

```bash
uv run pytest -q          # kỳ vọng: xanh toàn bộ
uv run ruff check .
git add docs/TASKLIST.md docs/WORKLOG.md
git commit -m "docs: record GraphCompliance POC results against lawyer gold labels"
```

- [ ] **Step 5: Hỏi chủ repo** trước khi push (nhánh `feat/ai-compliance` đang có PR #19
  mở — push là commit vào PR đó) và trước mọi bước tiếp theo (nới schema theo ca lạ, nối
  API, mở rộng độ phủ — cả ba nằm ngoài phạm vi plan này).

---

## Self-review (đã chạy)

- **Phủ spec:** schema fix (T1-3) · trích targeted + kiểm corpus (T4) · gold + vệ sinh dữ
  liệu (T7, .gitignore trước khi sinh file) · parse hợp đồng (T5-6) · Context Graph (T9-10)
  · Policy Graph + Gate (T8, T11) · Judge + override (T12) · báo cáo + recall (T13) · chạy
  thật + ghi sổ (T14). Giao thức "ca lạ" nằm ở T4/T13/T14 (cờ → gom → trình chủ repo).
- **Type-consistency:** `boc_nguong` trả `(list[Nguong], list[str])` dùng ở T3;
  `PolicyGraph.load/cu_cua_dieu/lang_gieng/closure/mien_tru_trong` dùng ở T11-12;
  `DeXuat` T10→T11; `CUPlan/PlanItem` T11→T12; `PhanQuyet` T12→T13.
- **Điểm phải kiểm lúc thực thi (ghi trong task, không phải placeholder):** pydantic có
  chấp nhận key thừa `fixture` không (T8 Step 3); `PremiseRecord.alias` tồn tại không
  (T10); đường dẫn corpus cho `load_corpus` (T13, xem cách `app/ingestion` CLI gọi);
  danh sách Điều viện dẫn chốt theo gold.jsonl (T4 Step 2 ↔ T7).
