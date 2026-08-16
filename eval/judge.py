"""LLM-judge: chấm CHẤT LƯỢNG CÂU TRẢ LỜI (Correctness §5.3 bài báo SBV-LawGraph).

Mọi bảng đo khác trong repo đo *retrieval* (tìm đúng văn bản chưa). Đây là con số duy nhất
đo *câu trả lời* — thứ người dùng thực sự đọc ở buổi demo. Là hạng mục 2 Sprint 3
(`docs/ROADMAP-SPRINT.md`), nằm trong DoD.

Chấm trên **bộ SBV** (`eval/bo_sbv.jsonl`, 100 câu): nhãn cấp điều 100%, luật đang hiệu lực,
là **dữ liệu ngoài** — và mỗi câu có `reference_answer` do chính tác giả bài báo viết (join lại từ
`data/evaluate/svb_graph/sbv_testset_tvpl.json` theo `question_id`; file nhãn giữ sạch, không nhét
đáp án vào — xem `docs/superpowers/specs/2026-08-12-danh-gia-bo-sbv.md`).

Ba tiêu chí Correctness của bài báo, chỉ MỘT tốn LLM:
  1. tương đương ngữ nghĩa với `reference_answer`  → LLM (`chat_json`, temperature=0)
  2. có trích dẫn                                    → Python (`citations` khác rỗng)
  3. trích dẫn khớp corpus                           → Python (doc vàng ∈ doc được dẫn)

Trích dẫn của LexFlow luôn sinh từ chunk THẬT nên `doc_id` chắc chắn có trong corpus — không thể
bịa doc_id. Vì thế tiêu chí 3 rút về "có dẫn đúng (các) văn bản vàng không", kiểm bằng Python,
không đốt một lượt gọi model cho việc xác định được.

Hai pha, tách cache: sinh câu trả lời (đắt: retrieval + chat, gọi mạng) ghi ra
`eval/results/answers-sbv.jsonl` một lần; chỉnh prompt judge rồi chấm lại KHÔNG sinh lại.
`--sinh-lai` để ép sinh mới.

KHÔNG so trực tiếp với số Correctness của bài báo: họ dùng **2 annotator người**, ta dùng LLM-judge
1 phiếu (temperature=0). Ghi rõ trong báo cáo. Mẫu 29 câu là nhỏ — nói rõ, đừng để tưởng là kết luận.

Chạy:
    uv run python -u eval/judge.py                 # dùng cache câu trả lời nếu có
    uv run python -u eval/judge.py --sinh-lai      # sinh lại câu trả lời rồi chấm
Yêu cầu: Gemini API + LanceDB (+ Neo4j nếu graph bật) như `run_benchmark.py`.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Chạy như SCRIPT ⇒ `import app` ném ModuleNotFoundError; nối gốc repo vào path như run_benchmark.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.llm import chat_json  # noqa: E402
from app.core.schemas import ChatRequest  # noqa: E402
from app.reasoning.answer import build_answer  # noqa: E402
from eval.bo_cau_hoi import CauHoi, nap  # noqa: E402

GOC = Path(__file__).resolve().parent.parent
BO = GOC / "eval/bo_sbv.jsonl"
NGUON_SBV = GOC / "data/evaluate/svb_graph/sbv_testset_tvpl.json"
CACHE = GOC / "eval/results/answers-sbv.jsonl"
RESULTS_DIR = GOC / "eval/results"

_SYSTEM = (
    "Bạn là giám khảo pháp lý. Cho một CÂU HỎI, một ĐÁP ÁN THAM CHIẾU (đúng, do chuyên gia viết) "
    "và một CÂU TRẢ LỜI của hệ thống, hãy phán định câu trả lời có tương đương về NỘI DUNG với "
    "đáp án tham chiếu không. Chỉ xét đúng/sai nội dung, KHÔNG trừ điểm vì diễn đạt khác, dài ngắn "
    "khác, hay trích dẫn khác cách. Trả về JSON đúng dạng "
    '{"tuong_duong": "dung|thieu|sai", "ly_do": "..."}. '
    '"dung" = truyền đạt đúng ý chính của đáp án tham chiếu; '
    '"thieu" = đúng một phần nhưng bỏ sót ý chính; '
    '"sai" = sai nội dung, mâu thuẫn, hoặc trả lời không tìm thấy trong khi đáp án tham chiếu có.'
)

#: dung/thieu/sai → điểm. thieu = 0.5 vì "đúng nhưng thiếu ý" khác hẳn "sai".
_DIEM = {"dung": 1.0, "thieu": 0.5, "sai": 0.0}


def _ref_answers() -> dict[int, str]:
    """`question_id` → `reference_answer` từ file nguồn của bài báo."""
    rows = json.loads(NGUON_SBV.read_text(encoding="utf-8"))
    return {r["question_id"]: r.get("reference_answer", "") for r in rows}


def _append_jsonl(path: Path, row: dict) -> None:
    """Ghi 1 dòng JSONL, chèn '\\n' nếu file cũ chưa kết thúc bằng newline (tránh dính hai dòng)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    prefix = "\n" if path.exists() and path.read_bytes()[-1:] not in (b"\n", b"") else ""
    with path.open("a", encoding="utf-8") as fh:
        fh.write(prefix + json.dumps(row, ensure_ascii=False) + "\n")


