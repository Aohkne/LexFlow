# Đối chiếu code hiện tại với Schema KG v0.5

**Câu hỏi:** schema văn bản pháp luật đang có trong repo đã thoả `research/schema-kg-v05.html` chưa?

**Trả lời: chưa — nhưng "chưa" đó không đồng đều.** Phần v0.5 đặc tả kỹ nhất (§4 khoá nhánh,
§5 đánh số) thì code **đã thoả và có test canh**. Phần từ cấp Điều trở lên (VanBan, 13 quan hệ,
tầng thời gian, độ tin cậy) **phần lớn chưa tồn tại dưới dạng code**.

Ngày đối chiếu: 2026-08-03 · v0.5 bản 29/07/2026 · mọi số trong tài liệu này kiểm lại được bằng §6.

---

## 1. Repo có HAI schema văn bản, v0.5 mô tả MỘT

Đây là điều phải đọc trước, vì nó quyết định cách hiểu toàn bộ phần còn lại.

| | tầng | khoá một Điều | dựng bởi | lưu ở |
|---|---|---|---|---|
| **A** | app đang chạy | `TT40-2024` + nhãn chuỗi `"Điều 41"` | `app/core/schemas.py` | Neo4j `(:Document)-[:REL]->` |
| **B** | PoC ontology | `40/2024/TT-NHNN#than/dieu_41#khoan_2` | `app/ontology/parser.py:232` | JSONL |

- **B** dùng đúng khoá của v0.5 §4.
- **A** không dùng — `doc_id` là chuỗi viết tắt do LLM sinh (`app/ingestion/extract.py:35`).
- **Không có bảng map giữa hai bên.**

⇒ Cùng một Điều 41 của TT 40/2024 hiện tồn tại dưới **hai khoá không quy về nhau được**.
Trái §9 quyết định #10 (*"giữ số hiệu chính thức làm khoá"*), và làm mọi kế hoạch
"đổ PoC vào KG" phải qua một bước dịch chưa ai viết.

Câu hỏi cần chốt trước khi làm tiếp: **v0.5 là đặc tả cho A, cho B, hay cho một tầng thứ ba
sẽ thay thế cả hai?**

---

## 2. Đối chiếu theo từng mục của v0.5

Mọi ô ✅ đều trỏ tới `file:dòng` của code thật. Mọi ô ❌ đều soi lại được bằng lệnh ở §6.

### 2.1 · §4 Khoá ba nhánh — **1/3**

| nhánh | hiện trạng | bằng chứng |
|---|---|---|
| `#than/` | ✅ ghi tường minh, đúng dạng spec | `parser.py:232` · `citation.py:198` |
| `#kemtheo_*` | ❌ không sinh, cũng không parse | 0 hit chuỗi `kemtheo_` trong `app/` |
| `#phuluc_*` | ❌ không sinh, cũng không parse | 0 hit chuỗi `phuluc_` trong `app/` |

⚠️ **Hệ quả chưa bắn nhưng có thật.** `#than/` được **hardcode ở hai chỗ** (`parser.py:232`,
`citation.py:198`). Nếu nạp một Điều nằm trong quy chế ban hành kèm theo hoặc trong phụ lục có
đánh số Điều, nó vẫn nhận khoá `#than/` — **đúng cái va khoá im lặng mà §3 dựng
`VanBanKemTheo` để chặn**. Hiện chưa hỏng vì cả 18 fixture đều là thân văn bản. Đây là rủi ro
cấu trúc, không phải lỗi đang có.

### 2.2 · §5 Đánh số Điều và Khoản — **5/6, khối mạnh nhất**

