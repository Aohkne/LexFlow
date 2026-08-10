"""Đọc một bộ câu hỏi eval (.jsonl) và chuẩn hoá về đúng một cấu trúc.

Tồn tại để bộ dữ liệu đánh giá **soạn ở nơi khác** cắm vào benchmark mà không phải sửa
benchmark: mọi hiểu biết về định dạng nằm ở đây, `run_benchmark.py` chỉ tiêu thụ kết quả.

## Định dạng một dòng

```json
{
  "query": "Hạn mức giao dịch qua ví điện tử cá nhân là bao nhiêu một tháng?",
  "as_of": "2025-01-01",
  "relevant_docs": ["TT40-2024"],
  "relevant_articles": ["TT40-2024::Điều 12"],
  "expected_doc": "TT40-2024",
  "must_not_doc": "TT39-2014",
  "expect_conflict": true,
  "group": "conflict"
}
```

| Trường | Bắt buộc | Nghĩa |
|---|---|---|
| `query` | ✓ | câu hỏi |
| `relevant_docs` | — | **tập** văn bản đủ để trả lời (`R_i` trong công thức của bài báo). Thiếu ⇒ suy từ `expected_doc` |
| `relevant_articles` | — | nhãn vàng cấp điều/khoản, dạng `"{doc_id}::Điều N[ Khoản M]"`. Thiếu ⇒ bỏ qua mức article trong bảng |
| `expected_doc` | — | nhãn cũ, một văn bản — giữ cho các cột đo cũ (`citation_accuracy`) |
| `must_not_doc` | — | văn bản hết hiệu lực KHÔNG được xuất hiện (`stale_avoidance`) |
| `as_of`, `expect_conflict`, `group` | — | như trước |

`relevant_docs` là **văn bản đủ để trả lời câu hỏi**, không phải "mọi văn bản có nhắc tới chủ
đề". Nhãn rộng tay làm recall trông thấp đi một cách giả tạo và precision trông cao lên — đây là
chỗ quyết định con số có nghĩa hay không, xem `docs/EVAL-IR.md`.

Tương thích ngược là bắt buộc: `eval/questions.jsonl` (36 câu, chỉ có `expected_doc`) phải chạy
được nguyên trạng, không sửa một dòng nào.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class CauHoi:
    query: str
    as_of: str | None = None
    expected_doc: str | None = None
    must_not_doc: str | None = None
    expect_conflict: bool = False
    group: str = ""
    relevant_docs: tuple[str, ...] = ()
    relevant_articles: tuple[str, ...] = ()
    #: Dòng gốc — các cột đo cũ của `run_benchmark` vẫn đọc theo kiểu dict.
    tho: dict = field(default_factory=dict, repr=False)


class LoiBoCauHoi(ValueError):
    """Dòng hỏng trong bộ câu hỏi. Ném ra chứ KHÔNG bỏ qua — bỏ qua một câu trong im lặng làm
    mẫu số nhỏ đi mà không ai biết, và bảng kết quả vẫn trông bình thường."""


def _doc_dong(dong: str, nguon: Path, so_dong: int) -> CauHoi:
    try:
        raw = json.loads(dong)
    except json.JSONDecodeError as exc:
        raise LoiBoCauHoi(f"{nguon}:{so_dong} — JSON hỏng: {exc}") from exc
    if not isinstance(raw, dict):
        raise LoiBoCauHoi(f"{nguon}:{so_dong} — mỗi dòng phải là một object JSON.")

    query = (raw.get("query") or "").strip()
    if not query:
        raise LoiBoCauHoi(f"{nguon}:{so_dong} — thiếu `query`.")

    docs = raw.get("relevant_docs")
    if docs is None:
        # Suy từ nhãn cũ: 36 câu hiện có chỉ có `expected_doc`.
        docs = [raw["expected_doc"]] if raw.get("expected_doc") else []
    if not isinstance(docs, list) or any(not isinstance(d, str) for d in docs):
        raise LoiBoCauHoi(f"{nguon}:{so_dong} — `relevant_docs` phải là danh sách chuỗi.")

    arts = raw.get("relevant_articles") or []
    if not isinstance(arts, list) or any(not isinstance(a, str) for a in arts):
        raise LoiBoCauHoi(f"{nguon}:{so_dong} — `relevant_articles` phải là danh sách chuỗi.")
    for a in arts:
        if "::" not in a:
            raise LoiBoCauHoi(
                f"{nguon}:{so_dong} — nhãn điều {a!r} thiếu `::`; đúng dạng là "
                '"{doc_id}::Điều N" (vd "TT40-2024::Điều 12").'
            )

    return CauHoi(
        query=query,
        as_of=raw.get("as_of"),
        expected_doc=raw.get("expected_doc"),
        must_not_doc=raw.get("must_not_doc"),
        expect_conflict=bool(raw.get("expect_conflict")),
        group=raw.get("group", ""),
        relevant_docs=tuple(docs),
        relevant_articles=tuple(arts),
        tho=raw,
    )


def nap(duong_dan: str | Path) -> list[CauHoi]:
    """Đọc file .jsonl → danh sách `CauHoi`. Dòng trắng bị bỏ qua, dòng hỏng thì ném."""
    p = Path(duong_dan)
    ra: list[CauHoi] = []
    for i, dong in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        if dong.strip():
            ra.append(_doc_dong(dong, p, i))
    if not ra:
        raise LoiBoCauHoi(f"{p} — không có câu hỏi nào.")
    return ra
