# Đối chiếu code hiện tại với Schema KG v0.5

**Câu hỏi:** schema văn bản pháp luật đang có trong repo đã thoả `research/schema-kg-v05.html` chưa?

**Trả lời: chưa — nhưng "chưa" đó không đồng đều.** Phần v0.5 đặc tả kỹ nhất (§4 khoá nhánh,
§5 đánh số) thì code **đã thoả và có test canh**. Phần từ cấp Điều trở lên (VanBan, 13 quan hệ,
tầng thời gian, độ tin cậy) **phần lớn chưa tồn tại dưới dạng code**.

Ngày đối chiếu: 2026-08-03, **đo lại 2026-08-04** · v0.5 bản 29/07/2026 · mọi số trong tài liệu
này kiểm lại được bằng §6.

> **Đo lại 04/08 — điểm các khối KHÔNG đổi một ô nào.** Ngày 04/08 có ba đợt việc ở tầng CU
> (`source_diem` suy từ parser · luật chapeau · bảng phân hoạch), và **không đợt nào chạm tầng
> văn bản**, nên mọi con số §2 và §5 giữ nguyên. Cái đã đổi là **§4 tăng từ 4 lên 7 mục** và
> **§3.5 là mục mới** — bốn phát hiện truy được nguyên nhân. Ghi lại đây thay vì làm tròn lên,
> vì một báo cáo đối chiếu mà tự cải thiện điểm sau mỗi lần chạm code thì hết là thước đo.

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

### 2.4 · §6 · 13 quan hệ giữa văn bản — **2/13, và cách lưu khác hẳn**

> Bản 03/08 ghi 4/13 (đếm số `rel_type` có trong dữ liệu). Sửa xuống **2/13** ngày 04/08 sau khi
> đối chiếu từng tên — xem §3.5b: chỉ `THAY_THE` và `DAN_CHIEU` trùng tên v0.5.

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

### 3.5 · Bốn phát hiện đo ngày 04/08 — mỗi cái truy được tới một dòng code

Khác §3.1–3.4 ở chỗ: bốn cái dưới đây **không phải mâu thuẫn thiết kế**, chúng là chỗ *đã có sẵn
đường đi mà dữ liệu bị chặn giữa chừng*. Nêu riêng vì chúng rẻ và vì mỗi cái chỉ ra đúng một dòng.

**(a) `Chương` bị vứt có chủ đích, nên `Article.chapter` là trường chết — nay biết chết ở đâu.**

HTML gốc **có đủ**: quét cả 9 file trong `data/raw` được **47 Chương · 15 Mục**
(ND52 = 7/6 · TT39 = 7/0 · ND101 = 6/0 · TT18 = 6/0 · TT23-2014 = 5/0 · TT40 = 5/6 · TT17 = 4/0 ·
TT46 = 4/0 · TT15 = 3/3). Nhưng `app/ingestion/extract.py:90`:

```python
if current is not None and not _CHUONG_RE.match(ln):
    current.append(ln)          # ← dòng Chương rơi vào đây và BIẾN MẤT
```

Dòng Chương bị loại để khỏi lẫn vào nội dung Điều — hợp lý — nhưng nó **không được giữ lại đâu
cả**. Hệ quả: `Article.chapter`/`.section` khai ở `app/core/schemas.py:51-52` mà **0/278** điều có
giá trị. §2.3 gọi đây là "trường chết"; nguyên nhân là một nhánh `if`, không phải thiếu dữ liệu.

> Mức: **thấp** · Chi phí rất nhỏ, và là đường rẻ nhất để §3 node cấu trúc đi từ 3/8 lên 6/8.

**(b) Tên quan hệ LỆCH, không chỉ thiếu.** 13 instance trong `corpus.real.json`:

| trong dữ liệu | số | v0.5 gọi là |
|---|---|---|
| `THAY_THE` | 4 | `THAY_THE` ✅ |
| `DAN_CHIEU` | 3 | `DAN_CHIEU` ✅ |
| `SUA_DOI` | 2 | `SUA_DOI_BO_SUNG` ❌ — đổi tên cơ học |
| `HUONG_DAN` | 4 | ❌ **cần phán định người** |

