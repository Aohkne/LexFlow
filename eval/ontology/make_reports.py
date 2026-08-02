"""pred.jsonl → một trang HTML mỗi Compliance Unit, để người duyệt đọc bằng mắt.

Không gọi LLM: dựng lại ComplianceUnit từ JSON đã có. Dùng sau khi `--batch` xong,
tránh phải chạy lại toàn bộ lượt Gemini chỉ để lấy HTML.

Chạy:  uv run python eval/ontology/make_reports.py [--out-dir eval/ontology/reports]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ontology.parser import parse_dieu
from app.ontology.report import render
from app.ontology.schema import ComplianceUnit

_INDEX = Path("data/fixtures/_index.json")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sinh trang kiểm từ pred.jsonl")
    ap.add_argument("--pred", default="eval/ontology/pred.jsonl")
    ap.add_argument("--out-dir", default="eval/ontology/reports")
    args = ap.parse_args(argv)

    index = json.loads(_INDEX.read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cache: dict[str, object] = {}
    written = 0
    lines = Path(args.pred).read_text(encoding="utf-8").splitlines()
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        fixture = Path(row["fixture"])
        if fixture.name not in cache:
            cache[fixture.name] = parse_dieu(
                fixture.read_text(encoding="utf-8"), index[fixture.name]
            )
        dieu = cache[fixture.name]
        cu = ComplianceUnit.model_validate({k: v for k, v in row.items() if k != "fixture"})
        name = f"{fixture.stem}-khoan{cu.id.rsplit('#khoan_', 1)[-1]}.html"
        (out_dir / name).write_text(render(cu, dieu), encoding="utf-8")
        written += 1

    print(f"Đã ghi {written} trang vào {out_dir}")
    return written


if __name__ == "__main__":
    main()