def sinh_cau_tra_loi(cases: list[CauHoi]) -> list[dict]:
    """Chạy đường sản phẩm (`build_answer`) cho từng câu → answer + doc_id đã dẫn.

    Ghi cache TỪNG CÂU (append, khoá theo question_id) để lượt bị cắt chạy lại chỉ bù câu còn
    thiếu — job 100 câu quá dài để mất trắng khi nền bị kill. Câu LỖI không ghi cache -> tự thử lại.
    """
    da_co = {r["question_id"] for r in doc_cache()} if CACHE.exists() else set()
    for i, c in enumerate(cases, 1):
        qid = c.tho.get("question_id")
        if qid in da_co:
            continue
        try:
            resp = build_answer(ChatRequest(query=c.query, as_of=c.as_of))
            _append_jsonl(CACHE, {
                "question_id": qid,
                "query": c.query,
                "answer": resp.answer,
                "cited_docs": sorted({cite.doc_id for cite in resp.citations}),
                "n_citations": len(resp.citations),
            })
            print(f"  [{i}/{len(cases)}] qid={qid} sinh xong ({len(resp.citations)} trích dẫn)")
        except Exception as e:  # noqa: BLE001 — một câu lỗi mạng không giết cả lượt (như run_benchmark)
            print(f"  [{i}/{len(cases)}] qid={qid} LỖI: {e}")
    return doc_cache()


def doc_cache() -> list[dict]:
    return [json.loads(d) for d in CACHE.read_text(encoding="utf-8").splitlines() if d.strip()]


def cham_python(cited_docs: list[str], relevant_docs: tuple[str, ...]) -> dict:
    """Hai tiêu chí trích dẫn — thuần Python, không mạng.

    `trich_dan_khop`: mọi văn bản vàng đều được dẫn. doc_id luôn từ chunk thật nên không thể bịa;
    câu không có văn bản vàng (không nên xảy ra ở bộ SBV) coi như không đánh giá được → False.
    """
    cited = set(cited_docs)
    return {
        "co_trich_dan": bool(cited),
        "trich_dan_khop": bool(relevant_docs) and set(relevant_docs) <= cited,
    }


def cham_ngu_nghia(query: str, answer: str, reference: str) -> dict:
    """Tiêu chí LLM: câu trả lời có tương đương nội dung với đáp án tham chiếu không.

    `reasoning=False` là BẮT BUỘC ở đây, không phải tối ưu. Model reasoning (mặc định của
    `chat_json`) đi vào vòng suy nghĩ cực dài trên nội dung pháp lý — đo 14/08: một câu treo
    > 2 phút không trả về, trong khi model thường chấm xong 12s với verdict + giải thích đúng.
    Đối chiếu ngữ nghĩa với một đáp án cho sẵn không cần suy luận sâu nhiều bước.
    """
    prompt = (
        f"CÂU HỎI:\n{query}\n\n"
        f"ĐÁP ÁN THAM CHIẾU:\n{reference}\n\n"
        f"CÂU TRẢ LỜI CỦA HỆ THỐNG:\n{answer}"
    )
    data = chat_json(prompt, system=_SYSTEM, temperature=0.0, reasoning=False)
    verdict = data.get("tuong_duong")
    if verdict not in _DIEM:
        verdict = "sai"  # JSON hỏng / verdict lạ → tính là sai, không âm thầm bỏ khỏi mẫu số
    return {"tuong_duong": verdict, "diem": _DIEM[verdict], "ly_do": data.get("ly_do", "")}


