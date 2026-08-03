"""Trang duyệt CỜ — xác nhận từng cảnh báo là đúng hay báo động giả.

Khác `review_ui.py`: trang kia duyệt **nhãn** (94 đơn vị, gán/sửa span → `gold.jsonl`),
việc nặng và đang 0/94. Trang này duyệt **cờ**: bộ dò đã bắn 82 lần, mỗi lần đúng hay
sai? Nhẹ hơn nhiều và trả về thứ hiện chưa có — **một con số do người chấm**, thay vì
máy tự chấm máy.

Vì sao đơn vị duyệt là CỜ chứ không phải BẢN GHI: một bản ghi có thể mang 10 cờ thuộc
5 loại khác nhau (ND52 Đ22 K2). Gật/lắc ở mức bản ghi thì không biết loại cờ nào đáng
tin — mà đó mới là thứ cần để chỉnh bộ dò.

Cái trang phải bày ra để quyết nhanh: **nhãn mô hình viết** đặt cạnh **chữ của luật tại
span đã neo**. Đó đúng là hai vế mà modality guard đem so; nhìn thấy cả hai thì phần lớn
cờ quyết được trong vài giây, không phải mở fixture đếm ký tự.

Xếp hạng lấy nguyên từ `triage.py` — không định nghĩa lại mức ở đây.

Chạy:
    uv run python -m eval.ontology.flag_ui                # sinh HTML rồi tự mở
    uv run python -m eval.ontology.flag_ui --serve        # nút Lưu ghi thẳng file
    uv run python -m eval.ontology.flag_ui --max-tier 5   # xem cả cờ ít giá trị

Dạng `-m` là bắt buộc (file này `import app.ontology.*`): gọi thẳng đường dẫn thì gốc
`sys.path` là `eval/ontology/` chứ không phải thư mục dự án ⇒ không thấy gói `app`.

Không có `--serve` thì trang vẫn chạy offline: tự lưu localStorage, xuất bằng nút Tải.
"""
from __future__ import annotations

import argparse
import json
import re
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from app.ontology.parser import khoan_de_trich, parse_dieu
from eval.ontology.triage import TIER_NAME, load, triage

_INDEX = Path("data/fixtures/_index.json")
_OUT = Path("eval/ontology/flags.html")
_VERDICTS = Path("eval/ontology/flag_verdicts.jsonl")

EXPORT = ["key", "id", "field", "tier", "kind", "warning", "verdict", "note"]


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def _locate(row: dict, field: str) -> dict:
    """`field` → span đã neo, nhãn mô hình viết, và chữ của luật ở đó.

    Trả `candidates` khi địa chỉ mơ hồ (nhiều điều kiện cùng `source_diem`, xảy ra với
    bản ghi sinh trước khi `extractor.py` đánh số). KHÔNG lặng lẽ lấy phần tử đầu —
    đưa người duyệt đọc nhầm đoạn luật là hỏng đúng thứ trang này sinh ra để tránh.
    """
    m = re.match(r"điều kiện (.+?)(?:\.(\w+))?$", field)
    if m:
        want, sub = m.group(1), m.group(2)
        idx = None
        if "#" in want:
            want, _, raw = want.partition("#")
            idx = int(raw) if raw.isdigit() else None
        hits = [c for c in row.get("conditions", []) if (c.get("source_diem") or None) == want]
        if idx is not None and 0 < idx <= len(hits):
            hits = [hits[idx - 1]]
        return {
            "span": (hits[0].get("grounding") or {}).get("char_span") if len(hits) == 1 else None,
            "label": (hits[0].get(sub) if sub else hits[0].get("object_label", "")) if len(hits) == 1 else "",
            "candidates": [c.get("text", "") for c in hits] if len(hits) > 1 else [],
        }
    f = row.get(field.split(".")[0])
    if isinstance(f, dict):
        return {
            "span": (f.get("grounding") or {}).get("char_span"),
            "label": f.get("label", ""),
            "candidates": [],
        }
    return {"span": None, "label": "", "candidates": []}


