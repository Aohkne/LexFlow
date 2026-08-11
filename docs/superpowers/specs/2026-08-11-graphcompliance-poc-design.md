# GraphCompliance POC — Compliance Check theo Policy Graph ↔ Context Graph

**Ngày:** 2026-08-11 · **Nhánh:** `feat/ai-compliance` · **Trạng thái:** đã duyệt design, chờ plan

Triển khai pipeline của paper *GraphCompliance* (arXiv:2510.26309, bản PDF tại
`docs/paper/`) cho tính năng Compliance Check, ở mức POC ngoại tuyến. Nền tảng đã có:
`app/ontology/` là extractor GraphCompliance hoàn chỉnh (ActorCU/MetaCU/Premise/KhaiNiem,
chống bịa 3 tầng, `citation.py` giải viện dẫn tất định) nhưng **chưa nối vào đâu** — xem
T26 trong `docs/TASKLIST.md`. POC này nối nó lại, đo bằng nhãn người thật đầu tiên.

## Quyết định đã chốt (brainstorm 11/08)

| Câu hỏi | Chốt |
|---|---|
| Phạm vi | POC hẹp, **gold-first**: chỉ trích CU cho các Điều được pháp lý viện dẫn + 12 Điều đã phủ (~15–20 Điều) |
| Đầu vào | Tài liệu nội bộ (2 hợp đồng docx có comment pháp lý), nâng đúng đường `review.py` đang đi |
| Schema CU | Sửa trước khi trích: thêm `modality` (6 nhãn VN) + `nguong` — cả hai gán **tất định** |
| Bộ nhãn tình thái | `nghia_vu · cam · cho_phep · chi_duoc · mien_tru · khong_ro` (không dùng must/must_not/may — "chỉ được…khi" và miễn trừ nghĩa vụ sẽ bị 3 nhãn Tây đọc sai) |
| Nơi chứa Policy Graph | In-memory từ JSONL, không đụng Neo4j Aura (chuyển sau khi độ phủ lớn) |
| Tiêu chí đạt | Recall trên comment pháp lý có viện dẫn trong corpus, so side-by-side với `review.py` cũ |

## Nhãn vàng

2 file `docs/compliance/*.docx` (hợp đồng PAYFAC draft + hợp đồng thu hộ) có **95 comment**
của pháp lý (chuyên viên pháp chế, PPC), trong đó **6 viện dẫn VBQPPL tường minh**: NĐ52/2024,
TT40/2024, TT15/2024, TT18/2024 (trong corpus) · TT64/2024, NĐ254/2026 (**ngoài corpus** —
2 comment này ghi nhãn "ngoài phạm vi", không tính recall). Comment còn lại: văn phong /
quy định nội bộ / cần làm rõ — lọc bằng trường `loai`, người duyệt cuối là chủ repo.
Đây là bộ nhãn người đầu tiên của dự án (hiện 0/94 — `ONTOLOGY-FOR-MENTOR.md` §7).

## Kiến trúc

Gói mới `app/compliance/`, POC chạy CLI `python -m app.compliance` (tiền lệ
`python -m app.ontology`). Chưa đụng API/production; không ghi LanceDB/Neo4j/Supabase.

```
OFFLINE (1 lần)
  docs/compliance/*.docx ──┬─► eval/compliance/lam_gold.py ─► gold.jsonl   (nhãn vàng)
                           └─► app/compliance/hop_dong.py  ─► điều hợp đồng (input)
  Điều được viện dẫn ─► python -m app.ontology (schema mới) ─► pred.jsonl mở rộng

RUNTIME (mỗi lần check)
  điều hợp đồng
    ├─► er_triples.py    S–A–O triples (LLM, temp 0)          ┐
    ├─► hypernym.py      entity → thuật ngữ luật               │ Context Graph
    │                    (36 KhaiNiem + 45 premise, in-memory) ┘
    ├─► policy_graph.py  nạp pred/premise/khainiem JSONL,      ┐
    │                    cạnh REFERS_TO, in-memory             │ Policy Graph
    ├─► gate.py          lọc tất định: hiệu lực as_of +        │
    │                    gate chủ thể/thời gian của meta-CU +  │ Compliance Gate
    │                    retrieval lai sẵn có → CU plan        ┘
    ├─► judge.py         phán từng CU (self-consistency như review.py)
    │                    vi_pham → closure REFERS_TO tìm mien_tru → override
    └─► report.py        side-by-side: gold ↔ đường cũ ↔ đường mới
```

Nguyên tắc xuyên suốt (giữ từ `app/ontology/`): cái gì regex/tra cứu làm được thì
**không hỏi LLM**. LLM chỉ ở 3 chỗ: trích CU (offline), ER-triple + hypernym confirm,
judge. Ước lượng ~200–300 lượt Gemini cho toàn POC.

## 1 · Sửa schema CU (`app/ontology/schema.py`)

