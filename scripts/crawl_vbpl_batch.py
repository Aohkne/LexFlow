"""Cào hàng loạt văn bản vbpl.vn từ một file danh sách URL (mỗi dòng 1 URL).

    uv run python scripts/crawl_vbpl_batch.py research/crawl_list.txt

Với mỗi URL ghi ra `data/raw/vbpl/<slug>.json` (3 tab) và `<slug>.corpus.json` (dạng
CorpusDocument) — đúng như lệnh `vbpl dump --corpus`, chỉ khác là chạy vòng lặp.

Bốn thứ khiến nó khác một vòng `for` gọi CLI:
  * dùng lại MỘT phiên Chromium cho cả danh sách (mỗi lần launch tốn vài giây);
  * một URL hỏng KHÔNG làm dừng cả mẻ — ghi lỗi lại rồi đi tiếp, hết mẻ mới báo cáo;
  * bỏ qua văn bản đã có file, nên chạy lại sau khi lỗi/Ctrl-C là tiếp tục chứ không cào lại;
  * nghỉ giữa hai văn bản cho lịch sự với server (mặc định 3 giây).

Ctrl-C dừng sạch và vẫn ghi báo cáo. Thoát với mã 1 nếu có URL nào hỏng.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ingestion.vbpl import (  # noqa: E402
    corpus_path,
    count_provisions,
    count_units,
    extract_document,
    open_browser,
    raw_path,
    slug_for,
    to_corpus_document,
)

_DETAIL_MARK = "/van-ban/chi-tiet/"


def read_urls(path: Path) -> list[str]:
    """URL theo thứ tự trong file, bỏ dòng trống / dòng `#` comment / URL trùng."""
    urls: list[str] = []
    seen: set[str] = set()
    # utf-8-sig: file sinh từ PowerShell/Notepad có BOM, đọc bằng utf-8 thuần thì dòng đầu
    # dính ﻿ và không còn khớp "http".
    for lineno, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not line.startswith("http"):
            raise SystemExit(f"{path}:{lineno}: không phải URL: {line[:80]!r}")
        if _DETAIL_MARK not in line:
            # Trang danh sách/tìm kiếm không có 3 tab để bóc — chặn sớm còn hơn để
            # Playwright timeout sau 45 giây.
            raise SystemExit(f"{path}:{lineno}: không phải URL văn bản chi tiết: {line[:80]!r}")
        if line in seen:
            continue
        seen.add(line)
        urls.append(line)
    return urls


def crawl_one(browser, url: str, out_dir: Path, corpus: bool) -> dict:
    """Cào 1 URL, ghi file, trả về thống kê ngắn để in ra và đưa vào báo cáo."""
    doc = extract_document(browser, url)
    slug = slug_for(url)
    path = raw_path(out_dir, slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")

    stat = {
        "canh_bao": doc["canh_bao"],
        "co_toan_van": doc["co_toan_van"],
        "slug": slug,
        "title": doc["title"],
        "trang_thai": doc["trang_thai"],
        "so_ky_tu": len(doc["noi_dung"]),
        "toan_van": count_units(doc["noi_dung"]),
        "cay_dieu_khoan": count_provisions(doc["cay_dieu_khoan"]),
        "so_tep_dinh_kem": len(doc["tep_dinh_kem"]),
        "so_dieu_bi_tac_dong": len(doc["dieu_khoan_bi_tac_dong"]),
        "so_van_ban_lien_quan": sum(
            len(items) for cats in doc["luoc_do"].values() for items in cats.values()
        ),
    }
    if corpus:
        cdoc = to_corpus_document(doc)
        cpath = corpus_path(out_dir, slug)
        cpath.parent.mkdir(parents=True, exist_ok=True)
        cpath.write_text(json.dumps(cdoc, ensure_ascii=False, indent=1), encoding="utf-8")
        stat["doc_id"] = cdoc["doc_id"]
        stat["so_dieu"] = len(cdoc["articles"])
    return stat


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("list_file", type=Path, help="file .txt, mỗi dòng 1 URL vbpl.vn")
    ap.add_argument("--out", type=Path, default=Path("data/raw/vbpl"))
    ap.add_argument("--delay", type=float, default=3.0, help="giây nghỉ giữa 2 văn bản")
    ap.add_argument("--retries", type=int, default=2, help="số lần thử lại mỗi URL khi lỗi")
    ap.add_argument("--limit", type=int, help="chỉ cào N URL đầu (để thử trước)")
    ap.add_argument("--force", action="store_true", help="cào lại cả văn bản đã có file")
    ap.add_argument("--no-corpus", action="store_true", help="không ghi bản .corpus.json")
    ap.add_argument(
        "--report",
        type=Path,
        help="file JSON báo cáo (mặc định <out>/crawl-report.json)",
    )
    args = ap.parse_args()

    urls = read_urls(args.list_file)
    if args.limit:
        urls = urls[: args.limit]
    args.out.mkdir(parents=True, exist_ok=True)
    report_path = args.report or args.out / "crawl-report.json"
    corpus = not args.no_corpus

    done: list[dict] = []
    skipped: list[str] = []
    failed: list[dict] = []
    interrupted = False

    print(f"[batch] {len(urls)} URL từ {args.list_file} → {args.out}")
    with open_browser() as browser:
        for i, url in enumerate(urls, 1):
            slug = slug_for(url)
            if not args.force and raw_path(args.out, slug).exists():
                print(f"[{i}/{len(urls)}] bỏ qua (đã có): {slug}")
                skipped.append(url)
                continue

            print(f"[{i}/{len(urls)}] {slug}")
            for attempt in range(1, args.retries + 2):
                try:
                    started = time.monotonic()
                    stat = crawl_one(browser, url, args.out, corpus)
                except KeyboardInterrupt:
                    interrupted = True
                    break
                except Exception as exc:  # noqa: BLE001 — 1 URL hỏng không được làm dừng cả mẻ
                    last = f"{type(exc).__name__}: {exc}"
                    if attempt <= args.retries:
                        wait = 5.0 * attempt
                        print(f"      lỗi ({last[:90]}) — thử lại sau {wait:.0f}s")
                        time.sleep(wait)
                        continue
                    print(f"      HỎNG sau {attempt} lần: {last[:140]}")
                    failed.append({"url": url, "error": last})
                    break
                stat["url"] = url
                stat["giay"] = round(time.monotonic() - started, 1)
                done.append(stat)
                tv = stat["toan_van"]
                print(
                    f"      OK {stat['giay']}s — {tv['dieu']} điều / {tv['khoan']} khoản / "
                    f"{tv['diem']} điểm | cây {stat['cay_dieu_khoan']} | "
                    f"{stat['so_tep_dinh_kem']} tệp | {stat['so_van_ban_lien_quan']} VB liên quan"
                    + (f" | doc_id={stat['doc_id']}" if corpus else "")
                )
                for w in stat["canh_bao"]:
                    print(f"      CẢNH BÁO: {w}")
                break

            if interrupted:
                print("\n[batch] Dừng theo Ctrl-C.")
                break
            if i < len(urls) and args.delay:
                time.sleep(args.delay)

    flagged = [d for d in done if d["canh_bao"]]
    print(
        f"\n[batch] Xong: {len(done)} cào mới, {len(skipped)} bỏ qua, {len(failed)} hỏng"
        + (f", {len(flagged)} có cảnh báo." if flagged else ".")
    )
    for d in flagged:
        print(f"    {d['slug']}")
        for w in d["canh_bao"]:
            print(f"       - {w}")
    for f in failed:
        print(f"    HỎNG {f['url']}\n         {f['error'][:150]}")
    report_path.write_text(
        json.dumps(
            {"nguon": str(args.list_file), "da_cao": done, "bo_qua": skipped, "hong": failed},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"[batch] Báo cáo: {report_path}")
    if done and corpus:
        print(
            "[batch] Bước tiếp: đưa các .corpus.json vào luồng duyệt, hoặc gộp vào văn bản "
            "đã có bằng scripts/enrich_corpus_from_vbpl.py --doc-id <id>"
        )
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