def build_payload(max_tier: int = 4) -> dict:
    index = json.loads(_INDEX.read_text(encoding="utf-8"))
    rows = load()
    items = triage(rows)
    done = {r["key"]: r for r in _read_jsonl(_VERDICTS)}

    trees: dict[str, object] = {}
    cards: list[dict] = []
    he_thong: list[dict] = []

    for it in items:
        row = it["row"]
        name = Path(row["fixture"]).name
        if name not in trees:
            trees[name] = parse_dieu(
                Path(row["fixture"]).read_text(encoding="utf-8"), index[name]
            )
        dieu = trees[name]
        so_khoan = row["id"].rsplit("#khoan_", 1)[-1] if "#khoan_" in row["id"] else ""
        khoan = next(
            (k for k in khoan_de_trich(dieu) if k.so_hien_thi == so_khoan), None
        )
        if khoan is None:
            continue

        if it["he_thong"]:
            he_thong.append(
                {
                    "id": row["id"],
                    "khai": [c.get("source_diem") for c in row.get("conditions", [])],
                }
            )

        for tier, kind, w in it["flags"]:
            # Cờ "điểm không tồn tại" của bản ghi hệ thống đã được gom thành một mục —
            # đưa lại vào hàng đợi là bắt người duyệt quyết 19 lần cho cùng một lỗi.
            if it["he_thong"] and "điểm không tồn tại" in w:
                continue
            if tier > max_tier:
                continue
            field = w.split(":", 1)[0].strip() if ":" in w else "—"
            loc = _locate(row, field)
            span = loc["span"]
            rel = None
            if span:
                rel = [
                    max(0, span[0] - khoan.start),
                    max(0, min(span[1], khoan.end) - khoan.start),
                ]
            key = f"{row['id']}||{w}"
            cards.append(
                {
                    "key": key,
                    "id": row["id"],
                    "type": row.get("type", "?"),
                    "tier": tier,
                    "tier_name": TIER_NAME[tier],
                    "kind": kind,
                    "warning": w.split(":", 1)[-1].strip() if ":" in w else w,
                    "field": field,
                    "label": loc["label"] or "",
                    "candidates": loc["candidates"],
                    "dieu_title": f"Điều {dieu.so_hien_thi}. {dieu.tieu_de}",
                    "khoan_text": khoan.text,
                    "span": rel,
                    "verdict": done.get(key, {}).get("verdict", ""),
                    "note": done.get(key, {}).get("note", ""),
                }
            )

    cards.sort(key=lambda c: (c["tier"], c["id"]))
    return {"cards": cards, "he_thong": he_thong}


def to_jsonl(rows: list[dict]) -> str:
    out = [json.dumps({k: r.get(k) for k in EXPORT}, ensure_ascii=False) for r in rows]
    return "\n".join(out) + "\n"


def render(payload: dict, *, can_save: bool) -> str:
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return _HTML.replace("__DATA__", data).replace(
        "__CAN_SAVE__", "true" if can_save else "false"
    )


class _Handler(BaseHTTPRequestHandler):
    """Server tối giản chỉ phục vụ localhost."""

    html: str = ""

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - chữ ký của BaseHTTPRequestHandler
        self._send(200, self.html.encode("utf-8"), "text/html; charset=utf-8")

    def do_POST(self) -> None:  # noqa: N802
        n = int(self.headers.get("Content-Length") or 0)
        rows = json.loads(self.rfile.read(n).decode("utf-8"))
        _VERDICTS.parent.mkdir(parents=True, exist_ok=True)
        _VERDICTS.write_text(to_jsonl(rows), encoding="utf-8")
        n_done = sum(1 for r in rows if r.get("verdict"))
        print(f"  [lưu] {_VERDICTS} — {n_done}/{len(rows)} cờ đã quyết")
        self._send(200, json.dumps({"ok": True, "reviewed": n_done}).encode(), "application/json")

    def log_message(self, *args) -> None:
        pass


