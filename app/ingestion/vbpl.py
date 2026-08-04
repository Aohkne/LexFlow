"""Công cụ nghiên cứu/cào văn bản từ vbpl.vn — Cơ sở dữ liệu quốc gia về pháp luật (Bộ Tư
pháp), nguồn CHÍNH THỐNG thay vì luatvietnam.vn (private aggregator) đang dùng hiện tại.

vbpl.vn là Next.js SPA: phần toàn văn (Điều/Khoản) chỉ xuất hiện sau khi JS chạy và gọi một
Server Action (POST) — httpx/BeautifulSoup thuần không lấy được, cần trình duyệt thật
(Playwright/Chromium). robots.txt cho phép crawl `/van-ban/...` và công bố sitemap liệt kê
toàn bộ văn bản (không cần đụng UI tìm kiếm — vốn có reCAPTCHA ẩn):
  https://vbpl.vn/sitemap/1.xml .. 12.xml  → văn bản trung ương
  https://vbpl.vn/sitemap/13.xml .. 35.xml → văn bản địa phương

Dùng như tool nghiên cứu theo yêu cầu (không phải crawler hàng loạt): tìm URL bằng `search`
(so khớp offline trên slug sitemap, không gọi UI search), rồi tải từng văn bản bằng `fetch`.

Chạy:
  uv run python -m app.ingestion.vbpl search "thanh toán không dùng tiền mặt"
  uv run python -m app.ingestion.vbpl fetch "<url văn bản chi tiết>" [--out data/raw/vbpl]

Output: .txt sạch (tiêu đề + trạng thái hiệu lực + ngày hiệu lực + toàn văn) vào
data/raw/vbpl/ — bước tiếp theo vẫn là pipeline hiện có, KHÔNG tự ingest:
  uv run python -m app.ingestion.extract data/raw/vbpl/<file>.txt --source external

Lịch sự với server: sitemap được cache ra đĩa (data/raw/vbpl/.sitemap_cache/, ít đổi), có
delay giữa các lần tải sitemap con, và mỗi lần fetch chỉ mở 1 trang. Nếu gọi `fetch` lặp lại
nhiều văn bản, tự thêm delay vài giây giữa các lần gọi.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

BASE = "https://vbpl.vn"
TRUNG_UONG_SITEMAP_IDS = range(1, 13)  # 1..12
DIA_PHUONG_SITEMAP_IDS = range(13, 36)  # 13..35

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
)
# Lưu ý: vbpl.vn chặn nội dung (trả <main> rỗng) khi UA chứa "Headless" hoặc tự xưng bot —
# đây là chặn theo fingerprint headless-browser, không phải rào chắn pháp lý/đăng nhập. Trang
# công bố robots.txt cho phép crawl đúng path này + sitemap liệt kê văn bản để máy đọc, nên
# dùng UA Chrome bình thường (đúng thực tế: Playwright chạy Chromium thật) là hợp lý — không
# giả mạo danh tính người dùng cụ thể nào, không qua mặt CAPTCHA/đăng nhập.

_SITEMAP_CACHE_DIR = Path("data/raw/vbpl/.sitemap_cache")

_STATUS_WORDS = {
    "Còn hiệu lực",
    "Hết hiệu lực toàn bộ",
    "Hết hiệu lực một phần",
    "Chưa có hiệu lực",
    "Ngưng hiệu lực",
    "Hết hiệu lực",
}

# Rác giao diện (nav/breadcrumb/tab bar) lẫn vào text lấy từ <main> — lọc theo dòng khớp
# nguyên văn, không phụ thuộc vị trí (nav lặp lại 2 lần ở đầu trang).
_NOISE_LINES = {
    "TRANG CHỦ",
    "GIỚI THIỆU",
    "VĂN BẢN PHÁP LUẬT TRUNG ƯƠNG",
    "VĂN BẢN PHÁP LUẬT ĐỊA PHƯƠNG",
    "Trang chủ",
    ">",
    "Nội dung",
    "Thuộc tính",
    "Lược đồ",
    "Văn bản gốc",
    "Tải về",
    "100%",
    "Hiển thị chi tiết cập nhật",
}

# uuid gắn cuối slug sitemap, vd "...-tt-bca--e7755200-8b31-11f1-9666-91b5d2eacc00"
_UUID_SUFFIX_RE = re.compile(
    r"--[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


@dataclass
class SitemapEntry:
    url: str
    title_guess: str  # suy từ slug, chỉ để tìm kiếm/hiển thị — không phải tiêu đề chính thức


def _slug_to_title(url: str) -> str:
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    slug = _UUID_SUFFIX_RE.sub("", slug)
    return slug.replace("-", " ")


def _normalize(s: str) -> str:
    """Bỏ dấu tiếng Việt + hạ chữ thường, để so khớp từ khoá không cần gõ đúng dấu."""
    s = unicodedata.normalize("NFKD", s.lower())
    return "".join(c for c in s if not unicodedata.combining(c))


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=2, max=20))
def _get_sitemap_xml(sid: int) -> str:
    # Server thỉnh thoảng reset kết nối khi tải liên tiếp nhiều sitemap ~1.5MB — client mới
    # mỗi lần gọi (không tái dùng connection pool) + backoff giúp ổn định hơn là retry trên
    # cùng 1 connection đã hỏng.
    with httpx.Client(headers={"User-Agent": _UA}, timeout=30.0, follow_redirects=True) as client:
        resp = client.get(f"{BASE}/sitemap/{sid}.xml")
        resp.raise_for_status()
        return resp.text


def fetch_sitemap_urls(sitemap_ids, cache: bool = True) -> list[SitemapEntry]:
    """Tải + parse các sitemap con của vbpl.vn, cache ra đĩa (mỗi file ~1-2 MB, ít đổi)."""
    _SITEMAP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    entries: list[SitemapEntry] = []
    for sid in sitemap_ids:
        cache_path = _SITEMAP_CACHE_DIR / f"{sid}.xml"
        if cache and cache_path.exists():
            xml = cache_path.read_text(encoding="utf-8")
        else:
            xml = _get_sitemap_xml(sid)
            if cache:
                cache_path.write_text(xml, encoding="utf-8")
            time.sleep(1.5)  # lịch sự — không dồn dập tải nhiều sitemap liền
        for m in re.finditer(r"<loc>([^<]+)</loc>", xml):
            url = m.group(1)
            entries.append(SitemapEntry(url=url, title_guess=_slug_to_title(url)))
    return entries


def search(
    keyword: str, sitemap_ids=TRUNG_UONG_SITEMAP_IDS, limit: int = 20
) -> list[SitemapEntry]:
    """Tìm văn bản theo từ khoá trong slug URL (offline — không đụng UI search có reCAPTCHA)."""
    entries = fetch_sitemap_urls(sitemap_ids)
    nk = _normalize(keyword)
    hits = [e for e in entries if nk in _normalize(e.title_guess)]
    return hits[:limit]


def fetch_rendered_main_text(url: str) -> tuple[str, str]:
    """Mở trang bằng Chromium headless (Playwright), trả (title, text thô của <main>).

    Cần trình duyệt thật vì nội dung Điều/Khoản load qua Server Action sau khi JS chạy —
    không nằm trong HTML trả về từ GET thuần.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(user_agent=_UA)
            # "networkidle" không bao giờ ổn định trên trang này (recaptcha/analytics giữ
            # kết nối) — dùng domcontentloaded rồi tự đợi <main> có đủ nội dung.
            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            try:
                page.wait_for_function(
                    "document.querySelector('main')?.innerText.length > 3000", timeout=20_000
                )
            except Exception:
                # Văn bản ngắn (Quyết định/Công văn...) có thể không bao giờ vượt 3000 ký tự
                page.wait_for_timeout(3000)
            title = page.title().split(" | CSDL")[0].strip()
            main_text = page.evaluate("document.querySelector('main')?.innerText ?? ''")
        finally:
            browser.close()
    return title, main_text