| yêu cầu v0.5 | hiện trạng | bằng chứng |
|---|---|---|
| `so_hien_thi`/`so_goc`/`so_hau_to` cho **Điều** | ✅ | `schema.py:33-35` · `parser.py:229-231` |
| …cho **Khoản** (ca `khoản 2đ`, mới v0.5) | ✅ | `parser.py:245-246`; `_KHOAN_RE` khớp hậu tố chữ |
| Bảng **23 chữ**, tra bảng — **không `ord()`** | ✅ | `parser.py:28-31`; `letter_to_so_hau_to()` **raise** khi chữ ngoài bảng |
| …soi lại ở phía web | ✅ | `web/lib/anchors.ts:7` kèm chú thích phải khớp `parser.py` |
| 1-based `a=1 … đ=5` | ✅ khớp bảng §5 (Điều 15a→1 · Khoản 2đ→5) | `parser.py:31` |
| **`nhanh` là một TRƯỜNG** | ❌ chỉ nằm *bên trong chuỗi* `id` | `Node` (`schema.py:25-38`) không có trường `nhanh` |

§5 liệt kê `nhanh` như một trường của node, và §4 có lệnh di trú `SET d.nhanh = 'than'`.
Hiện muốn biết nhánh phải **cắt chuỗi id**.

> **Một lỗi trong chính v0.5:** §2 (changelog) gọi hai trường mới là `so_khoan_goc` /
> `so_khoan_hau_to`, còn §5 (bảng chuẩn) gọi `so_goc` / `so_hau_to`. Code theo §5.
> Lệch tên, không lệch ngữ nghĩa — nên sửa changelog cho khớp bảng của chính nó.

Bẫy tách cấu trúc từ PDF ở §5 (*"mọi giải thuật dựa vào cỡ chữ chắc chắn thất bại"*):
✅ parser đi hoàn toàn theo **mẫu đánh số ở đầu dòng**, không đụng tới định dạng.

### 2.3 · §3 Meta-schema node — **4/15 có thật**

| | node |
|---|---|
| **có, kèm dữ liệu** | `Dieu` · `Khoan` · `Diem` · `KhaiNiem` (36 bản ghi, `eval/ontology/khainiem.jsonl`) |
| **một phần** | `VanBan` — A có `(:Document)` nhưng khác khoá và khác hẳn tập thuộc tính · `ThucTheChiuDieuChinh` chỉ là **chuỗi** `ConditionItem.object_label`, không phải node |
| **không có** | `VanBanKemTheo` · `PhuLuc` · `Chuong` · `Muc` · `CoQuanBanHanh` · `LinhVuc` · `DeMuc` · `PhienBanDieu` · `SuKienLapPhap` · `QuyTacHieuLuc` (§1.3b) |

Bằng chứng hàng cuối: grep từng tên trên toàn bộ `app/**/*.py` ⇒ **0 hit**. Bốn tên có hit đều
là **khớp chuỗi con**, không phải định nghĩa node:

| hit | thực chất |
|---|---|
| `Chuong` ×7 | `_CHUONG_RE` (regex nhận marker) · `Gate.pham_vi` enum · bảng chữ→mã ở `classify.py:98` |
| `Muc` ×3 | cùng ba chỗ trên |
| `CAN_CU` ×3 | hàm `_hard_deu_co_can_cu` của modality guard — không liên quan |
| `ThucTheChiuDieuChinh` ×1 | một dòng **docstring** ở `schema.py:9` |

**Hai dấu vết dễ đọc nhầm là "đã có `Chuong`/`Muc`":**

- `Article.chapter` / `Article.section` (`core/schemas.py:51-52`) **được khai báo nhưng
  0/278 điều có giá trị** — không code nào gán. **Trường chết.**
- `Gate.pham_vi` nhận `"chuong"` / `"muc"` (`schema.py:159`) — nhưng **luôn kèm
  `suy_ra_duoc=False`**, vì parser không có node tương ứng để quy về. Đây là cách xử lý
  **trung thực** (nói thẳng "có phạm vi nhưng chưa quy được về khoá node"), không phải một
  cài đặt dở. Ghi ở đây như điểm cộng, để không ai đi "sửa" nó thành `True`.

