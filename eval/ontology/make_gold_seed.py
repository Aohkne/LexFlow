"""Sinh KHUNG bộ nhãn từ dự đoán của máy — bước 2 của maker-checker.

QUAN TRỌNG: file sinh ra là `gold.seed.jsonl`, KHÔNG phải `gold.jsonl`. Nó là đề
xuất của máy, chưa phải nhãn. Người duyệt phải:
  1. mở trang HTML tương ứng (sinh bằng `--html-dir`),
  2. sửa các span/nhãn sai trong file,
  3. đổi `reviewed` thành true,
  4. đổi tên/gộp vào `gold.jsonl`.
`run_eval.py` chỉ đọc `gold.jsonl`, nên quên bước 4 thì không đo được — cố ý.

Rủi ro đã biết: gán trên nền output của máy có thể gây ANCHORING (người duyệt xuôi
theo đề xuất). Đổi lại nhanh hơn gán tay khoảng 5 lần. Ghi rõ khi báo cáo.

Chạy:  uv run python eval/ontology/make_gold_seed.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _span(field: dict | None) -> list | None:
    return ((field or {}).get("grounding") or {}).get("char_span")


def to_seed(pred: dict) -> dict:
    """Bản ghi máy trích → khung duyệt. Hai vai, hai bộ trường span.

    Trước khi tách kiểu, khung này phẳng và meta-CU luôn có `subject_span=null` —
    người duyệt không phân biệt được "không áp dụng" với "máy quên". Nay `subject_span`
    **không tồn tại** ở khung meta-CU, còn actor-CU thì không có `menh_de_span`.
    """
    la_meta = pred.get("type") == "meta_cu"
    rieng = (
        {
            "gates": pred.get("gates") or [],
            # Mốc ngày do regex tách, KHÔNG do mô hình chọn — nhưng regex vẫn có thể
            # sai, nên nó phải nằm trong tầm duyệt chứ không mặc nhiên coi là đúng.
            "dieu_kien_cong": pred.get("dieu_kien_cong"),
            "menh_de_span": _span(pred.get("menh_de")),
        }
        if la_meta
        else {
            "subject_span": _span(pred.get("subject")),
            "subject_source": pred.get("subject_source"),
            "action_span": _span(pred.get("action")),
        }
    )
    chinh = pred.get("menh_de") if la_meta else pred.get("action")
    return {
        "id": pred["id"],
        "kind": "cu",
        "fixture": pred.get("fixture"),
        "reviewed": False,  # ĐỔI THÀNH true sau khi đã đối chiếu bằng mắt
        # Vai do bước phân loại gán. Phải nằm trong bộ nhãn: người duyệt cần sửa
        # được cả VAI chứ không chỉ span — một actor-CU bị gán nhầm thành meta-CU
        # là bản ghi không bao giờ bị đem ra phán định vi phạm.
        "type": pred.get("type", "actor_cu"),
        **rieng,
        "logic": pred.get("logic"),
        "conditions": [
            {"source_diem": c.get("source_diem"), "span": _span(c)}
            for c in pred.get("conditions") or []
        ],
        # Đặt true cho case CỐ Ý cài lỗi để đo khả năng bắt lỗi cứng.
        "expect_hard_error": False,
        # Máy đề xuất gì — giữ lại để người duyệt biết mình đang sửa cái gì.
        "_may_de_xuat": {
            "subject_text": (pred.get("subject") or {}).get("text", "")[:120],
            "action_text": (chinh or {}).get("text", "")[:120],
            "errors": pred.get("errors") or [],
            # KHÔNG cắt bớt. Trước đây cắt `[:5]` cho gọn, và đúng chỗ đó làm rơi mất
            # cảnh báo quan trọng nhất của TT17 Điều 16 khoản 2: bản ghi không còn lỗi
            # cứng NHỜ được hạ mức, nhưng `text` vẫn không chứa đoạn mà nhãn mô tả —
            # dòng nói điều đó nằm thứ 6/10 nên bị cắt. Một bản ghi trông sạch mà lý do
            # nó sạch bị giấu đi là đúng thứ mà cả tầng duyệt này sinh ra để chặn.
            "warnings": pred.get("warnings") or [],
        },
        "note": "",
    }


def to_premise_seed(pr: dict) -> dict:
    """Bản ghi premise → khung duyệt.

    Premise không có 4-tuple để sửa span. Cái cần người duyệt xác nhận là **phán
    quyết phân loại**: đây có đúng là chất liệu phi-deontic không, đúng loại con
    chưa, và bí danh máy bóc ra có đúng là bí danh không.
    """
    return {
        "id": pr["id"],
        "kind": "premise",
        "fixture": pr.get("fixture"),
        "reviewed": False,
        "premise_kind": pr.get("premise_kind"),
        "alias": pr.get("alias"),
        # Người duyệt bật cờ này khi cho rằng đơn vị KHÔNG phải premise. Tách khỏi
        # `reviewed` để phân biệt "đã xem, đúng" với "đã xem, sai loại".
        "sai_loai": False,
        "raw_span": list(pr["char_span"]),
        "_may_de_xuat": {
            "raw_text": (pr.get("raw_text") or "")[:200],
            "alias_span": pr.get("alias_span"),
            "gop_vao_gate": pr.get("gop_vao_gate"),
            "errors": [],
            "warnings": pr.get("warnings") or [],
        },
        "note": "",
    }


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="pred.jsonl → khung gold cần người duyệt")
    ap.add_argument("--pred", default="eval/ontology/pred.jsonl")
    ap.add_argument("--premise", default="eval/ontology/premise.jsonl")
    ap.add_argument("--out", default="eval/ontology/gold.seed.jsonl")
    ap.add_argument("--premise-out", default="eval/ontology/gold.premise.seed.jsonl")
    args = ap.parse_args(argv)

    seeds = [to_seed(r) for r in _read(Path(args.pred))]
    out = Path(args.out)
    _write(out, seeds)
    flagged = sum(1 for s in seeds if s["_may_de_xuat"]["errors"])
    n_meta = sum(1 for s in seeds if s["type"] == "meta_cu")
    print(f"Đã ghi {out} — {len(seeds)} khung ({n_meta} meta_cu), "
          f"{flagged} case máy đã tự gắn cờ lỗi cứng.")

    # Tầng premise phải được duyệt RIÊNG: nó không có span 4-tuple nên trộn chung
    # một file sẽ phá hợp đồng mà `run_eval.py` đang đọc.
    pr_seeds = [to_premise_seed(r) for r in _read(Path(args.premise))]
    if pr_seeds:
        _write(Path(args.premise_out), pr_seeds)
        n_alias = sum(1 for s in pr_seeds if s["alias"])
        print(f"Đã ghi {args.premise_out} — {len(pr_seeds)} premise, {n_alias} có bí danh.")

    print("CHƯA phải bộ nhãn. Duyệt bằng mắt, đặt reviewed=true, rồi lưu thành gold.jsonl.")
    return len(seeds)


if __name__ == "__main__":
    main()
