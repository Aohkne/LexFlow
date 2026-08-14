"""Gộp văn bản đã cào (staging `data/raw/vbpl/corpus`) vào corpus phục vụ — tạo BASE entry cho
văn bản MỚI, rồi để `enrich_corpus_from_vbpl.py` thêm thuộc tính như đã làm với ND52/TT15.

Chỉ THÊM văn bản mới (doc_id chưa có). KHÔNG đụng văn bản cũ, KHÔNG đụng `relationships`.
Idempotent: chạy lại bỏ qua văn bản đã có, không nhân đôi.

BASE entry = 8 field core (`doc_id, title, doc_type, source, valid_from, valid_to, so_hieu,
articles`); article giữ `article/text/superseded/chapter/section`, **bỏ** `char_start/char_end`,
đặt `valid_from/valid_to` cấp điều = None (không bịa — curate cấp điều là việc eval-driven riêng,
xem spec 2026-08-14). Đây đúng shape article của ND52 trong corpus.

Nguồn "văn bản nào": mặc định tập `van_ban_thieu` của `eval/bo_sbv_khong_can_cu.jsonl` (23 văn bản
bộ SBV thiếu). Map số hiệu → file staging bằng `chuan_so_hieu` (KHÔNG so chuỗi thẳng: staging có
`'TT- NHNN'` thừa dấu cách và `'NĐ'` vs `'ND'`).

Sau script này: `uv run python scripts/enrich_corpus_from_vbpl.py --tu-thu-muc data/raw/vbpl/corpus`
rồi soi `git diff data/corpus.real.json` (maker-checker) trước khi ingest.

Chạy:
    uv run python scripts/gop_corpus_tu_staging.py            # thêm 23 văn bản SBV thiếu
    uv run python scripts/gop_corpus_tu_staging.py --dry-run  # chỉ in, không ghi
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eval.chuyen_tvpl import chuan_so_hieu  # noqa: E402

GOC = Path(__file__).resolve().parent.parent
STAGING = GOC / "data/raw/vbpl/corpus"
CORPUS = GOC / "data/corpus.real.json"
NEG = GOC / "eval/bo_sbv_khong_can_cu.jsonl"

#: Field article giữ lại (theo thứ tự ND52 trong corpus). char_start/char_end bị bỏ.
_ART_META = ("chapter", "section")


def so_hieu_thieu() -> list[str]:
    """Tập `van_ban_thieu` của bộ SBV negative, khử trùng, giữ thứ tự xuất hiện."""
    ra: list[str] = []
    seen: set[str] = set()
    for dong in NEG.read_text(encoding="utf-8").splitlines():
        if not dong.strip():
            continue
        for sh in json.loads(dong).get("van_ban_thieu", []):
            if sh not in seen:
                seen.add(sh)
                ra.append(sh)
    return ra


def index_staging(thu_muc: Path) -> dict[str, dict]:
    """`chuan_so_hieu(so_hieu)` → doc staging (json thô). Trùng key thì cái sau đè + cảnh báo."""
    idx: dict[str, dict] = {}
    for f in sorted(thu_muc.glob("*.json")):
        s = json.loads(f.read_text(encoding="utf-8"))
        key = chuan_so_hieu(s.get("so_hieu", ""))
        if key in idx:
            print(f"[gop] CẢNH BÁO: hai file staging cùng số hiệu {key!r}: giữ {f.name}")
        idx[key] = s
    return idx


def chuyen_article(a: dict) -> dict:
    """Article staging → article corpus: bỏ char_start/char_end, valid_from/valid_to cấp điều = None."""
    r: dict = {
        "article": a["article"],
        "text": a["text"],
        "valid_from": None,
        "valid_to": None,
        "superseded": bool(a.get("superseded", False)),
    }
    for k in _ART_META:
        if a.get(k) is not None:
            r[k] = a[k]
    return r


def chuyen_doc(s: dict) -> dict:
    """Staging → BASE entry corpus (8 field core). `valid_to` rỗng → None; giữ ngày với văn bản đã chết."""
    return {
        "doc_id": s["doc_id"],
        "title": s["title"],
        "doc_type": s["doc_type"],
        "source": s.get("source") or "external",
        "valid_from": s.get("valid_from") or None,
        "valid_to": s.get("valid_to") or None,
        "so_hieu": s["so_hieu"],
        "articles": [chuyen_article(a) for a in s.get("articles", [])],
    }


def gop(
    corpus: dict, staging_idx: dict[str, dict], so_hieu_list: list[str]
) -> tuple[list[str], list[str], list[str]]:
    """Thêm base entry cho văn bản mới. Trả (đã thêm, bỏ qua vì đã có, không thấy staging).

    Sửa `corpus` tại chỗ. Guard doc_id đã có ⇒ idempotent.
    """
    co = {d["doc_id"] for d in corpus["documents"]}
    them: list[str] = []
    bo_qua: list[str] = []
    khong_thay: list[str] = []
    for sh in so_hieu_list:
        s = staging_idx.get(chuan_so_hieu(sh))
        if s is None:
            khong_thay.append(sh)
            continue
        if s["doc_id"] in co:
            bo_qua.append(s["doc_id"])
            continue
        corpus["documents"].append(chuyen_doc(s))
        co.add(s["doc_id"])
        them.append(s["doc_id"])
    return them, bo_qua, khong_thay


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", type=Path, default=CORPUS)
    ap.add_argument("--staging", type=Path, default=STAGING)
    ap.add_argument("--so-hieu", action="append", default=[], help="chỉ định tay (lặp lại được)")
    ap.add_argument("--dry-run", action="store_true", help="chỉ in, không ghi file")
    a = ap.parse_args()

    corpus = json.loads(a.corpus.read_text(encoding="utf-8"))
    staging_idx = index_staging(a.staging)
    so_hieu_list = a.so_hieu or so_hieu_thieu()

    them, bo_qua, khong_thay = gop(corpus, staging_idx, so_hieu_list)

    print(f"[gop] nguồn: {len(so_hieu_list)} số hiệu")
    print(f"[gop] THÊM {len(them)} văn bản: {', '.join(them)}")
    if bo_qua:
        print(f"[gop] bỏ qua {len(bo_qua)} đã có: {', '.join(sorted(bo_qua))}")
    if khong_thay:
        print(f"[gop] KHÔNG thấy staging cho {len(khong_thay)}: {', '.join(khong_thay)}")

    if a.dry_run:
        print("[gop] --dry-run: không ghi file.")
        return
    if them:
        # indent=1 khớp format corpus.real.json hiện có (giảm nhiễu diff).
        a.corpus.write_text(
            json.dumps(corpus, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        print(f"[gop] đã ghi {a.corpus}")


if __name__ == "__main__":
    main()