Giới hạn có chủ đích của §3 (gạch đầu dòng không đánh số nằm lại trong nội dung của `Diem`):
✅ thoả **theo cấu trúc** — parser không tạo node nào dưới cấp Điểm.

### 2.4 · §6 · 13 quan hệ giữa văn bản — **4/13, và cách lưu khác hẳn**

| | |
|---|---|
| **có** (4) | `THAY_THE` · `SUA_DOI` · `HUONG_DAN` · `DAN_CHIEU` — `core/schemas.py:7`; 13 instance trong `data/corpus.real.json` |
| **thiếu** (9) | `HUONG_DAN_AP_DUNG` · `HOP_NHAT` · `DINH_CHINH` · `BAI_BO` · `CAN_CU` · `GIAI_THICH` · `DINH_CHI_THI_HANH` · `TAM_NGUNG_HIEU_LUC` · `CONG_BO` |
| **lệch tên** | `SUA_DOI` ↔ `SUA_DOI_BO_SUNG` · `HUONG_DAN` ↔ `QUY_DINH_CHI_TIET_HUONG_DAN` |

Chỗ lệch tên thứ hai **không chỉ là tên**: §6.3 nói đúng nhãn đó **gộp hai thứ mà Đ.53 kh.2
đối xử khác nhau**, và cần thuộc tính `co_uy_quyen` để tách. Cạnh hiện tại không có.

**Cách lưu khác hẳn spec.** `graph.py:67`:

```cypher
MERGE (a)-[e:REL {rel_type: $rt}]->(b)
```

Một **kiểu cạnh duy nhất** mang property, không phải 13 kiểu cạnh có tên.
⇒ **Mọi câu Cypher trong v0.5 không chạy được** trên đồ thị hiện tại — cả
`-[:QUY_DINH_CHI_TIET_HUONG_DAN]-` (§7.3 R8) lẫn `-[:CO_PHIEN_BAN]->` (§7.1).

Thuộc tính cạnh: có `valid_from` / `note` / `anchors`. Thiếu `co_uy_quyen`,
`dieu_khoan_uy_quyen`, `loai_thao_tac`, `nhanh_dich`, `do_tin_cay`, `trich_dan_nguon`.

> ⚠️ **Một năng lực v0.5 hứa mà hệ chưa có, không chỉ là một cạnh thiếu.**
> §6.2 đặt ra ca kiểm chứng **bắt buộc**: tìm mọi `VanBan` bị `BAI_BO` mà **không** có
> `THAY_THE` nào trỏ tới — *"legislative void"*, có tiền lệ học thuật (Colombo et al.,
> EDBT/ICDT 2025). Truy vấn đó hiện **không chạy được**, vì `BAI_BO` không tồn tại như một loại.

### 2.5 · §7 Tầng thời gian — **0/5**

| yêu cầu | hiện trạng |
|---|---|
| `PhienBanDieu` (nội dung theo thời điểm) | ❌ không có |
| Khoảng **nửa mở** `[hieu_luc_tu, hieu_luc_den)` | ❌ code dùng khoảng **đóng** — xem §3 mục 2 |
| **Bốn** trạng thái hiệu lực | ❌ chỉ có hai — xem §3 mục 3 |
| Cờ `la_vbhn` | ❌ không có; `doc_type` là chuỗi tự do, không gì chặn việc nạp một VBHN như văn bản thường |
| Ngày hiệu lực **trên cạnh** | ⚠️ **một phần** |

Ô cuối cần nói rõ: `Relationship.valid_from` **đúng là nằm trên cạnh** ✅
(`core/schemas.py:24`). Nhưng `RelAnchor` (`core/schemas.py:10-15`) **không mang ngày**.
⇒ **Hiệu lực phân kỳ không biểu diễn được** — đúng ca TT 25/2025 mà §7.2 dùng để chứng minh
tại sao ngày phải nằm trên cạnh (31/8/2025 chung, 01/12/2025 và 01/3/2026 cho một số quy định).
Ba mốc của một văn bản hiện chỉ ghi được **một**.

