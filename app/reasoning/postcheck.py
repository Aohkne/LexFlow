"""Hậu kiểm câu trả lời (T109 Phase 2) — trả CỜ CẢNH BÁO, không chặn cứng.

Bài báo (Algorithm 2, dòng 20–21) kiểm sau khi sinh: không có trích dẫn / trích dẫn không khớp
bằng chứng ⇒ từ chối. LexFlow warn-only: đây là heuristic, chặn cứng một câu đúng vì heuristic
sai còn tệ hơn để lọt một câu đáng ngờ. Cờ đưa lên `ChatResponse.canh_bao` để UI hiện cảnh báo.

Hai phép ĐÁNG TIN:
- `thiếu_trích_dẫn` — câu trả lời có nội dung mà không kèm một `[văn bản — điều]` nào.
- `trích_dẫn_ngoài_căn_cứ:<...>` — câu trích một (số hiệu, Điều) KHÔNG nằm trong chunk đã retrieve
  ⇒ nghi bịa. Chỉ báo khi trích dẫn có SỐ HIỆU rõ để đối chiếu; thiếu số hiệu thì bỏ qua (không đủ
  căn cứ để kết tội → tránh báo động giả).

Completeness (đếm khoản/điểm nguồn vs số mục answer liệt kê) CHƯA làm: Phase 1 (sửa prompt) đã chạm
gốc lỗi trích-xuất-thiếu, và đếm mục rất nhiễu với điều không đánh số rõ. Mở lại nếu số liệu cần.

# ponytail: khớp theo (số hiệu, Điều) — không bắt Khoản/Điểm, và không nhận trích dẫn từ khối
# "Quan hệ giữa các văn bản" (edges) trong prompt. Trần đã biết: có thể báo giả khi model dẫn một
# văn bản chỉ xuất hiện ở edges. Nâng khi thấy báo giả thực sự làm phiền.
"""
from __future__ import annotations

import re

_TRICH_DAN = re.compile(r"\[[^\]\n]*—[^\]\n]*\]")  # [văn bản — điều]
_SO_HIEU = re.compile(r"\d+/\d{4}")  # 40/2024
_DIEU = re.compile(r"Điều\s+\d+")


def _chu_ky(chuoi: str) -> tuple[str | None, str | None]:
    """(số hiệu, Điều) rút từ một chuỗi; None nếu không có."""
    sh = _SO_HIEU.search(chuoi)
    di = _DIEU.search(chuoi)
    return (sh.group() if sh else None, di.group() if di else None)


def hau_kiem(answer: str, chunks: list[dict], *, not_found: str) -> list[str]:
    """Trả các cờ cảnh báo (rỗng = sạch). `not_found` = câu 'chưa tìm thấy' (không cần trích dẫn)."""
    if not answer or answer.strip() == not_found.strip():
        return []

    brackets = _TRICH_DAN.findall(answer)
    if not brackets:
        return ["thiếu_trích_dẫn"]

    chunk_sig: set[tuple[str, str | None]] = set()
    for c in chunks:
        sh = _SO_HIEU.search(c.get("doc_title") or "")
        if sh:
            di = _DIEU.search(c.get("article") or "")
            chunk_sig.add((sh.group(), di.group() if di else None))

    canh_bao: list[str] = []
    for b in brackets:
        sh, di = _chu_ky(b)
        if sh is None:
            continue  # không đủ số hiệu để đối chiếu → không kết tội
        khop = any(
            csh == sh and (di is None or cdi is None or cdi == di) for csh, cdi in chunk_sig
        )
        if not khop:
            canh_bao.append(f"trích_dẫn_ngoài_căn_cứ:{b.strip('[]').strip()}")
    return canh_bao


def _demo() -> None:
    """Self-check: 4 ca cốt lõi. Chạy: python -m app.reasoning.postcheck"""
    chunks = [{"doc_title": "Thông tư 40/2024/TT-NHNN", "article": "Điều 12 Khoản 1-3"}]
    nf = "Chưa tìm thấy quy định."
    # khớp đúng → sạch
    assert hau_kiem("Theo [Thông tư 40/2024 — Điều 12 Khoản 1] thì...", chunks, not_found=nf) == []
    # không trích dẫn → cờ thiếu
    assert hau_kiem("Câu trả lời không kèm căn cứ.", chunks, not_found=nf) == ["thiếu_trích_dẫn"]
    # trích số hiệu/điều không có trong chunk → cờ ngoài căn cứ
    r = hau_kiem("Xem [Thông tư 99/2099 — Điều 5].", chunks, not_found=nf)
    assert r and r[0].startswith("trích_dẫn_ngoài_căn_cứ")
    # cùng số hiệu nhưng KHÁC điều (không có chunk điều đó) → cờ
    r2 = hau_kiem("Xem [Thông tư 40/2024 — Điều 99].", chunks, not_found=nf)
    assert r2 and r2[0].startswith("trích_dẫn_ngoài_căn_cứ")
    # câu 'chưa tìm thấy' → không cần trích dẫn
    assert hau_kiem(nf, chunks, not_found=nf) == []
    # trích dẫn thiếu số hiệu → bỏ qua, không báo giả
    assert hau_kiem("Theo [Nội bộ — Điều 3] thì...", chunks, not_found=nf) == []
    print("postcheck self-check OK")


if __name__ == "__main__":
    _demo()
