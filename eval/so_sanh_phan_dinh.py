"""So sánh các model trên tầng PHÁN ĐỊNH mâu thuẫn — đo cả hai chiều, và đo độ ổn định.

Vì sao tách khỏi `run_benchmark.py`:

* **Chỉ 14/50 lượt gọi API của benchmark phụ thuộc model phán định.** Chạy lại cả 36 câu cho
  mỗi model là trả tiền và thời gian để đo lại retrieval — thứ không đổi theo model. Ở đây
  retrieval chạy **một lần**, kết quả dùng chung cho mọi model, nên khác biệt đo được là của
  riêng phán định.
* **`run_benchmark` chỉ gọi `detect_conflicts` khi `expect_conflict` là true** (7/36 câu), nên
  `conflict_recall` **không có đối trọng precision**: một bộ phát hiện báo động mọi thứ vẫn
  đạt 7/7. Ở đây 29 câu còn lại cũng chạy qua bộ phát hiện để đếm **dương tính giả**.
* Phán định LLM không tất định, nên mỗi ca chạy nhiều lượt và báo **độ ổn định** (bao nhiêu
  lượt cho cùng kết luận). Một model đúng 3/3 khác hẳn một model đúng 2/3.

    uv run python -u eval/so_sanh_phan_dinh.py
    uv run python -u eval/so_sanh_phan_dinh.py --models gemini-2.5-flash-lite,gemini-2.5-pro \
        --lap 3 --mau-am 12

Kết quả ghi vào `eval/results/sosanh-<timestamp>.json` và tóm tắt vào `docs/EVAL-COMPLIANCE.md`.
KHÔNG đụng `.env`: model đặt qua `settings.gemini_reasoning_model` ngay trước mỗi lượt gọi.
"""
from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from app.core import llm
from app.core.config import settings
from app.knowledge.retrieval import hybrid_search
from app.reasoning.conflict import detect_conflicts

QUESTIONS = Path("eval/questions.jsonl")
RESULTS_DIR = Path("eval/results")

#: Giá paid tier, USD / 1M token — tra ngày 2026-08-10 tại ai.google.dev/gemini-api/docs/pricing.
#: Để ở đây và ghi ngày tra vì giá đổi được; số nào không có trong bảng thì báo, không đoán.
GIA = {
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 10.00),
}


def _dem_token():
    """Bọc client để đọc `usage_metadata` của chính response. Trả (bảng đếm, hàm gỡ)."""
    dem: dict[str, dict[str, int]] = defaultdict(lambda: {"luot": 0, "vao": 0, "ra": 0})
    client = llm.get_client()
    goc = client.models.generate_content

    def _bọc(*a, **k):
        r = goc(*a, **k)
        um = getattr(r, "usage_metadata", None)
        o = dem[k.get("model") or (a[0] if a else "?")]
        o["luot"] += 1
        if um is not None:
            o["vao"] += getattr(um, "prompt_token_count", 0) or 0
            # Token "suy nghĩ" tính theo giá output (bảng giá Gemini) — cộng vào `ra`.
            o["ra"] += (getattr(um, "candidates_token_count", 0) or 0) + (
                getattr(um, "thoughts_token_count", 0) or 0
            )
        return r

    client.models.generate_content = _bọc
    return dem, lambda: setattr(client.models, "generate_content", goc)


def _tien(model: str, vao: int, ra: int) -> float | None:
    gia = GIA.get(model)
    return None if gia is None else vao / 1e6 * gia[0] + ra / 1e6 * gia[1]


def lay_chunks(cases: list[dict]) -> dict[str, list[dict]]:
    """Retrieval MỘT LẦN, dùng chung cho mọi model — khác biệt còn lại là của phán định."""
    ra: dict[str, list[dict]] = {}
    for i, c in enumerate(cases, 1):
        q = c["query"]
        try:
            ra[q] = hybrid_search(q, top_k=6, as_of=c.get("as_of"), effective_only=True)
        except Exception as exc:  # noqa: BLE001 — một câu lỗi mạng không giết cả lượt đo
            print(f"  [{i}/{len(cases)}] LỖI retrieval, bỏ câu: {str(exc)[:90]}")
            continue
        print(f"  [{i}/{len(cases)}] {len(ra[q])} chunk · {q[:60]}")
    return ra