§7.4 (VBHN là phi quy phạm, nạp như văn bản thường sẽ **đếm trùng trong im lặng**): chưa có
cơ chế nào chặn. Corpus hiện chưa có VBHN nào nên chưa hỏng.

### 2.6 · §8 Độ tin cậy và nguồn — **0/2**

| yêu cầu | hiện trạng |
|---|---|
| `nguon_hieu_luc_den` (4 giá trị) | ❌ không có |
| `da_xac_minh_nguon` (3 mức) | ❌ không có |

**Chỗ dễ nhận vơ, phải tách bạch.** Repo **có** một trạng thái duyệt trên Supabase:
`pending` / `approved` / `rejected` (`api/documents.py:118,185`), và `extract.py` ghi rõ
*"NGƯỜI DUYỆT file này trước khi ingest"*. Nhưng đó là trục **"đã có người bấm duyệt bản
extract hay chưa"** — **khác trục** với `da_xac_minh_nguon`, vốn hỏi *"đọc bản Công báo có
chữ ký, hay đọc nguồn thứ cấp"*.

Sự khác biệt này không hình thức: §8.2 kể lại một ca hỏng thật (Điều 3 Luật 87/2025 từng bị
kết luận là không tồn tại) nằm **gọn trong vùng "thứ cấp mà tưởng là đủ"**. Trạng thái duyệt
hiện tại **không phân biệt được vùng đó** — một bản extract từ nguồn thứ cấp bị cắt cụt vẫn
`approved` y như một bản đọc từ Công báo.

Tương tự, thiếu `nguon_hieu_luc_den` nghĩa là một `valid_to` **do suy đoán** trông **y hệt**
một `valid_to` **đọc được từ văn bản**. Hiện chưa gây hại vì **0/278 điều có `valid_to`**.

### 2.7 · §9 · Mười quyết định thiết kế

| # | quyết định | hiện trạng |
|---|---|---|
| 1 | Cấp phân rã Điều/Khoản/Điểm | **B ✅** (dựng cả ba, luôn luôn — chặt hơn "theo nhu cầu" của spec) · **A ❌** (chỉ tới Điều, dạng nhãn chuỗi) |
| 2 | Phiên bản ở cấp Điều | — chưa áp dụng được (chưa có versioning) |
| 3 | Temporal chọn lọc | — chưa áp dụng được |
| 4 | Ngày sửa đổi trên cạnh | ⚠️ một phần (xem §2.5) |
| 5 | Neo4j 5.x / AuraDB | ⚠️ có Neo4j, nhưng schema không liên quan v0.5; đúng **1** constraint (`doc_id` unique, `graph.py:36`) |
| 6 | `KhaiNiem` tinh thần SKOS · `ThucTheChiuDieuChinh` P2 | ✅ `KhaiNiem` đã chạy 36 bản ghi · `ThucTheChiuDieuChinh` đúng là còn ở P2 |
| 7 | Loại bỏ `VuAn` | ✅ không có ở đâu |
| 8 | `Khoan.ten` **nullable** | ❌ `KhoanNode` **không có** trường `ten` |
| 9 | Không dựng `DiaGioi` | ✅ không có — và `DieuKienCong.kind` cố ý loại `lanh_tho` vì **0 case trong corpus**, đúng cùng một kỷ luật với lý do §9 #9 đưa ra |
| 10 | Số hiệu chính thức làm khoá | **B ✅ · A ❌** — xem §1 |

---

## 3. Ba chỗ MÂU THUẪN — khác hẳn "chưa dựng"

Tách riêng vì **"thiếu" thì dựng thêm là xong**, còn ba cái này đang **nói ngược nhau ngay
trong repo**. Xếp theo mức đáng xử lý.

