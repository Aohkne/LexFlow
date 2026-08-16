"""Đo IR VLQA trên bảng `chunks_vlqa` + dựng file nộp DRiLL. T117 — nhánh eval, tách corpus.

Retrieval dùng `hybrid_search(table="chunks_vlqa")` (Neo4j/overlay/hiệu lực đều KHÔNG dùng — VLQA
không có). Chunk → aid qua `aid_tu_chunk`; khớp metric = exact aid (dùng lại `eval/metrics.py` với
khoá `str(aid)`, nó thử `==` trước nên đúng).

Stage A (slice, đo máy móc):
  uv run python -u eval/vlqa_eval.py --do-train --gioi-han-doc 60 [--max-cau 40]
Stage B (nộp — sau khi ingest full):
  uv run python -u eval/vlqa_eval.py --nop data/raw/VLQA/public_test.json --topk 10 --ra eval/results/vlqa_public.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # chạy như script thấy `app`

from app.knowledge.retrieval import hybrid_search  # noqa: E402
from eval import metrics  # noqa: E402
from eval.vlqa_adapter import (  # noqa: E402
    BANG_VLQA,
    VLQA_DIR,
    aid_toi_da,
    aid_tu_chunk,
    nap_cau_hoi,
    nap_corpus,
)

_MOC = (1, 5, 10, 20)


def _aids(question: str, top_k: int = 20) -> list[str]:
    """Top-k aid (khử trùng, giữ thứ hạng) cho một câu — search bảng VLQA, không lọc hiệu lực."""
    hits = hybrid_search(question, top_k=top_k, effective_only=False, table=BANG_VLQA)
    out: list[str] = []
    seen: set[int] = set()
    for h in hits:
        a = aid_tu_chunk(h)
        if a is not None and a not in seen:
            seen.add(a)
            out.append(str(a))
    return out


def do_train(gioi_han_doc: int, max_cau: int | None = None) -> None:
    """Chấm IR trên câu train có gold NẰM TRỌN trong slice (mọi aid ≤ aid tối đa của slice)."""
    docs = nap_corpus(gioi_han=gioi_han_doc)
    tran = aid_toi_da(docs)
    hop_le = [
        c for c in nap_cau_hoi(VLQA_DIR / "train.json")
        if c["relevant_laws"] and all(a <= tran for a in c["relevant_laws"])
    ]
    if max_cau:
        hop_le = hop_le[:max_cau]
    print(f"Slice {gioi_han_doc} doc (aid ≤ {tran}) → {len(hop_le)} câu train đo được", flush=True)
    if not hop_le:
        print("Không câu train nào có gold nằm trọn trong slice — tăng --gioi-han-doc.", flush=True)
        return

    per: list[dict] = []
    for i, c in enumerate(hop_le, 1):
        retr = _aids(c["question"])
        vang = [str(a) for a in c["relevant_laws"]]
        per.append({k: metrics.do_mot_cau(retr, vang, k) for k in _MOC})
        if i % 20 == 0:
            print(f"  {i}/{len(hop_le)}", flush=True)

    print(f"\nIR VLQA (slice {gioi_han_doc} doc, {len(per)} câu) — khớp exact aid", flush=True)
    print(f"{'':<6}{'R@1':>8}{'R@5':>8}{'R@10':>8}{'R@20':>8}{'MRR':>8}{'F2@10':>8}", flush=True)
    agg = {k: metrics.tong_hop([p[k] for p in per]) for k in _MOC}
    print(
        f"{'hybrid':<6}"
        + "".join(f"{agg[k]['recall']:>8.3f}" for k in _MOC)
        + f"{agg[10]['mrr']:>8.3f}{agg[10]['f2']:>8.3f}",
        flush=True,
    )


def nop(test_path: str, topk: int, ra: str) -> None:
    """Dựng file nộp: mỗi câu → top-k aid. Định dạng mirror input (qid + relevant_laws)."""
    cauhoi = nap_cau_hoi(test_path)
    sub = []
    for i, c in enumerate(cauhoi, 1):
        aids = [int(a) for a in _aids(c["question"], top_k=topk)][:topk]
        sub.append({"qid": c["qid"], "relevant_laws": aids})
        if i % 50 == 0:
            print(f"  {i}/{len(cauhoi)}", flush=True)
    Path(ra).write_text(json.dumps(sub, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {len(sub)} câu, top-{topk} aid/câu → {ra}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--do-train", action="store_true", help="Stage A: đo IR trên slice train")
    ap.add_argument("--gioi-han-doc", type=int, default=60, help="số doc của slice (khớp lúc ingest)")
    ap.add_argument("--max-cau", type=int, default=None, help="giới hạn số câu train để chạy nhanh")
    ap.add_argument("--nop", metavar="TEST_JSON", help="Stage B: dựng file nộp từ public/private_test")
    ap.add_argument("--topk", type=int, default=10, help="số aid nộp mỗi câu")
    ap.add_argument("--ra", default="eval/results/vlqa_submission.json", help="đường ra file nộp")
    args = ap.parse_args()
    if args.nop:
        nop(args.nop, args.topk, args.ra)
    elif args.do_train:
        do_train(args.gioi_han_doc, args.max_cau)
    else:
        ap.error("chọn --do-train (Stage A) hoặc --nop <test.json> (Stage B)")


if __name__ == "__main__":
    main()
