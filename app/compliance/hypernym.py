"""Map entity hợp đồng → thuật ngữ luật, dùng chính Policy Graph làm từ vựng H.

Đúng paper §3.2 (policy-guided normalization) nhưng thu nhỏ: 36 KhaiNiem + alias
premise → ~40 vector, cosine in-memory là đủ, không cần LanceDB. LLM chỉ XÁC NHẬN
trong danh sách ứng viên đóng — trả tên ngoài danh sách coi như không map.
"""
from __future__ import annotations

import math

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


def _cosine(a: list[float], b: list[float]) -> float:
    tich = sum(x * y for x, y in zip(a, b))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return tich / (na * nb) if na and nb else 0.0


class TuVungLuat:
    def __init__(self, muc: list[tuple[str, str, bool]], vec: list[list[float]]):
        self._muc = muc  # (thuật ngữ, định nghĩa, manh)
        self._vec = vec

    @classmethod
    def tu_policy_graph(cls, pg, embed=embed_documents) -> "TuVungLuat":
        muc = [(k.thuat_ngu, k.dinh_nghia, True) for k in pg.khai_niem]
        muc += [(p.alias, "", True) for p in pg.premise if getattr(p, "alias", "")]
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