### 3.1 · Trạng thái nhị phân nuốt mất `chua_hieu_luc` — **lỗi đang sống trong UI**

`api/documents.py:49`:

```python
status = "con_hieu_luc" if effective else "het_hieu_luc"
```

mà `is_effective` (`versioning.py:37-38`) trả `False` khi `ref < valid_from`.

⇒ **Một văn bản đã ban hành nhưng CHƯA tới ngày hiệu lực đang hiển thị là HẾT hiệu lực.**
Hai trạng thái ở hai đầu đối lập của vòng đời bị gộp làm một, và người dùng thấy đúng cái
sai nghĩa nhất.

§7.3 của v0.5 có đủ **bốn** trạng thái (`chua_hieu_luc` · `hieu_luc` · `het_hieu_luc` ·
`hieu_luc_co_dieu_kien`) chính là để chặn ca này.

> Mức: **cao** — đây là lỗi hiện hành, không phải rủi ro tương lai.
> Sửa nhỏ (thêm một nhánh so sánh `valid_from`), nhưng chạm vào `DocumentSummary.status`
> nên phải xem cả phía web.

### 3.2 · Khoảng hiệu lực ĐÓNG, trong khi tài liệu thiết kế tuyên bố nửa mở là "duy nhất"

`versioning.py:37-40` dùng khoảng **đóng hai đầu** — `vf <= ref <= vt`.

Nhưng `docs/RAG-DESIGN.md §1.2` viết nguyên văn:

> **"Vị từ nửa mở là bộ lọc thời gian DUY NHẤT** — nguyên văn
> `hieu_luc_tu <= T AND (hieu_luc_den IS NULL OR T < hieu_luc_den)` …
> **Không viết biến thể thứ hai ở bất cứ đâu."**

và v0.5 §7.1 buộc `hieu_luc_den` của phiên bản cũ **bằng đúng** `hieu_luc_tu` của phiên bản
mới (*"không trừ một ngày ⇒ không thể sai lệch ở biên"*).

⇒ Ngay khi bắt đầu điền `valid_to` theo quy ước đó, **đúng ngày biên sẽ khớp CẢ HAI phiên bản**.

Hiện chưa bắn vì **0/278 điều có `valid_to`**. Nghĩa là nó sẽ hỏng đúng vào lúc tầng thời gian
bắt đầu có dữ liệu — lúc khó phát hiện nhất.

> Mức: **cao** (sửa trước khi nạp dữ liệu temporal) · Chi phí: một dấu `<`.

### 3.3 · Hai không gian ID, và một lời hứa đã ghi nhưng không đúng

Xem §1. Thêm một chi tiết: `docs/RAG-DESIGN.md §1.1` đã hứa

> *"`id` row **trùng id node KG** … Hệ quả: nhảy từ kết quả vector sang đồ thị **không cần
> bảng map**, citation deep-link tự nhiên."*

Lời hứa đó hiện **không đúng** với A. Nó đúng với B, và B chưa nối vào retrieval.

> Mức: **cao**, nhưng chi phí lớn — đổi `doc_id` chạm corpus + Neo4j + web + LanceDB.
> Là quyết định kiến trúc, không phải một bản vá.

### 3.4 · (rủi ro chưa bắn) Khoá `#than/` hardcode

Xem §2.1. Chưa hỏng, nhưng hỏng thì **im lặng**.

> Mức: **trung bình** · Rẻ nhất trong bốn cái: hoặc thêm tham số `nhanh`, hoặc chỉ cần
> **chặn** — `parse_dieu` nhận nguồn không phải thân văn bản thì raise thay vì gán `#than/`.

---

## 4. Bốn chỗ PoC đã đi TRƯỚC v0.5 — v0.6 nên hấp thụ

Không phải mục tự khen. Đây là những thứ **đo được trên văn bản thật** mà spec chưa phủ, nên
chúng là đầu vào cho bản sau chứ không phải là "code lệch spec".

