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
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote

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
_TAB_TAI_VE_URL = "tai-ve"

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
  // Nhãn vbpl chèn vào, KHÔNG thuộc văn bản. Bắt buộc có "được|bị": "Điều khoản thi hành" là
  // tiêu đề Điều có thật, lọc theo tiền tố "Điều khoản" trần sẽ ăn mất nó.
  const stripBadges = (s) => s.replace(/^(Điều khoản (được|bị) [^\n]*\n)+/, '');
  const norm = (s) => (s || '').replace(/\s+/g, ' ').trim();
  // Mỗi khối sửa đổi có mặt 2 lần: bản mang class prov-* (không nhãn) và bản bọc ngoài có
  // nhãn. Ghép cặp theo NỘI DUNG chứ không theo mã `type` — nhiều khối khác nhau dùng chung
  // một mã (cùng văn bản sửa đổi), nên ghép theo mã sẽ nuốt mất khối thật.
  const daCoMarkup = new Set(
    [...main.querySelectorAll('[class*="prov-"]')].map(e => norm(e.innerText))
  );
  // Cấp của một dòng, suy từ cách đánh số. Cố tình KHÔNG nhận "(i)"/"(ii)": cấp tiết được
  // mô hình hoá như một span bên trong Điểm chứ không có id riêng.
  const capOf = (line) => {
    if (/^Điều\s+\d+\s*\./.test(line)) return 'prov-article';
    if (/^\d+[a-z]?\.\s/.test(line)) return 'prov-clause';   // "3b." là số khoản có thật
    if (/^[a-zđ]\)\s/.test(line)) return 'prov-item';
    return null;
  };
  const out = [];
  const viTri = new Map();   // nội dung chuẩn hoá → vị trí nút trong `out`
  // Lấy cả phần tử prov-* LẪN khối sửa đổi, theo đúng thứ tự tài liệu.
  for (const el of main.querySelectorAll('[class*="prov-"], [type]')) {
    const t = el.getAttribute('type') || '';
    const isBlock = /^\d+:/.test(t);
    const cls = [...el.classList].find(c => c.startsWith('prov-'));

    // Phần tử điều khoản thật. Phải xét TRƯỚC nhánh khối: khi khối sửa đổi chỉ thay đúng
    // một Khoản, chính thẻ prov-clause đó mang luôn attribute `type`, và nếu ưu tiên nhánh
    // khối thì cả Khoản bị bỏ (chỉ tiêu đề Điều mới được giữ lại).
    if (cls) {
      const block = el.closest('[type]');
      const bt = block?.getAttribute('type') || '';
      const inBlock = /^\d+:/.test(bt) ? bt : (isBlock ? t : '');
      viTri.set(norm(stripBadges((el.innerText || '').trim())), out.length);
      out.push({
        id: el.id || null,
        cls,
        parent_id: el.getAttribute('parent-id'),
        hidden: getComputedStyle(el).display === 'none',
        amend_type: inBlock || null,
        amend_badges: inBlock ? badgesOf(block || el) : [],
        text: stripBadges((el.innerText || '').trim()).replace(/\s*\n\s*/g, ' '),
        html: el.innerHTML,   // giữ đậm/nghiêng; lọc bằng whitelist ở phía Python
      });
      continue;
    }
    if (!isBlock) continue;

    const hidden = getComputedStyle(el).display === 'none';
    const badges = badgesOf(el);
    const body = stripBadges((el.innerText || '').trim());
    const lines = body.split('\n').map(s => s.trim()).filter(Boolean);
    // Bản có nhãn của một khối đã được lấy qua thẻ prov-* của chính nó → bỏ, kẻo đếm 2 lần.
    // Nhãn thì chỉ bản này có, nên chuyển sang nút đã giữ trước khi bỏ.
    if (daCoMarkup.has(norm(body))) {
      const i = viTri.get(norm(body));
      if (i !== undefined && badges.length) out[i].amend_badges = badges;
      continue;
    }

    // Khối CÓ markup prov-* bên trong: các phần tử đó tự vào vòng lặp này rồi, ở đây chỉ
    // cần bù tiêu đề Điều — trang không gắn class cho nó (23 Điều nhưng chỉ 20 prov-article).
    if (el.querySelector('[class*="prov-"]')) {
      if (lines.length && capOf(lines[0]) === 'prov-article') {
        out.push({
          id: null, cls: 'prov-article', parent_id: null, tu_sinh: true, hidden,
          amend_type: t, amend_badges: badges, text: lines[0], html: '',
        });
      }
      continue;
    }

    // Khối KHÔNG có markup nào: toàn bộ phần được sửa đổi nằm ở dạng text thuần. Đây là
    // chỗ cây mất Khoản/Điểm — sinh nút theo cách đánh số của từng dòng.
    for (const line of lines) {
      const c = capOf(line);
      out.push({
        id: null, cls: c || 'prov-content', parent_id: null, tu_sinh: true, hidden,
        amend_type: t, amend_badges: c ? badges : [], text: line, html: '',
      });
    }
  }
  return out;
}"""

# Tab "Tải về": tên tệp / dung lượng / ngày nằm ở 3 phần tử lá liền nhau, KHÔNG có thẻ <a>
# nào — nên phải đọc theo dòng lá rồi ghép, chứ không lấy href được.
_JS_FILE_LEAVES = r"""() => [...document.querySelector('main').querySelectorAll('*')]
    .filter(e => !e.children.length)
    .map(e => (e.innerText || '').trim())
    .filter(t => t && t.length < 200)"""

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


# Chỉ những thẻ này được đi tiếp vào hệ thống. Mọi thẻ khác bị bóc bỏ (giữ lại chữ bên
# trong), mọi attribute bị vứt — kể cả style, class, id, on*. Trang nguồn là site ngoài;
# nội dung của nó cuối cùng sẽ được render trong app, nên whitelist phải hẹp và cố định,
# không phải blacklist "bỏ những thứ nguy hiểm đã biết".
_INLINE_TAGS = {"b", "strong", "i", "em", "u", "sup", "sub", "br"}
_VOID_TAGS = {"br"}


class _InlineSanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._open: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag not in _INLINE_TAGS:
            return
        if tag in _VOID_TAGS:
            self.parts.append(f"<{tag}>")
            return
        self.parts.append(f"<{tag}>")
        self._open.append(tag)

    def handle_startendtag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in _VOID_TAGS:
            self.parts.append(f"<{tag}>")

    def handle_endtag(self, tag: str) -> None:
        if tag not in _INLINE_TAGS or tag in _VOID_TAGS:
            return
        if tag in self._open:
            # đóng cả những thẻ lồng chưa đóng, giữ HTML luôn cân
            while self._open:
                t = self._open.pop()
                self.parts.append(f"</{t}>")
                if t == tag:
                    break

    def handle_data(self, data: str) -> None:
        self.parts.append(escape(data, quote=False))

    def result(self) -> str:
        while self._open:
            self.parts.append(f"</{self._open.pop()}>")
        return "".join(self.parts)


def sanitize_inline(html: str) -> str:
    """HTML thô của một đoạn → chỉ còn thẻ nhấn mạnh inline, không attribute nào.

    Trả chuỗi rỗng nếu sau khi lọc không còn chữ nào.
    """
    if not html:
        return ""
    p = _InlineSanitizer()
    p.feed(html)
    p.close()
    out = re.sub(r"\s+", " ", p.result()).strip()
    return "" if not re.sub(r"<[^>]+>", "", out).strip() else out


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

        html = sanitize_inline(raw.get("html") or "")

        if cls == "prov-content":
            target = by_id.get(parent_id or "") or last
            if target is not None and text:
                target["text"] = f"{target['text']}\n{text}".strip()
                target["html"] = f"{target['html']}<br>{html}" if target["html"] else html
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
            # HTML inline đã lọc, GIỮ cả tiền tố số ("1. ", "a) ") vì đó là cách đọc tự
            # nhiên của điều khoản; tiêu đề Chương/Mục/Điều thì app tự dựng từ so + tieu_de
            # nên không cần HTML.
            "html": "" if cap in ("chuong", "muc", "dieu") else html,
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


# Tiêu đề trong TOÀN VĂN. "Điều" giữ nguyên chữ hoa/thường vì "ĐIỀU KHOẢN THI HÀNH" là tiêu
# đề Chương, không phải Điều; Chương/Mục thì có văn bản viết hoa cả dòng ("CHƯƠNG IV").
_TEXT_DIEU_RE = re.compile(r"^Điều\s+(\d+)\s*\.\s*(.*)$")
_TEXT_CHUONG_RE = re.compile(r"^Chương\s+([IVXLCDM]+|\d+)\s*\.?\s*(.*)$", re.I)
_TEXT_MUC_RE = re.compile(r"^Mục\s+(\d+)\s*\.?\s*(.*)$", re.I)
# Hậu tố chữ là số khoản có thật: văn bản sửa đổi chèn "khoản 3a, 3b" vào giữa 3 và 4.
_TEXT_KHOAN_RE = re.compile(r"^(\d+[a-z]?)\.\s")
_TEXT_DIEM_RE = re.compile(r"^([a-zđ])\)\s")


# Ranh giới THÂN văn bản. Phụ lục hay là biểu mẫu (giấy phép, đơn đề nghị) và có "Điều 1..7"
# của riêng nó — đếm chúng vào là thổi phồng số điều (66/2025: 16 điều thật, 37 nếu tính phụ
# lục). Khoá node phía sau cũng chỉ neo vào thân ("#than/dieu_{n}").
_PHU_LUC_RE = re.compile(r"^PHỤ LỤC\b")


# Khối trích dẫn của văn bản sửa đổi. Văn bản sửa đổi luôn CHÉP NGUYÊN VĂN nội dung mới vào
# giữa hai dấu ngoặc kép, và phần chép mang đánh số của văn bản BỊ SỬA chứ không phải của văn
# bản đang đọc. 80/2016/NĐ-CP Điều 1 là ca rõ nhất:
#
#     1. Sửa đổi, bổ sung khoản 4, 5, 6, 7, 8 Điều 4 như sau:   ← khoản 1 của ND80
#     "4. Tổ chức cung ứng dịch vụ trung gian thanh toán là ...
#      5. Chủ tài khoản thanh toán ...                          ← khoản 5 của ND101
#     ...
#     5. Sửa đổi điểm b khoản 2 Điều 12 như sau:                ← khoản 5 của ND80
#
# nên số 5 xuất hiện hai lần mà KHÔNG phải hai phiên bản của một khoản — là hai văn bản.
#
# Dấu ngoặc là của chính văn bản: bỏ nó đi là sửa nguồn và làm mất nghĩa "đoạn này là trích".
# Ở đây chỉ dùng nó để biết dòng nào mang đánh số của văn bản khác. Đo trên cả 9 văn bản của
# lô này thì ngoặc CÂN 100% (`"` luôn chẵn, số `“` bằng số `”`) nên máy trạng thái là đủ.
_QUOTE_TOGGLE = '"'
_QUOTE_OPEN = "“"
_QUOTE_CLOSE = "”"


def _quote_step(line: str, straight: bool, depth: int) -> tuple[bool, int]:
    """Trạng thái ngoặc sau khi đi hết một dòng."""
    for c in line:
        if c == _QUOTE_TOGGLE:
            straight = not straight
        elif c == _QUOTE_OPEN:
            depth += 1
        elif c == _QUOTE_CLOSE:
            depth = max(0, depth - 1)
    return straight, depth


def iter_lines_trich_dan(body: str) -> Iterator[tuple[str, bool]]:
    """Duyệt từng dòng kèm cờ "dòng này nằm trong khối trích dẫn".

    Cờ tính theo trạng thái ngoặc ở ĐẦU dòng. Thế là đủ: mọi dòng mang đánh số đều bắt đầu
    bằng chữ số hoặc chữ cái, còn dòng mở ngoặc (`"4. Tổ chức ...`) bắt đầu bằng chính dấu
    ngoặc nên vốn đã không khớp regex đơn vị nào.
    """
    straight, depth = False, 0
    for line in body.split("\n"):
        yield line, (straight or depth > 0)
        straight, depth = _quote_step(line, straight, depth)


def quote_spans(body: str) -> list[dict]:
    """Vị trí các khối trích dẫn trong toàn văn: [{char_start, char_end}], kể cả dấu ngoặc.

    Xuất ra để phía sau khỏi phải suy lại. KHÔNG dùng để cắt gọt `noi_dung`.
    """
    out: list[dict] = []
    straight, depth = False, 0
    start: int | None = None
    for i, c in enumerate(body):
        if c not in (_QUOTE_TOGGLE, _QUOTE_OPEN, _QUOTE_CLOSE):
            continue
        truoc = straight or depth > 0
        straight, depth = _quote_step(c, straight, depth)
        sau = straight or depth > 0
        if not truoc and sau:
            start = i
        elif truoc and not sau and start is not None:
            out.append({"char_start": start, "char_end": i + 1})
            start = None
    if start is not None:  # ngoặc không đóng — coi như trích tới hết văn bản
        out.append({"char_start": start, "char_end": len(body)})
    return out


def _body_end(lines: list[str]) -> int:
    """Chỉ số dòng bắt đầu phần Phụ lục, hoặc hết văn bản nếu không có."""
    for i, ln in enumerate(lines):
        if _PHU_LUC_RE.match(ln.strip()):
            return i
    return len(lines)


def _is_shouted(line: str) -> bool:
    """Dòng viết hoa toàn bộ — tiêu đề Chương/Mục nằm ở (các) dòng ngay sau số hiệu."""
    return bool(line) and any(c.isalpha() for c in line) and line == line.upper()


def split_articles(noi_dung: str) -> list[dict]:
    """Toàn văn → danh sách Điều, text là LÁT CẮT NGUYÊN VĂN của `noi_dung`.

    Đây là nguồn duy nhất sinh `articles`, KHÔNG dựng lại từ cây điều khoản: cây lấy từ DOM
    và DOM thiếu markup cho phần bị sửa đổi (xem `check_tree_coverage`), nên dựng lại từ cây
    sẽ mất số thứ tự "1." / "a)" — mà số thứ tự chính là khoá định danh của Khoản/Điểm ở
    phía sau, không phải chuyện trình bày.

    `text` của Điều bắt đầu ngay SAU "Điều N. " (tức từ tiêu đề Điều) và kéo tới ngay trước
    tiêu đề kế tiếp, nên `noi_dung[char_start:char_end] == text` luôn đúng từng ký tự.
    Chương/Mục cắt ngang thân Điều nên cũng là điểm dừng — nhãn của chúng đi vào
    `chapter`/`section` thay vì lẫn vào text.
    """
    lines = noi_dung.split("\n")
    offsets, pos = [], 0
    for ln in lines:
        offsets.append(pos)
        pos += len(ln) + 1

    het_than = _body_end(lines)
    heads: list[tuple[int, str, str, str]] = []  # (dòng, cấp, số, phần tiêu đề cùng dòng)
    for i, ln in enumerate(lines[:het_than]):
        s = ln.strip()
        for cap, rx in (("dieu", _TEXT_DIEU_RE), ("chuong", _TEXT_CHUONG_RE), ("muc", _TEXT_MUC_RE)):
            m = rx.match(s)
            if m:
                heads.append((i, cap, m.group(1), m.group(2).strip()))
                break
    head_lines = {h[0] for h in heads}

    def title_after(i: int, inline: str) -> str:
        parts = [inline] if inline else []
        j = i + 1
        while j < len(lines) and j not in head_lines and _is_shouted(lines[j].strip()):
            parts.append(lines[j].strip())
            j += 1
        return " ".join(parts)

    out: list[dict] = []
    chuong = muc = None
    for idx, (i, cap, so, inline) in enumerate(heads):
        if cap in ("chuong", "muc"):
            ten = "Chương" if cap == "chuong" else "Mục"
            title = title_after(i, inline)
            label = f"{ten} {so}. {title}" if title else f"{ten} {so}"
            if cap == "chuong":
                chuong, muc = label, None
            else:
                muc = label
            continue

        head = lines[i]
        indent = len(head) - len(head.lstrip())
        start = offsets[i] + indent + _TEXT_DIEU_RE.match(head.strip()).start(2)
        nxt = heads[idx + 1][0] if idx + 1 < len(heads) else het_than
        end = offsets[nxt] - 1 if nxt < len(lines) else len(noi_dung)
        text = noi_dung[start:end].rstrip()
        out.append(
            {
                "article": f"Điều {so}",
                "text": text,
                "chapter": chuong,
                "section": muc,
                "superseded": False,
                "char_start": start,
                "char_end": start + len(text),
            }
        )
    return out


# Nhãn vbpl chèn vào thân điều để đánh dấu điều khoản bị tác động. Bắt buộc có "được|bị":
# "Điều khoản thi hành" là TIÊU ĐỀ ĐIỀU có thật (3 văn bản trong lô này có), lọc theo tiền tố
# "Điều khoản" trần là ăn mất nội dung thật.
_BADGE_LINE_RE = re.compile(r"^Điều khoản (được|bị)\s")
# Sai của NGUỒN, chỉ báo chứ không sửa: thiếu dấu cách sau dấu chấm ("3.Dịch vụ thu hộ") làm
# bộ tách khoản bỏ sót đúng khoản đó.
_KHOAN_DINH_LIEN_RE = re.compile(r"^(\d+)\.(?=\S)")


_FILE_NAME_RE = re.compile(r"\.(pdf|docx?|zip|rar|html?|xlsx?)$", re.I)
_FILE_SIZE_RE = re.compile(r"^[\d.,]+\s*[KMG]?B$", re.I)
# Tệp gốc nằm trên gateway của Bộ Tư pháp, không phải vbpl.vn. Mẫu URL này quan sát được từ
# request mà chính trang phát ra khi mở tab "Văn bản gốc", và đã đối chứng trên văn bản khác.
_FILE_GATEWAY = "https://vbpl-bientap-gateway.moj.gov.vn/api/qtdc/public/doc/minio/buckets/vbpl"


def parse_file_leaves(leaves: list[str]) -> list[dict]:
    """Danh sách text lá của tab "Tải về" → [{ten, kich_thuoc}] theo đúng thứ tự trang.

    Trang không dùng thẻ <a>: tên tệp, dung lượng và ngày là 3 phần tử liền nhau. Lấy tên
    trước rồi mới ngó sang phải tìm dung lượng, để một tệp không có dung lượng cũng không
    làm lệch cả danh sách.
    """
    out: list[dict] = []
    for i, t in enumerate(leaves):
        if not _FILE_NAME_RE.search(t):
            continue
        size = next(
            (s for s in leaves[i + 1 : i + 3] if _FILE_SIZE_RE.match(s)),
            None,
        )
        out.append({"ten": t, "kich_thuoc": size})
    return out


def file_download_url(url: str, ten: str) -> str | None:
    """URL tải tệp gốc, dựng từ id số trong URL chi tiết + tên tệp."""
    doc_id = url.rstrip("/").rsplit("--", 1)[-1]
    if not doc_id.isdigit():
        return None
    return f"{_FILE_GATEWAY}/{doc_id}/{quote(ten)}/download"


def strip_amend_noise(body: str) -> tuple[str, list[dict], list[str]]:
    """Toàn văn thô → (toàn văn sạch, nhãn đã lọc, cảnh báo).

    vbpl chèn vào trang hai thứ không thuộc văn bản: dòng nhãn đánh dấu điều khoản bị tác
    động, và ở một số điều là cả BẢN SAO của chính các khoản đó. Cả hai lọt vào toàn văn và
    thổi phồng số khoản.

    Hai điều tuyệt đối không được làm:
      - cắt mọi thứ từ dòng nhãn trở đi: ở nhiều điều nhãn chỉ là dấu đứng TRƯỚC khoản bị
        sửa, và khoản đó là nội dung thật, chỉ xuất hiện một lần;
      - khử hai dòng "gần giống": khác dù một ký tự thì rất có thể là bản cũ vs bản mới, giữ
        cả hai và cảnh báo — chọn hộ là im lặng làm sai.
    """
    out: list[str] = []
    labels: list[dict] = []
    warnings: list[str] = []
    dieu: str | None = None
    seen_khoan: dict[str, str] = {}  # số khoản → text (trong Điều hiện tại)
    seen_line: set[tuple[str, str]] = set()  # (phạm vi, text) đã gặp
    khoan: str | None = None
    pending: list[str] = []

    def note(cap: str, so: str | None) -> None:
        """Nhãn đứng trước đơn vị nào thì gắn vào đơn vị đó — đây là thông tin điều khoản bị
        tác động, lọc khỏi toàn văn thì phải giữ lại ở chỗ khác chứ không được vứt."""
        for nhan in pending:
            labels.append({"dieu": dieu, "cap": cap, "so": so, "nhan": nhan})
        pending.clear()

    for line, trong_trich_dan in iter_lines_trich_dan(body):
        s = line.strip()
        if _BADGE_LINE_RE.match(s):
            pending.append(s)
            continue

        m = _TEXT_DIEU_RE.match(s)
        if m:
            dieu, khoan = m.group(1), None
            seen_khoan, seen_line = {}, set()
            note("dieu", dieu)
            out.append(line)
            continue

        m = _TEXT_KHOAN_RE.match(s)
        if m and dieu is not None:
            so = m.group(1)
            if trong_trich_dan:
                # Đánh số của văn bản BỊ SỬA. Không so trùng và không ghi nhớ: khoản 5 được
                # chép vào mà đụng khoản 5 của chính văn bản này thì sinh ra cảnh báo giả,
                # và người đọc mở ra sẽ không thấy có gì để quyết. `khoan` giữ nguyên vì đoạn
                # trích nằm bên trong khoản hiện tại.
                note("khoan", so)
                out.append(line)
                continue
            truoc = seen_khoan.get(so)
            if truoc == s:  # lặp y hệt → bản sao vbpl chèn vào
                note("khoan", so)
                continue
            if truoc is not None:
                warnings.append(
                    f"Điều {dieu}: khoản {so} xuất hiện 2 lần với nội dung KHÁC nhau — giữ cả "
                    "hai, cần người đọc quyết bản nào là bản đang hiệu lực"
                )
            seen_khoan[so] = s
            khoan = so
            note("khoan", so)
            out.append(line)
            continue

        m = _TEXT_DIEM_RE.match(s)
        if m and dieu is not None:
            if trong_trich_dan:  # cùng lý do như Khoản ở trên
                note("diem", m.group(1))
                out.append(line)
                continue
            # Điểm chỉ khử lặp TRONG cùng một khoản: "a)" ở khoản 1 và "a)" ở khoản 2 là hai
            # điểm khác nhau, dù nội dung có thể ngắn và giống nhau.
            key = (f"{dieu}#{khoan}", s)
            if key in seen_line:
                note("diem", m.group(1))
                continue
            seen_line.add(key)
            note("diem", m.group(1))
            out.append(line)
            continue

        if _KHOAN_DINH_LIEN_RE.match(s):
            warnings.append(
                f"nguồn thiếu dấu cách sau số khoản: {s[:60]!r} — giữ nguyên như nguồn, "
                "bộ tách khoản sẽ không nhận ra dòng này"
            )
        note("khac", None)
        out.append(line)

    return "\n".join(out), labels, warnings


def count_units(noi_dung: str, *, ngoai_trich_dan: bool = False) -> dict[str, int]:
    """Đếm Điều/Khoản/Điểm trong THÂN văn bản.

    Điểm chỉ tính khi có Khoản cha: khoá định danh phía sau là `dieu_{n}#khoan_{m}#diem_{x}`,
    một Điểm không có Khoản cha thì không có khoá nào để mang.

    `ngoai_trich_dan=True` bỏ qua các dòng nằm trong khối trích dẫn — dùng khi ĐỐI CHIẾU với
    cây điều khoản (xem `check_tree_coverage`). Mặc định là False vì số đếm được dùng làm số
    Điều/Khoản/Điểm báo ra ngoài, mà ở đó đoạn trích vẫn là chữ nằm trong văn bản này.
    """
    out = {"dieu": 0, "khoan": 0, "diem": 0}
    in_dieu = False
    in_khoan = False
    het_than = _body_end(noi_dung.split("\n"))
    for i, (ln, trong_trich_dan) in enumerate(iter_lines_trich_dan(noi_dung)):
        if i >= het_than:
            break
        if ngoai_trich_dan and trong_trich_dan:
            # Không đụng in_dieu/in_khoan: đoạn trích nằm BÊN TRONG một khoản của văn bản
            # này, nên điểm đứng sau nó vẫn thuộc khoản đó.
            continue
        s = ln.strip()
        if _TEXT_DIEU_RE.match(s):
            out["dieu"] += 1
            in_dieu, in_khoan = True, False
        elif not in_dieu:
            continue
        elif _TEXT_KHOAN_RE.match(s):
            out["khoan"] += 1
            in_khoan = True
        elif in_khoan and _TEXT_DIEM_RE.match(s):
            out["diem"] += 1
    return out


def has_full_text(noi_dung: str) -> bool:
    """Nguồn có đăng thân văn bản hay không — mốc là có ít nhất một dòng "Điều N.".

    Cố tình KHÔNG đo bằng độ dài: trang chỉ có thuộc tính vẫn dài vài trăm ký tự.
    """
    return any(_TEXT_DIEU_RE.match(ln.strip()) for ln in noi_dung.split("\n"))


def check_tree_coverage(tree: list[dict], noi_dung: str) -> list[str]:
    """So số Khoản/Điểm trong cây với số đếm được từ toàn văn, trả danh sách cảnh báo.

    Cây dựng từ DOM nên chỉ thấy phần có class `prov-*`; phần nằm trong khối sửa đổi thường
    không có markup đó. Lệch là chuyện âm thầm — không có exception nào — nên phải đo.

    Mốc đối chiếu BỎ các dòng trong khối trích dẫn, nếu không sẽ báo ngược hẳn: ở 80/2016 cây
    có 10 Khoản và 10 mới là số đúng, còn đếm phẳng ra 14 vì tính cả 4 khoản của văn bản bị
    sửa được chép vào. Cây đọc theo cấu trúc HTML nên biết đoạn trích là con của khoản; ở văn
    bản sửa đổi cây ĐÚNG HƠN toàn văn đếm phẳng, ngược với 15/2024 (cây thiếu nút thật).
    """
    have = count_provisions(tree)
    want = count_units(noi_dung, ngoai_trich_dan=True)
    out = []
    for cap, ten in (("dieu", "Điều"), ("khoan", "Khoản"), ("diem", "Điểm")):
        got, exp = have.get(cap, 0), want[cap]
        if got < exp:
            out.append(f"cây điều khoản thiếu {exp - got} {ten} so với toàn văn ({got}/{exp})")
    return out


_DOC_TYPE_RE = re.compile(
    r"^(Thông tư liên tịch|Thông tư|Nghị định|Nghị quyết|Quyết định|Luật|Pháp lệnh|"
    r"Chỉ thị|Công văn|Văn bản hợp nhất)",
    re.I,
)


def _ascii_upper(s: str) -> str:
    """"NĐ-CP" → "NDCP": bỏ dấu, Đ→D, chỉ giữ chữ/số, viết hoa."""
    s = s.replace("Đ", "D").replace("đ", "d")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if c.isalnum() and not unicodedata.combining(c)).upper()


def doc_id_from_so_hieu(so_hieu: str) -> str:
    """Số hiệu → doc_id theo đúng quy ước corpus: `<loại ASCII><số>-<năm>`.

        15/2024/TT-NHNN → TT15-2024      101/2012/NĐ-CP → ND101-2012

    Ký hiệu không có năm thì phần phân biệt là cơ quan: 29/VBHN-NHNN → VBHN29-NHNN.
    Quy ước này đo từ 11 văn bản ngoại đang có trong corpus — sinh sai là tạo NODE THỨ HAI
    cho cùng một văn bản, không phải chỉ đặt tên xấu.
    """
    parts = [p.strip() for p in so_hieu.split("/") if p.strip()]
    if len(parts) < 2:
        return _ascii_upper(so_hieu)
    so = parts[0]
    if len(parts) >= 3 and re.fullmatch(r"\d{4}", parts[1]):
        loai, nam = parts[2], parts[1]
        return f"{_ascii_upper(loai.split('-')[0])}{so}-{nam}"
    loai, _, co_quan = parts[1].partition("-")
    head = f"{_ascii_upper(loai)}{so}"
    return f"{head}-{_ascii_upper(co_quan)}" if co_quan else head


def to_corpus_document(doc: dict) -> dict:
    """Kết quả `dump` → JSON đúng dạng `CorpusDocument` để đưa vào luồng duyệt.

    doc_id theo quy ước corpus (xem `doc_id_from_so_hieu`); thiếu Số hiệu thì lùi về slug
    URL để không bao giờ sinh doc_id rỗng.
    """
    props = doc.get("thuoc_tinh") or {}
    so_hieu = (props.get("so_hieu") or "").strip()
    doc_id = doc_id_from_so_hieu(so_hieu) if so_hieu else slug_for(doc["url"])[:60]
    title = doc.get("title") or doc_id
    m = _DOC_TYPE_RE.match(props.get("loai_van_ban") or title)
    tree = doc.get("cay_dieu_khoan") or []
    noi_dung = doc.get("noi_dung") or ""

    return {
        "doc_id": doc_id,
        "title": title,
        "doc_type": (props.get("loai_van_ban") or (m.group(1) if m else "")).strip(),
        "source": "external",
        "valid_from": doc.get("ngay_hieu_luc") or _iso_date(props.get("ngay_co_hieu_luc")),
        "valid_to": _iso_date(props.get("ngay_het_hieu_luc")),
        "so_hieu": so_hieu or None,
        "co_quan_ban_hanh": props.get("co_quan_ban_hanh") or None,
        "nguoi_ky": props.get("nguoi_ky") or None,
        "chuc_danh": props.get("chuc_danh") or None,
        "nganh": props.get("nganh") or None,
        "linh_vuc": props.get("linh_vuc") or None,
        "ngay_ban_hanh": _iso_date(props.get("ngay_ban_hanh")),
        "tinh_trang_hieu_luc": props.get("tinh_trang_hieu_luc")
        or doc.get("trang_thai")
        or None,
        "source_url": doc.get("url"),
        "source_files": doc.get("tep_dinh_kem") or [],
        "co_toan_van": bool(doc.get("co_toan_van", has_full_text(noi_dung))),
        "canh_bao": list(doc.get("canh_bao") or []),
        "articles": split_articles(noi_dung),
        "provisions": tree,
        "trich_dan": quote_spans(noi_dung),
    }


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


@contextmanager
def open_browser():
    """Một phiên Chromium dùng chung. Tách khỏi `extract_document` để cào nhiều văn bản
    trong cùng một lần launch (mỗi lần launch mất vài giây)."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            yield browser
        finally:
            browser.close()


