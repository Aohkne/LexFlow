"""Benchmark: RAG vector thuần (baseline) vs Hybrid + Versioning + Conflict.

Đo:
  - citation_accuracy: có trả về đúng văn bản đang hiệu lực (expected_doc) không
  - stale_avoidance : có TRÁNH được văn bản đã hết hiệu lực (must_not_doc) không
  - conflict_recall : có phát hiện đúng trường hợp có mâu thuẫn không
  - router ON/OFF   : lớp phủ dưới-văn-bản (`chu_thich_ket_qua`) đổi gì so với không áp

Kết quả in bảng + lưu JSON vào eval/results/<timestamp>.json để so sánh
giữa các lần chạy (regression gate).

Chạy:  uv run python -u eval/run_benchmark.py   (`-u` = stdout không buffer, thấy tiến độ ngay)
Yêu cầu: đã chạy ingest trước (LanceDB có dữ liệu).

Mỗi câu chạy trong try/except riêng: một lỗi mạng thoáng qua (LanceDB Cloud/Neo4j Aura) không
được giết cả lượt đo — câu lỗi bị bỏ qua, ghi lại trong `errors`, và KHÔNG tính vào mẫu số của
các tỷ lệ (accuracy tính trên số câu THÀNH CÔNG, không phải trên `n_cases` tổng).
"""
from __future__ import annotations

import json
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from app.knowledge.lop_phu import chu_thich_ket_qua
from app.knowledge.retrieval import baseline_vector_search, graph_augmented_search, hybrid_search
from app.reasoning.conflict import detect_conflicts

QUESTIONS = Path("eval/questions.jsonl")
RESULTS_DIR = Path("eval/results")


def _docs(chunks: list[dict]) -> set[str]:
    return {c["doc_id"] for c in chunks}


def _run_case(case: dict) -> dict:
    """Chạy một câu qua mọi cột. Ném lỗi ra ngoài — người gọi bắt và ghi lại."""
    q, as_of = case["query"], case.get("as_of")
    exp, must_not = case.get("expected_doc"), case.get("must_not_doc")

    b_docs = _docs(baseline_vector_search(q, top_k=6))
    t0 = time.perf_counter()
    o_chunks = hybrid_search(q, top_k=6, as_of=as_of, effective_only=True)
    latency = time.perf_counter() - t0
    o_docs = _docs(o_chunks)

    b_cite = exp in b_docs
    b_stale_ok = (must_not not in b_docs) if must_not else True
    o_cite = exp in o_docs
    o_stale_ok = (must_not not in o_docs) if must_not else True

    # Cột graph-ON: hybrid + mở rộng 1-hop qua knowledge graph
    g_chunks, _ = graph_augmented_search(q, top_k=6, as_of=as_of, effective_only=True)
    g_docs = _docs(g_chunks)
    g_cite = exp in g_docs
    g_stale_ok = (must_not not in g_docs) if must_not else True

    # Cột router ON/OFF: lớp phủ dưới-văn-bản (`settings.overlay_router`) áp SAU retrieval
    # graph-augmented (đúng đường sản phẩm thật trong `answer.py`/`review.py`) — router KHÔNG
    # đổi cách retrieval, chỉ lọc hit `bi_bai_bo` và gắn chú thích hiệu lực. OFF = chunks thô
    # (như cột lexflow_graph ở trên); ON = gọi thẳng `chu_thich_ket_qua` (tương đương
    # `settings.overlay_router = True`) trên CÙNG `g_chunks` — không gọi lại retrieval, nên
    # mọi khác biệt ON/OFF trong một lượt chạy là do router, không do nhiễu corpus/retrieval.
    router_on_chunks, ct = chu_thich_ket_qua(g_chunks, as_of)
    router_off_docs = g_docs
    router_on_docs = _docs(router_on_chunks)

    ron_cite = exp in router_on_docs
    ron_stale_ok = (must_not not in router_on_docs) if must_not else True
    roff_cite = exp in router_off_docs
    roff_stale_ok = (must_not not in router_off_docs) if must_not else True

    case_bai_bo = sum(1 for t in ct.values() if t.trang_thai == "bi_bai_bo")
    case_nan = sum(1 for t in ct.values() if t.trang_thai in ("da_sua", "la_loi_sua"))
    router_differs = sorted(router_on_docs) != sorted(router_off_docs)

    conflict_found = None
    g_conflict = None
    if case.get("expect_conflict"):
        conflict_found = len(detect_conflicts(o_chunks)) > 0
        g_conflict = len(detect_conflicts(g_chunks)) > 0

    return {
        "query": q,
        "group": case.get("group", ""),
        "as_of": as_of,
        "expected_doc": exp,
        "must_not_doc": must_not,
        "latency_s": latency,
        "baseline": {"cite": b_cite, "stale_ok": b_stale_ok, "docs": sorted(b_docs)},
        "lexflow": {"cite": o_cite, "stale_ok": o_stale_ok, "docs": sorted(o_docs)},
        "lexflow_graph": {"cite": g_cite, "stale_ok": g_stale_ok, "docs": sorted(g_docs)},
        "router_off": {"cite": roff_cite, "stale_ok": roff_stale_ok, "docs": sorted(router_off_docs)},
        "router_on": {"cite": ron_cite, "stale_ok": ron_stale_ok, "docs": sorted(router_on_docs)},
        "router_differs": router_differs,
        "router_hits_bai_bo": case_bai_bo,
        "router_hits_nan_trich_dan": case_nan,
        "conflict_found": conflict_found,
        "conflict_found_graph": g_conflict,
        "expect_conflict": bool(case.get("expect_conflict")),
    }