| phát hiện | số đo | v0.5 nói gì |
|---|---|---|
| **Tiết `(i)`/`(ii)`** — `TietSpan` (cố ý **không** cấp id) + `DiemRef.tiet` mô hình hoá như **hậu tố**, y cách §5 xử lý `Điều 15a` | 4/586 viện dẫn đi tới cấp này, **cả 4 đều ở văn bản đã hết hiệu lực**; chữ "tiết" xuất hiện **0 lần** trong 557k ký tự corpus (`citation.py:9-16`, `schema.py:41-47`) | §3 dừng ở `Diem`, **không nhắc tiết** |
| **Điều không chẻ Khoản** — `khoan_de_trich()` sinh một khoản ảo mang `id` của chính Điều | **25/267 điều (9,4%)**, kể cả điều nội dung như Đ.9, Đ.38 ND52 (`parser.py:176-186`) | §9 #1 coi Khoản là cấp phân rã của nhóm lõi, **không nói ca này**. Trước khi có hàm này, vòng lặp chạy 0 lần và **cả điều bị bỏ qua không một lời báo** |
| **`DieuKienCong`** — parse mốc ngày **tất định bằng regex**, có `moc: bat_dau \| ket_thuc` + `char_span` round-trip | 8 cổng thời gian; ca *"có hiệu lực thi hành **đến hết ngày** 14/8/2024"* là mốc **KẾT THÚC** (`schema.py:171-197`) | §7 nói `PhienBanDieu.hieu_luc_tu` phải có, nhưng **không nói lấy ngày ở đâu ra**. Đây chính là mặt trích xuất của nó |
| **Trục tin cậy thứ hai** — `CitationRef.do_tin_cay` (cao/trung_binh/thấp) + `Grounding.status` (exact/unit/invalid) | | §8 chỉ có trục *tin cậy **nguồn***. Đây là trục *tin cậy **trích xuất*** — cùng kỷ luật, khác chiều |

Riêng ô thứ ba đáng nêu với mentor: `moc` tồn tại vì nhét một ngày kết thúc vào ô tên là
"ngày hiệu lực" là **đảo ngược ngữ nghĩa trong im lặng** — đúng loại lỗi mà `Gate.phu_dinh`
cũng đã phải sinh ra để chặn. v0.5 §7 hiện chỉ có `hieu_luc_tu`/`hieu_luc_den` ở tầng node,
chưa có chỗ nào ghi *"câu luật này nói về mốc bắt đầu hay mốc kết thúc"*.

---

## 5. Tổng kết một trang

| khối v0.5 | điểm |
|---|---|
| §4 · Khoá ba nhánh | **1/3** |
| §5 · Đánh số Điều/Khoản | **5/6** |
| §3 · Node meta-schema | **4/15** |
| §6 · 13 quan hệ | **4/13** (và cách lưu khác kiểu ⇒ Cypher của spec không chạy) |
| §7 · Tầng thời gian | **0/5** |
| §8 · Độ tin cậy | **0/2** |
| §9 · Mười quyết định | 3 đạt · 2 không đạt · 1 một phần · 4 chưa áp dụng được |

**Kết luận, không làm tròn lên:** phần v0.5 đặc tả kỹ nhất — đánh số và khoá nhánh `than` —
code đã thoả và **có test canh**. Phần còn lại của v0.5 phần lớn **chưa tồn tại dưới dạng
code**, và ba chỗ mâu thuẫn ở §3 là thứ phải xử lý trước khi dựng thêm, không phải sau.

### Việc còn đọng — đã có chẩn đoán, chưa xử lý

