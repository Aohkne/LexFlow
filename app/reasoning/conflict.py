"""Conflict Detector: phát hiện mâu thuẫn giữa các điều khoản ĐANG hiệu lực.

Ưu tiên phát hiện mâu thuẫn giữa tài liệu nội bộ (source=internal) và luật
hiện hành (source=external) — rủi ro tuân thủ lớn nhất.
"""
from __future__ import annotations

import logging

from app.core.llm import chat_json
from app.core.schemas import ConflictAlert
from app.core.tracing import observe

logger = logging.getLogger(__name__)

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


def _quy_ve_chunk(id_llm: str | None, by_id: dict[str, dict]) -> dict | None:
    """Id mô hình trả về → chunk có thật. `None` nếu không quy được.

    Mô hình thường trích dẫn **chi tiết hơn** nhãn chunk: nó đọc `"TT18-2024::Điều 13"` rồi
    trả `"TT18-2024::Điều 13 Khoản 4"`, vì khoản 4 mới là chỗ đặt trần 5 triệu. Tra đúng id thì
    trượt, và bản trước `continue` trong im lặng — đó là toàn bộ khoảng cách `conflict_recall`
    6/7 đo trên benchmark 06/08. Phạt mô hình vì trích dẫn chuẩn hơn là sai hướng.

    Ranh giới là **dấu cách**, không phải `startswith` trần: `"Điều 1"` không được nuốt
    `"Điều 13 Khoản 4"` — corpus thật có đủ cặp Điều 1/Điều 10..19 để cái nhầm đó xảy ra hằng
    ngày. Cùng một luật với `retrieval.lay_chunk_theo_tien_to`; nhánh IR-eval đang tách nó
    thành `retrieval.khop_tien_to`, **gộp lại khi nhánh đó lên `main`** thay vì giữ hai bản.
    """
    if not id_llm:
        return None
    if id_llm in by_id:
        return by_id[id_llm]
    khop = [c for cid, c in by_id.items() if id_llm.startswith(cid + " ")]
    # Nhiều chunk cùng là tiền tố của một id thì không biết chọn cái nào — thà bỏ còn hơn đoán.
    return khop[0] if len(khop) == 1 else None


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
        a, b = _quy_ve_chunk(item.get("id_a"), by_id), _quy_ve_chunk(item.get("id_b"), by_id)
        if not a or not b or a["id"] == b["id"]:
            if not a or not b:
                logger.warning(
                    "Bỏ một cảnh báo mâu thuẫn vì không quy được id về chunk: "
                    "id_a=%r id_b=%r — %.120s",
                    item.get("id_a"), item.get("id_b"), item.get("explanation", ""),
                )
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