def do_mot_model(model: str, cases: list[dict], chunks: dict, lap: int) -> dict:
    truoc = settings.gemini_reasoning_model
    settings.gemini_reasoning_model = model
    ket: list[dict] = []
    try:
        for i, c in enumerate(cases, 1):
            q = c["query"]
            if q not in chunks:
                continue
            n_lap = lap if c.get("expect_conflict") else 1
            ban = [len(detect_conflicts(chunks[q])) > 0 for _ in range(n_lap)]
            ket.append({
                "query": q,
                "group": c.get("group", ""),
                "expect_conflict": bool(c.get("expect_conflict")),
                "n_lap": n_lap,
                "so_lan_bao": sum(ban),
            })
            dau = "!" if bool(c.get("expect_conflict")) != (sum(ban) > 0) else " "
            print(f"  {dau} [{i}/{len(cases)}] báo {sum(ban)}/{n_lap} · {q[:58]}")
    finally:
        settings.gemini_reasoning_model = truoc
    return {"model": model, "cases": ket}


def tong_hop(kq: dict) -> dict:
    duong = [c for c in kq["cases"] if c["expect_conflict"]]
    am = [c for c in kq["cases"] if not c["expect_conflict"]]
    # Recall tính theo "có bắt được ít nhất một lượt", đúng cách `run_benchmark` tính.
    return {
        "recall_bat_duoc": sum(1 for c in duong if c["so_lan_bao"] > 0),
        "recall_tong": len(duong),
        "on_dinh_tuyet_doi": sum(1 for c in duong if c["so_lan_bao"] == c["n_lap"]),
        "duong_tinh_gia": sum(1 for c in am if c["so_lan_bao"] > 0),
        "am_tong": len(am),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--models", default="gemini-2.5-flash-lite,gemini-2.5-pro")
    ap.add_argument("--lap", type=int, default=3, help="số lượt mỗi ca CÓ mâu thuẫn")
    ap.add_argument("--mau-am", type=int, default=12, help="số ca KHÔNG mâu thuẫn đem đo")
    args = ap.parse_args()

    tat_ca = [json.loads(x) for x in QUESTIONS.read_text(encoding="utf-8").splitlines() if x.strip()]
    duong = [c for c in tat_ca if c.get("expect_conflict")]
    # Lấy đều tay theo thứ tự file — tất định, chạy lại ra cùng bộ mẫu.
    am = [c for c in tat_ca if not c.get("expect_conflict")][: args.mau_am]
    cases = duong + am
    print(f"Bộ đo: {len(duong)} ca CÓ mâu thuẫn (x{args.lap} lượt) + {len(am)} ca KHÔNG (x1)\n")

    print("Retrieval (một lần, dùng chung):")
    chunks = lay_chunks(cases)

    dem, go = _dem_token()
    ket_qua = []
    t0 = time.perf_counter()
    try:
        for m in [x.strip() for x in args.models.split(",") if x.strip()]:
            print(f"\n=== {m} ===")
            t = time.perf_counter()
            kq = do_mot_model(m, cases, chunks, args.lap)
            kq["giay"] = round(time.perf_counter() - t, 1)
            ket_qua.append(kq)
    finally:
        go()

    print(f"\n{'model':<24} {'recall':>8} {'ổn định':>9} {'dương tính giả':>16} {'giây':>7} {'USD':>10}")
    for kq in ket_qua:
        t = tong_hop(kq)
        kq["tong_hop"] = t
        o = dem.get(kq["model"], {"vao": 0, "ra": 0, "luot": 0})
        kq["token"] = o
        tien = _tien(kq["model"], o["vao"], o["ra"])
        kq["usd"] = tien
        print(
            f"{kq['model']:<24} {t['recall_bat_duoc']:>4}/{t['recall_tong']:<3} "
            f"{t['on_dinh_tuyet_doi']:>5}/{t['recall_tong']:<3} "
            f"{t['duong_tinh_gia']:>10}/{t['am_tong']:<5} {kq['giay']:>7} "
            f"{('%.5f' % tien) if tien is not None else 'chưa có giá':>10}"
        )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = RESULTS_DIR / f"sosanh-{stamp}.json"
    out.write_text(
        json.dumps(
            {
                "run_at": stamp,
                "tong_giay": round(time.perf_counter() - t0, 1),
                "lap": args.lap,
                "mau_am": len(am),
                "gia_tra_ngay": "2026-08-10",
                "ket_qua": ket_qua,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"\n→ Đã lưu {out}")


if __name__ == "__main__":
    main()