Bốn cạnh `HUONG_DAN` (TT40 · TT15 · TT17 · TT18 → ND52) rơi đúng vào chỗ §6.3 cảnh báo: nhãn này
**gộp hai thứ mà Điều 53 khoản 2 đối xử khác nhau** — `QUY_DINH_CHI_TIET_HUONG_DAN` (ban hành theo
uỷ quyền ⇒ R5 *cùng ngày hiệu lực* áp dụng) và `HUONG_DAN_AP_DUNG` (hướng dẫn thuần tuý ⇒ **không**
áp dụng R5). Gộp lại là **báo lỗi giả** khi kiểm R5. Máy không tự tách được: đây là câu hỏi pháp lý.

**(c) `BAI_BO` = 0 instance ⇒ ca kiểm chứng bắt buộc của §6.2 sẽ chạy nhưng trả RỖNG.**

v0.5 §6.2 đặt truy vấn *legislative void* (`BAI_BO` mà không có `THAY_THE`) làm **ca kiểm chứng bắt
buộc**, kèm tiền lệ học thuật Colombo et al. Dựng đủ 13 cạnh có tên sẽ làm truy vấn **chạy được**,
nhưng kết quả rỗng vì corpus không có quan hệ bãi bỏ nào. Ghi rõ để không ai nhầm "dựng xong 13
cạnh" với "có demo": muốn demo phải **tìm một quan hệ bãi bỏ có thật** trong corpus mở rộng.

**(d) `so_hieu` đã trích được rồi bị vứt — cầu nối hai không gian ID rẻ hơn §3.3 tưởng.**

`_SO_HIEU_RE` (`extract.py:98`) kiểm lại **chạy đúng** trên cả ba dạng thử
(`52/2024/NĐ-CP` · `40/2024/TT-NHNN` · lẫn trong câu). Giá trị được `_head_text` đọc rồi **chỉ đưa
vào prompt làm ngữ cảnh**, `extract_metadata` không trả về. Thêm `so_hieu` như một **trường** trên
`DocumentMeta` (giữ nguyên `doc_id`) là việc một buổi, và nó cho A ↔ B **join được ngay** mà
**không chạm lịch sử Supabase** — khác hẳn phương án đổi `doc_id` ở §3.3.

> Mức: **trung bình** · Không thay §3.3, nhưng hạ cấp nó từ "chặn đường" xuống "dọn sau".

---

## 4. Bảy chỗ PoC đã đi TRƯỚC v0.5 — v0.6 nên hấp thụ

Không phải mục tự khen. Đây là những thứ **đo được trên văn bản thật** mà spec chưa phủ, nên
chúng là đầu vào cho bản sau chứ không phải là "code lệch spec".

| phát hiện | số đo | v0.5 nói gì |
|---|---|---|
| **Tiết `(i)`/`(ii)`** — `TietSpan` (cố ý **không** cấp id) + `DiemRef.tiet` mô hình hoá như **hậu tố**, y cách §5 xử lý `Điều 15a` | 4/586 viện dẫn đi tới cấp này, **cả 4 đều ở văn bản đã hết hiệu lực**; chữ "tiết" xuất hiện **0 lần** trong 557k ký tự corpus (`citation.py:9-16`, `schema.py:41-47`) | §3 dừng ở `Diem`, **không nhắc tiết** |
| **Điều không chẻ Khoản** — `khoan_de_trich()` sinh một khoản ảo mang `id` của chính Điều | **25/267 điều (9,4%)**, kể cả điều nội dung như Đ.9, Đ.38 ND52 (`parser.py:176-186`) | §9 #1 coi Khoản là cấp phân rã của nhóm lõi, **không nói ca này**. Trước khi có hàm này, vòng lặp chạy 0 lần và **cả điều bị bỏ qua không một lời báo** |
| **`DieuKienCong`** — parse mốc ngày **tất định bằng regex**, có `moc: bat_dau \| ket_thuc` + `char_span` round-trip | 8 cổng thời gian; ca *"có hiệu lực thi hành **đến hết ngày** 14/8/2024"* là mốc **KẾT THÚC** (`schema.py:171-197`) | §7 nói `PhienBanDieu.hieu_luc_tu` phải có, nhưng **không nói lấy ngày ở đâu ra**. Đây chính là mặt trích xuất của nó |
| **Trục tin cậy thứ hai** — `CitationRef.do_tin_cay` (cao/trung_binh/thấp) + `Grounding.status` (exact/unit/invalid) | | §8 chỉ có trục *tin cậy **nguồn***. Đây là trục *tin cậy **trích xuất*** — cùng kỷ luật, khác chiều |

