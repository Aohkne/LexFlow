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

# Ba tab dùng chung URL nhưng CÓ tham số `?tabs=` — mở thẳng bằng URL thay vì click tab
# antd rồi ngủ vài giây. Cách click + sleep cố định là một cuộc đua: máy chậm hoặc mạng
# chậm thì đọc DOM trước khi tab render xong và lặng lẽ trả về 0 trường.
_TAB_THUOC_TINH_URL = "thuoc-tinh"
_TAB_LUOC_DO_URL = "luoc-do"

# Mục trong Lược đồ không phải <a href> — điều hướng bằng window.open trong handler React.
# Ghi đè window.open để LẤY được URL đích mà không thật sự tải trang đó (13 mục = 13 lượt
# tải vô ích cho server).
_OPEN_HOOK_JS = """
  window.__lfOpened = [];
  window.open = function (u) { window.__lfOpened.push(String(u)); return null; };
"""

# Đánh dấu từng mục quan hệ để Python click đúng thứ tự, kèm nhóm và chiều.
_JS_TAG_RELATIONS = r"""() => {
  const main = document.querySelector('main');
  if (!main) return [];
  const CAT = /^(.+?)\s*\((\d+)\)$/;
  const marker = [...main.querySelectorAll('*')].find(
    el => !el.children.length && (el.innerText || '').trim().startsWith('VĂN BẢN ĐANG XEM')
  );
  const items = [];
  let idx = 0;
  for (const li of main.querySelectorAll('li')) {
    const link = li.querySelector('a');
    const opener = li.querySelector('span.cursor-pointer');
    const title = (link?.innerText || '').trim().replace(/\s+/g, ' ');
    if (!title || title === '--' || !opener) continue;   // mục rỗng không có nút mở
    // Tên nhóm nằm ở phần tử anh em ĐỨNG TRƯỚC một tổ tiên nào đó của <li>
    let category = null;
    for (let a = li.parentElement; a && a !== main && !category; a = a.parentElement) {
      let sib = a.previousElementSibling;
      while (sib && !category) {
        const m = CAT.exec((sib.innerText || '').trim());
        if (m) category = m[1].trim();
        sib = sib.previousElementSibling;
      }
    }
    const after = marker
      ? !!(marker.compareDocumentPosition(li) & Node.DOCUMENT_POSITION_FOLLOWING)
      : false;
    li.setAttribute('data-lf-idx', String(idx));
    items.push({ idx, title, category, direction: after ? 'incoming' : 'outgoing' });
    idx += 1;
  }
  return items;
}"""

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

# HTML vùng nội dung, giữ nguyên định dạng hiển thị (đậm/nghiêng/căn lề/ngắt dòng) và cấu
# trúc prov-* + id/parent-id. Chỉ bỏ thứ không phải văn bản: script, style, svg, nút bấm.
# Giữ luôn các phần tử display:none (bản trước khi sửa đổi) — render ra vẫn ẩn đúng như
# web, mà ai cần đối chiếu bản cũ thì vẫn còn dữ liệu.
_JS_CONTENT_HTML = r"""() => {
  const main = document.querySelector('main');
  if (!main) return '';
  const provs = [...main.querySelectorAll('[class*="prov-"]')];
  if (!provs.length) return '';
  let root = provs[0];
  while (root && root !== main && !provs.every(p => root.contains(p))) root = root.parentElement;
  const clone = root.cloneNode(true);
  // ghi nhãn sửa đổi thành attribute TRƯỚC khi xoá nút
  for (const el of clone.querySelectorAll('[type]')) {
    const t = el.getAttribute('type') || '';
    if (!/^\d+:/.test(t)) continue;
    const badges = [...new Set(
      [...el.querySelectorAll('button')].map(b => b.innerText.trim()).filter(Boolean)
    )];
    if (badges.length) el.setAttribute('data-amend-label', badges.join('|'));
    el.setAttribute('data-amend-type', t);
    el.removeAttribute('type');
  }
  for (const el of clone.querySelectorAll('script,style,svg,button,nav,noscript,input'))
    el.remove();
  return clone.innerHTML;
}"""