def extract_document(browser, url: str) -> dict:
    """Bóc cả 3 tab Nội dung / Thuộc tính / Lược đồ của 1 văn bản trên `browser` đang mở.

    Mỗi văn bản một tab mới rồi đóng: hook `window.open` và state SPA không lẫn giữa các văn bản.
    """
    page = browser.new_page(user_agent=_UA)
    try:
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

        files = _read_attachments(page, url)
    finally:
        page.close()

    if not properties:
        raise RuntimeError(
            "Tab Thuộc tính render xong nhưng không đọc được trường nào — bảng đã đổi cấu "
            "trúc. Kiểm tra _PROP_KEYS trước khi dùng kết quả."
        )

    raw_body, status, valid_from = clean_body(main_text)
    body, labels, warnings = strip_amend_noise(raw_body)
    tree = build_provision_tree(prov_nodes)
    luoc_do = group_relations(relations) if relations else parse_relations(luoc_do_text)

    affected = [
        {
            "dieu": a["article"],
            "phan_loai": sorted({classify_badge(b) for b in a["badges"]}),
            "nhan": a["badges"],
            "ma_type": a["type_code"],
            "trich": " ".join(a["text"].split())[:400],
        }
        for a in amendments
    ]
    affected += _labels_not_in(affected, labels)

    co_toan_van = has_full_text(body)
    if not co_toan_van:
        warnings.append(
            "nguồn không đăng toàn văn (chỉ có thuộc tính/lược đồ) — toàn văn nhiều khả năng "
            "chỉ nằm trong tệp đính kèm, cần tìm nguồn khác nếu muốn thân văn bản"
        )
    if not files:
        warnings.append("tab Tải về không liệt kê tệp nào — không có bản gốc để đối chiếu")
    warnings += check_tree_coverage(tree, body)
    warnings += _source_quirks(luoc_do)

    return {
        "url": url,
        "title": title,
        "trang_thai": status,
        "ngay_hieu_luc": _iso_date(valid_from),
        "co_toan_van": co_toan_van,
        "canh_bao": warnings,
        # 3 dạng của cùng một nội dung: text thuần cho pipeline extract hiện có, HTML giữ
        # đúng định dạng web để hiển thị lại, và cây có cấu trúc cho KG.
        "noi_dung": body,
        "noi_dung_html": content_html,
        "cay_dieu_khoan": tree,
        "thuoc_tinh": properties,
        "tep_dinh_kem": files,
        # DOM cho cả URL đích; chỉ khi không bóc được mục nào mới lùi về đọc text thuần
        # (giữ được tiêu đề, mất URL).
        "luoc_do": luoc_do,
        "dieu_khoan_bi_tac_dong": affected,
    }


