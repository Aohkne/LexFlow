"""Adapter VLQA (VLSP 2025 DRiLL) → CorpusDocument của LexFlow, cho nhánh eval T117.

Chỉ chuyển ĐỊNH DẠNG, không đụng corpus/đường sản phẩm banking (xem `docs/TASKLIST.md` T117).
Bộ VLQA là dữ liệu thi — KHÔNG commit (đã gitignore `data/raw/VLQA/`).

Cấu trúc nguồn (đã xác minh trên data thật):
  legal_corpus.json = [{id:int, law_id:"14/2022/TT-NHNN", content:[{aid:int, content_Article}]}]
  train.json        = [{qid, question, relevant_laws:[aid], answer}]
  public/private_test = như train nhưng relevant_laws=[] (cần đoán)

Điểm mấu chốt: `aid` là **id điều TOÀN CỤC** (0..59635, duy nhất, liên tục across cả corpus) — một
mình aid định danh điều. `relevant_laws` = tập aid cần đoán. Ta **nhét aid vào nhãn `article`**
(`article=str(aid)`); `_split_khoan` luôn giữ nhãn làm tiền tố nên chunk dài vẫn recover được aid từ
số đầu nhãn. doc_id chỉ để gom ngữ cảnh, KHÔNG cần cho việc nộp.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from app.core.schemas import Article, CorpusDocument

VLQA_DIR = Path("data/raw/VLQA")
#: Bảng LanceDB riêng cho VLQA — KHÔNG trộn bảng "chunks" sản phẩm.
BANG_VLQA = "chunks_vlqa"

_AID_DAU = re.compile(r"^(\d+)")


def nap_corpus(path: str | Path = VLQA_DIR / "legal_corpus.json", *, gioi_han: int | None = None) -> list[CorpusDocument]:
    """legal_corpus.json → [CorpusDocument]. `gioi_han` = chỉ lấy N doc ĐẦU (Stage A, slice rẻ).

    Doc `content` rỗng bị bỏ (1 doc như vậy trong corpus). aid → nhãn `article` để recover khi nộp.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    out: list[CorpusDocument] = []
    for d in raw:
        arts = [
            Article(article=str(a["aid"]), text=a["content_Article"])
            for a in d["content"]
            if (a.get("content_Article") or "").strip()
        ]
        if not arts:
            continue
        law_id = str(d["law_id"])
        out.append(
            CorpusDocument(
                doc_id=f"VLQA-{d['id']}",
                title=law_id,
                doc_type="VLQA",
                so_hieu=law_id,
                articles=arts,
            )
        )
        if gioi_han is not None and len(out) >= gioi_han:
            break
    return out


def aid_tu_chunk(chunk: dict) -> int | None:
    """Recover aid từ một chunk retrieve được: số nguyên ở đầu nhãn `article`."""
    m = _AID_DAU.match(chunk.get("article") or "")
    return int(m.group(1)) if m else None


def nap_cau_hoi(path: str | Path) -> list[dict]:
    """train/public_test/private_test → [{qid, question, relevant_laws:[aid]}]."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [
        {"qid": r["qid"], "question": r["question"], "relevant_laws": list(r.get("relevant_laws") or [])}
        for r in raw
    ]


def aid_toi_da(docs: list[CorpusDocument]) -> int:
    """aid lớn nhất trong slice — để chọn câu train có gold NẰM TRỌN trong slice mà đo (Stage A)."""
    return max(int(a.article) for d in docs for a in d.articles)


def _demo() -> None:
    """Self-check aid round-trip (không cần data thật): article=str(aid) → aid_tu_chunk khôi phục."""
    for aid, nhan in [(0, "0"), (53877, "53877"), (12, "12 Khoản 1-3"), (7, "7 (phần 2)")]:
        assert aid_tu_chunk({"article": nhan}) == aid, nhan
    assert aid_tu_chunk({"article": ""}) is None
    assert aid_tu_chunk({"article": "Điều 5"}) is None  # nhãn LexFlow, không phải aid
    print("vlqa_adapter self-check OK")


if __name__ == "__main__":
    _demo()
