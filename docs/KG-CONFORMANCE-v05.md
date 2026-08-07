# Đối chiếu code hiện tại với Schema KG v0.5

**Câu hỏi:** schema văn bản pháp luật đang có trong repo đã thoả `research/schema-kg-v05.html` chưa?

**Trả lời: chưa — nhưng "chưa" đó không đồng đều.** Phần v0.5 đặc tả kỹ nhất (§4 khoá nhánh,
§5 đánh số) thì code **đã thoả và có test canh**. Phần từ cấp Điều trở lên (VanBan, 13 quan hệ,
tầng thời gian, độ tin cậy) **phần lớn chưa tồn tại dưới dạng code**.

Ngày đối chiếu: 2026-08-03, đo lại 2026-08-04, **nạp corpus 2026-08-05** · v0.5 bản 29/07/2026 ·
mọi số trong tài liệu này kiểm lại được bằng §6.

> **05/08 — #14 đã xong: corpus 15 → 20 văn bản (278 → 338 điều), và lần đầu điểm nhích.**
> Nạp 8 văn bản crawl (5 mới + 3 thay: ND52/TT15/TT40; `29/VBHN-NHNN` giữ làm node rỗng vì vbpl
> không đăng toàn văn). Hệ quả đo được: `chapter` **115/338** điều (hết 0/278) · §6 lên **5/13**…
>
> **…và ĐỢT 2 cùng ngày, sau lượt crawl 22 văn bản của bên crawl:** corpus lên **26 văn bản ·
> 425 điều · 1 289 khoản · 1 053 điểm · `chapter` 180/425 · 35 quan hệ**. `BAI_BO` thành **4**
> (thêm ND58 —Đ28→ bãi bỏ Đ4 NĐ16; TT15 —Đ22→ bãi bỏ Đ3 TT30/2016 — ca đầu tiên **cả hai đầu
> đều có toàn văn**). 12 cạnh đợt 2 đều có căn cứ trích từ lời văn hoặc lược đồ; danh sách
> crawl tự lớn 67→89 vì 13 lược đồ mới trỏ tiếp ra ngoài — đúng thiết kế của `can_crawl`.
> Khối cũ bên dưới giữ số **đợt 1**: **5/13
> mã có instance** trong chính corpus (23 cạnh, **hai** cạnh `BAI_BO` kèm neo: NĐ52 —Điều 37→
> bãi bỏ Điều 3 NĐ16/2019; TT22 —Điều 6 k2→ bãi bỏ Điều 16/17/18 TT41/2025) · ca kiểm chứng §6.2 hết bị chặn bởi "0 `BAI_BO`". Ba phát hiện dọc đường,
> mỗi cái một bài: (1) `_KHOAN_RE` đòi dấu cách sau `1.` còn vbpl in `1.Việc` dính liền — **bảng
> nghiệm thu cũ đo bằng thước hỏng** (TT15 97→98 khoản, TT40 216→221 điểm, khớp corpus cũ từng
> khoản); (2) thuộc tính vbpl sai được: ND52 ghi hiệu lực `01/07/2027` trong khi Điều 37 của
> chính nó ghi `01/07/2024` ⇒ quy tắc *chữ trong luật thắng metadata* (`nap_corpus.py`);
> (3) đuôi `Nơi nhận:`/chữ ký/phụ lục vbpl dán vào điều cuối (TT40: 6 965 ký tự biểu mẫu) — cắt
> có vết, phụ lục chờ nhánh `#phuluc_`.

