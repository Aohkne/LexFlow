"""Extractor bán tự động: HTML/PDF văn bản pháp luật VN → CorpusDocument JSON.

Chiến lược (maker-checker):
1. Đọc file (HTML luatvietnam qua BeautifulSoup, PDF qua pypdf) → text thuần.
2. Regex tách "Điều N. Tiêu đề" (dấu chấm phân biệt điều thật với tham chiếu chéo).
3. Gemini chỉ dùng cho metadata (số hiệu, tiêu đề, ngày hiệu lực) + fallback
   khi regex thất bại (file bẩn/scan) — không LLM hoá phần tách điều khi không cần.
4. Ghi/merge vào corpus JSON — NGƯỜI DUYỆT file này trước khi ingest
   (quan hệ THAY_THE/SUA_DOI gán tay vào key "relationships").

Chạy:  uv run python -m app.ingestion.extract data/raw/ND52-2024.html
       uv run python -m app.ingestion.extract --all          # cả thư mục data/raw
Tuỳ chọn: --out data/corpus.real.json  --source internal|external
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from app.core.config import settings
from app.core.llm import chat_json
from app.core.schemas import Article, CorpusDocument
from app.core.so_hieu import phan_tich
from app.ingestion.vbpl_luoc_do import UNG_VIEN_RE

# Điều thật: "Điều 12. Tiêu đề" (tham chiếu chéo kiểu "Điều 3 Luật..." không có dấu chấm)
_DIEU_RE = re.compile(r"^Điều\s+(\d+)\s*\.\s*(.+)$")
_CHUONG_RE = re.compile(r"^Chương\s+[IVXLC\d]+\b")
# Hết phần nội dung — chữ ký / nơi nhận
_END_RE = re.compile(r"^(TM\.|KT\.|Nơi nhận\s*:|THỦ TƯỚNG|THỐNG ĐỐC|CHỦ TỊCH|BỘ TRƯỞNG)")

_META_SYSTEM = (
    "Bạn nhận phần đầu một văn bản pháp luật Việt Nam. Trích xuất metadata, trả JSON: "
    '{"doc_id": "<viết tắt kiểu TT40-2024 / ND52-2024 / QD123-2020 từ số hiệu>", '
    '"title": "<tên đầy đủ gồm loại + số hiệu + trích yếu>", '
    '"doc_type": "<Luật|Nghị định|Thông tư|Quyết định|Nội bộ>", '
    '"valid_from": "<ngày hiệu lực ISO yyyy-mm-dd, null nếu không thấy>"}. '
    "Chỉ trả JSON."
)

_FALLBACK_SYSTEM = (
    "Bạn nhận văn bản pháp luật Việt Nam dạng text lộn xộn. Tách thành các điều, trả JSON: "
    '{"articles": [{"article": "Điều <số>", "text": "<toàn bộ nội dung điều, giữ nguyên câu chữ>"}]}. '
    "Không tóm tắt, không bỏ sót điều nào. Chỉ trả JSON."
)


def read_text(path: Path) -> str:
    """HTML/PDF/TXT → text thuần, mỗi dòng một đoạn."""
    suffix = path.suffix.lower()
    if suffix in {".html", ".htm"}:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
        node = soup.select_one("article") or soup.body or soup
        return node.get_text("\n")
    if suffix == ".pdf":
        from pypdf import PdfReader

        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    return path.read_text(encoding="utf-8")


# Rác UI của luatvietnam lẫn vào text (nút theo dõi, điều hướng...)
_NOISE_LINES = {"Đang theo dõi", "Xem thêm", "Mục lục", "Tải về", "So sánh VB", "Bản in", "Lưu", "Theo dõi hiệu lực"}


def _lines(text: str) -> list[str]:
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    return [ln for ln in lines if ln not in _NOISE_LINES]


def split_articles(text: str) -> list[Article]:
    """Tách điều bằng regex. Trả [] nếu không nhận ra cấu trúc (để fallback LLM)."""
    lines = _lines(text)
    articles: list[Article] = []
    current: list[str] | None = None
    header = ""
    for ln in lines:
        if _END_RE.match(ln) and articles:
            break
        m = _DIEU_RE.match(ln)
        if m:
            if current is not None:
                articles.append(Article(article=header, text="\n".join(current)))
            header = f"Điều {m.group(1)}"
            current = [m.group(2)]  # tiêu đề điều nằm đầu text
            continue
        if current is not None and not _CHUONG_RE.match(ln):
            current.append(ln)
    if current is not None:
        articles.append(Article(article=header, text="\n".join(current)))
    return articles


# Số hiệu: bắt ỨNG VIÊN tới dấu phân cách rồi để `so_hieu.phan_tich` quyết. Khuôn cũ ở đây
# mô tả hình dạng mã bằng `[A-ZĐ]+(?:-[A-ZĐ]+)+`, và đó đúng là khuôn đã **im lặng cắt cụt**
# `51/2025/TT-BTС` (С Cyrillic) thành `51/2025/TT` — một khoá cụt vẫn join được, vào nhầm
# văn bản. Nó cũng đòi có năm, nên bỏ sót cả nhóm hành chính (`123/QĐ-NHNN`).


def so_hieu_trong(text: str) -> str | None:
    """Số hiệu của CHÍNH văn bản: ứng viên đầu tiên phân tích được, ở phần đầu văn bản.

    Trước đây `_head_text` trích số hiệu rồi **vứt** — chỉ nhét vào prompt cho Gemini đọc làm
    ngữ cảnh. Nay trả ra để điền `DocumentMeta.so_hieu`, tức cây cầu nối cạnh khoá-số-hiệu
    (lược đồ vbpl) với corpus khoá-`doc_id`.
    """
    for m in UNG_VIEN_RE.finditer(text or ""):
        sh = phan_tich(m.group(0))
        if sh:
            return sh.chuan
    return None


def _head_text(text: str, articles: list[Article]) -> str:
    """Ghép ngữ liệu cho Gemini đọc metadata: phần đầu văn bản (trước Điều 1)
    + các dòng chứa số hiệu + điều khoản thi hành (nơi ghi ngày hiệu lực)."""
    lines = _lines(text)
    end = len(lines)
    for i, ln in enumerate(lines):
        if _DIEU_RE.match(ln):
            end = i
            break
    parts = ["\n".join(lines[:end])[:5000]]
    so_hieu = [ln for ln in lines if UNG_VIEN_RE.search(ln)]
    if so_hieu:
        parts.append("Các dòng chứa số hiệu:\n" + "\n".join(so_hieu[:5]))
    for a in articles:
        if "hiệu lực" in a.text:
            parts.append(f"{a.article} (điều khoản thi hành):\n{a.text[:1500]}")
            break
    return "\n---\n".join(parts)


def extract_metadata(text: str, articles: list[Article]) -> dict:
    data = chat_json(_head_text(text, articles), system=_META_SYSTEM, reasoning=False)
    return {
        "doc_id": data.get("doc_id") or "UNKNOWN",
        "title": data.get("title") or "UNKNOWN",
        "doc_type": data.get("doc_type") or "Thông tư",
        "valid_from": data.get("valid_from"),
        # Số hiệu lấy từ PARSER, không hỏi mô hình: nó nằm nguyên văn trong văn bản, và một
        # khoá bịa ra thì vẫn join được — vào nhầm văn bản, không ai biết. Cùng lý do đã dùng
        # cho `source_diem` ở tầng CU.
        "so_hieu": so_hieu_trong(text),
    }


def _fallback_articles(text: str) -> list[Article]:
    """File bẩn (PDF scan/layout hỏng): nhờ Gemini tách điều theo từng khúc."""
    articles: list[Article] = []
    chunk_size = 30_000
    for i in range(0, len(text), chunk_size):
        data = chat_json(text[i : i + chunk_size], system=_FALLBACK_SYSTEM)
        for a in data.get("articles", []):
            if a.get("article") and a.get("text"):
                articles.append(Article(article=a["article"], text=a["text"]))
    return articles


def extract_document(path: Path, source: str = "external") -> CorpusDocument:
    text = read_text(path)
    articles = split_articles(text)
    if len(articles) < 3:
        print(f"  [extract] regex chỉ thấy {len(articles)} điều — chuyển fallback Gemini")
        articles = _fallback_articles(text)
    meta = extract_metadata(text, articles)
    return CorpusDocument(
        doc_id=meta["doc_id"],
        title=meta["title"],
        doc_type=meta["doc_type"],
        source=source,
        valid_from=meta["valid_from"],
        # `so_hieu` từng được tính ở `extract_metadata` rồi dừng lại đó — đúng thứ docstring
        # của `so_hieu_trong` nói là để điền vào đây. Thiếu nó thì `don_node_rong_da_co_toan_van`
        # (khớp `that.so_hieu = rong.doc_id`) không bao giờ khớp, và mỗi lượt duyệt qua `/admin`
        # để lại HAI node cho một văn bản. Xem T20.
        so_hieu=meta["so_hieu"],
        articles=articles,
    )


def merge_into_corpus(doc: CorpusDocument, out_path: Path) -> None:
    """Thay/thêm document theo doc_id; giữ nguyên relationships (gán tay)."""
    corpus = {"documents": [], "relationships": []}
    if out_path.exists():
        corpus = json.loads(out_path.read_text(encoding="utf-8"))
    docs = [d for d in corpus.get("documents", []) if d.get("doc_id") != doc.doc_id]
    docs.append(doc.model_dump())
    corpus["documents"] = docs
    corpus.setdefault("relationships", [])
    out_path.write_text(
        json.dumps(corpus, ensure_ascii=False, indent=1), encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Extract văn bản → corpus JSON (cần người duyệt)")
    parser.add_argument("files", nargs="*", help="file HTML/PDF/TXT trong data/raw")
    parser.add_argument("--all", action="store_true", help=f"xử lý mọi file trong {settings.data_raw_path}")
    parser.add_argument("--out", default="data/corpus.real.json")
    parser.add_argument("--source", choices=["external", "internal"], default="external")
    args = parser.parse_args(argv)

    paths = [Path(f) for f in args.files]
    if args.all:
        raw = Path(settings.data_raw_path)
        paths = sorted(p for p in raw.iterdir() if p.suffix.lower() in {".html", ".htm", ".pdf", ".txt"})
    if not paths:
        parser.error("Chưa chỉ định file (hoặc dùng --all)")

    out = Path(args.out)
    for p in paths:
        print(f"[extract] {p.name} ...")
        doc = extract_document(p, source=args.source)
        merge_into_corpus(doc, out)
        print(f"  → {doc.doc_id}: {len(doc.articles)} điều | {doc.title[:70]}")
    print(f"[extract] Đã ghi {out} — HÃY DUYỆT TAY trước khi ingest (điều khoản + gán relationships).")


if __name__ == "__main__":
    main(sys.argv[1:])