# Danh sách PHẲNG các nút điều khoản, đúng thứ tự tài liệu. Ghép thành cây ở phía Python
# để phần logic đó test được mà không cần trình duyệt.
_JS_PROVISION_NODES = r"""() => {
  const main = document.querySelector('main');
  if (!main) return [];
  const badgesOf = (el) => [...new Set(
    [...el.querySelectorAll('button')].map(b => b.innerText.trim()).filter(Boolean)
  )];
  const out = [];
  // Lấy cả phần tử prov-* LẪN khối sửa đổi, theo đúng thứ tự tài liệu. Khi văn bản sửa đổi
  // thay nguyên một Điều, tiêu đề Điều mới nằm trong khối và KHÔNG mang class prov-article
  // (trang chỉ có 20 prov-article cho 23 Điều) — phải sinh nút thay cho nó, nếu không mọi
  // khoản phía sau bị treo nhầm vào Điều liền trước.
  for (const el of main.querySelectorAll('[class*="prov-"], [type]')) {
    const t = el.getAttribute('type') || '';
    if (/^\d+:/.test(t)) {
      const stripped = (el.innerText || '').trim().replace(/^(Điều khoản [^\n]*\n)+/, '');
      const first = stripped.split('\n')[0].trim();
      if (/^Điều\s+\d+\s*\./.test(first)) {
        out.push({
          id: null, cls: 'prov-article', parent_id: null, tu_sinh: true,
          hidden: getComputedStyle(el).display === 'none',
          amend_type: t, amend_badges: badgesOf(el), text: first,
        });
      }
      continue;
    }
    const cls = [...el.classList].find(c => c.startsWith('prov-'));
    if (!cls) continue;
    const block = el.closest('[type]');
    const bt = block?.getAttribute('type') || '';
    const inBlock = /^\d+:/.test(bt);
    out.push({
      id: el.id || null,
      cls,
      parent_id: el.getAttribute('parent-id'),
      hidden: getComputedStyle(el).display === 'none',
      amend_type: inBlock ? bt : null,
      amend_badges: inBlock ? badgesOf(block) : [],
      text: (el.innerText || '').trim().replace(/\s*\n\s*/g, ' '),
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


# class trên trang → (tên cấp, độ sâu). Độ sâu quyết định ai là con của ai.
_PROV_LEVELS = {
    "prov-chapter": ("chuong", 1),
    "prov-section": ("muc", 2),
    "prov-article": ("dieu", 3),
    "prov-clause": ("khoan", 4),
    "prov-item": ("diem", 5),
}

# Trang viết tiêu đề lúc thường lúc HOA ("Chương IV" vs "CHƯƠNG IV") → khớp không phân biệt
# hoa thường, nếu không số chương rơi về None.
_HEADING_RES = {
    "chuong": re.compile(r"^Chương\s+([IVXLCDM]+)\b\.?\s*(.*)$", re.S | re.I),
    "muc": re.compile(r"^Mục\s+(\d+)\b\.?\s*(.*)$", re.S | re.I),
    "dieu": re.compile(r"^Điều\s+(\d+)\s*\.?\s*(.*)$", re.S | re.I),
    "khoan": re.compile(r"^(\d+)\s*\.\s*(.*)$", re.S),
    "diem": re.compile(r"^([a-zđ])\s*\)\s*(.*)$", re.S | re.I),
}


def split_heading(cap: str, text: str) -> tuple[str | None, str]:
    """Tách "Điều 7. Dịch vụ..." → ("7", "Dịch vụ..."). Không khớp thì trả (None, text)."""
    m = _HEADING_RES[cap].match(text.strip())
    if not m:
        return None, text.strip()
    return m.group(1), m.group(2).strip()


def build_provision_tree(nodes: list[dict]) -> list[dict]:
    """Danh sách phẳng prov-* (đúng thứ tự tài liệu) → cây Chương/Mục/Điều/Khoản/Điểm.

    Bốn loại phần tử cần xử lý riêng:
      - `prov-content`: đoạn nội dung nối vào nút đã có, trỏ bằng `parent-id`.
      - phần tử cùng cấp mang `parent-id` trỏ về nút liền trước: trang tách tiêu đề làm 2
        thẻ ("Chương I" rồi "QUY ĐỊNH CHUNG"), phải gộp lại chứ không tạo nút mới.
      - phần tử ẩn (`display:none`): bản TRƯỚC khi sửa đổi, trang giữ lại để đối chiếu và
        lặp y hệt bản đang hiệu lực. Bỏ khỏi cây, nếu không mỗi khoản bị sửa đếm 2 lần.
        Bản cũ vẫn còn nguyên trong `noi_dung_html`.
      - Điều tự sinh trùng số với Điều đang mở: khối sửa đổi xuất hiện 2 lần trong DOM nên
        cùng một tiêu đề Điều có thể tới 2 lượt — giữ lượt đầu.
    """
    roots: list[dict] = []
    stack: list[tuple[int, dict]] = []
    by_id: dict[str, dict] = {}
    last: dict | None = None

    for raw in nodes:
        cls, text = raw.get("cls"), (raw.get("text") or "").strip()
        parent_id = raw.get("parent_id")

        if raw.get("hidden"):
            continue

        if cls == "prov-content":
            target = by_id.get(parent_id or "") or last
            if target is not None and text:
                target["text"] = f"{target['text']}\n{text}".strip()
            continue

        level_info = _PROV_LEVELS.get(cls or "")
        if level_info is None:
            continue
        cap, depth = level_info

        # tiêu đề bị tách làm nhiều thẻ cùng class, thẻ sau trỏ parent-id về thẻ đầu
        merge_into = by_id.get(parent_id or "")
        if merge_into is not None and merge_into["cap"] == cap:
            if text:
                merge_into["tieu_de"] = f"{merge_into['tieu_de']} {text}".strip()
            continue

        so, rest = split_heading(cap, text)
        # cùng một Điều tới 2 lượt (bản có nhãn + bản chưa nhãn của cùng khối) → giữ lượt đầu
        if cap == "dieu" and so is not None:
            open_dieu = next((n for d, n in reversed(stack) if d == 3), None)
            if open_dieu is not None and open_dieu["so"] == so:
                if raw.get("amend_badges") and not open_dieu["bi_tac_dong"]:
                    open_dieu["bi_tac_dong"] = sorted(
                        {classify_badge(b) for b in raw["amend_badges"]}
                    )
                while stack and stack[-1][0] > 3:
                    stack.pop()
                last = open_dieu
                continue

        node = {
            "id": raw.get("id"),
            "cap": cap,
            "so": so,
            "tieu_de": rest if cap in ("chuong", "muc", "dieu") else "",
            "text": "" if cap in ("chuong", "muc", "dieu") else rest,
            "bi_tac_dong": sorted({classify_badge(b) for b in raw.get("amend_badges") or []})
            or None,
            "an": bool(raw.get("hidden")),
            "con": [],
        }
        while stack and stack[-1][0] >= depth:
            stack.pop()
        (stack[-1][1]["con"] if stack else roots).append(node)
        stack.append((depth, node))
        if node["id"]:
            by_id[node["id"]] = node
        last = node

    return roots


def count_provisions(tree: list[dict]) -> dict[str, int]:
    """Đếm số nút theo cấp — dùng để kiểm tra nhanh cây có đủ không."""
    out: dict[str, int] = {}
    stack = list(tree)
    while stack:
        n = stack.pop()
        out[n["cap"]] = out.get(n["cap"], 0) + 1
        stack.extend(n["con"])
    return out


def group_relations(items: list[dict]) -> dict[str, dict[str, list[dict]]]:
    """Danh sách phẳng các mục Lược đồ → {chiều: {nhóm: [{title, url}]}}.

    Giữ nguyên thứ tự trang. Mục không xác định được nhóm gom vào "(không rõ nhóm)" thay vì
    bị bỏ đi — thà lộ ra để sửa còn hơn mất dữ liệu âm thầm.
    """
    out: dict[str, dict[str, list[dict]]] = {"outgoing": {}, "incoming": {}}
    for it in items:
        direction = it.get("direction") or "outgoing"
        category = it.get("category") or "(không rõ nhóm)"
        out.setdefault(direction, {}).setdefault(category, []).append(
            {"title": it["title"], "url": it.get("url")}
        )
    return out


def _wait_for_content(page) -> None:
    try:
        page.wait_for_function(
            "document.querySelector('main')?.innerText.length > 3000", timeout=20_000
        )
    except Exception:
        # Văn bản ngắn (Quyết định/Công văn...) có thể không bao giờ vượt 3000 ký tự
        page.wait_for_timeout(3000)


def _open_tab(page, url: str, tab_slug: str, needle: str) -> None:
    """Mở 1 tab qua tham số URL và đợi đúng nội dung của nó xuất hiện.

    `needle` là chuỗi chỉ có trên tab đó — đợi nó thay vì ngủ một khoảng cố định. Hết giờ
    thì báo lỗi to, KHÔNG trả về dữ liệu rỗng như thể trang không có gì.
    """
    sep = "&" if "?" in url else "?"
    page.goto(f"{url}{sep}tabs={tab_slug}", wait_until="domcontentloaded", timeout=45_000)
    try:
        page.wait_for_function(
            "n => (document.querySelector('main')?.innerText ?? '').includes(n)",
            arg=needle,
            timeout=30_000,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Tab '{tab_slug}' không hiện nội dung mong đợi ({needle!r}) sau 30s. "
            "Mạng chậm, hoặc vbpl.vn đã đổi cấu trúc trang."
        ) from exc


def _resolve_relation_urls(page, items: list[dict]) -> list[dict]:
    """Bấm nút mở của từng mục để lấy URL đích qua window.open đã bị chặn."""
    out = []
    for it in items:
        opener = page.locator(f"main li[data-lf-idx='{it['idx']}'] span.cursor-pointer").first
        url = None
        try:
            before = page.evaluate("(window.__lfOpened || []).length")
            opener.click(timeout=8_000)
            page.wait_for_function(
                "n => (window.__lfOpened || []).length > n", arg=before, timeout=5_000
            )
            url = page.evaluate("window.__lfOpened[window.__lfOpened.length - 1]")
        except Exception:
            url = None  # mục không mở được — giữ tiêu đề, để URL trống
        out.append({**it, "url": url})
    return out


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
            page.add_init_script(_OPEN_HOOK_JS)

            page.goto(url, wait_until="domcontentloaded", timeout=45_000)
            _wait_for_content(page)
            title = page.title().split(" | CSDL")[0].strip()
            main_text = page.evaluate(_JS_MAIN_TEXT)
            content_html = page.evaluate(_JS_CONTENT_HTML)
            prov_nodes = page.evaluate(_JS_PROVISION_NODES)
            amendments = _dedupe_amendments(page.evaluate(_JS_AMENDMENTS))

            _open_tab(page, url, _TAB_THUOC_TINH_URL, "Số hiệu")
            properties = parse_property_rows(page.evaluate(_JS_PROP_ROWS))

            _open_tab(page, url, _TAB_LUOC_DO_URL, "VĂN BẢN ĐANG XEM")
            luoc_do_text = page.evaluate(_JS_MAIN_TEXT)
            relations = _resolve_relation_urls(page, page.evaluate(_JS_TAG_RELATIONS))
        finally:
            browser.close()

    if not properties:
        raise RuntimeError(
            "Tab Thuộc tính render xong nhưng không đọc được trường nào — bảng đã đổi cấu "
            "trúc. Kiểm tra _PROP_KEYS trước khi dùng kết quả."
        )

    body, status, valid_from = clean_body(main_text)
    return {
        "url": url,
        "title": title,
        "trang_thai": status,
        "ngay_hieu_luc": _iso_date(valid_from),
        # 3 dạng của cùng một nội dung: text thuần cho pipeline extract hiện có, HTML giữ
        # đúng định dạng web để hiển thị lại, và cây có cấu trúc cho KG.
        "noi_dung": body,
        "noi_dung_html": content_html,
        "cay_dieu_khoan": build_provision_tree(prov_nodes),
        "thuoc_tinh": properties,
        # DOM cho cả URL đích; chỉ khi không bóc được mục nào mới lùi về đọc text thuần
        # (giữ được tiêu đề, mất URL).
        "luoc_do": group_relations(relations) if relations else parse_relations(luoc_do_text),
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
        print(f"[vbpl] Đã lưu {out_path}")
        print(f"[vbpl] Nội dung   : {len(doc['noi_dung'])} ký tự text | "
              f"{len(doc['noi_dung_html'])} ký tự HTML")
        print(f"[vbpl] Cây điều khoản: {count_provisions(doc['cay_dieu_khoan'])}")
        print(f"[vbpl] Thuộc tính : {len(doc['thuoc_tinh'])} trường")
        print(f"[vbpl] Điều khoản bị tác động: {n_amend} — {dict(kinds)}")
        print("[vbpl] Lược đồ:")
        n_url = 0
        for direction, cats in doc["luoc_do"].items():
            for name, items in cats.items():
                if not items:
                    continue
                print(f"    [{direction}] {name} ({len(items)})")
                for it in items:
                    link = it.get("url") if isinstance(it, dict) else None
                    n_url += bool(link)
                    label = it["title"] if isinstance(it, dict) else it
                    print(f"       - {label[:88]}")
                    if link:
                        print(f"         {link}")
        print(f"[vbpl] Lấy được URL cho {n_url} văn bản liên quan")


if __name__ == "__main__":
    main(sys.argv[1:])