def _read_attachments(page, url: str) -> list[dict]:
    """Tab "Tải về" → [{ten, kich_thuoc, url}]. Không mở được tab thì trả rỗng."""
    try:
        _open_tab(page, url, _TAB_TAI_VE_URL, "Tải về")
        page.wait_for_function(
            "() => /\\.(pdf|docx?|zip|rar)\\b/i.test("
            "document.querySelector('main')?.innerText ?? '')",
            timeout=20_000,
        )
    except Exception:  # noqa: BLE001 — không có tệp là chuyện bình thường, đã có cảnh báo
        return []
    return [
        {**f, "url": file_download_url(url, f["ten"])}
        for f in parse_file_leaves(page.evaluate(_JS_FILE_LEAVES))
    ]


def _labels_not_in(affected: list[dict], labels: list[dict]) -> list[dict]:
    """Nhãn đã lọc khỏi toàn văn mà `dieu_khoan_bi_tac_dong` chưa có → bổ sung.

    Nhãn là thông tin thật (vbpl đánh dấu điều khoản nào bị tác động); lọc nó khỏi thân văn
    bản mà không giữ lại chỗ nào là mất dữ liệu.
    """
    have = {(a["dieu"], nhan) for a in affected for nhan in a["nhan"]}
    out: dict[tuple, dict] = {}
    for lb in labels:
        dieu = f"Điều {lb['dieu']}" if lb["dieu"] else None
        if (dieu, lb["nhan"]) in have:
            continue
        key = (dieu, lb["cap"], lb["so"])
        item = out.setdefault(
            key,
            {
                "dieu": dieu,
                "cap": lb["cap"],
                "so": lb["so"],
                "phan_loai": [],
                "nhan": [],
                "ma_type": None,
                "trich": "",
                "tu_nhan_trong_toan_van": True,
            },
        )
        if lb["nhan"] not in item["nhan"]:
            item["nhan"].append(lb["nhan"])
            item["phan_loai"] = sorted({classify_badge(b) for b in item["nhan"]})
    return list(out.values())


