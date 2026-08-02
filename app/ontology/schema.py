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


class SubCondition(BaseModel):
    """Một tiết bên trong điều kiện. `char_span` neo vào `dieu.text` như mọi span."""

    marker: str  # "i", "ii"
    text: str
    char_span: tuple[int, int]


class ConditionItem(BaseModel):
    """Một điều kiện — thường ứng với một Điểm con của Khoản."""

    source_diem: str | None  # "b"; None nếu Khoản không chẻ Điểm
    text: str  # chữ của luật tại span
    object_label: str = ""
    constraint_label: str = ""
    grounding: Grounding
    # Các tiết bên trong điều kiện này và cách chúng kết hợp. Suy ra TẤT ĐỊNH từ
    # parser (dấu "hoặc"/"và" ở đuôi câu), KHÔNG hỏi LLM.
    logic: Literal["all", "any", "unknown"] = "unknown"
    sub: list[SubCondition] = Field(default_factory=list)
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
    GraphCompliance: không đặt ra nghĩa vụ, không bị đem ra phán định tuân thủ.
    Điều "Giải thích từ ngữ" mỗi khoản là một thuật ngữ, nên gán ở mức Khoản để
    đổ thẳng vào node `KhaiNiem` mà KG v0.5 đã thiết kế.

    Giữ nguyên kỷ luật span: `thuat_ngu`/`dinh_nghia` là lát cắt `dieu.text`,
    không phải chữ LLM viết.
    """

    id: str  # 52/2024/NĐ-CP#than/dieu_3#khoan_1
    thuat_ngu: str
    dinh_nghia: str
    char_span_thuat_ngu: tuple[int, int] | None
    char_span_dinh_nghia: tuple[int, int] | None
    warnings: list[str] = Field(default_factory=list)


class ComplianceUnit(BaseModel):
    """Đơn vị trích xuất = 1 KHOẢN (không phải 1 Điểm).

    Điểm thường lược bỏ chủ ngữ vì là mệnh đề tiếp nối câu bao trùm (chapeau)
    của Khoản, nên trích Subject/Action riêng cho từng Điểm sẽ khiến LLM đoán
    bừa chủ ngữ. Mỗi Điểm trở thành một phần tử trong `conditions`.
    """

    id: str  # 52/2024/NĐ-CP#than/dieu_22#khoan_2
    # actor_cu = nghĩa vụ nhắm vào chủ thể; meta_cu = nêu phạm vi áp dụng, được
    # đánh giá TRƯỚC và không bao giờ báo vi phạm độc lập. Điều `premise` không
    # sinh ComplianceUnit — nó ra `KhaiNiem`.
    role: Literal["actor_cu", "meta_cu"] = "actor_cu"
    # Chỉ có nghĩa khi role == "meta_cu": cổng này phủ tới đâu. actor-CU luôn rỗng.
    gates: list[Gate] = Field(default_factory=list)
    # Θ của cổng ở dạng cấu trúc. Tên `dieu_kien_cong` chứ không phải `condition` vì
    # model đã có `conditions` (số nhiều, mỗi Điểm một phần tử) — để hai cái tên chỉ
    # khác một chữ 's' cạnh nhau là bẫy gõ nhầm im lặng, mà `run_eval.py`,
    # `make_gold_seed.py`, `review_ui.py` đều đang đọc `conditions`.
    #
    # Đánh đổi đã biết: `gates` là LIST còn trường này là số ít. Mốc ngày đặt ở đây
    # (thay vì trên `Gate`) đúng về ngữ nghĩa — `Gate` là *phạm vi*, đây là *phép thử*
    # — nhưng downstream phải join hai trường để biết "chặn cái gì, từ bao giờ". Giảm
    # nhẹ bằng cách dựng nó cùng chỗ với `Gate`, 1:1 với cổng nó thuộc về.
    dieu_kien_cong: DieuKienCong | None = None
    # `None` = **KHÔNG ÁP DỤNG**, không phải "chưa trích được".
    #
    # Cổng thời gian/lãnh thổ không có bên bị ràng buộc: *"Nghị định này có hiệu lực
    # thi hành từ ngày 01/7/2024"* có chủ ngữ NGỮ PHÁP ("Nghị định này") nhưng không
    # có **tác nhân** nào để mà tuân thủ hay vi phạm. ⟨S⟩ của GraphCompliance là bên
    # bị ràng buộc, không phải chủ ngữ của câu.
    #
    # Tiền lệ ngay trong Listing 1 của bài báo: `"context": null` được chấp nhận là
    # hợp lệ khi trường không áp dụng. Đây là cùng một loại vắng mặt — vắng mặt về
    # CẤU TRÚC, khác hẳn vắng mặt do trích hỏng.
    #
    # Ranh giới: chỉ cổng `thoi_gian`/`lanh_tho` mới được null. Cổng `chu_the`
    # (role qualification, vd. *"…chỉ áp dụng đối với tổ chức đã được cấp Giấy
    # phép"*) CÓ một vai cần định danh ⇒ vẫn bắt buộc. Nới rộng hơn thế là để lọt
    # trích hỏng dưới vỏ "không áp dụng".
    subject: GroundedField | None = None
    subject_source: Literal["explicit", "inherited"] | None = None
    action: GroundedField
    # Tương ứng condition {"all": [...]} / {"any": [...]} của GraphCompliance.
    logic: Literal["all", "any", "unknown"]
    conditions: list[ConditionItem] = Field(default_factory=list)
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
