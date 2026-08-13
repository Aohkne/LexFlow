# Worklog — LexFlow (VAIC 2026, đề SHB)

> Nhật ký công việc hằng ngày, dùng để tổng hợp báo cáo mentor cho giai đoạn 3 sprint (mốc đánh giá tại SHB ~04/09/2026, lộ trình gốc trong `docs/ROADMAP-SPRINT.md`).
>
> **Cách ghi:** mỗi ngày một mục, mới nhất trên cùng. Mỗi mục gồm: việc đã xong (Done), trạng thái deploy (Ship), quyết định quan trọng (Decision), việc kế tiếp (Next). Cuối tuần/cuối sprint chỉ cần gộp các mục lại là thành báo cáo.

---

## 2026-08-13 (T4) — POC GraphCompliance chạy thật: recall 0/4 cả hai đường, và con số 0 biết nói

- **Done (POC GraphCompliance, 11→13/08, nhánh `feat/ai-compliance`).** 14 task
  subagent-driven theo spec/plan ở `.superpowers/sdd/2026-08-11-graphcompliance-poc/`:
  schema thêm tình thái 6 nhãn (regex tất định, không LLM) + ngưỡng `Nguong` kèm giao thức
  ca-lạ (T1–3); trích CU targeted 49 bản ghi (T4); parse docx hợp đồng kèm comment luật sư
  (T5–6); gold 95 nhãn chủ repo duyệt (T7); Policy Graph in-memory (T8); ER-triples grounding
  nguyên văn (T9); hypernym danh sách ứng viên đóng (T10); gate tất định (T11); judge
  self-consistency 2 vòng + override miễn trừ Eq. 6 (T12); CLI báo cáo side-by-side + recall
  (T13); chạy thật 2 hợp đồng (T14). **854 test xanh, ruff sạch.**
- **Done (giải án "PAYFAC chết im lặng" — 4 lần chạy 12/08 không để lại vết).** Chạy lại có
  hứng stderr thì ra **hai** thủ phạm chồng nhau: (1) LanceDB Cloud đứt kết nối thoáng qua
  trong `run_review` (đường cũ), retry mặc định của client 3×/0.25s quá mỏng — nâng qua env
  `LANCE_CLIENT_*_RETRIES=6`, `BACKOFF_FACTOR=1`, không sửa mã; (2) bug tất định: LLM trả
  triple có chủ thể/đối tượng **rỗng**, chuỗi rỗng là substring của mọi text nên lọt qua
  grounding nguyên văn, xuống `embed_query("")` → Gemini 400. Vá tại gốc `er_triples.py`
  (chặn + cảnh báo, commit `a4f59f4`). Lần chạy sau: 2 blip LanceDB được retry nuốt gọn,
  báo cáo sinh đủ.
- **Số đo (2 báo cáo local, không commit):** mẫu số chính = 4 comment `phap_ly` viện dẫn
  tường minh + trong corpus. **Đường mới 0/4 — đường cũ cũng 0/4** (pass cả 4 điều liên
  quan). Số "bắt được 1" trong báo cáo thô là artifact khớp chéo giữa 2 hợp đồng — CLI nay
  lọc gold theo file hợp đồng nên lần đo sau hết bẫy này. Nguyên nhân 0/4 đường mới đo được: cả 4
  comment viện dẫn Đ3 NĐ52 · Đ3 TT18 · Đ8 TT40 · Đ20 TT15 — **không điều nào trong 12 Điều
  đã trích CU** (CU trích 11/08, gold chốt 12/08). Con số 0 đang đo độ phủ, chưa đo trí tuệ
  của gate/judge.
- **Decision.** Không kết luận hơn/kém giữa hai đường từ 0/4=0/4; bước rẻ nhất để số recall
  có nghĩa là trích CU đúng 4 điều gold viện dẫn rồi chạy lại (~4 lượt LLM). Ghi ở T26.
- **Done (review cuối toàn nhánh + vệ sinh trước push).** Review toàn dải `cc6ac199..HEAD`:
  các cam kết chống bịa xác nhận có trong mã, không lọt nội dung hợp đồng vào commit nào.
  Một đợt sửa duy nhất theo finding: lọc gold theo file hợp đồng trong CLI (hết phồng mẫu
  số recall), cổng `chu_the` khẳng định fail-open có cờ thay vì rơi im lặng, thêm test nhánh
  judge bỏ sót CU — re-review xác nhận đủ. Vệ sinh: tên riêng của chuyên viên pháp chế trong
  file spec bị phát hiện ở history **chưa push** → viết lại history local xoá hẳn (chủ repo
  duyệt), nhãn tác giả đối tác trong fixture test thay bằng nhãn chung.
- **Done (bước T26: trích 4 điều gold viện dẫn + chạy lại cả 2 báo cáo).** Hai điều định
  nghĩa (Đ3 NĐ52, Đ3 TT18) đúng vai `premise` — không sinh actor-CU (phát hiện cấu trúc:
  comment viện dẫn định nghĩa nằm ngoài tầm gate CU). Hai điều còn lại sinh **12 CU mới**
  (TT15-Đ20, TT40-Đ8) → `pred.jsonl` 61 bản ghi, 2 lỗi cứng chống-bịa bị loại ⇒ graph
  **59 CU**; suite 855 xanh (2 tripwire điều tra dân số soi tay rồi cập nhật đúng lệ).
