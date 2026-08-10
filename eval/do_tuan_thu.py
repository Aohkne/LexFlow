"""Chạy `review.py` trên 4 văn bản nội bộ SHB rồi chấm trên bộ nhãn sạch.

    uv run python -u eval/do_tuan_thu.py
    uv run python -u eval/do_tuan_thu.py --lap 2 --model gemini-2.5-flash-lite

Phạm vi đối chiếu là **toàn bộ văn bản external** trong corpus, không phải nhóm đã chọn sẵn:
đó là ca khó và trung thực hơn — người dùng thật không biết trước điều nội bộ này va vào luật
nào. Mỗi điều tốn 1 lượt truy hồi + 2–3 lượt phán định (`review._judge` self-consistency).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.core.schemas import CorpusDocument
from app.reasoning.review import run_review

CORPUS = Path("data/corpus.real.json")
RESULTS_DIR = Path("eval/results")


def _nap_cham():
    spec = importlib.util.spec_from_file_location("cham_tuan_thu", Path("eval/cham_tuan_thu.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="gemini-2.5-flash-lite")
    ap.add_argument("--lap", type=int, default=1, help="số lượt chạy lại để xem độ ổn định")
    args = ap.parse_args()

    cham = _nap_cham()
    vang = cham.doc_vang()
    settings.gemini_reasoning_model = args.model

    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    noi_bo = [d for d in corpus["documents"] if d["source"] == "internal"]
    against = [d["doc_id"] for d in corpus["documents"] if d["source"] == "external"]
    print(f"{args.model} · {len(noi_bo)} văn bản nội bộ · đối chiếu với {len(against)} văn bản "
          f"external · {len(vang)} mục có nhãn\n")

    cac_luot = []
    for lan in range(1, args.lap + 1):
        phan_dinh: dict[str, str] = {}
        for d in noi_bo:
            kq = run_review(CorpusDocument.model_validate(d), against, as_of="2025-01-01")
            for f in kq.findings:
                phan_dinh[f"{d['doc_id']}::{f.article}"] = f.verdict
            print(f"  [lượt {lan}] {d['doc_id']:<18} điểm {kq.score:>3} · "
                  + " ".join(f"{k}={v}" for k, v in kq.counts.items() if v))
        c = cham.cham(vang, phan_dinh)
        cac_luot.append({"lan": lan, **c, "phan_dinh": phan_dinh})
        print(f"  [lượt {lan}] đúng {c['dung']} · nửa đúng {c['nua_dung']} · sai {c['sai']} "
              f"· chưa đánh giá {c['chua_danh_gia']}  (tỷ lệ đúng {c['ty_le_dung']})")
        for x in cham.bo_sot_vi_pham(c):
            print(f"      *** NÓI ĐẠT VỀ MỘT VI PHẠM: {x['noi_bo']} — {x['mo_ta'][:70]}")

    print("\nTừng mục có nhãn, qua các lượt:")
    for c in vang:
        thuc = [lt["phan_dinh"].get(c["noi_bo"], "—") for lt in cac_luot]
        on_dinh = "" if len(set(thuc)) == 1 else "   ← KHÔNG ỔN ĐỊNH"
        print(f"  {c['noi_bo']:<28} vàng={c['verdict']:<10} thực={thuc}{on_dinh}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = RESULTS_DIR / f"tuan-thu-{stamp}.json"
    out.write_text(
        json.dumps({"run_at": stamp, "model": args.model, "lap": args.lap,
                    "n_vang": len(vang), "luot": cac_luot}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"\n→ {out}")


if __name__ == "__main__":
    main()