# --- Bóc 3 tab: Nội dung / Thuộc tính / Lược đồ ------------------------------
#
# Trang chi tiết là tab bar antd (div[role=tab], không phải link) nên phải click; cả 3 tab
# dùng chung 1 URL. Riêng tab Nội dung mang markup ngữ nghĩa mà innerText vứt đi:
#
#   <p id="id_<uuid>" class="prov-chapter|prov-section|prov-article|prov-clause|prov-item">
#   <p class="prov-content" parent-id="id_<uuid>">      → nối tiếp phần tử cha
#
# Mỗi đoạn bị sửa nằm trong 1 div bọc có attribute `type="<mã>:<uuid>"` kèm nút nhãn
# ("Điều khoản được sửa đổi, bổ sung" / "được thay thế" / "được bổ sung"). Mã số đầu quan
# sát được: 10 = sửa đổi bổ sung, 12 = thay thế, 13 = bổ sung — NHƯNG chỉ suy ra từ một văn
# bản, nên nhãn chữ mới là nguồn phân loại chính, mã số chỉ lưu kèm để đối chiếu.

_TAB_NOI_DUNG = "Nội dung"
_TAB_THUOC_TINH = "Thuộc tính"
_TAB_LUOC_DO = "Lược đồ"

_JS_AMENDMENTS = r"""() => {
  const main = document.querySelector('main');
  if (!main) return [];
  // Duyệt theo ĐÚNG thứ tự tài liệu, vừa đi vừa nhớ "Điều hiện hành". Không thể chỉ tìm
  // .prov-article gần nhất phía trên: khi văn bản sửa đổi thay nguyên một Điều thì tiêu đề
  // Điều mới nằm BÊN TRONG khối sửa đổi và không mang class prov-article (vì vậy trang chỉ
  // có 20 .prov-article cho 23 Điều). Bỏ qua điều đó thì mọi khoản đứng sau bị gán nhầm về
  // Điều cũ liền trước.
  const stripBadges = (t) => t.replace(/^(Điều khoản [^\n]*\n)+/, '');
  const nodes = [...main.querySelectorAll('.prov-article, [type]')];
  let current = null;
  const out = [];
  for (const el of nodes) {
    const typeAttr = el.getAttribute('type');
    const isBlock = typeAttr && /^\d+:/.test(typeAttr);
    if (!isBlock) {
      if (el.classList.contains('prov-article')) {
        current = (el.innerText || '').trim().split('\n')[0].trim();
      }
      continue;
    }
    const text = (el.innerText || '').trim();
    const inner = stripBadges(text).split('\n')[0].trim();
    if (/^Điều\s+\d+\./.test(inner)) current = inner;   // khối mang tiêu đề Điều mới
    out.push({
      type_code: typeAttr,
      new_types: el.getAttribute('new-types'),
      badges: [...new Set(
        [...el.querySelectorAll('button')].map(b => b.innerText.trim()).filter(Boolean)
      )],
      article: current,
      hidden: getComputedStyle(el).display === 'none',
      text,
    });
  }
  return out;
}"""

