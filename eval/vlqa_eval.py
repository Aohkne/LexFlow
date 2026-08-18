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
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # chạy như script thấy `app`

from app.knowledge.retrieval import hybrid_search  # noqa: E402
from eval import metrics  # noqa: E402
from eval.thu_rerank import rerank as _rerank_api  # noqa: E402
from eval.thu_rerank import rerank_scored as _rerank_scored_api  # noqa: E402
from eval.vlqa_adapter import (  # noqa: E402
    BANG_VLQA,
    VLQA_DIR,
    aid_toi_da,
    aid_tu_chunk,
    nap_cau_hoi,
    nap_corpus,
)

RESULTS_DIR = Path("eval/results")
_POOL = 20  # số aid cache/câu — cắt xuống --topk lúc nộp, không retrieve lại

# variable-k theo ĐIỂM RERANK (không phải RRF). Luật chốt bằng 2-fold CV trên 68 câu train
# (gain out-of-sample +0.048; cả 2 fold chọn cùng ngưỡng): top-1 áp đảo → nộp 1; top-2≈top-3 →
# nộp 3 (dấu hiệu đa gold); còn lại 2. Điểm relevance của Cohere phân biệt được, RRF thì không.
_VK_BIEN1 = 0.05  # điểm[0]-điểm[1] ≥ ngưỡng → nộp 1
_VK_HOA3 = 0.05   # điểm[1]-điểm[2] ≤ ngưỡng → nộp 3


def _var_k(scored: list) -> int:
    """Chọn k∈{1,2,3} từ [[aid, score], ...] (score giảm dần) theo luật đã validate."""
    s = [x[1] for x in scored] + [0.0, 0.0, 0.0]
    if s[0] - s[1] >= _VK_BIEN1:
        return 1
    if s[1] - s[2] <= _VK_HOA3:
        return 3
    return 2


def _aids_scored(question: str) -> list:
    """Top-`_POOL` [[aid, điểm rerank], ...] (khử trùng, giữ thứ hạng rerank) cho variable-k."""
    hits = hybrid_search(question, top_k=_POOL, effective_only=False, table=BANG_VLQA)
    if len(hits) > 1:
        order = _rerank_scored_api(question, [(h.get("text") or "") for h in hits], _POOL)
    else:
        order = [(i, 0.0) for i in range(len(hits))]
    out: list = []
    seen: set[int] = set()
    for idx, sc in order:
        a = aid_tu_chunk(hits[idx])
        if a is not None and a not in seen:
            seen.add(a)
            out.append([str(a), float(sc)])
    return out


def _aids(question: str, *, rerank: bool = False) -> list[str]:
    """Top-`_POOL` aid (khử trùng, giữ thứ hạng) — search bảng VLQA, không lọc hiệu lực.

    `rerank`: xáo lại top-20 bằng cross-encoder (reranker cấu hình ở `.env`) TRƯỚC khi rút aid —
    nhấc điều đúng lên top, hợp với submission k nhỏ (chỉ cần top-2 đúng).
    """
    hits = hybrid_search(question, top_k=_POOL, effective_only=False, table=BANG_VLQA)
    if rerank and len(hits) > 1:
        order = _rerank_api(question, [(h.get("text") or "") for h in hits], _POOL)
        hits = [hits[i] for i in order]
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


def _retrieve_cached(
    items: list[dict], cache_path: Path, *, moi: bool = False, rerank: bool = False,
    scored: bool = False,
) -> dict[int, list]:
    """items: [{qid, question}] → {qid: aids top-20}, checkpoint per-câu (chịu được kill).

    `scored`: aids là [[aid, điểm rerank], ...] (cho variable-k); mặc định là [aid str].
    """
    if moi:
        cache_path.unlink(missing_ok=True)
    cache = _nap_cache(cache_path)
    con = [c for c in items if c["qid"] not in cache]
    print(f"{len(items)} câu | đã cache {len(cache)} | còn {len(con)}", flush=True)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    for i, c in enumerate(con, 1):
        # Retry lỗi Cloud thoáng qua (LanceDB Cloud "error decoding response body" hay xảy ra ở
        # scale này); vẫn hỏng thì BỎ QUA câu (không cache) để relaunch sau thử lại — một hiccup
        # không được abort cả lượt 2.190 câu.
        aids = None
        for lan in range(3):
            try:
                aids = _aids_scored(c["question"]) if scored else _aids(c["question"], rerank=rerank)
                break
            except Exception as exc:  # noqa: BLE001
                if lan < 2:
                    time.sleep(2 * (lan + 1))
                else:
                    print(f"  bỏ qua qid={c['qid']} (3 lần lỗi): {exc!r}", flush=True)
        if aids is None:
            continue
        row = {"qid": c["qid"], "aids": aids}
        with cache_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        cache[c["qid"]] = row
        if i % 25 == 0:
            print(f"  {i}/{len(con)}", flush=True)
    return {c["qid"]: cache[c["qid"]]["aids"] for c in items if c["qid"] in cache}


