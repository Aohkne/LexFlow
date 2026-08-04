"""Pydantic models dùng chung giữa ingestion, knowledge, reasoning, api."""
from __future__ import annotations

from pydantic import BaseModel, Field

# --- Quan hệ đồ thị pháp lý ---
REL_TYPES = ["THAY_THE", "SUA_DOI", "HUONG_DAN", "DAN_CHIEU"]


class RelAnchor(BaseModel):
    """Neo mức điều: điều nào của văn bản nguồn tác động điều nào của văn bản đích."""

    source_article: str | None = None  # ví dụ "Điều 1" (trong văn bản sửa đổi)
    target_article: str | None = None  # ví dụ "Điều 9" (điều bị sửa đổi/thay thế)
    detail: str | None = None  # ví dụ "Sửa đổi khoản 2, khoản 7; bổ sung khoản 9-19"


class Relationship(BaseModel):
    """Cạnh trong knowledge graph giữa hai văn bản."""

    source_doc: str  # doc_id gốc
    target_doc: str  # doc_id đích
    rel_type: str  # một trong REL_TYPES
    valid_from: str | None = None  # ISO date; None = không rõ
    note: str | None = None
    # [] = quan hệ mức văn bản (như cũ); có phần tử = biết chi tiết mức điều
    anchors: list[RelAnchor] = Field(default_factory=list)


class SourceFile(BaseModel):
    """Một file bản gốc kèm theo văn bản (PDF scan, .doc, phụ lục...)."""

    ten: str  # tên file hiển thị
    kich_thuoc: str | None = None  # "10.79MB" — giữ chuỗi vì nguồn cho sẵn dạng này
    url: str | None = None  # None = biết có file nhưng chưa lấy được link tải


class DocumentMeta(BaseModel):
    """Metadata một văn bản pháp lý (hoặc tài liệu nội bộ).

    Nhóm thuộc tính và bản gốc bên dưới đều optional: corpus đã duyệt từ trước không có
    các trường này, thêm vào không được làm hỏng bản ghi cũ.
    """

    doc_id: str
    title: str
    doc_type: str  # Luật / Nghị định / Thông tư / Quyết định / Nội bộ
    source: str = "external"  # external (luật) | internal (nội bộ ngân hàng)
    valid_from: str | None = None  # ISO date ngày hiệu lực
    valid_to: str | None = None  # ISO date ngày hết hiệu lực; None = còn hiệu lực

    # --- Thuộc tính (khớp bảng Thuộc tính của vbpl.vn) ---
    so_hieu: str | None = None  # "15/2024/TT-NHNN"
    co_quan_ban_hanh: str | None = None
    nguoi_ky: str | None = None
    chuc_danh: str | None = None
    nganh: str | None = None
    linh_vuc: str | None = None
    ngay_ban_hanh: str | None = None  # ISO date
    tinh_trang_hieu_luc: str | None = None  # "Còn hiệu lực" | "Hết hiệu lực một phần" | ...

    # --- Bản gốc ---
    source_url: str | None = None  # trang gốc (vbpl.vn) để đối chiếu
    source_files: list[SourceFile] = Field(default_factory=list)  # file gốc đính kèm


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
    # Vị trí của `text` trong toàn văn nguồn: `noi_dung[char_start:char_end] == text`.
    # Cho phép phía sau neo trích dẫn ở mức ký tự về đúng bản gốc.
    char_start: int | None = None
    char_end: int | None = None


class Provision(BaseModel):
    """Một nút trong cây điều khoản (Chương → Mục → Điều → Khoản → Điểm).

    Song song với `articles` chứ không thay thế: `articles` vẫn là đơn vị chunk cho RAG,
    còn cây này để trình xem dựng lại đúng phân cấp và định dạng như nguồn.
    """

    id: str | None = None  # id gốc bên nguồn, giữ để đối chiếu khi crawl lại
    cap: str  # chuong | muc | dieu | khoan | diem
    so: str | None = None  # "I", "1", "a"
    tieu_de: str = ""  # tiêu đề Chương/Mục/Điều
    text: str = ""  # text thuần của Khoản/Điểm
    # HTML inline ĐÃ lọc whitelist (chỉ b/strong/i/em/u/sup/sub/br, không attribute).
    # Không bao giờ nhận HTML thô từ nguồn vào đây.
    html: str = ""
    bi_tac_dong: list[str] | None = None  # sua_doi_bo_sung | thay_the | bo_sung | ...
    an: bool = False
    con: list[Provision] = Field(default_factory=list)


class QuoteSpan(BaseModel):
    """Một khối trích dẫn trong `noi_dung`: `noi_dung[char_start:char_end]`, kể cả dấu ngoặc.

    Văn bản sửa đổi chép nguyên văn nội dung mới vào giữa hai dấu ngoặc kép, và phần chép mang
    ĐÁNH SỐ CỦA VĂN BẢN BỊ SỬA. Ai đọc `articles[].text` mà muốn tách đâu là điều khoản của
    văn bản này, đâu là đoạn trích, thì neo vào đây.
    """

    char_start: int
    char_end: int


class CorpusDocument(DocumentMeta):
    """Văn bản kèm danh sách điều khoản — đầu vào của ingest."""

    articles: list[Article] = Field(default_factory=list)
    provisions: list[Provision] = Field(default_factory=list)
    trich_dan: list[QuoteSpan] = Field(default_factory=list)
    # Nguồn có đăng toàn văn hay không. `False` = chỉ có thuộc tính/lược đồ (hay gặp ở văn
    # bản hợp nhất): `articles` rỗng vì KHÔNG CÓ, chứ không phải vì bóc hỏng.
    co_toan_van: bool = True
    canh_bao: list[str] = Field(default_factory=list)


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
    provisions: list[Provision] = Field(default_factory=list)  # [] = chưa crawl được cây
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


class GraphEdge(BaseModel):
    source: str
    target: str
    rel_type: str


class GraphData(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