```python
class Nguong(BaseModel):
    """Một ràng buộc định lượng bóc tất định từ text đã neo."""
    so: str                    # "100", chuẩn hoá như find_numbers
    don_vi: str | None         # "triệu đồng", "ngày làm việc", "%", "tuổi"…
    huong: Literal["toi_thieu", "toi_da", "khong_ro"]
    text: str                  # cụm gốc: "không quá 100 triệu đồng"
    span: tuple[int, int]      # char_span trong đoạn luật — cùng kỷ luật Grounding

class ActorCU(GroundedUnit):
    ...
    modality: Literal["nghia_vu", "cam", "cho_phep", "chi_duoc",
                      "mien_tru", "khong_ro"] = "khong_ro"
    nguong: list[Nguong] = Field(default_factory=list)
```

- **`modality`** gán tất định từ từ điển `modality.py`, mở rộng 2 nhóm:
  `chi_duoc: ["chỉ được"]`, `mien_tru: ["không phải", "được miễn", "không bắt buộc"]`.
  Chọn theo dấu hiệu trong `action.text` đã neo, ưu tiên
  `cam > chi_duoc > mien_tru > nghia_vu > cho_phep`. Hai bẫy phải xử trong từ điển:
  "chỉ được" xếp trên "được" (khớp-dài-nhất-trước đã có ở `_MODALITY_RE`);
  "không phải **là**" (phủ định danh xưng) ≠ miễn trừ → lookahead loại trừ "là".
- **`nguong`** ghép dấu hiệu nhóm `dinh_luong` với số liền kề (`_NUM_RE`) trong cùng
  cửa sổ cụm; `huong` suy từ dấu hiệu (tối thiểu/ít nhất/trở lên → `toi_thieu`;
  tối đa/không quá/chậm nhất/trở xuống → `toi_da`). Số không có dấu hiệu đi kèm
  **không** thành ngưỡng (tránh vơ số điều khoản, số tài khoản).
- `Nguong` đứng riêng với `DieuKienCong` (schema.py:213): một bên trả lời "vượt mức
  chưa" (actor-CU), một bên "áp dụng chưa" (gate meta-CU). Không gộp.
- Semantics tình thái: `cho_phep` = P(p) · `chi_duoc` = P(p|C) ∧ F(p|¬C) ·
  `mien_tru` = ¬O(p) — chất liệu cho vòng override.

### Xử lý ca lạ — lưới bắt, không đoán trước

Bộ bóc tất định **không ép** ca không khớp vào class hiện có, không tự chế class mới:

- dấu hiệu `dinh_luong` mà không dựng nổi `Nguong` hợp lệ → cờ `nguong_bo_sot`
  (kèm cụm gốc + span) trong báo cáo trích xuất;
- `modality = khong_ro` nhưng text có dấu hiệu ràng buộc cứng → cờ `tinh_thai_kho`.

