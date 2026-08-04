"""Pydantic models dùng chung giữa ingestion, knowledge, reasoning, api."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

# --- Quan hệ đồ thị pháp lý -------------------------------------------------
#
# TẬP ĐÓNG 13 quan hệ theo KG v0.5 §6. "Đóng" là điểm chính: bản trước để
# `REL_TYPES = ["THAY_THE", "SUA_DOI", "HUONG_DAN", "DAN_CHIEU"]` — bốn tên **tự đặt** —
# và `rel_type: str` **chưa bao giờ được đối chiếu với nó**. Hệ quả đo được: `HUONG_DAN`
# sống trong dữ liệu 4 lần dù đó không phải một quan hệ có thật trong hệ thống VBQPPL;
# nó gộp hai thứ mà Điều 53 khoản 2 đối xử khác nhau, và cả bốn cạnh đều gán sai. Một
# chuỗi tự do không có ai canh thì sai lặng lẽ và nhân lên.
#
# Cùng bảng đó từng bị CHÉP ở ba nơi (`schemas.py`, `answer.py`, `pipeline.py`) nên sửa
# một chỗ không kéo theo hai chỗ kia. Nay một nguồn sự thật duy nhất.
#
# Mỗi mục: mã → (nhãn đầu CHỦ ĐỘNG, nhãn đầu BỊ ĐỘNG). Chiều cạnh theo quy ước v0.5:
# văn bản chủ động / mới hơn → văn bản bị tác động / cũ hơn.
#
# 12/13 cặp theo khuôn `X` ⟷ `được X` hoặc `bị X`; `bị` (3 cạnh) đánh dấu **can thiệp
# bất lợi** (huỷ hoặc treo), `được` (9 cạnh) là **diễn biến bình thường**. Ranh giới KHÔNG
# phải "có chấm dứt hiệu lực hay không" — `thay thế` cũng chấm dứt nhưng mang `được`, vì
# nó là **kế thừa** chứ không phải **triệt tiêu**. Cặp #8 bất quy tắc, hai nhãn khác gốc từ.
REL_TYPES: dict[str, tuple[str, str]] = {
    "HUONG_DAN_AP_DUNG": ("hướng dẫn áp dụng", "được hướng dẫn áp dụng"),
    "QUY_DINH_CHI_TIET_HUONG_DAN": (
        "quy định chi tiết, hướng dẫn thi hành",
        "được quy định chi tiết, hướng dẫn thi hành",
    ),
    "HOP_NHAT": ("hợp nhất", "được hợp nhất"),
    "SUA_DOI_BO_SUNG": ("sửa đổi, bổ sung", "được sửa đổi, bổ sung"),
    "DINH_CHINH": ("đính chính", "được đính chính"),
    "BAI_BO": ("bãi bỏ", "bị bãi bỏ"),
    "DAN_CHIEU": ("dẫn chiếu", "được dẫn chiếu"),
    "CAN_CU": ("căn cứ ban hành", "áp dụng"),  # bất quy tắc
    "GIAI_THICH": ("giải thích", "được giải thích"),
    "DINH_CHI_THI_HANH": ("đình chỉ thi hành", "bị đình chỉ thi hành"),
    "TAM_NGUNG_HIEU_LUC": ("tạm ngưng hiệu lực", "bị tạm ngưng hiệu lực"),
    "CONG_BO": ("công bố", "được công bố"),
    "THAY_THE": ("thay thế", "được thay thế"),
}

#: Cạnh mang **can thiệp bất lợi** — huỷ bỏ hoặc treo hiệu lực.
REL_BAT_LOI = frozenset({"BAI_BO", "DINH_CHI_THI_HANH", "TAM_NGUNG_HIEU_LUC"})


def nhan_quan_he(rel_type: str, bi_dong: bool = False) -> str:
    """Mã quan hệ → nhãn tiếng Việt. Mã lạ trả về chính nó, để log còn đọc được."""
    cap = REL_TYPES.get(rel_type)
    return cap[1 if bi_dong else 0] if cap else rel_type


class RelAnchor(BaseModel):
    """Neo mức điều: điều nào của văn bản nguồn tác động điều nào của văn bản đích."""

    source_article: str | None = None  # ví dụ "Điều 1" (trong văn bản sửa đổi)
    target_article: str | None = None  # ví dụ "Điều 9" (điều bị sửa đổi/thay thế)
    detail: str | None = None  # ví dụ "Sửa đổi khoản 2, khoản 7; bổ sung khoản 9-19"


class Relationship(BaseModel):
    """Cạnh trong knowledge graph giữa hai văn bản."""

    source_doc: str  # doc_id gốc
    target_doc: str  # doc_id đích
    rel_type: str  # PHẢI thuộc REL_TYPES — xem validator bên dưới
    valid_from: str | None = None  # ISO date; None = không rõ
    note: str | None = None
    # [] = quan hệ mức văn bản (như cũ); có phần tử = biết chi tiết mức điều
    anchors: list[RelAnchor] = Field(default_factory=list)

    @field_validator("rel_type")
    @classmethod
    def _trong_tap_dong(cls, v: str) -> str:
        """Chặn tại BIÊN dữ liệu vào, không phải lúc truy vấn.

        Nêu đích danh mã sai **và** cả 13 mã hợp lệ: người sửa dữ liệu cần biết ngay
        phải điền gì, chứ không phải đi tra tài liệu. Đây là chỗ `HUONG_DAN` lẽ ra phải
        chết ngay lần nạp đầu tiên thay vì sống trong corpus.
        """
        if v not in REL_TYPES:
            raise ValueError(
                f"rel_type {v!r} không thuộc 13 quan hệ của KG v0.5. "
                f"Hợp lệ: {', '.join(sorted(REL_TYPES))}"
            )
        return v


class DocumentMeta(BaseModel):
    """Metadata một văn bản pháp lý (hoặc tài liệu nội bộ)."""

    doc_id: str
    title: str
    doc_type: str  # Luật / Nghị định / Thông tư / Quyết định / Nội bộ
    source: str = "external"  # external (luật) | internal (nội bộ ngân hàng)
    valid_from: str | None = None  # ISO date ngày hiệu lực
    valid_to: str | None = None  # ISO date ngày hết hiệu lực; None = còn hiệu lực
    #: Số hiệu công bố (`52/2024/NĐ-CP`) — trường **bắc cầu**, không phải danh tính.
    #: `doc_id` vẫn là khoá; đổi nó chạm hàng trăm chỗ và cả lịch sử Supabase. Nhưng nguồn
    #: chính thống (lược đồ vbpl, dẫn chiếu trong chính văn bản) khoá bằng SỐ HIỆU, nên không
    #: có trường này thì mọi cạnh đọc từ nguồn đều không quy về được node nào.
    so_hieu: str | None = None


class Article(BaseModel):
    """Một điều/khoản của văn bản (đơn vị chunk)."""

    article: str  # ví dụ "Điều 5" hoặc "Điều 5 Khoản 2"
    text: str
    # Cho phép override hiệu lực ở cấp điều khoản (partial supersession)
    valid_from: str | None = None
    valid_to: str | None = None
    superseded: bool = False
    # Nhãn phân cấp phẳng (không dựng cây) — hiển thị heading trong trình xem
    chapter: str | None = None  # ví dụ "Chương II. Mở và sử dụng tài khoản thanh toán"
    section: str | None = None  # ví dụ "Mục 1. Mở tài khoản"


class CorpusDocument(DocumentMeta):
    """Văn bản kèm danh sách điều khoản — đầu vào của ingest."""

    articles: list[Article] = Field(default_factory=list)


class VanBanRong(BaseModel):
    """Văn bản **biết là có** nhưng CHƯA có toàn văn — chỉ có số hiệu và chỗ nó nối vào.

    Cố ý KHÔNG kế thừa `DocumentMeta`: một `CorpusDocument` rỗng ruột trông y hệt một văn bản
    thật mà quên nhập điều khoản, nên sớm muộn cũng có chỗ đem nó đi trích dẫn. Kiểu riêng
    khiến mọi chỗ nhận nhầm hỏng **lúc dịch**, chứ không hỏng lúc người dùng đọc câu trả lời.

    `so_hieu` cũng là `doc_id` của node — xem `app.ingestion.bac_cau`: bịa một `doc_id` cho
    văn bản chưa đọc thì đến lúc crawl thật rất dễ thành hai node cho một văn bản.
    """

    so_hieu: str
    title: str | None = None
    doc_type: str | None = None


# --- API models ---
class DocumentSummary(BaseModel):
    """Một dòng trong thư viện văn bản (GET /documents)."""

    doc_id: str
    title: str
    doc_type: str
    source: str
    valid_from: str | None = None
    valid_to: str | None = None
    n_articles: int = 0
    status: str = "con_hieu_luc"  # con_hieu_luc | het_hieu_luc


class DocumentDetail(DocumentMeta):
    """Toàn văn + quan hệ hai chiều của một văn bản (GET /documents/{doc_id})."""

    articles: list[Article] = Field(default_factory=list)
    relationships_out: list[Relationship] = Field(default_factory=list)  # doc là source
    relationships_in: list[Relationship] = Field(default_factory=list)  # doc là target
    doc_titles: dict[str, str] = Field(default_factory=dict)  # doc_id -> title các doc liên quan


class Citation(BaseModel):
    doc_id: str
    doc_title: str
    doc_type: str
    article: str
    valid_from: str | None = None
    valid_to: str | None = None
    snippet: str


class ConflictAlert(BaseModel):
    doc_a: str
    doc_b: str
    article_a: str
    article_b: str
    explanation: str
    severity: str = "warning"  # info | warning | critical


class ChatRequest(BaseModel):
    query: str
    mode: str = "qa"  # qa | checklist
    as_of: str | None = None  # ISO date để tra cứu "tại thời điểm"; None = hôm nay
    top_k: int = 6
    session_id: str | None = None  # tiếp tục phiên hội thoại đã lưu; None = phiên mới
    # Phạm vi: giới hạn retrieval trong các văn bản này; [] = toàn bộ corpus
    doc_ids: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    conflicts: list[ConflictAlert] = Field(default_factory=list)
    session_id: str | None = None  # id phiên trên Supabase (None khi chưa cấu hình)


class ReviewRequest(BaseModel):
    """Kiểm tra tuân thủ: đối chiếu 1 tài liệu nội bộ với các văn bản pháp luật."""

    internal_doc_id: str
    # [] = tự chọn toàn bộ văn bản external đang hiệu lực tại as_of
    against_doc_ids: list[str] = Field(default_factory=list)
    as_of: str | None = None  # ISO date; None = hôm nay


class ReviewFinding(BaseModel):
    """Kết quả đối chiếu một điều nội bộ với căn cứ pháp lý."""

    # violation | warning | pass | not_assessed (không tìm thấy căn cứ để đối chiếu)
    verdict: str = "warning"
    article: str  # điều nội bộ, ví dụ "Điều 2"
    title: str
    summary: str = ""
    internal_quote: str = ""
    legal_doc_id: str | None = None
    legal_ref: str | None = None  # ví dụ "Thông tư 40/2024 — Điều 26"
    legal_quote: str | None = None
    legal_live: bool = True  # căn cứ còn hiệu lực tại as_of
    suggestion: str | None = None


class ReviewResponse(BaseModel):
    internal_doc_id: str
    internal_title: str
    as_of: str
    against_doc_ids: list[str] = Field(default_factory=list)
    # 0-100: pass=1, warning=0.5, violation=0 — trung bình trên các điều ĐÃ đối chiếu
    # (not_assessed loại khỏi mẫu số; không đối chiếu được điều nào → 0, UI hiện "—")
    score: int = 0
    counts: dict[str, int] = Field(default_factory=dict)  # violation/warning/pass/not_assessed
    findings: list[ReviewFinding] = Field(default_factory=list)
    session_id: str | None = None  # id trên Supabase (None khi chưa cấu hình/migration)


class GraphNode(BaseModel):
    id: str
    label: str
    doc_type: str
    valid_from: str | None = None
    valid_to: str | None = None
    #: `False` = **node rỗng**: biết văn bản này tồn tại và biết nó nối vào đâu, nhưng CHƯA có
    #: toàn văn. Phải phân biệt được ở tầng hiển thị lẫn tầng truy hồi — trích dẫn một node
    #: rỗng là trích dẫn thứ chưa đọc.
    co_toan_van: bool = True


class GraphEdge(BaseModel):
    source: str
    target: str
    rel_type: str


class GraphData(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
