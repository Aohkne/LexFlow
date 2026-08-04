"""Sinh **danh sách văn bản cần crawl** từ chính dữ liệu đang có.

Chạy:
    uv run python -m app.ingestion.can_crawl
    uv run python -m app.ingestion.can_crawl --corpus data/corpus.real.json --vbpl data/raw/vbpl
    uv run python -m app.ingestion.can_crawl --md docs/CAN-CRAWL.md

Vì sao là một công cụ chứ không phải một danh sách gõ tay: danh sách gõ tay đúng vào ngày gõ
rồi lệch dần mà không ai biết nó đã lệch. Ở đây mỗi dòng đều truy được về một **cạnh có thật**
trong lược đồ chính thống, và thứ tự do `MUC_UU_TIEN` quyết — *thiếu văn bản này thì hỏng cái
gì*, chứ không phải *có bao nhiêu cạnh trỏ tới nó* (đo trên dữ liệu thật: 30/30 đầu mút treo
đều đúng 1 cạnh, tức xếp theo số cạnh là xếp theo một cột hằng số).

Một chỗ danh sách này **không tự nói ra**, phải đọc kèm: lược đồ của một văn bản chỉ chứa quan
hệ *với chính nó*. Lược đồ ND52 xếp 20 Thông tư vào nhóm "Văn bản áp dụng" (`CAN_CU`), nhưng
tiêu đề của 5 trong số đó nói chúng **sửa đổi** TT15/TT17/TT40 — mà quan hệ sửa đổi ấy nằm ở
lược đồ của TT15/TT17/TT40, không nằm ở đây. Nên `--soat-sua-doi` in riêng nhóm đó ra.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.core.schemas import DocumentMeta, Relationship
from app.core.so_hieu import phan_tich
from app.ingestion.bac_cau import CanCrawl, thieu_toan_van
from app.ingestion.pipeline import load_corpus
from app.ingestion.vbpl_luoc_do import UNG_VIEN_RE, doc_luoc_do, tieu_de_theo_so_hieu

MUC_TEN = {0: "GẤP", 1: "cao", 2: "vừa", 3: "thấp"}
MUC_VI_SAO = {
    0: "nghĩa vụ có thể BIẾN MẤT — huỷ/treo hiệu lực, ca kiểm chứng §6.2",
    1: "nội dung đang áp dụng bị đổi",
    2: "thêm chi tiết cho thứ đã có",
    3: "xuất xứ / tham chiếu",
}


def _doc_vbpl(thu_muc: Path) -> tuple[list[Relationship], dict[str, str], list[str]]:
    """Đọc mọi bản ghi vbpl trong thư mục. Thiếu thư mục ⇒ rỗng, không phải lỗi."""
    canh: list[Relationship] = []
    tieu_de: dict[str, str] = {}
    canh_bao: list[str] = []
    for p in sorted(thu_muc.glob("*.json")) if thu_muc.exists() else []:
        mau = json.loads(p.read_text(encoding="utf-8"))
        c, cb = doc_luoc_do(mau)
        canh += c
        canh_bao += [f"{p.name}: {x}" for x in cb]
        for k, v in tieu_de_theo_so_hieu(mau).items():
            tieu_de.setdefault(k, v)
    return canh, tieu_de, canh_bao


def sua_doi_van_ban_ta_co(
    ds: list[CanCrawl], docs: list[DocumentMeta]
) -> list[tuple[CanCrawl, list[str]]]:
    """Văn bản chưa có, mà TIÊU ĐỀ nói nó tác động tới văn bản corpus đang có.

    Đọc từ tiêu đề là **dấu hiệu**, không phải kết luận — quan hệ thật phải lấy từ lược đồ của
    chính văn bản bị tác động. Nhưng dấu hiệu này đủ để đảo thứ tự crawl: nếu 30/2025/TT-NHNN
    sửa TT15/2024 thì corpus đang ghi TT15/2024 là "còn hiệu lực, chưa sửa đổi" — sai.
    """
    cua_ta = {d.so_hieu for d in docs if d.so_hieu}
    ra = []
    for d in ds:
        if not d.title:
            continue
        # Bỏ số hiệu ĐẦU (của chính nó); các số hiệu sau là văn bản bị tác động.
        cham = []
        for m in list(UNG_VIEN_RE.finditer(d.title))[1:]:
            sh = phan_tich(m.group(0))
            if sh and sh.chuan in cua_ta and sh.chuan not in cham:
                cham.append(sh.chuan)
        if cham:
            ra.append((d, cham))
    return ra


def _dong_md(d: CanCrawl) -> str:
    qh = " · ".join(f"`{m}` ({v})" for m, v in d.quan_he)
    return f"| {MUC_TEN.get(d.uu_tien, '?')} | `{d.so_hieu}` | {qh} | {d.title or '—'} |"


def bang_markdown(ds: list[CanCrawl], sua: list[tuple[CanCrawl, list[str]]]) -> str:
    dong = [
        "# Văn bản cần crawl",
        "",
        "**Sinh tự động** — `uv run python -m app.ingestion.can_crawl --md docs/CAN-CRAWL.md`.",
        "Đừng sửa tay: mỗi dòng truy được về một cạnh có thật trong lược đồ chính thống.",
        "",
        f"{len(ds)} văn bản xuất hiện trong đồ thị mà chưa có toàn văn.",
        "",
        "| mức | số hiệu | quan hệ (vai của văn bản còn thiếu) | tiêu đề theo nguồn |",
        "|---|---|---|---|",
    ]
    dong += [_dong_md(d) for d in ds]
    if sua:
        dong += [
            "",
            "## Ưu tiên đảo lên: sửa đổi văn bản corpus ĐANG CÓ",
            "",
            "Lược đồ của một văn bản chỉ chứa quan hệ **với chính nó**, nên các Thông tư dưới đây",
            "hiện ra ở lược đồ ND52 chỉ như `CAN_CU`. Tiêu đề của chúng nói khác — và nếu đúng thì",
            "corpus đang ghi văn bản bị sửa là *còn hiệu lực, chưa sửa đổi*.",
            "",
            "| số hiệu | tiêu đề nói nó tác động tới | quan hệ thấy ở lược đồ ND52 |",
            "|---|---|---|",
        ]
        dong += [
            f"| `{d.so_hieu}` | {', '.join(f'`{x}`' for x in cham)} | "
            f"{' · '.join(f'`{m}`' for m, _ in d.quan_he)} |"
            for d, cham in sua
        ]
    return "\n".join(dong) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Danh sách văn bản cần crawl, sinh từ dữ liệu")
    ap.add_argument("--corpus", default="data/corpus.real.json")
    ap.add_argument("--vbpl", default="data/raw/vbpl", help="thư mục bản ghi lược đồ vbpl")
    ap.add_argument("--md", help="ghi bảng Markdown ra file")
    a = ap.parse_args(argv)

    docs, rels_corpus = load_corpus(a.corpus)
    canh_vbpl, tieu_de, cb = _doc_vbpl(Path(a.vbpl))
    ds = thieu_toan_van(rels_corpus + canh_vbpl, docs, tieu_de)
    sua = sua_doi_van_ban_ta_co(ds, docs)

    print(
        f"{len(docs)} văn bản có toàn văn · {len(rels_corpus)} cạnh corpus "
        f"+ {len(canh_vbpl)} cạnh vbpl · **{len(ds)} văn bản cần crawl**"
    )
    for x in cb:
        print(f"  [cảnh báo nguồn] {x}")
    print()

    muc_truoc = None
    for d in ds:
        if d.uu_tien != muc_truoc:
            muc_truoc = d.uu_tien
            print(f"--- {MUC_TEN.get(d.uu_tien, '?')}: {MUC_VI_SAO.get(d.uu_tien, '')} ---")
        qh = ", ".join(f"{m}({v})" for m, v in d.quan_he)
        print(f"  {d.so_hieu:<18} {qh}")
        print(f"      {(d.title or '(nguồn không kèm tiêu đề)')[:96]}")

    if sua:
        print(f"\n=== {len(sua)} văn bản SỬA ĐỔI văn bản corpus đang có (theo tiêu đề) ===")
        print("    Quan hệ sửa đổi nằm ở lược đồ của văn bản BỊ SỬA, không ở lược đồ ND52.")
        for d, cham in sua:
            print(f"  {d.so_hieu:<18} → {', '.join(cham)}")

    if a.md:
        Path(a.md).write_text(bang_markdown(ds, sua), encoding="utf-8")
        print(f"\nĐã ghi {a.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
