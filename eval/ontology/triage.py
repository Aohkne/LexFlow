"""Xếp hạng các bản ghi bị gắn cờ trong `pred.jsonl` theo MỨC ĐÁNG ĐỌC.

Vì sao cần: 82 cảnh báo nằm trên 28/49 bản ghi. Đọc tuần tự cả 94 đơn vị là việc mà
người duyệt sẽ bỏ dở — và bỏ dở thì bỏ đúng phần cuối, chỗ không ai chọn. Nhưng 82 cảnh
báo đó **không cùng mức**: một cái nói *"không xác định được 'và' hay 'hoặc'"* (đọc sai
là đảo phép logic của cả khoản) nằm cùng một danh sách với một cái nói *"quote mất `a )`"*
(mất đúng ký hiệu đánh số, không mất chữ nào của luật).

Nên ở đây cờ được xếp thành 5 mức theo **hậu quả nếu bỏ qua**, không theo tần suất:

    T1  máy đã tự quyết thay người  — nới lỏng lỗi cứng, tự gộp span, tự lùi span
    T2  phép logic chưa xác định    — 'và' hay 'hoặc'; đọc sai là đảo nghĩa pháp lý
    T3  (bỏ trống — xem dưới)
    T4  neo sai phạm vi             — quote thu hẹp sai chỗ, span vắt qua nhiều điểm
    T5  ít giá trị đọc              — nhãn tóm lược, quote mất marker, THÊM dấu hiệu của
                                      một nhóm nguồn ĐÃ CÓ

T5 cố ý vẫn được đếm và in số, không bị xoá: một loại cờ bị ẩn đi thì lần sau không ai
biết nó còn tồn tại. Nhưng nó không vào hàng đợi duyệt.

**T3 "nghi bịa tình thái" bỏ trống từ 04/08.** Nó từng gom 9 cờ `thêm dấu hiệu …`, và người
duyệt chấm **8/9 là báo động giả**. Không phải mô hình bỗng tốt lên — mà mức T3 **đặt sai từ
đầu**, và chính `app/ontology/modality.py:65-68` đã viết trước điều đó:

> *"thêm số lần xuất hiện của một nhóm **đã có sẵn** thì không [phải bịa] — đó thường chỉ là
> **phân phối lệnh cấm ra từng vế**, hoặc **thay từ đồng nghĩa**."*

Đối chiếu chữ luật thì cả 9 cờ đúng hai dạng đó: TT40 Đ25 k5 luật viết *"không được…; không
được phép…"* rồi tỉnh lược vế ba, mô hình viết rõ ra; bốn ca *"khi"* là luật viết *"(trong)
trường hợp"* — **cùng nhóm `dieu_kien`** trong từ điển. Tín hiệu bịa THẬT là `invented_groups`
(nguồn **không có** dấu hiệu nào thuộc nhóm) và nó đã là **lỗi cứng**, không phải cảnh báo —
hiện **0/49**. Nên `added` chuyển xuống T5: vẫn đếm, không chiếm chỗ trong hàng đợi.

Giữ số hiệu T3 trống thay vì đánh số lại T4→T3: mọi bản `flag_verdicts.jsonl` đã duyệt đều
ghi `tier`, đánh số lại sẽ làm nhãn cũ trỏ sai mức trong im lặng.

Từng có mức **T6 · khuyết tật hệ thống** gom 19 cờ "điểm không tồn tại" (13 bản ghi) thành
một dòng, để người duyệt khỏi quyết 19 lần cho cùng một lỗi. Nay bỏ: cờ đó đã bị xoá **tận
gốc** — `source_diem` suy từ nhãn parser thay vì lấy lời khai của LLM (`docs/ONTOLOGY-POC.md`
§14d), nên không còn gì để gom. Giữ lại một bộ dò không bao giờ khớp sẽ khiến người đọc sau
tưởng chỗ đó vẫn đang được canh.

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

#: Bản sao của `app.ontology.extractor.KHONG_RO_DIEM`. Không import trực tiếp vì file này
#: cố ý chạy được ở dạng đường dẫn trần (`python eval/ontology/triage.py`), lúc đó gói
#: `app` không nằm trên `sys.path`. `tests/test_ontology_diem_suy.py` canh hai bên khớp.
KHONG_RO_DIEM = "(không rõ điểm)"

# (mức, nhãn, mẫu nhận diện). Thứ tự QUAN TRỌNG: khớp mẫu đầu tiên thắng, nên mẫu hẹp
# phải đứng trước mẫu rộng — "hạ mức" phải bắt trước "quote không nằm trong".
_RULES: list[tuple[int, str, re.Pattern[str]]] = [
    (1, "máy tự hạ lỗi cứng xuống cảnh báo", re.compile(r"hạ mức '")),
    (1, "máy tự gộp span của mô hình", re.compile(r"đã gộp đơn vị")),
    (1, "máy tự lùi về span đơn vị", re.compile(r"lùi về span đơn vị")),
    # Hai mã phải đếm ĐỘC LẬP: câu hỏi bàn giao cho người khác nhau, nên công sức duyệt
    # cũng khác. Mã hẹp đứng trước mã rộng — cả hai đều chứa cụm "'và' hay 'hoặc'".
    # Miền ĐÃ khai nhưng guard chưa phủ hết ⇒ câu hỏi cụ thể nhất trong cả bảng này, và là
    # câu hỏi PHÁP LÝ thật: phần bỏ sót là đúng chỗ AND (miễn trừ) khác OR (bất khả thi).
    (2, "guard chưa phủ hết miền — hỏi phần bỏ sót", re.compile(r"tiet_guard_thieu_gia_tri")),
    (2, "tiết đã có guard — xác nhận loại trừ nhau", re.compile(r"tiet_semicolon_guard_da_phu")),
    (2, "chưa xác định 'và' hay 'hoặc'", re.compile(r"'và' hay 'hoặc'")),
    # T5 chứ không phải T3 — xem docstring. Nhóm ràng buộc nguồn ĐÃ CÓ, chỉ khác số lần
    # xuất hiện hoặc khác từ đồng nghĩa; bịa thật thì `invented_groups` bắt thành LỖI CỨNG.
    (5, "THÊM dấu hiệu của nhóm nguồn đã có", re.compile(r"thêm dấu hiệu")),
    # Guard không tách được ⇒ phần tử KHÔNG mang điều kiện áp dụng, tức phạm vi của nó
    # RỘNG HƠN luật ("chỉ áp dụng cho thẻ trả trước" thành "áp dụng cho mọi thẻ"). Không
    # sai dữ liệu, nhưng mất ràng buộc — cùng họ hậu quả với neo sai phạm vi.
    (4, "guard không tách được — phạm vi rộng hơn luật", re.compile(r"guard_ngoai_mau")),
    # Nhiều guard khác nhau trong một đơn vị ⇒ chúng gắn vào những danh ngữ khác nhau.
    # Máy KHÔNG chọn hộ: bản đầu chọn cụm đầu tiên và sinh ra guard bất khả thi
    # `cá nhân ∧ tổ chức` cho tiết (ii) — lỗi im lặng, 2/2 ca có guard ở cả hai tầng.
    (4, "nhiều guard trong một đơn vị — không chọn hộ", re.compile(r"guard_nhieu_cum")),
    (4, "quote thu hẹp sai chỗ", re.compile(r"thu hẹp sai chỗ")),
    # Hai mã thay cho "điểm không tồn tại". Cờ cũ hỏi người một câu mà **parser đã biết
    # đáp án** (Khoản có chẻ Điểm hay không) nên nó bị xoá tận gốc: `source_diem` nay suy
    # từ nhãn parser dán lên `units`. Hai mã dưới đây là phần CÒN LẠI, tức những chỗ máy
    # thật sự không quyết được và phải mở luật ra đọc.
    (4, "span vắt qua nhiều điểm", re.compile(r"diem_vat_nhieu_diem")),
    (4, "khai điểm nhưng neo ra ngoài mọi điểm", re.compile(r"diem_khai_lech")),
    (4, "span không bao hết các tiết", re.compile(r"span không bao hết")),
    (4, "cổng thời gian thiếu mốc ngày", re.compile(r"chưa tách được mốc ngày")),
    # Máy ĐÃ quyết được từ chữ luật ⇒ không có câu hỏi nào bàn giao cho người, nên không
    # vào hàng đợi. Nhưng vẫn phải đếm: đây là một MẪU (khác liên từ "hoặc" vốn là một
    # từ), và mẫu thì sai được — soát lại rẻ hơn nhiều so với phát hiện muộn.
    (5, "phép nối tiết đọc từ câu bao trùm", re.compile(r"tiet_logic_tu_chapeau")),
    # Máy đã CHỨNG MINH connector vô hại bằng bảng phân hoạch ⇒ không còn câu hỏi nào bàn
    # giao. Vẫn đếm: chứng minh dựa trên dữ liệu người viết, mà dữ liệu người viết thì sai được.
    (5, "guard phủ trọn miền — connector vô hại", re.compile(r"tiet_guard_phan_hoach")),
    (5, "nhãn tóm lược: MẤT dấu hiệu", re.compile(r"mất dấu hiệu")),
    (5, "quote lệch marker/dấu câu", re.compile(r"quote không nằm trong")),
]

TIER_NAME = {
    # triage() gán tier 0 cho `errors` từ ngày đầu, nhưng khoá này chỉ cần đến khi
    # pred.jsonl CÓ record lỗi cứng — lần đầu là TT15-Đ20k3/TT40-Đ8k1 (13/08).
    0: "T0 · lỗi cứng — record bị loại khỏi Policy Graph",
    1: "T1 · máy đã tự quyết thay người",
    2: "T2 · phép logic chưa xác định",
    # T3 giữ trống: `flag_verdicts.jsonl` đã duyệt có ghi `tier`, đánh số lại sẽ làm nhãn
    # cũ trỏ sai mức trong im lặng. Xem docstring về lý do nhóm này xuống T5.
    3: "T3 · (bỏ trống — 'nghi bịa tình thái' đã chuyển xuống T5)",
    4: "T4 · neo sai phạm vi",
    5: "T5 · ít giá trị đọc",
    6: "T6 · (bỏ trống — khuyết tật hệ thống đã xoá tận gốc)",
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
        out.append(
            {
                "id": r["id"],
                "type": r.get("type", "?"),
                "worst": min(f[0] for f in flags),
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
        # `source_diem` nay suy từ parser nên "không rõ điểm" là kết quả THƯỜNG GẶP, không
        # còn là ca hiếm: 19/102 điều kiện. Không ánh xạ ngược thì đúng những điều kiện đó
        # tra ra rỗng và người duyệt thấy cảnh báo không kèm chữ của luật.
        hits = [
            c for c in row.get("conditions", [])
            if (c.get("source_diem") or None) == (None if want == KHONG_RO_DIEM else want)
        ]
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
