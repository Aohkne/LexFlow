"""Conflict Detector: phát hiện mâu thuẫn giữa các điều khoản ĐANG hiệu lực.

Ưu tiên phát hiện mâu thuẫn giữa tài liệu nội bộ (source=internal) và luật
hiện hành (source=external) — rủi ro tuân thủ lớn nhất.
"""
from __future__ import annotations

from app.core.llm import chat_json
from app.core.schemas import ConflictAlert
from app.core.tracing import observe

_SYSTEM = (
    "Bạn là chuyên gia pháp chế ngân hàng. Nhiệm vụ: xác định các cặp điều khoản "
    "MÂU THUẪN trực tiếp với nhau (ví dụ khác nhau về hạn mức, điều kiện, hoặc cho "
    "phép/cấm cùng một hành vi). Chỉ báo mâu thuẫn thực sự, không suy diễn. "
    "Trả về JSON."
)

_SCHEMA_HINT = (
    'Định dạng JSON: {"conflicts": [{"id_a": "<id chunk>", "id_b": "<id chunk>", '
    '"explanation": "<giải thích ngắn gọn>", "severity": "info|warning|critical"}]}. '
    'Nếu không có mâu thuẫn: {"conflicts": []}.'
)


@observe(name="conflict.detect")
def detect_conflicts(chunks: list[dict]) -> list[ConflictAlert]:
    # Cần ít nhất 2 văn bản khác nhau mới có thể mâu thuẫn
    if len({c["doc_id"] for c in chunks}) < 2:
        return []

    listing = "\n".join(
        f"- id={c['id']} | nguồn={c['source']} | {c['doc_title']} — {c['article']}: {c['text']}"
        for c in chunks
    )
    prompt = f"{_SCHEMA_HINT}\n\nCác điều khoản đang hiệu lực:\n{listing}"
    data = chat_json(prompt, system=_SYSTEM)

    by_id = {c["id"]: c for c in chunks}
    alerts: list[ConflictAlert] = []
    for item in data.get("conflicts", []):
        a, b = by_id.get(item.get("id_a")), by_id.get(item.get("id_b"))
        if not a or not b or a["id"] == b["id"]:
            continue
        alerts.append(
            ConflictAlert(
                doc_a=a["doc_title"], doc_b=b["doc_title"],
                article_a=a["article"], article_b=b["article"],
                explanation=item.get("explanation", ""),
                severity=item.get("severity", "warning"),
            )
        )
    return alerts
