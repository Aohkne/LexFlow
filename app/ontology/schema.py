"""Schema Pydantic cho PoC ontology: cây Điều/Khoản/Điểm + Compliance Unit.

Ánh xạ sang tên node đã thiết kế trong KG v0.5 §10.2 (đang chờ chốt phát biểu
bài toán) — cố tình KHÔNG đẻ thêm từ vựng mới:

    Subject     → ChuThe
    Action      → NghiaVu
    Constraint  → BuocBatBuoc / NgoaiLe
    Object      → ThucTheChiuDieuChinh (P2)

Khoá node theo chuẩn KG v0.5 §4: nhánh `than` ghi tường minh, ví dụ
`52/2024/NĐ-CP#than/dieu_22#khoan_2#diem_b`.

Tách riêng khỏi app/core/schemas.py: file kia là hợp đồng API đang chạy.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# --- Cây cấu trúc văn bản -------------------------------------------------


class Node(BaseModel):
    """Một nút cấu trúc, kèm vị trí ký tự trong văn bản đã làm sạch.

    Bất biến: `van_ban[start:end] == text` (được test round-trip canh).
    """

    id: str
    kind: Literal["dieu", "khoan", "diem"]
    so_hien_thi: str  # "22", "15a", "2đ", "b"
    so_goc: int  # phần số; Điểm không có số → 0
    so_hau_to: int  # 1-based theo bảng 23 chữ; 0 = không hậu tố
    start: int
    end: int
    text: str


class TietSpan(BaseModel):
    """Tiết `(i)`/`(ii)` bên trong một Điểm.

    CỐ Ý KHÔNG có `id`: đo trên corpus thấy chỉ 4/586 viện dẫn đi tới cấp này, và
    cả 4 đều nằm trong văn bản đã hết hiệu lực ⇒ không cấp địa chỉ KG (xem
    docs/ONTOLOGY-POC.md §10). Dựng ở đây chỉ để giữ QUAN HỆ LOGIC giữa các tiết —
    thứ mà bỏ đi là mất nghĩa pháp lý, khác hẳn chuyện không viện dẫn tới được.
    """

    marker: str  # "i", "ii"
    start: int
    end: int
    text: str
    # Quan hệ với tiết KẾ TIẾP, đọc từ đuôi câu. "unknown" khi chỉ có dấu ';'
    # trần — tiếng Việt pháp lý dùng ';' cho cả liệt kê lẫn lựa chọn, đoán là sai.
    connector: Literal["hoac", "va", "unknown"] = "unknown"


class DiemNode(Node):
    kind: Literal["diem"] = "diem"
    tiet: list[TietSpan] = Field(default_factory=list)


class KhoanNode(Node):
    kind: Literal["khoan"] = "khoan"
    diem: list[DiemNode] = Field(default_factory=list)


class DieuNode(Node):
    kind: Literal["dieu"] = "dieu"
    tieu_de: str = ""
    khoan: list[KhoanNode] = Field(default_factory=list)


class Unit(BaseModel):
    """Đơn vị nguyên tử để LLM chọn theo ID. Offset tương đối với `dieu.text`."""

    uid: int  # 0 = tiêu đề Điều
    kind: Literal["tieu_de", "chapeau", "diem"]
    source_diem: str | None
    start: int
    end: int
    text: str


# --- Compliance Unit ------------------------------------------------------


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


class Grounding(BaseModel):
    """Bằng chứng neo một field về ký tự gốc trong `dieu.text`.

    LLM chọn `units` (ID trong tập đóng) nên `char_span` LUÔN hợp lệ — nó do ta
    tính, không phải do LLM khai. `quote` chỉ là tuỳ chọn để thu hẹp span trong
    phạm vi các đơn vị đã chọn.
    """

    units: list[int]
    char_span: tuple[int, int] | None
    # exact = quote khớp chính xác trong bao lồi; unit = chỉ neo được ở mức đơn vị;
    # invalid = LLM trả uid không tồn tại (mất provenance).
    status: Literal["exact", "unit", "invalid"]
    quote: str = ""


class GroundedField(BaseModel):
    """Một trường của CU: chữ của luật + diễn giải của mô hình, tách bạch."""

    text: str  # CHỮ CỦA LUẬT — lát cắt tại char_span, không phải chữ LLM viết
    label: str = ""  # diễn giải của mô hình, KHÔNG phải chữ của luật
    grounding: Grounding
    issues: list[str] = Field(default_factory=list)


class GuardApDung(BaseModel):
    """Điều kiện áp dụng của MỘT phần tử — *"vế này áp dụng khi nào"*.

    Khác `connector` (`all`/`any`) vốn trả lời *"các vế **kết hợp** thế nào"*. Trộn hai
    câu hỏi vào một enum là đúng loại mơ hồ im lặng mà `menh_de` đã phải tách khỏi
    `action`: *"(i) … đối với khách hàng là **cá nhân**; (ii) … đối với khách hàng là
    **tổ chức**"* không phải `any` (không được chọn bừa một vế) mà cũng không phải
    `all` — hai vế **loại trừ nhau theo loại chủ thể**.

    Khác `Gate` ở **đối tượng bị chặn**: `Gate` chặn theo *bên bị ràng buộc* (mức
    meta-CU, ai phải tuân thủ), guard chặn theo *thuộc tính của đối tượng hành vi*
    (mức phần tử, quy tắc này nói về loại gì). Hai nghĩa ⇒ hai kiểu, không tái dùng.

    **Do PARSER sinh 100%, không hỏi LLM** — cùng kỷ luật với `DieuKienCong` (mốc ngày)
    và `tiet_logic` (và/hoặc): thứ gì regex bắt được thì không đưa cho mô hình, vì mỗi
    ô hỏi thêm là một ô có thể bị lấp bừa.

    `thuoc_tinh`/`gia_tri` cố ý là **chuỗi tự do, không chuẩn hoá**: đo trên 18 fixture
    đã thấy ít nhất ba họ (`khách hàng` · `tài khoản thanh toán` · `thẻ`), enum sẽ phải
    nới liên tục. Chuẩn hoá về từ vựng có kiểm soát là việc của bước **nạp KG** qua
    `KhaiNiem`, không phải của tầng trích.
    """

    thuoc_tinh: str  # "khách hàng", "tài khoản thanh toán", "thẻ"
    gia_tri: str  # "cá nhân", "tổ chức", "thẻ trả trước"
    raw_text: str  # nguyên văn cụm guard; PHẢI round-trip đúng char_span
    char_span: tuple[int, int]  # neo vào `dieu.text` như mọi span


class SubCondition(BaseModel):
    """Một tiết bên trong điều kiện. `char_span` neo vào `dieu.text` như mọi span."""

    marker: str  # "i", "ii"
    text: str
    char_span: tuple[int, int]
    # None = vô điều kiện (đa số). Guard hiệu lực của tiết = AND của guard tại tiết và
    # guard tại Điểm chứa nó — xem `hop_guard()` trong parser.py.
    ap_dung_khi: GuardApDung | None = None


class ConditionItem(BaseModel):
    """Một điều kiện — thường ứng với một Điểm con của Khoản."""

    # "b"; None nếu Khoản không chẻ Điểm. Suy ra TẤT ĐỊNH từ nhãn điểm mà parser đã dán
    # lên các đơn vị mô hình chọn (`Unit.source_diem`), KHÔNG lấy lời khai của LLM —
    # xem `extractor._suy_diem`.
    source_diem: str | None
    text: str  # chữ của luật tại span
    object_label: str = ""
    constraint_label: str = ""
    grounding: Grounding
    # Các tiết bên trong điều kiện này và cách chúng kết hợp. Suy ra TẤT ĐỊNH từ
    # parser (dấu "hoặc"/"và" ở đuôi câu), KHÔNG hỏi LLM.
    logic: Literal["all", "any", "unknown"] = "unknown"
    sub: list[SubCondition] = Field(default_factory=list)
    # None = vô điều kiện. Guard ở tầng này phủ mọi tiết bên trong (AND dọc đường đi).
    ap_dung_khi: GuardApDung | None = None
    # Không rỗng ⇒ guard của các tiết PHỦ TRỌN miền giá trị này (đã đối chiếu
    # `data/phan_hoach.json`), nên `logic` dù là "unknown" cũng KHÔNG ảnh hưởng kết quả:
    # đúng một tiết áp dụng với mọi tình huống. Đây là chứng cứ, không phải suy diễn —
    # `connector` vẫn giữ nguyên. Xem `app/ontology/phan_hoach.py`.
    guard_phan_hoach: str | None = None
    issues: list[str] = Field(default_factory=list)


class Gate(BaseModel):
    """Phạm vi chặn cổng của một meta-CU.

    Bài báo GraphCompliance định nghĩa meta-CU là điều kiện áp dụng phạm vi rộng
    nhưng KHÔNG công bố listing JSON nào cho nó (chỉ có ví dụ actor-CU, Article 37
    GDPR) — thiết kế trường này là suy diễn theo đúng ngữ nghĩa "gate cho nhiều
    actor-CU, bản thân không tự bị vi phạm".

    Vì sao không dùng `gates: list[str]` phẳng như bản phác thảo đầu:

    1. "Toàn văn bản" mà liệt kê ra thì ND52 phải ghi 267 khoá node, và danh sách
       đó **sai ngay** khi văn bản được sửa đổi bổ sung thêm điều. `pham_vi="van_ban"`
       + `targets=[]` diễn đạt đúng ý "phủ tất cả" mà không phải đếm.
    2. "Quy định tại Mục này…" thì parser hiện KHÔNG giải được: cây chỉ có
       Điều→Khoản→Điểm, không có node Chương/Mục. Với list phẳng thì phải trả `[]` —
       không phân biệt được với "không chặn gì cả". `suy_ra_duoc=False` nói thẳng
       "có phạm vi nhưng chưa quy được về khoá node".
    """

    kind: Literal["thoi_gian", "chu_the", "lanh_tho", "khac"]
    # Cấp phủ của cổng. "van_ban" = cả văn bản; "muc"/"chuong" hiện chưa có node
    # tương ứng trong parser nên luôn đi kèm suy_ra_duoc=False.
    pham_vi: Literal["van_ban", "chuong", "muc", "dieu", "khoan"]
    targets: list[str] = Field(default_factory=list)  # khoá node; rỗng = phủ cả cấp
    suy_ra_duoc: bool = False
    # Cực của cổng. "Quy định tại khoản 1 Điều này KHÔNG áp dụng đối với…" (TT40
    # Điều 26 khoản 2, có thật) là LOẠI TRỪ; đọc nhầm cực là đảo ngược hiệu lực.
    phu_dinh: bool = False
    # "…có hiệu lực từ ngày X, TRỪ TRƯỜNG HỢP quy định tại khoản 2…" — các đơn vị
    # bị khoét khỏi phạm vi. Khác `targets` (phạm vi phủ) nên phải để riêng.
    ngoai_tru: list[str] = Field(default_factory=list)
    ghi_chu: str = ""


class DieuKienCong(BaseModel):
    """Θ của một meta-CU, ở dạng CÓ CẤU TRÚC — thay vì chữ tự do trong `action`.

    Giữ nguyên schema 4-tuple, KHÔNG tách meta-CU ra một schema riêng. Tiền lệ nằm
    ngay trong Listing 1 của GraphCompliance: `condition` ở đó là object lồng
    (`{"any": [...]}`), không phải chuỗi phẳng. Ở đây nội dung của object đổi theo
    `Gate.kind` — cùng một ô, hình dạng khác nhau tuỳ loại cổng.

    `char_span` do REGEX của ta tính trên `khoan.text` rồi quy về `dieu.text`, KHÔNG
    hỏi LLM. Nhờ vậy yêu cầu "span không lan sang phần câu khác của cùng khoản" đúng
    THEO CẤU TRÚC, chứ không nhờ một phép validate chạy sau — mà một phép validate
    chạy sau cũng không bắt được gì, vì `resolve()` trả bao lồi nên span luôn liền mạch.
    """

    # Mới chỉ có `thoi_gian`. Corpus 16 fixture KHÔNG có một mệnh đề lãnh thổ nào và
    # `detect_gate` chưa bao giờ phát ra `lanh_tho` ⇒ dựng trường cho nó bây giờ là
    # thiết kế không có dữ liệu. Nới `Literal` khi gặp case thật là sửa một dòng.
    kind: Literal["thoi_gian"]
    ngay: str | None = None  # ISO "2024-08-15"; None = không có/không đọc được ngày
    # KHÔNG gộp thành một trường tên "ngay_hieu_luc": TT40 Điều 52 khoản 6 điểm a/b
    # viết *"có hiệu lực thi hành ĐẾN HẾT ngày 14 tháng 8 năm 2024"* — đó là mốc KẾT
    # THÚC. Nhét ngày kết thúc vào ô đọc ra là "ngày bắt đầu có hiệu lực" là đảo ngược
    # ngữ nghĩa trong im lặng, đúng loại lỗi mà `Gate.phu_dinh` đã sinh ra để chặn.
    moc: Literal["bat_dau", "ket_thuc"] = "bat_dau"
    raw_text: str = ""
    char_span: tuple[int, int] | None = None
    ghi_chu: str = ""


class PremiseRecord(BaseModel):
    """Một đơn vị PREMISE trong sổ đăng ký (registry) — không sinh Compliance Unit.

    Gộp cả hai loại chất liệu phi-deontic mà GraphCompliance xếp vào premise:
    định nghĩa thuật ngữ (`dinh_nghia`), phát biểu phạm vi (`pham_vi`), và khai báo
    vai trò chủ thể (`vai_tro` — các khoản của "Đối tượng áp dụng").

    `raw_text` là lát cắt `dieu.text[char_span]`, không phải chữ mô hình viết.
    """

    id: str  # 52/2024/NĐ-CP#than/dieu_2#khoan_4
    type: Literal["premise"] = "premise"
    premise_kind: Literal["dinh_nghia", "pham_vi", "vai_tro"]
    raw_text: str
    char_span: tuple[int, int]
    # "(sau đây gọi là khách hàng)" → alias="khách hàng". Trích TẤT ĐỊNH bằng regex,
    # không hỏi LLM: đây là bí danh do chính văn bản tuyên bố, đoán là sai.
    alias: str | None = None
    alias_span: tuple[int, int] | None = None
    # Khai báo vai trò góp vào cổng chủ thể của Điều nào ("Đối tượng áp dụng").
    # Không phải bản thân nó là cổng — nó là một phần tử của tập chủ thể được phủ.
    gop_vao_gate: str | None = None
    warnings: list[str] = Field(default_factory=list)


class KhaiNiem(BaseModel):
    """Một thuật ngữ được định nghĩa — tầng PREMISE, mức Khoản.

    Premise là *"non-deontic definitional or interpretive material"* của
    GraphCompliance: không đặt ra nghĩa vụ. Điều "Giải thích từ ngữ" mỗi khoản là
    một thuật ngữ, nên gán ở mức Khoản để đổ thẳng vào node `KhaiNiem` mà KG v0.5
    đã thiết kế.

    Sửa 16/08 (T26 nhóm 2): định nghĩa ĐƯỢC đưa vào judge — không phải như nghĩa
    vụ, mà để đối chiếu CÁCH hợp đồng dùng/định nghĩa thuật ngữ với định nghĩa
    luật (2 miss gold #13/#35 đều là comment viện dẫn điều định nghĩa). Verdict
    mang id khái niệm để recall khớp tiền tố văn bản như CU thường.

    Giữ nguyên kỷ luật span: `thuat_ngu`/`dinh_nghia` là lát cắt `dieu.text`,
    không phải chữ LLM viết.
    """

    id: str  # 52/2024/NĐ-CP#than/dieu_3#khoan_1
    thuat_ngu: str
    dinh_nghia: str
    char_span_thuat_ngu: tuple[int, int] | None
    char_span_dinh_nghia: tuple[int, int] | None
    warnings: list[str] = Field(default_factory=list)


class GroundedUnit(BaseModel):
    """Phần chung của mọi đơn vị đã neo — tầng BẰNG CHỨNG, không phải ngữ nghĩa tuân thủ.

    Cố ý tách khỏi 4-tuple: `references`/`warnings`/`errors` là sổ ghi *"chữ này lấy
    ở đâu ra, có tin được không"*. Bài báo không đếm chúng vì không làm tầng này.
    """

    id: str  # 52/2024/NĐ-CP#than/dieu_22#khoan_2
    # Khoá node đích của các viện dẫn trong Khoản này, giải bằng citation.py.
    references: list[str] = Field(default_factory=list)
    # Có viện dẫn đi tới cấp tiết `(i)` mà khoá node không tới được — tiết cố ý
    # không có địa chỉ, nhưng sự mất mát phải hiện ra chứ không im lặng.
    references_hep_hon: bool = False
    warnings: list[str] = Field(default_factory=list)
    # Lỗi cứng (bịa nghĩa vụ/cấm đoán/số liệu, mất provenance) — bản ghi KHÔNG
    # được dùng ở downstream khi danh sách này không rỗng.
    errors: list[str] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


class ActorCU(GroundedUnit):
    """Nghĩa vụ nhắm vào một chủ thể — đơn vị DUY NHẤT bị đem ra phán định tuân thủ.

    Đơn vị trích xuất = 1 KHOẢN (không phải 1 Điểm). Điểm thường lược bỏ chủ ngữ vì
    là mệnh đề tiếp nối câu bao trùm (chapeau) của Khoản, nên trích Subject/Action
    riêng cho từng Điểm sẽ khiến LLM đoán bừa chủ ngữ. Mỗi Điểm thành một phần tử
    trong `conditions`.

    KHÔNG có `gates`/`dieu_kien_cong`: actor-CU không chặn cổng cho ai cả.
    """

    type: Literal["actor_cu"] = "actor_cu"
    # BẮT BUỘC — khác hẳn meta-CU. Đo trên corpus: 40/40 actor-CU đều có. Một nghĩa
    # vụ không có bên bị ràng buộc thì không phán định tuân thủ được, nên vắng mặt ở
    # đây luôn là trích hỏng, không bao giờ là "không áp dụng".
    subject: GroundedField
    subject_source: Literal["explicit", "inherited"] = "explicit"
    action: GroundedField
    # Tương ứng condition {"all": [...]} / {"any": [...]} của GraphCompliance.
    logic: Literal["all", "any", "unknown"] = "unknown"
    conditions: list[ConditionItem] = Field(default_factory=list)
    # Tình thái + ngưỡng — GÁN TẤT ĐỊNH ở build_actor_cu từ text đã neo, không phải
    # lời khai của LLM. 6 nhãn VN thay cho must/must_not/may: "chỉ được…khi" và
    # miễn trừ nghĩa vụ bị 3 nhãn Tây đọc ngược nghĩa. Xem spec 2026-08-11.
    modality: Literal[
        "nghia_vu", "cam", "cho_phep", "chi_duoc", "mien_tru", "khong_ro"
    ] = "khong_ro"
    nguong: list[Nguong] = Field(default_factory=list)


class MetaCU(GroundedUnit):
    """Mệnh đề chặn cổng — được đánh giá TRƯỚC, không bao giờ tự bị vi phạm.

    **Vì sao tách khỏi `ActorCU` thay vì dùng chung 4-tuple.** Đo trên cả 9 meta-CU
    của corpus:

    - **9/9 không có bên bị ràng buộc.** 8 cái khai `subject=None`; cái thứ 9
      (TT40 Đ26 k2) có điền, nhưng điền *"Quy định tại khoản 1 Điều này"* — một **tập
      quy phạm**, không phải một bên có thể tuân thủ hay vi phạm. ⟨S⟩ của
      GraphCompliance là *bên bị ràng buộc*, nên đó cũng không phải ⟨S⟩.
    - **⟨A⟩ không phải hành vi.** Tám cổng thời gian có `action` là *"có hiệu lực thi
      hành"* (ba cái giống hệt nhau từng chữ) — đó là **trạng thái của quy phạm**,
      không phải việc ai đó phải làm. Vì thế trường ở đây tên `menh_de`, không phải
      `action`: để một ô mang hai nghĩa khác nhau tuỳ vai là đúng loại mơ hồ im lặng
      mà `suy_ra_duoc` đã phải sinh ra để cứu cho `targets`.
    - **Bài báo KHÔNG công bố listing nào cho meta-CU** (chỉ có một ví dụ actor-CU,
      Article 37 GDPR). Nên giữ chung 4-tuple ở đây không phải là trung thành với bài
      báo — không có gì để mà trung thành.
    - Sự tách biệt **vốn đã tồn tại**, chỉ là viết bằng 6 nhánh `if role ==` trong
      `extractor.py` thay vì bằng kiểu dữ liệu. Người đọc `pred.jsonl` không thấy nó.

    Tiền lệ trong chính dự án: `PremiseRecord` đã tách khỏi CU vì trộn chung khiến
    `run_eval` gặp bản ghi không có `subject_span` và **tính sai trong im lặng**.
    """

    type: Literal["meta_cu"] = "meta_cu"
    # Phạm vi chặn. Rỗng = chưa xác định được cổng ⇒ bản ghi chưa dùng được.
    gates: list[Gate] = Field(default_factory=list)
    # Θ của cổng ở dạng cấu trúc.
    #
    # Đánh đổi đã biết: `gates` là LIST còn trường này là số ít. Mốc ngày đặt ở đây
    # (thay vì trên `Gate`) đúng về ngữ nghĩa — `Gate` là *phạm vi*, đây là *phép thử*
    # — nhưng downstream phải join hai trường để biết "chặn cái gì, từ bao giờ". Giảm
    # nhẹ bằng cách dựng nó cùng chỗ với `Gate`, 1:1 với cổng nó thuộc về.
    dieu_kien_cong: DieuKienCong | None = None
    # Mệnh đề nêu hiệu lực/phạm vi, đã neo. KHÔNG phải hành vi — xem docstring.
    # Khi mô hình lỡ khai `subject`, đơn vị đó được GỘP vào đây: ở TT40 Đ26 k2 hai
    # span liền kề nhau ([346,375] + [376,397]) và ghép lại mới thành trọn mệnh đề
    # *"Quy định tại khoản 1 Điều này không áp dụng đối với"*.
    menh_de: GroundedField
    # Các đơn vị được liệt kê riêng trong mệnh đề. Với cổng `phu_dinh` đó là danh
    # sách được MIỄN (TT40 Đ26 k2); với cổng thời gian có Điểm đó là các mốc riêng
    # cho từng quy định (TT40 Đ52 k6). Cả hai đều là *điều kiện của cổng*, nên vẫn
    # gọi là `conditions`.
    logic: Literal["all", "any", "unknown"] = "unknown"
    conditions: list[ConditionItem] = Field(default_factory=list)


# Hợp nhất để chú kiểu ở chỗ nhận cả hai. `type` là trường phân biệt, cùng quy ước
# với `PremiseRecord.type`.
ComplianceUnit = ActorCU | MetaCU
