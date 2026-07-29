# RAG-DESIGN — Kiến trúc RAG v2: hỏi đáp luật + kiểm tra tuân thủ

> Bản thiết kế chốt ngày 2026-07-29, kết quả brainstorm trên nền `docs/SCHEMA_KG.md` v0.4.
> Đây là căn cứ triển khai cho giai đoạn KB mới; các mục "Ngay" (§6) làm trước, không phụ thuộc KB.

## 0. Bối cảnh

Hệ hiện tại đã chạy prod: LanceDB hybrid (vector + BM25, RRF) + lọc hiệu lực `as_of` +
graph 1-hop cấp văn bản (Neo4j) + review tuân thủ từng điều. KB mới theo `docs/SCHEMA_KG.md` v0.4:
mô hình FRBR (`Dieu` là định danh bất biến, `PhienBanDieu` giữ nội dung theo thời gian), 13 quan hệ
liên văn bản, tầng `KhaiNiem`, vị từ hiệu lực nửa mở `[hieu_luc_tu, hieu_luc_den)`.
Tài liệu này thiết kế cách pipeline RAG **tiêu thụ** KB đó.

## 1. Nguyên tắc kiến trúc

1. **Neo4j là nguồn chân lý, LanceDB là chỉ mục dẫn xuất.** Mỗi row LanceDB = một `PhienBanDieu`
   (văn bản nhóm nóng) hoặc `Dieu` (nhóm cơ bản); `id` row **trùng id node KG**
   (ví dụ `40/2024/TT-NHNN#than/dieu_41@v2`). Hệ quả: nhảy từ kết quả vector sang đồ thị không cần
   bảng map, citation deep-link tự nhiên, re-index là thao tác derive lại được (idempotent).
2. **Vị từ nửa mở là bộ lọc thời gian DUY NHẤT** — nguyên văn
   `hieu_luc_tu <= T AND (hieu_luc_den IS NULL OR T < hieu_luc_den)`
   dùng ở cả Cypher lẫn LanceDB `where`. Không viết biến thể thứ hai ở bất cứ đâu.
3. **Hợp đồng truy vấn trước khi nạp dữ liệu.** 5 truy vấn Cypher ở §5 là API của KG;
   schema chỉ được coi là xong khi cả 5 chạy được trên nhóm nóng.
4. **Mọi câu trả lời mang nhãn độ tin cậy dữ liệu.** `muc_temporal`, `do_tin_cay` (cạnh),
   `nguon_hieu_luc_den` phải truyền được ra tới UI, không dừng ở trong đồ thị.

## 2. Pipeline hỏi đáp (QA)

```text
câu hỏi ──► [1] Query understanding
                ├─ regex viện dẫn (văn phạm Phụ lục I §2.b — có sẵn trong SCHEMA_KG §2.b)
                ├─ mốc thời gian trong câu ("tại 2025", "trước khi TT41 hiệu lực") → as_of
                └─ chuẩn hoá thuật ngữ qua KhaiNiem.chuan_hoa
            [2] Router
                ├─ có viện dẫn tường minh → GRAPH LOOKUP trực tiếp (Q1+Q2, không vector search)
                └─ câu hỏi ngữ nghĩa → hybrid search (vector+BM25, RRF), PREFILTER as_of
            [3] Mở rộng đồ thị cấp ĐIỀU (thay 1-hop cấp văn bản hiện nay)
                ├─ DAN_CHIEU từ các điều đã trúng — câu trả lời hay nằm sau 1 viện dẫn
                ├─ QUY_DINH_CHI_TIET_HUONG_DAN — luật gốc → thông tư chi tiết
                └─ DINH_NGHIA — kéo định nghĩa KhaiNiem của thuật ngữ trong chunks
            [4] Sufficiency check (bounded): LLM tự đánh giá đủ căn cứ chưa;
                thiếu → theo DAN_CHIEU thêm 1 hop rồi dừng (tối đa 2 vòng)
            [5] Generate + provenance: dòng xuất xứ từ TAO_PHIEN_BAN
                ("Điều 41 bản đang áp dụng có hiệu lực từ 05/11/2025
                  do khoản 3 Điều 1 TT 41/2025/TT-NHNN sửa đổi")
```