def main(argv: list[str] | None = None) -> Path:
    ap = argparse.ArgumentParser(description="Trang duyệt cờ (đúng / báo động giả)")
    ap.add_argument("--out", default=str(_OUT))
    ap.add_argument("--max-tier", type=int, default=4)
    ap.add_argument("--serve", action="store_true", help="chạy server để nút Lưu ghi thẳng file")
    ap.add_argument("--port", type=int, default=8778)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args(argv)

    payload = build_payload(args.max_tier)
    html = render(payload, can_save=args.serve)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")

    by_tier: dict[int, int] = {}
    for c in payload["cards"]:
        by_tier[c["tier"]] = by_tier.get(c["tier"], 0) + 1
    tom = " · ".join(f"T{t}:{n}" for t, n in sorted(by_tier.items()))
    print(f"Đã ghi {out} — {len(payload['cards'])} cờ cần quyết ({tom})")
    print(f"  gom riêng: {len(payload['he_thong'])} bản ghi lỗi hệ thống, không vào hàng đợi")

    if args.serve:
        _Handler.html = html
        url = f"http://127.0.0.1:{args.port}/"
        print(f"Server tại {url} (chỉ localhost). Nút Lưu ghi vào {_VERDICTS}. Ctrl+C để dừng.")
        if not args.no_open:
            webbrowser.open(url)
        try:
            HTTPServer(("127.0.0.1", args.port), _Handler).serve_forever()
        except KeyboardInterrupt:
            print("\nĐã dừng server.")
    elif not args.no_open:
        webbrowser.open(out.resolve().as_uri())
    return out