- **Done (giải án "chết giữa batch dài" — 3 lần chạy lại chết 3 kiểu).** RetryError 3/3 dù
  đã set env retry=6 ⇒ **env `LANCE_CLIENT_*` không tới tầng Rust của client** — truyền
  `retry_config` tường minh tại `vectordb.connect()` (commit `e6fc1e2`); crash native
  `0xc0000005` trong `msvcrt.dll` (soi Windows Event Log — giải thích luôn vì sao "chết im
  lặng" không có traceback); và `HttpError: connection reset` bị client ném thẳng **không
  retry** (chỉ retry lỗi có mã HTTP) — bọc `_vector_hits` retry 5/15/45s dùng chung cho
  `hybrid_search`/`search_in_docs`, kèm test (commit `233bd80`). Sau vá: cả ThuHo (~22')
  lẫn PAYFAC (~45') chạy trọn.
- **Số đo lại (13/08 tối): ThuHo 0/1 · PAYFAC 0/3 — nhưng từng miss quy được nguyên nhân.**
  #30: chunk TT15-Đ20-k3 xếp hạng 5/8 retrieval, k1/2/4/5 được judge — CU khớp comment là
  k3, đúng bản ghi lỗi cứng bị loại; #13/#35: cấu trúc (điều định nghĩa không có actor-CU);
  #194: thân Điều 4 HĐ chỉ 243 ký tự (nội dung ở Phụ lục) → top-8 không có chunk TT40-Đ8
  (đo bằng probe `search_in_docs`). Tín hiệu đúng hướng: ThuHo Đ2 ra `thieu_thong_tin` trên
  TT40-Đ8 k5/k7 — trùng chủ đề lawyer nêu, khác văn bản cite nên không tính điểm. Chi tiết
  + bước kế tiếp 3 nhóm ghi ở **T26**.
- **Ship.** Không deploy. Sáng: push 26 commit lên PR #19 (chủ repo duyệt, fast-forward
  `5c0e9fd..9c71656`). Tối: thêm 4 commit local chưa push (`9f36b4e` CU mới, `e6fc1e2` +
  `233bd80` vá retry, docs lượt này) — chờ chủ repo quyết.
- **Next.** Hỏi chủ repo về push đợt tối; việc mở tiếp theo của T26: sửa 2 bản ghi CU lỗi
  cứng (rẻ, gỡ ngay #30), cân nhắc gate mức toàn-hợp-đồng cho CU "hợp đồng phải có tối
  thiểu..." (gỡ #194).

## 2026-08-10 (CN) — mã, dữ liệu và đồ thị khớp nhau; và một cạnh tác động không có thật

- **Done (compliance — `conflict_recall` 6/7 → 7/7).** Ca trượt là *"Số dư tối đa trên thẻ trả
  trước vô danh là bao nhiêu?"* (nội bộ SHB 20 triệu vs TT18-2024 Đ13.4 trần **5 triệu**). Loại
  trừ bằng đo chứ không suy: truy hồi lấy **đủ cả hai phía**; bỏ sót **5/5 lần** nên không phải
  nhiễu; gọi thẳng `chat_json` với **đúng prompt hiện tại** thì bắt được **3/3**. Thủ phạm nằm
  ở hậu xử lý — mô hình trả `"TT18-2024::Điều 13 Khoản 4"`, tức địa chỉ **chi tiết hơn** nhãn
  chunk `"TT18-2024::Điều 13"`, `by_id.get()` trượt rồi `continue` **trong im lặng**. Bộ phát
  hiện đang phạt mô hình vì trích dẫn chuẩn hơn nhãn nó được đưa. Nay quy id theo tiền tố có
  ranh giới dấu cách, khớp nhiều chunk thì bỏ chứ không đoán, không quy được thì **ghi log**.
  PR #16, 4 test mới, CI xanh.
- **Benchmark lại 36 câu** (`eval/results/20260810-073306.json`), **12,1 phút**:

  | | 06/08 | 10/08 |
  |---|---|---|
  | Phát hiện mâu thuẫn | 6/7 | **7/7** |
  | Citation accuracy (baseline / hybrid / +graph) | 36/36 | 35/35 cả ba |
  | Tránh văn bản hết hiệu lực (baseline → LexFlow) | 21/36 → 36/36 | 21/35 → **35/35** |
  | Latency retrieval p50 | 5.028 ms | **3.970 ms** |
  | Router: câu OFF/ON khác nhau · hit nắn trích dẫn | 0/36 · 8 | 1/35 · 10 |

  **1/36 câu lỗi** (*"Ai được mở tài khoản thanh toán…"*) — `HttpError` khi gọi LanceDB Cloud,
  lỗi mạng thoáng qua, bị loại khỏi mẫu số đúng theo thiết kế của `run_benchmark`. Con số
  router đổi (1/35 · 10) là do artefact lớp phủ đã sinh lại còn **177 cạnh** kèm bản vá
  chunking, không phải do router đổi hành vi.
- **Chi phí một lượt benchmark — đo thật, không ước.** Bọc `client.models.generate_content` /
  `embed_content` để đọc `usage_metadata` của chính response:

  ```
  gemini-2.5-flash-lite   14 lượt   38.095 token vào · 7.593 token ra
  gemini-embedding-001    36 lượt   ~723 token (ước từ 2.529 ký tự — API embed
                                     không trả usage_metadata)
  ```

  Theo bảng giá paid tier (flash-lite $0.10 vào / $0.40 ra, embedding $0.15 — mỗi 1M token):
  **≈ 0,0070 USD ≈ 181 VNĐ cho cả lượt 36 câu**, tức ~0,19 USD nếu chạy 1.000 câu cùng dạng.
  Chi phí **không phải** thứ đáng cân nhắc khi quyết có chạy benchmark hay không; 12 phút đồng
  hồ mới là cái giá thật.
- **Phát hiện kèm theo: đường phán định đang chạy `gemini-2.5-flash-lite`, không phải
  `gemini-2.5-pro`.** `config.py` mặc định `gemini_reasoning_model = "gemini-2.5-pro"` nhưng
  `.env` đặt `GEMINI_REASONING_MODEL=gemini-2.5-flash-lite`, và `.env` thắng. Nghĩa là
  conflict detector + review tuân thủ — hai chỗ phán định pháp lý nặng nhất — đang chạy trên
  model rẻ nhất họ Gemini, còn **chưa ai đo** xem đổi lên `pro` thì được gì. Đáng đo, vì với
  0,007 USD/lượt thì phép so sánh gần như miễn phí.
- **Done (T2 — id chunk phải định danh đúng một chunk).** `TT23-2019 Điều 1` là điều *sửa đổi*
  dài 55.902 ký tự, chép nguyên văn nhiều điều của TT39-2014 nên số khoản **khởi động lại
  nhiều lần** trong cùng một điều. Chunker thấy một điều phẳng và đúc ra cùng một nhãn ba lần
  ⇒ **5 id / 7 hàng đụng nhau**. Vì `_rrf()` gom kết quả vào `dict` khoá bằng `id`, một hàng bị
  nuốt và trích dẫn trỏ tới một địa chỉ mang ba nội dung khác nhau. Nay nhãn trùng được thêm
  hậu tố thứ tự (`Điều 1 Khoản 2 (2)`), và nhãn dải kiểu `"Khoản 18-1"` — vốn tuyên bố một dải
  chạy ngược từ 18 về 1 — rơi về số khoản đầu.
- **Done (T1 — re-ingest).** LanceDB Cloud: **661 hàng / 661 id phân biệt** (trước: 654 id).
  Neo4j về đúng số cũ: 26 `Document` · 293 `DonVi` · 255 `THUOC` · 178 `TAC_DONG` · 35 cạnh
  văn bản.
- **Hai cái bẫy lộ ra giữa lượt ingest, đều đã bịt.** (1) `ingest_docs` **không** gọi lại
  `push_overlay` sau `push_corpus`, mà `push_corpus` mở đầu bằng `DETACH DELETE` trên
  `Document` — xoá luôn 255 cạnh `THUOC`. Node `DonVi` và cạnh `TAC_DONG` sống sót nên đồ thị
  *trông vẫn đủ*, chỉ mất sạch đường nối về văn bản, không một lời báo. Yêu cầu này trước nay
  chỉ nằm trong docstring dặn người chạy nhớ. (2) Aura **rớt kết nối giữa chừng** ở 221/255
  cạnh vì `push_overlay` chạy ~764 round-trip lẻ trong một session — gộp lô bằng `UNWIND` còn
  3 câu lệnh.
- **Verify (trên chính dữ liệu đang phục vụ, không nhìn exit code).** `TT66-2025 Điều 6` hết
  cắt giữa từ. Bốn chunk từng đụng chung id lộ ra là **bốn điều khoản khác hẳn nhau** — thông
  tin khách hàng mở Ví · hạn mức BTĐT · quyền và trách nhiệm ngân hàng hợp tác — tức va chạm cũ
  đúng là có hại thật. Hybrid search trả 4 hit bình thường ⇒ chỉ mục FTS sống sót qua lượt ghi
  đè.
- **Ship.** `3219fba`, `f3ccf2f`. Cloud Run rev **`00021-jvs`** (100% traffic). 737 test xanh,
  ruff sạch, CI xanh.
- **Verify sau deploy.** `/health` không phân biệt được revision cũ với mới (khối `overlay` đã
  có từ bản trước), nên nghiệm thu bằng thứ đúng chỗ: tra 10 nhãn có hậu tố **trên bảng LanceDB
  đang phục vụ** — **10/10 giải được** bằng mã mới, **0/10** bằng regex cũ; cả 10 rơi về khoá
  cấp điều `23/2019/TT-NHNN#than/dieu_1`, đúng thiết kế.
- **Decision.** Không đổi model embedding sang `paraphrase-multilingual-mpnet-base-v2`. Nó
  cũng 768 chiều nên schema không phải đổi, nhưng cửa sổ **128 token** so với ngưỡng
  **~7.156 ký tự** vừa đo được của Gemini nghĩa là gần như *toàn bộ* 661 chunk sẽ mất đuôi
  (median chunk 1.044 ký tự). Thêm nữa, đổi model là đổi **cả hai đầu** — vector câu hỏi phải
  cùng không gian với vector chunk — nên Cloud Run (512Mi) sẽ phải gánh torch + 1,1 GB trọng
  số. Và chưa có bộ câu hỏi chấm điểm thì đổi xong cũng không biết tốt lên hay xấu đi.
- **Đính chính.** Ghi chép 09/08 đoán "sửa T2 thì T3 tan theo" — **sai**. T2 chỉ đổi nhãn,
  không chẻ nhỏ thêm; chunk quá cỡ vẫn còn, mang tên mới `TT23-2019::Điều 1 Khoản 6 (2)`
  (9.750 ký tự, mất ~2.594). Muốn hết phải chẻ *bên trong* một khoản ⇒ thêm một lượt re-ingest.
- **Done (T8 — BM25 chấm cụm, không chỉ chấm túi-từ).** Chỉ mục cũ dựng bằng **mặc định tiếng
  Anh** (stemmer Snowball + stop-word Anh, mà `ascii_folding` bỏ dấu *trước* khi lọc nên từ
  Việt rơi đúng vào danh sách đó) và **không lưu vị trí token** nên không truy vấn cụm nào khả
  thi. Nay `PhraseQuery` đứng cạnh `MatchQuery` ở mức `SHOULD`: precision@10 của riêng nhánh
  BM25 đi từ **8,4 → 9,9/10** trên 14 cụm có thật trong corpus. Dựng lại chỉ mục **không
  embedding lại chunk nào**. Rev `lexflow-api-00022-242`. Giới hạn đã ghi rõ: mọi endpoint chạm
  truy hồi đều đòi đăng nhập nên chưa chứng minh được bằng một lượt truy vấn thật qua
  production — mở **T19** cho khoảng mù đó.

### Nhánh software

- **Done (cạnh tác động GIẢ — 178 → 177).** Span mệnh lệnh của khoản cuối chạy tới hết văn bản
  nên nuốt luôn **khối kết** (`Nơi nhận:` + chữ ký); dòng `- Như Điều 5;` trong danh sách nơi
  nhận bị đọc thành trích dẫn, đẻ ra một cạnh `bai_bo` **không hề tồn tại**:
  `22/2026/TT-NHNN Điều 6 khoản 2 → 40/2024/TT-NHNN Điều 5`. Vá bằng `_che_khoi_ket`: **che
  khối kết bằng dấu cách chứ không cắt**, vì `char_span` tính theo offset tuyệt đối — cắt là
  lệch mọi span phía sau. Bỏ đúng 1 cạnh, không thêm cạnh nào, 142 cạnh có chữ giữ nguyên.
- **Done (đẩy lại lớp phủ lên Neo4j).** Đây là bước dễ bỏ sót nhất: `push_overlay` **toàn
  `MERGE`** nên nó chỉ THÊM — chạy lại một mình sẽ để nguyên cạnh giả và không ai biết. Nên đo
  trước: đồ thị **178 cạnh / 293 nút / 255 THUOC** so với artefact **177 / 292**, thừa đúng 1
  cạnh và 1 nút, thiếu 0. `DETACH DELETE` nút thừa gỡ 2 quan hệ chạm nó (cạnh `TAC_DONG` giả +
  cạnh `THUOC` của nó), rồi đẩy lại. Sau: **177 / 292 / 254**, so lại hai chiều đều bằng 0.
- **Done (trình xem toàn văn).** Thanh định vị dính đầu trang + mục lục mở khi cần + chỉnh cỡ
  chữ và độ rộng cột. Neo mục lục phải mang tên chương cha vì "Mục 1" lặp lại ở mỗi chương —
  kiểm trên cả 22 file corpus: không neo nào trùng, không Điều nào sót.
- **Done (giao diện điều bị tác động).** Mỗi tác động chỉ hiện **một lần**, và dấu cấp điều neo
  vào **tiêu đề Điều** chứ không vào đoạn dẫn — đo ra **10/16** tác động cấp điều rơi vào Điều
  không hề có đoạn dẫn, để ở đoạn dẫn là mất hơn nửa. Bảng đối chiếu tra ra nguyên văn 86/104
  đơn vị; 16 trong 18 còn lại là `bo_sung` nên vốn chưa tồn tại trong bản gốc, 2 ca cuối là
  khuyết tật nguồn → **T16**.
- **Done (T16 — ghi sổ khuyết tật nguồn, không tự đoán).** Hai đơn vị mất/lệch nút vì vbpl.vn
  phát `<p>` layout Tailwind thay vì `prov-*` — **soi DOM xác nhận**, không suy từ JSON đã
  parse. Chữ không mất, chỉ mất nhãn ngữ nghĩa. Thêm `check_unit_sequence` bắt được ca "tổng số
  Điểm vẫn đúng nhưng treo nhầm cha" mà phép đếm tổng mù hoàn toàn: chạy trên 14 văn bản ra 3
  cảnh báo, đều thuộc TT15-2024, 13 văn bản còn lại sạch. **Không vá bằng cách đoán** — chính
  nguồn đang tự mâu thuẫn, suy nút từ tiền tố là chuẩn hoá ngầm mà dự án cấm.
- **Ship.** PR **#13** (`1584502`, `8d2af3c`, `5be4aea`) và PR **#14** (`1d4aa87`) đã merge; ba
  commit dọn dẹp `40d7d0a`/`59fd303`/`be97441`.
- **Decision (quy ước push).** Track AI thôi đẩy thẳng vào `main`; **mỗi track một nhánh, một
  worktree, và `main` chỉ nhận qua PR**. Lý do là sự cố có thật chứ không phải nguyên tắc suông:
  `main` nhận thêm commit trong lúc PR #11 đang mở, PR merge mà thiếu phần push sau đó, hai
  commit mắc lại tới khi tình cờ phát hiện. Dựng worktree `../LexFlow-ai` (736 test xanh) và ghi
  luôn vào `COMMIT-CONVENTION.md` thủ tục git không mang theo được: `.env`, `uv sync`, và
  **junction** trỏ `data/raw/vbpl/raw/` về một checkout duy nhất — riêng cái junction un-skip 52
  test vốn đang bị bỏ qua.
- **Ship (deploy bù 12 commit tồn đọng).** Production đang chạy revision build từ `3f02a23`,
  tức **hai thay đổi hành vi chưa tới người dùng**: bộ lọc `chi_noi_bo_voi_luat` (`9328dbf`,
  precision cặp 0,145 → 0,615) và quy id theo tiền tố (`3751d91`, recall 6/7 → 7/7). Deploy
  rev **`lexflow-api-00024-jsv`**, 100% traffic; `/health` trả `overlay.nap=true ·
  so_canh=177 · sinh_luc=2026-08-09` — đúng artefact đã sinh lại, khớp con số lệch một đã báo
  trước (prod trước đó phục vụ 178 cạnh từ cây trước rebase). **Giới hạn nghiệm thu, ghi rõ:**
  mọi endpoint chạm truy hồi đều sau `get_current_user`, nên chỉ chứng minh được image đã
  roll, **không** chạy được hành vi bộ lọc từ ngoài — đúng khoảng mù **T19**.
- **Done (soi tầng chuẩn tắc → T26).** Câu hỏi: KB có thành phần nào trích premise /
  Compliance Unit / meta-CU không. **Có** — `app/ontology/schema.py` định nghĩa đủ `ActorCU`,
  `MetaCU`, `PremiseRecord`, `KhaiNiem`, `Gate`, `DieuKienCong`, kèm phân vai tất định và ba
  tầng chống bịa. **Nhưng nó không nối vào đâu cả**: không ở LanceDB (chunk có đúng 10 cột),
  không ở Neo4j (chỉ `:Document` + `:DonVi`), không ở đường phục vụ (`review.py`/`conflict.py`
  đều nối `text` thô ném thẳng cho LLM). Chạy ngoại tuyến qua `python -m app.ontology`, phủ
  **49 CU trên 12 Điều / 4 văn bản**, mà một trong bốn còn **không có trong corpus** ⇒
  **8/425 Điều ≈ 1,9 %**, và **0/94 nhãn người gán**. Phát hiện đáng giá nhất là lỗ hổng
  schema: **không có ô ngưỡng/số nào**, trong khi cả 5 cặp vàng đều là số chọi số và T24 hỏng
  đúng ở một cặp số — nên schema phải đi trước độ phủ.
- **Decision.** Hoãn cả ba hướng (thêm ô ngưỡng+tình thái · mở rộng độ phủ · nối CU vào phán
  định); chỉ ghi sổ. Lý do: chưa có nhãn người gán thì mọi cải tiến ở tầng này vẫn là máy tự
  chấm máy — đúng câu hỏi #1 đang chờ mentor trả lời.
- **Next.** (1) Không còn mục nào chặn. (2) **T5** là rủi ro lớn nhất còn lại cho kỳ đánh giá:
  luồng duyệt văn bản qua `/admin` **chưa từng chạy thật** trên production (bucket `legal-docs`
  rỗng, `legal_documents` rỗng), mà đó là tính năng sẽ được nhìn. (3) **T19** — không có cách
  nghiệm thu nhánh truy hồi trên production mà không cần đăng nhập; đúng khoảng mù mà T9 đã bịt
  cho lớp phủ, chỉ khác tầng. (4) `docs/ARCHITECTURE.md` không hề nhắc tới lớp phủ — cả một tầng
  kiến trúc đã lên sản phẩm mà tài liệu kiến trúc không biết.

---

## 2026-08-09 (T7) — dọn ba chỗ "hỏng lặng lẽ", và một cuốn sổ nợ

- **Done (chunk cắt giữa từ).** Điều dài mà regex khoản không bắt được cấu trúc thì bị cắt
  **cửa sổ ký tự cứng**. Ca thật duy nhất trong corpus: `TT66-2025 Điều 6` (4.313 ký tự) — một
  điều *sửa đổi* đánh số ở cấp điểm/tiểu mục (`đ)`, `(i)`…`(vii)`) chứ không phải khoản. Vết
  cắt ở vị trí 4.000 chẻ đôi chữ **"ngân"** thành `ngâ` + `n`, mà điều này lại nằm trên đường
  nóng của lớp phủ nên chữ kéo vào prompt mở đầu bằng nửa câu. Vá bằng hai lớp: **thang bậc cấu
  trúc** (điểm → tiểu mục → gạch đầu dòng) và **lưới ranh giới dòng/câu/từ**. Nhãn giữ nguyên
  `(phần k)` ở mọi bậc dưới khoản — `đ)`/`(i)` trong một điều sửa đổi là chữ TRÍCH của văn bản
  bị sửa, gắn nhãn "Điểm đ" cho nó là khai man địa chỉ pháp lý.
- **Số đo.** 651/654 chunk id giữ nguyên **từng byte**, 0 id thêm/mất, chỉ 3 mảnh của
  `TT66-2025 Điều 6` đổi ⇒ bộ nhãn lớp phủ và benchmark đã đo không phải làm lại.
- **Done (T3 — đo giới hạn embedding).** `scripts/do_gioi_han_embed.py`: gắn câu mốc vào cuối
  chuỗi rồi so vector, mốc không làm đổi vector nghĩa là nó không tới được model. Kết quả:
  **ngưỡng ~7.156 ký tự**, chỉ **1/661 chunk** vượt. Tức `_MAX_CHUNK = 2000` là lựa chọn về
  **độ chính xác retrieval**, không phải ràng buộc của API — trần thật cách nó hơn ba lần.
- **Done (T10 — một nguồn ánh xạ `doc_id`).** `dong_goi` đã đóng băng bảng `so_hieu_theo_doc`
  vào artefact, nhưng `lop_phu.tach_khoa` vẫn **suy lại** `doc_id` từ số hiệu theo quy ước.
  Lệch 4/26 văn bản (toàn nhóm nội bộ SHB). Nặng hơn: với 9 văn bản **ngoài corpus**, quy ước
  **bịa** ra mã trông y hệt mã thật (`ND135-2015`, `TT19-2016`) khiến web dựng link `/docs/{id}`
  tới trang trống. Nay tra bảng, không có thì trả `None`. Ba call site còn lại nằm sâu trong
  khoá sắp xếp và hàm dựng câu trích — thay vì refactor rộng cho một lỗi tác hại bằng 0, đặt
  một **test dây bẫy** đỏ đúng ngày điều đó hết đúng.
- **Done (T9 — lớp phủ hỏng lặng lẽ).** `/health` nay có khối `overlay` (`nap`, `so_canh`,
  `sinh_luc`), `status` xuống `degraded` khi lớp phủ bật mà artefact không nạp được, và log một
  dòng lúc khởi động. HTTP vẫn 200 ở mọi ca — không có gì đọc endpoint này bằng máy, đổi thành
  mã lỗi là biến cảnh báo thành sự cố triển khai.
- **Chạy server thật cứu một bàn.** Test xanh hết nhưng chạy `uvicorn` thì **dòng log không hề
  tồn tại**: uvicorn chỉ cấu hình logger `uvicorn.*`, mọi record `app.*` mức INFO rơi vào hư
  không. `basicConfig` cũng không cứu được vì nó là no-op khi root đã có handler — đúng tình
  huống dưới pytest. Phải đặt mức thẳng trên namespace `app`, và ca test nay assert
  `isEnabledFor(INFO)` trước khi xét nội dung, vì `caplog` tự gắn handler nên sẽ xanh trong khi
  ngoài đời log mất hút.
- **Ship.** `8dd53f0`, `83ac6dd`, `27abe0d`, `85c9467`. 730 test xanh, ruff sạch, CI xanh.
- **Decision.** Lập `docs/TASKLIST.md` — sổ ghi việc **đã biết nhưng chưa làm**, mỗi mục kèm
  *vì sao quan trọng*, *bước đầu tiên cụ thể* và **ngày đo** của mọi con số, để một số liệu cũ
  nhìn ra là cũ thay vì được tin. Khác `ROADMAP-SPRINT.md` (kế hoạch theo sprint) và worklog
  này (nhật ký theo ngày): nó tổ chức theo *cái gì còn mở*, và teo dần khi đóng mục.
- **Next.** Re-ingest LanceDB để hai bản vá chunking tới được dữ liệu đang phục vụ (T1 + T2).

---

## 2026-08-07 (T6) — thuộc tính văn bản: 1/26 → 14/26, và đường lên canonical

- **Done.** Bản crawl vbpl.vn có đủ bảng Thuộc tính cho 22 văn bản, nhưng corpus canonical chỉ
  mang thuộc tính của **TT15-2024** — `scripts/enrich_corpus_from_vbpl.py` ghép **từng file
  một** và 13 văn bản còn lại chưa bao giờ được chạy qua. Thêm chế độ `--tu-thu-muc` khớp cả
  thư mục theo `doc_id`, và bổ sung `source_files` vào danh sách trường được chép — thiếu nó
  thì endpoint tải file gốc của #10 không có gì để phục vụ.
- **Số đo.** Độ phủ thuộc tính **1/26 → 14/26** văn bản (`co_quan_ban_hanh`, `nguoi_ky`,
  `chuc_danh`, `ngay_ban_hanh`, `tinh_trang_hieu_luc`, `source_url`, `source_files`);
  `provisions` 1/26 → **13/26**. Badge cấp khoản gắn được vào cây điều khoản **26/124 → 104/124**
  đơn vị bị tác động; 20 mục còn lại thuộc ND101-2012 (16) và TT39-2014 (4) — hai văn bản **chưa
  cào**, nên chưa có cây để gắn. 12 văn bản chưa có thuộc tính = 4 quy định nội bộ SHB (vbpl.vn
  không có) + 8 văn bản ngoài chưa cào.
- **Kiểm trước khi ghi.** Dựng lại 22 bản corpus từ `raw/` bằng parser ở HEAD: **0/22 lệch** so
  với bản dump 05/08 ⇒ bản đang ghép đúng là bản parser hiện tại sinh ra. Sau khi ghép:
  `doc_id`/`title`/hiệu lực/`articles`/`relationships` **giữ nguyên từng byte**, 26/26 văn bản
  vẫn hợp lệ với `DocumentDetail`.
- **Decision.** `articles`/`title`/hiệu lực không bao giờ nhận từ bản crawl. Ca cụ thể:
  crawl **ND52-2024** mang `valid_from: 2027-07-01` trong khi corpus curate tay ghi
  `2024-07-01` — chép sang là đẩy một nghị định đang hiệu lực ra tương lai.
- **Ship.** `a2ff265`, `0a4f06d`. 704 test xanh, ruff sạch, CI xanh cả hai commit.
- **Chưa tới production.** Backend đọc canonical **trên Supabase Storage** (file trong image chỉ
  là fallback), nên sửa local chưa đổi gì ở prod. Mở rộng `scripts/sync_corpus_storage.py`: ngoài
  anchors, nay bổ sung cả thuộc tính/cây/file gốc, **chỉ thêm không xoá** (văn bản chỉ có trên
  canonical vẫn còn, `articles` trên Storage là bản đã duyệt nên không đụng), sao lưu canonical
  về `data/backup/` trước khi ghi đè, có `--dry-run`. Chạy được cần tài khoản admin Supabase.
- **Next.** (1) Chạy sync canonical bằng tài khoản admin → xác minh `/documents/TT40-2024` trên
  prod có `co_quan_ban_hanh`/`source_files`. (2) Cào 8 văn bản ngoài còn thiếu (ND101-2012,
  TT17-2024, TT18-2024, TT20-2016, TT23-2014, TT23-2019, TT39-2014, TT46-2014) — `vbpl search`
  không tìm ra URL của chúng qua sitemap, phải lấy URL tay.

---

## 2026-08-06 (T5) — đợt 5: nối lớp phủ vào sản phẩm (P4), 10 task subagent-driven TDD

- **Done.** Lớp phủ dưới-văn-bản đi hết đường từ artefact tới UI: `app/ontology/dong_goi.py`
  đóng gói 178 cạnh thành `data/overlay/lop_phu.json` **tự chứa** (giải span `loi_van_moi` thành
  chữ ngay lúc build, vì `data/raw/vbpl/` gitignored nên runtime không bao giờ giải được);
  `app/knowledge/lop_phu.py` là **cổng runtime duy nhất** bọc `dinh_tuyen`/`phien_ban_hien_hanh`,
  fail-open; `answer.py` gắn nhãn hiệu lực cấp khoản vào prompt + `Citation`; `review.py` không
  còn phán tuân thủ trên luật đã chết; `GET /documents/{id}` trả `tac_dong` cấp khoản; web hiện
  badge ở 3 màn; `push_overlay` đẩy bản sao lên Neo4j để xem.
- **Ship.** 16 commit `e21c50f..14b2901`. **Ingest:** LanceDB Cloud 449→**661 chunk**, 15→**26
  văn bản**. **Neo4j:** 293 `DonVi`, 178 `TAC_DONG`, 255/293 `THUOC`. **Cloud Run** rev
  `00016-n6k`, **Vercel** production + alias `lexflow-taupe`. 588 test xanh, ruff sạch.
- **Verify prod (e2e qua `_prepare` thật).** `TT41-2025::Điều 10` → `la_loi_sua` → trích dẫn nắn
  về **đúng chủ**: *"TT40-2024 Điều 26 Khoản 1 (sửa bởi TT41-2025 Điều 10 Khoản 1)"* — vá lỗ
  §3.8 ở tầng retrieval. `TT41-2025::Điều 16` → `bi_bai_bo` (cạnh TT22 Điều 6 Khoản 2), ca
  cạnh-chết chạy thật. `TT40-2024::Điều 26/37/25` → `da_sua` kèm nguồn sửa.
- **Benchmark 36 câu (`eval/results/20260806-072821.json`), 0 câu lỗi.** Citation 36/36 ở cả ba
  cột; stale-avoidance baseline 21/36 → LexFlow **36/36**; mâu thuẫn 6/7; retrieval p50 5028 ms.
  **Router OFF vs ON: 0/36 câu khác nhau**, 0 hit bị loại vì bãi bỏ, 8 hit được nắn trích dẫn.
- **Decision.** Ghi **dự đoán trước khi chạy** benchmark (0–3 hit bị loại; 10–25 hit được nắn) —
  thực tế 0 và 8, tức **dự đoán sai phía nắn trích dẫn**. Kết luận thẳng: **bộ 36 câu này không
  đo được lớp phủ**, vì nó chấm ở mức `doc_id` còn lớp phủ làm việc ở mức khoản; "0/36 khác nhau"
  là giới hạn của thước đo, không phải bằng chứng lớp phủ vô dụng (giá trị của nó hiện ra ở
  verify e2e và ở bộ nhãn cấp khoản). Muốn đo được thì cần bộ câu hỏi chấm ở mức điều/khoản —
  việc riêng, chưa làm.
- **Sự cố đáng ghi.** (1) `.gcloudignore` bỏ sót `data/tuvanphapluat/` (516 MB) ⇒ upload không
  bao giờ tới bước build, mà `gcloud … | grep | tail` lại trả exit 0 (mã thoát của `tail`) ⇒ hai
  lần "deploy thành công" giả. Chốt tiêu chí nghiệm thu deploy = **OpenAPI của bản đang phục vụ
  có trường mới**, không phải exit code. (2) `Dockerfile` không copy `data/overlay/` ⇒ image
  thiếu artefact ⇒ `tai_lop_phu()` trả `None` ⇒ lớp phủ **tắt trong im lặng** (fail-open nuốt
  luôn) — vá ở `35031dd`. (3) Subagent kết luận `.where()` treo trên LanceDB Cloud và đề xuất né;
  đo trực tiếp thì `.where()` chạy tốt (1.85s/5.19s), lỗi thật là thoáng qua ngay sau khi ghi đè
  bảng — bác bỏ bằng số, không đổi cột nền.
- **Final review toàn nhánh (bước cuối của quy trình) — 1 Critical + 6 Important.** Chạy trên
  model mạnh nhất, đo **trên artefact đã ship**: (1) nhánh 3 lấy cạnh khớp đầu tiên rồi tuyên bố
  như sự thật — 46 cặp cạnh chung span, ca `ND80→ND101` sửa **5 khoản** mà chỉ nêu 1; (2) fallback
  kéo lời văn hiện hành hỏi id cấp điều nên **31/40 ca trả rỗng** — **lỗi trong plan**, và mọi test
  đều mock đúng hàm bị hỏng nên sống sót qua 10 cổng review; (3) chunk kéo thêm không qua chú
  thích/hiệu lực/phạm vi. Sửa 7 commit `ec41c13..87b2e1d`, **620 test** xanh, classify 94 giữ,
  deploy rev `00017-cqc`. Đợt sửa tự gây một hồi quy (thu hẹp "cả Khoản 2" xuống "Điểm b, đ", bắn
  ở 2/15 nhóm span thật) — bắt ở re-review, đi thêm một vòng ngoài mặc định quy trình vì cái giá
  của việc bỏ qua là một trích dẫn pháp lý sai. Luật chốt: **không chắc thì nới rộng, đừng thu hẹp**.
- **Next.** Bộ câu hỏi eval chấm ở mức điều/khoản (#19 — mở khoá con số trình hội đồng); tín hiệu
  runtime báo lớp phủ đã nạp (`/health`, parked); `so_hieu_theo_doc` đóng băng lúc build sẽ mục
  ruỗng khi corpus lớn (parked); cào 89 văn bản tồn đọng.

---

## 2026-08-05 (T4) — đợt 4: overlay dưới-văn-bản (P1–P3), 8 task subagent-driven TDD

- **Done (P1–P3 qua 8 task, mỗi task TDD đỏ→xanh, 2 vòng fix sau review).** `CanhTacDong` (cạnh
  con↔con: khoản/điểm chạm khoản/điểm) sinh từ mệnh lệnh sửa đổi → nút overlay thưa
  (`dung_overlay`) → phiên bản hiện hành theo thời gian + luật cạnh-chết (`phien_ban_hien_hanh`)
  → định tuyến sau truy hồi (`dinh_tuyen`, 3 nhánh: nguyen_ven/nen_da_sua/trich_trong_van_ban_sua).
  Số đo thật (xem mục mới trong `docs/KG-CONFORMANCE-v05.md`): **178 cạnh**, đối chứng TT40
  90.4% (75/83) · TT15 92.5% (37/40) · TT34 92.1% (35/38); **167 khoá đích — 126 da_sua · 36
  bi_bai_bo · 5 nguyên_ven**; bộ nhãn tay `eval/overlay/cau_hoi_nhan.jsonl` (13 dòng — 12 lúc nghiệm thu + 1 hàng khoản-gộp thêm ở đợt sửa final review, cả 3
  nhánh, gắn nhãn bằng đọc luật rồi mới chạy `dinh_tuyen` đối chiếu) khớp **13/13**. Final review toàn nhánh bắt 3 lỗi Important có ca tái hiện (khoá giả cho chunk khoản-gộp — 21.8% corpus; nhánh trích-dẫn không qua luật cạnh-chết; đuôi trích dẫn `bai_bo` in nhầm "sửa bởi") — một đợt sửa, re-review đủ 5/5, suite lên 555.
- **Decision (hai lệch so với kế hoạch — đo rồi giữ số thật, không sửa cho khớp dự đoán).**
  (1) Kế hoạch đoán TT40 Điều 41 sẽ về `nguyen_ven` "vì TT22 đã giết TT41 Đ16" — dữ liệu thật có
  cạnh THỨ BA (TT22 Đ1 tự viết lại trực tiếp TT40 Đ41, không chỉ bãi TT41 Đ16) nên trạng thái
  thật là `da_sua`; sửa test theo số đo, không sửa code cho khớp dự đoán mù.
  (2) Kế hoạch giả định mỗi `loi_van_moi` nằm gọn trong MỘT khối `trich_dan` — đo thật thấy
  13/142 cạnh là khối GỘP (nhiều khối trích không liền kề trong cùng mệnh lệnh, đúng luật
  `canh_tu_dieu` Quy tắc 3), mỗi ca đều mang cảnh báo kèm theo — test đổi sang bất biến chính
  xác hơn (biên span khớp đúng biên `trich_dan` thật) thay vì khẳng định hẹp ban đầu.
- **Kiểm:** `uv run pytest -q` **551 passed** · `ruff check .` sạch · `--classify` giữ 94 đơn vị
  45/9/40.

---

## 2026-08-05 (T4) — đợt 3: nạp lượt crawl 22 văn bản (20 → 26 văn bản, `BAI_BO` ×4)

- **Done (kiểm độc lập báo cáo crawler trước khi tin).** 22 file corpus + 22 raw; 14 văn bản có toàn văn = đúng **261 điều** như báo cáo; cả 14 qua kiểm `char_span` lớp 1 của mình, 0 cảnh báo đối chứng; 8 VBHN rỗng đúng như đã đoán (giới hạn nguồn). Đuôi `Nơi nhận:` nguồn **vẫn dán** ở 7/14 — bộ cắt của loader xử lý, không lọt vào corpus. TT38 được crawler điền sẵn `valid_to=2024-07-01` — khớp bằng chứng TT15 Đ22 k4 độc lập tìm ra.
- **Done (nạp đợt 2 — 6 văn bản mới, 12 cạnh mới, tất cả có căn cứ).** Corpus: **26 văn bản · 425 điều · 1 289 khoản · 1 053 điểm · `chapter` 180/425 · 35 quan hệ · `kiem_quan_he` 0 cạnh sai**. Quét IGNORECASE (bài học TT22 áp dụng từ đầu) ra hai ca `BAI_BO` mới: **ND58 Đ28 k2 bãi bỏ Đ4 NĐ16** (NĐ16 giờ mang hai vết cắt từ hai nghị định — mỗi nghị định thay một mảng thì gỡ đúng điều sửa mảng đó) và **TT15 Đ22 k4 bãi bỏ Đ3 TT30/2016** — ca đầu tiên **cả nguồn lẫn đích đều có toàn văn**, tức truy vấn §6.2 hết phụ thuộc node rỗng. `BAI_BO` 2 → **4**.
- **Done (test đo dữ liệu sống theo kịp — và một bài học về test "bằng chứng sống").** Bắc cầu ba mốc cùng phép đo 48/18/30 → 58/33/25 → **70/48/22**, số học khớp từng phần. Test "một lược đồ không đủ" mất chuyên án lần thứ HAI trong ngày (TT41 rồi TT34 lần lượt được nạp) — test neo vào "văn bản còn thiếu" thì mỗi đợt crawl thành công lại phá nó, nên chuyển sang lược đồ dựng tối thiểu, lịch sử hai ca thật giữ trong docstring. Viện dẫn cấp tiết 4 → 17 → **23** (TT30-2025 +3, TT34 +2, TT38 +1 — đo từng văn bản).
- **Done (danh sách crawl tự lớn 67 → 89 — đúng thiết kế).** 13 lược đồ mới trỏ tiếp ra nhánh thẻ (TT19/2016 + 5 bản sửa), IBPS, thông tin tín dụng… `research/crawl_68_urls.txt` sinh lại: **89/89 có URL vbpl**, xếp GẤP → cao → vừa → thấp.
- **Ship (Neo4j — lần đầu đồ thị 13-kiểu-cạnh chạy trên server thật).** `push_corpus` bản 26 văn bản · 35 cạnh có kiểu lên Aura vừa resume. Lần chạy thật ĐẦU TIÊN lộ ngay hai lỗi Cypher mà mock không bắt được (code viết 04/08 khi instance còn pause): mẫu đa kiểu phải là `:A|B|C` một dấu hai chấm, và `IS NOT false` là Python lạc sang Cypher → `coalesce(x, true)`. Sửa xong: **truy vấn §6.2 trả 3 khoảng trống lập pháp thật** — NĐ16/2019 (bị bãi bỏ hai lần, không ai thay thế), TT30/2016, TT41/2025; `related_docs`/`related_edges`/`don_node_rong` đều đã chạy sống. LanceDB/web vẫn đợi theo quyết định của bạn.
- **Next:** quyết chuyện `corpus/` tự đứng (3), thiết kế `PhienBanDieu` từ `trich_dan` + `dieu_khoan_bi_tac_dong` (4), crawl 89 văn bản theo `research/crawl_68_urls.txt`.

---

## 2026-08-05 (T4) — #14: nạp 8 văn bản crawl vào corpus (15 → 20 văn bản)

- **Done (kiểm trước nạp — và phép đo từng điều tóm được lỗi của chính bộ tách).** Cả 8 văn bản có toàn văn qua kiểm `char_span` từng ký tự; đo từng điều 3 văn bản trùng (ND52/TT15/TT40) thay vì tin tổng. Ba chỗ tưởng là lỗi crawl hoá ra ngược lại:
  - **`_KHOAN_RE` đòi dấu cách sau chấm, vbpl in `1.Việc` dính liền** ⇒ TT40 Đ25 mất trọn khoản 1 (5 điểm), TT15 Đ14 khoản 3 bị nuốt vào khoản 2. Tức **bảng nghiệm thu cũ (97 khoản/216 điểm) đo bằng thước hỏng**. Sửa regex có lá chắn: chỉ nhận thiếu-cách khi ký tự kế **không phải chữ số** — `1.000.000 đồng` vẫn không thành khoản, có test canh cả hai chiều. Sau sửa: TT15 **98** khoản, TT40 **194/221** — khớp corpus cũ **từng khoản một**.
  - **Thuộc tính vbpl sai được:** trang ND52 ghi hiệu lực `01/07/2027 — Chưa có hiệu lực`, trong khi Điều 37 của chính nó viết *"có hiệu lực thi hành từ ngày 01 tháng 7 năm 2024"*. Thành quy tắc 1 của bộ nạp: **chữ trong luật thắng metadata** — văn bản đã có trong corpus thì giữ ngày corpus khi lệch, kèm cảnh báo.
  - **Đuôi hành chính dán vào điều cuối:** `Nơi nhận:` + chữ ký, và ở TT40 là **6 965 ký tự biểu mẫu phụ lục** nằm trong `Điều 54`. Cắt tại dòng đúng bằng `Nơi nhận:` (5/8 văn bản có, 3 văn bản còn lại đuôi sạch), chỉ đụng điều cuối, cắt **sau** khi `char_span` đã kiểm, có vết trong cảnh báo. Phụ lục chờ nhánh `#phuluc_`.
- **Done (`app/ingestion/nap_corpus.py` + 6 test).** Trộn có vết, **idempotent** (chạy hai lần cùng bộ số, không nhân đôi), cạnh mới chỉ vào khi **cả hai đầu trong corpus** — cạnh nửa vời sẽ bị `MATCH…MATCH` của Neo4j nuốt im lặng. Kết quả: **20 văn bản · 338 điều · 1 036 khoản · 821 điểm · `chapter` 115/338 · 23 quan hệ, `kiem_quan_he` 0 cạnh sai**.
  - **Ca `BAI_BO` đầu tiên vào corpus, đúng như #14 hứa:** ND52 Điều 37 *"bãi bỏ Điều 3 của Nghị định số 16/2019/NĐ-CP"* — cạnh mang neo `Điều 37 → Điều 3`, bãi bỏ **một phần** (khớp tình trạng vbpl "Hết hiệu lực một phần"). Truy vấn §6.2 hết bị chặn bởi dữ liệu.
  - **Cạnh `BAI_BO` thứ hai — và một lỗi grep của tôi bị bạn bắt.** Tôi từ chối thêm `TT22 -BAI_BO-> TT41` với lý do "toàn văn TT22 không có câu bãi bỏ nào" — **sai**: TT22 Điều 6 khoản 2 viết *"Bãi bỏ Điều 16, Điều 17, Điều 18 Thông tư số 41/2025/TT-NHNN…"*, mở câu bằng **"Bãi bỏ" viết hoa** nên grep `bãi bỏ` chữ thường không thấy. Bạn chỉ ra; quét lại IGNORECASE cả 8 văn bản thì không còn câu nào sót khác. Ba nguồn vbpl hoá ra **nhất quán**: lược đồ "bị bãi bỏ" + tình trạng "Hết hiệu lực một phần" + lời văn bãi bỏ đúng 3/27 điều (các điều sửa Điều 41/42/43 của TT40). Cạnh vào với neo `Điều 6 → Điều 16/17/18`; TT41 **không** nhận `valid_to` vì chỉ chết một phần. Bài học ghi thẳng vào docstring `nap_corpus`: **tìm mệnh đề trong văn bản pháp lý phải IGNORECASE — mệnh đề đứng đầu khoản luôn viết hoa.** Bạn cũng xác nhận hai phán định hôm nay: ND52 hiệu lực `01/07/2024`, ND80 hết hiệu lực `01/07/2024`.
  - TT41 có **27 điều thật** (mỗi điều sửa đúng một điều TT40) — nghi vấn "điều giả từ khối trích dẫn" kiểm xong, không phải.
- **Done (4 test đo dữ liệu sống viết lại theo hiện thực sau nạp, số nào cũng đo tay trước).** Bắc cầu 48/18/30 → **57/32/25** (số học khớp từng phần: +9 cạnh, 5 văn bản rời tập stub); test canh-cái-chặn `BAI_BO` **đỏ đúng ngày ND16 được nạp** như thiết kế, viết lại thành mặt sau (cạnh phải tồn tại, neo phải đúng); bài học "một lược đồ không đủ" chuyển bằng chứng từ TT41 (đã nạp) sang **TT34/2024 qua lược đồ TT66** (ưu tiên 2 → 1, lộ thêm `THAY_THE`); viện dẫn cấp tiết 4 → **17** (TT41 +5, TT66 +8 — đo từng văn bản trước khi ghi vào docstring).
- **Done (đợt 2 — ba câu trả lời của bạn thành bốn việc).**
  - **Danh sách crawl có URL:** rút từ chính các mục lược đồ đã crawl — **67/67 văn bản đều có URL vbpl**, ghi vào `research/crawl_68_urls.txt` theo thứ tự GẤP → cao → thấp, cùng format `crawl_list.txt`.
  - **Rác lược đồ đầu tiên bị loại có căn cứ:** `19/2016/QĐ-UBND` (thoát nước Khánh Hoà) nằm ở `incoming/"Văn bản áp dụng"` của ND80 — bạn xác nhận bỏ. Loại ở tầng **sinh danh sách** (`RAC_LUOC_DO` + `loc_rac` trong `can_crawl.py`, có test), KHÔNG sửa bản ghi thô: lần đối chiếu sau còn phải thấy vbpl đã ghi gì. Danh sách 68 → **67**.
  - **Neo4j: chẩn đoán "chết DNS" sai một nửa.** Instance chỉ bị Aura free **tự pause** — pause thì DNS ngừng phân giải, nhìn từ ngoài y hệt chết. Bạn resume, kết nối lại được ngay, và bên trong là **nguyên bản đồ thị cũ**: 15 node · 13 cạnh mang tên cũ (`HUONG_DAN` 4 · `SUA_DOI` 2) · 0 node có `so_hieu` — đúng cái "tồn đọng schema cũ trong hệ đang chạy" mà đợt soát 04/08 kết luận nhầm là không có. Không dọn tay: `push_corpus` xoá sạch trước khi nạp; **chưa push** theo quyết định của bạn.
  - **Cả bốn cạnh TT15/TT17/TT18/TT40 → ND52 được bạn xác nhận là `CAN_CU`** (căn cứ ban hành; TT17/TT18 chốt sau khi đọc tiêu đề) — khớp dữ liệu hiện có, không đổi gì. Câu hỏi treo từ G3 về tách `HUONG_DAN` đóng lại cho 4 cạnh này.
- **Ship:** không deploy; `data/corpus.real.json` mới nằm trong repo, LanceDB/web chưa nạp lại — **bạn chốt: đợi dữ liệu và schema ổn định**.
- **Decision:** `29/VBHN-NHNN` tiếp tục là node rỗng (vbpl không đăng toàn văn — nhiều khả năng nằm trong tệp đính kèm); ND80 nhận `valid_to=2024-07-01` theo lời văn ND52 dù vbpl gắn "Còn hiệu lực" — **bạn đã xác nhận cả ND52 lẫn ND80**.
- **Next:** #16 crawl 67 văn bản theo `research/crawl_68_urls.txt` (2 mức GẤP đứng đầu); #17 chỉ còn `push_corpus` khi bạn cho phép; #18 nhận `source_url`/`source_files`; nạp lại LanceDB khi corpus ổn định. 8 VBHN: đánh giá 05/08 — bỏ qua được trước mắt (VBHN không mang hiệu lực độc lập, bản sát đề nhất 29/VBHN đã lỗi thời vì chưa gồm TT22); giá trị thật là làm **bản đối chứng** cho phép tự hợp nhất khi dựng tầng thời gian §7.
- **Kiểm:** `uv run pytest -q` **516 passed** · `ruff` sạch · `--classify` giữ 94 đơn vị 45/9/40 · `nap_corpus --kho` lặp lại cùng bộ số.

---

## 2026-08-04 (T3) — đợt 3: khối trích dẫn trong văn bản sửa đổi

- **Done (`parse_dieu` học đọc ngoặc kép — `app/ontology/parser.py`).** Bộ crawl cảnh báo *"ND80 Điều 1: khoản 5, 6, 7, 8 xuất hiện 2 lần với nội dung KHÁC nhau — cần người đọc quyết bản nào đang hiệu lực"*. Truy ra thì **không có gì để quyết**: một văn bản sửa đổi chép nguyên văn nội dung mới vào giữa hai dấu ngoặc kép, và phần chép mang **đánh số của văn bản BỊ sửa**. Khoản 5 lần một là của **ND101**, lần hai là của **ND80** — hai văn bản khác nhau, không phải hai phiên bản.
  - **Hậu quả thật không nằm ở con số** mà ở khoá: `80/2016/NĐ-CP#than/dieu_1#khoan_5` trỏ vào **hai thứ khác nhau**, một trong hai là nội dung của văn bản khác — đúng kiểu nhập nhằng cả lớp khoá này sinh ra để chặn.
  - **Việc này là của bộ tách, không phải của bên crawl.** Ngoặc kép là chữ của chính đạo luật; bỏ nó đi là sửa văn bản gốc và làm mất nghĩa của một văn bản sửa đổi. Nên `trong_trich_dan()` dựng mặt nạ theo ký tự, và cả ba chỗ nhận diện (khoản · điểm · tiết) bỏ qua dòng nằm trong khối. Khối **ở lại trong `text` của khoản mẹ** — bỏ khoản-giả khác hẳn bỏ chữ, và không có nó thì khoản 1 chỉ còn câu lệnh trống nghĩa.
  - **Ngoặc lệch ⇒ bỏ luật cho cả Điều đó**, không đoán chỗ đóng: đoán sai sẽ nuốt phần còn lại của Điều — hỏng nặng hơn hẳn cái nó định sửa, và hỏng im lặng.
  - **Đo trước khi viết**, và chính phép đo quyết định là làm được: ngoặc **cân 100%** trên cả 9 bản ghi; **0/18 fixture** có khoản/điểm trong ngoặc ⇒ 94 đơn vị và nhãn vàng **không đổi một dòng**; corpus có **75 khoản** đang bị gán nhầm chủ, tất cả ở TT20-2016 và TT23-2019 — đúng hai văn bản sửa đổi.
  - **Kết quả:** ND80 Điều 1 từ 14 → **10 khoản, khớp đúng cây `provisions` của nguồn**; `char_span` không khoản nào lệch; ND52/TT15/TT40 không đổi một con số. **506 test** (thêm 11), ruff sạch, `--classify` giữ 94 đơn vị 45/9/40.
  - Một lỗi bắt được khi chạy: văn bản kết thúc bằng `\n` sinh dòng rỗng cuối có `start == len(text)` ⇒ tra mặt nạ ném `IndexError`. Mặt nạ nay dài `len(text) + 1`, có test canh riêng.
- **Done (`docs/PROMPT-SUA-CRAWLER-2.md`).** Bên crawl **không phải sửa dữ liệu** — chỉ hai câu cảnh báo: (1) cảnh báo "cần người đọc quyết" tạo ra **việc rà soát giả**, chỉ nên bắn khi cả hai dòng trùng đều **ngoài** ngoặc; (2) `check_tree_coverage` nói **ngược** — *"cây thiếu 4 khoản (10/14)"* trong khi cây đúng là 10, còn 14 mới là số thừa. Ở TT15 thì cây thiếu nút thật, ở văn bản sửa đổi thì cây lại **đúng hơn** toàn văn, vì cây đọc theo cấu trúc HTML nên biết khối trích dẫn là con của khoản.
  - Ghi rõ trong prompt rằng cột đối chiếu đếm bằng regex thô nên **không** bằng số khoản của bộ tách (TT40: 209 vs 193) — để bên kia không chỉnh code cho khớp nhầm số.

---

## 2026-08-04 (T3) — đợt 2: nhận dữ liệu crawl lại

- **Done (kiểm độc lập báo cáo của crawler).** Không lấy báo cáo làm bằng, đếm lại khoản/điểm từ `articles[]` **và** từ `noi_dung` cho cả 9 văn bản: **8/9 khớp bảng nghiệm thu**. Ca lệch duy nhất là TT40 — **216 điểm, không phải 218 như tôi đưa**. Truy bằng chính file cũ trong git: bản cũ có điểm `đ` và `i` **lặp** ở cuối Điều 37 khoản 1, bản mới bỏ đúng hai cái đó. ⇒ **số của tôi sai**, vì phép khử trùng lúc tôi đo chỉ xử lý dòng khoản `^\d+\.` mà bỏ sót dòng điểm.
- **Done (`articles[]` đảo vai từ "không được dùng" thành NGUỒN).** Đo được ba điều: `char_span` khớp `noi_dung` **8/8 văn bản, 100% số điều**; số khoản/điểm khớp bảng; `chapter`/`section` đầy đủ ở mọi văn bản **có** Chương (ND52 38/38 · TT40 54/54 · TT15 23/23 — các văn bản còn 0 đều là văn bản sửa đổi ngắn, cây cũng không có Chương nào).
  - Lý do đủ mạnh để tin là **nguồn tự bảo đảm đúng bất biến xuất xứ mà tầng ontology dựa vào**, và nó **kiểm được ngay tại chỗ nạp** — không phải tin suông.
  - Phép dựng lại từ `noi_dung` **ở lại làm đối chứng**, không xoá: cái đã hỏng một lần thì hỏng lại được, và kiểu hỏng của nó là im lặng (0 khoản trông y hệt một điều không chẻ khoản). `dieu_tu_ban_ghi` kiểm **hai lớp** — `char_span` sai ⇒ **từ chối cả văn bản**; số khoản/điểm lệch ⇒ cảnh báo. Có test dựng bản ghi mang đúng chữ ký khuyết tật cũ (mất đánh số nhưng `char_span` vẫn khớp) để chứng minh lớp 1 **không** đủ.
- **Done (sửa lỗi của chính tôi — đổi bố cục thư mục làm hai bộ đọc câm).** Bộ crawl chuyển sang `raw/` + `corpus/`, cả `_doc_vbpl` lẫn `doc_thu_muc` còn quét phẳng ⇒ đọc ra **0 cạnh**, và công cụ in *"0 văn bản cần crawl"* — **đọc như đã xong hết, tức đúng nghĩa ngược lại**. Cùng lúc **42 test lặng lẽ chuyển sang skip** vì `skipif` trỏ đường dẫn cứng: suite vẫn báo xanh trong khi không kiểm gì.
  - Sửa tận gốc chứ không vá đường dẫn: `tho_theo_so_hieu()` tra bản ghi theo **số hiệu nằm trong file**. Tên file đã đổi ba lần (`sample.json` → `<slug>.json` → `raw/<slug>.json`), số hiệu thì không đổi theo cách xếp file.
  - Thêm chốt: thư mục **có file mà không nhận ra bản ghi nào** thì kêu. *Rỗng-vì-không-tìm-thấy* và *rỗng-vì-không-còn-gì* không được in ra giống nhau.
  - **495 test, 0 skip** (trước đợt này: 446 pass + 42 skip).
- **Decision:** chưa nạp 7 văn bản vào corpus. Không phải vì dữ liệu xấu — mà vì TT15 crawl lại **khác corpus ở 9/22 điều** và corpus đang **sai** ở đó (Điều 18 nuốt trọn Điều 19). Nạp đè là việc riêng, cần đo trước từng điều.
- **Next:** nạp 7 văn bản (đầu tiên là `16/2019/NĐ-CP` — mở khoá ca §6.2); crawl tiếp theo `docs/CAN-CRAWL.md` (**68 văn bản**, `30/2016/TT-NHNN` và `58/2021/NĐ-CP` đứng mức GẤP vì mang `BAI_BO`); dựng lại instance Neo4j.

---

## 2026-08-04 (T3)

**Giai đoạn:** chuẩn hoá **số hiệu văn bản**, bắc cầu `so_hieu` ↔ `doc_id`, **node rỗng**, và soát tồn đọng schema cũ.

- **Done (số hiệu — `app/core/so_hieu.py`, `data/ky_hieu_van_ban.json`).** Nghiên cứu ký hiệu của bạn (`research/vb-phap-luat-ky-hieu.html`) đổi ba thứ tôi chưa tính: ký hiệu **hợp thành** `<loại>-<cơ quan>` ⇒ từ vựng là O(loại)+O(cơ quan) chứ không phải tích, tổ hợp chưa gặp (`TT-BNNMT`) tự hợp lệ; **năm tuỳ chọn** ⇒ khuôn cũ đòi năm nên bỏ sót **trọn nhóm hành chính** (`123/QĐ-NHNN`) trong im lặng; `TT-BT` là placeholder, văn bản đó về thuế XNK nên mã thật là `TT-BTC` — trùng đúng ca Cyrillic.
  - **Chỉ lưu MỘT dạng: dạng công bố.** Bản nháp trước định thêm "dạng so khớp" (bỏ số 0 đầu, `Đ→D`) + id kỹ thuật từ URL vbpl — ba danh tính, và bạn nói thẳng là thừa. Đo lại chốt: **0 xung đột số 0 đầu** trên mọi nguồn ⇒ bỏ số 0 là giải bài toán không tồn tại mà lại làm dạng lưu lệch dạng công bố. Chuẩn hoá là **hàm ở biên**, không phải trường thứ hai; id trong URL vbpl là *provenance của bản ghi thô*.
  - **Khử homoglyph là quy tắc CẤU TRÚC, không phải tra danh sách**: mã chỉ gồm chữ cái ⇒ bắt được cả mã cơ quan **chưa có trong bảng**. Cảnh báo nêu đích danh codepoint vì người sửa nguồn cần biết ký tự nào.
  - `loai` **đóng** (luật liệt kê đủ hình thức) ⇒ mã lạ là lỗi. `co_quan` **không đóng được** (63 UBND tỉnh, doanh nghiệp) ⇒ mã lạ là cảnh báo. `QĐ` trả `qppl=None` **cố ý**: từ 2015 Quyết định của Bộ trưởng không còn là VBQPPL nhưng của Thủ tướng/UBND tỉnh thì vẫn — riêng ký hiệu không đủ chốt.
  - **Test bắt một lỗi của chính tôi:** `TTg` (Thủ tướng) và `TTr` (Tờ trình) là chính tả chuẩn hoa-thường lẫn lộn, `.upper()` mù biến `QĐ-TTg` thành `QĐ-TTG` trong im lặng. Sửa theo nguyên tắc đang dùng — **từ vựng chốt chính tả**, không phải phép biến đổi chuỗi.
- **Done (cầu `so_hieu` → `doc_id` + node rỗng — `app/ingestion/bac_cau.py`).**
  - **Vì sao là chuyện im lặng, không phải chuyện bất tiện:** `push_corpus` viết `MATCH (a:Document {doc_id}), (b:Document {doc_id})` rồi mới `MERGE`, mà Cypher `MATCH` không khớp thì **cả câu không chạy**. Đổ 35 cạnh khoá-số-hiệu vào hôm nay ⇒ **0 cạnh, 0 lỗi**.
  - `DocumentMeta.so_hieu` nullable, **`doc_id` vẫn là danh tính** (đổi nó chạm 243 chỗ + lịch sử Supabase). Điền **không gõ tay dòng nào**: 15/15 văn bản đọc được số hiệu từ chính `title`, kể cả 4 văn bản nội bộ SHB.
  - **57 cạnh** (13 corpus + 44 từ hai bản ghi vbpl) quy hết về `doc_id`, **0 cạnh rơi, 0 cảnh báo**; 21 nối hai văn bản có toàn văn, **32 đầu mút thành node rỗng**. Mã có instance: **4/13 trong corpus → 7/13** khi hợp nhất lược đồ (thêm `BAI_BO`, `QUY_DINH_CHI_TIET_HUONG_DAN`, `HOP_NHAT`).
  - **Cơ chế cập nhật là SUY RA, không vá.** Node rỗng không ai soạn — điều kiện tồn tại là "chưa văn bản nào nhận số hiệu này". Crawl xong, đưa vào corpus kèm `so_hieu` ⇒ lần nạp sau tự thành node thật, **không có bước di trú**. Đường nạp bổ sung có `don_node_rong_da_co_toan_van()` để cơ chế đó là thứ **gọi được và kiểm được**, không phải hệ quả phụ của việc xoá sạch.
  - Hai chỗ **cố ý không làm**: node rỗng lấy chính số hiệu làm `doc_id` (bịa `ND16-2019` thì lúc crawl thật dễ thành hai node cho một văn bản); `related_docs()` **loại** node rỗng khỏi truy hồi (trích dẫn node rỗng là trích dẫn thứ chưa đọc) trong khi `related_edges()` giữ — ở đó chính **cạnh** mới là thông tin.
  - **Xếp ưu tiên crawl theo *hỏng cái gì*, không theo số cạnh**: đo được 30/30 đầu mút treo đều đúng **1 cạnh** ⇒ xếp theo số cạnh là xếp theo một cột hằng số.
- **Done (soát tồn đọng schema cũ — `docs/KG-CONFORMANCE-v05.md` §3.6).** Ba chỗ, mức rất khác nhau:
  - **Neo4j: không tồn đọng, nhưng vì lý do đáng lo hơn** — instance Aura `fd63789d.databases.neo4j.io` **không phân giải DNS nữa** (`databases.neo4j.io` và `google.com` phân giải bình thường ⇒ không phải lỗi mạng). Đồ thị hiện không có dữ liệu để tồn đọng, và cũng không có để chạy.
  - **Web: còn sống ở BA file và hỏng theo kiểu không ai thấy.** `anchors.ts:73` lọc `rel_type !== "SUA_DOI"` ⇒ sau khi đổi tên, **bản đồ sửa đổi theo điều rỗng đi**, bỏ đúng 2 cạnh `SUA_DOI_BO_SUNG` của corpus. Ba bảng nhãn 4 dòng ⇒ 11 mã còn lại rơi xuống nhánh dự phòng, người dùng đọc chữ `SUA_DOI_BO_SUNG` thay cho "Văn bản sửa đổi, bổ sung", **không lỗi nào trong console**. Gom về `web/lib/quan-he.ts`; `tests/test_quan_he_web.py` đọc thẳng file `.ts` canh 13 mã + 26 nhãn khớp `REL_TYPES`, kể cả cặp bất quy tắc #8.
  - **Supabase: chỗ DUY NHẤT schema cũ còn sống trong dữ liệu thật.** Migration `0003` **seed thẳng** `HUONG_DAN` và `SUA_DOI` vào `change_events`, và đã chạy. Nặng hơn tên xấu: khoá chống trùng `unique (doc_id, source_doc_id, rel_type)` **có `rel_type` trong khoá** ⇒ lần ingest sau, cùng một thay đổi mang tên mới bị coi là **sự kiện khác** và chèn thêm dòng. `0006_quan_he_v05.sql` sửa + thêm `check` chặn ở biên — **chưa chạy**, cần dán vào SQL Editor.
- **Done (`docs/CAN-CRAWL.md` — `app/ingestion/can_crawl.py`).** 32 văn bản, mỗi dòng truy được về một cạnh có thật. Danh sách gõ tay đúng vào ngày gõ rồi lệch dần mà không ai biết; cái này sinh lại được.
  - **Một chỗ danh sách tự nó giấu — và bản ghi thứ hai của bạn chứng minh ngay trong ngày.** Lược đồ của một văn bản chỉ chứa quan hệ **với chính nó**. Lược đồ ND52 xếp 20 Thông tư vào `CAN_CU`, nhưng tiêu đề của 6 trong số đó nói chúng **sửa đổi** văn bản corpus — dấu hiệu, chưa phải kết luận. Thêm `sample_v2.json` (lược đồ **của chính TT40/2024**): `41/2025/TT-NHNN` và `22/2026/TT-NHNN` lộ ra ở `incoming / "Văn bản sửa đổi bổ sung"`, mức nhảy **thấp → cao**, và cùng lượt lộ `29/VBHN-NHNN` (`HOP_NHAT`). ⇒ corpus đang ghi TT40/2024 là *còn hiệu lực, chưa sửa đổi* — **sai**. Phải crawl lược đồ của **từng văn bản corpus**, không chỉ của các đầu mút.
  - Một cảnh báo còn lại, và nó **đúng**: mục thứ hai trong nhóm *Văn bản hợp nhất* của TT40 chỉ có trích yếu *"Quy định về hoạt động cung ứng dịch vụ trung gian thanh toán"*, **không kèm số hiệu**. Rất có thể là chính `29/VBHN-NHNN` ở dòng trên, nhưng "rất có thể" không phải "biết" — báo ra, không đoán.
- **Done (khảo sát dữ liệu ngoài, tách biệt khỏi luồng ontology ở trên).** Tải bộ dataset công khai `phamson02/tuvanphapluat` (HuggingFace) về `data/tuvanphapluat/` — 224,005 đoạn corpus + 169,451/9,999 cặp hỏi-đáp train/test, script tái tạo ở `scripts/download_tuvanphapluat.py`. Dựng UI duyệt cục bộ (`scripts/tuvanphapluat_viewer.py`, FastAPI + DuckDB đọc thẳng parquet, không load hết vào RAM — hợp máy 8GB) để xem/tìm kiếm, có liên kết câu hỏi ↔ đoạn corpus qua `contextoid`.
  - Bộ dữ liệu **không** có trường "lĩnh vực pháp luật" tổng quát, chỉ có `category` rất chi tiết (**13,464 tag khác nhau**/câu hỏi, không phân cấp). Thêm bộ lọc theo tag vào UI (gõ "ngân hàng" → gợi ý tag liên quan kèm số lượng: *Tổ chức tín dụng* 461, *Ngân hàng Nhà nước* 275, *Ngân hàng thương mại* 163, *Tài khoản thanh toán* 60...) để lọc nhanh theo miền quan tâm thay vì gõ tay từng tag.
  - Mới dừng ở bước xem qua — **chưa quyết định** có dùng làm nguồn eval/train bổ sung cho RAG hay không.
- **Ship:** chưa deploy (chưa chạm đường chạy). `npm run lint` + `tsc --noEmit` + `next build` xanh; **466 test** + `ruff` xanh; `--classify` giữ **94 đơn vị 45/9/40**, `classify_testset` **9/9**. Hai script khảo sát dữ liệu đã commit (`46d7b4e`), không đụng pipeline chính.
- **Decision:**
  - Đầu mút chưa có toàn văn ⇒ **node rỗng**, không bỏ cạnh. Bỏ thì mất luôn instance `BAI_BO` duy nhất có thật (NĐ52 → NĐ16/2019), tức mất đúng ca kiểm chứng bắt buộc §6.2.
  - `doc_id` **không đổi**; `so_hieu` là trường bắc cầu. §3.3 (hai không gian ID) từ "chặn đường" xuống "dọn sau".
- **Next:** crawl theo `docs/CAN-CRAWL.md` (ưu tiên `16/2019/NĐ-CP`), crawl lược đồ **từng văn bản corpus** để lộ các quan hệ sửa đổi đang bị che; chạy migration `0006`; dựng lại instance Neo4j; G2 phần còn lại (giữ dòng Chương/Mục ở `extract.py:90` — 47 Chương + 15 Mục đang bị vứt).

---

## 2026-08-03 (T2)

**Giai đoạn:** đối chiếu code với **KG v0.5**, dựng hàng đợi duyệt cờ, và **B22 — guard `ap_dung_khi`**.

- **Done (B22 — guard "vế này áp dụng khi nào", `docs/ONTOLOGY-POC.md` §14c):**
  - **Vấn đề:** TT17 Đ16 k1 điểm a — *"(i) … **đối với khách hàng là cá nhân**; (ii) … **đối với khách hàng là tổ chức**"*. Hai tiết loại trừ nhau theo loại chủ thể. Ghi `any` là **nói sai luật** (cho phép lấy sinh trắc học người đại diện của một khách hàng cá nhân mà vẫn "đạt"); ghi `all` cũng sai (không ai đòi cả hai). Bộ tách chỉ thấy `;` trần nên trả `unknown`.
  - **`connector` GIỮ NGUYÊN `all|any|unknown`.** Hai câu hỏi khác nhau: `connector` = *các vế **kết hợp** thế nào*, `ap_dung_khi` = *vế này **khi nào** áp dụng*. Nhét cả hai vào một enum là đúng loại mơ hồ im lặng mà `menh_de` đã phải tách khỏi `action`.
  - **`GuardApDung` ở CẢ HAI tầng** (`ConditionItem` + `SubCondition`) vì đo được ở cả hai: **4/71 Điểm** và **5/12 tiết** — gần một nửa số tiết trong corpus.
  - **Parser sinh 100%, LLM không có đường nào chạm tới**: prompt không có ô nào, `build_cu` không đọc `ap_dung_khi` từ JSON mô hình ⇒ *"0 ca do LLM sinh"* là bất biến **theo thiết kế**, không phải theo số đo. Cùng kỷ luật `DieuKienCong` và `tiet_logic`.
  - **Ba chỗ chệch khỏi đề bài, đều vì đo được.** (1) Mẫu nền `(đối với|trường hợp)…(là|:)…` bắt **36 ca mà phần lớn là rác** (`thuoc_tinh='các'`, `'phát'`, `'trường'`) ⇒ siết thành ba dạng: `X là Y` · `X của Y:` · danh ngữ trần **mở đầu đơn vị** ≤4 từ. (2) Cảnh báo cho mọi ca ngoài mẫu = **+48** lên nền 82 cảnh báo, dìm chết hàng đợi duyệt ⇒ cụm chứa viện dẫn bỏ **hẳn** (đó là địa chỉ, không phải loại), chỉ **13** ca đáng ngờ được nêu. (3) Ca *"Đối với thẻ trả trước"* không có `là`/`của` ⇒ tách bằng head-word `("thẻ", "thẻ trả trước")`, `raw_text` vẫn giữ sự thật.
  - **`thuoc_tinh`/`gia_tri` là chuỗi tự do, KHÔNG enum**: 18 fixture đã có ba họ (`khách hàng` · `tài khoản thanh toán` · `thẻ`). Chuẩn hoá là việc của **bước nạp KG** qua `KhaiNiem`.
  - **Lỗi đường ống chỉ batch mới lộ.** Lần chạy đầu ra **10 guard, thiếu TT18 Đ13 k4** — một trong bốn ca thử bắt buộc — dù test parser cho ca đó **xanh**. Regex không sai; sai ở chỗ **đọc trên text nào**: Khoản không chẻ Điểm thì bản đầu đọc trên *đoạn đã neo của điều kiện* thay vì *cả Khoản*. Mô hình neo vào nửa sau câu ⇒ cụm guard rơi ra ngoài ⇒ **một tầng tất định lại phụ thuộc đầu ra của LLM**. Test đơn vị không bắt được vì nó gọi thẳng `tach_guard(khoan.text, khoan.start)` — tự cho mình đúng đầu vào. Đã thêm test đi qua `build_cu` và cố ý neo vào **đơn vị cuối**, xa cụm guard nhất.
  - **Đo lại sau khi sửa: 13 guard** (9 tầng điều kiện · 4 tầng tiết), **đủ cả 4 ca thử bắt buộc**, lỗi cứng **0/49**. Cảnh báo 82 → 95 (13 cái thêm đều là `guard_ngoai_mau`). Phát hiện thêm nhánh thứ tư ngoài đề bài: TT18 Đ9 k2 **điểm d** *"Trường hợp khách hàng tổ chức"* ⇒ chuỗi phân nhánh ở đó là **4 nhánh**, không phải 3.
  - **Ranh giới guard ↔ chapeau**: TT18 Đ9 k3 điểm c *"phải đảm bảo **các nguyên tắc sau**"* là `all`, giải bằng luật chapeau, **không sinh guard**. Hai cơ chế bù nhau, không chồng nhau.
  - **Guard KHÔNG trả lời thay `connector`** (đợt sau, cùng ngày). Hai Điểm có mọi tiết mang guard nên câu hỏi *"và hay hoặc"* nhìn qua đã moot — vẫn **không** tự nâng `unknown` → `all`: guard chỉ làm connector vô hại khi các guard anh em **loại trừ nhau từng đôi**, mà máy không chứng minh được (chuỗi tự do ⇒ hai guard tương lai có thể chồng lấn). Suy diễn hộ là **phán định**, không phải đánh dấu. Cái đổi được là **câu hỏi bàn giao**: từ *"và hay hoặc?"* (chỉ đoán được từ một dấu `;` trần) sang *"các guard này có loại trừ nhau không?"* (nhìn danh sách giá trị là trả lời được). Cảnh báo **không xoá**, chỉ đổi lời + mang **mã riêng** để hai loại đếm độc lập. Đo: tổng cảnh báo **95 không đổi**, mã cũ **3 → 1**, mã mới **0 → 2**, và ba bản ghi `connector unknown` vẫn đúng ba id cũ. Thêm một test **đọc chính mã nguồn** để một lần sửa tương lai không lặng lẽ nhét `logic = "all"` vào nhánh đã có guard.
- **Done (hàng đợi duyệt cờ):** `eval/ontology/triage.py` + `eval/ontology/flag_ui.py` — xếp 82 cảnh báo theo **hậu quả nếu bỏ qua** (T1…T6) thay vì theo tần suất ⇒ **94 đơn vị → 20 cờ cần quyết**. Nhóm cờ đông nhất (19 cờ *"điểm không tồn tại"*) hoá ra là **MỘT** khuyết tật prompt: cả 13 bản ghi đều có `khoan.diem == []`, mô hình dùng `source_diem` như **số thứ tự** chứ không phải **địa chỉ** ⇒ gom thành một dòng, không bắt đọc luật 13 lần.
  - Tìm ra khi dựng hàng đợi: **9 cảnh báo mang địa chỉ không phân biệt được** (`điều kiện g` khi điểm `g` xuất hiện **5 lần** ở ND52 Đ22 k2). Đã đánh số **chỉ khi thật sự trùng** để 46 bản ghi còn lại không đổi nhãn.
  - **Mọi script `eval/ontology` có `import app.*` đều chạy sai theo lệnh trong docstring của chính nó** (`ModuleNotFoundError: No module named 'app'`) — tức trang duyệt nhãn cũ chưa từng mở được theo hướng dẫn. Đã sửa sang dạng `-m`.
  - Nút Lưu dùng `alert()` — hộp thoại chặn cả event loop của tab. Đổi sang dòng trạng thái.
- **Done (`source_diem` suy từ parser — `docs/ONTOLOGY-POC.md` §14d).** Đợt cuối ngày, **thay thế**
  cách xử lý T6 ghi ở mục trên: 19 cờ *"điểm không tồn tại"* không còn được **gom lại** mà bị **xoá tận
  gốc**.
  - **Chẩn đoán đầu tiên sai, và cái sai đáng ghi hơn cái đúng.** Phản xạ là gọi đây là *lỗi prompt* rồi
    đi dạy mô hình trả `null` cho đúng. Nhưng như thế là **chấp nhận LLM làm nguồn sự thật cho một trường
    parser đã biết chắc**: `parser.py` tách `a)` `b)` `c)` thành `DiemNode`, `segmenter.py` dán nhãn đó
    lên từng đơn vị (`Unit.source_diem`) và **in sẵn trong menu** (`[7] (điểm b) …`). Hỏi lại mô hình
    "vế này thuộc điểm nào" là hỏi câu **đã có đáp án in trong đề bài**. Chính `schema.py` đã ghi luật này
    cho `logic` (*"suy ra TẤT ĐỊNH từ parser, KHÔNG hỏi LLM"*); `source_diem` lọt lưới vì nó nằm cùng
    object JSON với các trường mô hình thật sự phải trả lời.
  - **Sửa:** `_suy_diem()` lấy `source_diem` từ nhãn điểm của các đơn vị mô hình chọn. Một điểm → lấy;
    nhiều điểm → `None` + `diem_vat_nhieu_diem`; không điểm nào & Khoản **không** chẻ điểm → `None`, **im
    lặng** (parser chắc chắn, không có gì bàn giao cho người); không điểm nào & Khoản **có** chẻ điểm →
    `None` + `diem_khai_lech`. Lời khai của LLM **vẫn đọc nhưng bị giáng xuống làm phép đối chiếu** — nó
    không quyết định giá trị nào nữa, chỉ còn là máy dò bịa miễn phí.
  - **Đo (chạy lại `--batch` toàn corpus):** cảnh báo **95 → 76** (−19, đúng nhóm cờ đó) · **mọi mức khác
    không đổi một cờ nào** (T1 1/1/3 · T2 1/2 · T3 9 · T4 1/13/1/1 · T5 25/18) · điều kiện có `source_diem`
    **102/102 → 83/102** · bản ghi có cờ **28/49 → 21/49** · lỗi cứng **0/49** · `--classify` vẫn **94 đơn
    vị 45/9/40** · `classify_testset` **9/9**. Bỏ riêng `source_diem` ra thì **49/49 bản ghi trùng khít**
    bản cũ ⇒ thay đổi **cô lập**, không kéo theo gì.
  - **Hàng đợi duyệt vẫn 33 cờ — và đó là kết quả đúng.** 19 cờ kia trước đã bị mục T6 loại khỏi hàng đợi
    rồi; sửa lần này bỏ **cái gây nhiễu**, không bỏ việc phải duyệt. Bộ máy T6 (`_diem_bia_toan_bo`, mục
    "lỗi hệ thống" trên trang) đã **gỡ hẳn**: giữ một bộ dò không bao giờ khớp sẽ khiến người đọc sau tưởng
    chỗ đó vẫn đang được canh.
  - **Hai thứ lộ ra khi sửa.** (1) **5 test cũ neo vào đơn vị đầu tiên rồi *khai* một điểm khác** — chúng
    xanh dưới mã cũ **vì mã cũ tin lời khai**, tức chính bộ test cũng mang giả định sai. (2) Nhãn địa chỉ
    `"(không rõ điểm)"` là chuỗi, không bao giờ bằng `None`, nên nếu không ánh xạ ngược thì **19/102 điều
    kiện hiện cờ mà không kèm chữ của luật** — đúng loại lỗi im lặng trang duyệt sinh ra để chặn. Đã vá cả
    `triage._field_text` lẫn `flag_ui._locate`, kèm test.
  - **Bịt XSS bằng cấu trúc thay vì bằng lọc:** `source_diem` từng là chuỗi LLM điều khiển được (có ca mô
    hình trả nguyên chuỗi viện dẫn `"b, c, d, đ khoản 2 Điều 25"`), phải trông vào `escape()`. Nay chuỗi
    độc bị loại **từ gốc**; đường duy nhất còn lại là nội dung cảnh báo `diem_khai_lech`, vẫn escape.
  - **Còn nợ:** hai mã cờ mới **bắn 0 lần** trên corpus này — chúng chỉ được chứng minh bằng test đơn vị,
    chưa bằng dữ liệu thật.
- **Done (câu bao trùm quyết phép nối các tiết — `docs/ONTOLOGY-POC.md` §14e).** Chốt mục để ngỏ
  từ §14c. Cùng loại sai với §14d: `tiet_logic` chỉ đọc liên từ hiện, nên TT18 Đ9 k3 điểm c —
  chapeau *"phải đảm bảo **các nguyên tắc sau**:"* — vẫn bàn giao cho người câu hỏi *"và hay
  hoặc?"* dù **câu trả lời nằm ngay trong chữ luật**.
  - **Đo trước khi viết mẫu, và số liệu bác một phần đề xuất ban đầu của tôi.** Cả 18 fixture chỉ
    có **5 Điểm có tiết**; 2 đã giải bằng "hoặc", 3 còn `unknown`, và trong 3 cái đó **chỉ 1**
    mang cụm chapeau. Luật này mua **đúng một ca** — đáng viết vì tất định và vì cụm lặp khắp
    VBQPPL, **không** vì số lượng.
  - **Cụm `"sau"` trong corpus mang BỐN nghĩa trái ngược nhau**, đây mới là thứ phải canh: ALL
    (*"phải đảm bảo các nguyên tắc sau:"*) · **ANY** (*"đáp ứng ít nhất **một trong** các tiêu chí
    sau:"*) · loại trừ (*"**không áp dụng** đối với các trường hợp sau:"*, *"**trừ** các quy định
    sau đây"*) · định nghĩa (*"(sau đây **gọi là** …)"* — **15+ lần, dạng ĐÔNG NHẤT**). Regex lỏng
    sẽ bắt nhầm chính dạng đông nhất, và tệ hơn là đọc `any` thành `all` — **đảo nghĩa pháp lý**.
  - **Ba chốt chặn:** (1) **vị trí** — cụm phải ở **đuôi** chapeau, một mình điều này loại hết
    `(sau đây gọi là …)` vì chúng luôn nằm giữa câu; (2) `một trong`/`ít nhất một` hạ xuống `any`;
    (3) loại trừ và định nghĩa trả `unknown`, không đoán. `(?<!bù )` giữ *"Hệ thống **bù trừ** điện
    tử"* khỏi bị đọc thành mệnh đề trừ. **Liên từ hiện luôn thắng chapeau** — "hoặc" nói về đúng
    hai tiết đang xét, chapeau nói về cả danh sách.
  - **Máy quyết thì để lại vết.** Đọc "hoặc" là đọc **một từ**, không cần cảnh báo; chapeau là một
    **mẫu**, mà mẫu thì sai được ⇒ mã `tiet_logic_tu_chapeau` nêu đích danh cụm đã khớp, xếp **T5**
    (không vào hàng đợi vì máy đã quyết được, nhưng đếm và soát lại được). Một ca thật thì chưa đủ
    để im lặng.
  - **Đo: 7 dự đoán ghi trước khi chạy, 7 đúng.** Tổng cảnh báo **76 → 76** (một mã đổi chỗ cho mã
    khác) · T2 **3 → 2** · T5 **43 → 44** · hàng đợi **33 → 32** · `logic` của TT18 Đ9 k3 điểm c
    `unknown → all` · **không bản ghi nào khác đổi**. `--classify` **94 đơn vị 45/9/40**,
    `classify_testset` **9/9**, pytest **344**, ruff sạch.
  - **Hệ quả: một nhánh mã mất hết ca thật.** Corpus không còn Điểm nào rơi vào
    `tiet_semicolon_mo_ho`. Nhánh vẫn phải chạy đúng nên test của nó chuyển sang **Điểm dựng tay**
    và nói rõ là dựng tay — sửa fixture cho vừa test thì rẻ hơn, nhưng fixture là **chữ luật thật**,
    sửa nó là làm hỏng thứ đắt nhất trong repo.
- **Done (chuẩn hoá SỐ HIỆU theo khung ký hiệu — `research/vb-phap-luat-ky-hieu.html`).**
  - **Nghiên cứu của bạn đổi hẳn thiết kế, theo hướng tốt hơn.** Ba điều tôi chưa tính: (1) ký
    hiệu là **hợp thành** `<loại>-<cơ quan>` ⇒ từ vựng là **O(loại)+O(cơ quan)**, tổ hợp mới
    (`TT-BNNMT`) tự hợp lệ, không phải liệt kê tích của hai; (2) **năm TUỲ CHỌN** — `123/QĐ-NHNN`
    là văn bản hành chính hợp lệ, regex cũ đòi năm nên **bỏ sót cả nhóm đó trong im lặng**;
    (3) `TT-BT` là placeholder chứ không phải mã thật, và văn bản đó về thuế XNK ⇒ đúng là
    **`TT-BTC`**, khớp ca Cyrillic.
  - **Chỉ lưu MỘT dạng — dạng công bố.** Bản nháp của tôi định thêm "dạng so khớp" (bỏ số 0 đầu,
    `Đ→D`) và một khoá kỹ thuật từ URL ⇒ **ba dạng, thừa**. Đo lại: **0 xung đột số 0 đầu** trên
    toàn dữ liệu ⇒ giải bài toán không tồn tại. Chuẩn hoá là **hàm chạy ở biên**, không phải
    trường thứ hai; ID trong URL vbpl là *provenance của bản ghi thô*, không phải danh tính.
  - **Khử homoglyph là quy tắc CẤU TRÚC, không phải tra danh sách:** mã chỉ gồm chữ cái ⇒ bắt
    được ký tự lạ **kể cả với mã cơ quan chưa có trong bảng**. Ca thật `51/2025/TT-BTС` (С =
    U+0421 CYRILLIC ES) nay **sửa được + nêu đích danh codepoint**, thay vì regex cũ **im lặng
    cắt cụt** thành `51/2025/TT` — một khoá cụt tệ hơn không có khoá vì nó vẫn join được, vào
    nhầm văn bản.
  - **`loai` đóng · `co_quan` mở.** Luật liệt kê đủ hình thức văn bản ⇒ mã loại lạ là lỗi. Còn
    cơ quan thì không đóng được (63 UBND tỉnh, doanh nghiệp, cơ quan mới lập) ⇒ **cảnh báo, không
    từ chối**. `qppl` suy được từ chính ký hiệu (có năm + loại quy phạm); `QĐ` trả `None` **cố ý**
    vì từ 2015 Quyết định của Bộ trưởng không còn là VBQPPL nhưng của Thủ tướng/UBND tỉnh thì vẫn.
  - **Test bắt một lỗi thật của tôi:** `TTg` (Thủ tướng) và `TTr` (Tờ trình) là mã **hoa-thường
    lẫn lộn**, `.upper()` mù biến `QĐ-TTg` thành `QĐ-TTG` trong im lặng. Sửa theo đúng nguyên tắc
    đang dùng: **từ vựng chốt chính tả**, không phải một phép biến đổi chuỗi.
  - **Đo:** đọc lại mẫu vbpl vẫn **35 cạnh**, và cảnh báo đi từ 0 → **1** — đúng cái lỗi của
    nguồn, trước đây bị nuốt. pytest **444**, ruff sạch.
- **Done (13 quan hệ thành TẬP ĐÓNG + đọc lược đồ vbpl.vn).**
  - **Gốc rễ:** `REL_TYPES` cũ là **4 tên tự đặt** và `rel_type: str` **chưa bao giờ được đối
    chiếu với nó** ⇒ `HUONG_DAN` — một loại không có thật — sống 4 lần. Cùng bảng còn bị **chép ở
    ba nơi** (`schemas.py`, `answer.py`, `pipeline.py`). Nay một nguồn duy nhất + validator chặn ở
    **biên dữ liệu vào**, thông báo lỗi nêu đủ 13 mã hợp lệ.
  - **Cạnh CÓ KIỂU trong Neo4j** (4 chỗ Cypher). Nhờ đó viết được truy vấn §6.2 *legislative void*
    (`BAI_BO` mà không `THAY_THE`) — với một kiểu cạnh duy nhất thì câu đó **không tồn tại**.
    `khoang_trong_lap_phap()` ghi rõ: corpus có **0 `BAI_BO`** nên trả rỗng **vì thiếu dữ liệu**,
    không phải vì không có khoảng trống nào.
  - **Câu hỏi tưởng phải hỏi người thì NGUỒN trả lời.** `data/raw/vbpl/sample.json` (mẫu schema sẽ
    thu thập) có `luoc_do.outgoing/incoming` khớp đúng hai cột nhãn của v0.5 §6. Cả bốn Thông tư
    TT15/17/18/40-2024 nằm ở `incoming / "Văn bản áp dụng"` — **nhãn bị động của `CAN_CU`**, cặp
    **#8 bất quy tắc** — chứ không ở `"Văn bản quy định chi tiết, hướng dẫn thi hành"` (chỉ có
    TT34/2024). ⇒ quan hệ đúng là **`CAN_CU`**: các TT **ban hành căn cứ** NĐ52, không hướng dẫn nó.
  - **Chiều mũi tên do `outgoing`/`incoming` quyết, KHÔNG do nhãn** — một quy tắc cho cả 13 mã.
    Bằng chứng nó đúng kể cả với cặp bất quy tắc: cùng mã `CAN_CU` ra **hai chiều ngược nhau** trên
    cùng một trang (outgoing "Căn cứ ban hành" → 10 Luật; incoming "Văn bản áp dụng" → 20 Thông tư).
    Bảng nhãn **suy từ `REL_TYPES`**, không gõ tay ⇒ không thể trôi khỏi tập đóng; 26 nhãn sau
    chuẩn hoá vẫn phân biệt được từng cái (có test canh vì phép chuẩn hoá bỏ dấu phẩy).
  - **Đo:** đọc mẫu ra **35 cạnh · 0 cảnh báo** (`CAN_CU` 30 · `THAY_THE` 2 · `BAI_BO` 1 ·
    `QUY_DINH_CHI_TIET_HUONG_DAN` 1 · `DAN_CHIEU` 1). **`BAI_BO` có instance thật**: NĐ52 → NĐ16/2019
    ⇒ ca kiểm chứng §6.2 sẽ có dữ liệu khi chuyển nguồn. Sửa 6/13 hàng corpus (diff **10 dòng**,
    chiều giữ nguyên, `documents` không đụng), `kiem_quan_he` báo **0 cạnh sai**. pytest **413**.
  - Cạnh khoá bằng **số hiệu** (`52/2024/NĐ-CP`) — khoá v0.5 dùng và có sẵn trong vbpl — chứ không
    phải `doc_id`. Quy về `doc_id` chờ trường bắc cầu `so_hieu` (việc #11).
- **Done (đối chiếu lại v0.5 + G1 tầng CU — `docs/KG-CONFORMANCE-v05.md`, `ONTOLOGY-POC.md` §14g–h).**
  - **Đo lại conformance: điểm KHÔNG đổi một ô nào.** Ba đợt việc 04/08 đều ở tầng CU, không chạm
    tầng văn bản. Ghi lại thay vì làm tròn lên — một báo cáo đối chiếu mà tự cải thiện điểm sau
    mỗi lần chạm code thì hết là thước đo. Cái lớn lên: §4 "PoC đi trước v0.5" **4 → 7 mục**.
  - **Một ô sửa XUỐNG: §6 từ 4/13 còn 2/13.** Bản cũ đếm 4 vì dữ liệu có 4 `rel_type`. Đối chiếu
    từng tên: chỉ `THAY_THE`, `DAN_CHIEU` trùng; `SUA_DOI` phải thành `SUA_DOI_BO_SUNG`; 4 cạnh
    `HUONG_DAN` **không ánh xạ được** — §6.3 tách nó làm hai quan hệ mà Điều 53 k2 đối xử khác nhau.
  - **Bốn phát hiện mới, mỗi cái truy tới một dòng:** (a) `Chương` có thật trong HTML gốc — **47
    Chương + 15 Mục** trên 9 file — nhưng `extract.py:90` vứt đi, nên `Article.chapter` là trường
    chết **0/278**; (b) tên quan hệ lệch; (c) **`BAI_BO` = 0 instance** ⇒ truy vấn *legislative
    void* §6.2 sẽ **chạy nhưng rỗng**, đừng nhầm "dựng xong 13 cạnh" với "có demo"; (d)
    `_SO_HIEU_RE` chạy đúng, `so_hieu` **đã trích rồi vứt** ⇒ bắc cầu ID rẻ hơn §3.3 tưởng.
    Hai cái (a)(d) làm **đổi thứ tự phụ thuộc**: `Chuong`/`Muc` không cần chờ thống nhất ID.
  - **LỖI ĐANG SỐNG tìm ra khi đối chiếu hai tầng guard.** TT17 Đ16 k1 điểm a: guard tại Điểm là
    `('khách hàng','cá nhân')` trong khi tiết (ii) là `('khách hàng','tổ chức')`. `hop_guard` là
    AND dọc đường đi ⇒ tiết (ii) nhận **`cá nhân ∧ tổ chức`, guard bất khả thi** — vế đó vĩnh viễn
    không áp dụng cho ai. **2/2** ca có guard ở cả hai tầng đều hỏng. Test cũ không bắt vì không
    test nào canh **quan hệ giữa hai tầng**.
  - **Hai nguyên nhân độc lập, sửa cả hai:** (1) `tach_guard` trả cụm **đầu tiên** ⇒ đổi sang chỉ
    nhận khi có **đúng một** cặp `(thuoc_tinh, gia_tri)`; từ hai trở lên báo `guard_nhieu_cum` và
    **không chọn hộ**. (2) `extractor` đưa toàn văn Điểm vào ⇒ Điểm **có tiết** thì đọc trên **câu
    bao trùm**, đúng ranh giới §14e. Chỉ sửa (2) thì chưa đủ: điểm b có **hai cụm ngoặc ngay trong
    chapeau**. Kèm một sửa lỗi cắt câu: `_GUARD_CUM` nay dừng ở `)` — an toàn một chiều vì mọi cụm
    chứa ngoặc **đang** bị loại.
  - **Đo: guard 13 → 11 · guard bất khả thi 2 → 0** · cảnh báo 76 → 76 · lỗi cứng 0/49 ·
    `guard_ngoai_mau` 13 → 12, `guard_nhieu_cum` 0 → 1 · `--classify` **94 đơn vị 45/9/40** ·
    `classify_testset` **9/9** · pytest **365**.
  - **Hai đề xuất của tôi bị ĐO bác bỏ** (lần thứ ba trong ngày): nới dạng C ra 6 từ cho
    `thuoc_tinh = 'dịch'`, `'khách'` — **sai tiếng Việt**, vì danh ngữ Việt có head hai âm tiết;
    bỏ điều kiện `ket==':'` của dạng B chỉ mua **1 ca** và đó là một khoản **định nghĩa**, nơi
    guard vô nghĩa. Kế hoạch ghi "T4 16 → ~6" là **sai**, thực tế 16 → 16.
  - **T3 "nghi bịa tình thái" bỏ trống**, 9 cờ xuống T5. Người duyệt chấm 8/9 báo động giả, và
    `modality.py:65-68` đã viết trước: thêm dấu hiệu của nhóm **nguồn đã có** là *phân phối lệnh
    cấm ra từng vế* hoặc *thay từ đồng nghĩa*, không phải bịa. Bịa thật là `invented_groups` → lỗi
    cứng, 0/49. **Không** đụng `modality.py`. Số hiệu T3 giữ trống, không đánh số lại T4→T3 vì
    `flag_verdicts.jsonl` đã duyệt có ghi `tier`. **Hàng đợi 31 → 22.**
- **Done (bảng phân hoạch — `docs/ONTOLOGY-POC.md` §14f).** Chốt vế còn thiếu của câu hỏi T2.
  - **Câu hỏi ở §14c thiếu một vế.** Người duyệt trả lời *"loại trừ nhau về đối tượng áp dụng"*,
    nhưng loại trừ nhau **chưa đủ**: `(g₁→c₁)∧(g₂→c₂)` vs `(g₁∧c₁)∨(g₂∧c₂)` chỉ trùng nhau ở
    tình huống **có** một guard đúng; tình huống **không guard nào đúng** thì AND ra **miễn trừ**
    còn OR ra **bất khả thi**. Điều kiện đúng là **phân hoạch** = loại trừ nhau **và phủ hết**.
  - **Người chốt một lần cho mỗi thuộc tính, máy đối chiếu.** `data/phan_hoach.json` (người viết,
    kèm **trích nguyên văn**) + `app/ontology/phan_hoach.py`. `connector` **giữ `unknown`**; cái
    thêm vào là `ConditionItem.guard_phan_hoach` — trường **mang chứng cứ**. Chỗ thắng không phải
    2 ca hiện có mà là **trả lời một lần cho mỗi thuộc tính thay vì mỗi bản ghi**.
  - **Đo bác một quyết định thiết kế của chính tôi.** Định khoá bảng **thuần theo miền giá trị**
    (lý do: `'cá nhân'` xuất hiện với **3** `thuoc_tinh` khác nhau). Nhưng khi tra căn cứ thật:
    `khách hàng` = {cá nhân, tổ chức} (TT17 Đ2 k2) còn `tài khoản thanh toán` = {cá nhân, tổ chức,
    **chung**} (TT17 Đ3 k1). **Cùng hai chữ, hai kết luận ngược nhau** ⇒ miền tách riêng để dùng
    chung, nhưng **binding vẫn theo `thuoc_tinh`**. Khoá thuần theo tập giá trị sẽ chứng minh nhầm.
  - **Lật lại một nhãn "báo động giả" của người duyệt.** TT17 Đ16 k2 điểm b chỉ nói tới tài khoản
    `của cá nhân` và `của tổ chức`, trong khi TT17 Đ3 k1 liệt kê **ba** hình thức. Máy không kết
    luận luật thiếu (chỗ khác có thể điều chỉnh) — nó đổi câu hỏi thành thứ trả lời được:
    ***"tài khoản thanh toán chung thì áp dụng gì?"***
  - **Bốn cửa mới được kết luận "phủ hết"**: luật có câu liệt kê đóng (bắt buộc `can_cu` + `trich`)
    · không giá trị lạ · không guard trùng nhau · không giá trị nào bị bỏ sót. `chung_minh()` trả
    `None` khi **chưa khai** — khác hẳn `du=False` là *đã trả lời và chưa phủ hết*. So khớp chuẩn
    hoá hoa/thường, **không dò mờ**. Có test đối chiếu **từng câu `trich`** với `corpus.real.json`:
    trích dẫn bịa tạo cảm giác đã kiểm chứng, nguy hiểm hơn ô để trống.
  - **Đo: 6 số dự đoán trước, 5 đúng.** Tổng **76 → 76** · T5 **44 → 45** · hàng đợi **32 → 31** ·
    **0 bản ghi khác đổi**. Sai một: ghi "T2 3 → 2" trong khi nền đã là 2 sau việc chapeau, thực
    tế **2 → 1** — độ lệch đúng, con số nền lấy cũ một bước. pytest **357**, ruff sạch,
    `--classify` **94 đơn vị 45/9/40**, `classify_testset` **9/9**.
  - **Ngoài phạm vi cố ý:** guard anh em ở **tầng Điểm** (TT18 Đ9 k2, 4 nhánh) trộn hai miền —
    3 giá trị quốc tịch + 1 loại chủ thể — nên không phải phân hoạch đơn miền; cảnh báo hiện chỉ
    sinh ở tầng tiết nên phạm vi giữ đúng theo đó.
- **Done (duyệt 33 cờ — nhãn người, `anotate/flag_verdicts.jsonl`).** Cờ ĐÚNG 15 · Báo động GIẢ 8
  · Không chắc **10**. Con số đáng đọc nhất là **10/33 (30%) không quyết được** — cờ không đưa đủ
  cho người duyệt, đó là hỏng của trang chứ không phải của người đọc. Ba kết luận rút ra:
  - **T3 xếp sai mức, và chính code đã nói trước.** 8/9 cờ T3 là báo động giả — không phải mô hình
    bỗng tốt lên mà vì `modality.py:65-68` đã viết sẵn: *"thêm số lần xuất hiện của một nhóm **đã
    có sẵn** thì không [phải bịa] — đó thường chỉ là **phân phối lệnh cấm ra từng vế**, hoặc **thay
    từ đồng nghĩa**"*. Đối chiếu chữ luật đúng hai dạng đó: TT40 Đ25 k5 luật viết *"không được…;
    không được phép…"* rồi tỉnh lược vế ba, mô hình viết rõ ra; 4 ca *"khi"* là luật viết *"(trong)
    trường hợp"* — **cùng nhóm `dieu_kien`**. Tín hiệu bịa thật là `invented_groups` → lỗi cứng,
    hiện **0/49**. ⇒ T3 nên xuống T5 và đổi tên; **chưa làm**.
  - **`guard_ngoai_mau` (13 cờ) là MỘT lỗ hổng mẫu, không phải 13 việc.** 10/13 là đúng hai cụm
    `'dịch vụ ví điện tử'`, `'dịch vụ chuyển mạch tài chính'`. Thử trực tiếp: dạng C (danh ngữ trần)
    chỉ nhận khi cụm **mở đầu đơn vị**, nên `"Đối với dịch vụ ví điện tử,"` rơi ngoài cả ba dạng.
  - **Câu hỏi T2 tôi viết còn thiếu.** Người duyệt trả lời *"loại trừ nhau về đối tượng áp dụng"* —
    nhưng loại trừ nhau **chưa đủ**: với `(g₁→c₁)∧(g₂→c₂)` vs `(g₁∧c₁)∨(g₂∧c₂)`, hàng "không thuộc
    guard nào" cho AND = **miễn trừ** còn OR = **bất khả thi**. Điều kiện đúng là **phân hoạch**
    (loại trừ **và** phủ hết). Hướng đã chốt: bảng phân hoạch người viết một lần, **khoá theo miền
    giá trị chứ không theo `thuoc_tinh`** (hai ca có `thuoc_tinh` khác nhau — `khách hàng` vs `tài
    khoản thanh toán` — nhưng **cùng miền** `{cá nhân, tổ chức}`); máy **chứng minh**, không suy
    diễn; `connector` giữ `unknown`. **Chưa làm — việc kế tiếp.**
- **Done (đối chiếu v0.5):** `docs/KG-CONFORMANCE-v05.md` — xem mục dưới.

- **Done:** `docs/KG-CONFORMANCE-v05.md` — đối chiếu từng mục của `research/schema-kg-v05.html`.
  - **Phát hiện đầu tiên, quan trọng hơn mọi ô đạt/chưa: repo có HAI schema văn bản, v0.5 mô tả MỘT.** Tầng app đang chạy khoá bằng `TT40-2024` (chuỗi viết tắt do LLM sinh, `extract.py:35`); tầng PoC ontology khoá bằng `40/2024/TT-NHNN#than/dieu_41#khoan_2`. **Không có bảng map.** Cùng một Điều 41 tồn tại dưới hai khoá không quy về nhau được — trái §9 quyết định #10, và `docs/RAG-DESIGN.md §1.1` đã hứa *"id row **trùng** id node KG ⇒ không cần bảng map"*, lời hứa đó hiện **không đúng** với tầng app.
  - **Điểm theo khối:** §4 khoá nhánh **1/3** · §5 đánh số **5/6** · §3 node **4/15** · §6 quan hệ **4/13** · §7 thời gian **0/5** · §8 tin cậy **0/2** · §9 ba quyết định đạt, hai không đạt. Phần v0.5 đặc tả kỹ nhất (đánh số + khoá nhánh `than`) **đã thoả và có test canh**; phần từ cấp Điều trở lên **phần lớn chưa tồn tại dưới dạng code**.
  - **Ba chỗ MÂU THUẪN, tách riêng khỏi "chưa dựng"** — thiếu thì dựng thêm là xong, ba cái này đang nói ngược nhau ngay trong repo:
    1. **Lỗi đang sống trong UI.** `api/documents.py:49` `status = "con_hieu_luc" if effective else "het_hieu_luc"`, mà `is_effective` trả `False` khi `ref < valid_from` ⇒ **văn bản CHƯA tới ngày hiệu lực đang hiển thị là HẾT hiệu lực**. Hai trạng thái ở hai đầu đối lập của vòng đời bị gộp làm một. §7.3 có đủ bốn trạng thái chính là để chặn ca này.
    2. **Khoảng đóng vs nửa mở.** `versioning.py:37-40` dùng `vf <= ref <= vt`, trong khi `RAG-DESIGN.md §1.2` tuyên bố nửa mở là *"bộ lọc thời gian **DUY NHẤT** — không viết biến thể thứ hai ở bất cứ đâu"* và §7.1 buộc `hieu_luc_den` của bản cũ **bằng đúng** `hieu_luc_tu` của bản mới. ⇒ đúng ngày biên sẽ khớp **cả hai** phiên bản. Chưa bắn vì **0/278 điều có `valid_to`** — nghĩa là nó sẽ hỏng đúng lúc tầng thời gian bắt đầu có dữ liệu, lúc khó thấy nhất.
    3. **Khoá `#than/` hardcode ở hai chỗ** (`parser.py:232`, `citation.py:198`): Điều nằm trong quy chế kèm theo hoặc phụ lục vẫn nhận khoá `#than/` — đúng cái va khoá im lặng mà §3 dựng `VanBanKemTheo` để chặn. Chưa hỏng vì cả 18 fixture đều là thân văn bản.
  - **Hai chỗ dễ nhận vơ, phải tách bạch.** (a) `Article.chapter`/`section` **có khai báo nhưng 0/278 điều có giá trị** — trường chết, không phải node `Chuong`/`Muc`. (b) Trạng thái duyệt Supabase `pending|approved|rejected` **không phải** `da_xac_minh_nguon`: nó là *"đã có người bấm duyệt"*, còn v0.5 hỏi *"đọc Công báo hay đọc nguồn thứ cấp"* — mà §8.2 kể một ca hỏng thật nằm gọn trong vùng "thứ cấp mà tưởng là đủ". Ngược lại `Gate.pham_vi` nhận `"chuong"/"muc"` nhưng luôn kèm `suy_ra_duoc=False` là cách xử lý **trung thực**, ghi lại để không ai đi "sửa" nó thành `True`.
  - **Cách lưu quan hệ khác kiểu, không chỉ khác tên.** `graph.py:67` dùng **một** kiểu cạnh `REL` mang property `rel_type`, không phải 13 kiểu cạnh có tên ⇒ **mọi câu Cypher trong v0.5 không chạy được** (`-[:QUY_DINH_CHI_TIET_HUONG_DAN]-`, `-[:CO_PHIEN_BAN]->`). Kéo theo: **ca kiểm chứng bắt buộc của §6.2** (`BAI_BO` mà không có `THAY_THE` = *legislative void*) hiện **không chạy được**, vì `BAI_BO` không tồn tại như một loại — đó là một **năng lực v0.5 hứa** mà hệ chưa có, không chỉ là một cạnh thiếu.
  - **Bốn chỗ PoC đã đi TRƯỚC v0.5, đề nghị v0.6 hấp thụ**: tiết `(i)` (4/586 viện dẫn, cả 4 ở văn bản đã hết hiệu lực; chữ "tiết" **0 lần** trong 557k ký tự) · điều không chẻ khoản (**25/267 = 9,4%**) · `DieuKienCong` — §7 đòi `PhienBanDieu.hieu_luc_tu` nhưng **không nói lấy ngày ở đâu ra**, đây chính là mặt trích xuất của nó, kèm `moc: bat_dau|ket_thuc` chống đảo ngữ nghĩa · trục *tin cậy trích xuất* (`do_tin_cay` + `Grounding.status`) bên cạnh trục *tin cậy nguồn* của §8.
  - **Một lỗi trong chính v0.5**: §2 changelog gọi `so_khoan_goc`/`so_khoan_hau_to`, §5 (bảng chuẩn) gọi `so_goc`/`so_hau_to`. Code theo §5 — nên sửa changelog cho khớp bảng của chính nó.
- **Ship:** không đụng code. **284 pytest + ruff xanh**, `--classify` **94 đơn vị không đổi** (premise 45 · meta_cu 9 · actor_cu 40).
- **Decision:** người dùng chốt **chỉ viết báo cáo**, không sửa ba lỗi ở trên trong cùng đợt — sửa hiệu lực/khoá là thay đổi hành vi, không đi kèm một đợt đo đạc. Ba mục vào bảng "việc còn đọng, đã có chẩn đoán" kèm mức + chi phí để lần sau không phải chẩn lại.
- **Ghi chú:** báo cáo viết theo **bản working copy** của `research/schema-kg-v05.html` (v0.5 vòng 4, chưa commit), không theo bản trong git HEAD (còn 3 trạng thái hiệu lực, chưa có §1.3b `QuyTacHieuLuc`).
- **Next:** ưu tiên cao và rẻ: `status` bốn trạng thái · `is_effective` sang nửa mở (một dấu `<` + test biên) · chặn khoá `#than/` bịa. Ưu tiên cao nhưng lớn: thống nhất không gian ID — quyết định kiến trúc, chạm corpus + Neo4j + web + LanceDB, phải chốt trước khi dựng `PhienBanDieu`.

---

## 2026-08-02 (CN)

**Giai đoạn:** hạ bước phân loại xuống **mức Khoản**, chạy trước khi trích S-O-A-C.

- **Done:**
  - **`app/ontology/classify.py` — `classify_unit(text, position_context)`** theo ba phép thử A/B/C của GraphCompliance, chạy **trước** extractor và **không gọi LLM lần nào**. Mọi nhánh quyết định ghi vào `test_path` để người đọc thấy được phép xấp xỉ nào đã dùng — Test A trong bài viết gốc là quan hệ **cú pháp**, ở đây không có phân tích cú pháp tiếng Việt nên nó được xấp xỉ bằng luật tiêu đề + từ điển tình thái. Nói thẳng chỗ này trong `docs/ONTOLOGY-CLASSIFY.md` §3.
  - **Đổi kết luận về "Đối tượng áp dụng", có bằng chứng đo được.** §13 xếp cả Điều là `meta_cu`; nay **từng khoản là `premise`/`vai_tro`**, còn cả Điều vẫn là cổng chủ thể. Lý do không phải tranh luận thuật ngữ: 4 CU mà bản trước sinh ra từ ND52 Điều 2 đều **suy biến** — khoản 1 và 2 có `action` **trùng khít `subject`**, khoản 3 và 4 lấy mệnh đề định ngữ của chính danh ngữ làm "hành vi". Nhãn *"Là đối tượng áp dụng"* ở khoản 1 là vị ngữ mô hình tự dựng để lấp ô trống (cụm đó chỉ có trong **tiêu đề Điều**). Phép thử phân biệt: cổng phải là **mệnh đề có giá trị đúng/sai**; `"Tổ chức cung ứng dịch vụ trung gian thanh toán."` là **danh ngữ trần**, không có vị ngữ để vi phạm hay để chặn.
  - **Sổ đăng ký premise (`premise.jsonl`)** — 45 bản ghi (36 định nghĩa · 7 vai trò · 2 phạm vi), giữ nguyên khối văn bản + `char_span`, **không hỏi LLM một chữ nào**. Bí danh do chính văn bản tuyên bố (`"(sau đây gọi là khách hàng)"`) trích tất định bằng regex: đo trên corpus **73 lần/11 văn bản**, văn bản nào cũng có. Trước đây bí danh bị nhét vào `subject.label`, chỗ không phân biệt được với một câu diễn giải bất kỳ.
  - **`Gate` thay cho `gates: list[str]` phẳng.** List phẳng không diễn đạt được hai tình huống có thật: (1) "toàn văn bản" mà liệt kê thì ND52 phải ghi 267 khoá và sai ngay khi văn bản được bổ sung; (2) `"Quy định tại Mục này…"` — parser **không có node Mục**, list phẳng buộc phải trả `[]`, không phân biệt được với "không chặn gì". `pham_vi` + `targets` + `suy_ra_duoc` nói đúng cả ba trạng thái.
  - **Hai trường sinh ra từ văn bản thật, không phải thiết kế bàn giấy**: `phu_dinh` (TT40 Đ26 K2 — *"Quy định tại khoản 1 Điều này **không** áp dụng đối với…"*, bỏ sót chữ "không" là **đảo ngược** hiệu lực của cả khoản 1) và `ngoai_tru` (TT40 Đ52 K1 — *"…**trừ trường hợp** quy định tại khoản 2, 3, 4, 5 Điều này"*, khác hẳn phạm vi phủ).
  - **Cổng hiệu lực không mặc nhiên phủ cả văn bản**: TT40 Điều 52 có **4 khoản** đặt mốc hiệu lực riêng cho từng nhóm Điều. Bản đầu gán cả 6 khoản thành "cả văn bản" — sai phạm vi gấp nhiều lần. Nay giải bằng `citation.py`, lấy viện dẫn **đứng trước** mệnh đề hiệu lực.
  - **Bắt được 1 bug thật trong `citation.py`**: `_NUM_LIST` cho phép từ nối tiếp danh sách là `khoản` **hoặc** `Điều` bất kể đang đọc cấp nào, nên `"Điều 35, khoản 4 Điều 47"` bị đọc thành Điều 35, **Điều 4**, Điều 47 — sai đích, im lặng. Tách thành `_KHOAN_LIST`/`_DIEU_LIST`, từ nối tiếp phải **cùng cấp**. 193 test cũ vẫn xanh.
  - **6/94 đơn vị bị gán nhầm ở lần chạy đầu, đều do bẫy "phải" phi-deontic**: `"tổ chức **không phải là** ngân hàng"` (hệ từ phủ định) và `"số tiền **phải thu, phải trả**"` (danh ngữ kế toán). Che hai khuôn này **chỉ ở tầng phân loại** — `modality.py` cố ý giữ nguyên độ nhạy vì ở đó bắt nhầm chỉ tốn một cảnh báo, còn bỏ sót là lọt một nghĩa vụ bịa ra. Thêm chốt: tiêu đề `premise` không bị dấu hiệu tình thái lật âm thầm, có cãi nhau thì lấy tiêu đề (đã đo) + **cảnh báo**.
  - **`eval/ontology/classify_testset.py`** — 5 case bắt buộc của đề bài, in bảng kỳ vọng vs thực tế + ghi JSON, **9/9 khớp**, không gọi LLM. Case 2 chạy **cả hai** biến thể: luật thật viết *"**từ** ngày"*, đề bài viết *"kể từ ngày"*. Case 5 đánh dấu rõ là **câu giả định**, không trích từ văn bản thật.
  - Fixture mới: ND52 Điều 37, TT40 Điều 52 (hiệu lực thi hành) — để đường meta-CU được **chạy** chứ không chỉ được viết.
  - **Trang duyệt trước đó không hiện vai — người dùng báo, đúng.** 49 CU trong danh sách trông y hệt nhau dù **9 cái là meta-CU**, và **45 bản ghi premise không xuất hiện ở đâu cả**: nghĩa là cả bước phân loại nằm **ngoài tầm duyệt**, làm đúng hay sai cũng không ai kiểm được. Sửa: huy hiệu `ACTOR`/`META`/`PREMISE` + bộ lọc theo vai; CU có ô chọn `role` (sửa được **vai** chứ không chỉ span); meta-CU hiện **bảng cổng** (kind · phạm vi · đích · `LOẠI TRỪ` khi `phu_dinh` · `chưa quy được về khoá node` khi `suy_ra_duoc=False`); premise có khung riêng (loại con + bí danh + nguyên văn + cổng nó góp vào) và ẩn hẳn thanh gán Subject/Action vì nó không có 4-tuple.
  - **Hai hợp đồng, hai file**: `gold.jsonl` (CU) và `gold.premise.jsonl`. Trộn chung sẽ khiến `run_eval.py` gặp bản ghi không có `subject_span` và tính sai **trong im lặng**.
  - **`run_eval.py` thêm `role_accuracy`** — vai là phán quyết **độc lập** với span: một CU neo hoàn hảo nhưng gán nhầm `meta_cu` thì **không bao giờ** bị phán định vi phạm, mà sai kiểu đó không hiện ra ở bất kỳ chỉ số span nào.
  - **Một lỗi tiềm ẩn sửa luôn**: `build_payload` dùng `dieu.khoan` trực tiếp nên Điều **không chẻ khoản** (9.4% số điều) sẽ làm hỏng cả trang bằng `StopIteration`; đổi sang `khoan_de_trich`. Và `esc()` không escape `"`/`'` — bí danh được nhả vào **thuộc tính** `value=` của ô nhập, một dấu nháy trong luật là vỡ trang.
  - **Kiểm bằng mắt trong Chrome** (không chỉ tin test): 94 mục, bộ lọc đếm đúng 40/9/45, nhảy ▶ đi trong phạm vi đang lọc, ND52 Đ2 K4 tô xanh cả khoản + tô vàng riêng cụm "khách hàng", bấm Lưu ghi ra đúng hai file với hai bộ trường tách bạch. Xoá hai file sau khi thử vì 0/94 đã duyệt.
  - **`subject: null` cho meta-CU không có bên bị ràng buộc** (đề xuất của người dùng, có tiền lệ trong bài báo). *"Nghị định này có hiệu lực thi hành từ ngày 01/7/2024"* có chủ ngữ **ngữ pháp** nhưng không có **tác nhân** nào để tuân thủ hay vi phạm — ⟨S⟩ của GraphCompliance là *bên bị ràng buộc*, không phải chủ ngữ câu. Listing 1 của bài báo đã chấp nhận `"context": null` khi trường không áp dụng; đây là cùng loại vắng mặt về **cấu trúc**. Ranh giới cố ý hẹp: chỉ cổng `thoi_gian`/`lanh_tho`; cổng `chu_the` (role qualification) **vẫn bắt buộc** vì nó CÓ một vai cần định danh; meta-CU **chưa xác định được cổng** cũng vẫn bắt buộc (không có cổng = chưa có căn cứ nào để miễn). `null` chỉ có nghĩa "không áp dụng", không bao giờ là "chưa trích được": uid sai vẫn là lỗi mất provenance kể cả ở đơn vị được miễn, và ô trống vẫn hiện thành một dòng trong trang kiểm chứ không biến mất. Prompt sửa để nói thẳng với mô hình rằng khoản này trả `"units": []` — miễn mà không nói thì nó vẫn điền.
  - **Đo lại:** 8/9 meta-CU ra `subject: null`; đúng một cái giữ subject là TT40 Đ26 K2 (`chu_the`). Lỗi cứng ở ô `subject` **3 → 0**. **Nhưng tổng bản ghi có lỗi cứng 4 → 5**: các diễn giải lệch-neo **dịch sang `conditions[]`**. TT40 Đ52 K3/K4/K5 **không có điểm nào** mà mô hình vẫn sinh 1–2 "điều kiện", neo vào nửa câu nêu phạm vi rồi gắn nhãn bằng nửa câu nêu ngày — cả hai nửa đều là chữ thật của cùng khoản, nên là lệch **phạm vi neo**, không phải bịa. Nói rõ chứ không báo là đã xong.
  - **Chỗ hổng thật lộ ra**: `Gate` có `kind="thoi_gian"` **nhưng không có trường ngày**. Mốc hiệu lực — thứ duy nhất đáng kể của cổng thời gian — hiện chỉ sống dưới dạng chữ tự do trong `action`. Đưa lên hỏi thay vì tự nới, vì nó cùng với việc cho `conditions` rỗng sẽ đẩy meta-CU loại thời gian ra xa hẳn schema 4-tuple.
- **Done (chốt câu hỏi mở — `DieuKienCong`, xem `docs/ONTOLOGY-CLASSIFY.md` §4.2):**
  - **Quyết định: giữ 4-tuple, structure hoá ô điều kiện, KHÔNG tách schema riêng cho meta-CU.** Tiền lệ ngay trong Listing 1 của bài báo — `condition` ở đó đã là JSON lồng (`{"any": [...]}`), không phải chuỗi phẳng. Thêm `DieuKienCong{kind, ngay, moc, raw_text, char_span, ghi_chu}` trên `ComplianceUnit`.
  - **Phản biện 1 — luật "char_span phải liên tục" trong đề xuất không bao giờ bắn được, đã bỏ.** `resolve()` trả `hull(units, uids)`: span liền mạch **theo cấu trúc**, `quote` chỉ thu hẹp bên trong bao lồi, kiểu là `tuple[int,int]` ⇒ span "nhảy cóc" **không biểu diễn được**. Luật đó sẽ luôn xanh và cho an toàn giả. Lỗi thật: span đúng và liền, còn *nhãn* mô tả chữ **ngoài** span — và guard **đã bắt được** (chính là 3 lỗi cứng đó). Chặn bằng **cấu trúc**: meta-CU cổng `thoi_gian`/`lanh_tho` **và** Khoản **không chẻ Điểm** ⇒ `conditions` rỗng. Vế thứ hai bắt buộc: TT40 Đ52 K6 cũng là cổng thời gian nhưng **có** điểm a/b mang mốc hết hiệu lực thật.
  - **Phản biện 2 — `moc` chứ không phải một trường "ngày hiệu lực".** TT40 Đ52 K6 điểm a/b viết *"có hiệu lực thi hành **đến hết ngày** 14/8/2024"* — mốc **kết thúc**. Nhét ngày kết thúc vào ô đọc ra là "ngày bắt đầu có hiệu lực" là đảo ngược hiệu lực **trong im lặng**, đúng loại lỗi mà `phu_dinh` đã sinh ra để chặn.
  - **Phản biện 3 — không overload `suy_ra_duoc`.** Cờ đó nghĩa là *"phạm vi quy được về khoá node"*. K3 có `suy_ra_duoc=False` (viện dẫn phân phối) trong khi ngày parse hoàn hảo — hai thứ độc lập, gộp lại là mất khả năng biết cái nào hỏng. Trạng thái ngày ở `ngay is None` + `ghi_chu`, phân biệt **ba** tình huống: đọc được · không có ngày tuyệt đối (*"kể từ ngày Thông tư này có hiệu lực"*) · có cụm ngày nhưng không hợp lệ.
  - **Ai sinh `char_span` mới là chỗ quyết định** — đề xuất yêu cầu span khớp đúng `raw_text` nhưng không nói ai sinh nó. Ở đây là **regex của ta** chạy trên `khoan.text` rồi quy về `dieu.text` (`+ khoan.start`, cùng kỷ luật `alias_span`), không đi qua tay mô hình lần nào ⇒ "không lan sang phần câu khác" đúng **theo cấu trúc**, không nhờ validate chạy sau.
  - **Đo lại, theo từng bản ghi — lỗi cứng 5 → 2, KHÔNG phải "gần 0" như kỳ vọng ban đầu.** K3/K4/K5 sạch (1+1+2 → 0). Còn đúng hai cái, đều đã lường trước: **TT40 Đ52 K6** (có điểm thật, bệnh khác — người dùng chọn để lại, xem §6 mục 7a) và **TT17 Đ16 K2** (actor-CU, guard bắt **đúng** nhãn bịa "phải được" — phải giữ, không tối ưu cho con số 0). Mốc ngày tách được cho **7/9** meta-CU, 6 cái ra ngày ISO; mọi `char_span` round-trip đúng. Phụ phẩm: K1/K2 trước cũng sinh điều kiện lệch-neo (chưa tới lỗi cứng) — nay cũng rỗng.
  - **`lanh_tho` cố ý chưa dựng trường**: 0 case trong corpus, `detect_gate` chưa bao giờ phát ra loại cổng đó. Nó vẫn nằm trong luật `conditions` rỗng (không tốn gì) nhưng bịa một trường dữ liệu cho case chưa từng gặp là thiết kế không có dữ liệu.
  - Bày ra được để duyệt: `report.py` thêm dòng `dieu_kien_cong` + dòng `conditions` *"không áp dụng"* (ô trống có chủ ý phải **thấy được**); `review_ui.py` hiện mốc ngày trong bảng cổng; `make_gold_seed.py` mang trường mới vào khung — regex vẫn sai được nên không được mặc nhiên coi là đúng.
- **Done (hợp đồng modality guard khi `quote` thu hẹp span — `docs/ONTOLOGY-CLASSIFY.md` §4.3):**
  - **Đo trước khi sửa, và phép đo lật ngược tiền đề.** Quét **296 nhãn không rỗng** trong `pred.jsonl` tìm từ nghĩa vụ/cấm đoán ("phải", "phải được", "cần", "bắt buộc", "có nghĩa vụ", "không được", "cấm") có trong **nhãn** mà không có trong **span**, rồi đối chiếu ngược văn bản gốc: **đúng 1/296**, và cụm đó **có trong văn bản gốc, nguyên văn**. Không có thói quen "nâng cấp câu mô tả thành câu nghĩa vụ" — tần suất bịa thật là **0/296**.
  - **TT17 Đ16 K2 KHÔNG phải fabrication như đã ghi hôm qua — là báo nhầm.** Mô hình chọn `units` `[6…14]` = **trọn** điểm c; bao lồi chứa nguyên văn *"Các thông tin, dữ liệu **phải được** lưu trữ an toàn, bảo mật, **được** sao lưu dự phòng…"* (đơn vị [13]). Rồi nó dùng `quote` thu hẹp span về **câu đầu** của điểm c, guard so nhãn với span đã hẹp ⇒ kết luận "bịa nhóm nghia_vu". Nhãn trung thành với bằng chứng mô hình đã trích dẫn; chỗ hỏng là `quote` thu hẹp sai chỗ.
  - **Chẩn đoán TT40 Đ52 K6 ghi hôm qua cũng sai.** Mục 7a viết *"mô hình bị phạt vì đã neo chính xác hơn"*, tức cùng bệnh với TT17. Đo lại: **không phải**. Điểm a bị tách thành 5 đơn vị `[18…22]`, mô hình chỉ chọn `[22]`, **bao lồi chính là đơn vị đó** — nới ra không lấy thêm được chữ nào. Số `9a`, `11`, `4`, `23/2019` thật sự không nằm trong bằng chứng nó viện ra ⇒ **lỗi cứng là phán quyết đúng**, chỗ hỏng nằm sớm hơn guard (mô hình **chọn thiếu đơn vị**).
  - **Luật: cáo buộc VẮNG MẶT phải kiểm trên bằng chứng đã trích dẫn.** `modality.relax_absence` — trước khi cho thành lỗi cứng, kiểm lại trên **bao lồi các đơn vị mô hình đã chọn**, không phải trên lát cắt `quote` đã thu hẹp. Không thể kết tội bịa một cụm nằm nguyên văn bên trong chính bằng chứng bị viện ra.
  - **Nới CÓ CHỌN LỌC, ranh giới ở tính đơn điệu.** Nới `invented_groups` + `added_numbers` (đơn điệu: nguồn rộng ra thì phát hiện chỉ co lại). **Không** nới `flips` và `condition_to_obligation` — cái sau **ngược** đơn điệu, và đây không phải lý thuyết: nới cả gói cho đúng case TT17 điểm c thì `invented_groups` hết nhưng `condition_to_obligation` **lại nổ**, vì bao lồi 1097 ký tự có *"khi có yêu cầu từ cơ quan có thẩm quyền"* ở mệnh đề mà bản tóm tắt 150 ký tự không nhắc. Nới cả gói là đổi một báo nhầm này lấy một báo nhầm khác.
  - **Hạ mức không được im lặng.** Mỗi lần hạ đều để lại cảnh báo nêu đích danh cụm bị hạ **và** hệ quả: *"`text` của trường này KHÔNG chứa đoạn mà nhãn đang mô tả"*. Hết lỗi cứng ≠ đã ổn. Cố ý **không** tự nới span về bao lồi: sửa provenance bằng suy đoán còn tệ hơn nêu tên chỗ lệch.
  - **Bắt được chỗ này lại lòi ra một chỗ giấu tin khác**: `make_gold_seed.to_seed` cắt cảnh báo ở `[:5]` cho gọn, mà đúng hai dòng trên nằm ở vị trí 6–7 của 10 ⇒ khung duyệt hiện ra bản ghi sạch còn lý do nó sạch thì bị cắt mất. Đã bỏ cắt + thêm test canh.
  - **KHÔNG làm hai việc trong đề xuất, vì phép đo nói là thừa:** (a) danh sách từ khoá deontic thứ hai chạy song song `modality.py` — nó sẽ trôi lệch khỏi `MODALITY` mà không bắt thêm được gì khi tần suất bịa thật là 0/296; (b) siết prompt — sửa prompt để chữa 1 case là đem 295 nhãn còn lại ra đánh cược, trong khi tầng tất định chữa được mà không đụng hành vi mô hình. Cũng không có chuyện "label trộn với modality": `ComplianceUnit` **chưa từng** có trường modality riêng để mà lặp.
  - **Đo lại:** lỗi cứng **2 → 1**. Trên 49 CU chỉ **một** bản ghi đổi (TT17 Đ16 K2), từ 1 lỗi cứng thành 4 cảnh báo nêu rõ lý do. Xác nhận bằng cách phát lại `build_cu` offline trên **chính output đã ghi** trước khi tốn một lần gọi API nào.
- **Done (menu đơn vị bị vỡ vì `\n` của HTML — `docs/ONTOLOGY-CLASSIFY.md` §4.4):**
  - **Mở dữ liệu ra xem trước khi sửa, và mục 7a sai LẦN THỨ HAI.** Điểm a của TT40 Đ52 K6 là **MỘT câu, 142 ký tự, 7 dòng**: `'a)\nĐiều 9a\nvà\nkhoản 4 Điều 11\nđã được sửa đổi, bổ sung theo Thông tư số\n23/2019/TT-NHNN\ncó hiệu lực…'`. Các số nằm ở đơn vị `[18]`–`[21]` mà mô hình không chọn — nhưng gọi đó là "mô hình chọn thiếu" là dừng quá sớm: menu bày ra cho nó có 4/5 mảnh là **câu cụt không có vị ngữ**. Với cái menu đó thì **không có lựa chọn nào đúng để mà chọn**.
  - **Truy được tới dòng code.** `clean_text` giữ mỗi dòng nguồn một dòng và chỉ nối lại mảnh hyperlink *bắt đầu bằng dấu câu*; nguồn là HTML nên mỗi viện dẫn nằm trong thẻ `<a>` chiếm trọn một dòng; `segment()` coi `\n` là ranh giới cứng; `_MIN_UNIT = 15` gộp mảnh dưới 15 ký tự mà `'khoản 4 Điều 11'` và `'23/2019/TT-NHNN'` **dài đúng 15** — hụt một ký tự để được gộp.
  - **Sửa ở tầng tách, không đụng guard**: thêm mức 0 cho `segment()` — gom dòng nối tiếp một câu (dòng trước chưa tận cùng bằng `.`/`;`/`:`), **chỉ gom trong cùng một Điểm**. Vế sau bắt buộc: thiếu nó thì một Điểm không có dấu kết sẽ nuốt trọn Điểm sau, đổi lỗi vỡ vụn lấy lỗi dính liền. Đây là chỗ hỏng **nằm trước** mọi tầng chống bịa: `char_span` do ta tính nên bịa provenance là bất khả thi, nhưng tập đóng để chọn mà đã sai thì đảm bảo đó rỗng.
  - **Đo diện rộng (16 fixture):** **90/267** chỗ xuống dòng là cắt giữa câu, ở **21/94** khoản. Đơn vị **293 → 237**; đơn vị kết thúc giữa câu **64 (22%) → 0**; riêng K6 **27 → 6**. Bất biến span + không chồng lấn + đơn vị nằm trọn trong Điểm: canh trên **toàn corpus**, không chỉ 1 fixture.
  - **Hệ quả 1 → 3 → 1: hai khiếm khuyết CÓ SẴN của guard lộ ra khi span dài hơn.** K6 sạch nhưng 3 bản ghi khác đỏ lên. Đọc từng cái đối chiếu luật: 2 báo nhầm, 1 đúng.
  - **Hai giả thuyết đầu của tôi về cách tách chúng đều SAI khi soi opcode** — `flips` *không* bắt được case hồi quy gốc (nên không gộp hai luật làm một được), và dấu hiệu điều kiện bị mất nằm trong opcode `delete` ở **cả hai** case (nên loại opcode cũng vô dụng). Dấu hiệu tách được, tìm bằng cách nhìn dữ liệu: (a) **`flips`** — đảo cực là phát biểu về việc *tráo một từ* nên hai vế phải ngắn; flip thật đo được là **1↔1** từ, báo nhầm là **29↔6** (nhãn nén một danh sách liệt kê) ⇒ chặn ở `_FLIP_MAX_TU = 6`; (b) **`condition_to_obligation`** — xét cặp **(dấu hiệu cứng + từ liền sau)**: case gốc `"phải đáp"` **không** có trong nguồn (luật viết *"khi đáp ứng"*) ⇒ vẫn nổ, còn TT17 Đ16 K1 điểm c `"không được thực"` **có** nguyên văn ⇒ mô hình chép chứ không chế ⇒ im. Xét riêng dấu hiệu thì không tách được vì cả hai bên đều có nó.
  - **Cố ý GIỮ lỗi cứng còn lại**: TT40 Đ26 K2 đổi *"Điều này"* → *"Điều 26"*. Suy ra đúng, nhưng số 26 không nằm trong đoạn được viện dẫn, mà `citation.py` đã giải viện dẫn tương đối một cách **tất định** rồi — không cần mô hình suy hộ kèm một con số tự điền. Đây là **lớp lỗi thứ ba**, khác hẳn bịa và lệch neo, xứng đáng một quyết định riêng.
- **Done (lớp lỗi thứ ba: khai triển viện dẫn tương đối — `docs/ONTOLOGY-CLASSIFY.md` §4.5):**
  - **Người dùng chốt hướng 2** (luật hẹp) sau khi tôi nêu ba lựa chọn cho TT40 Đ26 K2: luật viết *"Quy định tại khoản 1 **Điều này** không áp dụng…"*, mô hình viết *"Quy định tại khoản 1 **Điều 26**"*. Guard đúng hợp đồng, mô hình cũng đúng về nghĩa — đây là **lớp lỗi thứ ba**, khác hẳn bịa và lệch-neo.
  - **Đo trước khi dựng luật, đúng kỷ luật đã đặt.** Quét 294 nhãn: **1** nhãn thêm số so với đoạn đã neo · **1** trong đó nguồn có cụm tự trỏ · **1** số khớp đơn vị đang xét · **0** case "khớp khuôn nhưng số khác". Dòng cuối bằng 0 nghĩa là **corpus không kiểm được vế chống lọt** — phải canh bằng test dựng tay, và test ghi rõ là dựng tay.
  - **`modality.relax_dereference` — ba điều kiện, đủ cả ba mới hạ mức**, cả ba tất định: (1) đoạn đã neo thật sự chứa `"Điều này"`/`"khoản này"`; (2) số bị tố cáo khớp đúng số Điều/Khoản đang xét; (3) trong nhãn, số đó đứng **ngay sau** đúng từ đó. Vế 3 chống lọt: thiếu nó thì nhãn bịa *"áp dụng cho **26** tổ chức"* trong Điều 26 cũng được tha.
  - **Cố ý KHÔNG dựng cho `điểm` và `"Thông tư này"`**: điểm đánh bằng chữ cái nên không sinh số; còn số hiệu văn bản thì chưa gặp case nào mô hình khai triển ⇒ dựng trước là thiết kế không có dữ liệu.
  - **Vì sao hạ mức chứ không siết mô hình:** `citation.py` đã giải viện dẫn tương đối thành khoá node ở `references` **tất định** rồi — bản ghi mang sẵn `['40/2024/TT-NHNN#than/dieu_26#khoan_1']`. Nhãn chép thêm số vào **không mang thêm thông tin**. Phép nới chỉ để bản ghi khỏi bị đánh dấu không dùng được.
  - **Lỗi cứng 1 → 0, và con số đó KHÔNG được đứng một mình.** Nó là 0 vì **2 bản ghi được nới**, mỗi cái để lại một câu cảnh báo **khác nhau** (có chủ ý — người duyệt phải biết bản ghi sạch vì lý do nào): TT17 Đ16 k2 nới bằng `relax_absence` (*"quote thu hẹp sai chỗ"*), TT40 Đ26 k2 nới bằng `relax_dereference`. Toàn corpus còn **82 cảnh báo trên 28/49 bản ghi** — 0 lỗi cứng **không** có nghĩa là hết việc duyệt.
- **Done (tách kiểu `ActorCU` / `MetaCU` — `docs/ONTOLOGY-CLASSIFY.md` §4.6):**
  - **Người dùng chốt hướng B** sau khi tôi bày ba lựa chọn. Câu hỏi: meta-CU cần hai trường ngoài bài báo để nói được điều nó muốn nói, trong khi hai ô ⟨S,A⟩ rỗng — giữ chung 4-tuple còn đúng không?
  - **Bốn bằng chứng, không phải thẩm mỹ.** (1) **9/9 meta-CU không có bên bị ràng buộc** — 8 khai `None`, cái thứ 9 điền *"Quy định tại khoản 1 Điều này"*, một **tập quy phạm** không tuân thủ/vi phạm được. (2) **⟨A⟩ không phải hành vi**: 8 cổng thời gian có `action` = *"có hiệu lực thi hành"*, **3 cái giống hệt nhau từng chữ** — trạng thái của quy phạm, không phải việc ai phải làm. (3) **Bài báo KHÔNG công bố listing nào cho meta-CU** (chỉ 1 ví dụ actor-CU, Article 37 GDPR) ⇒ lý lẽ "trung thành với bài báo" đang bảo vệ một quy ước bài báo **không đặt ra**. (4) **Sự tách biệt VỐN ĐÃ TỒN TẠI** — 6 nhánh `if role ==` trong `extractor.py` + 2 khối prompt, chỉ là viết bằng if/else thay vì bằng kiểu, nên người đọc `pred.jsonl` không thấy.
  - **Hình dạng mới**: `GroundedUnit` (id · references · warnings · errors) → `ActorCU` (subject **BẮT BUỘC** · subject_source · action · logic · conditions) và `MetaCU` (gates · dieu_kien_cong · **menh_de** · logic · conditions). `menh_de` thay `action` ở meta-CU: để một ô mang hai nghĩa tuỳ vai là đúng loại mơ hồ im lặng mà `suy_ra_duoc` đã phải sinh ra để cứu cho `targets`. `conditions` giữ tên ở cả hai vì với cổng nó đúng là *điều kiện của cổng*.
  - **`subject` mô hình lỡ khai được GỘP vào `menh_de`, không vứt.** TT40 Đ26 k2 có hai span **liền kề** (`[346,375]` + `[376,397]`); vứt vế đầu là mất nửa câu, mà đó lại là vế mang viện dẫn `gates.targets` suy ra từ đó. Span thực tế nới **[376,397] → [343,398]**.
  - **Cái mất, ghi rõ**: cổng `chu_the` không còn ô nào cho **tên vai**. Lý lẽ cũ (*"role qualification có một vai cần định danh"*) dựa trên ví dụ **giả định**; cổng `chu_the` duy nhất trong corpus không nêu vai nào, nó nêu **quy định**. Đúng kỷ luật đã áp cho `lanh_tho` — 0 case thì không dựng trường. Có test canh đích danh chỗ này.
  - **Truyền `gates` cho actor-CU nay ném `ValueError`** thay vì âm thầm bỏ kèm cảnh báo: sai ở chỗ gọi thì phải nổ tại chỗ gọi, không được trôi xuống một bản ghi trông hợp lệ.
  - **Khung duyệt + `run_eval` tách theo**: meta-CU có `menh_de_span`, actor-CU có `subject_span`/`action_span`, **không bên nào mang ô của bên kia**. Trước đây xuất chung một danh sách phẳng nên meta-CU luôn có `subject_span: null` — ô đó không phân biệt được "không áp dụng" với "người duyệt chưa gán". Đổi khoá localStorage sang `lexflow-gold-v3` vì tiến độ lưu theo shape cũ không còn đọc đúng.
  - **Đo sau khi tách**: 49 CU = **40 ActorCU + 9 MetaCU**; meta có `subject`/`subject_source`/`action`: **0**; actor có `gates`/`dieu_kien_cong`/`menh_de`: **0**; actor thiếu `subject`: **0**. Lỗi cứng **0/49 không đổi**, `--classify` **không đổi một dòng**, `classify_testset` 9/9.
- **Ship:** chưa deploy. **284 pytest + ruff xanh** (191 → 221 → 226 → 235 → 258 → 268 → 276 → 283 → 284), `classify_testset` **9/9**, bảng `--classify` **không đổi một dòng** (94 đơn vị: premise 45 · actor_cu 40 · meta_cu 9). Batch: **49 CU** (40 ActorCU + 9 MetaCU) · **45 premise** · **36 KhaiNiem**; cổng **5/9 quy được về khoá node**; lỗi cứng **0/49** (2 bản ghi được nới, có ghi tên). Đã commit + push: `8ec3ab4` (PoC) · `658ac22` (bảng review) · `75e59f2` · `7649fc7` · `63d7939`.
- **Decision:** **thà bỏ đích còn hơn phát ra khoá sai.** Văn phạm viện dẫn hiện chưa đọc được danh sách nhiều cấp (`"khoản 2 Điều 17, Điều 18, Điều 19…"` — đúng ra khoản 2 **chỉ** của Điều 17; `"…khoản 1, …khoản 2 Điều 25"` — Điều nằm ở cuối, dùng chung). Hai hình thái này bị **bỏ** kèm `suy_ra_duoc=False` + lý do, thay vì đoán: `dieu_18#khoan_2` là một khoá **sai** trông y hệt khoá đúng. Sửa tử tế cần viết lại thành parser danh sách phân phối — việc riêng.
- **Nhận xét để hỏi mentor:** meta-CU dùng chung schema 4-tuple (theo đúng yêu cầu) nhưng chạy thật thì hai ô `subject`/`action` **không hợp** với mệnh đề hiệu lực — chủ thể của *"Quy định tại Điều 11, Điều 12… có hiệu lực từ ngày…"* là một **tập quy định**, không phải tác nhân. 3/6 meta-CU của TT40 Đ52 bị guard chặn cứng đúng ở ô `subject`. Thông tin thật của chúng nằm trọn trong `gates`.
- **Bài học lặp lại ba lần, ghi ra để khỏi lặp lần thứ tư:** *"phạt vì trích chính xác"* · *"bịa phải được"* · *"mô hình chọn thiếu đơn vị"* — cả ba đều nghe hợp lý và đều sai khi mở dữ liệu thật ra xem. Mỗi lần chỉ mất vài phút để in nguyên văn đoạn luật ra, mà mỗi lần không in thì mất một vòng sửa nhầm chỗ.
- **Next:** bộ nhãn vẫn **0/94 đã duyệt** — chờ người gán, và đây là chỗ yếu nhất: mọi số hiện tại là **máy tự chấm máy**, đo nhất quán nội bộ chứ không đo tính đúng. Ba việc còn để ngỏ: (1) **hai phép nới đều giảm độ nhạy** — `relax_absence` khi bao lồi rộng, `relax_dereference` ở khuôn `"Điều này"`; cả hai chỉ chạy khi đã có lỗi cứng và luôn để lại cảnh báo, hiện 2/49 bản ghi, cần theo dõi khi corpus lớn hơn; (2) **`_MIN_UNIT = 15`** vẫn là ngưỡng chọn tay không có căn cứ đo đạc; (3) vế chống lọt của `relax_dereference` chưa kiểm được bằng dữ liệu (0 case trong corpus). Chưa dùng nhãn `role` để **gate** thật (mới gắn nhãn, chưa chặn). Bí danh trong đơn vị actor-CU (1 chỗ: TT18 Đ9 K2) chưa có nơi lưu.

---

## 2026-08-01 (T7)

**Giai đoạn:** thí nghiệm mở khoá tầng chuẩn tắc đang bị treo ở KG v0.5 §10.2.

- **Done:**
  - **PoC `app/ontology/`** — trích Compliance Unit ⟨Subject, Object, Action, Constraint⟩ **mức Khoản** từ luật VN thật, ý tưởng lấy từ GraphCompliance (arXiv:2510.26309). Đơn vị trích xuất là Khoản chứ không phải Điểm, vì Điểm là mệnh đề tiếp nối câu bao trùm (chapeau) và đã lược bỏ chủ ngữ — mỗi Điểm thành một phần tử `conditions`. Khớp sẵn hai quyết định đã chốt: chunk mức Khoản (`RAG-DESIGN.md` §2) và Điểm dựng theo nhu cầu (KG v0.5 §9). Từ vựng ánh xạ thẳng sang `ChuThe`/`NghiaVu`/`NgoaiLe`, khoá node theo chuẩn v0.5 §4 (`52/2024/NĐ-CP#than/dieu_22#khoan_2`).
  - **Parser giữ offset ký tự** (`parser.py`) — provenance mức ký tự đầu tiên của repo (trước đó `grep char_span|offset` = 0 hit). Bất biến `text[start:end] == node.text` được test canh trên mọi nút.
  - **Neo bằng chứng không tin LLM đếm** (`extractor.py`): LLM chỉ trả `quote` chép nguyên văn, code tự `find()` ra `char_span` — 3 bậc `grounded / normalized / not_grounded`. Dùng lại `app/core/llm.chat_json` (Gemini, `temperature=0`), không thêm dependency/API key.
  - **Verify trên ND52-2024 Điều 22**: parser ra 3 khoản, khoản 2 ra đủ 8 điểm `a b c d đ e g h`; K1 2/2 neo nguyên văn, K2 6/10 nguyên văn + 3 sau chuẩn hoá, K3 5/5. **Cơ chế neo bắt được 1 hallucination thật**: Gemini trả *"**phải** đáp ứng đầy đủ"* trong khi luật viết *"cấp Giấy phép **khi** đáp ứng đầy đủ"* — tự biến điều kiện thành nghĩa vụ, câu vẫn xuôi nên đọc lướt không thấy.
  - 22 test offline mới + `docs/ONTOLOGY-POC.md`, fixture `data/fixtures/ND52-dieu22.txt` (offset neo vào đúng file này nên phải commit).
- **Done (chiều — giai đoạn 2 của PoC):**
  - **Chuyển từ "phát hiện bịa" sang "ngăn bịa": giao thức menu span.** LLM giờ **chọn số hiệu đơn vị** trong một tập đóng do `app/ontology/segmenter.py` tách sẵn (theo dòng → `;` → ranh giới câu; đơn vị `[0]` là tiêu đề Điều để chủ ngữ kế thừa có chỗ neo), thay vì tự chép chuỗi. `char_span` do mình tính ⇒ **bịa provenance là bất khả thi**. `quote` chỉ còn là tuỳ chọn thu hẹp span *bên trong* đơn vị đã chọn. Trạng thái mới: `exact | unit | invalid`.
  - **Đóng lỗ hổng lớn nhất của giai đoạn 1**: `subject`/`action`/`constraint` không còn là chữ LLM viết mà là **lát cắt `dieu.text[start:end]`** — chữ của luật. Diễn giải của mô hình tách sang trường `label` riêng và bị kiểm. Trước đó `action` là text tự do và **không hề được kiểm**, nên chuỗi sai vẫn đi tiếp xuống downstream với đúng một dòng warning.
  - **`app/ontology/modality.py` — từ điển tình thái tiếng Việt đầu tiên của repo** (5 nhóm: nghĩa vụ / cấm / cho phép / điều kiện / định lượng) + 4 quy tắc chặn cứng: thêm nghĩa vụ-cấm đoán, bịa số, đảo cực tình thái theo vị trí, và **điều kiện → nghĩa vụ**. `explain()` diff mức từ in `'khi' → 'phải'` thay vì báo chung chung.
  - **`app/ontology/report.py`** — trang HTML tự chứa tô màu span theo vai, làm công cụ cho cả duyệt gold lẫn kiểm kết quả. **`eval/ontology/`**: `run_eval.py` (span exact + IoU≥0.8, condition-set F1, accuracy `subject_source`/`logic`, khớp phán định lỗi cứng), `make_gold_seed.py`, `make_reports.py`.
  - **Verify diện rộng**: 10 fixture / 4 văn bản (ND52, TT40, TT17, TT18) → 41 CU, 102 điều kiện, 184 trường được neo. **0 mất provenance**, 67.4% `exact`, 32.6% `unit`, **1/41 CU bị chặn** (TT17 Đ16 K2 điểm c — mô hình thêm "an toàn, bảo mật, sao lưu dự phòng", "phòng chống rửa tiền" không có trong đoạn được neo). Riêng ND52 Đ22 K2: giai đoạn 1 là 6/10 neo chính xác + 1 mất provenance, giai đoạn 2 là **21/22 + 0 mất**.
  - **Chạy thật rồi mới siết được luật**: bản đầu của modality guard báo nhầm 2 case, cả hai đều lộ ra khi chạy diện rộng chứ không thấy trên giấy — (1) TT40 Đ25 K5: luật cấm 2 vế, mô hình phân phối thành 3 vế "không được", phép đếm ra "thêm 2 lệnh cấm" dù nguồn đã cấm sẵn → sửa thành chỉ tính bịa khi nguồn KHÔNG có nhóm đó; (2) TT17 Đ16 K2 điểm d: luật "trong trường hợp", mô hình "khi" — cùng nhóm điều kiện, chỉ là từ đồng nghĩa → thêm vế "diễn giải không còn dấu hiệu điều kiện nào". Cả hai có test canh.
  - **Bằng chứng sống cho luận điểm trung thành ≠ đúng đắn**: ở ND52 Đ22 K1 mô hình neo `subject` vào *"Hoạt động cung ứng dịch vụ…"* trong khi chủ thể đúng là *"Dịch vụ trung gian thanh toán"* ở câu trước. Span hợp lệ, chữ có thật, nhưng **sai vai** — không tầng tất định nào bắt được, đúng chỗ cần bộ nhãn người gán.
  - **Bắt được 1 bug thật của chính mình**: `_load_dieu` dò số hiệu trong THÂN Điều, mà mọi Thông tư đều trích dẫn `52/2024/NĐ-CP` ⇒ **7/10 fixture bị gán sai khoá node KG, im lặng**. Sửa: chốt số hiệu lúc sinh fixture (đọc header văn bản gốc) vào `data/fixtures/_index.json`, cấm dò lại. `tests/test_ontology_fixtures.py` canh.
  - **Trang duyệt bộ nhãn `eval/ontology/review_ui.py`** — HTML tự chứa, cố ý KHÔNG nhét vào app Next.js (công cụ gán nhãn nội bộ, không phải tính năng người dùng). Duyệt bằng editor là bất khả thi vì span lưu dạng `[295, 391]`, muốn biết là chữ gì phải tự đếm ký tự. Trang này: toàn văn Điều tô màu theo vai, phần ngoài Khoản làm mờ, sửa span bằng bôi đen chữ hoặc bấm chip đơn vị, hiện đúng cảnh báo máy đã gắn, `localStorage` chống mất tiến độ, `--serve` cho nút Lưu ghi thẳng `gold.jsonl` (chỉ nghe 127.0.0.1). Cơ chế: cắt văn bản thành lát tại mọi biên, mỗi lát mang `data-s` = offset toàn cục ⇒ selection→offset chỉ là phép cộng. **Verify trong Chrome**: mọi lát khớp văn bản gốc, ghép lại bằng đúng `dieu.text`, bôi đen "Dịch vụ trung gian thanh toán" ra đúng `[76,105]`, bấm Lưu → file trên đĩa UTF-8 sạch → `run_eval` đọc được và chỉ số phản ứng đúng.
- **Done (tối — tiết `(i)/(ii)` và bóc viện dẫn):**
  - **Quyết định bằng số liệu: KHÔNG địa chỉ hoá tiết.** Nhiều Điểm còn chẻ tiếp thành `(i)`, `(ii)`. Đo trên corpus: viện dẫn tới Khoản 356 · tới Điểm 226 · **tới tiết 4** — và cả 4 nằm trong TT23-2019 (`valid_to=2024-07-17`, đã hết hiệu lực), **0 ở văn bản còn hiệu lực**; cả 4 lại là tự tham chiếu nội bộ (`"điểm b(i) khoản này"`) nên giải được ngay trong chunk. Chi phí nếu dựng: +270 nút (+12.2%). Cộng với `RAG-DESIGN` §2 đã chốt chunk mức Khoản (tiết luôn nằm sẵn trong chunk) và KG v0.5 §9 "Điểm dựng theo nhu cầu, không dựng đại trà" ⇒ không đáng.
  - **Và hình dạng tôi đề xuất ban đầu (`#diem_b#tiet_i`) là sai.** Chữ "tiết" xuất hiện **0 lần** trong 557k ký tự; văn bản thật viết `điểm a(ii)`, `điểm b(i)` — số La Mã **dính vào chữ cái điểm**. Người soạn luật coi nó là **hậu tố**, đúng cách KG v0.5 §5 xử lý `Điều 15a` bằng `so_hau_to`. Nếu có ngày làm thì là `so_hien_thi="b(i)"` trên chính node `Diem`.
  - **Nhưng quan hệ logic thì bắt buộc giữ**: TT17 Đ16 K1 điểm b là `"(i) …; hoặc (ii) …"` — phép TUYỂN bên trong một Điểm, bỏ đi thì "thoả (i) HOẶC (ii)" thành "thoả cả hai". Thêm `TietSpan` (không có `id`) + `ConditionItem.logic`/`sub`, suy ra **tất định** từ đuôi câu, không hỏi LLM: `"; hoặc"`→`any`, `"; và"`→`all`, `;` trần→**`unknown` + cảnh báo** (tiếng Việt pháp lý dùng `;` cho cả liệt kê lẫn lựa chọn, đoán bừa chính là kiểu đổi nghĩa pipeline này sinh ra để chặn).
  - **`app/ontology/citation.py` — parser viện dẫn đầu tiên của repo.** Trước đó văn phạm chỉ nằm trong spec `SCHEMA_KG` §2.b, chưa ai hiện thực (khảo sát xác nhận `retrieval.py`/`answer.py` không hề đọc nội dung câu hỏi; router viện dẫn vẫn là việc "Tuần 3"). Phủ 3 thứ spec bỏ sót: hậu tố La Mã, nhiều đích một câu, tự tham chiếu. **Không âm thầm**: `co_tiet` ghi lại "viện dẫn hẹp hơn node trả về"; `"khoản này"` thiếu ngữ cảnh thì trả **rỗng** chứ không tụt lên khoá rộng hơn.
  - **Phần đắt nhất là phân biệt viện dẫn với chữ thường**, đã đếm: `điểm`+chữ đơn lẻ 210 (ngây thơ 298 — dính *"điểm nhận được lệnh"*); `khoản`+số 401 (ngây thơ 1846 — dính *"tài khoản thanh toán"* 69 lần); `Điều` **viết hoa** 537 (loại 154 chữ *"điều kiện/điều chỉnh"*). Bẫy sập một lần khi làm: thiếu lookbehind thì chính chữ `"điểm"` và `"và"` bị tách thành điểm giả `đ,i,m,v` → `"điểm a, điểm b… và điểm đ"` ra 18 điểm thay vì 5.
  - **Sửa 1 bug thật đang chạy ở web**: `web/lib/anchors.ts` dùng `/Điều\s+(\d+[a-zA-Z]?)/` — `[a-zA-Z]` không khớp `đ`, nên `"Điều 15đ"` cắt thành `dieu-15`, **đụng slug với `Điều 15`**, deep-link nhảy sai điều mà không báo. Đúng bẫy 23 chữ mà phía Python đã chặn từ đầu; nay lớp ký tự dựng từ bảng `VI_LETTERS`.
- **Done (giai đoạn 3 — premise / meta-CU / references):**
  - **Đính chính quy công trong tài liệu gửi mentor.** `docs/ONTOLOGY-POC.md` ghi `char_span` là "ý tưởng chống hallucination của GraphCompliance" — **sai**. Tra lại bài báo: **không dùng chữ "hallucination"** ở đâu cả, `char_span` ở đó chỉ để **truy vết**, và họ **không** mô tả việc đối chiếu span lúc trích. Menu-span + đối chiếu span + modality guard là phần tự làm. Thêm bảng tách bạch "lấy từ bài báo" vs "tự làm" (§1.0). Bài báo cũng **không có** gold label cho CU và không có IAA — họ kiểm bằng cycle-consistency.
  - **Đối chiếu tuple ⟨S, Θ, Π, κ⟩**: có S, Θ; Π tách khác; **κ (context) không có**; **`references` không có** (citation.py build rồi mà extractor không import); **`type` actor_cu/meta_cu không có**; **premise hoàn toàn chưa có**. meta-CU hoá ra **không phải lớp bọc mức văn bản** mà là trường `type` trên chính node CU, đánh giá trước và không bao giờ báo vi phạm độc lập.
  - **`app/ontology/roles.py`** — phân vai premise/meta_cu/actor_cu. Ba tầng: regex tiêu đề (bắt 40/278 điều, **0 token**), đối chứng vị trí (Điều 1 phạm vi / Điều 2 đối tượng — tri thức miền của người dùng, đo được **9/11** và **8/11**), LLM cho phần dư. Bẫy đã sập: **"Trách nhiệm thi hành" là actor_cu**, không phải meta — khảo sát đầu tiên xếp nhầm vì khớp chữ "thi hành". Ngoại lệ vị trí đều là **văn bản sửa đổi** (TT20-2016, TT23-2019) ⇒ `is_van_ban_sua_doi()` tắt luật vị trí.
  - **Tầng premise → `KhaiNiem`**: Điều `premise` không sinh CU nữa mà ra thuật ngữ + định nghĩa (mức Khoản, khớp node `KhaiNiem` KG v0.5 đã thiết kế), dùng lại y nguyên `segment()`/`resolve()` nên không đẻ cơ chế neo mới.
  - **Nối `citation.py` vào extractor** — điểm g ND52 Đ22 K2 (*"…quy định tại điểm a, điểm b, điểm c, điểm d và điểm đ khoản 2 Điều này"*) trước nằm chết trong text, giờ thành 5 khoá node trong `references`.
  - **Tìm ra 1 lỗi im lặng khi test hỏng**: ND52 Điều 1 **không có khoản nào** (thân là đoạn liền) ⇒ `for k in dieu.khoan` chạy 0 lần ⇒ **cả điều bị bỏ qua không báo gì**. Đo lại: **25/267 điều (9.4%)** ở dạng này, gồm cả actor-CU (Điều 9, Điều 38 ND52). Sửa bằng `khoan_de_trich()` trả khoản ảo mang `id` của chính Điều, không bịa "khoản 1".
- **Ship:** chưa deploy — PoC chưa nối Neo4j/LanceDB, không đụng đường ingest. 85 pytest (giai đoạn 1) → 138 (gđ 2) → 167 (gđ 2b) → **191 pytest + ruff + eslint xanh**.
- **Decision:** **không bắt LLM tự khai offset** — LLM đếm ký tự không đáng tin, và khi sai thì không phân biệt được "bịa nội dung" với "đếm sai"; chuyển sang quote-rồi-tự-dò thì cả hai đều lộ. Ba cái bẫy chốt lại thành luật cho mọi parser sau này: (1) bảng 23 chữ tường minh — `[a-z]\)` **không** khớp `đ)` nên nuốt điểm đ im lặng, `ord()` cho `đ`=3 là sai; (2) chapeau không nằm trên dòng đánh số; (3) rác biên tập luatvietnam (`"Phân tích"` + khối chú giải) chèn giữa chapeau và điểm a) — khảo sát cả văn bản: 71 dòng, 66 vô hại, 5 mở khối chú giải thật.
- **Next:** hỏi mentor — `char_span` có đủ tư cách làm nguồn kiểm chứng độc lập để mở khoá 7 node chuẩn tắc ở §10.2, hay vẫn cần gold label người gán? Nếu được thì chạy diện rộng nhiều Điều/nhiều loại văn bản để có số liệu, và bổ sung nhánh `kemtheo_*`/`phuluc_*`.

## 2026-07-29 (T4)

**Giai đoạn:** thiết kế kiến trúc RAG v2 cho KB mới + trả nợ chất lượng review.

- **Done:**
  - **Chốt `docs/RAG-DESIGN.md`** (brainstorm + phản biện trên nền `docs/SCHEMA_KG.md` v0.4): Neo4j là nguồn chân lý — LanceDB là chỉ mục dẫn xuất (id row = id node KG); pipeline QA 5 bước (router viện dẫn → hybrid prefilter as-of → graph expansion cấp Điều → sufficiency check → provenance answer); pipeline review 2 chiều (trái luật + thiếu nghĩa vụ); "hợp đồng truy vấn" 5 truy vấn Cypher chốt tuần 2 của kế hoạch KB; danh mục không-làm (GraphRAG community, reranker...).
  - **Ship ngay 3 mục không phụ thuộc KB mới:** (1) verdict thứ 4 `not_assessed` — không tìm thấy căn cứ ≠ đạt, loại khỏi mẫu số điểm (trước đó tài liệu lạc đề được 100/100), UI hiện tile/tab "Chưa đối chiếu" + điểm "—" khi không đối chiếu được điều nào; (2) `search_in_docs` (đường retrieval của review) thành hybrid vector+BM25/RRF — bắt từ khoá chính xác kiểu "150 triệu"; (3) ổn định phán định: rubric có quy tắc ranh giới, temperature=0, self-consistency 2 lần (bất đồng → lần 3 lấy đa số), chạy song song 4 điều để giữ latency.
- **Ship:** commits `f7ac3a9` → `9203b99`; Cloud Run + Vercel production; 63 pytest + ruff + eslint + build xanh.
- **Decision:** "không biết" phải khác "đạt" trong điểm tuân thủ; không theo GraphRAG community-summary (corpus nhỏ, quan hệ tường minh → duyệt cạnh xác định); lọc hiệu lực phải chuyển thành prefilter LanceDB trước khi nạp KB có phiên bản.
- **Next:** theo lộ trình RAG-DESIGN §7 — tuần 2 KB: hợp đồng truy vấn + schema row LanceDB mới; sau đó router viện dẫn + graph expansion cấp Điều.

## 2026-07-28 (T3)

**Giai đoạn:** sau Sprint 2 — hoàn thiện UX + backend kiểm tra tuân thủ.

- **Done:**
  - **Backend kiểm tra tuân thủ `POST /reviews`** (nợ lớn nhất trong DESIGN-GAP): mỗi điều nội bộ → retrieval điều luật trong phạm vi chọn (lọc hiệu lực tại as-of) → Gemini phán định violation/warning/pass kèm trích dẫn hai phía → findings + điểm tuân thủ. 7 test offline. Màn `/review` bỏ dữ liệu minh họa, chọn tài liệu nội bộ thật (4 văn bản SHB), gọi API thật, deep-link căn cứ sang trình xem. **Verify prod:** SHB-QD-VI-2023 ↔ TT40-2024 → bắt đúng 2 mâu thuẫn cài chủ đích (hạn mức 150tr vs Điều 26; nộp tiền mặt vs Điều 25), điểm 33/100.
  - Hạ tầng vận hành: workflow **Supabase keep-alive** (ping mỗi 2 ngày, tự cảnh báo khi project bị pause — đã verify run xanh); nhật ký `docs/WORKLOG.md` + lệnh `/worklog`; quy ước commit tiếng Anh + CLAUDE.md.
  - **Lưu trữ phiên (migration 0005)**: bảng `review_sessions` (sidebar Kiểm tra hiện lịch sử, mở lại qua `?session=`) + cột `scope`/`as_of` trong `chat_messages` (mở lại phiên chat khôi phục đúng chip Phạm vi và mốc "tra tại" theo lượt). Migration đã chạy, **verify prod end-to-end**: `/reviews` trả `session_id` khớp row trong `review_sessions`; `/chat` có phạm vi + as-of được lưu đúng vào `chat_messages`.
  - Tích hợp mascot **Lexi** (con cú, 8 trạng thái) từ design handoff v2: avatar động theo vòng đời câu hỏi ở màn Tra cứu (searching → found/conflict), pha "đang đối chiếu" ở màn Kiểm tra (reading), chào ở Landing (greeting), trang lỗi/404 (error), favicon mới.
  - Review handoff phát hiện lỗi (SVG thiếu keyframes) → designer sửa theo kiến trúc "hoạt ảnh trong CSS, SVG tĩnh"; ô lỗi chat có thêm nút **Thử lại**.
  - Chốt **quy ước commit** (`docs/COMMIT-CONVENTION.md`): Conventional Commits, message tiếng Anh; tạo `CLAUDE.md` gốc repo.
- **Ship:** commits `3e73992` → `9480eb3` — Cloud Run rev 00014 + Vercel production, CI xanh.
- **Decision:** không dùng Lexi làm logo sidebar (linh vật ≠ logo, theo designer); greeting đặt ở Landing vì "chỉ chào một lần"; điểm tuân thủ = trung bình (pass=1, warning=0.5, violation=0) theo điều.
- **Next:** thêm `issuer/issued_date/field` vào schema (gộp vào đợt KB mới); follow-up chips; các mục nhỏ còn lại trong DESIGN-GAP theo nhu cầu demo.

## 2026-07-27 (T2)

**Giai đoạn:** kế hoạch mới sau Sprint 2 (3 tính năng chờ KB + redesign).

- **Done:**
  - **Sáng:** schema quan hệ mức Điều (`RelAnchor`), API đọc văn bản (GET /documents, /documents/{id} + cache TTL 60s), trang Thư viện `/docs`, **trình xem toàn văn** `/docs/[docId]` (tab Nội dung + Lược đồ kiểu thuvienphapluat, highlight điều bị sửa đổi/thay thế, banner hết hiệu lực), seed anchors thật (TT23-2019/TT20-2016 → TT39-2014), citation chat deep-link `#dieu-N`, Neo4j lưu anchors trên cạnh.
  - **Chiều:** redesign toàn bộ UI theo design handoff (style giấy ấm + clay + serif Newsreader): 5 màn — Tra cứu (trust bar, mâu thuẫn accordion, trích dẫn superscript, **bộ chọn phạm vi** + as-of), Thư viện 3 cột, Kiểm tra tuân thủ (UI, kết quả minh họa), Auth 2 cột, Landing. Backend thêm `ChatRequest.doc_ids` → retrieval giới hạn trong văn bản chọn (verify trên prod).
  - Viết `docs/DESIGN-GAP.md` — đối chiếu design ↔ hệ thống, xếp ưu tiên việc còn thiếu.
- **Ship:** commits `ba0c5dc` → `0a87627`; Cloud Run rev 00012; Vercel aliased; 50 pytest + lint/build xanh.
- **Decision:** mở rộng app hiện có (không làm FE mới từ đầu); lược đồ theo từng văn bản; "Điều" là đơn vị neo quan hệ (khớp nghiên cứu cấu trúc luật VN của mình).
- **Next:** backend /reviews; migration lưu scope+as_of theo lượt chat; thêm issuer/field vào schema khi làm KB mới.

## 2026-07-24 (T6)

**Giai đoạn:** Sprint 1 + 1.5 + 2 (kế hoạch 4 tuần — làm xong trong 1 ngày).

- **Done:**
  - **Sprint 1 — corpus thật & benchmark:** 15 văn bản / 449 chunk (11 văn bản luật thanh toán–ví điện tử + 4 quy định nội bộ SHB mô phỏng có cài mâu thuẫn chủ đích); extractor tách Điều bằng regex + Gemini metadata; chunking mức Khoản; **benchmark 36 case: stale-avoidance 36/36** (baseline 21/36), phát hiện mâu thuẫn 7/7.
  - **Sprint 1.5 — web production:** deploy Vercel https://lexflow-taupe.vercel.app, CORS đa origin.
  - **Sprint 2 — luồng nghiệp vụ:** upload → duyệt (maker-checker) → re-ingest tự động; trang /admin; graph-augmented retrieval (Neo4j 1-hop vào prompt); lịch sử chat; roadmap hạ tầng 1–9 hoàn tất (auth Supabase JWT, SSE streaming, Langfuse observability, bảng change_events + trang /alerts).
- **Ship:** Cloud Run rev 00004 → 00010; migrations 0001–0004.
- **Decision:** corpus canonical đặt trên Supabase Storage (đè file commit, fail-open khi lỗi); không dùng service-role key — mọi ghi DB qua JWT người dùng.
- **Next:** giai đoạn tính năng chờ KB mới.

## 2026-07-23 (T5)

**Giai đoạn:** dựng hạ tầng production.

- **Done:** chốt kiến trúc (Cloud Run + Supabase + LanceDB Cloud + Neo4j Aura + Gemini — chi tiết `docs/ARCHITECTURE.md`); tạo GCP project `lexflow-shb-2026`; deploy FastAPI đầu tiên lên Cloud Run (asia-southeast1); pipeline ingest chạy với corpus mẫu.
- **Decision:** loại Railway (hết trial), loại Qdrant (corpus nhỏ, LanceDB đủ); máy local yếu → mọi build/deploy đều trên cloud.

---

## Template mục mới (copy khi ghi tay)

```markdown
## YYYY-MM-DD (Thứ)

**Giai đoạn:** ...

- **Done:** ...
- **Ship:** commit ..., deploy ...
- **Decision:** ...
- **Next:** ...
```