Ghi chú thiết kế:

- **[1] viện dẫn gần như miễn phí**: regex `(điểm X )?(khoản Y )?Điều Z( của <văn bản>)?` có sẵn
  trong spec; bảng phân giải *tên văn bản → số hiệu* lấy từ phần căn cứ ban hành (nguồn của `CAN_CU`).
- **So sánh hai mốc**: chạy [2]–[5] tại T1 và T2, diff phiên bản qua `KE_THUA` —
  khớp thiết kế eval 30 câu × 3 mốc.
- **Chunking**: giữ mức **Khoản**, phiên bản hoá ở mức **Điều**; header ngữ cảnh mỗi chunk =
  `văn bản — Điều X (tiêu đề) — khoản Y`. `pham_vi_thay_doi` cho biết khoản bị chạm →
  chỉ re-embed khoản đó khi sinh phiên bản mới.
- **Schema row LanceDB mới** (bổ sung so với hiện tại): `id` = id node KG, `nhanh`
  (than/kemtheo/phuluc), `hieu_luc_tu`/`hieu_luc_den` (so sánh được, dùng cho prefilter),
  `muc_temporal`, `so_phien_ban`.

## 3. Pipeline kiểm tra tuân thủ tài liệu người dùng

```text
upload (PDF/DOCX) ──► extract điều/mục (tái dùng app/ingestion/extract.py)
   ──► embed tạm thời (in-memory, KHÔNG ghi vào chỉ mục corpus)
   ──► [A] Chiều XUÔI (đã có): mỗi điều nội bộ → retrieval điều luật → verdict
   ──► [B] Chiều NGƯỢC (mới): danh mục nghĩa vụ trong phạm vi đối chiếu
             → điều nội bộ nào phủ nghĩa vụ này? → không có → finding "THIẾU"
   ──► tổng hợp: score 2 thành phần (mâu thuẫn + độ phủ) + findings hai loại
```

- **[B] là nâng cấp giá trị nhất**: tuân thủ không chỉ là "điều bạn viết trái luật" mà còn là
  "luật bắt buộc X mà quy định của bạn không nói gì". Danh mục nghĩa vụ trích một lần mỗi văn bản
  luật lúc ingest (câu chứa "phải / không được / có trách nhiệm / tối thiểu / chậm nhất…") —
  dạng tối giản của lớp deontic "Phần B": thuộc tính/node `NghiaVu` trên `Dieu`, chưa cần formal logic.
- **Chuẩn hoá thuật ngữ hai phía qua KhaiNiem**: tài liệu nội bộ hay dùng từ khác luật
  ("ví" vs "ví điện tử", "KYC" vs "nhận biết khách hàng") — map qua `chuan_hoa` trước retrieval,
  nếu không chiều [B] báo thiếu oan.
- **Verdict 4 mức**: `violation | warning | pass | not_assessed`. `not_assessed`
  (không tìm thấy căn cứ để đối chiếu) **loại khỏi mẫu số** khi tính điểm — "không biết" khác "đạt".
- **Ổn định verdict** (thực tế đã dao động 33↔17 giữa hai lần chạy cùng input):
  rubric có ví dụ ranh giới warning/pass trong system prompt, `temperature=0`,
  self-consistency: chạy 2 lần, bất đồng → lần 3 lấy đa số. Bộ eval cố định để đo drift
  giữa các phiên bản prompt.

## 4. Phản biện đã chốt (ghi lại để không quên lý do)

| # | Vấn đề | Quyết định |
|---|---|---|
| P1 | "Không tìm căn cứ → pass" thổi phồng điểm (tài liệu lạc đề = 100/100) | Verdict `not_assessed`, loại khỏi mẫu số, UI hiện riêng |
| P2 | Temporal chọn lọc: văn bản `co_ban` trả bản hiện hành cho as_of quá khứ mà không báo | Citation mang cờ `muc_temporal`; UI ghi "văn bản chưa có dữ liệu phiên bản" khi as_of ≠ hôm nay |
| P3 | Lọc hiệu lực là POST-filter — phiên bản cũ chiếm pool RRF khi có `PhienBanDieu` | Chuyển vị từ nửa mở vào `where(..., prefilter=True)` của LanceDB, làm trước khi nạp KB mới |
| P4 | Kế hoạch 6 tuần chưa có mục "app tiêu thụ đồ thị" | Tuần 2 chốt hợp đồng truy vấn (§5), tuần 3 wire vào retrieval — không đợi tuần 6 |
| P5 | GraphRAG community-summary không hợp corpus nhỏ, quan hệ tường minh | Duyệt cạnh xác định (deterministic traversal); không reranker cross-encoder ở quy mô này |
| P6 | `search_in_docs` (đường retrieval của review) chỉ có vector | Thêm nhánh FTS + RRF — đối chiếu tuân thủ nhạy khớp từ khoá chính xác ("150 triệu") |

