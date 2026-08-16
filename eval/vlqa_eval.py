"""Đo IR VLQA trên bảng `chunks_vlqa` + dựng file nộp DRiLL. T117 — nhánh eval, tách corpus.

Retrieval dùng `hybrid_search(table="chunks_vlqa")` (Neo4j/overlay/hiệu lực đều KHÔNG dùng — VLQA
không có). Chunk → aid qua `aid_tu_chunk`; khớp metric = exact aid (dùng lại `eval/metrics.py` với
khoá `str(aid)`, nó thử `==` trước nên đúng).

**Checkpoint per-câu:** retrieval (embed + search) là phần đắt và dễ bị kill; cache top-20 aid theo
`qid` vào `eval/results/cache-vlqa-*.jsonl` (gitignored). Chạy lại chỉ bù câu thiếu; `--moi` để bỏ
cache (BẮT BUỘC khi đã re-ingest bảng — cache cũ ứng với index cũ). Cache top-20 nên đổi `--topk`
không phải retrieve lại.

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

RESULTS_DIR = Path("eval/results")
_MOC = (1, 5, 10, 20)
_POOL = 20  # số aid cache/câu — cắt xuống --topk lúc nộp, không retrieve lại


def _aids(question: str) -> list[str]:
    """Top-`_POOL` aid (khử trùng, giữ thứ hạng) — search bảng VLQA, không lọc hiệu lực."""
    hits = hybrid_search(question, top_k=_POOL, effective_only=False, table=BANG_VLQA)
    out: list[str] = []
    seen: set[int] = set()
    for h in hits:
        a = aid_tu_chunk(h)
        if a is not None and a not in seen:
            seen.add(a)
            out.append(str(a))
    return out


def _nap_cache(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    return {
        r["qid"]: r
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for r in [json.loads(line)]
    }


def _retrieve_cached(items: list[dict], cache_path: Path, *, moi: bool = False) -> dict[int, list[str]]:
    """items: [{qid, question}] → {qid: [aid str top-20]}, checkpoint per-câu (chịu được kill)."""
    if moi:
        cache_path.unlink(missing_ok=True)
    cache = _nap_cache(cache_path)
    con = [c for c in items if c["qid"] not in cache]
    print(f"{len(items)} câu | đã cache {len(cache)} | còn {len(con)}", flush=True)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    for i, c in enumerate(con, 1):
        row = {"qid": c["qid"], "aids": _aids(c["question"])}
        with cache_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        cache[c["qid"]] = row
        if i % 25 == 0:
            print(f"  {i}/{len(con)}", flush=True)
    return {c["qid"]: cache[c["qid"]]["aids"] for c in items}


def do_train(gioi_han_doc: int, max_cau: int | None = None, *, moi: bool = False) -> None:
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

    retr = _retrieve_cached(hop_le, RESULTS_DIR / "cache-vlqa-train.jsonl", moi=moi)
    vang = {c["qid"]: [str(a) for a in c["relevant_laws"]] for c in hop_le}
    per = [
        {k: metrics.do_mot_cau(retr[c["qid"]], vang[c["qid"]], k) for k in _MOC}
        for c in hop_le
    ]
    agg = {k: metrics.tong_hop([p[k] for p in per]) for k in _MOC}
    print(f"\nIR VLQA (slice {gioi_han_doc} doc, {len(per)} câu) — khớp exact aid", flush=True)
    print(f"{'':<6}{'R@1':>8}{'R@5':>8}{'R@10':>8}{'R@20':>8}{'MRR':>8}{'F2@10':>8}", flush=True)
    print(
        f"{'hybrid':<6}"
        + "".join(f"{agg[k]['recall']:>8.3f}" for k in _MOC)
        + f"{agg[10]['mrr']:>8.3f}{agg[10]['f2']:>8.3f}",
        flush=True,
    )


def nop(test_path: str, topk: int, ra: str, *, moi: bool = False) -> None:
    """Dựng file nộp: mỗi câu → top-k aid. Định dạng mirror input (qid + relevant_laws)."""
    cauhoi = nap_cau_hoi(test_path)
    cache_path = RESULTS_DIR / f"cache-vlqa-nop-{Path(test_path).stem}.jsonl"
    retr = _retrieve_cached(cauhoi, cache_path, moi=moi)
    sub = [{"qid": c["qid"], "relevant_laws": [int(a) for a in retr[c["qid"]][:topk]]} for c in cauhoi]
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
    ap.add_argument("--moi", action="store_true", help="bỏ cache retrieval (bắt buộc khi đã re-ingest)")
    args = ap.parse_args()
    if args.nop:
        nop(args.nop, args.topk, args.ra, moi=args.moi)
    elif args.do_train:
        do_train(args.gioi_han_doc, args.max_cau, moi=args.moi)
    else:
        ap.error("chọn --do-train (Stage A) hoặc --nop <test.json> (Stage B)")


if __name__ == "__main__":
    main()
