"""Benchmark: RAG vector thuần (baseline) vs Hybrid + Versioning + Conflict.

Đo:
  - citation_accuracy: có trả về đúng văn bản đang hiệu lực (expected_doc) không
  - stale_avoidance : có TRÁNH được văn bản đã hết hiệu lực (must_not_doc) không
  - conflict_recall : có phát hiện đúng trường hợp có mâu thuẫn không

Kết quả in bảng + lưu JSON vào eval/results/<timestamp>.json để so sánh
giữa các lần chạy (regression gate).

Chạy:  uv run python eval/run_benchmark.py
Yêu cầu: đã chạy ingest trước (LanceDB có dữ liệu).
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from app.knowledge.retrieval import baseline_vector_search, graph_augmented_search, hybrid_search
from app.reasoning.conflict import detect_conflicts

QUESTIONS = Path("eval/questions.jsonl")
RESULTS_DIR = Path("eval/results")


def _docs(chunks: list[dict]) -> set[str]:
    return {c["doc_id"] for c in chunks}


def evaluate() -> dict:
    cases = [json.loads(line) for line in QUESTIONS.read_text(encoding="utf-8").splitlines() if line.strip()]

    base = {"cite": 0, "stale": 0}
    ours = {"cite": 0, "stale": 0, "conflict": 0}
    graph = {"cite": 0, "stale": 0, "conflict": 0}
    conflict_total = sum(1 for c in cases if c.get("expect_conflict"))
    details: list[dict] = []
    latencies: list[float] = []

    print(f"{'Câu hỏi':<55} {'Baseline':<18} {'LexFlow':<18}")
    print("-" * 92)
    for case in cases:
        q, as_of = case["query"], case.get("as_of")
        exp, must_not = case.get("expected_doc"), case.get("must_not_doc")

        b_docs = _docs(baseline_vector_search(q, top_k=6))
        t0 = time.perf_counter()
        o_chunks = hybrid_search(q, top_k=6, as_of=as_of, effective_only=True)
        latencies.append(time.perf_counter() - t0)
        o_docs = _docs(o_chunks)

        b_cite = exp in b_docs
        b_stale_ok = (must_not not in b_docs) if must_not else True
        o_cite = exp in o_docs
        o_stale_ok = (must_not not in o_docs) if must_not else True

        base["cite"] += b_cite
        base["stale"] += b_stale_ok
        ours["cite"] += o_cite
        ours["stale"] += o_stale_ok

        # Cột graph-ON: hybrid + mở rộng 1-hop qua knowledge graph
        g_chunks, _ = graph_augmented_search(q, top_k=6, as_of=as_of, effective_only=True)
        g_docs = _docs(g_chunks)
        g_cite = exp in g_docs
        g_stale_ok = (must_not not in g_docs) if must_not else True
        graph["cite"] += g_cite
        graph["stale"] += g_stale_ok

        conflict_found = None
        g_conflict = None
        if case.get("expect_conflict"):
            conflict_found = len(detect_conflicts(o_chunks)) > 0
            ours["conflict"] += conflict_found
            g_conflict = len(detect_conflicts(g_chunks)) > 0
            graph["conflict"] += g_conflict

        details.append(
            {
                "query": q,
                "group": case.get("group", ""),
                "as_of": as_of,
                "expected_doc": exp,
                "must_not_doc": must_not,
                "baseline": {"cite": b_cite, "stale_ok": b_stale_ok, "docs": sorted(b_docs)},
                "lexflow": {"cite": o_cite, "stale_ok": o_stale_ok, "docs": sorted(o_docs)},
                "lexflow_graph": {"cite": g_cite, "stale_ok": g_stale_ok, "docs": sorted(g_docs)},
                "conflict_found": conflict_found,
                "conflict_found_graph": g_conflict,
            }
        )

        def tag(cite: bool, stale: bool) -> str:
            return f"cite={'✓' if cite else '✗'} stale_ok={'✓' if stale else '✗'}"

        print(f"{q[:53]:<55} {tag(b_cite, b_stale_ok):<18} {tag(o_cite, o_stale_ok):<18}")

    n = len(cases)
    summary = {
        "n_cases": n,
        "baseline": {"citation_accuracy": base["cite"] / n, "stale_avoidance": base["stale"] / n},
        "lexflow": {
            "citation_accuracy": ours["cite"] / n,
            "stale_avoidance": ours["stale"] / n,
            "conflict_recall": ours["conflict"] / conflict_total if conflict_total else None,
            "retrieval_latency_p50_ms": round(sorted(latencies)[n // 2] * 1000),
        },
        "lexflow_graph": {
            "citation_accuracy": graph["cite"] / n,
            "stale_avoidance": graph["stale"] / n,
            "conflict_recall": graph["conflict"] / conflict_total if conflict_total else None,
        },
        "conflict_cases": conflict_total,
    }
    print("-" * 92)
    print("KẾT QUẢ TỔNG HỢP (baseline | LexFlow hybrid | LexFlow +graph)")
    print(f"  Citation accuracy : {base['cite']}/{n}  |  {ours['cite']}/{n}  |  {graph['cite']}/{n}")
    print(f"  Tránh văn bản hết hiệu lực: {base['stale']}/{n}  |  {ours['stale']}/{n}  |  {graph['stale']}/{n}")
    print(f"  Phát hiện mâu thuẫn: — | {ours['conflict']}/{conflict_total} | {graph['conflict']}/{conflict_total}")
    print(f"  Latency retrieval p50: {summary['lexflow']['retrieval_latency_p50_ms']} ms")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = RESULTS_DIR / f"{stamp}.json"
    out.write_text(
        json.dumps({"run_at": stamp, "summary": summary, "details": details}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"  → Đã lưu {out}")
    return summary


if __name__ == "__main__":
    evaluate()