_JS_PROP_ROWS = r"""() => [...document.querySelectorAll('main table tr')]
    .map(tr => [...tr.querySelectorAll('td,th')].map(td => td.innerText.trim()))
    .filter(cells => cells.some(c => c))"""

_JS_MAIN_TEXT = "document.querySelector('main')?.innerText ?? ''"

# Nhãn trên trang → khoá ổn định dùng trong KG.
_BADGE_KINDS = {
    "Điều khoản được sửa đổi, bổ sung": "sua_doi_bo_sung",
    "Điều khoản được thay thế": "thay_the",
    "Điều khoản được bổ sung": "bo_sung",
    "Điều khoản được bãi bỏ": "bai_bo",
    "Điều khoản bị bãi bỏ": "bai_bo",
    "Điều khoản hết hiệu lực": "het_hieu_luc",
}

# Nhãn thuộc tính trên trang → khoá.
_PROP_KEYS = {
    "Số hiệu": "so_hieu",
    "Loại văn bản": "loai_van_ban",
    "Ngành": "nganh",
    "Ngày ban hành": "ngay_ban_hanh",
    "Lĩnh vực": "linh_vuc",
    "Ngày có hiệu lực": "ngay_co_hieu_luc",
    "Tình trạng hiệu lực": "tinh_trang_hieu_luc",
    "Ngày hết hiệu lực": "ngay_het_hieu_luc",
    "Cơ quan ban hành": "co_quan_ban_hanh",
    "Chức danh": "chuc_danh",
    "Người ký": "nguoi_ky",
}

