"""CLI GraphCompliance POC: đối chiếu hợp đồng docx, sinh báo cáo Markdown side-by-side.

Chạy:
    uv run python -m app.compliance <docx> --against ND52-2024 --corpus data/corpus.sample.json

`--bo-duong-cu` bỏ hẳn `run_review` (đường cũ) để chạy nhanh — dùng cho smoke test
hoặc khi chỉ cần xem đường mới.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.compliance import hypernym
from app.compliance.er_triples import trich_triples
from app.compliance.gate import lap_cu_plan
from app.compliance.hop_dong import parse_hop_dong, to_corpus_document
from app.compliance.hypernym import map_hypernym
from app.compliance.judge import phan_dinh
from app.compliance.policy_graph import PolicyGraph
from app.compliance.report import render_md
from app.core.schemas import ReviewFinding
from app.ingestion.pipeline import load_corpus
from app.ingestion.versioning import today_iso
from app.reasoning.review import run_review

#: Tiền tố cảnh báo "ca lạ" gán sẵn trên CU (Task 4) — nguong_bo_sot/tinh_thai_kho.
_CANH_BAO_CU_PREFIX = ("nguong_bo_sot", "tinh_thai_kho")


def _tai_gold(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(dg) for dg in path.read_text(encoding="utf-8").splitlines() if dg.strip()]


def _canh_bao_cu(pg: PolicyGraph, cu_ids: set[str]) -> list[str]:
    return [
        f"{cid}: {w}"
        for cid in sorted(cu_ids)
        if (cu := pg.cu.get(cid)) is not None
        for w in cu.warnings
        if w.startswith(_CANH_BAO_CU_PREFIX)
    ]


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m app.compliance",
                                 description="Đối chiếu hợp đồng docx với luật — POC.")
    p.add_argument("docx", type=Path)
    p.add_argument("--against", nargs="+", required=True, help="so_hieu văn bản đối chiếu")
    p.add_argument("--corpus", type=Path, required=True, help="đường dẫn corpus cho load_corpus")
    p.add_argument("--gold", type=Path, default=Path("eval/compliance/gold.jsonl"))
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--as-of", default=None)
    p.add_argument("--cu-dir", type=Path, default=Path("eval/ontology"))
    p.add_argument("--bo-duong-cu", action="store_true",
                    help="bỏ run_review (đường cũ) để chạy nhanh")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> Path:
    args = _parse_args(argv)
    as_of = args.as_of or today_iso()
    hd = parse_hop_dong(args.docx)

    cu: dict[str, ReviewFinding] = {}
    if not args.bo_duong_cu:
        resp = run_review(to_corpus_document(hd), args.against, as_of)
        cu = {f.article.removeprefix("Điều "): f for f in resp.findings}

    docs, _rels = load_corpus(args.corpus)
    so_hieu_cua = {d.doc_id: d.so_hieu for d in docs}
    pg = PolicyGraph.load(args.cu_dir)
    tv = hypernym.TuVungLuat.tu_policy_graph(pg, embed=hypernym.embed_documents)

    moi: dict[str, list[dict]] = {}
    canh_bao: list[str] = []
    cu_dung_toi: set[str] = set()
    for d in hd.dieu:
        triples, canh_bao_tr = trich_triples(d.text)
        canh_bao += canh_bao_tr
        entities = sorted({t.chu_the for t in triples} | {t.doi_tuong for t in triples})
        hyp_map = map_hypernym(entities, tv)
        hypernyms = [v for v in hyp_map.values() if v is not None]
        plan = lap_cu_plan(d.text, hypernyms, pg, args.against, as_of, so_hieu_cua)
        canh_bao += plan.ghi_chu
        cu_dung_toi.update(item.cu.id for item in plan.items)
        moi[d.so] = [pq.model_dump() for pq in phan_dinh(d.text, plan, pg)]

    canh_bao += _canh_bao_cu(pg, cu_dung_toi)
    gold_rows = _tai_gold(args.gold)
    report = render_md(hd, gold_rows, cu, moi, canh_bao)

    out = args.out or Path("eval/compliance") / f"bao_cao_{hd.ten}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    return out


if __name__ == "__main__":
    main()
