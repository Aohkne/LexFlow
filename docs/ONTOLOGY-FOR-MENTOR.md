# Tầng chuẩn tắc dựng trên cây cấu trúc văn bản — PoC

> Bản tóm tắt cho mentor. Mọi ví dụ dưới đây là **bản ghi thật** máy trích từ văn bản
> luật thật (`eval/ontology/pred.jsonl`), không phải minh hoạ bịa.
> Chi tiết kỹ thuật: `docs/ONTOLOGY-POC.md`, `docs/ONTOLOGY-CLASSIFY.md`.

---

## 1. Hai tầng

```
┌─────────────────────────────────────────────────────────────┐
│  TẦNG CHUẨN TẮC  (ontology)                                 │
│  "ai phải làm gì" · "quy định nào có hiệu lực từ bao giờ"    │
│                                                              │
│     ActorCU        MetaCU        PremiseRecord / KhaiNiem   │
│        │              │                    │                 │
└────────┼──────────────┼────────────────────┼─────────────────┘
         │  neo bằng char_span + khoá node   │
         ▼              ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│  CÂY CẤU TRÚC  (taxonomy)                                   │
│  VanBan → Điều → Khoản → Điểm                               │
│  52/2024/NĐ-CP#than/dieu_22#khoan_2#diem_b                  │
└─────────────────────────────────────────────────────────────┘
```

**Chiều phụ thuộc chỉ đi một hướng.** Cây cấu trúc là **nền**: nó có địa chỉ ổn định
và giữ offset ký tự. Tầng chuẩn tắc **dựng trên** nó — mọi trường đều trỏ ngược xuống
bằng `char_span` (vị trí ký tự) và khoá node (địa chỉ). Cây cấu trúc **không biết gì**
về tầng trên; xoá tầng trên đi thì cây vẫn nguyên vẹn.

> *Chú thích thuật ngữ:* quan hệ Điều→Khoản→Điểm là **part-of** (meronomy) chứ không
> phải is-a. Tài liệu vẫn gọi là "taxonomy" theo cách dùng phổ biến trong KG, nhưng
> nêu ra để khỏi hiểu nhầm là phân loại theo lớp.

### Bất biến nền móng

```python
van_ban[node.start:node.end] == node.text
```

Cây không chứa bản sao văn bản — nó chứa **toạ độ**. Nhờ vậy mọi trường ở tầng trên
đều truy ngược được về đúng ký tự trong luật gốc, và có test canh trên từng nút.

---

## 2. Một Khoản có ba số phận

Bước phân loại chạy **trước**, tất định, **không gọi LLM**:

| vai | sinh ra | vì sao |
|---|---|---|
| `premise` | `PremiseRecord` (+ `KhaiNiem`) | không đặt nghĩa vụ ⇒ không có 4-tuple để trích |
| `meta_cu` | **`MetaCU`** | nêu phạm vi áp dụng, đánh giá **trước**, không tự bị vi phạm |
| `actor_cu` | **`ActorCU`** | nghĩa vụ nhắm vào chủ thể — thứ duy nhất bị phán định tuân thủ |

Trên 16 fixture / 11 văn bản: **94 đơn vị → 45 premise · 40 actor · 9 meta**.

---

## 3. `ActorCU` — "ai phải làm gì"

```python
ActorCU:
    subject          # ⟨S⟩ BẮT BUỘC — bên bị ràng buộc
    subject_source   # explicit | inherited
    action           # ⟨A⟩ hành vi
    logic            # all | any | unknown
    conditions[]     # mỗi Điểm một phần tử, mang ⟨O⟩ và ⟨C⟩
```

### Ví dụ 1 — TT17/2024 Điều 11 khoản 1