# Lỗi của NGUỒN — chỉ báo, KHÔNG tự sửa: chuẩn hoá im lặng ở tầng crawl thì phía sau không
# còn cách nào biết nguồn đã sai.
_QUIRK_SPACED_DASH_RE = re.compile(r"\b[A-ZĐ]{2,5}-\s+[A-ZĐ]{2,5}\b")
_QUIRK_CYRILLIC_RE = re.compile(r"[Ѐ-ӿ]")


def _source_quirks(luoc_do: dict) -> list[str]:
    out: list[str] = []
    for cats in luoc_do.values():
        for items in cats.values():
            for it in items:
                title = it["title"] if isinstance(it, dict) else str(it)
                if _QUIRK_SPACED_DASH_RE.search(title):
                    out.append(f"nguồn thừa dấu cách trong số hiệu: {title[:70]!r}")
                m = _QUIRK_CYRILLIC_RE.search(title)
                if m:
                    out.append(
                        f"nguồn dùng ký tự Cyrillic {m.group()!r} (U+{ord(m.group()):04X}) "
                        f"trong số hiệu: {title[:70]!r}"
                    )
    return out


def fetch_document(url: str) -> dict:
    """Cào 1 văn bản trong một phiên trình duyệt riêng (dùng cho lệnh `dump`)."""
    with open_browser() as browser:
        return extract_document(browser, url)


