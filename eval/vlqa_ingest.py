"""Ingest VLQA vào bảng LanceDB RIÊNG `chunks_vlqa` — không đụng bảng "chunks" sản phẩm. T117.

Tái dùng `build_chunks` + `_embed_rows` của pipeline (cùng cách chẻ khoản + embedding) nhưng ghi
bảng khác. Neo4j KHÔNG dùng (VLQA không có quan hệ).

**Resumable theo lô doc** — full ~60k chunk (~$4, ~30+ phút) mà máy hay kill: embed từng lô rồi
`add` ngay vào bảng, ghi doc_id đã xong vào checkpoint. Chạy lại chỉ bù lô thiếu (khỏi embed lại,
khỏi đốt tiền). `--moi` để làm mới (xoá checkpoint + ghi đè bảng). FTS dựng MỘT lần ở cuối khi đã
đủ mọi doc.

  uv run python -u eval/vlqa_ingest.py --slice 60   # Stage A: 60 doc đầu (~cents)
  uv run python -u eval/vlqa_ingest.py              # Stage B: toàn bộ 2.157 doc (~$4)
  uv run python -u eval/vlqa_ingest.py --moi        # làm mới từ đầu
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # chạy như script thấy `app`

from app.core import vectordb  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.ingestion.pipeline import _FTS_OPTS, _embed_rows, build_chunks  # noqa: E402
from eval.vlqa_adapter import BANG_VLQA, aid_toi_da, nap_corpus  # noqa: E402

_LO_DOC = 50  # số doc mỗi lô embed+append — nhỏ đủ để một cú kill chỉ mất tối đa 1 lô
_CHECKPOINT = Path("eval/results/cache-vlqa-ingest.jsonl")  # doc_id đã ghi vào bảng (gitignored)


def _da_xong() -> set[str]:
    if not _CHECKPOINT.exists():
        return set()
    return {
        json.loads(line)["doc_id"]
        for line in _CHECKPOINT.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def _ghi_xong(doc_ids: list[str]) -> None:
    with _CHECKPOINT.open("a", encoding="utf-8") as fh:
        for d in doc_ids:
            fh.write(json.dumps({"doc_id": d}, ensure_ascii=False) + "\n")


def ingest(gioi_han: int | None = None, *, moi: bool = False, lo: int = _LO_DOC) -> None:
    docs = nap_corpus(gioi_han=gioi_han)
    _CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    if moi:
        _CHECKPOINT.unlink(missing_ok=True)

    done = _da_xong()
    db = vectordb.connect()
    # Resume: bảng đã có → mở để `add`. Checkpoint có mà bảng mất → coi như làm lại từ đầu.
    tbl = None
    if done and not moi:
        try:
            tbl = db.open_table(BANG_VLQA)
        except Exception:  # noqa: BLE001 — bảng không còn → bỏ checkpoint, dựng lại
            done = set()

    todo = [d for d in docs if d.doc_id not in done]
    print(
        f"{len(docs)} doc (aid tối đa {aid_toi_da(docs)}) | đã xong {len(done)} | "
        f"còn {len(todo)} — lô {lo} doc",
        flush=True,
    )

    for i in range(0, len(todo), lo):
        batch = todo[i : i + lo]
        rows = build_chunks(batch)
        _embed_rows(rows)
        if tbl is None:
            # Lô đầu của một lần chạy mới: overwrite để full ghi đè slice cũ (nếu có).
            tbl = db.create_table(BANG_VLQA, data=rows, mode="overwrite")
        else:
            tbl.add(rows)
        _ghi_xong([d.doc_id for d in batch])
        print(f"  +{len(rows)} chunk ({min(i + lo, len(todo))}/{len(todo)} doc)", flush=True)

    if tbl is None:  # không có gì mới (đã xong hết trước đó) → mở để dựng FTS
        tbl = db.open_table(BANG_VLQA)

    # FTS một lần ở cuối. Đã có index (chạy-lại-khi-đã-xong) thì bỏ qua, không coi là lỗi.
    try:
        if settings.lancedb_cloud_enabled:
            tbl.create_fts_index("text", **_FTS_OPTS)
        else:
            tbl.create_fts_index("text", replace=True, **_FTS_OPTS)
        print("  FTS xong", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"  FTS bỏ qua (có thể đã tồn tại): {exc!r}", flush=True)
    print(f"→ bảng {BANG_VLQA}: {tbl.count_rows()} chunk", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slice", type=int, default=None, help="chỉ ingest N doc đầu (Stage A)")
    ap.add_argument("--moi", action="store_true", help="làm mới: xoá checkpoint + ghi đè bảng")
    args = ap.parse_args()
    ingest(args.slice, moi=args.moi)


if __name__ == "__main__":
    main()
