"""Đo precision/recall của bộ phát hiện mâu thuẫn trên bộ nhãn vàng cấp CẶP ĐIỀU KHOẢN.

Khác `run_benchmark.py`: ở đó `conflict_recall` tính theo **câu hỏi** có gắn `expect_conflict`
và không có precision. Ở đây nhãn gắn vào **cặp** (`eval/mau_thuan_vang.jsonl`), kỳ vọng của
mỗi lượt suy ra từ tập chunk thật sự lấy về, nên nói được cả hai chiều — xem `cham_mau_thuan`.

    uv run python -u eval/do_precision_cap.py
    uv run python -u eval/do_precision_cap.py --model gemini-2.5-pro --mau-am 20

LLM gọi **một lần mỗi ca** (không lọc), rồi chấm hai chính sách trên cùng kết quả — so được
"lọc cặp nội bộ×luật" với "không lọc" mà không tốn gấp đôi lượt gọi.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.knowledge.retrieval import hybrid_search
from app.reasoning.conflict import detect_conflicts

QUESTIONS = Path("eval/questions.jsonl")
RESULTS_DIR = Path("eval/results")

#: Bỏ quá tỷ lệ này thì lượt đo KHÔNG được coi là kết quả. Có chốt vì đã vấp thật ngày
#: 10/08: LanceDB Cloud rớt liên tục, 14/27 ca bị bỏ — trong đó **cả 7 ca có mâu thuẫn** —
#: và bảng tổng kết vẫn in ra `recall 0/0` trông như một con số. Một lượt đo vô hiệu phải
#: nói rằng nó vô hiệu.
TRAN_BO_QUA = 0.15


def _nap_cham():
    spec = importlib.util.spec_from_file_location("cham_mau_thuan", Path("eval/cham_mau_thuan.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _lay_chunks(case: dict, so_lan: int = 4):
    for lan in range(so_lan):
        try:
            return hybrid_search(
                case["query"], top_k=6, as_of=case.get("as_of"), effective_only=True
            )
        except Exception as exc:  # noqa: BLE001 — mạng chập chờn, thử lại rồi mới bỏ
            if lan == so_lan - 1:
                print(f"     bỏ sau {so_lan} lần: {str(exc)[:70]}")
            time.sleep(3 * (lan + 1))
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="gemini-2.5-flash-lite")
    ap.add_argument("--mau-am", type=int, default=20)
    args = ap.parse_args()

    cham = _nap_cham()
    vang = cham.doc_vang()
    settings.gemini_reasoning_model = args.model

    tat_ca = [json.loads(x) for x in QUESTIONS.read_text(encoding="utf-8").splitlines() if x.strip()]
    duong = [c for c in tat_ca if c.get("expect_conflict")]
    cases = duong + [c for c in tat_ca if not c.get("expect_conflict")][: args.mau_am]
    print(f"{args.model} · {len(vang)} cặp vàng · {len(cases)} ca\n")

    luot_all, luot_loc, chi_tiet, bo_qua = [], [], [], 0
    for c in cases:
        ch = _lay_chunks(c)
        if ch is None:
            bo_qua += 1
            continue
        ids = [x["id"] for x in ch]
        theo_title = {x["doc_title"]: (x["doc_id"], x["source"]) for x in ch}
        al = detect_conflicts(ch, chi_noi_bo_voi_luat=False)

        def _dc(title: str, art: str) -> str:
            return f"{theo_title.get(title, (title, '?'))[0]}::{art}"

        bao_all = [(_dc(a.doc_a, a.article_a), _dc(a.doc_b, a.article_b)) for a in al]
        bao_loc = [
            (_dc(a.doc_a, a.article_a), _dc(a.doc_b, a.article_b))
            for a in al
            if {theo_title.get(a.doc_a, ("", "?"))[1], theo_title.get(a.doc_b, ("", "?"))[1]}
            == {"internal", "external"}
        ]
        k_all, k_loc = cham.cham(vang, ids, bao_all), cham.cham(vang, ids, bao_loc)
        luot_all.append(k_all)
        luot_loc.append(k_loc)
        chi_tiet.append({
            "query": c["query"], "ky_vong": k_all["ky_vong"],
            "bat_khong_loc": k_all["bat_duoc"], "bat_co_loc": k_loc["bat_duoc"],
            "gia_khong_loc": k_all["duong_tinh_gia"], "gia_co_loc": k_loc["duong_tinh_gia"],
            "bo_sot": k_loc["cap_bo_sot"],
        })
        print(f"  kỳ vọng {k_all['ky_vong']} · bắt {k_loc['bat_duoc']} · thừa "
              f"{k_all['duong_tinh_gia']}→{k_loc['duong_tinh_gia']} · {c['query'][:46]}")

    ty_le_bo = bo_qua / len(cases)
    bang = {"khong_loc": cham.gop(luot_all), "chi_noi_bo": cham.gop(luot_loc)}
    print()
    for ten, g in (("A · không lọc", bang["khong_loc"]), ("C · chỉ nội bộ×luật", bang["chi_noi_bo"])):
        print(f"{ten:<22} recall {g['bat_duoc']}/{g['ky_vong']} = {g['recall']}   "
              f"precision {g['bao'] - g['duong_tinh_gia']}/{g['bao']} = {g['precision']}")

    hop_le = ty_le_bo <= TRAN_BO_QUA and bang["khong_loc"]["ky_vong"] > 0
    print(f"\nbỏ qua {bo_qua}/{len(cases)} ca ({ty_le_bo:.0%})")
    if not hop_le:
        print("*** LƯỢT ĐO VÔ HIỆU — bỏ quá nhiều ca hoặc không ca nào có kỳ vọng. "
              "Đừng dùng số ở trên; chạy lại khi hạ tầng ổn. ***")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = RESULTS_DIR / f"precision-cap-{stamp}.json"
    out.write_text(
        json.dumps({
            "run_at": stamp, "model": args.model, "hop_le": hop_le,
            "bo_qua": bo_qua, "n_ca": len(cases), "n_cap_vang": len(vang),
            **bang, "chi_tiet": chi_tiet,
        }, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"→ {out}")
    raise SystemExit(0 if hop_le else 1)


if __name__ == "__main__":
    main()