def evaluate() -> dict:
    cases = [json.loads(line) for line in QUESTIONS.read_text(encoding="utf-8").splitlines() if line.strip()]
    n = len(cases)

    base = {"cite": 0, "stale": 0}
    ours = {"cite": 0, "stale": 0, "conflict": 0}
    graph = {"cite": 0, "stale": 0, "conflict": 0}
    router_on = {"cite": 0, "stale": 0}
    router_off = {"cite": 0, "stale": 0}
    n_router_diff = 0
    hits_bai_bo = 0
    hits_nan_trich_dan = 0
    conflict_total = 0
    details: list[dict] = []
    errors: list[dict] = []
    latencies: list[float] = []

    print(f"{'#':<4}{'Câu hỏi':<55} {'Baseline':<18} {'LexFlow':<18}", flush=True)
    print("-" * 96, flush=True)
    for i, case in enumerate(cases, start=1):
        q = case["query"]
        try:
            r = _run_case(case)
        except Exception as exc:  # noqa: BLE001 — một câu lỗi không được giết cả lượt đo
            print(f"{i:<4}{q[:53]:<55} LỖI: {exc!r}", flush=True)
            errors.append({"query": q, "error": repr(exc), "traceback": traceback.format_exc()})
            details.append({"query": q, "group": case.get("group", ""), "error": repr(exc)})
            continue

        latencies.append(r["latency_s"])
        base["cite"] += r["baseline"]["cite"]
        base["stale"] += r["baseline"]["stale_ok"]
        ours["cite"] += r["lexflow"]["cite"]
        ours["stale"] += r["lexflow"]["stale_ok"]
        graph["cite"] += r["lexflow_graph"]["cite"]
        graph["stale"] += r["lexflow_graph"]["stale_ok"]
        router_on["cite"] += r["router_on"]["cite"]
        router_on["stale"] += r["router_on"]["stale_ok"]
        router_off["cite"] += r["router_off"]["cite"]
        router_off["stale"] += r["router_off"]["stale_ok"]
        hits_bai_bo += r["router_hits_bai_bo"]
        hits_nan_trich_dan += r["router_hits_nan_trich_dan"]
        n_router_diff += r["router_differs"]
        if r["expect_conflict"]:
            conflict_total += 1
            ours["conflict"] += bool(r["conflict_found"])
            graph["conflict"] += bool(r["conflict_found_graph"])

        details.append(r)

        def tag(cite: bool, stale: bool) -> str:
            return f"cite={'✓' if cite else '✗'} stale_ok={'✓' if stale else '✗'}"

        print(
            f"{i:<4}{q[:53]:<55} {tag(r['baseline']['cite'], r['baseline']['stale_ok']):<18} "
            f"{tag(r['lexflow']['cite'], r['lexflow']['stale_ok']):<18}",
            flush=True,
        )

    n_ok = n - len(errors)
    denom = n_ok or 1  # tránh chia 0 nếu mọi câu đều lỗi (summary khi đó vô nghĩa nhưng không crash)
    summary = {
        "n_cases": n,
        "n_ok": n_ok,
        "n_errors": len(errors),
        "baseline": {"citation_accuracy": base["cite"] / denom, "stale_avoidance": base["stale"] / denom},
        "lexflow": {
            "citation_accuracy": ours["cite"] / denom,
            "stale_avoidance": ours["stale"] / denom,
            "conflict_recall": ours["conflict"] / conflict_total if conflict_total else None,
            "retrieval_latency_p50_ms": (
                round(sorted(latencies)[len(latencies) // 2] * 1000) if latencies else None
            ),
        },
        "lexflow_graph": {
            "citation_accuracy": graph["cite"] / denom,
            "stale_avoidance": graph["stale"] / denom,
            "conflict_recall": graph["conflict"] / conflict_total if conflict_total else None,
        },
        "router": {
            "off": {"citation_accuracy": router_off["cite"] / denom, "stale_avoidance": router_off["stale"] / denom},
            "on": {"citation_accuracy": router_on["cite"] / denom, "stale_avoidance": router_on["stale"] / denom},
            "n_cases_differ": n_router_diff,
            "hits_bai_bo": hits_bai_bo,
            "hits_nan_trich_dan": hits_nan_trich_dan,
        },
        "conflict_cases": conflict_total,
    }
    print("-" * 96, flush=True)
    print(f"CÂU LỖI (bỏ qua, không tính vào tỷ lệ): {len(errors)}/{n}", flush=True)
    for e in errors:
        print(f"  - {e['query'][:70]}: {e['error']}", flush=True)
    print("KẾT QUẢ TỔNG HỢP (baseline | LexFlow hybrid | LexFlow +graph) — trên", n_ok, "câu thành công", flush=True)
    print(f"  Citation accuracy : {base['cite']}/{n_ok}  |  {ours['cite']}/{n_ok}  |  {graph['cite']}/{n_ok}", flush=True)
    print(f"  Tránh văn bản hết hiệu lực: {base['stale']}/{n_ok}  |  {ours['stale']}/{n_ok}  |  {graph['stale']}/{n_ok}", flush=True)
    print(f"  Phát hiện mâu thuẫn: — | {ours['conflict']}/{conflict_total} | {graph['conflict']}/{conflict_total}", flush=True)
    print(f"  Latency retrieval p50: {summary['lexflow']['retrieval_latency_p50_ms']} ms", flush=True)
    print("-" * 96, flush=True)
    print("ROUTER (lớp phủ dưới-văn-bản, áp trên cột +graph) — OFF | ON", flush=True)
    print(f"  Citation accuracy : {router_off['cite']}/{n_ok}  |  {router_on['cite']}/{n_ok}", flush=True)
    print(f"  Tránh văn bản hết hiệu lực: {router_off['stale']}/{n_ok}  |  {router_on['stale']}/{n_ok}", flush=True)
    print(f"  Số câu OFF/ON khác nhau (docs trả về): {n_router_diff}/{n_ok}", flush=True)
    print(f"  Hit bị loại vì bãi bỏ (tổng trên {n_ok} câu): {hits_bai_bo}", flush=True)
    print(f"  Hit được nắn trích dẫn (da_sua/la_loi_sua, tổng trên {n_ok} câu): {hits_nan_trich_dan}", flush=True)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = RESULTS_DIR / f"{stamp}.json"
    out.write_text(
        json.dumps(
            {"run_at": stamp, "summary": summary, "details": details, "errors": errors},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"  → Đã lưu {out}", flush=True)
    return summary


if __name__ == "__main__":
    evaluate()
