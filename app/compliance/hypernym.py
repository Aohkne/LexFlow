"""Map entity hợp đồng → thuật ngữ luật, dùng chính Policy Graph làm từ vựng H.

Đúng paper §3.2 (policy-guided normalization) nhưng thu nhỏ: 36 KhaiNiem + alias
premise → ~40 vector, cosine in-memory là đủ, không cần LanceDB. LLM chỉ XÁC NHẬN
trong danh sách ứng viên đóng — trả tên ngoài danh sách coi như không map.
"""
from __future__ import annotations

import math
import re

from pydantic import BaseModel

from app.core.llm import chat_json, embed_documents, embed_query

_SYSTEM = (
    "Cho một cụm từ trong hợp đồng và các thuật ngữ pháp lý ứng viên (kèm định nghĩa). "
    "Chọn thuật ngữ bao trùm đúng cụm từ đó, hoặc trả null nếu không cái nào đúng. "
    'Chỉ trả JSON: {"hypernym": "<thuật ngữ hoặc null>", "do_tin": 0.0-1.0}'
)


class DeXuat(BaseModel):
    entity: str
    hypernym: str
    do_tin: float
    manh: bool  # True = chống lưng bằng premise/khái niệm (STRONG của paper)


def _bo_so_khoan(s: str) -> str:
    """Bỏ số thứ tự khoản đầu raw_text ("21. Đơn vị…" → "Đơn vị…")."""
    return re.sub(r"^\d+[.)]\s*", "", s or "")


#: Văn bản luật VN tự khai báo viết tắt: "X (sau đây gọi tắt là Y)". IGNORECASE
#: theo lệ grep văn bản pháp lý (đầu câu viết hoa).
_ALIAS_RE = re.compile(
    r"\((?:sau đây\s+)?(?:gọi(?:\s+tắt)?\s+là|viết tắt là)\s+([^)]{2,60})\)",
    re.IGNORECASE,
)


def alias_tu_corpus(docs) -> list[tuple[str, str, bool]]:
    """Cặp (viết tắt/tên gọi tắt, dạng đầy đủ) khai báo NGAY TRONG văn bản luật.

    Bổ khuyết cho alias premise: mẫu "(sau đây gọi tắt là X)" xuất hiện cả NGOÀI
    điều giải-thích-từ-ngữ (28 chỗ trong corpus, đo 18/08 — "Bộ tiêu chí",
    "Ngân hàng Nhà nước"…) nên premise extraction không quét tới. Tất định,
    không LLM. Dạng đầy đủ = cụm đứng ngay trước ngoặc, cắt ở ranh câu/khoản.
    """
    ra: list[tuple[str, str, bool]] = []
    thay: set[str] = set()
    for doc in docs:
        for art in doc.articles:
            for m in _ALIAS_RE.finditer(art.text):
                alias = " ".join(m.group(1).split())
                if not alias or alias.lower() in thay:
                    continue
                truoc = art.text[max(0, m.start() - 120):m.start()]
                day_du = re.split(r"[.;:\n]", truoc)[-1]
                day_du = re.sub(r"^\s*[0-9a-zđ]{1,3}\)\s*", "", day_du).strip(" ,–-")
                if len(day_du.split()) < 2:
                    continue
                thay.add(alias.lower())
                ra.append((alias, day_du, True))
    return ra


def _cosine(a: list[float], b: list[float]) -> float:
    tich = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return tich / (na * nb) if na and nb else 0.0


class TuVungLuat:
    def __init__(self, muc: list[tuple[str, str, bool]], vec: list[list[float]]):
        self._muc = muc  # (thuật ngữ, định nghĩa, manh)
        self._vec = vec

    @classmethod
    def tu_policy_graph(cls, pg, embed=embed_documents, them=()) -> "TuVungLuat":
        muc = [(k.thuat_ngu, k.dinh_nghia, True) for k in pg.khai_niem]
        # alias kèm raw_text làm định nghĩa — alias trần thì vector vô nghĩa và
        # LLM xác nhận mù ("Ngân hàng"→ĐVCNT 0.9, đo 18/08).
        muc += [
            (p.alias, _bo_so_khoan(p.raw_text), True)
            for p in pg.premise if getattr(p, "alias", None)
        ]
        da_co = {t.lower() for t, _, _ in muc}
        muc += [(t, d, m) for t, d, m in them if t.lower() not in da_co]
        vec = embed([f"{t}: {d}" if d else t for t, d, _ in muc]) if muc else []
        return cls(muc, vec)

    def ung_vien(self, entity_vec: list[float], top_m: int = 3):
        diem = sorted(
            ((_cosine(entity_vec, v), m) for v, m in zip(self._vec, self._muc)),
            key=lambda x: -x[0],
        )
        return [m for _, m in diem[:top_m]]


def map_hypernym(
    entities: list[str], tv: TuVungLuat, nguong_tin: float = 0.5
) -> dict[str, DeXuat | None]:
    ra: dict[str, DeXuat | None] = {}
    for e in entities:
        uv = tv.ung_vien(embed_query(e))
        if not uv:
            ra[e] = None
            continue
        listing = "\n".join(f"- {t}" + (f": {d}" if d else "") for t, d, _ in uv)
        data = chat_json(
            f"Cụm từ trong hợp đồng: {e!r}\nỨng viên:\n{listing}",
            system=_SYSTEM, temperature=0.0,
        )
        ten = data.get("hypernym")
        tin = float(data.get("do_tin") or 0)
        khop = next((m for m in uv if m[0] == ten), None)
        ra[e] = (
            DeXuat(entity=e, hypernym=ten, do_tin=tin, manh=khop[2])
            if khop and tin >= nguong_tin else None
        )
    return ra