| # | việc | mức | chi phí |
|---|---|---|---|
| 1 | `status` bốn trạng thái (§3.1) — **lỗi đang sống** | cao | nhỏ, chạm web |
| 2 | `is_effective` sang nửa mở (§3.2) | cao | một dấu `<` + test biên |
| 3 | Chặn khoá `#than/` bịa (§3.4) | trung bình | nhỏ |
| 4 | Thống nhất không gian ID (§3.3) | cao | lớn — quyết định kiến trúc |
| 5 | 13 cạnh có kiểu thay `REL{rel_type}` (§2.4) | trung bình | vừa; mở khoá được ca kiểm chứng §6.2 |
| 6 | `la_vbhn`, `nguon_hieu_luc_den`, `da_xac_minh_nguon` (§2.5, §2.6) | trung bình | nhỏ mỗi cái, nhưng cần quy trình nhập liệu đi kèm |
| 7 | `nhanh` thành trường, `Khoan.ten` nullable (§2.2, §2.7) | thấp | rất nhỏ |
| 8 | `PhienBanDieu`, `Chuong`/`Muc`, `VanBanKemTheo`, `PhuLuc` | — | phụ thuộc #4 |
| 9 | Sửa changelog v0.5 §2 cho khớp bảng §5 (`so_goc` chứ không `so_khoan_goc`) | thấp | sửa spec, không sửa code |

---

## 6. Cách kiểm lại mọi con số trong tài liệu này

```powershell
# --- 0 hit: các node/trường/cạnh v0.5 yêu cầu mà app/ không có ---
$names = @('VanBanKemTheo','PhuLuc','CoQuanBanHanh','LinhVuc','DeMuc','PhienBanDieu',
           'SuKienLapPhap','QuyTacHieuLuc','la_vbhn','nguon_hieu_luc_den','da_xac_minh_nguon',
           'kemtheo_','phuluc_','hieu_luc_co_dieu_kien','thu_bac','BAI_BO','HOP_NHAT',
           'DINH_CHINH','GIAI_THICH','TAM_NGUNG','DINH_CHI_THI_HANH','CONG_BO','HUONG_DAN_AP_DUNG')
$py = (Get-ChildItem -Recurse -Path app -Filter *.py).FullName
foreach ($n in $names) { "{0,-24} {1}" -f $n, (Select-String -Path $py -SimpleMatch -Pattern $n).Count }

# 'Chuong' 'Muc' 'CAN_CU' 'ThucTheChiuDieuChinh' CÓ hit — đọc từng dòng để thấy
# cả bốn đều là khớp chuỗi con (regex / enum / docstring), không phải định nghĩa node.

# --- 0/278 chapter · 0/278 valid_to · 4 loại quan hệ · 13 instance ---
$c = Get-Content data\corpus.real.json -Raw | ConvertFrom-Json
$a = $c.documents | ForEach-Object { $_.articles }
$a.Count                                        # 278
($a | Where-Object { $_.chapter }).Count        # 0
($a | Where-Object { $_.valid_to }).Count       # 0
$c.relationships.Count                          # 13
$c.relationships | Group-Object rel_type        # THAY_THE 4 · SUA_DOI 2 · HUONG_DAN 4 · DAN_CHIEU 3

# --- KhoanNode không có trường `ten` (rỗng = không có) ---
Select-String -Path app\ontology\schema.py -Pattern "^\s*ten\s*:"

# --- 36 KhaiNiem · 45 premise · 49 CU ---
foreach ($f in 'khainiem','premise','pred') { (Get-Content "eval\ontology\$f.jsonl" | Measure-Object -Line).Lines }
```

```bash
uv run python -m app.ontology --classify data/fixtures
# 94 đơn vị: 45 premise · 9 meta_cu · 40 actor_cu
```

Hai số ở §4 **không đo lại trong đợt này**, lấy từ số đo đã ghi trong code:
4/586 viện dẫn tới cấp tiết (`app/ontology/citation.py:9-16`) và 25/267 điều không chẻ khoản
(`app/ontology/parser.py:176-186`). Cả hai đo trên corpus 15 văn bản, không phải trên 18 fixture.