def slug_for(url: str) -> str:
    """Tên file cho một URL chi tiết: slug đã bỏ đuôi id/uuid, cắt còn 80 ký tự."""
    return _UUID_SUFFIX_RE.sub("", url.rstrip("/").rsplit("/", 1)[-1])[:80]


# Hai artefact để RIÊNG thư mục: cùng nằm một chỗ thì glob `*.json` của luồng đọc bản ghi thô
# sẽ nuốt luôn bản đã chuyển khuôn (và cả file báo cáo).
def raw_path(out_dir: Path, slug: str) -> Path:
    return out_dir / "raw" / f"{slug}.json"


def corpus_path(out_dir: Path, slug: str) -> Path:
    return out_dir / "corpus" / f"{slug}.json"


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
    if _looks_like_property_table(body):
        # Trang không đăng thân văn bản; cái còn lại trong <main> là bảng thuộc tính. Trả về
        # nó như thể là toàn văn thì phía sau không có cách nào biết — để rỗng và báo ra.
        return "", status, valid_from
    return body, status, valid_from


def _looks_like_property_table(body: str) -> bool:
    """Thân văn bản rỗng nên phần đọc được chỉ là bảng thuộc tính (hay gặp ở văn bản hợp nhất).

    Nhận diện bằng CẤU TRÚC — có nhãn của bảng thuộc tính mà không có dòng "Điều N." nào —
    chứ không bằng độ dài: bảng thuộc tính vẫn dài vài trăm ký tự.
    """
    if has_full_text(body):
        return False
    lines = {ln.strip() for ln in body.split("\n")}
    return len(lines & set(_PROP_KEYS)) >= 4


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
    out_path = out_dir / f"{slug_for(url)}.txt"
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
    p_dump.add_argument(
        "--corpus",
        action="store_true",
        help="Ghi thêm bản .corpus.json đúng dạng CorpusDocument để đưa vào luồng duyệt",
    )

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
        slug = slug_for(args.url)
        out_path = raw_path(out_dir, slug)
        out_path.parent.mkdir(parents=True, exist_ok=True)
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
        print(f"[vbpl] Toàn văn   : {'có' if doc['co_toan_van'] else 'KHÔNG CÓ'} | "
              f"{count_units(doc['noi_dung'])}")
        print(f"[vbpl] Tệp đính kèm: {len(doc['tep_dinh_kem'])}")
        for f in doc["tep_dinh_kem"]:
            print(f"    - {f['ten']} ({f['kich_thuoc']})\n      {f['url']}")
        print(f"[vbpl] Điều khoản bị tác động: {n_amend} — {dict(kinds)}")
        for w in doc["canh_bao"]:
            print(f"[vbpl] CẢNH BÁO: {w}")
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

        if args.corpus:
            cdoc = to_corpus_document(doc)
            cpath = corpus_path(out_dir, slug)
            cpath.parent.mkdir(parents=True, exist_ok=True)
            cpath.write_text(
                json.dumps(cdoc, ensure_ascii=False, indent=1), encoding="utf-8"
            )
            print(
                f"[vbpl] Đã lưu {cpath} — doc_id={cdoc['doc_id']!r}, "
                f"{len(cdoc['articles'])} Điều, {count_provisions(cdoc['provisions'])}"
            )
            print("[vbpl] Bước tiếp: đưa file này vào luồng duyệt (POST /documents/{id}/approve)")


if __name__ == "__main__":
    main(sys.argv[1:])
