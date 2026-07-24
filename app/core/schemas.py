"""Pydantic models dùng chung giữa ingestion, knowledge, reasoning, api."""
from __future__ import annotations

from pydantic import BaseModel, Field

# --- Quan hệ đồ thị pháp lý ---
REL_TYPES = ["THAY_THE", "SUA_DOI", "HUONG_DAN", "DAN_CHIEU"]


class Relationship(BaseModel):
    """Cạnh trong knowledge graph giữa hai văn bản."""

    source_doc: str  # doc_id gốc
    target_doc: str  # doc_id đích
    rel_type: str  # một trong REL_TYPES
    valid_from: str | None = None  # ISO date; None = không rõ
    note: str | None = None


class DocumentMeta(BaseModel):
    """Metadata một văn bản pháp lý (hoặc tài liệu nội bộ)."""

    doc_id: str
    title: str
    doc_type: str  # Luật / Nghị định / Thông tư / Quyết định / Nội bộ
    source: str = "external"  # external (luật) | internal (nội bộ ngân hàng)
    valid_from: str | None = None  # ISO date ngày hiệu lực
    valid_to: str | None = None  # ISO date ngày hết hiệu lực; None = còn hiệu lực


class Article(BaseModel):
    """Một điều/khoản của văn bản (đơn vị chunk)."""

    article: str  # ví dụ "Điều 5" hoặc "Điều 5 Khoản 2"
    text: str
    # Cho phép override hiệu lực ở cấp điều khoản (partial supersession)
    valid_from: str | None = None
    valid_to: str | None = None
    superseded: bool = False


class CorpusDocument(DocumentMeta):
    """Văn bản kèm danh sách điều khoản — đầu vào của ingest."""

    articles: list[Article] = Field(default_factory=list)


# --- API models ---
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


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    conflicts: list[ConflictAlert] = Field(default_factory=list)
    session_id: str | None = None  # id phiên trên Supabase (None khi chưa cấu hình)


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
