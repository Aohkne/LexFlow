"""Đo xem Gemini có ÂM THẦM cắt đuôi chunk dài khi embedding không.

Vì sao cần đo thay vì đọc tài liệu: `pipeline._MAX_CHUNK = 2000` **không phải trần thật** —
nhánh chẻ theo khoản chỉ ngắt *giữa* các khoản, không bao giờ cắt *trong* một khoản, nên một
khoản dài đơn lẻ đi thẳng thành chunk vài nghìn ký tự. Nếu API lặng lẽ cắt input thì phần đuôi
những chunk đó **không nằm trong vector**, và retrieval trượt đúng các khoản dài nhất mà không
có một dấu hiệu nào. Tài liệu nhà cung cấp nói giới hạn theo *token*; thứ ta cần là ngưỡng
**ký tự** trên chính văn bản tiếng Việt của corpus này.

Phép đo: gắn một câu mốc vào cuối chuỗi rồi so vector.

    v1 = embed(X)          v2 = embed(X + MỐC)
    v1 == v2  ⇒  MỐC không tới được model  ⇒  đuôi bị cắt

Chuỗi đem đo là chuỗi **thật sự được embed** lúc ingest — `"{doc_title} — {article}: {text}"`
(xem `pipeline._embed_rows`), không phải mình `text`, vì tiền tố tiêu đề cũng chiếm chỗ.

    uv run python scripts/do_gioi_han_embed.py

Tốn khoảng 2 + 2·log2(N) lượt embedding, KHÔNG ghi gì lên LanceDB/Neo4j/Supabase.
"""
from __future__ import annotations

import sys

from app.core.config import settings
from app.core.llm import EMBED_DIM, embed_documents
from app.ingestion.pipeline import _MAX_CHUNK, build_chunks, load_corpus

_CORPUS = "data/corpus.real.json"

#: Câu mốc: phải là chữ KHÔNG xuất hiện trong corpus, để nếu nó tới được model thì vector
#: chắc chắn đổi. Dài một chút cho chắc — một token lẻ có thể không dịch chuyển vector đủ để
#: phân biệt với nhiễu số học.
_MOC = (
    "\nCÂU MỐC KIỂM TRA CẮT ĐUÔI: bạch tuộc tím nhảy điệu tango trên sao Hoả "
    "lúc ba giờ sáng ngày ba mươi hai tháng mười ba."
)


def _chuoi_embed(r: dict) -> str:
    """Đúng chuỗi mà `pipeline._embed_rows` đưa cho Gemini."""
    return f"{r['doc_title']} — {r['article']}: {r['text']}"


def _giong_nhau(a: list[float], b: list[float]) -> bool:
    """Hai vector có phải cùng một kết quả không.

    So bằng khoảng cách tuyệt đối lớn nhất chứ không phải cosine: cosine của hai vector chỉ
    khác nhau ở phần đuôi vẫn rất gần 1, còn cái ta cần biết là API có trả về **đúng cùng một
    embedding** hay không. Ngưỡng nới cho nhiễu dấu phẩy động của đường truyền.
    """
    return max(abs(x - y) for x, y in zip(a, b)) < 1e-6


def _co_bi_cat(chuoi: str) -> bool:
    v1, v2 = embed_documents([chuoi, chuoi + _MOC])
    return _giong_nhau(v1, v2)


def _tim_nguong(chuoi: str, tran: int) -> int:
    """Tiền tố dài nhất mà câu mốc CÒN tới được model — tìm nhị phân trên độ dài ký tự."""
    lo, hi = 0, tran  # lo: chắc chắn chưa cắt · hi: chắc chắn đã cắt
    while hi - lo > 32:
        giua = (lo + hi) // 2
        if _co_bi_cat(chuoi[:giua]):
            hi = giua
        else:
            lo = giua
        print(f"    ... khoảng còn [{lo}, {hi}]", flush=True)
    return lo


def main() -> None:
    if not settings.gemini_api_key:
        raise SystemExit("Chưa có GEMINI_API_KEY trong .env — phép đo này cần gọi API thật.")

    docs, _ = load_corpus(_CORPUS)
    rows = build_chunks(docs)
    theo_dai = sorted(rows, key=lambda r: len(_chuoi_embed(r)), reverse=True)
    dai_nhat = theo_dai[0]
    chuoi = _chuoi_embed(dai_nhat)
    vuot = [r for r in rows if len(_chuoi_embed(r)) > _MAX_CHUNK]

    print(f"model            {settings.gemini_embed_model} · {EMBED_DIM} chiều")
    print(f"corpus           {_CORPUS} — {len(docs)} văn bản, {len(rows)} chunk")
    print(f"ngưỡng chẻ       _MAX_CHUNK = {_MAX_CHUNK}")
    print(f"chuỗi vượt ngưỡng {len(vuot)}/{len(rows)}")
    print(f"dài nhất         {dai_nhat['id']} — {len(chuoi)} ký tự\n")

    print("Đo trên chuỗi dài nhất...", flush=True)
    try:
        bi_cat = _co_bi_cat(chuoi)
    except Exception as exc:  # noqa: BLE001 — API từ chối cũng là một kết quả, và là kết quả TỐT
        print(f"\nAPI TỪ CHỐI chuỗi dài nhất: {type(exc).__name__}: {str(exc)[:300]}")
        print("Từ chối ồn ào an toàn hơn cắt im lặng: ingest sẽ đỏ chứ không âm thầm mất đuôi.")
        return

    if not bi_cat:
        print(f"\nKHÔNG cắt: chuỗi {len(chuoi)} ký tự vẫn tới model trọn vẹn.")
        print(f"⇒ {len(vuot)} chunk vượt _MAX_CHUNK hiện KHÔNG mất đuôi. Ngưỡng 2000 là lựa "
              "chọn về độ chính xác retrieval, không phải ràng buộc của API.")
        return

    print(f"\nCÓ CẮT ở chuỗi {len(chuoi)} ký tự. Đang tìm ngưỡng...", flush=True)
    nguong = _tim_nguong(chuoi, len(chuoi))
    mat = [r for r in rows if len(_chuoi_embed(r)) > nguong]
    print(f"\nngưỡng đo được   ~{nguong} ký tự (sai số ±32)")
    print(f"chunk MẤT ĐUÔI   {len(mat)}/{len(rows)}")
    for r in sorted(mat, key=lambda r: -len(_chuoi_embed(r)))[:10]:
        n = len(_chuoi_embed(r))
        print(f"   {r['id']:<44} {n:6} ký tự — mất {n - nguong}")
    if len(mat) > 10:
        print(f"   … và {len(mat) - 10} chunk nữa")
    print("\n⇒ Ghi con số này vào docs/TASKLIST.md T3 kèm ngày đo, rồi mới bàn cách sửa "
          "(mọi cách đều đổi nhãn chunk ⇒ kéo theo re-ingest).")


if __name__ == "__main__":
    sys.exit(main())
