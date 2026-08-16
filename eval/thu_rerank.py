"""Thí nghiệm rerank (T114): top-20 hybrid → cross-encoder rerank → so R@1/R@2/MRR mức ĐIỀU.

CHỈ ĐỂ THÍ NGHIỆM. Không đụng đường sản phẩm, không đụng regression gate của `run_benchmark.py`.
Trả lời đúng một câu hỏi: rerank có nhấc thứ hạng (nhất là mức điều, chỗ hybrid yếu nhất) đủ để
đáng host một reranker (Modal / API) cho production không? Không nhấc → khỏi làm, ghi TASKLIST.

Cách đo: rerank chỉ xáo lại thứ tự trong CÙNG top-20 hybrid, nên R@20 không đổi — chỉ R@1/R@2/MRR@2
mới đổi. Đó chính là thứ rerank sinh ra để cải thiện. So "hybrid" (thứ tự RRF) với "+rerank" trên
cùng bộ ứng viên, cùng nhãn vàng.

Reranker gọi qua API tương thích Jina/Cohere (`results:[{index, relevance_score}]`); endpoint/model/
khoá đọc từ env để đổi nhà cung cấp (Jina ↔ Cohere ↔ Modal tự host) không phải sửa mã:
    RERANK_API_KEY   (bắt buộc)
    RERANK_URL       (mặc định Jina)   RERANK_MODEL  (mặc định jina-reranker-v2-base-multilingual)

Lấy khoá Jina miễn phí tức thì tại https://jina.ai/reranker (1M token free, không cần thẻ).

Chạy:  uv run python -u eval/thu_rerank.py --self-check          # kiểm logic, KHÔNG cần mạng/khoá
       uv run python -u eval/thu_rerank.py                       # bộ mặc định eval/questions.jsonl
       uv run python -u eval/thu_rerank.py --bo eval/bo_sbv.jsonl  # bộ có nhãn cấp điều → số có nghĩa

Job dài (bộ SBV ~100 câu) hay bị kill trên máy này: checkpoint per-câu, HAI tầng —
  eval/results/cache-hybrid-<bộ>.jsonl          retrieval (dùng chung mọi provider)
  eval/results/cache-rerank-<bộ>-<provider>.jsonl  thứ tự rerank (riêng từng provider)
(đều gitignore vì chứa query/lời văn SBV). Chạy lại là bù câu thiếu; đổi provider chỉ chạy lại
tầng rerank, không tốn lại retrieval. So sánh nhiều provider: đổi RERANK_* trong .env rồi chạy lại.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.knowledge.retrieval import hybrid_search  # noqa: E402
from eval import metrics  # noqa: E402
from eval.bo_cau_hoi import nap  # noqa: E402

RESULTS_DIR = Path("eval/results")
_K_POOL = 20  # số ứng viên hybrid đưa cho reranker xáo lại
_MOC_K = (1, 2, 5)  # các mốc k in ra; R@20 bất biến qua rerank nên không cần

# Đọc qua settings (pydantic-settings) — đây là thứ nạp .env; os.getenv KHÔNG thấy .env.
_URL = settings.rerank_url
_MODEL = settings.rerank_model
_KEY = settings.rerank_api_key
_MAX_DOC = 1024  # cắt lời văn điều dài trước khi gửi reranker (giới hạn token + chi phí)


def rerank(query: str, docs: list[str], top_n: int) -> list[int]:
    """Gọi rerank API tương thích Jina/Cohere → trả thứ tự INDEX mới (điểm giảm dần).

    Ném lỗi ra ngoài: người gọi bắt per-câu và bỏ qua câu lỗi (như run_benchmark), để một lỗi
    mạng thoáng qua không giết cả lượt — nhưng KHÔNG fail-open về thứ tự cũ, vì thế sẽ khiến cột
    rerank giống hệt hybrid và ngụy tạo kết luận "rerank vô dụng".

    Retry khi 429 (key trial Cohere ~10 req/phút; Modal cold-start có thể 5xx): tôn trọng
    `Retry-After` nếu có, không thì backoff luỹ thừa. Cạn lượt thử mới ném ra để người gọi bỏ câu.
    """
    payload = {
        "model": _MODEL,
        "query": query,
        "documents": [d[:_MAX_DOC] for d in docs],
        "top_n": top_n,
    }
    for lan in range(5):
        resp = httpx.post(
            _URL,
            headers={"Authorization": f"Bearer {_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=60,
        )
        if resp.status_code in (429, 502, 503) and lan < 4:
            cho = float(resp.headers.get("Retry-After") or 2**lan)
            time.sleep(min(cho, 30))
            continue
        resp.raise_for_status()
        return [r["index"] for r in resp.json()["results"]]
    raise RuntimeError("unreachable")  # vòng lặp luôn return hoặc raise_for_status ở lần cuối


def _the_provider() -> str:
    """Nhãn phân biệt provider trong tên file cache: model + host của endpoint.

    Cần cả host vì khi trỏ RERANK_URL sang Modal mà quên đổi RERANK_MODEL, tên model vẫn là
    mặc định Jina — chỉ model là không đủ, sẽ trộn cache Modal với Jina. Host tách chúng ra.
    """
    tho = f"{_MODEL}-{urlparse(_URL).netloc}"
    return re.sub(r"[^a-z0-9]+", "-", tho.lower()).strip("-")


def _nap_cache(path: Path) -> dict[str, dict]:
    d: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                d[r["query"]] = r
    return d


def _ghi_cache(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _do_bo(order_lists: list[list[str]], vang_lists: list[list[str]]) -> dict[int, dict]:
    """R/P/MRR/F2 trung bình trên các câu, cho từng mốc k."""
    return {
        k: metrics.tong_hop([metrics.do_mot_cau(o, v, k) for o, v in zip(order_lists, vang_lists)])
        for k in _MOC_K
    }


def _in_bang(hybrid: dict[int, dict], rer: dict[int, dict], n: int) -> None:
    print(f"\nMức ĐIỀU — trên {n} câu có nhãn vàng cấp điều", flush=True)
    print(f"{'Metric':<10}{'hybrid':>10}{'+rerank':>10}{'Δ':>9}", flush=True)
    print("-" * 39, flush=True)
    rows = [(f"R@{k}", "recall", k) for k in _MOC_K] + [("MRR@2", "mrr", 2)]
    for nhan, khoa, k in rows:
        a, b = hybrid[k][khoa], rer[k][khoa]
        print(f"{nhan:<10}{a:>10.3f}{b:>10.3f}{b - a:>+9.3f}", flush=True)


def chay(duong_dan: str | Path) -> None:
    cases = nap(duong_dan)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stem = Path(duong_dan).stem
    # Hai tầng cache: retrieval (hybrid) dùng CHUNG cho mọi provider — khỏi chạy lại phần đắt +
    # dễ bị kill; rerank tách RIÊNG theo provider — đổi Jina→Cohere→Modal không đọc nhầm số cũ.
    hybrid_cache = RESULTS_DIR / f"cache-hybrid-{stem}.jsonl"
    rerank_cache = RESULTS_DIR / f"cache-rerank-{stem}-{_the_provider()}.jsonl"
    HC = _nap_cache(hybrid_cache)
    RC = _nap_cache(rerank_cache)

    base_art: list[list[str]] = []
    rer_art: list[list[str]] = []
    vang: list[list[str]] = []
    n_err = 0

    print(f"=== THÍ NGHIỆM RERANK: {duong_dan} ({len(cases)} câu) — reranker={_MODEL} @ {urlparse(_URL).netloc} ===", flush=True)
    for i, case in enumerate(cases, start=1):
        gold = list(case.relevant_articles)
        if not gold:
            continue  # rerank chỉ đo được ở câu có nhãn cấp điều
        q = case.query

        # Tầng 1 — retrieval hybrid (không phụ thuộc provider), có TEXT để rerank lại
        h = HC.get(q)
        if h is None:
            try:
                hits = hybrid_search(q, top_k=_K_POOL, as_of=case.as_of, effective_only=True)
            except Exception as exc:  # noqa: BLE001 — một câu lỗi không giết cả lượt
                print(f"{i:<4} LỖI hybrid: {exc!r}", flush=True)
                n_err += 1
                continue
            h = {
                "query": q,
                "arts": [metrics.khoa_dieu(c) for c in hits],
                "texts": [(c.get("text") or "") for c in hits],
                "vang": gold,
            }
            _ghi_cache(hybrid_cache, h)
            HC[q] = h

        # Tầng 2 — rerank theo provider hiện tại
        r = RC.get(q)
        if r is None:
            try:
                order = rerank(q, h["texts"], _K_POOL)
            except Exception as exc:  # noqa: BLE001
                print(f"{i:<4} LỖI rerank: {exc!r}", flush=True)
                n_err += 1
                continue
            r = {"query": q, "rer": [h["arts"][j] for j in order]}
            _ghi_cache(rerank_cache, r)
            RC[q] = r

        base_art.append(h["arts"])
        rer_art.append(r["rer"])
        vang.append(h["vang"])
        print(f"{i:<4} ok ({len(base_art)} câu có nhãn)", flush=True)

    if not base_art:
        print("Không câu nào có nhãn cấp điều (relevant_articles) — không đo được rerank.", flush=True)
        print("Dùng bộ có nhãn điều, ví dụ --bo eval/bo_sbv.jsonl", flush=True)
        return
    if n_err:
        print(f"Câu lỗi (bỏ qua): {n_err}", flush=True)
    _in_bang(_do_bo(base_art, vang), _do_bo(rer_art, vang), len(base_art))


def _self_check() -> None:
    """Kiểm logic before/after KHÔNG cần mạng: đưa nhãn vàng lên hạng 1 phải nhấc R@1 và MRR."""
    v = ["D::Điều 5"]
    base = ["D::Điều 9", "D::Điều 5", "D::Điều 3"]
    rer = ["D::Điều 5", "D::Điều 9", "D::Điều 3"]
    assert metrics.do_mot_cau(base, v, 1)["recall"] == 0.0
    assert metrics.do_mot_cau(rer, v, 1)["recall"] == 1.0
    assert metrics.do_mot_cau(base, v, 2)["rr"] == 0.5
    assert metrics.do_mot_cau(rer, v, 2)["rr"] == 1.0
    b = _do_bo([base], [v])
    r = _do_bo([rer], [v])
    assert r[1]["recall"] > b[1]["recall"] and r[2]["mrr"] > b[2]["mrr"]
    print("self-check OK", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bo", default="eval/questions.jsonl", help="Bộ câu hỏi .jsonl")
    ap.add_argument("--self-check", action="store_true", help="Kiểm logic metric, không cần mạng/khoá")
    args = ap.parse_args()
    if args.self_check:
        _self_check()
        return
    if not _KEY:
        sys.exit("Thiếu RERANK_API_KEY. Lấy khoá Jina free tại https://jina.ai/reranker rồi đặt vào env.")
    chay(args.bo)


if __name__ == "__main__":
    main()