def _hang(nhan: str, retr: dict[int, list[str]], vang: dict[int, list[str]], qids: list[int]) -> None:
    """In một hàng IR — R@k + Macro-F2@{2,3} (cutoff nộp) + MRR. Câu bị skip loại khỏi mẫu số."""
    ks = (1, 2, 3, 5, 10, 20)
    per = [{k: metrics.do_mot_cau(retr[q], vang[q], k) for k in ks} for q in qids if q in retr]
    if not per:
        print(f"{nhan:<8} (chưa câu nào)", flush=True)
        return
    a = {k: metrics.tong_hop([p[k] for p in per]) for k in ks}
    print(
        f"{nhan:<8}"
        + "".join(f"{a[k]['recall']:>7.3f}" for k in (1, 2, 5, 20))
        + f"{a[2]['f2_macro']:>8.3f}{a[3]['f2_macro']:>8.3f}{a[10]['mrr']:>8.3f}  (n={len(per)})",
        flush=True,
    )


def do_train(gioi_han_doc: int, max_cau: int | None = None, *, moi: bool = False, rerank: bool = False) -> None:
    """Đo IR trên câu train có gold ≤ aid tối đa của slice. `rerank`: so thêm hàng +rerank."""
    docs = nap_corpus(gioi_han=gioi_han_doc)
    tran = aid_toi_da(docs)
    hop_le = [
        c for c in nap_cau_hoi(VLQA_DIR / "train.json")
        if c["relevant_laws"] and all(a <= tran for a in c["relevant_laws"])
    ]
    if max_cau:
        hop_le = hop_le[:max_cau]
    print(f"Corpus {gioi_han_doc} doc (aid ≤ {tran}) → {len(hop_le)} câu train", flush=True)
    if not hop_le:
        print("Không câu train nào có gold nằm trọn — tăng --gioi-han-doc.", flush=True)
        return

    vang = {c["qid"]: [str(a) for a in c["relevant_laws"]] for c in hop_le}
    qids = [c["qid"] for c in hop_le]
    # Baseline: giữ cache cũ khi đang so rerank (đắt, đừng xoá); chỉ `--moi` thuần baseline mới xoá.
    base = _retrieve_cached(hop_le, RESULTS_DIR / "cache-vlqa-train.jsonl", moi=moi and not rerank)
    print(f"\n{'Model':<8}{'R@1':>7}{'R@2':>7}{'R@5':>7}{'R@20':>7}{'F2@2':>8}{'F2@3':>8}{'MRR':>8}", flush=True)
    _hang("hybrid", base, vang, qids)
    if rerank:
        rr = _retrieve_cached(hop_le, RESULTS_DIR / "cache-vlqa-train-rerank.jsonl", moi=moi, rerank=True)
        _hang("+rerank", rr, vang, qids)