### Ba mục thêm ngày 04/08 — cùng một luận điểm, đo trên văn bản thật

| phát hiện | số đo | v0.5 nói gì |
|---|---|---|
| **`GuardApDung`** — *"vế này áp dụng khi nào"* tách khỏi *"các vế kết hợp thế nào"*. Bốn trường `thuoc_tinh`/`gia_tri`/`raw_text`/`char_span`, **parser sinh 100%**, LLM không có ô nào để điền | **13 guard** (9 tầng điều kiện · 4 tầng tiết) trên 18 fixture; 3 họ thuộc tính (`khách hàng` · `tài khoản thanh toán` · `thẻ`) nên `thuoc_tinh` cố ý **không enum** | §3/§6 **không có** khái niệm điều kiện áp dụng ở cấp dưới Điều. `connector` của v0.5 chỉ trả lời câu hỏi *kết hợp*, không trả lời câu hỏi *khi nào* |
| **Bảng phân hoạch** (`data/phan_hoach.json` + `guard_phan_hoach`) — chứng minh `connector` **vô hại** thay vì hỏi lại mỗi bản ghi | 2 nhóm guard anh em; **1 chứng minh được** (`khách hàng` = {cá nhân, tổ chức}, TT17 Đ2 k2), **1 không** (`tài khoản thanh toán` còn hình thức `chung`, TT17 Đ3 k1) | v0.5 không có chỗ nào ghi *"tập giá trị này là đóng"*. Mà thiếu nó thì `(g→c)∧…` và `(g∧c)∨…` **lệch nhau** đúng ở phần bỏ sót: AND ra **miễn trừ**, OR ra **bất khả thi** |
| **Luật chapeau** (`chapeau_logic`) — câu bao trùm quyết phép nối các tiết khi tiết im lặng | 5 Điểm có tiết; 2 giải bằng liên từ hiện, **1 bằng chapeau**, 2 còn `unknown`. Chữ `"sau"` trong corpus mang **bốn nghĩa trái ngược**, dạng đông nhất là `(sau đây gọi là …)` **15+ lần** | §5 đặc tả đánh số nhưng **không nói** cấp dưới Điểm kết hợp theo phép gì, cũng không cảnh báo `"một trong các … sau"` là `any` chứ không phải `all` |

Ba mục này chung một luận điểm với bốn mục trên: **v0.5 đặc tả rất kỹ *địa chỉ* của một quy phạm
(khoá, đánh số, quan hệ giữa văn bản) nhưng chưa đặc tả *nội dung chuẩn tắc* bên trong một Khoản.**
Đó đúng là mặt mà PoC buộc phải dựng để trích được Compliance Unit, nên v0.6 hấp thụ được ngay.

Riêng ô thứ ba của bảng đầu đáng nêu với mentor: `moc` tồn tại vì nhét một ngày kết thúc vào ô tên là
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
| §6 · 13 quan hệ | **2/13** (sửa xuống 04/08 — xem dưới) · cách lưu khác kiểu ⇒ Cypher của spec không chạy |
| §7 · Tầng thời gian | **0/5** |
| §8 · Độ tin cậy | **0/2** |
| §9 · Mười quyết định | 3 đạt · 2 không đạt · 1 một phần · 4 chưa áp dụng được |

> **Một ô sửa XUỐNG ngày 04/08: §6 từ 4/13 thành 2/13.** Bản 03/08 đếm 4 vì dữ liệu có 4 `rel_type`.
> Đối chiếu kỹ từng tên (§3.5b) thì chỉ `THAY_THE` và `DAN_CHIEU` **trùng tên** v0.5; `SUA_DOI`
> phải đổi thành `SUA_DOI_BO_SUNG`, còn `HUONG_DAN` **không ánh xạ được** vì v0.5 tách nó làm hai
> quan hệ mà Điều 53 k2 đối xử khác nhau. Đếm một cạnh sai tên là đạt thì lần cutover sẽ vỡ im lặng.

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
| 8 | `PhienBanDieu`, `Chuong`/`Muc`, `VanBanKemTheo`, `PhuLuc` | — | ~~phụ thuộc #4~~ → **xem #10**: `Chuong`/`Muc` KHÔNG phụ thuộc #4 |
| 9 | Sửa changelog v0.5 §2 cho khớp bảng §5 (`so_goc` chứ không `so_khoan_goc`) | thấp | sửa spec, không sửa code |
| **10** | **Giữ dòng Chương/Mục ở `extract.py:90`** (§3.5a) — điền `Article.chapter`/`.section` | trung bình | **rất nhỏ**; 47 Chương + 15 Mục có sẵn trong HTML gốc, **0 dữ liệu tay** |
| **11** | **Bắc cầu `so_hieu` trên `DocumentMeta`** (§3.5d) — giữ nguyên `doc_id` | trung bình | nhỏ; regex đã chạy đúng, chỉ chưa trả về. **Không chạm lịch sử Supabase** |
| **12** | **Chuẩn hoá 4 tên quan hệ** (§3.5b) — `SUA_DOI`→`SUA_DOI_BO_SUNG` cơ học; 4 cạnh `HUONG_DAN` **cần người phán định** | trung bình | tiền đề của #5 |