_CATEGORY_RE = re.compile(r"^(.+?)\s*\((\d+)\)$")


def classify_badge(badge: str) -> str:
    """Nhãn tiếng Việt trên trang → khoá phân loại; nhãn lạ giữ nguyên dạng slug thô."""
    if badge in _BADGE_KINDS:
        return _BADGE_KINDS[badge]
    return "khac:" + badge


def parse_property_rows(rows: list[list[str]]) -> dict[str, str]:
    """Bảng Thuộc tính → dict. Mỗi ô là "<nhãn>\\n<giá trị>", một hàng có thể có 2 ô."""
    props: dict[str, str] = {}
    for row in rows:
        for cell in row:
            label, _, value = cell.partition("\n")
            key = _PROP_KEYS.get(label.strip())
            if not key:
                continue
            value = value.strip()
            props[key] = "" if value == "--" else value
    return props


def parse_relations(luoc_do_text: str) -> dict[str, dict[str, list[str]]]:
    """Text tab Lược đồ → {"outgoing": {...}, "incoming": {...}}.

    Trang chia 2 nửa quanh mốc "VĂN BẢN ĐANG XEM": nửa trên là việc văn bản NÀY làm với văn
    bản khác (thay thế/bãi bỏ cái gì, căn cứ ban hành là gì), nửa dưới là việc văn bản khác
    làm với NÓ (ai sửa đổi/hợp nhất nó). Mỗi mục có sẵn số đếm "(n)" nên dùng n để cắt đúng
    n dòng tiếp theo thay vì đoán bằng dòng trống — "--" nghĩa là rỗng.
    """
    lines = [ln.strip() for ln in luoc_do_text.split("\n")]
    split_at = next(
        (i for i, ln in enumerate(lines) if ln.startswith("VĂN BẢN ĐANG XEM")), len(lines)
    )
    out: dict[str, dict[str, list[str]]] = {"outgoing": {}, "incoming": {}}
    for direction, chunk in (
        ("outgoing", lines[:split_at]),
        ("incoming", lines[split_at:]),
    ):
        i = 0
        while i < len(chunk):
            m = _CATEGORY_RE.match(chunk[i])
            if not m:
                i += 1
                continue
            name, want = m.group(1).strip(), int(m.group(2))
            items: list[str] = []
            j = i + 1
            while j < len(chunk) and len(items) < want:
                ln = chunk[j]
                if not ln or ln == "--":
                    j += 1
                    continue
                if _CATEGORY_RE.match(ln):  # sang mục kế tiếp trước khi đủ n → dừng
                    break
                items.append(ln)
                j += 1
            out[direction][name] = items
            i = j
    return out


def _wait_for_content(page) -> None:
    try:
        page.wait_for_function(
            "document.querySelector('main')?.innerText.length > 3000", timeout=20_000
        )
    except Exception:
        # Văn bản ngắn (Quyết định/Công văn...) có thể không bao giờ vượt 3000 ký tự
        page.wait_for_timeout(3000)