> **1. Cá nhân** mở tài khoản thanh toán tại ngân hàng, chi nhánh ngân hàng nước ngoài
> **bao gồm:**
> a) Người từ đủ 15 tuổi trở lên không bị hạn chế hoặc mất năng lực hành vi dân sự…;
> b) Người chưa đủ 15 tuổi… mở tài khoản **thông qua người đại diện theo pháp luật**;
> c) Người có khó khăn trong nhận thức… mở tài khoản **thông qua người giám hộ**.

| trường | giá trị | span |
|---|---|---|
| `subject` | `"Cá nhân"` | `[46,53]` |
| `action` | `"mở tài khoản thanh toán tại ngân hàng, chi nhánh ngân hàng nước ngoài"` | `[54,123]` |
| `logic` | `"any"` — *"bao gồm"* + ba trường hợp song song | |
| `conditions[a]` | ⟨O⟩ *"Người từ đủ 15 tuổi trở lên…"* · ⟨C⟩ *"không bị hạn chế… năng lực hành vi dân sự"* | `[133,247]` |
| `conditions[b]` | ⟨O⟩ *"Người chưa đủ 15 tuổi…"* · ⟨C⟩ *"…thông qua người đại diện theo pháp luật"* | `[248,425]` |
| `conditions[c]` | ⟨O⟩ *"Người có khó khăn trong nhận thức…"* · ⟨C⟩ *"…thông qua người giám hộ"* | `[426,565]` |

Đây là 4-tuple **đầy đủ**. `logic="any"` quan trọng: ba Điểm là ba **loại** cá nhân,
thoả một là đủ — đọc thành `all` thì hoá ra phải vừa trên vừa dưới 15 tuổi.

### Ví dụ 2 — TT40/2024 Điều 25 khoản 5 (không chẻ Điểm)

> **5. Tổ chức cung ứng dịch vụ ví điện tử** **không được** nhận tiền mặt từ khách hàng
> để nạp tiền vào ví điện tử; **không được phép** cấp tín dụng…, trả lãi trên số dư…

| trường | giá trị |
|---|---|
| `subject` | `"Tổ chức cung ứng dịch vụ ví điện tử"` `[2394,2429]` |
| `action` | `"không được nhận tiền mặt…; không được phép cấp tín dụng…"` `[2430,2590]` |
| `conditions` | **rỗng** |

**Khoản không chẻ Điểm ⇒ không có ⟨O⟩ lẫn ⟨C⟩ ở đâu cả** — bản ghi này là **2-tuple**.
Đúng **13/40** actor-CU rơi vào trường hợp này. Đây là hệ quả trực tiếp của việc đặt
⟨O, C⟩ **bên trong** `conditions` thay vì ở cấp CU (xem §6).

---

## 4. `MetaCU` — "quy định nào, từ bao giờ, trừ ai"

```python
MetaCU:
    gates[]          # phạm vi chặn: kind · pham_vi · targets · phu_dinh · ngoai_tru
    dieu_kien_cong   # mốc ngày CÓ CẤU TRÚC: ngay (ISO) · moc (bat_dau|ket_thuc)
    menh_de          # mệnh đề hiệu lực/phạm vi — KHÔNG phải hành vi
    logic
    conditions[]     # các đơn vị được liệt kê riêng trong mệnh đề
```

**Không có ô `subject`.** Không phải "để trống" — mà **không tồn tại**. Lý do ở §5.

### Ví dụ 3 — TT40/2024 Điều 52 khoản 2 (cổng thời gian)

> **2. Quy định tại Điều 11, Điều 12, Điều 13, Điều 14, Điều 35, khoản 4 Điều 47
> Thông tư này** có hiệu lực thi hành **từ ngày 15 tháng 8 năm 2024**.

| trường | giá trị |
|---|---|
| `gates[0]` | `kind=thoi_gian` · `pham_vi=dieu` · `suy_ra_duoc=True` · `phu_dinh=False` |
| `gates[0].targets` | 6 khoá node: `#dieu_11` `#dieu_12` `#dieu_13` `#dieu_14` `#dieu_35` `#dieu_47#khoan_4` |
| `dieu_kien_cong` | `ngay="2024-08-15"` · `moc="bat_dau"` · span `[256,304]` |
| `menh_de` | `"có hiệu lực thi hành từ ngày 15 tháng 8 năm 2024"` |
| `conditions` | rỗng |