_HTML = r"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Duyệt cờ — ontology</title>
<style>
:root{--bg:#fff;--fg:#1c1917;--dim:#6b7280;--line:#e7e5e4;--panel:#fafaf9;
 --hit:#fde68a;--hitfg:#78350f;--ok:#047857;--okbg:#d1fae5;--bad:#b91c1c;--badbg:#fef2f2;
 --warn:#b45309;--warnbg:#fef3c7;}
@media(prefers-color-scheme:dark){:root{--bg:#1c1917;--fg:#e7e5e4;--dim:#a8a29e;--line:#44403c;
 --panel:#292524;--hit:#78350f;--hitfg:#fde68a;--okbg:#053c2e;--badbg:#2a1315;--warnbg:#4a3410;}}
*{box-sizing:border-box}
body{margin:0;font:14px/1.65 system-ui,"Segoe UI",sans-serif;background:var(--bg);color:var(--fg)}
header{position:sticky;top:0;z-index:9;background:var(--panel);border-bottom:1px solid var(--line);
 padding:10px 16px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
h1{font-size:15px;margin:0}
.wrap{max-width:960px;margin:0 auto;padding:16px}
.card{border:1px solid var(--line);border-radius:9px;margin:14px 0;overflow:hidden}
.card.done{opacity:.5}
.chead{background:var(--panel);padding:9px 13px;border-bottom:1px solid var(--line);
 display:flex;gap:9px;align-items:center;flex-wrap:wrap}
.tag{font-size:11px;font-weight:700;padding:2px 7px;border-radius:5px;background:var(--warnbg);
 color:var(--warn);text-transform:uppercase;letter-spacing:.03em}
.tag.t1{background:var(--badbg);color:var(--bad)}
code{background:var(--panel);padding:1px 5px;border-radius:4px;font-size:12.5px;
 font-family:ui-monospace,Consolas,monospace}
.cbody{padding:13px}
.row{display:grid;grid-template-columns:120px 1fr;gap:10px;margin:9px 0;align-items:start}
@media(max-width:640px){.row{grid-template-columns:1fr}}
.lbl{color:var(--dim);font-size:12px;text-transform:uppercase;letter-spacing:.04em;padding-top:2px}
.quote{border-left:3px solid var(--line);padding-left:11px}
.law{background:var(--panel);border-radius:7px;padding:11px 13px;white-space:pre-wrap;
 max-height:230px;overflow:auto;font-size:13.5px}
mark{background:var(--hit);color:var(--hitfg);border-radius:3px;padding:1px 0}
.acts{display:flex;gap:8px;flex-wrap:wrap;margin-top:11px;align-items:center}
button{font:inherit;padding:6px 13px;border-radius:7px;border:1px solid var(--line);
 background:var(--bg);color:var(--fg);cursor:pointer}
button:hover{border-color:var(--dim)}
button.on[data-v="dung"]{background:var(--okbg);border-color:var(--ok);color:var(--ok);font-weight:600}
button.on[data-v="sai"]{background:var(--badbg);border-color:var(--bad);color:var(--bad);font-weight:600}
button.on[data-v="khong_chac"]{background:var(--warnbg);border-color:var(--warn);color:var(--warn);font-weight:600}
input.note{flex:1;min-width:170px;padding:6px 9px;border-radius:7px;border:1px solid var(--line);
 background:var(--bg);color:var(--fg)}
.amb{background:var(--badbg);border:1px solid var(--bad);border-radius:7px;padding:9px 12px;margin:9px 0;font-size:13px}
.sys{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:13px;margin:14px 0}
.sys li{font-size:13px;margin:3px 0}
.muted{color:var(--dim);font-size:12.5px}
</style>
</head>
<body>
<header>
  <h1>Duyệt cờ</h1>
  <span id="prog" class="muted"></span>
  <span id="stat" style="font-size:12.5px;font-weight:600"></span>
  <span style="flex:1"></span>
  <label class="muted"><input type="checkbox" id="hideDone"> ẩn cờ đã quyết</label>
  <button id="save">Lưu</button>
  <button id="dl">Tải flag_verdicts.jsonl</button>
</header>
<div class="wrap" id="app"></div>

<script>
const DATA = __DATA__;
const CAN_SAVE = __CAN_SAVE__;
const KEY = "lexflow-flags-v1";

const saved = JSON.parse(localStorage.getItem(KEY) || "{}");
DATA.cards.forEach(c => {
  const s = saved[c.key];
  if (s) { c.verdict = s.verdict || c.verdict; c.note = s.note || c.note; }
});

const esc = s => String(s == null ? "" : s)
  .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
  .replace(/"/g,"&quot;").replace(/'/g,"&#39;");

function lawHtml(c) {
  const t = c.khoan_text || "";
  if (!c.span) return esc(t);
  const [a, b] = c.span;
  return esc(t.slice(0, a)) + "<mark>" + esc(t.slice(a, b)) + "</mark>" + esc(t.slice(b));
}

function persist() {
  const o = {};
  DATA.cards.forEach(c => { if (c.verdict || c.note) o[c.key] = {verdict: c.verdict, note: c.note}; });
  localStorage.setItem(KEY, JSON.stringify(o));
  const n = DATA.cards.filter(c => c.verdict).length;
  document.getElementById("prog").textContent =
    n + "/" + DATA.cards.length + " cờ đã quyết";
}

function render() {
  const hide = document.getElementById("hideDone").checked;
  const app = document.getElementById("app");
  let html = "";

  if (DATA.he_thong.length) {
    html += '<div class="sys"><b>Lỗi hệ thống — không vào hàng đợi (' +
      DATA.he_thong.length + ' bản ghi)</b><div class="muted">Mọi <code>source_diem</code> ' +
      'mô hình khai đều không tồn tại ⇒ Khoản không chẻ Điểm nào. Một khuyết tật của prompt, ' +
      'sửa một lần — không cần quyết từng bản ghi.</div><ul>' +
      DATA.he_thong.map(h => "<li><code>" + esc(h.id) + "</code> — khai " +
        esc(JSON.stringify(h.khai)) + "</li>").join("") + "</ul></div>";
  }

  DATA.cards.forEach((c, i) => {
    if (hide && c.verdict) return;
    html += '<div class="card' + (c.verdict ? " done" : "") + '" id="c' + i + '">';
    html += '<div class="chead"><span class="tag' + (c.tier <= 1 ? " t1" : "") + '">' +
      esc(c.tier_name) + '</span><b>' + esc(c.kind) + '</b>' +
      '<code>' + esc(c.field) + '</code>' +
      '<span style="flex:1"></span><span class="muted">' + esc(c.id) + '</span></div>';
    html += '<div class="cbody">';
    html += '<div class="row"><div class="lbl">Máy nói</div><div class="quote">' +
      esc(c.warning) + '</div></div>';
    if (c.label) {
      html += '<div class="row"><div class="lbl">Nhãn mô hình</div><div class="quote">' +
        esc(c.label) + '</div></div>';
    }
    if (c.candidates && c.candidates.length) {
      html += '<div class="amb">⚠️ Địa chỉ mơ hồ: ' + c.candidates.length +
        ' điều kiện cùng nhãn này (bản ghi sinh trước khi <code>extractor.py</code> đánh số). ' +
        'Phải đọc cả:<ul>' + c.candidates.map(t => "<li>" + esc(t) + "</li>").join("") +
        '</ul></div>';
    }
    html += '<div class="row"><div class="lbl">Chữ của luật</div><div class="law">' +
      lawHtml(c) + '</div></div>';
    html += '<div class="acts">' +
      ['dung', 'sai', 'khong_chac'].map(v =>
        '<button data-i="' + i + '" data-v="' + v + '"' +
        (c.verdict === v ? ' class="on"' : '') + '>' +
        {dung: "Cờ ĐÚNG", sai: "Báo động GIẢ", khong_chac: "Không chắc"}[v] + '</button>'
      ).join("") +
      '<input class="note" data-i="' + i + '" placeholder="ghi chú (tuỳ chọn)" value="' +
      esc(c.note) + '">' +
      '</div>';
    html += '</div></div>';
  });
  app.innerHTML = html || '<p class="muted">Không còn cờ nào để quyết.</p>';
  persist();
}

document.addEventListener("click", e => {
  const b = e.target.closest("button[data-v]");
  if (!b) return;
  const c = DATA.cards[+b.dataset.i];
  c.verdict = c.verdict === b.dataset.v ? "" : b.dataset.v;
  render();
});
document.addEventListener("input", e => {
  if (!e.target.classList.contains("note")) return;
  DATA.cards[+e.target.dataset.i].note = e.target.value;
  persist();
});
document.getElementById("hideDone").addEventListener("change", render);

function rows() {
  return DATA.cards.map(c => ({
    key: c.key, id: c.id, field: c.field, tier: c.tier, kind: c.kind,
    warning: c.warning, verdict: c.verdict || "", note: c.note || ""
  }));
}

document.getElementById("dl").addEventListener("click", () => {
  const body = rows().map(r => JSON.stringify(r)).join("\n") + "\n";
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([body], {type: "application/x-ndjson"}));
  a.download = "flag_verdicts.jsonl";
  a.click();
});

// Trạng thái báo bằng một dòng chữ trong header, KHÔNG dùng alert(): hộp thoại của
// trình duyệt chặn toàn bộ event loop của tab, nên trang đứng im cho tới khi có người
// bấm OK — và với công cụ tự động thì nó treo hẳn phiên làm việc.
function flash(msg, bad) {
  const el = document.getElementById("stat");
  el.textContent = msg;
  el.style.color = bad ? "var(--bad)" : "var(--ok)";
  clearTimeout(flash._t);
  flash._t = setTimeout(() => { el.textContent = ""; }, 4000);
}

document.getElementById("save").addEventListener("click", async () => {
  if (!CAN_SAVE) {
    flash("Chạy với --serve để Lưu ghi thẳng file — hiện hãy dùng nút Tải.", true);
    return;
  }
  try {
    const r = await fetch("/", {method: "POST", body: JSON.stringify(rows())});
    const j = await r.json();
    flash("Đã lưu " + j.reviewed + "/" + DATA.cards.length + " cờ đã quyết.");
  } catch (e) {
    flash("Lưu hỏng: " + e.message, true);
  }
});

render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
