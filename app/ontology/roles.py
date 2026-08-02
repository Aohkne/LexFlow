"""Phân loại vai của một Điều: premise · meta-CU · actor-CU.

Vì sao cần: pipeline trước đó mặc định **mọi Khoản đều là Compliance Unit**. Đo
trên corpus thì 40/278 điều (14.4%) không phải vậy — 24 điều định nghĩa/phạm vi,
16 điều hiệu lực. Chạy extractor lên Điều 3 "Giải thích từ ngữ" sẽ sinh
`subject="Dịch vụ thanh toán không dùng tiền mặt"`, `action="bao gồm…"` — một
"Compliance Unit" không phải nghĩa vụ gì cả.

Ba vai, theo GraphCompliance (arXiv:2510.26309):

- **premise** — chất liệu định nghĩa/diễn giải, *"not itself judged for
  (non)compliance"*. Ở ta đổ vào node `KhaiNiem` mà KG v0.5 đã thiết kế sẵn.
- **meta-CU** — nêu phạm vi áp dụng, **đánh giá trước**, không bao giờ báo vi phạm
  độc lập; chặn cổng xem actor-CU có áp dụng không.
- **actor-CU** — nghĩa vụ/cấm đoán/cho phép nhắm vào một chủ thể. Mặc định.

Ánh xạ sang cấu trúc văn bản QPPL Việt Nam là phần thiết kế riêng, không có trong
bài báo — xem `_TITLE_RULES`.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from app.ontology.schema import DieuNode

Role = Literal["premise", "meta_cu", "actor_cu"]
# Premise có hai loại rất khác nhau và chỉ MỘT loại sinh ra được node:
#   dinh_nghia — "Giải thích từ ngữ": mỗi khoản một thuật ngữ → KhaiNiem
#   pham_vi    — "Phạm vi điều chỉnh": phát biểu phạm vi, KHÔNG định nghĩa gì cả
# Gộp hai loại này khiến Điều 1 bị đem đi trích thuật ngữ và ra bản ghi rỗng.
PremiseKind = Literal["dinh_nghia", "pham_vi"]

# Bảng tiêu đề. Thứ tự QUAN TRỌNG: "trách nhiệm thi hành" phải đứng trước
# "thi hành", nếu không nó bị nuốt vào nhóm hiệu lực.
_TITLE_RULES: list[tuple[str, Role, str, PremiseKind | None]] = [
    # Giao nghĩa vụ thật cho cơ quan cụ thể ("Bộ trưởng… chịu trách nhiệm thi
    # hành") ⇒ actor-CU, KHÔNG phải meta. Khảo sát đầu tiên của tôi xếp nhầm nó
    # vào meta vì khớp chữ "thi hành" — ghi lại để không lặp.
    (r"trách nhiệm (thi hành|tổ chức thực hiện)", "actor_cu", "giao nghĩa vụ cho cơ quan", None),
    (r"phạm vi điều chỉnh", "premise", "scope statement", "pham_vi"),
    (r"giải thích (từ ngữ|thuật ngữ)", "premise", "định nghĩa thuật ngữ", "dinh_nghia"),
    (r"nguyên tắc chung", "premise", "nguyên tắc diễn giải", "pham_vi"),
    # "Đối tượng áp dụng" = role qualification → chặn cổng chủ thể ⇒ meta-CU.
    (r"đối tượng áp dụng", "meta_cu", "role qualification", None),
    (r"hiệu lực (thi hành|của)", "meta_cu", "phạm vi thời gian", None),
    (r"điều khoản chuyển tiếp", "meta_cu", "phạm vi thời gian", None),
    (r"quy định chuyển tiếp", "meta_cu", "phạm vi thời gian", None),
]
_COMPILED = [(re.compile(p, re.I), role, why, kind) for p, role, why, kind in _TITLE_RULES]

# Điều 1 của văn bản sửa đổi là "Sửa đổi, bổ sung một số điều của…" chứ không phải
# phạm vi điều chỉnh. Đo trên corpus: quy ước vị trí đúng 9/11 và 8/11, cả hai
# ngoại lệ đều là văn bản sửa đổi ⇒ phải nhận diện lớp này để TẮT luật vị trí.
_SUA_DOI_RE = re.compile(r"sửa đổi|bổ sung một số điều|thay thế một số điều", re.I)

# Quy ước vị trí (tri thức miền): Điều 1 phạm vi, Điều 2 đối tượng áp dụng.
_POSITION_RULES: dict[int, tuple[Role, str]] = {
    1: ("premise", "Điều 1 thường là phạm vi điều chỉnh"),
    2: ("meta_cu", "Điều 2 thường là đối tượng áp dụng"),
}

_SYSTEM = (
    "Bạn phân loại vai của một Điều trong văn bản quy phạm pháp luật Việt Nam. "
    "Trả đúng một trong ba giá trị:\n"
    "- premise: chất liệu định nghĩa/diễn giải (giải thích từ ngữ, phạm vi điều "
    "chỉnh, nguyên tắc). KHÔNG đặt ra nghĩa vụ cho ai, không bị đem ra phán định "
    "tuân thủ.\n"
    "- meta_cu: nêu điều kiện ÁP DỤNG của văn bản — đối tượng áp dụng, hiệu lực "
    "thời gian, điều khoản chuyển tiếp. Quyết định quy định có áp cho ai/khi nào, "
    "chứ bản thân không phải nghĩa vụ.\n"
    "- actor_cu: đặt ra nghĩa vụ, cấm đoán hoặc cho phép nhắm vào một chủ thể.\n"
    'Chỉ trả JSON: {"role": "...", "ly_do": "<một câu ngắn>"}'
)


class RoleVerdict(BaseModel):
    dieu_id: str
    role: Role
    nguon: Literal["tieu_de", "vi_tri", "llm", "mac_dinh"]
    ly_do: str = ""
    # Chỉ có nghĩa khi role == "premise". Chỉ `dinh_nghia` mới sinh KhaiNiem.
    premise_kind: PremiseKind | None = None
    warnings: list[str] = Field(default_factory=list)


def is_van_ban_sua_doi(tieu_de_dieu_1: str) -> bool:
    """Điều 1 mở đầu bằng "Sửa đổi, bổ sung…" ⇒ văn bản sửa đổi."""
    return bool(_SUA_DOI_RE.search(tieu_de_dieu_1))


def _by_title(tieu_de: str) -> tuple[Role, str, PremiseKind | None] | None:
    for pat, role, why, kind in _COMPILED:
        if pat.search(tieu_de):
            return role, why, kind
    return None


def title_rule(tieu_de: str) -> tuple[Role, str, PremiseKind | None] | None:
    """Luật tiêu đề dưới dạng công khai — tầng phân loại đơn vị dùng lại."""
    return _by_title(tieu_de)


def classify_dieu(
    dieu: DieuNode, *, van_ban_sua_doi: bool = False, allow_llm: bool = False
) -> RoleVerdict:
    """Phân loại một Điều. Tầng tất định trước, LLM chỉ cho phần dư.

    `van_ban_sua_doi=True` tắt luật vị trí — Điều 1/2 của văn bản sửa đổi không
    theo quy ước phạm vi/đối tượng.
    """
    warnings: list[str] = []
    by_title = _by_title(dieu.tieu_de)
    by_pos = None if van_ban_sua_doi else _POSITION_RULES.get(dieu.so_goc)
    if dieu.so_hau_to:  # "Điều 1a" là điều chèn thêm, không theo quy ước vị trí
        by_pos = None

    if by_title:
        role, why, kind = by_title
        if by_pos and by_pos[0] != role:
            # Đo được tiêu đề đúng hơn vị trí (9/11 vs 11/11 theo tiêu đề).
            warnings.append(
                f"tiêu đề cho {role!r} nhưng vị trí gợi ý {by_pos[0]!r} — lấy theo tiêu đề"
            )
        return RoleVerdict(dieu_id=dieu.id, role=role, nguon="tieu_de", ly_do=why,
                           premise_kind=kind, warnings=warnings)

    if by_pos:
        role, why = by_pos
        warnings.append("phân loại theo VỊ TRÍ vì tiêu đề không khớp khuôn nào — nên soi lại")
        return RoleVerdict(dieu_id=dieu.id, role=role, nguon="vi_tri", ly_do=why,
                           premise_kind="pham_vi" if role == "premise" else None,
                           warnings=warnings)

    if allow_llm:
        from app.core.llm import chat_json

        data = chat_json(
            f"Điều {dieu.so_hien_thi}. {dieu.tieu_de}\n\n{dieu.text[:3000]}",
            system=_SYSTEM, reasoning=False, temperature=0.0,
        )
        role = data.get("role")
        if role in {"premise", "meta_cu", "actor_cu"}:
            return RoleVerdict(dieu_id=dieu.id, role=role, nguon="llm",
                               ly_do=(data.get("ly_do") or "")[:120],
                               premise_kind="pham_vi" if role == "premise" else None,
                               warnings=warnings)
        warnings.append(f"LLM trả vai không hợp lệ ({role!r}) — về mặc định actor_cu")

    return RoleVerdict(dieu_id=dieu.id, role="actor_cu", nguon="mac_dinh",
                       ly_do="không khớp khuôn nào", warnings=warnings)


def classify_document(dieu_list: list[DieuNode], *, allow_llm: bool = False) -> list[RoleVerdict]:
    """Phân loại cả văn bản — cần cả tập để biết có phải văn bản sửa đổi không."""
    dieu_1 = next((d for d in dieu_list if d.so_goc == 1 and not d.so_hau_to), None)
    sua_doi = is_van_ban_sua_doi(dieu_1.tieu_de) if dieu_1 else False
    return [
        classify_dieu(d, van_ban_sua_doi=sua_doi, allow_llm=allow_llm) for d in dieu_list
    ]
