"""Bắc cầu **số hiệu → doc_id**, và sinh **node rỗng** cho đầu mút chưa có toàn văn.

Vì sao cần: nguồn chính thống khoá bằng **số hiệu** (`52/2024/NĐ-CP`) — lược đồ vbpl, dẫn
chiếu trong chính văn bản, mọi truy vấn của KG v0.5 — còn corpus khoá bằng `doc_id`
(`ND52-2024`). Không có cầu thì 35 cạnh đọc được từ vbpl **không tạo ra cạnh nào**, và tệ
hơn là không báo gì: `push_corpus` viết `MATCH (a:Document {doc_id}), (b:Document {doc_id})`
rồi mới `MERGE`, mà Cypher `MATCH` không khớp thì cả câu **im lặng không chạy**.

**Node rỗng.** 35 cạnh chạm 36 số hiệu, corpus chỉ có 6. Ba lối xử lý 30 đầu mút còn lại —
bỏ cạnh, để tồn đọng, hay dựng node rỗng — chọn lối thứ ba, vì lược đồ vbpl *chính là* mạng
tham chiếu vượt ra ngoài phần đã tải: bỏ đi thì mất luôn ca `BAI_BO` (§6.2 *khoảng trống lập
pháp*) vốn chỉ tồn tại ở đầu mút chưa tải. Dựng node rỗng biến "corpus còn thiếu gì" thành
thứ **truy vấn được** thay vì thứ phải nhớ.

**Cơ chế cập nhật khi có dữ liệu thật: SUY RA, không vá.** Node rỗng không bao giờ được ai
soạn — nó được *dẫn xuất* mỗi lần nạp, và điều kiện tồn tại của nó là "chưa văn bản nào trong
corpus nhận số hiệu này". Nên khi bạn crawl xong và đưa toàn văn vào corpus (kèm `so_hieu`),
lần nạp sau **tự** quy cạnh về `doc_id` thật và node rỗng biến mất — không có bước di trú,
không có trạng thái phải đồng bộ tay. Đường nạp không xoá-sạch thì dùng
`app.knowledge.graph.don_node_rong_da_co_toan_van()` cho cùng một kết quả.

Hai bất biến, và đều là chỗ dễ hỏng im lặng nên có test canh:

1. **Không đoán `doc_id`.** Node rỗng lấy chính số hiệu làm `doc_id`. Bịa một `doc_id` kiểu
   `ND16-2019` thì đến lúc crawl thật, văn bản có thể mang `doc_id` khác và sinh ra hai node
   cho một văn bản — đúng kiểu hỏng mà `HUONG_DAN` đã gây ra một lần.
2. **Trùng số hiệu là lỗi, không phải ca cần đoán.** Hai văn bản cùng số hiệu ⇒ báo ra và
   **không** ánh xạ, thay vì chọn bừa một cái.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.schemas import CorpusDocument, DocumentMeta, Relationship, VanBanRong
from app.core.so_hieu import phan_tich

#: Mã loại → nhãn `doc_type` mà corpus đang dùng. Chỉ để hiển thị; thiếu thì để `None`
#: chứ không đoán, vì `doc_type` sai còn khó thấy hơn `doc_type` trống.
LOAI_SANG_DOC_TYPE = {
    "NĐ": "Nghị định",
    "TT": "Thông tư",
    "TTLT": "Thông tư",
    "QĐ": "Quyết định",
    "CT": "Chỉ thị",
    "NQ": "Nghị quyết",
    "PL": "Pháp lệnh",
}


def bang_so_hieu(docs: list[DocumentMeta]) -> tuple[dict[str, str], list[str]]:
    """`{số hiệu: doc_id}` + cảnh báo. Văn bản không khai `so_hieu` thì đứng ngoài cầu."""
    bang: dict[str, str] = {}
    canh_bao: list[str] = []
    for d in docs:
        if not d.so_hieu:
            continue
        cu = bang.get(d.so_hieu)
        if cu and cu != d.doc_id:
            canh_bao.append(
                f"số hiệu {d.so_hieu!r} bị hai văn bản cùng nhận: {cu!r} và {d.doc_id!r} — "
                f"không bắc cầu số hiệu này cho tới khi sửa dữ liệu"
            )
            bang[d.so_hieu] = ""  # đánh dấu nhập nhằng, xử lý ở `_quy_mot_dau_mut`
            continue
        bang.setdefault(d.so_hieu, d.doc_id)
    return {k: v for k, v in bang.items() if v}, canh_bao


def _doc_type_tu_so_hieu(so_hieu: str) -> str | None:
    sh = phan_tich(so_hieu)
    if sh is None:
        return None
    if sh.khoa_qh:
        return "Luật"  # nhóm Quốc hội: Luật/Nghị quyết — nhãn thô, sẽ đúng lại khi có toàn văn
    return LOAI_SANG_DOC_TYPE.get(sh.loai or "")


def quy_ve_doc_id(
    rels: list[Relationship],
    docs: list[DocumentMeta],
    tieu_de: dict[str, str] | None = None,
) -> tuple[list[Relationship], list[VanBanRong], list[str]]:
    """Cạnh khoá-số-hiệu → cạnh khoá-`doc_id`, kèm node rỗng cho đầu mút chưa có toàn văn.

    Trả `(cạnh đã quy, node rỗng, cảnh báo)`. Đầu mút đã là `doc_id` sẵn có trong corpus thì
    giữ nguyên — nên hàm này chạy được trên corpus hiện tại mà không đổi gì.
    """
    bang, canh_bao = bang_so_hieu(docs)
    co_doc_id = {d.doc_id for d in docs}
    tieu_de = tieu_de or {}
    rong: dict[str, VanBanRong] = {}

    def quy(dau_mut: str) -> str:
        if dau_mut in bang:
            return bang[dau_mut]
        if dau_mut in co_doc_id:
            return dau_mut
        if phan_tich(dau_mut) is None:
            # Không phải số hiệu, cũng không có trong corpus — để nguyên và nói ra, chứ dựng
            # node rỗng cho một chuỗi chưa quy được về khoá là nhân bản cái sai.
            canh_bao.append(
                f"đầu mút {dau_mut!r} không có trong corpus và không đọc được thành số hiệu"
            )
            return dau_mut
        rong.setdefault(
            dau_mut,
            VanBanRong(
                so_hieu=dau_mut,
                title=tieu_de.get(dau_mut),
                doc_type=_doc_type_tu_so_hieu(dau_mut),
            ),
        )
        return dau_mut

    ra = [
        r.model_copy(update={"source_doc": quy(r.source_doc), "target_doc": quy(r.target_doc)})
        for r in rels
    ]
    return ra, sorted(rong.values(), key=lambda v: v.so_hieu), canh_bao


#: Thiếu văn bản này thì **hỏng cái gì** — nhỏ hơn là gấp hơn. Đây là thứ quyết thứ tự crawl,
#: không phải số cạnh: đo trên dữ liệu thật thì 30/30 đầu mút treo đều đúng **1 cạnh**, nên
#: xếp theo số cạnh là xếp theo một cột hằng số.
MUC_UU_TIEN: dict[str, int] = {
    # Nghĩa vụ có thể BIẾN MẤT mà không có văn bản kế nhiệm — ca §6.2 *khoảng trống lập pháp*.
    "BAI_BO": 0,
    "DINH_CHI_THI_HANH": 0,
    "TAM_NGUNG_HIEU_LUC": 0,
    # Nội dung đang áp dụng bị đổi.
    "THAY_THE": 1,
    "SUA_DOI_BO_SUNG": 1,
    "HOP_NHAT": 1,
    "DINH_CHINH": 1,
    # Thêm chi tiết cho thứ đã có.
    "QUY_DINH_CHI_TIET_HUONG_DAN": 2,
    "HUONG_DAN_AP_DUNG": 2,
    "GIAI_THICH": 2,
    # Chỉ là xuất xứ / tham chiếu.
    "CAN_CU": 3,
    "DAN_CHIEU": 3,
    "CONG_BO": 3,
}


class CanCrawl(BaseModel):
    """Một dòng trong danh sách cần crawl."""

    so_hieu: str
    title: str | None = None
    doc_type: str | None = None
    so_canh: int = 0
    #: `(mã quan hệ, vai)` — `vai` là vị trí của văn bản CHƯA CÓ trong cạnh.
    quan_he: list[tuple[str, str]] = Field(default_factory=list)
    uu_tien: int = 9


def thieu_toan_van(
    rels: list[Relationship],
    docs: list[DocumentMeta],
    tieu_de: dict[str, str] | None = None,
) -> list[CanCrawl]:
    """**Danh sách cần crawl, sinh từ dữ liệu** — thay cho câu "chắc còn thiếu vài văn bản".

    Xếp theo `MUC_UU_TIEN`: thiếu một văn bản `BAI_BO` làm hổng đúng ca kiểm chứng bắt buộc
    của v0.5, còn thiếu một văn bản `CAN_CU` thì chỉ mất phần xuất xứ.
    """
    _, rong, _ = quy_ve_doc_id(rels, docs, tieu_de)
    theo_sh = {v.so_hieu: v for v in rong}
    gom: dict[str, CanCrawl] = {
        sh: CanCrawl(so_hieu=sh, title=v.title, doc_type=v.doc_type) for sh, v in theo_sh.items()
    }
    for r in rels:
        for dau_mut, vai in ((r.source_doc, "nguồn"), (r.target_doc, "đích")):
            d = gom.get(dau_mut)
            if d is None:
                continue
            d.so_canh += 1
            if (r.rel_type, vai) not in d.quan_he:
                d.quan_he.append((r.rel_type, vai))
            d.uu_tien = min(d.uu_tien, MUC_UU_TIEN.get(r.rel_type, 9))
    return sorted(gom.values(), key=lambda d: (d.uu_tien, -d.so_canh, d.so_hieu))


def tach_rong(docs: list[CorpusDocument]) -> list[CorpusDocument]:
    """Chỉ giữ văn bản CÓ toàn văn — dùng ở đường ingest chunk/embedding."""
    return [d for d in docs if d.articles]
