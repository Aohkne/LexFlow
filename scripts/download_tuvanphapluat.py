"""Tải bộ dữ liệu phamson02/tuvanphapluat (HuggingFace) về data/tuvanphapluat/.

Chỉ tải 3 file parquet gốc (corpus/train/test) — bỏ qua thư mục processed/
vì chỉ là bản TSV/JSONL trùng lặp của cùng dữ liệu. Tổng dung lượng ~540MB;
thư mục đích đã được thêm vào .gitignore.

Cách dùng:
    uv run python scripts/download_tuvanphapluat.py
"""
from __future__ import annotations

from pathlib import Path

import httpx

_BASE_URL = "https://huggingface.co/datasets/phamson02/tuvanphapluat/resolve/main"
_FILES = ["corpus.parquet", "train.parquet", "test.parquet"]
_DEST_DIR = Path("data/tuvanphapluat")


def _download(name: str) -> None:
    dest = _DEST_DIR / name
    with httpx.stream("GET", f"{_BASE_URL}/{name}", follow_redirects=True, timeout=None) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        done = 0
        with dest.open("wb") as f:
            for chunk in r.iter_bytes(chunk_size=1 << 20):
                f.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r{name}: {done / 1e6:.0f}/{total / 1e6:.0f} MB", end="", flush=True)
    print()


def main() -> None:
    _DEST_DIR.mkdir(parents=True, exist_ok=True)
    for name in _FILES:
        _download(name)


if __name__ == "__main__":
    main()