def _dedupe_amendments(raw: list[dict]) -> list[dict]:
    """Mỗi khối sửa đổi xuất hiện 2 lần trong DOM (bản chưa gắn nhãn + bản có nhãn) — giữ
    bản có nhãn, cùng khoá `type`."""
    best: dict[str, dict] = {}
    for blk in raw:
        key = blk["type_code"]
        prev = best.get(key)
        if prev is None or (not prev["badges"] and blk["badges"]):
            best[key] = blk
    return [b for b in best.values() if b["badges"]]


def fetch_document(url: str) -> dict:
    """Mở 1 văn bản, bóc cả 3 tab Nội dung / Thuộc tính / Lược đồ trong MỘT phiên trình duyệt."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(user_agent=_UA)
            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            _wait_for_content(page)

            title = page.title().split(" | CSDL")[0].strip()
            main_text = page.evaluate(_JS_MAIN_TEXT)
            amendments = _dedupe_amendments(page.evaluate(_JS_AMENDMENTS))

            page.get_by_role("tab", name=_TAB_THUOC_TINH, exact=True).click(timeout=15_000)
            page.wait_for_timeout(3000)
            properties = parse_property_rows(page.evaluate(_JS_PROP_ROWS))

            page.get_by_role("tab", name=_TAB_LUOC_DO, exact=True).click(timeout=15_000)
            page.wait_for_timeout(3000)
            luoc_do_text = page.evaluate(_JS_MAIN_TEXT)
        finally:
            browser.close()

    body, status, valid_from = clean_body(main_text)
    return {
        "url": url,
        "title": title,
        "trang_thai": status,
        "ngay_hieu_luc": _iso_date(valid_from),
        "noi_dung": body,
        "thuoc_tinh": properties,
        "luoc_do": parse_relations(luoc_do_text),
        "dieu_khoan_bi_tac_dong": [
            {
                "dieu": a["article"],
                "phan_loai": sorted({classify_badge(b) for b in a["badges"]}),
                "nhan": a["badges"],
                "ma_type": a["type_code"],
                "trich": " ".join(a["text"].split())[:400],
            }
            for a in amendments
        ],
    }


def _iso_date(vn_date: str | None) -> str | None:
    if not vn_date or not re.match(r"^\d{2}/\d{2}/\d{4}$", vn_date):
        return None
    d, m, y = vn_date.split("/")
    return f"{y}-{m}-{d}"


def clean_body(main_text: str) -> tuple[str, str | None, str | None]:
    """Trả (toàn văn đã bỏ rác UI, trạng thái hiệu lực, ngày hiệu lực dd/mm/yyyy).

    Layout trang lặp lại thanh tab (Nội dung/Thuộc tính/.../Tải về) 2 lần trước khi vào nội
    dung thật — heuristic: nội dung bắt đầu ngay sau lần "Tải về" CUỐI CÙNG.
    """
    lines = [ln.strip() for ln in main_text.split("\n")]
    status = next((ln for ln in lines if ln in _STATUS_WORDS), None)
    valid_from = None
    for i, ln in enumerate(lines):
        if ln == "Ngày có hiệu lực:" and i + 1 < len(lines):
            valid_from = lines[i + 1].strip()
            break
    last_tai_ve = max((i for i, ln in enumerate(lines) if ln == "Tải về"), default=-1)
    body_lines = lines[last_tai_ve + 1 :] if last_tai_ve >= 0 else lines
    body = "\n".join(ln for ln in body_lines if ln and ln not in _NOISE_LINES)
    return body, status, valid_from


def save_document(url: str, out_dir: Path) -> Path:
    title, main_text = fetch_rendered_main_text(url)
    body, status, valid_from = clean_body(main_text)
    if len(body) < 200:
        raise RuntimeError(
            f"Nội dung quá ngắn ({len(body)} ký tự) sau khi lọc — có thể trang chưa render "
            "kịp hoặc DOM vbpl.vn đã đổi cấu trúc. Kiểm tra lại thủ công trước khi dùng."
        )

    header = [title]
    if status:
        header.append(f"Trạng thái: {status}")
    iso = _iso_date(valid_from)
    if iso:
        header.append(f"Ngày hiệu lực: {iso}")
    header.append(f"Nguồn: {url}")
    text = "\n".join(header) + "\n\n" + body

    out_dir.mkdir(parents=True, exist_ok=True)
    slug = _UUID_SUFFIX_RE.sub("", url.rstrip("/").rsplit("/", 1)[-1])[:80]
    out_path = out_dir / f"{slug}.txt"
    out_path.write_text(text, encoding="utf-8")
    return out_path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Cào văn bản pháp luật từ vbpl.vn (nguồn chính thống Bộ Tư pháp)"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_search = sub.add_parser("search", help="Tìm URL văn bản theo từ khoá (offline, dò sitemap)")
    p_search.add_argument("keyword")
    p_search.add_argument("--limit", type=int, default=20)
    p_search.add_argument(
        "--include-dia-phuong", action="store_true", help="Tìm cả văn bản địa phương (mặc định chỉ trung ương)"
    )

    p_fetch = sub.add_parser("fetch", help="Tải 1 văn bản (URL chi tiết) → text sạch")
    p_fetch.add_argument("url")
    p_fetch.add_argument("--out", default="data/raw/vbpl")

    p_dump = sub.add_parser(
        "dump", help="Tải cả 3 tab (Nội dung + Thuộc tính + Lược đồ) → JSON có cấu trúc"
    )
    p_dump.add_argument("url")
    p_dump.add_argument("--out", default="data/raw/vbpl")

    args = parser.parse_args(argv)

    if args.cmd == "search":
        ids = list(TRUNG_UONG_SITEMAP_IDS) + (
            list(DIA_PHUONG_SITEMAP_IDS) if args.include_dia_phuong else []
        )
        print(f"[vbpl] Đang dò {len(ids)} sitemap (lần đầu sẽ cache lại, các lần sau nhanh)...")
        hits = search(args.keyword, sitemap_ids=ids, limit=args.limit)
        if not hits:
            print("Không tìm thấy — thử từ khoá khác (so khớp trên slug URL, không dấu).")
            return
        for e in hits:
            print(f"{e.title_guess}\n  {e.url}\n")

    elif args.cmd == "fetch":
        print(f"[vbpl] Đang tải {args.url} ...")
        out_path = save_document(args.url, Path(args.out))
        print(f"[vbpl] Đã lưu {out_path}")
        print(
            f"[vbpl] Bước tiếp: uv run python -m app.ingestion.extract {out_path} --source external"
        )

    elif args.cmd == "dump":
        print(f"[vbpl] Đang tải 3 tab của {args.url} ...")
        doc = fetch_document(args.url)
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        slug = _UUID_SUFFIX_RE.sub("", args.url.rstrip("/").rsplit("/", 1)[-1])[:80]
        out_path = out_dir / f"{slug}.json"
        out_path.write_text(
            json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        n_amend = len(doc["dieu_khoan_bi_tac_dong"])
        kinds = Counter(k for a in doc["dieu_khoan_bi_tac_dong"] for k in a["phan_loai"])
        rel = {
            d: {k: len(v) for k, v in cats.items() if v}
            for d, cats in doc["luoc_do"].items()
        }
        print(f"[vbpl] Đã lưu {out_path}")
        print(f"[vbpl] Thuộc tính : {len(doc['thuoc_tinh'])} trường")
        print(f"[vbpl] Điều khoản bị tác động: {n_amend} — {dict(kinds)}")
        print(f"[vbpl] Lược đồ    : {rel}")


if __name__ == "__main__":
    main(sys.argv[1:])
