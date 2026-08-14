"""Benchmark: RAG vector thuần (baseline) vs Hybrid + Versioning + Conflict, kèm metric IR.

Hai tầng đo, chạy trong cùng một lượt:

**Tầng cũ (regression gate, không đổi nghĩa)**
  - citation_accuracy: có trả về đúng văn bản đang hiệu lực (expected_doc) không
  - stale_avoidance : có TRÁNH được văn bản đã hết hiệu lực (must_not_doc) không
  - conflict_recall : có phát hiện đúng trường hợp có mâu thuẫn không
  - router ON/OFF   : lớp phủ dưới-văn-bản (`chu_thich_ket_qua`) đổi gì so với không áp

**Tầng IR (mới)** — theo §5.3 của bài báo SBV-LawGraph (`docs/paper/ACIIDS2026a.pdf`):
R@{1,2,5,10,20}, P@k, MRR@k, F2@k cho từng cột truy hồi, ở hai mức: **văn bản** và **điều**.
Các cột tái lập §5.2 của bài báo (BM25 · NaiveRAG · AdvancedRAG) đứng cạnh các cột LexFlow
(hybrid · +graph · +router) để so trên cùng corpus, cùng bộ câu hỏi. Xem `docs/EVAL-IR.md`
về vì sao KHÔNG so trực tiếp với bảng số trong bài báo.

Kết quả in bảng + lưu JSON vào eval/results/<timestamp>.json để so sánh
giữa các lần chạy (regression gate).

Chạy:  uv run python -u eval/run_benchmark.py   (`-u` = stdout không buffer, thấy tiến độ ngay)
       uv run python -u eval/run_benchmark.py --bo eval/bo_ngan_hang.jsonl   (thêm bộ khác)
Yêu cầu: đã chạy ingest trước (LanceDB có dữ liệu).

Mỗi câu chạy trong try/except riêng: một lỗi mạng thoáng qua (LanceDB Cloud/Neo4j Aura) không
được giết cả lượt đo — câu lỗi bị bỏ qua, ghi lại trong `errors`, và KHÔNG tính vào mẫu số của
các tỷ lệ (accuracy tính trên số câu THÀNH CÔNG, không phải trên `n_cases` tổng).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Chạy như một SCRIPT (`python eval/run_benchmark.py`) đặt `sys.path[0]` là `eval/`, không phải
# gốc repo ⇒ `import app` ném `ModuleNotFoundError`. Trước 10/08 chỗ này được vá bằng cách dặn
# người chạy đặt `PYTHONPATH=.` (xem `docs/KG-CONFORMANCE-v05.md`), tức một bước bắt buộc nằm
# ngoài mã — loại thoả thuận chỉ đúng tới lần đầu có người quên, mà README lại ghi lệnh không
# kèm nó. Tự nối gốc repo vào đường tìm là cách để mọi lệnh trong tài liệu chạy được như đã viết.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.knowledge.lop_phu import chu_thich_ket_qua  # noqa: E402
from app.knowledge.retrieval import (  # noqa: E402
    advanced_rag_search,
    baseline_vector_search,
    bm25_search,
    graph_augmented_search,
    hybrid_search,
)
from app.reasoning.conflict import detect_conflicts  # noqa: E402
from eval import metrics  # noqa: E402
from eval.bo_cau_hoi import CauHoi, nap  # noqa: E402

QUESTIONS = Path("eval/questions.jsonl")
RESULTS_DIR = Path("eval/results")

#: Chiều sâu truy hồi cho tầng IR — đủ cho mốc lớn nhất bài báo báo cáo (R@20).
_K_IR = 20

#: Thứ tự cột trong bảng IR. Ba cột đầu tái lập baseline của bài báo (§5.2), ba cột sau là LexFlow.
_COT_IR = (
    ("bm25", "BM25"),
    ("naive_rag", "Naive RAG"),
    ("advanced_rag", "Advanced RAG"),
    ("lexflow", "LexFlow hybrid"),
    ("lexflow_graph", "LexFlow +graph"),
    ("lexflow_router", "LexFlow +router"),
)

_MUC = (("doc", "văn bản"), ("art", "điều"))


def _docs(chunks: list[dict]) -> set[str]:
    return {c["doc_id"] for c in chunks}


def _run_case(case: CauHoi) -> dict:
    """Chạy một câu qua mọi cột. Ném lỗi ra ngoài — người gọi bắt và ghi lại."""
    q, as_of = case.query, case.as_of
    exp, must_not = case.expected_doc, case.must_not_doc

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
    if case.expect_conflict:
        conflict_found = len(detect_conflicts(o_chunks)) > 0
        g_conflict = len(detect_conflicts(g_chunks)) > 0

    return {
        "query": q,
        "group": case.group,
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
        "expect_conflict": case.expect_conflict,
        "ir": _ir_case(case),
    }


def _ir_case(case: CauHoi) -> dict[str, dict[str, list[str]]]:
    """Truy hồi tới `_K_IR` cho từng cột → khoá xếp hạng ở hai mức (văn bản, điều).

    **Gọi retrieval riêng, không cắt lại kết quả top-6 ở trên.** `hybrid_search` đặt
    `pool = max(top_k*3, 15)`, nên `top_k=20` nhìn thấy nhiều ứng viên hơn `top_k=6` và thứ tự
    RRF có thể khác — lấy `[:6]` của lượt k=20 để tính lại cột cũ sẽ âm thầm đổi nghĩa
    `stale_avoidance`, tức đổi chính cái gate hồi quy. Cái giá là mỗi câu chạy retrieval hai
    lượt; embedding câu hỏi đã được `_qv` cache nên phần đắt nhất không lặp lại.

    Ba cột baseline KHÔNG lọc hiệu lực — đúng như bài báo (§5.2), ở đó không có khái niệm `as_of`.
    """
    q, as_of = case.query, case.as_of
    g20, _ = graph_augmented_search(q, top_k=_K_IR, as_of=as_of, effective_only=True)
    router20, _ = chu_thich_ket_qua(g20, as_of)

    theo_cot = {
        "bm25": bm25_search(q, top_k=_K_IR),
        "naive_rag": baseline_vector_search(q, top_k=_K_IR),
        "advanced_rag": advanced_rag_search(q, top_k=_K_IR),
        "lexflow": hybrid_search(q, top_k=_K_IR, as_of=as_of, effective_only=True),
        "lexflow_graph": g20,
        "lexflow_router": router20,
    }
    return {
        ten: {
            "doc": [c["doc_id"] for c in chunks],
            "art": [metrics.khoa_dieu(c) for c in chunks],
        }
        for ten, chunks in theo_cot.items()
    }


def _tong_hop_ir(cases: list[CauHoi], details: list[dict]) -> dict:
    """Gộp metric IR trên các câu CHẠY ĐƯỢC, theo cột × mức × k.

    Câu có nhãn vàng rỗng ở một mức thì bị loại khỏi mức đó (và chỉ mức đó) — `n` đi kèm mỗi
    mức cho biết mẫu số thật. `relevant_articles` là trường tuỳ chọn nên mức "điều" thường có
    mẫu số nhỏ hơn mức "văn bản"; trộn chung hai mẫu số là cách nhanh nhất để đọc sai bảng.
    """
    ra: dict = {}
    for muc, _ in _MUC:
        vang_theo_cau = [
            list(c.relevant_docs if muc == "doc" else c.relevant_articles) for c in cases
        ]
        ra[muc] = {"n": 0, "cot": {}}
        for ten, _nhan in _COT_IR:
            theo_k: dict[str, dict[str, float]] = {}
            n_dung = 0
            for k in metrics.CAC_MOC_K:
                diem = []
                for d, vang in zip(details, vang_theo_cau):
                    if "ir" not in d or not vang:
                        continue
                    diem.append(metrics.do_mot_cau(d["ir"][ten][muc], vang, k))
                n_dung = len(diem)
                theo_k[f"@{k}"] = metrics.tong_hop(diem)
            ra[muc]["cot"][ten] = theo_k
            ra[muc]["n"] = n_dung
    return ra


def _in_bang_ir(ir: dict) -> None:
    """In theo bố cục Table 3 của bài báo: R@1..20, MRR@2, P@2, F2@2."""
    for muc, ten_muc in _MUC:
        khoi = ir[muc]
        if not khoi["n"]:
            print(f"\nIR — mức {ten_muc}: không câu nào có nhãn vàng ở mức này, bỏ qua.", flush=True)
            continue
        print(f"\nIR — mức {ten_muc} (trên {khoi['n']} câu có nhãn)", flush=True)
        print(
            f"{'Model':<17}{'R@1':>7}{'R@2':>7}{'R@5':>7}{'R@10':>7}{'R@20':>7}"
            f"{'MRR@2':>8}{'P@2':>7}{'F2@2':>7}",
            flush=True,
        )
        print("-" * 76, flush=True)
        for ten, nhan in _COT_IR:
            c = khoi["cot"][ten]
            print(
                f"{nhan:<17}"
                + "".join(f"{c[f'@{k}']['recall']:>7.2f}" for k in metrics.CAC_MOC_K)
                + f"{c['@2']['mrr']:>8.2f}{c['@2']['precision']:>7.2f}{c['@2']['f2']:>7.2f}",
                flush=True,
            )


def evaluate(duong_dan: str | Path = QUESTIONS) -> dict:
    cases = nap(duong_dan)
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

    print(f"\n=== BỘ CÂU HỎI: {duong_dan} ({n} câu) ===", flush=True)
    print(f"{'#':<4}{'Câu hỏi':<55} {'Baseline':<18} {'LexFlow':<18}", flush=True)
    print("-" * 96, flush=True)
    for i, case in enumerate(cases, start=1):
        q = case.query
        try:
            r = _run_case(case)
        except Exception as exc:  # noqa: BLE001 — một câu lỗi không được giết cả lượt đo
            print(f"{i:<4}{q[:53]:<55} LỖI: {exc!r}", flush=True)
            errors.append({"query": q, "error": repr(exc), "traceback": traceback.format_exc()})
            details.append({"query": q, "group": case.group, "error": repr(exc)})
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
    ir = _tong_hop_ir(cases, details)
    summary = {
        "bo_cau_hoi": str(duong_dan),
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
        "ir_metrics": ir,
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
    print("-" * 96, flush=True)
    _in_bang_ir(ir)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    ten_bo = Path(duong_dan).stem
    out = RESULTS_DIR / (f"{stamp}.json" if ten_bo == "questions" else f"{stamp}-{ten_bo}.json")
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


def main() -> list[dict]:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--bo",
        action="append",
        default=None,
        help="Bộ câu hỏi .jsonl (lặp lại được). Mặc định: eval/questions.jsonl",
    )
    args = ap.parse_args()
    return [evaluate(p) for p in (args.bo or [QUESTIONS])]


if __name__ == "__main__":
    main()
