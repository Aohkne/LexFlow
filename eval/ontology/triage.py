"""Xếp hạng các bản ghi bị gắn cờ trong `pred.jsonl` theo MỨC ĐÁNG ĐỌC.

Vì sao cần: 82 cảnh báo nằm trên 28/49 bản ghi. Đọc tuần tự cả 94 đơn vị là việc mà
người duyệt sẽ bỏ dở — và bỏ dở thì bỏ đúng phần cuối, chỗ không ai chọn. Nhưng 82 cảnh
báo đó **không cùng mức**: một cái nói *"không xác định được 'và' hay 'hoặc'"* (đọc sai
là đảo phép logic của cả khoản) nằm cùng một danh sách với một cái nói *"quote mất `a )`"*
(mất đúng ký hiệu đánh số, không mất chữ nào của luật).

Nên ở đây cờ được xếp thành 5 mức theo **hậu quả nếu bỏ qua**, không theo tần suất:

    T1  máy đã tự quyết thay người  — nới lỏng lỗi cứng, tự gộp span, tự lùi span
    T2  phép logic chưa xác định    — 'và' hay 'hoặc'; đọc sai là đảo nghĩa pháp lý
    T3  nghi bịa tình thái          — nhãn THÊM dấu hiệu nghĩa vụ/cấm mà nguồn không có
    T4  neo sai phạm vi             — quote thu hẹp sai chỗ, điểm không tồn tại
    T5  ít giá trị đọc              — nhãn tóm lược (MẤT dấu hiệu), quote mất marker

T5 cố ý vẫn được đếm và in số, không bị xoá: một loại cờ bị ẩn đi thì lần sau không ai
biết nó còn tồn tại. Nhưng nó không vào hàng đợi duyệt.

Chạy:
    uv run python eval/ontology/triage.py              # bảng tóm tắt
    uv run python eval/ontology/triage.py --queue      # hàng đợi duyệt, kèm chữ của luật
    uv run python eval/ontology/triage.py --md docs/ONTOLOGY-TRIAGE.md
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

_PRED = Path("eval/ontology/pred.jsonl")

# (mức, nhãn, mẫu nhận diện). Thứ tự QUAN TRỌNG: khớp mẫu đầu tiên thắng, nên mẫu hẹp
# phải đứng trước mẫu rộng — "hạ mức" phải bắt trước "quote không nằm trong".
_RULES: list[tuple[int, str, re.Pattern[str]]] = [
    (1, "máy tự hạ lỗi cứng xuống cảnh báo", re.compile(r"hạ mức '")),
    (1, "máy tự gộp span của mô hình", re.compile(r"đã gộp đơn vị")),
    (1, "máy tự lùi về span đơn vị", re.compile(r"lùi về span đơn vị")),
    (2, "chưa xác định 'và' hay 'hoặc'", re.compile(r"'và' hay 'hoặc'")),
    (3, "nghi bịa: THÊM dấu hiệu tình thái", re.compile(r"thêm dấu hiệu")),
    (4, "quote thu hẹp sai chỗ", re.compile(r"thu hẹp sai chỗ")),
    (4, "điểm không tồn tại trong khoản", re.compile(r"điểm không tồn tại")),
    (4, "span không bao hết các tiết", re.compile(r"span không bao hết")),
    (4, "cổng thời gian thiếu mốc ngày", re.compile(r"chưa tách được mốc ngày")),
    (5, "nhãn tóm lược: MẤT dấu hiệu", re.compile(r"mất dấu hiệu")),
    (5, "quote lệch marker/dấu câu", re.compile(r"quote không nằm trong")),
]

TIER_NAME = {
    1: "T1 · máy đã tự quyết thay người",
    2: "T2 · phép logic chưa xác định",
    3: "T3 · nghi bịa tình thái",
    4: "T4 · neo sai phạm vi",
    5: "T5 · ít giá trị đọc",
    6: "T6 · khuyết tật hệ thống — sửa prompt, không đọc luật",
    9: "T? · chưa phân loại",
}


def classify(warning: str) -> tuple[int, str]:
    for tier, label, pat in _RULES:
        if pat.search(warning):
            return tier, label
    return 9, "chưa phân loại"


def load(path: Path = _PRED) -> list[dict]:
    return [
        json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()
    ]


def _diem_bia_toan_bo(row: dict) -> bool:
    """Mọi `source_diem` mô hình khai đều KHÔNG tồn tại ⇒ Khoản không chẻ Điểm.

    Đo trên corpus: đúng **13** bản ghi như vậy, sinh **19** cờ — nhóm cờ đông nhất.
    Nhưng cả 13 đều có `khoan.diem == []`: mô hình đang dùng `source_diem` như **số
    thứ tự** cho các ý trong một đoạn văn liền, chứ không phải như **địa chỉ** của một
    Điểm có thật. Đó là MỘT khuyết tật của prompt, không phải 13 việc phải đọc luật.

    Suy ra được từ chính `pred.jsonl`, không cần mở fixture: nếu mọi điều kiện có nêu
    điểm đều bị gắn cờ "điểm không tồn tại" thì Khoản không có Điểm nào để mà trỏ tới.
    """
    khai = [c for c in row.get("conditions", []) if c.get("source_diem")]
    if not khai:
        return False
    n_bia = sum(1 for w in row.get("warnings", []) if "điểm không tồn tại" in w)
    return n_bia == len(khai)


def triage(rows: list[dict]) -> list[dict]:
    """Mỗi bản ghi → mức xấu nhất + các cờ, sắp xếp theo mức rồi theo số cờ."""
    out = []
    for r in rows:
        flags = []
        for w in r.get("errors", []):
            flags.append((0, "LỖI CỨNG", w))
        for w in r.get("warnings", []):
            tier, label = classify(w)
            flags.append((tier, label, w))
        if not flags:
            continue
        he_thong = _diem_bia_toan_bo(r)
        # Bản ghi mà cờ DUY NHẤT là khuyết tật hệ thống thì không vào hàng đợi đọc —
        # nó đi vào một dòng tổng kết. Còn cờ loại khác thì vẫn phải đọc.
        con_lai = [f for f in flags if "điểm không tồn tại" not in f[2]]
        worst = min(f[0] for f in (con_lai if (he_thong and con_lai) else flags))
        out.append(
            {
                "id": r["id"],
                "type": r.get("type", "?"),
                "worst": 6 if (he_thong and not con_lai) else worst,
                "he_thong": he_thong,
                "flags": sorted(flags, key=lambda f: f[0]),
                "n": len(flags),
                "row": r,
            }
        )
    return sorted(out, key=lambda d: (d["worst"], -d["n"]))


def _field_text(row: dict, field_path: str) -> tuple[list[str], bool]:
    """'điều kiện c.constraint_label' → (chữ của luật, có mơ hồ địa chỉ không).

    Trả về DANH SÁCH chứ không phải một chuỗi, vì `pred.jsonl` sinh trước ngày
    `extractor.py` đánh số điều kiện trùng điểm vẫn còn nhãn mơ hồ: ND52 Đ22 K2 có
    **5** điều kiện cùng `source_diem="g"`, và cả 5 cảnh báo đều ghi "điều kiện g".
    Lặng lẽ lấy phần tử đầu là đưa người duyệt đọc nhầm đoạn luật — hỏng đúng thứ mà
    công cụ này sinh ra để tránh. Nhãn mới ("điều kiện g#2") thì khớp đúng một.
    """
    m = re.match(r"điều kiện (.+?)(?:\.\w+)?$", field_path)
    if m:
        want = m.group(1)
        idx = None
        if "#" in want:
            want, _, raw_idx = want.partition("#")
            idx = int(raw_idx) if raw_idx.isdigit() else None
        hits = [c for c in row.get("conditions", []) if (c.get("source_diem") or None) == want]
        if idx is not None:
            return ([hits[idx - 1].get("text", "")] if 0 < idx <= len(hits) else [], False)
        return [c.get("text", "") for c in hits], len(hits) > 1
    base = field_path.split(".")[0]
    f = row.get(base)
    return ([f.get("text", "")] if isinstance(f, dict) else []), False


def summary(items: list[dict], rows: list[dict]) -> str:
    by_tier: dict[int, int] = {}
    by_label: dict[tuple[int, str], int] = {}
    for it in items:
        for tier, label, _ in it["flags"]:
            by_tier[tier] = by_tier.get(tier, 0) + 1
            by_label[(tier, label)] = by_label.get((tier, label), 0) + 1

    lines = [
        f"{len(items)}/{len(rows)} bản ghi có cờ · {sum(by_tier.values())} cờ tổng cộng",
        "",
        "| mức | loại cờ | số cờ | số bản ghi ở mức này |",
        "|---|---|---|---|",
    ]
    for tier in sorted(by_tier):
        n_rec = sum(1 for it in items if it["worst"] == tier)
        first = True
        for (t, label), n in sorted(by_label.items()):
            if t != tier:
                continue
            lines.append(
                f"| {TIER_NAME[tier] if first else ''} | {label} | {n} | "
                f"{n_rec if first else ''} |"
            )
            first = False
    return "\n".join(lines)


def queue(items: list[dict], max_tier: int = 4) -> str:
    """Hàng đợi duyệt: chỉ T0–T4, kèm chữ của luật để quyết ngay không phải mở file."""
    out: list[str] = []

    ht = [it for it in items if it["he_thong"]]
    if ht:
        n_co = sum(1 for it in ht for f in it["flags"] if "điểm không tồn tại" in f[2])
        out += [
            f"### [{TIER_NAME[6]}] · {len(ht)} bản ghi · {n_co} cờ",
            "",
            "Mọi `source_diem` mô hình khai đều không tồn tại ⇒ **Khoản không chẻ Điểm nào**. "
            "Mô hình đang dùng `source_diem` như *số thứ tự* cho các ý trong một đoạn liền, "
            "không phải như *địa chỉ*. Một khuyết tật của prompt — **không cần đọc luật bản nào**:",
            "",
        ]
        for it in ht:
            khai = [c.get("source_diem") for c in it["row"].get("conditions", [])]
            out.append(f"- `{it['id']}` — mô hình khai {khai}, Khoản không có Điểm")
        out.append("")

    for it in items:
        if it["worst"] > max_tier:
            continue
        out.append(f"### [{TIER_NAME[it['worst']]}] `{it['id']}`  ·  {it['type']}")
        out.append("")
        for tier, label, w in it["flags"]:
            if tier > max_tier:
                continue
            field = w.split(":", 1)[0].strip() if ":" in w else "—"
            out.append(f"- **{label}** — `{field}`")
            out.append(f"  > {w.split(':', 1)[-1].strip()[:300]}")
            texts, ambiguous = _field_text(it["row"], field)
            if ambiguous:
                out.append(
                    f"  - ⚠️ địa chỉ mơ hồ: {len(texts)} điều kiện cùng mang nhãn này "
                    "(bản ghi sinh trước khi `extractor.py` đánh số) — phải đọc cả:"
                )
            for t in texts:
                t = " ".join(t.split())
                if t:
                    out.append(f"  - chữ của luật: *{t[:280]}*")
        n_hidden = sum(1 for t, _, _ in it["flags"] if t > max_tier)
        if n_hidden:
            out.append(f"- _(ẩn {n_hidden} cờ mức T5)_")
        out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Xếp hạng cờ trong pred.jsonl theo mức đáng đọc")
    ap.add_argument("--queue", action="store_true", help="in hàng đợi duyệt (T0–T4)")
    ap.add_argument("--max-tier", type=int, default=4, help="mức cao nhất đưa vào hàng đợi")
    ap.add_argument("--md", help="ghi báo cáo đầy đủ ra file markdown")
    args = ap.parse_args(argv)

    rows = load()
    items = triage(rows)
    head = summary(items, rows)

    if args.md:
        body = (
            "# Hàng đợi duyệt — các đơn vị bị gắn cờ\n\n"
            "> Sinh bằng `uv run python eval/ontology/triage.py --md <file>`.\n"
            "> Xếp theo **hậu quả nếu bỏ qua**, không theo tần suất. T5 được đếm nhưng\n"
            "> không vào hàng đợi — xem `eval/ontology/triage.py` để biết vì sao.\n\n"
            f"{head}\n\n---\n\n## Hàng đợi (T0–T{args.max_tier})\n\n"
            f"{queue(items, args.max_tier)}"
        )
        Path(args.md).write_text(body, encoding="utf-8")
        print(f"[triage] đã ghi {args.md}")
        return

    print(head)
    if args.queue:
        print()
        print(queue(items, args.max_tier))


if __name__ == "__main__":
    main()