> **Đo lại 04/08 — điểm các khối KHÔNG đổi một ô nào**, qua **sáu đợt việc** trong ngày. Ba đợt
> đầu ở tầng CU (`source_diem` suy từ parser · luật chapeau · bảng phân hoạch) không chạm tầng
> văn bản. Ba đợt sau **có** chạm (cầu `so_hieu` · node rỗng · nhận dữ liệu crawl lại · khối
> trích dẫn) nhưng vẫn không nâng ô nào, vì chúng **mở đường** chứ chưa **nạp dữ liệu**: §3
> `Chuong`/`Muc` nay có 115/174 điều đã crawl nhưng corpus vẫn 0/278; §6 có đủ 13 mã trong
> schema nhưng corpus vẫn 4/13 instance.
>
> Cái đã đổi: **§4 từ 4 → 9 mục**, **§3.5–§3.8 là bốn mục mới**, và hai lỗi §3.1/§3.2 được **đo
> lại trực tiếp** — cả hai còn sống, xem §5. Ghi vậy thay vì làm tròn lên, vì một báo cáo đối
> chiếu mà tự cải thiện điểm sau mỗi lần chạm code thì hết là thước đo.
>
> Đường găng nay là **một việc dữ liệu, không phải việc code**: nạp 7 văn bản đã crawl (#14).
> *(05/08: #14 xong — xem khối đầu tài liệu; đường găng chuyển sang #16 crawl và #17 Neo4j.)*

> **Overlay dưới-văn-bản (05/08, P1–P3).** 178 cạnh tác động (`eval/overlay/canh_tac_dong.jsonl`),
> đối chứng hai chiều với `dieu_khoan_bi_tac_dong`: TT40 **90.4%** (75/83) · TT15 **92.5%**
> (37/40) · TT34 **92.1%** (35/38) — cả ba qua ngưỡng ≥90%. 167 khoá đích xuất hiện trong 178
> cạnh: **126 da_sua · 36 bi_bai_bo · 5 nguyên_ven** (đo tại 2026-08-05, sau luật cạnh-chết).
> Bộ câu hỏi gắn nhãn tay (`eval/overlay/cau_hoi_nhan.jsonl`, 12 dòng, cả 3 nhánh) khớp
> `dinh_tuyen` **13/13** (12 khi nghiệm thu Task 8; +1 hàng khoản-gộp sau đợt sửa của final review — vá luôn khoá giả `#khoan_1-3` từng làm 14 chunk trả `nguyen_ven` sai). Cạnh sửa đổi giờ nối con↔con (khoản/điểm chạm khoản/điểm), cạnh văn
> bản (Điều X sửa đổi Điều Y) chỉ còn làm tầng hiệu lực, không phải nơi tra lời văn mới.

> **P4 (06/08) — lớp phủ đã CHẠM SẢN PHẨM, không còn là artefact offline.** 10 task
> subagent-driven TDD, 17 commit `e21c50f..a78a62e`, 588 test xanh.
>
> **Đường đi:** artefact **tự chứa** `data/overlay/lop_phu.json` (178 cạnh, span `loi_van_moi`
> giải thành chữ **lúc build** — `data/raw/vbpl/` gitignored nên runtime không bao giờ giải được)
> → cổng runtime **duy nhất** `app/knowledge/lop_phu.py` bọc `dinh_tuyen`/`phien_ban_hien_hanh`,
> fail-open → `answer.py` (nhãn hiệu lực cấp khoản vào prompt + `Citation`) · `review.py` (không
> phán tuân thủ trên luật đã chết) · `GET /documents/{id}.tac_dong` · badge ở 3 màn web.
>
> **Số đo trên hệ thống chạy thật:** LanceDB Cloud **449 → 661 chunk**, 15 → **26 văn bản**;
> Neo4j **293 `DonVi`** · **178 `TAC_DONG`** · **255/293 `THUOC`** (38 đầu mút chưa có node
> `Document` — đúng dải node rỗng §3.7, và `push_overlay` **in ra** khoảng chênh thay vì để
> `MATCH` trượt trong im lặng); Cloud Run rev `00016-n6k`, Vercel production.
>
> **Verify e2e qua `_prepare` thật** (không phải mock): `TT41-2025::Điều 10` → `la_loi_sua` →
> trích dẫn nắn về **đúng chủ** *"TT40-2024 Điều 26 Khoản 1 (sửa bởi TT41-2025 Điều 10 Khoản 1)"*;
> `TT41-2025::Điều 16` → `bi_bai_bo` (cạnh TT22 Điều 6 Khoản 2) — **ca cạnh-chết chạy thật trên
> production**; `TT40-2024::Điều 26/37/25` → `da_sua` kèm nguồn sửa.
>
> **Benchmark 36 câu (`eval/results/20260806-072821.json`, 0 câu lỗi) — và đây là chỗ phải đọc
> kỹ:** citation 36/36 cả ba cột; stale-avoidance baseline 21/36 → LexFlow **36/36**; mâu thuẫn
> 6/7. Nhưng **router OFF vs ON: 0/36 câu khác nhau**, 0 hit bị loại vì bãi bỏ, **8** hit được
> nắn trích dẫn. Dự đoán ghi TRƯỚC khi chạy là 0–3 và 10–25 ⇒ **sai ở vế nắn trích dẫn**.
> Kết luận thẳng: **bộ 36 câu này không đo được lớp phủ** — nó chấm ở mức `doc_id`, lớp phủ làm
> việc ở mức khoản; "0/36" là giới hạn của **thước đo**, không phải bằng chứng lớp phủ vô dụng
> (giá trị của nó nằm ở verify e2e trên và ở bộ nhãn cấp khoản 13/13). Muốn có số trình hội đồng
> thì cần **bộ câu hỏi chấm ở mức điều/khoản** — việc riêng, chưa làm. Không được trích bảng
> "0/36" mà bỏ đoạn giải thích này.
>
> **Hai sự cố hạ tầng đáng ghi, vì cả hai đều là hỏng-trong-im-lặng.** (1) `Dockerfile` không
> copy `data/overlay/` ⇒ image thiếu artefact ⇒ `tai_lop_phu()` trả `None` ⇒ **lớp phủ tắt hoàn
> toàn mà fail-open nuốt luôn dấu vết** (vá `35031dd`) — đúng cái giá của fail-open: nó đổi lỗi
> ồn ào lấy lỗi câm. (2) `.gcloudignore` bỏ sót `data/tuvanphapluat/` (516 MB) ⇒ upload không bao
> giờ tới bước build, mà `gcloud … | grep | tail` trả exit **0** (mã thoát của `tail`) ⇒ hai lần
> "deploy thành công" giả, revision cũ vẫn `ACTIVE`, `/health` vẫn `ok`. ⇒ **Tiêu chí nghiệm thu
> deploy từ nay = OpenAPI của bản ĐANG PHỤC VỤ có trường mới**, không phải exit code.

> **Final review toàn nhánh (06/08, model mạnh nhất) — 1 Critical + 6 Important, đo TRÊN ARTEFACT
> ĐÃ SHIP chứ không đọc code rồi suy.** Mười vòng review cấp task đều bỏ lọt. Ba cái nặng nhất:
>
> 1. **Critical — nhánh 3 lấy cạnh khớp ĐẦU TIÊN rồi tuyên bố như sự thật.** 46 cặp cạnh chung
>    span, 17 nhóm (văn bản, lời văn) trùng khít. `ND80` span `[1071,2386]` là đích của `ND101`
>    Điều 4 **khoản 4, 5, 6, 7, 8** — năm cạnh một span, chỉ khoản 4 được nêu. Một span của `ND16`
>    còn trỏ sang **hai văn bản nền khác nhau**. Vi phạm thẳng "không bịa".
> 2. **Important — fallback kéo lời văn hiện hành hỏi id CẤP ĐIỀU** (`f"{doc}::{article}"`) trong
>    khi `pipeline.py` mint nhãn `"Điều N Khoản a-b"` cho điều >2000 ký tự ⇒ **31/40 ca trả `[]`**,
>    fail-open che mất. **Đây là lỗi trong PLAN**, và mọi test đều mock đúng hàm bị hỏng nên nó
>    sống sót qua mười cổng review.
> 3. **Important — chunk kéo thêm không qua chú thích / lọc hiệu lực / phạm vi người dùng** ⇒ hiện
>    lên như `Citation` không nhãn, và ở `/reviews` có thể thành `legal_doc_id` ngoài `against_ids`.
>
> Sửa trong 7 commit `ec41c13..87b2e1d`; **620 test** xanh, classify 94 (45/9/40) giữ. Đợt sửa tự
> gây một hồi quy (gộp điểm dưới khoản làm mất cạnh trỏ *cả khoản* — in "Khoản 2 Điểm b, đ" trong
> khi thật ra sửa cả Khoản 2, bắn ở 2/15 nhóm span thật), bắt được ở vòng re-review và sửa thêm
> một vòng. Luật chốt cho `_cite_nhieu`: **không chắc thì NỚI RỘNG, đừng THU HẸP** — nói rộng hơn
> là phiền, nói hẹp hơn là claim sai phạm vi sửa đổi. Đo lại sau khi sửa:
> `ND101-2012 Điều 4 Khoản 4, 5, 6, 7, 8` và `TT15-2024 Điều 7 Khoản 2`. Deploy rev `00017-cqc`.
>
> **Bài học về quy trình, không phải về code:** plan nhúng sẵn cả code lẫn test, nên test chỉ lặp
> lại giả định của người viết plan thay vì dò chúng. Đợt sau nên giữ **hợp đồng giao diện** trong
> plan và để implementer tự viết test đối chiếu với index thật.

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
  > **Cập nhật 04/08 — nút thắt đã dịch chỗ.** Bên crawl nay trả `chapter`/`section` sẵn, và
  > `vbpl_corpus.doc_file` nhận được: **115/174 điều** trong 8 văn bản đã crawl có `chapter`
  > (đầy đủ ở mọi văn bản *có* Chương — ND52 38/38, TT40 54/54, TT15 23/23; các văn bản còn 0
  > đều là văn bản sửa đổi ngắn, bản thân chúng không có Chương nào). Corpus vẫn **0/278** vì
  > 7 văn bản này **chưa được nạp**. Tức từ *"code không đọc được"* thành *"chưa nạp"* — vẫn
  > 0 điểm cho §3, nhưng việc còn lại là nạp dữ liệu, không phải viết code.
  >
  > **05/08 — nạp xong: 115/338 điều trong corpus có `chapter`.** Trường hết chết. 223 điều
  > còn lại thuộc 12 văn bản chưa crawl lại (corpus cũ không giữ Chương) — theo #16.
- `Gate.pham_vi` nhận `"chuong"` / `"muc"` (`schema.py:159`) — nhưng **luôn kèm
  `suy_ra_duoc=False`**, vì parser không có node tương ứng để quy về. Đây là cách xử lý
  **trung thực** (nói thẳng "có phạm vi nhưng chưa quy được về khoá node"), không phải một
  cài đặt dở. Ghi ở đây như điểm cộng, để không ai đi "sửa" nó thành `True`.

Giới hạn có chủ đích của §3 (gạch đầu dòng không đánh số nằm lại trong nội dung của `Diem`):
✅ thoả **theo cấu trúc** — parser không tạo node nào dưới cấp Điểm.

### 2.4 · §6 · 13 quan hệ giữa văn bản — **13/13 schema · ~~4/13~~ 5/13 instance (05/08)**

> **05/08:** nạp #14 đưa corpus lên **23 cạnh · 5/13 mã** — thêm `BAI_BO` ×2 (NĐ52 → NĐ16/2019
> neo `Điều 37 → Điều 3`; TT22 → TT41/2025 neo `Điều 6 → Điều 16/17/18` — cạnh này vào sau khi
> người dùng chỉ ra câu bãi bỏ mà grep chữ thường bỏ sót) và nâng `CAN_CU` 4→7,
> `SUA_DOI_BO_SUNG` 2→6, `THAY_THE` 4→5. `kiem_quan_he`: **0 cạnh sai**. Khối bên dưới giữ
> nguyên các mốc 03–04/08.

> **Ba mốc trong một ngày, giữ lại cả ba vì chúng nói ba chuyện khác nhau.**
> Bản 03/08 ghi **4/13**, đếm số `rel_type` có trong dữ liệu. Sửa xuống **2/13** sáng 04/08 sau
> khi đối chiếu **từng tên** (§3.5b): chỉ `THAY_THE` và `DAN_CHIEU` trùng tên v0.5 — đếm một
> cạnh sai tên là đạt thì lần cutover sẽ vỡ im lặng. Rồi sửa cả hai đầu trong ngày: **schema**
> lên đủ **13/13** (tập đóng có validator + cạnh có kiểu trong Neo4j), **dữ liệu** về đúng tên
> v0.5 nên trở lại **4/13 instance** — lần này là 4 cái đúng. Hợp nhất thêm lược đồ vbpl thì
> **7/13** (thêm `BAI_BO` · `QUY_DINH_CHI_TIET_HUONG_DAN` · `HOP_NHAT`), nhưng những cạnh đó
> chạm đầu mút chưa có toàn văn ⇒ xem §3.7.
>
> Bảng dưới giữ nguyên **hiện trạng lúc phát hiện**, không viết lại — nó là bằng chứng cho §3.5b.

| | |
|---|---|
| **có** (4, *tên cũ — đã sửa*) | `THAY_THE` · `SUA_DOI` · `HUONG_DAN` · `DAN_CHIEU` — `core/schemas.py:7`; 13 instance trong `data/corpus.real.json` |
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

> **Một nửa của §8 nay rẻ hơn hẳn — đo 04/08.** Bản ghi crawl mang sẵn `source_url` (trang
> vbpl.vn) và `source_files` (link `.docx`/`.pdf` **bản gốc** trên `moj.gov.vn`, có cả với
> ND80/2016). Đây đúng là *xuất xứ cấp văn bản* mà §8 đòi. Nhưng `DocumentMeta` **không có
> trường nào để nhận**, nên `vbpl_corpus.doc_file` đọc xong rồi **bỏ đi** — cùng kiểu lãng phí
> mà `so_hieu` đã mắc một lần (§3.5d).
>
> Thêm hai trường là việc nhỏ. Nó **chưa** cho `da_xac_minh_nguon` (3 mức) — biết link bản gốc
> khác với đã đọc bản Công báo có chữ ký — nhưng nó cho **cái tiền đề**: muốn xác minh thì
> trước hết phải biết đường tới bản gốc, và hiện ta biết rồi mà không lưu.

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

**(b) Tên quan hệ LỆCH, không chỉ thiếu — và một loại là do tự đặt.** ✅ **ĐÃ SỬA 04/08.**

| trong dữ liệu (cũ) | số | v0.5 gọi là | xử lý |
|---|---|---|---|
| `THAY_THE` | 4 | `THAY_THE` ✅ | giữ |
| `DAN_CHIEU` | 3 | `DAN_CHIEU` ✅ | giữ |
| `SUA_DOI` | 2 | `SUA_DOI_BO_SUNG` | đổi tên cơ học |
| `HUONG_DAN` | 4 | **không tồn tại** | → **`CAN_CU`** |

Gốc rễ: `REL_TYPES` cũ là **bốn tên tự đặt** (`app/core/schemas.py`), và `rel_type: str` **chưa
bao giờ được đối chiếu với nó** — nên một loại không có thật sống được 4 lần. Cùng bảng đó còn bị
**chép ở ba nơi** (`schemas.py`, `answer.py`, `pipeline.py`) nên sửa một chỗ không kéo theo hai
chỗ kia.

Bốn cạnh `HUONG_DAN` (TT40 · TT15 · TT17 · TT18 → ND52) ban đầu tưởng cần phán định giữa
`QUY_DINH_CHI_TIET_HUONG_DAN` và `HUONG_DAN_AP_DUNG` (§6.3 — hai thứ Điều 53 k2 đối xử khác nhau).
**Nguồn chính thống trả lời thay:** trong lược đồ vbpl.vn của NĐ 52/2024, cả bốn nằm ở
`incoming / "Văn bản áp dụng"` — **nhãn bị động của `CAN_CU`**, cặp **#8 bất quy tắc** — chứ không
nằm ở `"Văn bản quy định chi tiết, hướng dẫn thi hành"` (nhóm đó chỉ có TT 34/2024). Tức các Thông
tư **ban hành căn cứ** NĐ 52, không phải hướng dẫn nó.

⇒ §6 lên **4/13 mã có instance** (`THAY_THE` 4 · `CAN_CU` 4 · `DAN_CHIEU` 3 · `SUA_DOI_BO_SUNG` 2),
tất cả đều là tên v0.5. Soát lại bằng `uv run python -m app.ingestion.kiem_quan_he`.

**(b2) Nguồn vbpl.vn đã mô hình hoá sẵn đúng thứ §6 đặc tả.** `luoc_do.outgoing`/`incoming`, mỗi
nhóm mang một nhãn trùng cột "chủ động/bị động" của bảng 13 quan hệ. **Chiều mũi tên do
`outgoing`/`incoming` quyết định, không do nhãn** — quy tắc đồng nhất cho cả 13 mã:

```
outgoing  ⇒  văn bản đang xem là ĐẦU NGUỒN   (current → listed)
incoming  ⇒  văn bản đang xem là ĐẦU ĐÍCH    (listed → current)
```

Bằng chứng nó đúng kể cả với cặp bất quy tắc: cùng mã `CAN_CU` ra **hai chiều ngược nhau** trên
cùng một trang — `outgoing "Căn cứ ban hành"` (ND52 → 10 Luật) và `incoming "Văn bản áp dụng"`
(20 Thông tư → ND52). Đọc `data/raw/vbpl/sample.json` bằng `app/ingestion/vbpl_luoc_do.py` ra
**35 cạnh · 0 cảnh báo**: `CAN_CU` 30 · `THAY_THE` 2 · `BAI_BO` 1 · `QUY_DINH_CHI_TIET_HUONG_DAN` 1
· `DAN_CHIEU` 1.

**(c) `BAI_BO` = 0 instance ⇒ ca kiểm chứng bắt buộc của §6.2 sẽ chạy nhưng trả RỖNG.**

v0.5 §6.2 đặt truy vấn *legislative void* (`BAI_BO` mà không có `THAY_THE`) làm **ca kiểm chứng bắt
buộc**, kèm tiền lệ học thuật Colombo et al. Dựng đủ 13 cạnh có tên sẽ làm truy vấn **chạy được**,
nhưng kết quả rỗng vì corpus không có quan hệ bãi bỏ nào. Ghi rõ để không ai nhầm "dựng xong 13
cạnh" với "có demo": muốn demo phải **tìm một quan hệ bãi bỏ có thật** trong corpus mở rộng.

> **✅ 05/08 — tìm được, và nó nằm ngay trong lời văn NĐ52 Điều 37:** *"bãi bỏ Điều 3 của Nghị
> định số 16/2019/NĐ-CP"*. Nạp ND16 (#14) xong, corpus có cạnh `BAI_BO` đầu tiên kèm neo
> `Điều 37 → Điều 3` — bãi bỏ **một phần**, khớp tình trạng vbpl "Hết hiệu lực một phần".
> Cùng ngày thêm cạnh thứ hai: TT22/2026 Điều 6 khoản 2 bãi bỏ Điều 16/17/18 của TT41/2025 —
> câu này grep `bãi bỏ` chữ thường KHÔNG thấy vì nó mở câu bằng "Bãi bỏ" viết hoa (người dùng
> chỉ ra); tìm mệnh đề trong văn bản pháp lý phải IGNORECASE.
> §6.2 hết bị chặn bởi dữ liệu; còn chờ #17 (Neo4j) để chạy trên đồ thị thật.

**(d) `so_hieu` đã trích được rồi bị vứt — cầu nối hai không gian ID rẻ hơn §3.3 tưởng.**

`_SO_HIEU_RE` (`extract.py:98`) kiểm lại **chạy đúng** trên cả ba dạng thử
(`52/2024/NĐ-CP` · `40/2024/TT-NHNN` · lẫn trong câu). Giá trị được `_head_text` đọc rồi **chỉ đưa
vào prompt làm ngữ cảnh**, `extract_metadata` không trả về. Thêm `so_hieu` như một **trường** trên
`DocumentMeta` (giữ nguyên `doc_id`) là việc một buổi, và nó cho A ↔ B **join được ngay** mà
**không chạm lịch sử Supabase** — khác hẳn phương án đổi `doc_id` ở §3.3.

> Mức: **trung bình** · Không thay §3.3, nhưng hạ cấp nó từ "chặn đường" xuống "dọn sau".
>
> **✅ Đã làm 04/08.** `DocumentMeta.so_hieu` + `app/ingestion/bac_cau.py`. Bổ chính một chi
> tiết ở đoạn trên: `_SO_HIEU_RE` **không** "chạy đúng trên cả ba dạng thử" — ba dạng ấy chọn
> chưa đủ khó. Khuôn `[A-ZĐ]+(?:-[A-ZĐ]+)+` gặp `С` Cyrillic thì lùi lại khớp ngắn hơn, **im
> lặng cắt cụt** `51/2025/TT-BTС` → `51/2025/TT`; và nó đòi có năm nên bỏ sót trọn nhóm hành
> chính (`123/QĐ-NHNN`). Nay dùng `app.core.so_hieu.phan_tich`, và một **khoá cụt tệ hơn không
> có khoá** vì nó vẫn join được — vào nhầm văn bản.

### 3.6 · Soát tồn đọng schema cũ (04/08) — ba chỗ, mức nghiêm trọng rất khác nhau

Câu hỏi: bốn tên tự đặt (`THAY_THE`/`SUA_DOI`/`HUONG_DAN`/`DAN_CHIEU`) còn sống ở đâu trong một
hệ thống **đang chạy**, chứ không chỉ trong code?

**(a) Neo4j — không tồn đọng được, nhưng vì một lý do đáng lo hơn.** Instance Aura
`fd63789d.databases.neo4j.io` **không phân giải DNS nữa** (`databases.neo4j.io` và `google.com`
đều phân giải bình thường ⇒ không phải lỗi mạng). Tức đồ thị hiện **không có dữ liệu để tồn
đọng** — và cũng không có dữ liệu để chạy. Ngoài ra `push_corpus` mở đầu bằng
`MATCH (d:Document) DETACH DELETE d`, nên kể cả còn sống thì lần nạp sau cũng xoá sạch.

> **05/08 — chẩn đoán trên sai một nửa, đo lại được sau khi người dùng resume.** Instance không
> chết: Aura free **tự pause** sau thời gian không hoạt động, và pause thì DNS của instance
> ngừng phân giải — nhìn từ ngoài giống hệt "chết". Resume xong kết nối được ngay, và bên trong
> là **đúng cái tồn đọng mà (a) kết luận là không có**: 15 node `Document` · 13 cạnh mang **tên
> cũ** (`HUONG_DAN` 4 · `SUA_DOI` 2 · `THAY_THE` 4 · `DAN_CHIEU` 3) · **0 node có `so_hieu`** ·
> thiếu cả 5 văn bản nạp 05/08. Không cần dọn tay: `push_corpus` xoá sạch rồi nạp lại — chạy
> khi người dùng cho phép đụng dữ liệu chạy thật (#17).

**(b) Web — còn sống ở BA file, và hỏng theo kiểu không ai thấy.** ✅ đã sửa.

| chỗ | hỏng ra sao |
|---|---|
| `web/lib/anchors.ts:73` | lọc `rel_type !== "SUA_DOI"` ⇒ sau khi đổi tên, **bản đồ sửa đổi theo điều rỗng đi**, đúng 2 cạnh `SUA_DOI_BO_SUNG` của corpus bị bỏ qua |
| `web/lib/anchors.ts:22` · `graph/page.tsx:19` · `alerts/page.tsx:17` | bảng nhãn 4 dòng ⇒ 11 mã còn lại rơi xuống nhánh dự phòng, người dùng đọc thấy chữ `SUA_DOI_BO_SUNG` thay cho "Văn bản sửa đổi, bổ sung" — **không lỗi nào trong console** |

Gom về `web/lib/quan-he.ts` (một bảng), và `tests/test_quan_he_web.py` đọc thẳng file `.ts` để
canh 13 mã + 26 nhãn khớp `REL_TYPES` — kể cả cặp bất quy tắc #8 (`căn cứ ban hành` ⟷ `áp dụng`),
chỗ dễ tự suy ra sai nhất.

**(c) Supabase — chỗ DUY NHẤT schema cũ còn sống trong dữ liệu thật.** Migration `0003` **seed
thẳng** hai dòng `HUONG_DAN` và `SUA_DOI` vào `change_events`, và nó đã chạy. Nặng hơn tên xấu:
khoá chống trùng là `unique (doc_id, source_doc_id, rel_type)` — **có `rel_type` trong khoá** —
nên lần ingest sau, cùng một thay đổi mang tên mới bị coi là **sự kiện khác** và chèn thêm dòng.
Người dùng thấy một thay đổi hiện hai lần với hai động từ, không gì nói đó là một.
⇒ `supabase/migrations/0006_quan_he_v05.sql` (đổi tên + `check` chặn ở biên). **Chưa chạy** —
cần bạn dán vào SQL Editor.

### 3.7 · Node rỗng: ~~32~~ 27 đầu mút chưa có toàn văn (05/08)

**57 cạnh** (13 corpus + 44 từ hai bản ghi vbpl) quy hết về `doc_id`, **0 cạnh rơi, 0 cảnh báo**:
21 nối hai văn bản có toàn văn, 36 chạm ít nhất một đầu mút chưa có. Ba lối cho 32 đầu mút ấy:
bỏ cạnh · để tồn đọng · dựng **node rỗng**. Chọn lối thứ ba — bỏ đi thì mất luôn instance
`BAI_BO` duy nhất có thật (NĐ52 → NĐ16/2019), tức mất đúng ca kiểm chứng bắt buộc §6.2.

> **05/08, cùng phép đo trên corpus đã nạp:** 67 cạnh (23 corpus + 44 vbpl) vẫn quy hết,
> **0 rơi**; node rỗng **32 → 27** (5 văn bản nạp đợt này rời tập stub), 38 cạnh đủ hai đầu
> có toàn văn, 29 còn chạm stub.
>
> **Đợt 2 (cùng ngày), phép đo chuẩn của test (corpus + lược đồ ND52):** 70 cạnh vào, 0 rơi,
> **48** đủ hai đầu có toàn văn, **22** node rỗng — xem `test_corpus_that_cong_luoc_do_that`
> cho số học từng phần của cả ba mốc 48/18/30 → 58/33/25 → 70/48/22. Đúng cơ chế thiết kế ở §3.6: node rỗng là *trạng thái chờ*,
> mỗi đợt nạp rút bớt — không phải nợ vĩnh viễn.

**Một lược đồ không đủ, và đây là bằng chứng chứ không phải suy đoán.** Lược đồ của một văn bản
chỉ chứa quan hệ **với chính nó**. Trong lược đồ NĐ52, `41/2025/TT-NHNN` và `22/2026/TT-NHNN` chỉ
hiện ra là `CAN_CU` (mức *thấp*); thêm lược đồ của **chính TT40/2024** thì cả hai lộ ra ở nhóm
`incoming / "Văn bản sửa đổi bổ sung"` — chúng **sửa đổi TT40/2024**, và mức nhảy lên *cao*. Tức
corpus đang ghi TT40/2024 là *còn hiệu lực, chưa sửa đổi* — và điều đó **sai**. Cùng lượt còn lộ
`29/VBHN-NHNN` (`HOP_NHAT`), mã thứ 7 có instance.

⇒ **Phải crawl lược đồ của TỪNG văn bản corpus**, không chỉ của các đầu mút.

**Cơ chế cập nhật là SUY RA, không vá.** Node rỗng không ai soạn — điều kiện tồn tại của nó là
"chưa văn bản nào trong corpus nhận số hiệu này". Crawl xong, đưa toàn văn vào corpus kèm
`so_hieu` ⇒ lần nạp sau cạnh tự quy về `doc_id` thật, node rỗng không được sinh lại. Không có
bước di trú, không có trạng thái phải đồng bộ tay. Đường nạp bổ sung dùng
`don_node_rong_da_co_toan_van()` cho cùng kết quả.

Hai chỗ **cố ý không làm**: node rỗng lấy chính số hiệu làm `doc_id` (bịa `ND16-2019` thì đến
lúc crawl thật rất dễ thành hai node cho một văn bản), và `related_docs()` **loại** node rỗng
khỏi truy hồi (trích dẫn một node rỗng là trích dẫn thứ chưa đọc) trong khi `related_edges()`
vẫn giữ — ở đó chính **cạnh** mới là thông tin.

Danh sách cần crawl: `docs/CAN-CRAWL.md`, sinh bằng
`uv run python -m app.ingestion.can_crawl --md docs/CAN-CRAWL.md`.

### 3.8 · Khối trích dẫn: chỗ §5 đặc tả kỹ nhất vẫn còn một lỗ

§5 là khối v0.5 viết chặt nhất — `so_goc`/`so_hau_to`, bảng 23 chữ, `Điều 15a`. Nhưng nó đặc tả
**cách đọc một con số**, không nói con số ấy **thuộc về ai**.

Văn bản sửa đổi chép nguyên văn nội dung mới vào giữa hai dấu ngoặc kép, và phần chép mang đánh
số của văn bản **bị** sửa. `80/2016/NĐ-CP` Điều 1 vì thế đếm phẳng ra **14 khoản**, thật ra là
**10 của ND80 + 4 của ND101**. Cây `provisions` của nguồn nói 10 — và cây đúng.

Hậu quả không nằm ở con số mà ở khoá: `80/2016/NĐ-CP#than/dieu_1#khoan_5` trỏ vào **hai thứ khác
nhau**, một trong hai là nội dung của văn bản khác. Đúng loại nhập nhằng §4 sinh ra để chặn, mà
§4 không chặn được vì nó chỉ quy định *hình dạng* khoá.

Đã xử lý ở `parser.trong_trich_dan()` — mặt nạ theo ký tự, cả ba chỗ nhận diện (khoản · điểm ·
tiết) bỏ qua dòng trong khối. Khối **ở lại trong `text` của khoản mẹ**: bỏ khoản-giả khác hẳn bỏ
chữ, không có nó thì khoản 1 chỉ còn câu lệnh trống nghĩa. Ngoặc lệch ⇒ **bỏ luật cho cả Điều
đó** thay vì đoán chỗ đóng.

Đo trước khi viết, và chính phép đo cho phép làm: ngoặc **cân 100%** trên 9 bản ghi · **0/18
fixture** dính ⇒ 94 đơn vị và nhãn vàng không đổi · corpus có **75 khoản** đang gán nhầm chủ,
tất cả ở TT20-2016 và TT23-2019 — đúng hai văn bản sửa đổi. Sau khi sửa: ND80 Điều 1 về **10
khoản khớp cây**, `char_span` không khoản nào lệch, ND52/TT15/TT40 không đổi một con số.

> ⇒ **Đề nghị cho v0.6:** §5 nên có một mục *"phạm vi đánh số"* — số thứ tự chỉ thuộc về văn bản
> đang đọc khi nó nằm **ngoài** khối trích dẫn. Đây là mục thứ 8 trong §4 (PoC đi trước v0.5).

> **06/08 — lỗ này đã đóng ở TẦNG TRUY HỒI (P4), không chỉ ở parser.** `parser.trong_trich_dan()`
> chặn nhập nhằng lúc *dựng* khoá; nhưng chunk retrieval vẫn có thể là một khối trích dẫn nằm
> trong văn bản sửa, và trước P4 nó bị trích dưới tên văn bản sửa. Nhánh 3 của `dinh_tuyen`
> (`la_loi_sua`) nay map ngược về đích và trả câu trích dẫn đúng chủ. Đo trên production:
> `TT41-2025::Điều 10` → *"TT40-2024 Điều 26 Khoản 1 (sửa bởi TT41-2025 Điều 10 Khoản 1)"*.
> Nhận diện bằng **chữ chứa nhau**, không bằng toạ độ — hàng LanceDB không mang `char_start`, và
> thêm toạ độ vào chunk nghĩa là đổi ingest + re-embed toàn bộ.

---

## 4. Chín chỗ PoC đã đi TRƯỚC v0.5 — v0.6 nên hấp thụ

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

### Hai mục thêm cuối ngày 04/08 — khác ba mục trên ở chỗ chúng chạm vào chính khối v0.5 đặc tả kỹ

| phát hiện | số đo | v0.5 nói gì |
|---|---|---|
| **Node rỗng** (`VanBanRong`) — đầu mút xuất hiện trong đồ thị mà **chưa có toàn văn** vẫn là một node thật, có `so_hieu`, tự biến mất khi crawl xong | 57 cạnh quy hết về `doc_id`, **32 đầu mút** thành node rỗng; `related_docs()` loại chúng khỏi truy hồi còn `related_edges()` giữ | v0.5 §3 **giả định mọi node đều có văn bản**. Nhưng ca kiểm chứng bắt buộc §6.2 (*khoảng trống lập pháp*) chỉ tồn tại **ở đúng những đầu mút chưa tải** — bỏ chúng đi là bỏ luôn ca kiểm chứng |
| **Phạm vi đánh số** (`trong_trich_dan`) — số thứ tự chỉ thuộc văn bản đang đọc khi nằm **ngoài** khối trích dẫn | ND80 Điều 1: **14 → 10 khoản**, khớp cây nguồn; ngoặc cân 100%/9 bản ghi; **0/18 fixture** dính; corpus có **75 khoản** gán nhầm chủ (TT20-2016, TT23-2019) | §5 đặc tả *cách đọc* một con số rất chặt nhưng **không nói con số ấy thuộc về ai**. Xem §3.8 |

Năm mục này chung một luận điểm với bốn mục trên: **v0.5 đặc tả rất kỹ *địa chỉ* của một quy phạm
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
| §4 · Khoá ba nhánh | **1/3** — `#than/` có, `#kemtheo_`/`#phuluc_` không sinh được |
| §5 · Đánh số Điều/Khoản | **5/6** — thêm luật *phạm vi đánh số* (§3.8), v0.5 chưa có |
| §3 · Node meta-schema | **4/15** — dữ liệu `Chuong`/`Muc` ~~chưa nạp, corpus 0/278~~ → **nạp 05/08 (2 đợt): 180/425 điều có `chapter`** (§2.3); vẫn là trường phẳng, chưa phải node nên điểm khối chưa nhích |
| §6 · 13 quan hệ | **13/13 trong schema · ~~4/13~~ → 5/13 có instance trong corpus (05/08: `BAI_BO` ×4, `kiem_quan_he` 0 cạnh sai)** · 7/13 khi hợp nhất lược đồ vbpl — cạnh đã CÓ KIỂU ⇒ Cypher của spec chạy được; sau đợt 2: **35 cạnh corpus + 35 vbpl (lược đồ ND52) = 70 quy hết về `doc_id`, 0 rơi, 22 đầu mút còn là node rỗng, 48 cạnh đủ hai đầu có toàn văn** (§3.7) |
| §7 · Tầng thời gian | **0/5** |
| §8 · Độ tin cậy | **0/2** |
| §9 · Mười quyết định | 3 đạt · 2 không đạt · 1 một phần · 4 chưa áp dụng được |

> **§6 đi qua hai bước ngày 04/08.** Bản 03/08 đếm **4/13** vì dữ liệu có 4 `rel_type`. Đối chiếu
> từng tên (§3.5b) thì thực chất chỉ **2** trùng tên v0.5 — đếm một cạnh sai tên là đạt thì lần
> cutover sẽ vỡ im lặng. Sau đó sửa cả hai đầu: **schema** lên đủ 13 mã dưới dạng **tập đóng có
> validator** kèm cạnh có kiểu trong Neo4j, và **dữ liệu** về đúng 4 mã v0.5 (`HUONG_DAN` → `CAN_CU`
> theo lược đồ vbpl.vn). Hai con số tách riêng vì chúng nói hai chuyện: *"hệ đã biểu diễn được"* và
> *"corpus đã có bao nhiêu"*.

**Kết luận, không làm tròn lên:** phần v0.5 đặc tả kỹ nhất — đánh số và khoá nhánh `than` —
code đã thoả và **có test canh**. Phần còn lại của v0.5 phần lớn **chưa tồn tại dưới dạng
code**, và ba chỗ mâu thuẫn ở §3 là thứ phải xử lý trước khi dựng thêm, không phải sau.

### Việc còn đọng — đã có chẩn đoán, chưa xử lý

| # | việc | mức | chi phí |
|---|---|---|---|
| 1 | `status` bốn trạng thái (§3.1) — **lỗi đang sống, đo lại 04/08 vẫn còn**: `valid_from=2030` hôm nay hiện ra `het_hieu_luc`, trong khi nó **chưa từng** có hiệu lực | cao | nhỏ, chạm web |
| 2 | `is_effective` sang nửa mở (§3.2) — **đo lại 04/08 vẫn ĐÓNG**: `valid_to=2024-07-01` hỏi đúng ngày 01/07 vẫn trả `True`, lệch v0.5 đúng **một ngày** | cao | một dấu `<` + test biên |
| 3 | Chặn khoá `#than/` bịa (§3.4) | trung bình | nhỏ |
| 4 | Thống nhất không gian ID (§3.3) | cao | lớn — quyết định kiến trúc |
| ~~5~~ | ~~13 cạnh có kiểu thay `REL{rel_type}`~~ — ✅ **xong 04/08** | — | truy vấn §6.2 nay viết được (`khoang_trong_lap_phap()`); ~~corpus 0 `BAI_BO` nên trả rỗng~~ → **05/08 corpus đã có cạnh đó** (NĐ52 → NĐ16/2019, neo Điều 37→Điều 3) |
| 6 | `la_vbhn`, `nguon_hieu_luc_den`, `da_xac_minh_nguon` (§2.5, §2.6) | trung bình | nhỏ mỗi cái, nhưng cần quy trình nhập liệu đi kèm |
| 7 | `nhanh` thành trường, `Khoan.ten` nullable (§2.2, §2.7) | thấp | rất nhỏ |
| 8 | `PhienBanDieu`, `Chuong`/`Muc`, `VanBanKemTheo`, `PhuLuc` | — | ~~phụ thuộc #4~~ → **xem #10**: `Chuong`/`Muc` KHÔNG phụ thuộc #4 |
| 9 | Sửa changelog v0.5 §2 cho khớp bảng §5 (`so_goc` chứ không `so_khoan_goc`) | thấp | sửa spec, không sửa code |
| ~~10~~ | ~~Giữ dòng Chương/Mục ở `extract.py:90`~~ — ✅ **giải bằng đường khác 04/08**: nguồn crawl trả sẵn, `vbpl_corpus` nhận được **115/174 điều có `chapter`**. Không cần sửa `extract.py` nữa; chỉ còn **nạp** | — | gộp vào #14 |
| ~~11~~ | ~~Bắc cầu `so_hieu` trên `DocumentMeta`~~ — ✅ **xong 04/08**: 15/15 văn bản có `so_hieu`, `doc_id` không đổi một dòng | — | `app/ingestion/bac_cau.py` · 16 test |
| ~~12~~ | ~~Chuẩn hoá 4 tên quan hệ~~ — ✅ **xong 04/08**: `SUA_DOI`→`SUA_DOI_BO_SUNG`, `HUONG_DAN`→`CAN_CU` | — | `kiem_quan_he` báo **0 cạnh sai** |
| ~~13~~ | ~~Nạp lược đồ vbpl thành cạnh~~ — ✅ **xong 04/08**: 48 cạnh quy được về `doc_id`, **0 cạnh rơi**; 30 đầu mút thành **node rỗng** | — | xem §3.6 |
| ~~**14**~~ | ~~Nạp 7 văn bản đã crawl vào corpus~~ — ✅ **xong 05/08** (`app/ingestion/nap_corpus.py`): 15→20 văn bản, đã đo từng điều trước khi thay; đúng như chẩn đoán, **corpus là bên sai ở TT15** (Điều 18 nuốt Điều 19, tách xong 22→23 điều). Mở khoá đủ ba thứ: `chapter` 115/338, ca `BAI_BO` §6.2, khoản về đúng chủ | — | 9 cạnh mới có căn cứ; TT22-`BAI_BO`→TT41 **cố ý không thêm**: lược đồ vbpl nói "bị bãi bỏ" nhưng toàn văn TT22 không có câu bãi bỏ và vbpl gắn TT41 "Hết hiệu lực một phần" — hai nguồn vbpl mâu thuẫn thì người quyết |
| **15** | ~~Chạy `supabase/migrations/0006_quan_he_v05.sql`~~ — ✅ **user đã chạy 04/08** | — | xem §3.6c |
| **16** | **Crawl tiếp** — danh sách tự lớn 67→**89 văn bản** (`research/crawl_68_urls.txt`, thứ tự GẤP→thấp); `30/2016/TT-NHNN` và `58/2021/NĐ-CP` đã nạp ở đợt 2 05/08 | cao | phụ thuộc dữ liệu, không phụ thuộc code |
| ~~**17**~~ | ~~Đẩy corpus mới lên Neo4j~~ — ✅ **xong 06/08**: `push_corpus` 26 node + 35 cạnh, và `push_overlay` thêm **293 `DonVi` · 178 `TAC_DONG` · 255/293 `THUOC`**. Aura chỉ bị **tự pause** chứ không chết (đã resume 05/08). Rớt kết nối một lần giữa ~470 round-trip — `MERGE` idempotent nên chạy lại là đủ; đó cũng đúng minor N+1 mà reviewer Task 8 đã nêu (chưa `UNWIND`) | — | xem khối P4 đầu tài liệu |
| **19** | **Bộ câu hỏi eval chấm ở mức điều/khoản** — bộ 36 câu hiện tại chấm ở `doc_id` nên **không đo được** lớp phủ (router OFF/ON: 0/36 khác nhau). Đây là việc mở khoá con số trình hội đồng | cao | viết bộ câu hỏi mới, không sửa code |
| **18** | **Nhận `source_url`/`source_files` vào `DocumentMeta`** (§2.6) — bản ghi crawl đã có, `doc_file` đọc xong rồi bỏ đi | trung bình | rất nhỏ; là tiền đề của `da_xac_minh_nguon`, không thay thế nó |

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

# --- corpus: TRƯỚC nạp 05/08 các số là 278 · 0 chapter · 13 quan hệ (giữ làm mốc §3.5) ---
$c = Get-Content data\corpus.real.json -Raw | ConvertFrom-Json
$a = $c.documents | ForEach-Object { $_.articles }
$a.Count                                        # 425   (trước 05/08: 278; sau đợt 1: 338)
($a | Where-Object { $_.chapter }).Count        # 180   (trước 05/08: 0; sau đợt 1: 115)
($a | Where-Object { $_.valid_to }).Count       # 0 — hết hiệu lực chỉ ghi ở CẤP VĂN BẢN (ND101, ND80…), cấp điều vẫn trống (§2.5 chưa đổi)
$c.relationships.Count                          # 35    (trước 05/08: 13; sau đợt 1: 23)
$c.relationships | Group-Object rel_type        # CAN_CU 13 · SUA_DOI_BO_SUNG 9 · THAY_THE 6 · BAI_BO 4 · DAN_CHIEU 3

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
print('khớp tên v0.5 :', sorted(co & V))        # lúc đo 04/08: THAY_THE, DAN_CHIEU → 2/13; sau nạp 05/08 in đủ 5 mã
print('KHÔNG khớp    :', sorted(co - V))        # lúc đo 04/08: HUONG_DAN, SUA_DOI; nay rỗng
print('BAI_BO        :', sum(1 for x in r if x['rel_type'] == 'BAI_BO'))   # 04/08: 0 → 05/08: 1
"@

# --- (d) so_hieu: đọc được, và KHÔNG cắt cụt khi gặp homoglyph ---
$env:PYTHONPATH="."; uv run python -c @"
from app.ingestion.extract import so_hieu_trong
for s in ['Số: 52/2024/NĐ-CP', 'Số: 51/2025/TT-BTС', 'Số: 123/QĐ-NHNN', 'ngày 15/5/2024']:
    print(f'{s:28} -> {so_hieu_trong(s)}')   # ...TT-BTC (đã khử С Cyrillic) · ... · None
"@

# --- §3.6/§3.7: cầu số hiệu → doc_id, node rỗng, danh sách cần crawl ---
uv run pytest -q tests\test_bac_cau.py tests\test_quan_he_web.py
uv run python -m app.ingestion.can_crawl        # 20 có toàn văn · 23 cạnh corpus + 134 vbpl · 68 cần crawl (04/08: 13+134; 68 giữ nguyên vì 8 văn bản nạp đợt này vốn đã crawl xong)

# --- §3.8: khối trích dẫn — ND80 Điều 1 phải ra 10 khoản, KHÔNG phải 14 ---
uv run pytest -q tests\test_ontology_trich_dan.py

# --- §3.1 và §3.2: hai lỗi còn sống. Đo TRỰC TIẾP, đừng đọc code rồi suy ---
$env:PYTHONPATH="."; uv run python -c @"
from app.ingestion.versioning import is_effective
print([is_effective('2020-01-01','2024-07-01',False,d) for d in
       ('2024-06-30','2024-07-01','2024-07-02')])   # [True, True, False] ⇒ khoảng ĐÓNG
print(is_effective('2030-01-01',None,False,'2026-08-04'))  # False ⇒ UI dán nhãn 'het_hieu_luc'
"@

# --- §2.3: Chương/Mục — trường sống chưa, dữ liệu nạp chưa ---
$env:PYTHONPATH="."; uv run python -c @"
from pathlib import Path
from app.ingestion.pipeline import load_corpus
from app.ingestion.vbpl_corpus import doc_thu_muc
d, _ = load_corpus('data/corpus.real.json')
print('corpus  :', sum(1 for x in d for a in x.articles if a.chapter), '/', sum(len(x.articles) for x in d))
k = [x for x in doc_thu_muc(Path('data/raw/vbpl')) if x.van_ban]
print('đã crawl:', sum(1 for x in k for a in x.van_ban.articles if a.chapter), '/', sum(len(x.van_ban.articles) for x in k))
"@

# --- §4: 13 guard · 5 Điểm có tiết · 2 nhóm guard anh em ---
$env:PYTHONPATH="."; uv run pytest -q tests\test_ontology_guard.py tests\test_ontology_phan_hoach.py tests\test_ontology_chapeau_tiet.py
```

```bash
uv run python -m app.ontology --classify data/fixtures
# 94 đơn vị: 45 premise · 9 meta_cu · 40 actor_cu
```

Hai số ở §4 **không đo lại trong đợt 04/08**, lấy từ số đo đã ghi trong code:
4/586 viện dẫn tới cấp tiết (`app/ontology/citation.py:9-16`) và 25/267 điều không chẻ khoản
(`app/ontology/parser.py:176-186`). Cả hai đo trên corpus 15 văn bản, không phải trên 18 fixture.

### Lệnh thêm ngày 05/08 (#14 — nạp corpus)

```powershell
# Nạp lặp lại được (idempotent): chạy thêm lần nữa phải in đúng cùng bộ số, không nhân đôi
uv run python -m app.ingestion.nap_corpus --kho   # → 26 văn bản · 425 điều · 35 quan hệ

# 0 cạnh sai, BAI_BO=1, hết cảnh báo "trả RỖNG"
uv run python -m app.ingestion.kiem_quan_he

# Toàn bộ phép đo của đợt nạp nằm dưới dạng test: bảng nghiệm thu mới (TT15 23/98/57),
# đuôi hành chính bị cắt, cạnh thiếu đầu mút bị chặn, 57/25/32 của tầng bắc cầu,
# ca BAI_BO có neo Điều 37→Điều 3, và 17 viện dẫn cấp tiết (4 cũ + 5 TT41 + 8 TT66)
uv run pytest -q tests\test_nap_corpus.py tests\test_vbpl_corpus.py tests\test_bac_cau.py tests\test_ontology_citation.py tests\test_ontology_parser.py
```

Viện dẫn cấp tiết 4/586 nói trên nay là **17** (đo 05/08, xem
`tests/test_ontology_citation.py::test_bao_phu_corpus_that`) — tăng đúng ở TT41/TT66, hai thông
tư sửa đổi nhắm vào tiết.

### Lệnh thêm ngày 06/08 (P4 — nối lớp phủ vào sản phẩm)

```powershell
# --- artefact tự chứa: 178 cạnh, khớp đúng nguồn JSONL của P1 ---
$env:PYTHONIOENCODING="utf-8"; uv run python -m app.ontology.dong_goi
uv run python -c "import json,pathlib; g=json.loads(pathlib.Path('data/overlay/lop_phu.json').read_text(encoding='utf-8')); n=sum(1 for _ in open('eval/overlay/canh_tac_dong.jsonl',encoding='utf-8')); print(len(g['canh']), n, len(g['canh'])==n)"
# 178 178 True   -- lệch ⇒ ĐIỀU TRA, không chỉnh test cho khớp

# --- LanceDB production: 661 chunk / 26 văn bản ---
$env:PYTHONPATH="."; uv run python -c "from app.core import vectordb; from app.core.config import LANCEDB_TABLE; t=vectordb.connect().open_table(LANCEDB_TABLE); r=t.search().limit(10000).to_list(); print(t.count_rows(), len(set(x['doc_id'] for x in r)))"
# 661 26

# --- Neo4j: 293 DonVi · 178 TAC_DONG · 255 THUOC ---
$env:PYTHONPATH="."; uv run python -c "from app.knowledge.graph import session
with session() as s:
    print(s.run('MATCH (n:DonVi) RETURN count(n) AS c').single()['c'],
          s.run('MATCH ()-[r:TAC_DONG]->() RETURN count(r) AS c').single()['c'],
          s.run('MATCH ()-[r:THUOC]->() RETURN count(r) AS c').single()['c'])"

# --- NGHIỆM THU DEPLOY: OpenAPI của bản ĐANG PHỤC VỤ, không phải exit code ---
uv run python -c "import httpx; sch=httpx.get('https://lexflow-api-puuthweg3q-as.a.run.app/openapi.json',timeout=60).json()['components']['schemas']; print('tac_dong' in sch['DocumentDetail']['properties'], 'trang_thai' in sch['Citation']['properties'], 'TacDongDonVi' in sch)"
# True True True

# --- verify e2e: trích dẫn đúng chủ + ca cạnh-chết, chạy qua _prepare THẬT ---
$env:PYTHONPATH="."; uv run python -c "from app.knowledge.lop_phu import tai_lop_phu, chu_thich_chunk
lp=tai_lop_phu()
for cid in ['TT41-2025::Điều 10','TT41-2025::Điều 16']:
    t=chu_thich_chunk({'id':cid,'text':''},'2026-08-06',lp); print(cid,'->',t.trang_thai)"
# TT41-2025::Điều 10 -> nguyen_ven (cần text thật mới ra la_loi_sua — nhánh 3 nhận diện bằng CHỮ)
# TT41-2025::Điều 16 -> bi_bai_bo

# --- benchmark router ON/OFF (cần PYTHONPATH, và -u để thấy tiến độ) ---
$env:PYTHONIOENCODING="utf-8"; $env:PYTHONPATH="."; uv run python -u eval/run_benchmark.py
# 36 câu, 0 lỗi; stale-avoidance 21/36 -> 36/36; router OFF|ON khác nhau 0/36; 8 hit được nắn
```

**Đọc kỹ ba chỗ dễ hiểu sai trong bộ lệnh trên.** (1) `chu_thich_chunk` với `text` rỗng trả
`nguyen_ven` cho `Điều 10` — không phải sai, vì nhánh 3 nhận diện bằng **chữ chứa nhau**; muốn
thấy `la_loi_sua` phải truyền text thật của chunk. (2) `PYTHONPATH="."` là bắt buộc khi chạy
`eval/run_benchmark.py` trực tiếp — thiếu nó ra `ModuleNotFoundError: No module named 'app'`.
(3) Deploy: **đừng** đọc exit code qua pipe (`gcloud … | grep | tail` trả mã thoát của `tail`);
ghi thẳng ra log rồi bắt `$?`, và nghiệm thu bằng OpenAPI của bản đang phục vụ.
