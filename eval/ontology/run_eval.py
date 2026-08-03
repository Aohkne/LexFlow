"""Đo chất lượng trích Compliance Unit so với bộ nhãn người gán.

Vì sao cần bộ nhãn: `char_span` chỉ chứng minh TÍNH TRUNG THÀNH (mô hình không bịa
chữ), không chứng minh TÍNH ĐÚNG ĐẮN (đây có thật là Subject không? phân rã vậy có
đúng không?). Một trích xuất neo hoàn hảo vẫn có thể phân tích sai. Hai thứ đó cần
hai cơ chế khác nhau — đây là cơ chế thứ hai.

Quy trình maker-checker, giống `app/ingestion/extract.py`:
  1. máy trích  : uv run python -m app.ontology --batch data/fixtures
  2. người duyệt: đọc HTML (--html), sửa JSONL trong editor → eval/ontology/gold.jsonl
  3. đo         : uv run python eval/ontology/run_eval.py

Chạy:  uv run python eval/ontology/run_eval.py [--pred ...] [--gold ...]
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

_IOU_THRESHOLD = 0.8


def load_jsonl(path: Path) -> dict[str, dict]:
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return {r["id"]: r for r in rows}


def iou(a: list | tuple | None, b: list | tuple | None) -> float:
    """Chồng lấn ký tự giữa hai span (Jaccard 1 chiều). 0 nếu thiếu một bên."""
    if not a or not b:
        return 0.0
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = max(a[1], b[1]) - min(a[0], b[0])
    return inter / union if union else 0.0


def _span(field: dict | None) -> list | None:
    g = (field or {}).get("grounding") or {}
    return g.get("char_span")


class Metric:
    """Đếm có LOẠI KHỎI MẪU SỐ — theo đúng quy ước đã dùng hai chỗ trong repo:
    `review._score` (chỉ tính verdict có trong _WEIGHT) và `run_benchmark`
    (`conflict_total`). Trường gold để `null` = không áp dụng, không phải sai."""

    def __init__(self) -> None:
        self.hit = 0
        self.total = 0
        self.skipped = 0

    def add(self, applicable: bool, ok: bool) -> None:
        if not applicable:
            self.skipped += 1
            return
        self.total += 1
        self.hit += bool(ok)

    @property
    def value(self) -> float | None:
        return round(self.hit / self.total, 4) if self.total else None

    def as_dict(self) -> dict:
        return {"value": self.value, "hit": self.hit, "total": self.total, "skipped": self.skipped}


def evaluate(pred: dict[str, dict], gold: dict[str, dict]) -> dict:
    span_exact = Metric()
    span_iou = Metric()
    subject_source = Metric()
    logic = Metric()
    role = Metric()
    cond_tp = cond_fp = cond_fn = 0
    cond_span_iou = Metric()
    hard_error = Metric()
    missing = sorted(set(gold) - set(pred))
    details = []

    for cu_id, g in gold.items():
        p = pred.get(cu_id)
        if p is None:
            continue
        row: dict = {"id": cu_id}

        # Hai vai, hai bộ trường span. Trước khi tách kiểu, meta-CU luôn có
        # `subject_span=null` và bị `applicable=False` bỏ qua — đúng kết quả nhưng vì
        # lý do sai: nó bị bỏ qua như một ô "chưa gán", trong khi ô đó KHÔNG TỒN TẠI.
        cap = (
            (("menh_de", "menh_de_span"),)
            if g.get("type") == "meta_cu"
            else (("subject", "subject_span"), ("action", "action_span"))
        )
        for name, key in cap:
            gs, ps = g.get(key), _span(p.get(name))
            applicable = gs is not None
            span_exact.add(applicable, ps is not None and list(ps) == list(gs or []))
            score = iou(gs, ps)
            span_iou.add(applicable, score >= _IOU_THRESHOLD)
            if applicable:
                row[f"{name}_iou"] = round(score, 3)

        subject_source.add(
            g.get("subject_source") is not None,
            p.get("subject_source") == g.get("subject_source"),
        )
        logic.add(g.get("logic") is not None, p.get("logic") == g.get("logic"))
        # Vai do bước phân loại gán. Đo riêng vì nó là phán quyết ĐỘC LẬP với span:
        # một CU neo hoàn hảo nhưng gán nhầm meta_cu sẽ không bao giờ bị phán định
        # vi phạm — sai kiểu đó không hiện ra ở bất kỳ chỉ số span nào.
        role.add(g.get("type") is not None,
                 p.get("type", "actor_cu") == g.get("type"))
        if g.get("type") is not None:
            row["type"] = g["type"]
            row["type_khop"] = p.get("type", "actor_cu") == g["type"]

        # Điều kiện: khớp theo source_diem. Khoản không chẻ điểm → khoá theo thứ tự.
        gc = {(c.get("source_diem") or f"#{i}"): c for i, c in enumerate(g.get("conditions") or [])}
        pc = {(c.get("source_diem") or f"#{i}"): c for i, c in enumerate(p.get("conditions") or [])}
        cond_tp += len(gc.keys() & pc.keys())
        cond_fp += len(pc.keys() - gc.keys())
        cond_fn += len(gc.keys() - pc.keys())
        for k in gc.keys() & pc.keys():
            cond_span_iou.add(gc[k].get("span") is not None,
                              iou(gc[k].get("span"), _span(pc[k])) >= _IOU_THRESHOLD)

        # Bộ nhãn ghi `expect_hard_error` cho case cố tình cài lỗi; mặc định là False.
        hard_error.add(True, bool(p.get("errors")) == bool(g.get("expect_hard_error", False)))
        row["errors"] = len(p.get("errors") or [])
        details.append(row)

    prec = cond_tp / (cond_tp + cond_fp) if (cond_tp + cond_fp) else None
    rec = cond_tp / (cond_tp + cond_fn) if (cond_tp + cond_fn) else None
    f1 = round(2 * prec * rec / (prec + rec), 4) if prec and rec else None

    return {
        "n_gold": len(gold),
        "n_pred": len(pred),
        "n_scored": len(details),
        "missing_from_pred": missing,
        "span_exact": span_exact.as_dict(),
        f"span_iou_ge_{_IOU_THRESHOLD}": span_iou.as_dict(),
        "role_accuracy": role.as_dict(),
        "subject_source_accuracy": subject_source.as_dict(),
        "logic_accuracy": logic.as_dict(),
        "condition_set": {
            "precision": round(prec, 4) if prec is not None else None,
            "recall": round(rec, 4) if rec is not None else None,
            "f1": f1,
            "tp": cond_tp, "fp": cond_fp, "fn": cond_fn,
        },
        "condition_span_iou": cond_span_iou.as_dict(),
        "hard_error_agreement": hard_error.as_dict(),
        "details": details,
    }


def _fmt(m: dict) -> str:
    v = "—" if m["value"] is None else f"{m['value']:.3f}"
    return f"{v:>6}  ({m['hit']}/{m['total']}, bỏ qua {m['skipped']})"


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description="Đo trích Compliance Unit so với gold")
    ap.add_argument("--pred", default="eval/ontology/pred.jsonl")
    ap.add_argument("--gold", default="eval/ontology/gold.jsonl")
    ap.add_argument("--results-dir", default="eval/ontology/results")
    args = ap.parse_args(argv)

    pred, gold = load_jsonl(Path(args.pred)), load_jsonl(Path(args.gold))
    summary = evaluate(pred, gold)

    print(f"gold={summary['n_gold']}  pred={summary['n_pred']}  chấm={summary['n_scored']}")
    if summary["missing_from_pred"]:
        print(f"THIẾU trong pred: {', '.join(summary['missing_from_pred'])}")
    print(f"span khớp chính xác        {_fmt(summary['span_exact'])}")
    print(f"span IoU >= {_IOU_THRESHOLD}            {_fmt(summary[f'span_iou_ge_{_IOU_THRESHOLD}'])}")
    print(f"vai (actor/meta) accuracy  {_fmt(summary['role_accuracy'])}")
    print(f"subject_source accuracy    {_fmt(summary['subject_source_accuracy'])}")
    print(f"logic accuracy             {_fmt(summary['logic_accuracy'])}")
    c = summary["condition_set"]
    print(f"condition set F1           {c['f1']}  (P={c['precision']} R={c['recall']}, "
          f"tp={c['tp']} fp={c['fp']} fn={c['fn']})")
    print(f"condition span IoU         {_fmt(summary['condition_span_iou'])}")
    print(f"khớp phán định lỗi cứng    {_fmt(summary['hard_error_agreement'])}")

    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    out = Path(args.results_dir) / f"{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"run_at": stamp, **summary}, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"\nĐã ghi {out}")
    return summary


if __name__ == "__main__":
    main()