> **Hai mục 10–11 làm đổi thứ tự phụ thuộc của #8.** Bản 03/08 xếp `Chuong`/`Muc` sau #4 (thống
> nhất ID) vì tưởng phải có `VanBan` node trước. Đo lại: `Article.chapter` là **trường phẳng trên
> Article đã có sẵn**, điền được ngay mà không cần một node `VanBan` nào — #8 tách làm hai, nửa
> rẻ đi trước.

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

### Ba lệnh thêm ngày 04/08 (§3.5 và §4)

```powershell
# --- (a) 16 Chương · 15 Mục · 11 Phụ lục CÓ trong HTML gốc, nhưng 0/278 vào được Article ---
$env:PYTHONPATH="."; uv run python -c @"
from app.ingestion.extract import read_text
from pathlib import Path
import re
t = 0
for f in Path('data/raw').glob('*.html'):
    x = read_text(f)
    n = len(re.findall(r'(?m)^\s*Chương\s+[IVXLC\d]+', x))
    t += n
    print(f'{f.name:18} Chương={n}')
print('TỔNG Chương:', t)
"@
Select-String -Path app\ingestion\extract.py -Pattern "_CHUONG_RE.match"   # dòng 90 — chỗ vứt đi

# --- (b) chỉ 2/4 tên quan hệ khớp v0.5; (c) BAI_BO = 0 instance ---
$env:PYTHONPATH="."; uv run python -c @"
import json
r = json.load(open('data/corpus.real.json', encoding='utf-8'))['relationships']
V = {'HUONG_DAN_AP_DUNG','QUY_DINH_CHI_TIET_HUONG_DAN','HOP_NHAT','SUA_DOI_BO_SUNG','DINH_CHINH',
     'BAI_BO','DAN_CHIEU','CAN_CU','GIAI_THICH','DINH_CHI_THI_HANH','TAM_NGUNG_HIEU_LUC',
     'CONG_BO','THAY_THE'}
co = {x['rel_type'] for x in r}
print('khớp tên v0.5 :', sorted(co & V))        # THAY_THE, DAN_CHIEU  → 2/13
print('KHÔNG khớp    :', sorted(co - V))        # HUONG_DAN, SUA_DOI
print('BAI_BO        :', sum(1 for x in r if x['rel_type'] == 'BAI_BO'))   # 0
"@

# --- (d) _SO_HIEU_RE chạy đúng — giá trị có, chỉ chưa trả về ---
$env:PYTHONPATH="."; uv run python -c @"
from app.ingestion.extract import _SO_HIEU_RE
print(_SO_HIEU_RE.findall('Thông tư số 17/2024/TT-NHNN và 52/2024/NĐ-CP'))
"@

# --- §4: 13 guard · 5 Điểm có tiết · 2 nhóm guard anh em ---
$env:PYTHONPATH="."; uv run pytest -q tests\test_ontology_guard.py tests\test_ontology_phan_hoach.py tests\test_ontology_chapeau_tiet.py
```

```bash
uv run python -m app.ontology --classify data/fixtures
# 94 đơn vị: 45 premise · 9 meta_cu · 40 actor_cu
```

Hai số ở §4 **không đo lại trong đợt này**, lấy từ số đo đã ghi trong code:
4/586 viện dẫn tới cấp tiết (`app/ontology/citation.py:9-16`) và 25/267 điều không chẻ khoản
(`app/ontology/parser.py:176-186`). Cả hai đo trên corpus 15 văn bản, không phải trên 18 fixture.
