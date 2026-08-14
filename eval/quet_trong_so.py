"""Quét trọng số nhánh thưa trong RRF, đo lại R@k ở cả hai mức.

Đo 11/08 cho thấy nhánh BM25 gần như vô dụng ở **mức điều** (R@20 = 0.21, so với 0.82 của chính
nó ở mức văn bản): nó tìm ra đúng văn bản nhưng không phân biệt nổi điều nào trong đó. Vì
`hybrid_search` hợp nhất nó qua RRF với trọng số ngang nhánh vector, nó kéo các điều **sai** của
**đúng văn bản** lên top — LexFlow vì thế xếp hạng mức điều thua cả dense thuần từ R@1 tới R@10
(`docs/EVAL-IR.md` §6). Script này trả lời: hạ trọng số ấy có lấy lại được không, và ở mức nào.

**Truy hồi một lần, quét nhiều trọng số.** RRF là phép xếp hạng thuần trên hai danh sách đã có,
nên hai nhánh chỉ cần gọi **một lượt cho mỗi câu**; mọi trọng số tính lại trong bộ nhớ. Chạy full
benchmark cho từng trọng số sẽ mất khoảng một giờ mỗi lần và không cho thêm thông tin nào.

Chạy:  uv run python -u eval/quet_trong_so.py
       uv run python -u eval/quet_trong_so.py --bo eval/bo_khac.jsonl --trong-so 0 0.25 1
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ingestion.versioning import is_effective  # noqa: E402
from app.knowledge import retrieval  # noqa: E402
from eval import metrics  # noqa: E402
from eval.bo_cau_hoi import CauHoi, nap  # noqa: E402

MAC_DINH = Path("eval/bo_tvpl_dung_thoi.jsonl")

#: Bằng `hybrid_search(top_k=20)`: pool = max(top_k*3, 15).
_TOP_K = 20
_POOL = max(_TOP_K * 3, 15)

_TRONG_SO = (0.0, 0.1, 0.25, 0.5, 0.75, 1.0)


def _hai_nhanh(query: str) -> tuple[list[dict], list[dict]]:
    """Hai bảng xếp hạng thô, đúng như `hybrid_search` lấy — gọi một lần cho mọi trọng số."""
    tbl = retrieval._open_table()
    vector_hits = tbl.search(list(retrieval._qv(query))).limit(_POOL).to_list()
    try:
        fts_hits = tbl.search(query, query_type="fts").limit(_POOL).to_list()
    except Exception:  # noqa: BLE001 — FTS chưa sẵn sàng ⇒ nhánh thưa rỗng, y như bản thật
        fts_hits = []
    return vector_hits, fts_hits


def _xep_hang(nhanh: tuple[list[dict], list[dict]], as_of: str | None, w: float) -> list[dict]:
    """Phần còn lại của `hybrid_search`: RRF → lọc hiệu lực → cắt top_k."""
    merged = retrieval._rrf(*nhanh, _POOL, trong_so_thua=w)
    merged = [
        r for r in merged
        if is_effective(r.get("valid_from"), r.get("valid_to"), r.get("superseded", False), as_of)
    ]
    return merged[:_TOP_K]


def quet(cases: list[CauHoi], trong_so: tuple[float, ...]) -> dict[float, dict]:
    nhanh_theo_cau: list[tuple[CauHoi, tuple[list[dict], list[dict]]]] = []
    for i, case in enumerate(cases, start=1):
        try:
            nhanh_theo_cau.append((case, _hai_nhanh(case.query)))
        except Exception as exc:  # noqa: BLE001 — một câu lỗi mạng không giết cả lượt quét
            print(f"  {i:>3}/{len(cases)} LỖI, bỏ qua: {exc!r}"[:120], flush=True)
        if i % 10 == 0:
            print(f"  đã truy hồi {i}/{len(cases)} câu", flush=True)

    ra: dict[float, dict] = {}
    for w in trong_so:
        ra[w] = {}
        for muc in ("doc", "art"):
            diem_theo_k: dict[int, list[dict]] = {k: [] for k in metrics.CAC_MOC_K}
            for case, nhanh in nhanh_theo_cau:
                vang = list(case.relevant_docs if muc == "doc" else case.relevant_articles)
                if not vang:
                    continue
                hits = _xep_hang(nhanh, case.as_of, w)
                khoa = [h["doc_id"] for h in hits] if muc == "doc" else [metrics.khoa_dieu(h) for h in hits]
                for k in metrics.CAC_MOC_K:
                    diem_theo_k[k].append(metrics.do_mot_cau(khoa, vang, k))
            ra[w][muc] = {
                "n": len(diem_theo_k[metrics.CAC_MOC_K[0]]),
                **{f"@{k}": metrics.tong_hop(v) for k, v in diem_theo_k.items()},
            }
    return ra


def _in(ket_qua: dict[float, dict]) -> None:
    for muc, ten in (("doc", "văn bản"), ("art", "điều")):
        n = next(iter(ket_qua.values()))[muc]["n"]
        if not n:
            print(f"\nMức {ten}: không câu nào có nhãn, bỏ qua.", flush=True)
            continue
        print(f"\nMức {ten} ({n} câu có nhãn) — trọng số nhánh thưa trong RRF", flush=True)
        print(
            f"{'trọng số':<10}{'R@1':>7}{'R@2':>7}{'R@5':>7}{'R@10':>7}{'R@20':>7}"
            f"{'MRR@2':>8}{'P@2':>7}{'F2@2':>7}",
            flush=True,
        )
        print("-" * 69, flush=True)
        for w, khoi in ket_qua.items():
            c = khoi[muc]
            nhan = f"{w:g}" + ("  (nay)" if w == retrieval.TRONG_SO_THUA else "")
            print(
                f"{nhan:<10}"
                + "".join(f"{c[f'@{k}']['recall']:>7.2f}" for k in metrics.CAC_MOC_K)
                + f"{c['@2']['mrr']:>8.2f}{c['@2']['precision']:>7.2f}{c['@2']['f2']:>7.2f}",
                flush=True,
            )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bo", default=MAC_DINH, help=f"Bộ câu hỏi .jsonl (mặc định {MAC_DINH})")
    ap.add_argument(
        "--trong-so", nargs="+", type=float, default=list(_TRONG_SO),
        help="Các trọng số cần quét (0 = bỏ hẳn nhánh thưa)",
    )
    args = ap.parse_args()

    cases = nap(args.bo)
    print(f"=== {args.bo} ({len(cases)} câu) — truy hồi 1 lượt, quét {len(args.trong_so)} trọng số ===",
          flush=True)
    _in(quet(cases, tuple(args.trong_so)))


if __name__ == "__main__":
    main()