Điều 52 **một mình** khai **5 mốc bắt đầu khác nhau + 1 mốc kết thúc**. Nếu gán một
`ngay_hieu_luc` duy nhất cho cả văn bản thì sai phạm vi cho phần lớn các Điều — đây là
lý do `gates` phải có `pham_vi` + `targets` thay vì một danh sách phẳng.

### Ví dụ 4 — TT40/2024 Điều 26 khoản 2 (cổng chủ thể, cực **âm**)

> **2. Quy định tại khoản 1 Điều này** **không áp dụng** đối với:
> a) Ví điện tử cá nhân của người có ký hợp đồng… làm đơn vị chấp nhận thanh toán;
> b) Các giao dịch thanh toán: điện; nước; viễn thông; học phí; viện phí;…

| trường | giá trị |
|---|---|
| `gates[0]` | `kind=chu_the` · `pham_vi=khoan` · **`phu_dinh=True`** ← LOẠI TRỪ |
| `gates[0].targets` | `#dieu_26#khoan_1` |
| `dieu_kien_cong` | `None` — không phải cổng thời gian, không có "từ bao giờ" |
| `menh_de` | `"Quy định tại khoản 1 Điều này không áp dụng đối với:"` `[343,398]` |
| `logic` | `"any"` — thuộc **một** trong hai nhóm là được miễn |
| `conditions` | a `[399,534]` · b `[535,973]` — **danh sách được MIỄN** |

Hai điểm đáng chú ý:

**`conditions` ở meta-CU mang nghĩa khác actor-CU.** Ở ví dụ 1 là *điều kiện phải
thoả*; ở đây là *danh sách được miễn*. Đọc phải kèm `phu_dinh` — bỏ sót chữ "không"
trong *"không áp dụng"* là **đảo ngược hiệu lực** của cả khoản 1.

**`dieu_kien_cong = None` chứng minh vì sao nó tách khỏi `Gate`.** Cùng là meta-CU,
nhưng cổng chủ thể không có "từ bao giờ" để mà điền.

---

## 5. Vì sao tách `ActorCU` và `MetaCU`

Ban đầu cả hai dùng chung schema 4-tuple. Đo trên **cả 9 meta-CU thật** thì:

1. **9/9 không có bên bị ràng buộc.** Tám cái để `subject` trống. Cái thứ chín (ví dụ
   4) *có* điền — nhưng điền *"Quy định tại khoản 1 Điều này"*, một **tập quy phạm**.
   Nó không tuân thủ, không vi phạm, không bị xử phạt được. ⟨S⟩ của GraphCompliance là
   *bên bị ràng buộc*, nên đó cũng không phải ⟨S⟩.
2. **⟨A⟩ không phải hành vi.** Tám cổng thời gian có `action` là *"có hiệu lực thi
   hành"* — **ba cái giống hệt nhau từng chữ**. Đó là **trạng thái của quy phạm**.
3. **Bài báo GraphCompliance không công bố listing nào cho meta-CU** — chỉ một ví dụ
   actor-CU (Article 37 GDPR). Nên "giữ chung cho đúng bài báo" đang bảo vệ một quy ước
   mà bài báo **không đặt ra**.
4. **Sự tách biệt vốn đã tồn tại**, chỉ viết bằng 6 nhánh `if role ==` trong code thay
   vì bằng kiểu dữ liệu — người đọc dữ liệu không thấy nó.

Kết quả: `menh_de` thay `action` ở meta-CU (một ô mang hai nghĩa tuỳ vai là mơ hồ im
lặng), và meta-CU **không còn ô `subject`**.