def nop(
    test_path: str, topk: int, ra: str, *, moi: bool = False, rerank: bool = False,
    var_k: bool = False,
) -> None:
    """Dựng file nộp: MIRROR y hệt file test, chỉ điền `relevant_laws`.

    Giữ nguyên mọi trường gốc (`question`, `answer`, …) — định dạng nộp không được công bố cụ thể
    (xem T117), mirror input là an toàn nhất: grader muốn shape nào cũng khớp, thừa trường thì bỏ
    qua. `topk` mặc định 2 = tối ưu Macro-F2 trên train (sweep k=1..20; k=2 → F2 0.533 vs k=10 0.335).
    `rerank`: xáo top-20 bằng cross-encoder trước khi cắt top-k (cache riêng, xem `--rerank`).
    `var_k`: điểm rerank + chọn k∈{1,2,3} mỗi câu theo `_var_k` (hàm ý rerank; +0.048 F2 out-of-sample).
    """
    raw = json.loads(Path(test_path).read_text(encoding="utf-8"))
    suffix = "-rerankscore" if var_k else ("-rerank" if rerank else "")
    cache_path = RESULTS_DIR / f"cache-vlqa-nop-{Path(test_path).stem}{suffix}.jsonl"
    retr = _retrieve_cached(raw, cache_path, moi=moi, rerank=rerank, scored=var_k)  # raw có qid+question
    thieu = [r["qid"] for r in raw if r["qid"] not in retr]
    if thieu and (rerank or var_k):
        # Reranker (Cohere trial) dính 429/lỗi vài câu — thà lấy top-2 hybrid còn hơn rỗng (0 điểm).
        hb = {q: r["aids"] for q, r in _nap_cache(RESULTS_DIR / f"cache-vlqa-nop-{Path(test_path).stem}.jsonl").items()}
        bu = [q for q in thieu if q in hb]
        for q in bu:
            retr[q] = [[a, 0.0] for a in hb[q]] if var_k else hb[q]  # đồng dạng scored để cắt thống nhất
        print(f"  ↩ {len(bu)}/{len(thieu)} câu rerank-lỗi → fallback hybrid top-2", flush=True)
        thieu = [q for q in thieu if q not in hb]
    if thieu:
        print(f"  ⚠ {len(thieu)} câu chưa retrieve được → relevant_laws RỖNG; relaunch để bù: {thieu[:10]}", flush=True)
    sub = []
    for r in raw:
        rec = dict(r)  # giữ nguyên question/answer/…
        aids = retr.get(r["qid"], [])
        if var_k:
            k = _var_k(aids)
            rec["relevant_laws"] = [int(a) for a, _ in aids[:k]]
        else:
            rec["relevant_laws"] = [int(a) for a in aids[:topk]]
        sub.append(rec)
    Path(ra).write_text(json.dumps(sub, ensure_ascii=False, indent=1), encoding="utf-8")
    canh = "variable-k (rerank score)" if var_k else f"top-{topk} aid/câu"
    print(f"→ {len(sub)} câu, {canh} → {ra}", flush=True)


def _check_var_k() -> None:
    """Kiểm logic _var_k KHÔNG cần mạng."""
    assert _var_k([["a", 0.9], ["b", 0.2], ["c", 0.1]]) == 1, "top-1 áp đảo → 1"
    assert _var_k([["a", 0.5], ["b", 0.48], ["c", 0.47]]) == 3, "top-2≈top-3 → 3"
    assert _var_k([["a", 0.5], ["b", 0.47], ["c", 0.1]]) == 2, "giữa → 2"
    assert _var_k([["a", 0.9]]) == 1, "một aid, đệm 0 → biên lớn → 1"
    assert _var_k([]) == 3, "rỗng → điểm toàn 0, s1-s2=0 ≤ ngưỡng → 3 (mọi aid rỗng nên vô hại)"
    print("self-check _var_k OK", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--do-train", action="store_true", help="Stage A: đo IR trên slice train")
    ap.add_argument("--gioi-han-doc", type=int, default=60, help="số doc của slice (khớp lúc ingest)")
    ap.add_argument("--max-cau", type=int, default=None, help="giới hạn số câu train để chạy nhanh")
    ap.add_argument("--nop", metavar="TEST_JSON", help="Stage B: dựng file nộp từ public/private_test")
    ap.add_argument("--topk", type=int, default=2, help="số aid nộp mỗi câu (2 = tối ưu Macro-F2 trên train)")
    ap.add_argument("--ra", default="eval/results/vlqa_submission.json", help="đường ra file nộp")
    ap.add_argument("--moi", action="store_true", help="bỏ cache retrieval (bắt buộc khi đã re-ingest)")
    ap.add_argument("--rerank", action="store_true", help="xáo top-20 bằng cross-encoder (.env) trước khi cắt")
    ap.add_argument("--var-k", action="store_true", help="điểm rerank + chọn k∈{1,2,3} mỗi câu (thay --topk)")
    ap.add_argument("--self-check", action="store_true", help="kiểm logic _var_k, không cần mạng")
    args = ap.parse_args()
    if args.self_check:
        _check_var_k()
    elif args.nop:
        nop(args.nop, args.topk, args.ra, moi=args.moi, rerank=args.rerank, var_k=args.var_k)
    elif args.do_train:
        do_train(args.gioi_han_doc, args.max_cau, moi=args.moi, rerank=args.rerank)
    else:
        ap.error("chọn --do-train (Stage A) hoặc --nop <test.json> (Stage B)")


if __name__ == "__main__":
    main()
