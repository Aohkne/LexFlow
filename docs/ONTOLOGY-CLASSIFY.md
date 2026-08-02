# Bước phân loại premise · meta-CU · actor-CU (chạy trước khi trích S-O-A-C)

Bổ sung cho `docs/ONTOLOGY-POC.md`. Tài liệu này chỉ nói về **bước phân loại** và
những chỗ nó còn mơ hồ.

Chạy:

```bash
uv run python -m app.ontology --classify data/fixtures     # bảng phân loại, không gọi LLM
uv run python -m eval.ontology.classify_testset            # 5 case bắt buộc, không gọi LLM
uv run python -m app.ontology --batch data/fixtures --out eval/ontology/pred.jsonl
```

---

## 1. Vì sao cần bước này

Pipeline trước mặc định **mọi Khoản đều là Compliance Unit**. `roles.py` đã hạ bớt
sai lệch đó ở **mức Điều** (đo được 40/278 điều, 14.4%, không phải actor-CU), nhưng
vai của Điều không phải lúc nào cũng là vai của từng Khoản bên trong.

Bằng chứng đo được, không phải suy đoán — 4 CU mà pipeline cũ sinh ra từ ND52 Điều 2
*"Đối tượng áp dụng"* (đã có trong `pred.jsonl` bản trước):

| khoản | `subject.text` | `action.text` | `action.label` |
|---|---|---|---|
| 1 | Tổ chức cung ứng dịch vụ thanh toán… | **y hệt subject** | "Là đối tượng áp dụng" |
| 2 | `2. Tổ chức cung ứng dịch vụ trung gian thanh toán.` | **y hệt subject** | "Đối tượng áp dụng" |
| 3 | Tổ chức, cá nhân có liên quan đến… | "có liên quan đến…" | "Có liên quan đến…" |
| 4 | Tổ chức, cá nhân sử dụng dịch vụ… | "sử dụng dịch vụ…" | "Sử dụng dịch vụ…" |

**4/4 có `action` suy biến**: hoặc trùng khít `subject`, hoặc là mệnh đề định ngữ của
chính danh ngữ đó. Không CU nào mang một vị ngữ deontic. Khoản 1 tệ nhất — nhãn
*"Là đối tượng áp dụng"* là vị ngữ mô hình tự thêm, cả cụm đó chỉ có trong **tiêu đề
Điều**, không có trong khoản. Nó lọt guard vì chữ "là" không nằm trong từ điển tình
thái, nhưng nó vẫn là một vị ngữ được dựng ra để lấp ô trống.

Bí danh *"khách hàng"* của khoản 4 thì bị nhét vào `subject.label`, chỗ không phân
biệt được với một câu diễn giải bất kỳ — tức là một tuyên bố của chính văn bản bị hạ
xuống thành lời của mô hình.

Đó là lý do bước phân loại phải chạy **trước**, ở **mức Khoản**.

---

## 2. Có nên mặc định coi "Đối tượng áp dụng" là premise không?

**Câu trả lời: có, ở mức Khoản — nhưng không phải vì thế mà cả Điều là premise.**
Hai phán quyết nằm ở hai cấp và cả hai đều đúng:

| cấp | vai | vì sao |
|---|---|---|
| **Điều 2** trọn vẹn | `meta_cu` | mệnh đề *"Nghị định này áp dụng đối với …"* nằm ở **tiêu đề + phép liệt kê**. Nó chặn cổng chủ thể cho cả văn bản. |
| **từng khoản** 1–4 | `premise` / `vai_tro` | mỗi khoản là một **danh ngữ trần**: *"Tổ chức cung ứng dịch vụ trung gian thanh toán."* Không có vị ngữ, nên không có gì để vi phạm và cũng không có mệnh đề nào để chặn cổng. |

Phép thử phân biệt là **có vị ngữ hay không**. Một cái cổng phải là một *mệnh đề có
giá trị đúng/sai*. `"Tổ chức cung ứng dịch vụ trung gian thanh toán."` không phải
mệnh đề — nó là một **hạng từ**, một phần tử của tập chủ thể mà cổng mức Điều phủ.

Vì vậy `PremiseRecord` có trường `gop_vao_gate` trỏ về `dieu.id`: khai báo vai trò
**góp vào** cổng, chứ bản thân không **là** cổng.

Mặc định này áp cho toàn bộ 7 khoản "Đối tượng áp dụng" trong bộ fixture (ND52 Điều 2
×4, TT40 Điều 2 ×3) — 7/7 là danh ngữ trần. Nhưng **không phải luật cứng**: nếu một
khoản "Đối tượng áp dụng" mang dấu hiệu nghĩa vụ/cấm đoán thật, Test B sẽ đẩy nó về
`actor_cu`. Chưa gặp trường hợp nào trong corpus 11 văn bản, nên đường đó chưa được
kiểm chứng bằng dữ liệu thật.

---

## 3. Ba phép thử, và phần nào là xấp xỉ

| phép thử | câu hỏi | hiện thực |
|---|---|---|
| **A** vị trí văn bản | đơn vị có cặp chủ-thể + hành-vi tại chỗ không? | luật tiêu đề (`roles.title_rule`) + từ điển tình thái (`modality.py`) + bộ dò mệnh đề cổng |
| **B** vi phạm độc lập | có thể tự bị phán "không tuân thủ" không? | có nghĩa vụ/cấm đoán ⇒ actor-CU; có mệnh đề cổng ⇒ meta-CU; không cả hai ⇒ premise |
| **C** phạm vi ảnh hưởng | chặn tới đâu? | `Gate.pham_vi` + `Gate.targets`, giải bằng `citation.py` |