Cờ nổ → tổng hợp trình chủ repo (cụm gốc + đề xuất class mới/nới Literal) → chốt →
PR schema nhỏ riêng → chạy lại extractor. Hai ca đã lường trước: mốc-ngày-trong-nghĩa-vụ
("chậm nhất ngày 15/01 hằng năm") và ngưỡng-theo-bậc-chủ-thể ("5 triệu/ngày với cá nhân,
100 triệu/ngày với tổ chức").

### Trích targeted

Chạy lại extractor schema mới trên (a) 12 Điều đã phủ, (b) các Điều được pháp lý viện
dẫn nằm trong corpus. Kiểm trước xem `python -m app.ontology` nhận chọn đích từng Điều
chưa — chưa thì thêm cờ `--dieu`.

## 2 · Nhãn vàng & parse hợp đồng

**`eval/compliance/lam_gold.py`** (stdlib `zipfile` + `xml`, không thêm thư viện):

- Bóc comment + đoạn neo (`commentRangeStart/End` trong `document.xml`) + điều hợp
  đồng chứa đoạn đó.
- Giải viện dẫn bằng `parse_citations` **sau lớp chuẩn hoá văn nói** (NĐ→Nghị định,
  TT→Thông tư, "điều"→"Điều", TT_NHNN→TT-NHNN) — chỉ trong script này, không nới
  `citation.py` lõi (đã đo: không chuẩn hoá thì 0/95 comment bắt được viện dẫn).
- `gold.jsonl`: `{file, comment_id, dieu_hop_dong, anchor_text, comment_text, refs[], loai}`;
  `loai ∈ {phap_ly, noi_bo, van_phong, lam_ro}` — gán sơ bộ bằng luật đơn giản,
  **chủ repo duyệt** một lượt 95 dòng.

**`app/compliance/hop_dong.py`**: parse `document.xml` →
`HopDong{ten, dieu: [DieuHopDong{so, tieu_de, text, span}]}`, nhận cả "Điều 1." lẫn "1.1".
Tách khỏi gold để cắm hợp đồng mới không kéo theo phần nhãn.

## 3 · Context Graph

- **`er_triples.py`** — LLM trích (subject, predicate, object) từng điều hợp đồng,
  temp 0, JSON theo schema. Entity không nằm nguyên văn trong điều → bỏ triple + cảnh
  báo (kỷ luật chống bịa).
- **`hypernym.py`** — map entity → thuật ngữ luật: embed entity, so cosine in-memory
  với 36 `KhaiNiem` + 45 premise (81 vector, không cần LanceDB), LLM xác nhận kèm độ
  tin; đề xuất chống lưng bằng premise = STRONG, còn lại WEAK (đúng paper §3.2).
  Dưới ngưỡng tin → entity để không map, không ép.

## 4 · Policy Graph + Compliance Gate

- **`policy_graph.py`** — nạp JSONL → dict theo node key; cạnh REFERS_TO hai chiều từ
  trường `references`; lọc hiệu lực bằng chuỗi lớp phủ (`hien_hanh`) — CU thuộc đơn vị
  bị sửa/bãi bỏ tại `as_of` loại khỏi plan.
- **`gate.py`** — tất định, chạy trước LLM: (1) ứng viên = retrieval lai trên text điều
  hợp đồng → chunk → Điều → CU neo trong đó, cộng CU có `subject` khớp hypernym các bên;
  (2) nở 1 hop REFERS_TO; (3) meta-CU trước: gate `thoi_gian` so `DieuKienCong` với
  `as_of`, gate `chu_the` so hypernym các bên; gate không xác quyết được (`lanh_tho`,
  `khac`, `suy_ra_duoc=False`) → **giữ CU + đánh dấu "gate chưa xác quyết"** (fail-open:
  mục tiêu là recall, thà judge thừa còn hơn gate nuốt); (4) ra CU plan.

## 5 · Judge + override

- Mỗi điều hợp đồng một lượt phán **cả plan** (như paper Eq. 5), self-consistency y
  `review.py`: temp 0, 2 phiếu, hòa → phiếu 3, đa số thắng.
- Nhãn: `tuan_thu | vi_pham | thieu_thong_tin | khong_ap_dung`. Prompt cấm suy từ im
  lặng; CU có `nguong` → bắt so số-với-số tường minh.
- `vi_pham` → closure REFERS_TO (tất định, sâu ≤ 2) gom CU `mien_tru`/`NgoaiLe` → lượt
  gọi 2 hỏi một câu "ngoại lệ này có áp không" (paper Eq. 6) → flip nếu có, ghi căn cứ.
- Plan rỗng → `khong_ap_dung` kèm ghi chú, không im lặng.

## 6 · Báo cáo & tiêu chí đạt

`report.py` xuất mỗi hợp đồng một báo cáo, mỗi điều 3 cột:
**gold** (comment pháp lý) ↔ **đường cũ** (`review.py` text thô) ↔ **đường mới**
(verdict + CU + văn bản viện dẫn).

Số đo duy nhất: **recall trên comment `loai=phap_ly` có ref trong corpus** — đường mới
có trỏ đúng điều-hợp-đồng và đúng văn bản luật mà pháp lý đã chỉ không. Đường cũ đo cùng
thước. Không đo F1 (chưa đủ nhãn), không tự chấm bằng LLM rater.

## Kiểm thử

- Mọi module tất định (parse docx, gold, modality, nguong, gate, closure, policy_graph)
  có unit test với fixture tổng hợp. **Docx fixture tự dựng bằng `zipfile`, không chứa
  chữ nào của hợp đồng thật.**
- LLM sau interface mỏng; test dùng fake, không gọi mạng trong pytest (giữ nếp 797 test
  offline).
- Trước khi xong: `uv run pytest -q` xanh, `uv run ruff check .` sạch.

## Vệ sinh dữ liệu

2 docx là hợp đồng thật của ngân hàng (bản PAYFAC chưa ẩn danh). **Không commit**:
thêm `docs/compliance/` và `eval/compliance/*.jsonl` vào `.gitignore`; chỉ commit script.
Không dán nguyên văn hợp đồng vào tài liệu/commit message/chat log công khai.

## Giả định phải kiểm khi thực thi

1. **NĐ52/2024 trong corpus**: T26 ghi "không có trong corpus" nhưng
   `data/raw/vbpl/corpus/nghi-dinh-so-52-2024-*.json` tồn tại — nghi là ca
   `so_hieu=None` đã sửa ở `da9d1ab` nhưng chưa re-ingest. Kiểm bằng truy vấn LanceDB
   trước khi trích; nếu thiếu thật thì xin chủ repo duyệt re-ingest (ghi cloud).
2. **TT18/2024 đã ingest chưa** — có `data/raw/TT18-2024.html` nhưng cần xác nhận trong
   corpus 26 văn bản.
3. `python -m app.ontology` chọn đích từng Điều được chưa (nếu chưa → thêm `--dieu`).
4. TT64/2024, NĐ254/2026 ngoài corpus: comment viện dẫn chúng = nhãn "ngoài phạm vi".

## Ngoài phạm vi POC

- Nối vào API/`review.py` production, endpoint tình huống tự do, ghi Neo4j/LanceDB,
  mở rộng độ phủ 425 Điều, LLM rater kiểu paper RQ — tất cả chờ kết quả POC + nhãn duyệt.