Đồng tình giữ nguyên từ spec: nửa mở `[tu, den)`; bãi bỏ = phiên bản `noi_dung=null`;
`Diem` tạo theo nhu cầu; loại án lệ; VBHN làm ground truth chấm tự động; tách `do_tin_cay`.

## 5. Hợp đồng truy vấn KG (API của đồ thị — chốt tuần 2)

| # | Truy vấn | Input → Output | Dùng ở |
|---|---|---|---|
| Q1 | Resolve viện dẫn → node | `(điểm?, khoản?, Điều, văn_bản?)` + văn bản ngữ cảnh → id node `Dieu`/`Khoan`/`Diem` | Router [2] |
| Q2 | Nội dung điều tại mốc T | id `Dieu` + date T → `PhienBanDieu` khớp vị từ nửa mở (hoặc `Dieu.noi_dung` nếu `co_ban` + cờ `muc_temporal`) | [2], [5], review |
| Q3 | Hàng xóm cấp điều | id `Dieu` → đích `DAN_CHIEU` + `QUY_DINH_CHI_TIET_HUONG_DAN` (1 hop, kèm `do_tin_cay`) | [3], [4] |
| Q4 | Chuỗi phiên bản + xuất xứ | id `Dieu` → các `PhienBanDieu` theo `KE_THUA` + văn bản nguồn qua `TAO_PHIEN_BAN` | [5] provenance, so sánh 2 mốc |
| Q5 | Định nghĩa khái niệm | thuật ngữ (đã `chuan_hoa`) → `KhaiNiem` + điều nguồn `DINH_NGHIA` | [1], [3], review |

Tiêu chí nghiệm thu: cả 5 chạy được trên cụm nóng TT 40/2024 ← 41/2025 ← 22/2026
(chuỗi 3 phiên bản Điều 41) và cụm TT 17/2024 ← 25/2025 (Điều 15a — ca hậu tố).

## 6. Không làm (chống phình phạm vi)

Fine-tune embedding tiếng Việt · cross-encoder reranker · agentic loop >2 vòng ·
GraphRAG community-summary · lớp không gian (đã loại trong spec) · formal deontic logic đầy đủ
(chỉ `NghiaVu` tối giản cho chiều [B]).

## 7. Lộ trình (khớp kế hoạch 6 tuần của SCHEMA_KG §7)

| Khi nào | Việc phía RAG/app | Phụ thuộc |
|---|---|---|
| **Ngay** (trước KB mới) | P1 `not_assessed` · P6 hybrid cho `search_in_docs` · ổn định verdict (§3) | không |
| Tuần 2 | Chốt hợp đồng truy vấn (§5) · schema row LanceDB mới (§2) | KG tuần 2 |
| Tuần 3 | P3 prefilter · router viện dẫn · graph expansion cấp Điều | nhóm nóng nạp xong |
| Tuần 4 | Provenance answer (`TAO_PHIEN_BAN`) · cờ `muc_temporal` ra UI (P2) · KhaiNiem vào QA + review | tầng KhaiNiem |
| Tuần 5 | Chiều [B] coverage cho review · eval 30 câu × 3 mốc · eval review (cài mâu thuẫn + hố thiếu chủ đích) | danh mục NghiaVu |
| 6 tuần+ | Upload tài liệu người dùng tự do (extract + embed tạm) | luồng [A]+[B] ổn |

Mọi thay đổi retrieval verify bằng `uv run pytest -q` + benchmark 36 case không tụt
(stale-avoidance 36/36 là gate hồi quy).