**Chỗ phải nói thẳng:** Test A trong bài viết gốc là quan hệ **cú pháp** ("cùng một
câu"). Ở đây **không có phân tích cú pháp tiếng Việt**. Nó được xấp xỉ bằng hai tín
hiệu đã đo được. Mọi nhánh quyết định được ghi vào `UnitVerdict.test_path`, nên người
đọc thấy được phép xấp xỉ nào đã dùng chứ không chỉ nhận một cái nhãn.

Khi hai tín hiệu cãi nhau ở một điều `premise` (ví dụ một định nghĩa có chứa "phải"
thật), **luật tiêu đề thắng và có cảnh báo** — vì luật tiêu đề đã được đo (40/278, và
9/11 · 8/11 theo quy ước vị trí) còn từ điển tình thái là xấp xỉ có bẫy đã biết.

---

## 4. Thiết kế trường `gates` — và vì sao không dùng list phẳng

Bài báo GraphCompliance định nghĩa meta-CU nhưng **không công bố listing JSON nào cho
nó** (chỉ có ví dụ actor-CU, Article 37 GDPR). Phần này là suy diễn theo đúng ngữ
nghĩa *"chặn cổng cho nhiều actor-CU, bản thân không tự bị vi phạm"*.

Bản phác thảo ban đầu đề nghị `gates: list[str]` (danh sách ID, để trống/TODO nếu
chưa suy ra được). Đã đổi sang một đối tượng có cấu trúc, vì list phẳng **không diễn
đạt được hai tình huống có thật**:

1. **"Toàn văn bản"** — liệt kê ra thì ND52 phải ghi 267 khoá node, và danh sách đó
   sai ngay khi văn bản được bổ sung thêm điều. `pham_vi="van_ban"` + `targets=[]`
   nói đúng ý "phủ tất cả" mà không phải đếm.
2. **"Quy định tại Mục này…"** — parser chỉ có Điều→Khoản→Điểm, **không có node Mục**.
   Với list phẳng thì buộc phải trả `[]`, không phân biệt được với "không chặn gì cả".
   `suy_ra_duoc=False` nói thẳng *"có phạm vi nhưng chưa quy được về khoá node"*.

Hai trường nữa sinh ra từ văn bản thật, không phải từ thiết kế bàn giấy:

| trường | vì sao | nguồn |
|---|---|---|
| `phu_dinh` | *"Quy định tại khoản 1 Điều này **không** áp dụng đối với…"* — bỏ sót chữ "không" là **đảo ngược** hiệu lực của cả khoản 1 | TT40 Điều 26 khoản 2 |
| `ngoai_tru` | *"…có hiệu lực từ ngày 17/7/2024, **trừ trường hợp** quy định tại khoản 2, 3, 4, 5 Điều này"* — các đơn vị bị khoét khỏi phạm vi, khác hẳn `targets` | TT40 Điều 52 khoản 1 |

### 4.1. `subject: null` khi cổng không có bên bị ràng buộc

Chạy thật cho thấy ô `subject` **không hợp** với mệnh đề hiệu lực: *"Nghị định này có
hiệu lực thi hành từ ngày 01/7/2024"* có chủ ngữ **ngữ pháp** ("Nghị định này") nhưng
không có **tác nhân** nào để tuân thủ hay vi phạm. ⟨S⟩ của GraphCompliance là *bên bị
ràng buộc*, không phải chủ ngữ của câu. Bắt điền ô đó chỉ đẩy mô hình đi chọn bừa một
đơn vị — 3/6 meta-CU của TT40 Điều 52 bị guard chặn cứng chính ở đây.

Nên `subject` được phép `null`. **Tiền lệ nằm ngay trong Listing 1 của bài báo**:
`"context": null` đã được chấp nhận là hợp lệ khi trường không áp dụng. Đây là cùng
một loại vắng mặt — vắng mặt về **cấu trúc**, khác hẳn vắng mặt do trích hỏng.

Ranh giới cố ý hẹp:

| nhóm cổng | `subject` | vì sao |
|---|---|---|
| `thoi_gian` · `lanh_tho` | được `null` | không có bên bị ràng buộc |
| **`chu_the`** (role qualification) | **vẫn bắt buộc** | *"…chỉ áp dụng đối với tổ chức đã được cấp Giấy phép"* CÓ một vai cần định danh |
| meta-CU chưa xác định được cổng | **vẫn bắt buộc** | không có cổng = chưa có căn cứ nào để miễn |
| `actor_cu` | **vẫn bắt buộc** | luôn có chủ thể |

`null` chỉ có nghĩa **"không áp dụng"**, không bao giờ có nghĩa "chưa trích được": uid
sai vẫn là lỗi *mất provenance* kể cả ở đơn vị được miễn, và ô trống vẫn hiện thành
một dòng trong trang kiểm chứ không biến mất. Prompt cũng được sửa để nói thẳng với
mô hình rằng khoản này trả `"units": []` — miễn mà không nói thì mô hình vẫn điền.

**Kết quả đo lại:** 8/9 meta-CU ra `subject: null`; đúng một cái giữ subject là TT40
Điều 26 khoản 2 (`chu_the`, *"Quy định tại khoản 1 Điều này"*). Lỗi cứng ở ô `subject`
**3 → 0**.

**Nhưng vấn đề chỉ dịch chỗ, chưa hết.** Tổng số bản ghi có lỗi cứng **4 → 5**: các
diễn giải lệch-neo chuyển sang `conditions[]`. TT40 Điều 52 khoản 3/4/5 **không có
điểm nào**, mô hình vẫn sinh 1–2 "điều kiện", neo vào nửa câu nêu phạm vi rồi gắn nhãn
bằng nửa câu nêu ngày — cả hai nửa đều là chữ thật của cùng khoản đó, nên đây là lệch
**phạm vi neo**, không phải bịa. Cùng một kiểu sai mà `subject` vừa mắc.

Và chỗ hổng thật: `Gate` có `kind="thoi_gian"` **nhưng không có trường ngày**. Mốc
hiệu lực — thứ duy nhất đáng kể của cổng thời gian — hiện chỉ sống sót dưới dạng chữ
tự do trong `action`. **Đã chốt và đã sửa — xem §4.2.**

### 4.2. Chốt: giữ 4-tuple, structure hoá Θ thay vì tách schema riêng

Đây là câu trả lời cho câu hỏi để ngỏ ở §4.1 và §6 mục 7.

**Quyết định.** Không tách meta-CU loại thời gian ra một schema riêng. Thay vào đó ô
điều kiện mang **object có cấu trúc**, nội dung đổi theo `Gate.kind`. Tiền lệ nằm ngay
trong Listing 1 của bài báo: `condition` ở đó là JSON lồng (`{"any": [...]}`), không
phải chuỗi phẳng — nên "ô điều kiện có cấu trúc" không phải phát minh mới, chỉ là dùng
đúng cái ô đã có.

```python
class DieuKienCong(BaseModel):
    kind: Literal["thoi_gian"]
    ngay: str | None = None                    # ISO; None = không có/không đọc được
    moc: Literal["bat_dau", "ket_thuc"] = "bat_dau"
    raw_text: str = ""
    char_span: tuple[int, int] | None = None
    ghi_chu: str = ""
```

Ba chỗ **khác** với bản đề xuất, mỗi chỗ vì một lý do đo được:

**1. Không có luật "char_span phải liên tục" — luật đó không bao giờ bắn được.**
`resolve()` trả `hull(units, uids)`, tức bao lồi của các đơn vị đã chọn: span liền mạch
**theo cấu trúc**, `quote` chỉ thu hẹp *bên trong* bao lồi, và kiểu là `tuple[int,int]`.
Một span "nhảy cóc" **không biểu diễn được** trong schema này. Thêm luật đó vào chỉ tạo
một ô xanh vĩnh viễn.

Lỗi thật có hình dạng khác hẳn: span **liên tục và đúng**, còn *nhãn* mô tả chữ nằm
**ngoài** span. Và nó **đã bị bắt** — chính là 3 lỗi cứng ở khoản 3/4/5. Bộ dò không
hỏng; chỗ hỏng là mô hình bị ép lấp một ô không có nội dung. Nên chặn bằng **cấu trúc**:

> meta-CU cổng `thoi_gian`/`lanh_tho` **VÀ** Khoản không chẻ Điểm ⇒ `conditions` rỗng.

Vế thứ hai bắt buộc. Khoản 6 cũng là cổng thời gian nhưng **có** điểm a/b mang mốc hết
hiệu lực riêng cho từng quy định của TT39/2014 — xoá chúng là mất thông tin thật.
Mô hình trả điều kiện dù đã được dặn thì **bỏ + cảnh báo nêu tên cái đã bỏ**, không
phải lỗi cứng: mốc ngày đã được tách tất định nên bản ghi vẫn dùng được.

**2. `moc` chứ không phải một trường tên "ngày hiệu lực".** Khoản 6 điểm a/b viết
*"có hiệu lực thi hành **đến hết ngày** 14 tháng 8 năm 2024"* — mốc **kết thúc**; chapeau
khoản 6 viết *"**hết hiệu lực** kể từ ngày…"*. Nhét một ngày kết thúc vào ô đọc ra là
"ngày bắt đầu có hiệu lực" là đảo ngược hiệu lực trong im lặng — đúng loại lỗi mà
`Gate.phu_dinh` đã sinh ra để chặn.

**3. Không dùng lại `suy_ra_duoc` cho trạng thái ngày.** Cờ đó đang mang đúng một nghĩa:
*"phạm vi quy được về khoá node"*. Khoản 3 có `suy_ra_duoc=False` (viện dẫn phân phối
chưa đọc được) trong khi mốc ngày parse hoàn hảo — hai thứ độc lập, gộp lại là mất khả
năng biết cái nào hỏng. Trạng thái ngày nằm ở `ngay is None` + `ghi_chu`, và `ghi_chu`
phân biệt **ba** tình huống: đọc được · không có ngày tuyệt đối (*"kể từ ngày Thông tư
này có hiệu lực"* — viện dẫn tương đối) · có cụm ngày nhưng không hợp lệ.

**Ai sinh ra `char_span` mới là chỗ quyết định.** Đề xuất yêu cầu span khớp đúng
`raw_text` và không lan sang phần câu khác, nhưng không nói ai sinh nó. Nếu để mô hình
sinh qua `quote` thì quay lại đúng lỗi cũ. Ở đây nó do **regex của ta** chạy trên
`khoan.text` rồi quy về `dieu.text` (`+ khoan.start`, cùng kỷ luật với `alias_span`) —
cùng cách `find_alias` và `tiet_logic` đang làm. Yêu cầu "không lan" vì thế đúng **theo
cấu trúc**, không nhờ một phép validate chạy sau.

**Tên trường và đánh đổi.** Gọi là `dieu_kien_cong`, không phải `condition`: model đã có
`conditions` (số nhiều, mỗi Điểm một phần tử) mà `run_eval.py`, `make_gold_seed.py`,
`review_ui.py` đều đọc — hai cái tên chỉ khác một chữ `s` cạnh nhau là bẫy gõ nhầm im
lặng. Đánh đổi phải nói ra: `gates` là **list** còn trường này là **số ít**. Đặt mốc ngày
ở đây (thay vì trên `Gate`) đúng về ngữ nghĩa — `Gate` là *phạm vi*, đây là *phép thử* —
nhưng downstream phải join hai trường để biết "chặn cái gì, từ bao giờ". Hiện
`detect_gate` trả tối đa một cổng nên chưa mơ hồ; giảm nhẹ bằng cách dựng nó cùng chỗ
với `Gate`, 1:1 với cổng nó thuộc về.

**`lanh_tho` cố ý chưa dựng.** Corpus 16 fixture không có một mệnh đề lãnh thổ nào và
`detect_gate` chưa bao giờ phát ra loại cổng đó. Nó vẫn nằm trong luật `conditions` rỗng
(không tốn gì) nhưng **không** có trường dữ liệu — bịa một trường cho case 0 lần xuất
hiện là thiết kế không có dữ liệu.

#### Kết quả đo, theo từng bản ghi

Lỗi cứng **5 → 2**, không phải "gần 0":

| bản ghi | trước | sau | vì sao |
|---|---|---|---|
| TT40 Đ52 k3 · k4 · k5 | 1 · 1 · 2 | **0 · 0 · 0** | không chẻ Điểm ⇒ `conditions` rỗng |
| TT40 Đ52 **k6** | 2 | **2** | **CÓ điểm a/b thật** — nằm ngoài luật này, xem §6 mục 7 |
| TT17 Đ16 k2 | 1 | **1** | actor-CU — lúc đó đọc là "guard bắt đúng một nhãn bịa". **Sai**, xem §4.3 |

Mốc ngày tách được cho **7/9** meta-CU: `2024-07-01` · `2024-07-17` · `2024-08-15` ·
`2024-10-01` · `2025-01-01` · `2025-07-01`, cộng khoản 6 ra `moc="ket_thuc"` không ngày.
Hai cái còn lại đúng là không có mốc riêng: ND52 Đ37 k2 (điều khoản thay thế) và
TT40 Đ26 k2 (cổng chủ thể). Mọi `char_span` round-trip đúng `raw_text` trên `dieu.text`.

Phụ phẩm: khoản 1 và 2 của TT40 Điều 52 trước đây cũng sinh mỗi cái một "điều kiện"
lệch-neo (chưa tới mức lỗi cứng nên không bị đếm) — nay cũng rỗng.

---

### 4.3. Hợp đồng của modality guard khi `quote` thu hẹp span

Đợt trước để lại hai lỗi cứng và **chẩn đoán sai cả hai**. Lần này đo trước khi sửa:
quét toàn bộ **296 nhãn không rỗng** trong `pred.jsonl`, tìm từ mang nghĩa vụ/cấm đoán
("phải", "phải được", "cần", "bắt buộc", "có nghĩa vụ", "không được", "cấm") xuất hiện
trong **nhãn** mà không có trong **span** đã neo, rồi đối chiếu ngược lại văn bản gốc.

Kết quả: **đúng 1 lần trên 296**, và cụm đó **có trong văn bản gốc**, nguyên văn.

**Không có thói quen "nâng cấp câu mô tả thành câu nghĩa vụ".** Tần suất bịa thật trên
corpus này là **0/296**. Vì vậy **không** dựng danh sách từ khoá deontic thứ hai chạy
song song `modality.py`: nó sẽ trôi lệch khỏi `MODALITY` mà không bắt thêm được gì. Vì
vậy cũng **không** siết prompt — sửa prompt để chữa 1 case là đem 295 nhãn còn lại ra
đánh cược, trong khi tầng tất định chữa được mà không đụng tới hành vi mô hình.

#### Hai lỗi cứng, hai chẩn đoán đều phải sửa lại

**TT17 Điều 16 khoản 2 điểm c — báo nhầm, không phải bịa.** Mô hình chọn `units`
`[6…14]` = **trọn** điểm c. Bao lồi của tập đó chứa nguyên văn:

> Các thông tin, dữ liệu **phải được** lưu trữ an toàn, bảo mật, **được** sao lưu dự
> phòng, đảm bảo tính đầy đủ, toàn vẹn của dữ liệu…  *(đơn vị [13])*

Rồi nó dùng `quote` thu hẹp span về **câu đầu** của điểm c. Guard so nhãn với span đã
hẹp ⇒ kết luận *"bịa ràng buộc nhóm nghia_vu"*. Nhãn trung thành với bằng chứng mô
hình đã trích dẫn; chỗ hỏng là `quote` thu hẹp sai chỗ.

**TT40 Điều 52 khoản 6 — lỗi cứng ĐÚNG, nhưng lý do ghi ở mục 7a cũ là sai.** Mục đó
viết rằng mô hình *"neo bằng `quote` vào đuôi điểm a rồi lấy `object_label` từ đầu cùng
điểm a"*, tức cùng bệnh với TT17. Đo lại: **không phải**. Điểm a bị tách thành 5 đơn vị
`[18…22]` và mô hình chỉ chọn **`[22]`** — bao lồi *chính là* đơn vị đó, nới ra không
lấy thêm được chữ nào. Các số `9a`, `11`, `4`, `23/2019` trong `object_label` thật sự
**không** nằm trong bằng chứng nó trích dẫn. Đây là **trích thiếu đơn vị**, và lỗi cứng
là phán quyết đúng.

#### Luật: cáo buộc VẮNG MẶT phải kiểm trên bằng chứng đã trích dẫn

`modality.relax_absence` — trước khi cho một cáo buộc thành lỗi cứng, kiểm lại nó trên
**bao lồi các đơn vị mô hình đã chọn**, không phải trên lát cắt `quote` đã thu hẹp.
Không thể kết tội bịa một cụm nằm nguyên văn bên trong chính bằng chứng bị viện ra.

Nới **có chọn lọc**, và ranh giới nằm ở tính đơn điệu:

| tín hiệu | bản chất | theo độ rộng nguồn | có nới? |
|---|---|---|---|
| `invented_groups` | vắng mặt — *"nguồn không hề có nhóm này"* | đơn điệu: nguồn rộng ra ⇒ phát hiện chỉ co lại | **có** |
| `added_numbers` | vắng mặt — *"số này không có trong nguồn"* | đơn điệu | **có** |
| `flips` | biến đổi một đoạn cụ thể | không đơn điệu | không |
| `condition_to_obligation` | biến đổi — đòi dấu hiệu điều kiện **mất đi** | **ngược** đơn điệu | không |

Vế cuối không phải lý thuyết. Nới cả gói cho đúng case TT17 điểm c thì `invented_groups`
hết, nhưng `condition_to_obligation` **lại nổ**: bao lồi dài 1097 ký tự có *"khi có yêu
cầu từ cơ quan có thẩm quyền"* ở một mệnh đề mà bản tóm tắt 150 ký tự không nhắc tới.
Nới cả gói là đổi một báo nhầm này lấy một báo nhầm khác.

#### Hạ mức không được im lặng

Hạ mức luôn kèm cảnh báo nêu đích danh cụm bị hạ **và** hệ quả còn lại:

```
điều kiện c.constraint_label: hạ mức 'bịa ràng buộc nhóm nghia_vu': cụm này CÓ trong
  các đơn vị đã chọn, chỉ nằm ngoài đoạn mà 'quote' thu hẹp vào
điều kiện c.constraint_label: ⇒ 'quote' thu hẹp sai chỗ: `text` của trường này KHÔNG
  chứa đoạn mà nhãn đang mô tả — cần người duyệt xác nhận phạm vi
```

Vế thứ hai là vế quan trọng: bản ghi hết lỗi cứng **không** có nghĩa là nó đã ổn.
`text` (chữ của luật) vẫn hẹp hơn cái `constraint_label` đang nói tới, và người duyệt
phải biết điều đó. Cố ý **không** tự động nới span về bao lồi: sửa provenance bằng suy
đoán còn tệ hơn nêu tên chỗ lệch.

Bắt được chỗ này lại lòi ra một chỗ giấu tin khác: `make_gold_seed.to_seed` cắt cảnh báo
ở `[:5]` cho gọn, mà đúng hai dòng trên nằm ở vị trí 6–7 của 10 ⇒ khung duyệt hiện ra
bản ghi sạch còn lý do nó sạch thì bị cắt mất. Đã bỏ cắt.

**Đo được:** lỗi cứng **2 → 1**. Trên 49 CU chỉ **một** bản ghi đổi (TT17 Đ16 k2), và
đổi từ 1 lỗi cứng thành 4 cảnh báo nêu rõ lý do. `--classify` không xê dịch một dòng.

---

### 4.4. Menu đơn vị bị vỡ vì `\n` của HTML — sửa ở tầng tách

§4.3 kết luận TT40 Điều 52 khoản 6 là *"mô hình chọn thiếu đơn vị"*. Câu hỏi phải trả
lời trước khi sửa: các số `9a` · `11` · `4` · `23/2019` nằm ở đâu? In nguyên văn ra:

```python
'a)\nĐiều 9a\nvà\nkhoản 4 Điều 11\nđã được sửa đổi, bổ sung theo Thông tư số\n'
'23/2019/TT-NHNN\ncó hiệu lực thi hành đến hết ngày 14 tháng 8 năm 2024;'
```

**Điểm a là MỘT câu, 142 ký tự, 7 dòng.** Các số nằm ở đơn vị `[18]`–`[21]` — những
đơn vị mô hình không chọn. Nhưng gọi đó là "mô hình chọn thiếu" là dừng lại quá sớm:
menu bày ra cho nó gồm `'a) Điều 9a và'` · `'khoản 4 Điều 11'` · `'đã được sửa đổi, bổ
sung theo Thông tư số'` · `'23/2019/TT-NHNN'` · `'có hiệu lực thi hành đến hết ngày…'`.
Bốn trong năm là câu cụt không có vị ngữ. Mô hình chọn mảnh duy nhất đứng vững một
mình. **Với cái menu đó thì không có lựa chọn nào đúng để mà chọn.**

Vì sao vỡ, truy được tới dòng code:

1. `clean_text` (`parser.py:86`) giữ **mỗi dòng nguồn một dòng**, và chỉ nối lại những
   mảnh hyperlink *bắt đầu bằng dấu câu* (`_ORPHAN_PUNCT`).
2. Nguồn là HTML: mỗi viện dẫn nằm trong một thẻ `<a>` nên chiếm trọn một dòng. Mảnh
   bắt đầu bằng chữ hoặc số (`Điều 9a`, `23/2019/TT-NHNN`) rơi ngoài luật ở bước 1.
3. `segment()` coi `\n` là ranh giới cứng.
4. `_MIN_UNIT = 15` gộp mảnh ngắn hơn 15 ký tự. `'khoản 4 Điều 11'` và
   `'23/2019/TT-NHNN'` **dài đúng 15** — hụt đúng một ký tự để được gộp.

**Sửa (mức 0 của `segment`):** gom dòng nối tiếp một câu — dòng nào mà dòng trước nó
chưa kết thúc (không tận cùng bằng `.`/`;`/`:`) thì nối lại, và **chỉ nối trong cùng một
Điểm**. Vế sau bắt buộc: thiếu nó, một Điểm tình cờ không có dấu kết sẽ nuốt trọn Điểm
sau — đổi lỗi vỡ vụn lấy lỗi dính liền, tệ hơn vì mất luôn ranh giới Điểm.

Đây là chỗ hỏng **nằm trước** mọi tầng chống bịa: `char_span` do ta tính nên mô hình
không bịa được provenance, nhưng nếu tập đóng nó được chọn đã sai thì đảm bảo đó rỗng.

#### Đo diện rộng (16 fixture, đúng kỷ luật §4.3)

| chỉ số | trước | sau |
|---|---|---|
| chỗ xuống dòng giữa câu | **90/267** dòng, ở **21/94** khoản | — |
| đơn vị (không tính uid 0) | 293 | **237** |
| đơn vị kết thúc giữa câu | **64 (22%)** | **0** |
| TT40 Đ52 k6 | 27 đơn vị | **6** |

Không phải một bản ghi lẻ. Bất biến `dieu.text[start:end] == text`, không chồng lấn,
và đơn vị nằm trọn trong Điểm của nó — cả ba đều được canh trên **toàn corpus**.

#### Hệ quả: 1 → 3 → 1, và hai khiếm khuyết có sẵn của guard lộ ra

Chạy lại batch: K6 **sạch**, nhưng tổng lỗi cứng **1 → 3**. Ba cái ở ba bản ghi khác.
Đọc từng cái đối chiếu luật:

| bản ghi | guard nói | thực tế |
|---|---|---|
| ND52 Đ26 k1 `subject` | đảo cực `'sau: tên tổ chức…đã được cấp'` → `'khi thay đổi nội dung giấy'` | **báo nhầm** — nhãn nén một danh sách liệt kê; difflib gióng **29 từ với 6 từ** |
| TT17 Đ16 k1 `cond[c]` | điều kiện → nghĩa vụ | **báo nhầm** — nhãn **chép lại** `"không được thực hiện"` của luật rồi bỏ đuôi danh ngữ chứa `"khi mở"` |
| TT40 Đ26 k2 `subject` | bịa số `26` | **đúng** — mô hình đổi *"Điều này"* → *"Điều 26"* |

Cả hai báo nhầm là khiếm khuyết **có sẵn**, chỉ chưa gặp đoạn nguồn đủ dài để lộ. Hai
giả thuyết đầu của tôi về cách tách chúng **đều sai khi soi opcode**: `flips` *không*
bắt được case hồi quy gốc (nên không gộp được hai luật làm một), và dấu hiệu điều kiện
bị mất nằm trong opcode `delete` ở **cả hai** case (nên loại opcode cũng không tách được).

Dấu hiệu tách được, tìm ra bằng cách nhìn dữ liệu:

- **`flips`** — đảo cực là phát biểu về việc **tráo một từ**, nên hai vế phải ngắn. Đo
  được: flip thật là **1↔1** từ; báo nhầm duy nhất là **29↔6**. Chặn ở `_FLIP_MAX_TU = 6`.
- **`condition_to_obligation`** — xét cặp **(dấu hiệu cứng + từ liền sau)**. Case gốc:
  `"phải đáp"` **không** có trong nguồn (luật viết *"**khi** đáp ứng"*) ⇒ vẫn nổ. TT17:
  `"không được thực"` **có** nguyên văn trong nguồn ⇒ mô hình chép chứ không chế ⇒ im.
  Xét riêng dấu hiệu thì không tách được, vì cả hai bên đều có nó.

Số cuối: **1/49** lỗi cứng, và nó là cái **đúng**.

---

### 4.5. Lớp lỗi thứ ba: khai triển viện dẫn tương đối

Lỗi cứng còn lại sau §4.4 là TT40 Điều 26 khoản 2: luật viết *"Quy định tại khoản 1
**Điều này** không áp dụng…"*, mô hình viết *"Quy định tại khoản 1 **Điều 26**"*.

Nó **không** thuộc hai lớp trên. Mô hình suy ra **đúng** — đó *là* Điều 26 — nhưng số
26 không nằm trong đoạn nó viện dẫn (`units=[1]`, dài 53 ký tự), và bao lồi cũng không
có ⇒ `relax_absence` bất lực. Guard làm đúng hợp đồng; mô hình cũng không sai về nghĩa.

**Đo trước khi dựng luật** (294 nhãn trong `pred.jsonl`):

| | số case |
|---|---|
| nhãn thêm số so với đoạn đã neo | **1** |
| …trong đó nguồn có cụm tự trỏ (`"Điều này"`…) | **1** |
| …và số thêm vào **khớp** đơn vị đang xét | **1** ← luật đụng tới |
| nguồn có cụm tự trỏ nhưng số thêm vào **khác** | **0** ← luật không được đụng |

Dòng cuối bằng 0 nghĩa là **corpus không kiểm được vế chống lọt**. Vế đó phải canh
bằng test dựng tay, và test phải nói rõ là dựng tay.

**Luật (`modality.relax_dereference`)** — ba điều kiện, đủ cả ba mới hạ mức, cả ba đều
kiểm tất định:

1. đoạn luật đã neo **thật sự** chứa `"Điều này"` / `"khoản này"`;
2. số bị tố cáo **khớp đúng** số Điều/Khoản đang xét;
3. trong nhãn, số đó đứng **ngay sau** đúng từ đó (`"Điều 26"`).

Vế 3 là vế chống lọt: thiếu nó thì một nhãn bịa *"áp dụng cho **26** tổ chức"* nằm
trong Điều 26 cũng được tha — mà đó mới đúng là bịa số.

Chỉ dựng cho `Điều` và `khoản`: `điểm` đánh bằng chữ cái nên không sinh số, còn
*"Thông tư này"* / *"Nghị định này"* thì **chưa có case nào** mô hình khai triển ra số
hiệu — dựng trước là thiết kế không có dữ liệu.

**Vì sao hạ mức chứ không sửa mô hình:** `citation.py` đã giải viện dẫn tương đối
thành khoá node ở `references` một cách tất định — bản ghi này mang sẵn
`['40/2024/TT-NHNN#than/dieu_26#khoan_1']`. Việc dereference đã xong ở đúng chỗ của nó;
nhãn chép thêm số vào **không mang thêm thông tin**. Phép nới chỉ để bản ghi khỏi bị
đánh dấu không dùng được, **không** để khuyến khích mô hình tự suy.

#### Lỗi cứng 1 → 0, và vì sao con số đó không được đứng một mình

**0/49 lỗi cứng** — nhưng nó là 0 vì **2 bản ghi được nới**, mỗi lần đều để lại cảnh
báo nêu đích danh:

| bản ghi | nới bằng | cảnh báo còn lại |
|---|---|---|
| TT17 Đ16 k2 | `relax_absence` | *"`quote` thu hẹp sai chỗ: `text` KHÔNG chứa đoạn mà nhãn đang mô tả"* |
| TT40 Đ26 k2 | `relax_dereference` | *"khai triển viện dẫn tương đối… khoá node đã có sẵn ở `references`"* |

Hai câu cảnh báo **khác nhau** là có chủ ý: người duyệt phải biết bản ghi sạch vì lý do
nào. Bản ghi được nới vẫn là bản ghi **cần đọc kỹ**, không phải bản ghi đã ổn — riêng
TT17 Đ16 k2 thì `text` và `constraint_label` vẫn đang nói về hai đoạn khác nhau.

Toàn corpus: **82 cảnh báo trên 28/49 bản ghi**. Số lỗi cứng bằng 0 **không** có nghĩa
là không còn gì để duyệt.

---

## 5. Kết quả trên bộ fixture (16 file, 11 văn bản gốc)

94 đơn vị (Khoản; Điều không chẻ khoản tính là 1):

| loại | số đơn vị | ghi chú |
|---|---|---|
| `premise` | 45 | 36 định nghĩa · 7 vai trò · 2 phạm vi |
| `actor_cu` | 40 | đi tiếp vào trích S-O-A-C |
| `meta_cu` | 9 | 8 cổng thời gian · 1 cổng chủ thể (phủ định) |

Sau khi trích: **49 CU** (9 meta-CU), **45 bản ghi premise** (11 có bí danh),
**36 KhaiNiem**. Trước thay đổi này là 48 CU / 0 premise.

Cổng: **5/9 quy được về khoá node**, 4 còn lại khai rõ `suy_ra_duoc=False` kèm lý do.
Mốc ngày (§4.2): **7/9** meta-CU có `dieu_kien_cong`, trong đó 6 cái đọc ra ngày ISO.

Lỗi cứng: **0/49** — nhưng xem §4.5: nó là 0 vì **2 bản ghi được nới**, mỗi lần kèm
một cảnh báo nêu đích danh. Toàn corpus còn **82 cảnh báo trên 28/49 bản ghi**.

---

## 5b. Duyệt phán quyết phân loại

Bản đầu của trang duyệt **không hiện vai**: 49 CU trong danh sách trông y hệt nhau dù
9 cái là meta-CU, và 45 bản ghi premise không xuất hiện ở đâu cả — cả bước phân loại
nằm ngoài tầm duyệt. Nay:

- mỗi mục mang huy hiệu `ACTOR` · `META` · `PREMISE`, kèm bộ lọc theo vai;
- CU có ô chọn `role` — sửa được **vai** chứ không chỉ span;
- meta-CU hiện **bảng cổng**: kind · phạm vi · đích · `LOẠI TRỪ` khi `phu_dinh` ·
  `chưa quy được về khoá node` khi `suy_ra_duoc=False`;
- premise có khung riêng (loại con + bí danh + nguyên văn + cổng nó góp vào), ẩn hẳn
  thanh gán Subject/Action vì premise không có 4-tuple;
- `run_eval.py` thêm chỉ số **`role_accuracy`** — vai là phán quyết **độc lập** với
  span: một CU neo hoàn hảo nhưng gán nhầm `meta_cu` sẽ **không bao giờ** bị phán định
  vi phạm, và sai kiểu đó không hiện ra ở bất kỳ chỉ số span nào.

Hai hợp đồng, hai file: `gold.jsonl` (CU) và `gold.premise.jsonl`. Trộn chung sẽ khiến
`run_eval.py` gặp bản ghi không có `subject_span` và tính sai trong im lặng.

## 6. Case mơ hồ và giới hạn còn để ngỏ

**1. Bẫy "phải" phi-deontic.** Chạy lần đầu, 6/94 đơn vị bị đẩy nhầm sang `actor_cu`:

- `"tổ chức **không phải là** ngân hàng"` — hệ từ phủ định (ND52 Đ3 k5, TT40 Đ3 k13)
- `"số tiền **phải thu, phải trả**"` — danh ngữ kế toán (ND52 Đ3 k15, TT40 Đ3 k7/k9)

Đã che hai khuôn này **chỉ ở tầng phân loại**. `modality.py` cố ý giữ nguyên độ nhạy:
ở đó bắt nhầm chỉ tốn một cảnh báo, còn bỏ sót là lọt một nghĩa vụ bịa ra. Hai khuôn
này là *khuôn*, không phải danh sách đầy đủ — chắc chắn còn cách dùng "phải" phi-deontic
khác chưa gặp.

**2. Văn phạm viện dẫn chưa đọc được danh sách nhiều cấp.** Ba hình thái, đều có thật
trong TT40 Điều 52:

| viết trong luật | vấn đề | xử lý hiện tại |
|---|---|---|
| `Điều 35, khoản 4 Điều 47` | `khoản 4` bị nuốt thành `Điều 4` | **đã sửa** — từ nối tiếp danh sách phải cùng cấp |
| `khoản 2 Điều 17, Điều 18, Điều 19…` | cách đọc đúng: khoản 2 **chỉ** của Điều 17 | **bỏ**, `suy_ra_duoc=False` |
| `điểm c, điểm đ khoản 1, điểm b, điểm d khoản 2 Điều 25` | Điều nằm ở **cuối**, dùng chung cho cả hai cụm | **bỏ cụm đầu**, giữ cụm sau |

Hai dòng cuối là giới hạn thật, **chưa sửa**. Chọn bỏ thay vì đoán: phát ra
`dieu_18#khoan_2` là một khoá **sai** trông y như khoá đúng. Sửa tử tế cần viết lại
văn phạm viện dẫn thành parser danh sách phân phối — việc riêng, không gộp vào đây.

**3. Viện dẫn trỏ sang văn bản khác không được giải.** Điều khoản bãi bỏ
(TT40 Đ52 k6, ND52 Đ37 k2) nhắc *"Điều 2 của Thông tư số 20/2016/TT-NHNN"*. Giải bằng
số hiệu của văn bản **đang xét** sẽ ra khoá sai mà không ai biết ⇒ trả rỗng +
`suy_ra_duoc=False`.

**4. Bí danh trong đơn vị actor-CU chưa vào sổ.** Đo trên corpus: **73 lần** xuất hiện
khuôn `(sau đây gọi là …)` trên 11 văn bản, văn bản nào cũng có ít nhất 1. Trong bộ
fixture, 11 bí danh nằm ở đơn vị premise (đã vào `premise.jsonl`) và **1 nằm ở đơn vị
actor-CU** (TT18 Điều 9 khoản 2, *"người đại diện hợp pháp"*) — hiện **chưa lưu ở đâu
cả**, vì sổ đăng ký chỉ nhận premise. Đó là mất mát có thật, đã biết.

**5. Cấp Chương/Mục không tồn tại trong parser.** Nên cổng phạm vi Mục (case 5 của bộ
test) nhận đúng là meta-CU nhưng không quy được về khoá node. Muốn hết mơ hồ thì phải
thêm hai cấp đó vào cây, không phải sửa classifier.

**6. Nhánh "Đối tượng áp dụng có nghĩa vụ thật" chưa có dữ liệu.** Xem §2.

**7. `conditions[]` và mốc ngày của cổng thời gian — ĐÃ CHỐT, xem §4.2.** Giữ 4-tuple,
cho ô điều kiện mang object có cấu trúc. Lỗi cứng **5 → 2** (§4.2) → **1** (§4.3) →
**0** (§4.4 sửa tầng tách, §4.5 lớp lỗi thứ ba) — với hai bản ghi được nới có ghi tên.

**7a. TT40 Điều 52 khoản 6 — ĐÃ XỬ LÝ ở tầng tách, xem §4.4.** Mục này đã sai **hai
lần**, cùng một kiểu sai: suy luận nghe hợp lý mà không mở dữ liệu ra xem.

| lần | chẩn đoán | sai ở đâu |
|---|---|---|
| 1 | *"mô hình bị phạt vì đã neo chính xác hơn"* | bao lồi `==` span, không có chuyện `quote` thu hẹp |
| 2 | *"mô hình chọn thiếu đơn vị"* | đúng về hiện tượng, sai về tầng — menu vốn không có lựa chọn nào đúng |

Nguyên nhân thật: `\n` do thẻ `<a>` của HTML để lại làm vỡ một câu 142 ký tự thành 5
"đơn vị", 4 trong đó là câu cụt. Sửa ở `segment()`, không đụng guard. Đo diện rộng:
64/293 đơn vị từng kết thúc giữa câu, nay 0.

Còn để ngỏ: `_MIN_UNIT = 15` vẫn là một ngưỡng chọn tay. Nó không còn gây lỗi nào sau
khi gom dòng, nhưng vẫn là con số không có căn cứ đo đạc.

**7b. `quote` thu hẹp sai chỗ — ĐÃ XỬ LÝ, xem §4.3.** Mục cũ ở đây khẳng định TT17 Điều
16 khoản 2 là *"guard bắt đúng một nhãn bịa"*. Phép đo 296 nhãn cho thấy điều ngược lại:
cụm *"phải được lưu trữ an toàn, bảo mật"* nằm **nguyên văn** trong điểm c, trong đúng
tập đơn vị mà mô hình đã chọn. Đó là báo nhầm, đã hạ mức thành cảnh báo nêu đích danh.

Cái còn để ngỏ ở đây là bản thân phép nới: nó **giảm độ nhạy** khi mô hình chọn bao lồi
rộng — một nhãn bịa nằm lọt trong một bao lồi lớn sẽ không bị bắt là "bịa". Giảm nhẹ
hiện tại chỉ là: phép nới chỉ chạy khi `quote` thật sự thu hẹp span, và mỗi lần hạ mức
đều để lại cảnh báo. Trên corpus này nó chạy đúng **1/49** bản ghi.

---

## 7. Ranh giới quy công

| lấy từ bài báo (arXiv:2510.26309) | đóng góp riêng của PoC |
|---|---|
| ba vai premise / meta-CU / actor-CU | ánh xạ sang tiêu đề Điều của văn bản QPPL Việt Nam |
| meta-CU đánh giá trước, không tự bị vi phạm | `Gate` có cấu trúc: `pham_vi` · `targets` · `phu_dinh` · `ngoai_tru` · `suy_ra_duoc` |
| premise là chất liệu phi-deontic | tách `dinh_nghia` / `pham_vi` / `vai_tro`; trích bí danh tất định |
| `condition` là object lồng, `"context": null` hợp lệ khi không áp dụng (Listing 1) | `DieuKienCong` cho cổng thời gian: `ngay` ISO · `moc` bắt đầu/kết thúc · span do regex tách |
| — | ba phép thử A/B/C ghi lại `test_path`; bẫy "phải" phi-deontic |

Bài báo **không** có: nhãn vàng cho CU, IAA, listing JSON cho meta-CU, và không dùng
chữ "hallucination" ở đâu cả.
