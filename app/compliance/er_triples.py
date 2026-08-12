"""Trích (chủ thể, hành vi, đối tượng) từ MỘT điều hợp đồng — LLM, temp 0.

Kỷ luật chống bịa như extractor: chủ thể/đối tượng phải nằm NGUYÊN VĂN trong
text (so không phân biệt hoa thường); không thì bỏ triple + cảnh báo. `hanh_vi`
được diễn giải tự do (động từ thường bị biến đổi ngữ pháp) — không kiểm.
"""
from __future__ import annotations

from pydantic import BaseModel

from app.core.llm import chat_json

_SYSTEM = (
    "Trích các bộ ba (chủ thể, hành vi, đối tượng) từ một điều khoản hợp đồng "
    "tiếng Việt. Chủ thể và đối tượng phải CHÉP NGUYÊN VĂN cụm từ trong điều khoản, "
    "không viết lại. Chỉ trả JSON: "
    '{"triples": [{"chu_the": "...", "hanh_vi": "...", "doi_tuong": "..."}]}'
)


class Triple(BaseModel):
    chu_the: str
    hanh_vi: str
    doi_tuong: str


def trich_triples(text: str) -> tuple[list[Triple], list[str]]:
    data = chat_json(f"Điều khoản:\n{text}", system=_SYSTEM, temperature=0.0)
    low = text.lower()
    ra: list[Triple] = []
    canh_bao: list[str] = []
    for raw in data.get("triples") or []:
        try:
            t = Triple.model_validate(raw)
        except Exception:  # noqa: BLE001 — JSON LLM tuỳ tiện, bỏ phần tử hỏng là đủ
            continue
        thieu = [x for x in (t.chu_the, t.doi_tuong) if x.lower() not in low]
        if thieu:
            canh_bao.append(f"bỏ triple: {thieu[0]!r} không nằm trong điều khoản")
            continue
        ra.append(t)
    return ra, canh_bao
