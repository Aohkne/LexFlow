"""Benchmark: RAG vector thuần (baseline) vs Hybrid + Versioning + Conflict.

Đo:
  - citation_accuracy: có trả về đúng văn bản đang hiệu lực (expected_doc) không
  - stale_avoidance : có TRÁNH được văn bản đã hết hiệu lực (must_not_doc) không
  - conflict_recall : có phát hiện đúng trường hợp có mâu thuẫn không

Chạy:  uv run python eval/run_benchmark.py
Yêu cầu: đã chạy ingest trước (LanceDB có dữ liệu).
"""
from __future__ import annotations

import json
from pathlib import Path

from app.knowledge.retrieval import baseline_vector_search, hybrid_search
from app.reasoning.conflict import detect_conflicts

QUESTIONS = Path("eval/questions.jsonl")


def _docs(chunks: list[dict]) -> set[str]:
    return {c["doc_id"] for c in chunks}


def evaluate() -> None:
    cases = [json.loads(line) for line in QUESTIONS.read_text(encoding="utf-8").splitlines() if line.strip()]

    base = {"cite": 0, "stale": 0}
    ours = {"cite": 0, "stale": 0, "conflict": 0}
    conflict_total = sum(1 for c in cases if c.get("expect_conflict"))

    print(f"{'Câu hỏi':<55} {'Baseline':<18} {'LexFlow':<18}")
    print("-" * 92)
    for case in cases:
        q, as_of = case["query"], case.get("as_of")
        exp, must_not = case.get("expected_doc"), case.get("must_not_doc")

        b_docs = _docs(baseline_vector_search(q, top_k=6))
        o_chunks = hybrid_search(q, top_k=6, as_of=as_of, effective_only=True)
        o_docs = _docs(o_chunks)

        b_cite = exp in b_docs
        b_stale_ok = (must_not not in b_docs) if must_not else True
        o_cite = exp in o_docs
        o_stale_ok = (must_not not in o_docs) if must_not else True

        base["cite"] += b_cite
        base["stale"] += b_stale_ok
        ours["cite"] += o_cite
        ours["stale"] += o_stale_ok

        if case.get("expect_conflict"):
            found = len(detect_conflicts(o_chunks)) > 0
            ours["conflict"] += found

        def tag(cite: bool, stale: bool) -> str:
            return f"cite={'✓' if cite else '✗'} stale_ok={'✓' if stale else '✗'}"

        print(f"{q[:53]:<55} {tag(b_cite, b_stale_ok):<18} {tag(o_cite, o_stale_ok):<18}")

    n = len(cases)
    print("-" * 92)
    print("KẾT QUẢ TỔNG HỢP")
    print(f"  Citation accuracy : baseline {base['cite']}/{n}  |  LexFlow {ours['cite']}/{n}")
    print(f"  Tránh văn bản hết hiệu lực: baseline {base['stale']}/{n}  |  LexFlow {ours['stale']}/{n}")
    print(f"  Phát hiện mâu thuẫn: LexFlow {ours['conflict']}/{conflict_total} (baseline: không hỗ trợ)")


if __name__ == "__main__":
    evaluate()