**Cái mất, ghi rõ:** cổng `chu_the` nay không có chỗ lưu **tên vai**. Lý lẽ cũ dựa trên
ví dụ giả định; cổng `chu_the` duy nhất trong corpus không nêu vai nào. Đúng kỷ luật đã
áp cho `lanh_tho`: **0 case thì không dựng trường**, gặp case thật thì thêm một trường.

---

## 6. Vì sao 4-tuple không phẳng

⟨S, A⟩ ở cấp **Khoản**; ⟨O, C⟩ ở cấp **Điểm**, bên trong từng `ConditionItem`.

Lý do là cấu trúc văn bản: một Khoản = một câu bao trùm (mang ⟨S, A⟩) + N Điểm, mỗi
Điểm là một cặp ⟨O, C⟩ **khác nhau**. Ví dụ 1 có 3 Điểm = 3 cặp; ND52 Điều 22 khoản 2
có **8 Điểm** = 8 điều kiện cấp phép độc lập (vốn điều lệ 50/300 tỷ, Đề án, nhân sự…).

Ép về một cặp phẳng thì hoặc **bỏ 7 điều kiện**, hoặc **nối chuỗi** và mất neo. Quan
trọng hơn: mỗi Điểm có khoá node riêng (`…#khoan_2#diem_b`), nên phẳng là mất khả năng
nói **"vi phạm điểm b"** — vốn là toàn bộ giá trị của một hệ kiểm tra tuân thủ.

Bài báo cũng không phẳng: `condition` trong Listing 1 là object lồng
(`{"any": [...]}`). `logic` + `conditions[]` của PoC chính là hình dạng đó.

---

## 7. Trạng thái thật — cái gì ĐÃ có, cái gì CHƯA

| | trạng thái |
|---|---|
| Cây cấu trúc + khoá node ba nhánh | **đã có**, có test canh bất biến offset |
| Phân loại 3 vai, tất định | **đã có** — 94 đơn vị: 45/40/9 |
| `ActorCU` / `MetaCU` / `PremiseRecord` / `KhaiNiem` | **đã có** — 40/9/45/36 bản ghi |
| Ba tầng chống bịa (menu span · từ điển tình thái · diff) | **đã có** — lỗi cứng 0/49 |
| Viện dẫn → khoá node | **đã có**, 5/9 cổng quy được |
| **Nạp vào Neo4j** | **CHƯA** — hiện là JSONL, khoá node ở dạng chuỗi |
| **Node `ChuThe` / `NghiaVu` / `ThucTheChiuDieuChinh`** | **CHƯA** — ⟨S⟩,⟨O⟩ mới là span + nhãn chữ |
| **Cạnh giữa các CU với nhau** | **CHƯA** — chỉ có cạnh CU → cây cấu trúc |
| **Bộ nhãn người gán** | **0/94** ⚠️ |

> ⚠️ **Chỗ yếu nhất.** Mọi con số hiện tại là *máy tự chấm máy* — đo tính nhất quán nội
> bộ, **không** đo tính đúng. `char_span` chứng minh chuỗi **có trong luật**, không
> chứng minh **trích đúng chỗ cần trích**. Chưa có precision/recall thật.

---

## 8. Ba câu hỏi xin ý kiến

1. **Nguồn gold label độc lập cho tầng chuẩn tắc lấy ở đâu?** Đây là thứ đang chặn cả
   tầng E của KG v0.5 (§10.2). Nếu tập luồng nghiệp vụ do chính tác giả soạn kèm khuyết
   tật cài sẵn thì không đo được năng lực thật.
2. **`char_span` có đủ tư cách làm nguồn kiểm chứng độc lập không**, hay vẫn bắt buộc
   phải có nhãn người gán?
3. **Đơn vị trích xuất là Khoản — có đúng không?** Điểm thường lược chủ ngữ vì là mệnh
   đề tiếp nối câu bao trùm, nên trích riêng từng Điểm sẽ khiến mô hình đoán bừa chủ ngữ.