def tong_hop(ket_qua: list[dict]) -> dict:
    n = len(ket_qua)
    if not n:
        return {"n": 0}
    return {
        "n": n,
        "diem_ngu_nghia_tb": round(sum(k["diem"] for k in ket_qua) / n, 3),
        "ty_le_dung": round(sum(k["tuong_duong"] == "dung" for k in ket_qua) / n, 3),
        "ty_le_co_trich_dan": round(sum(k["co_trich_dan"] for k in ket_qua) / n, 3),
        "ty_le_trich_dan_khop": round(sum(k["trich_dan_khop"] for k in ket_qua) / n, 3),
    }


def in_bang(tong: dict) -> None:
    print("\n=== LLM-judge — bộ SBV (đường sản phẩm LexFlow) ===")
    if not tong.get("n"):
        print("  (không có câu nào)")
        return
    print(f"  câu chấm được          : {tong['n']}")
    print(f"  điểm ngữ nghĩa TB      : {tong['diem_ngu_nghia_tb']:.3f}  (dung=1 · thieu=0.5 · sai=0)")
    print(f"  tỷ lệ 'dung' hoàn toàn : {tong['ty_le_dung']:.3f}")
    print(f"  tỷ lệ có trích dẫn     : {tong['ty_le_co_trich_dan']:.3f}")
    print(f"  tỷ lệ trích dẫn khớp   : {tong['ty_le_trich_dan_khop']:.3f}")
    print(f"  Lưu ý: 1 phiếu (temperature=0), mẫu {tong['n']} câu — KHÔNG so trực tiếp Correctness 2-annotator của bài báo.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sinh-lai", action="store_true", help="ép sinh lại câu trả lời (bỏ cache)")
    args = ap.parse_args()

    cases = nap(BO)
    refs = _ref_answers()

    # Xoá CẢ HAI cache TRƯỚC pha sinh. Nếu chỉ xoá verdict cache ở pha chấm (như trước), một cú
    # kill giữa pha sinh để verdict cache cũ còn nguyên → resume thường đọc verdict CŨ cho câu trả
    # lời MỚI, báo số sai mà không lộ ra. Xoá sớm cả hai để --sinh-lai luôn cho lượt đo sạch.
    vcache = RESULTS_DIR / "cache-judge-sbv.jsonl"
    if args.sinh_lai:
        CACHE.unlink(missing_ok=True)
        vcache.unlink(missing_ok=True)
    print(f"Sinh/bù câu trả lời cho {len(cases)} câu (đường sản phẩm, cache {CACHE.name})…")
    answers = sinh_cau_tra_loi(cases)

    # Pha chấm cũng checkpoint: verdict LLM ~12s/câu, mất khi nền bị kill thì phí. Khoá theo
    # question_id (duy nhất từng dòng -> không khử trùng).
    by_qid = {c.tho.get("question_id"): c for c in cases}
    da_cham = {}
    if vcache.exists():
        for line in vcache.read_text(encoding="utf-8").splitlines():
            if line.strip():
                v = json.loads(line)
                da_cham[v["question_id"]] = v

    ket_qua: list[dict] = []
    print(f"\nChấm {len(answers)} câu…")
    for i, a in enumerate(answers, 1):
        qid = a["question_id"]
        c = by_qid.get(qid)
        ref = refs.get(qid, "")
        if c is None or not ref:
            print(f"  [{i}] qid={qid} BỎ (thiếu case hoặc reference_answer)")
            continue
        cached = da_cham.get(qid)
        if cached is not None:
            ket_qua.append(cached)
            print(f"  [{i}/{len(answers)}] qid={qid} {cached['tuong_duong']} (cache)")
            continue
        py = cham_python(a["cited_docs"], c.relevant_docs)
        ng = cham_ngu_nghia(a["query"], a["answer"], ref)
        row = {"question_id": qid, "query": a["query"], **py, **ng}
        _append_jsonl(vcache, row)
        ket_qua.append(row)
        print(f"  [{i}/{len(answers)}] qid={qid} {ng['tuong_duong']}")

    tong = tong_hop(ket_qua)
    in_bang(tong)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS_DIR / f"judge-sbv-{ts}.json"
    out.write_text(
        json.dumps({"tong_hop": tong, "chi_tiet": ket_qua}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nGhi: {out}")


if __name__ == "__main__":
    main()
