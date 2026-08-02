"""Sinh trang HTML tự chứa để duyệt bộ nhãn — bước 2 của maker-checker.

Vì sao cần: `gold.seed.jsonl` lưu span dạng `[295, 391]`. Duyệt bằng editor nghĩa là
phải tự đếm ký tự trong fixture để biết đó là chữ gì — không kiểm nổi 49 Compliance
Unit. Trang này hiển thị toàn văn Điều, tô màu span theo vai, và cho sửa bằng cách
bôi đen chữ hoặc bấm vào đơn vị.

**Trang phải hiện được VAI**, không chỉ span. Bản đầu thiếu hẳn phần này: 49 CU trong
danh sách trông y hệt nhau dù 9 cái là meta-CU, và 45 bản ghi premise thì không xuất
hiện ở đâu cả — tức là cả bước phân loại nằm ngoài tầm duyệt. Nay mỗi mục mang huy
hiệu ACTOR / META / PREMISE, có bộ lọc theo vai, meta-CU hiện bảng cổng chặn, và
premise có khung duyệt riêng (loại con + bí danh) vì nó không có 4-tuple để sửa span.

Hai hợp đồng, hai file: `gold.jsonl` (CU, thứ `run_eval.py` đọc) và
`gold.premise.jsonl`. Trộn chung sẽ khiến `run_eval` gặp bản ghi không có
`subject_span` và tính sai trong im lặng.

Đây là CÔNG CỤ NỘI BỘ, cố ý không nhét vào app Next.js: nó chỉ phục vụ việc gán nhãn,
không phải tính năng cho người dùng cuối.

Chạy:
    uv run python eval/ontology/review_ui.py                 # sinh HTML rồi tự mở
    uv run python eval/ontology/review_ui.py --serve         # kèm server lưu tại chỗ
    uv run python eval/ontology/review_ui.py --no-open

Không có `--serve` thì trang vẫn chạy offline: tự lưu vào localStorage, xuất bằng nút
"Tải gold.jsonl". Có `--serve` thì nút "Lưu" ghi thẳng vào eval/ontology/.
"""
from __future__ import annotations

import argparse
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from app.ontology.parser import khoan_de_trich, parse_dieu
from app.ontology.segmenter import segment

_INDEX = Path("data/fixtures/_index.json")
_SEED = Path("eval/ontology/gold.seed.jsonl")
_PREMISE_SEED = Path("eval/ontology/gold.premise.seed.jsonl")
_GOLD = Path("eval/ontology/gold.jsonl")
_GOLD_PREMISE = Path("eval/ontology/gold.premise.jsonl")
_OUT = Path("eval/ontology/review.html")

# Các trường được xuất ra gold.jsonl — đúng thứ `run_eval.py` đọc.
EXPORT_FIELDS = [
    "id", "fixture", "reviewed", "role", "subject_span", "subject_source",
    "action_span", "logic", "conditions", "expect_hard_error", "note",
]
# Tầng premise xuất RIÊNG (`gold.premise.jsonl`): nó không có 4-tuple, trộn chung
# một file sẽ phá hợp đồng mà `run_eval.py` đang đọc.
PREMISE_FIELDS = ["id", "fixture", "reviewed", "premise_kind", "alias", "sai_loai", "note"]


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()
    ]


def build_payload(
    seed_path: Path = _SEED, premise_path: Path = _PREMISE_SEED
) -> dict:
    """Gộp bộ khung + toàn văn Điều + đơn vị đã tách thành một payload nhúng vào HTML."""
    index = json.loads(_INDEX.read_text(encoding="utf-8"))
    seeds = _read_jsonl(seed_path) + _read_jsonl(premise_path)
    # Bộ nhãn đã duyệt (nếu có) ghi đè lên khung, để mở lại là tiếp tục được.
    done = {r["id"]: r for r in _read_jsonl(_GOLD) + _read_jsonl(_GOLD_PREMISE)}

    fixtures: dict[str, dict] = {}
    trees: dict[str, object] = {}
    items = []
    for s in seeds:
        name = Path(s["fixture"]).name
        if name not in fixtures:
            text = Path(s["fixture"]).read_text(encoding="utf-8")
            fixtures[name] = {"text": text, "so_hieu": index[name]}
            trees[name] = parse_dieu(text, index[name])
        dieu = trees[name]
        so_khoan = s["id"].rsplit("#khoan_", 1)[-1] if "#khoan_" in s["id"] else ""
        # `khoan_de_trich` trả khoản ảo cho Điều không chẻ khoản (9.4% số điều) —
        # dùng `dieu.khoan` trực tiếp thì những điều đó làm hỏng cả trang.
        khoan = next(k for k in khoan_de_trich(dieu) if k.so_hien_thi == so_khoan)
        item = {**s, **done.get(s["id"], {})}
        item.setdefault("kind", "cu")
        item.setdefault("role", "actor_cu")
        item["fixture_name"] = name
        item["khoan"] = so_khoan
        item["dieu_title"] = f"Điều {dieu.so_hien_thi}. {dieu.tieu_de}"
        item["khoan_span"] = [khoan.start, khoan.end]
        item["diem"] = [d.so_hien_thi for d in khoan.diem]
        item["units"] = [
            {"uid": u.uid, "kind": u.kind, "diem": u.source_diem, "start": u.start, "end": u.end}
            for u in segment(dieu, khoan)
        ]
        items.append(item)
    return {"fixtures": fixtures, "items": items}


def render(payload: dict, *, can_save: bool) -> str:
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return (
        _HTML.replace("__DATA__", data)
        .replace("__CAN_SAVE__", "true" if can_save else "false")
        .replace("__FIELDS__", json.dumps(EXPORT_FIELDS))
        .replace("__PFIELDS__", json.dumps(PREMISE_FIELDS))
    )


def to_jsonl(rows: list[dict], fields: list[str] | None = None) -> str:
    fields = fields or EXPORT_FIELDS
    out = [json.dumps({k: r.get(k) for k in fields}, ensure_ascii=False) for r in rows]
    return "\n".join(out) + "\n"


def split_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Tách bản ghi CU và premise — hai hợp đồng khác nhau, hai file khác nhau."""
    return (
        [r for r in rows if r.get("kind", "cu") != "premise"],
        [r for r in rows if r.get("kind") == "premise"],
    )


class _Handler(BaseHTTPRequestHandler):
    """Server tối giản chỉ phục vụ localhost: trả trang và nhận lệnh lưu."""

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
        cu_rows, pr_rows = split_rows(rows)
        _GOLD.parent.mkdir(parents=True, exist_ok=True)
        _GOLD.write_text(to_jsonl(cu_rows), encoding="utf-8")
        print(f"  [lưu] {_GOLD} — "
              f"{sum(1 for r in cu_rows if r.get('reviewed'))}/{len(cu_rows)} đã duyệt")
        if pr_rows:
            _GOLD_PREMISE.write_text(to_jsonl(pr_rows, PREMISE_FIELDS), encoding="utf-8")
            print(f"  [lưu] {_GOLD_PREMISE} — "
                  f"{sum(1 for r in pr_rows if r.get('reviewed'))}/{len(pr_rows)} đã duyệt")
        done = sum(1 for r in rows if r.get("reviewed"))
        self._send(200, json.dumps({"ok": True, "reviewed": done}).encode(), "application/json")

    def log_message(self, *args) -> None:  # tắt log mặc định cho đỡ ồn
        pass


def main(argv: list[str] | None = None) -> Path:
    ap = argparse.ArgumentParser(description="Trang duyệt bộ nhãn ontology")
    ap.add_argument("--seed", default=str(_SEED))
    ap.add_argument("--premise-seed", default=str(_PREMISE_SEED))
    ap.add_argument("--out", default=str(_OUT))
    ap.add_argument("--serve", action="store_true", help="chạy server để nút Lưu ghi thẳng file")
    ap.add_argument("--port", type=int, default=8777)
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args(argv)

    payload = build_payload(Path(args.seed), Path(args.premise_seed))
    html = render(payload, can_save=args.serve)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Tự ghi bằng encoding utf-8 — không bao giờ qua redirect của shell.
    out.write_text(html, encoding="utf-8")
    n = {k: sum(1 for i in payload["items"] if i.get("kind", "cu") == "cu"
                and i.get("role") == k) for k in ("actor_cu", "meta_cu")}
    n_pr = sum(1 for i in payload["items"] if i.get("kind") == "premise")
    print(f"Đã ghi {out} — {n['actor_cu']} actor-CU · {n['meta_cu']} meta-CU · {n_pr} premise")

    if args.serve:
        _Handler.html = html
        url = f"http://127.0.0.1:{args.port}/"
        print(f"Server tại {url} (chỉ localhost). Nút Lưu sẽ ghi vào {_GOLD}. Ctrl+C để dừng.")
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
<title>Duyệt bộ nhãn ontology</title>
<style>
:root{--bg:#fff;--fg:#1c1917;--dim:#6b7280;--line:#e7e5e4;--panel:#fafaf9;
 --subj:#2563eb;--subjbg:#dbeafe;--act:#b45309;--actbg:#fef3c7;--cond:#047857;--condbg:#d1fae5;
 --err:#b91c1c;--errbg:#fef2f2;--ok:#047857;}
@media(prefers-color-scheme:dark){:root{--bg:#1c1917;--fg:#e7e5e4;--dim:#a8a29e;--line:#44403c;
 --panel:#292524;--subjbg:#1e3a5f;--actbg:#4a3410;--condbg:#053c2e;--errbg:#2a1315;}}
*{box-sizing:border-box}
body{margin:0;font:14px/1.6 system-ui,"Segoe UI",sans-serif;background:var(--bg);color:var(--fg)}
#app{display:grid;grid-template-columns:230px 1fr 340px;height:100vh}
@media(max-width:1100px){#app{grid-template-columns:1fr;height:auto}}
aside,section,#side{overflow-y:auto;padding:12px}
aside{border-right:1px solid var(--line);background:var(--panel)}
#side{border-left:1px solid var(--line);background:var(--panel)}
h1{font-size:15px;margin:0 0 10px}
.item{padding:5px 7px;border-radius:6px;cursor:pointer;font-size:12px;display:flex;gap:6px;align-items:center}
.item:hover{background:var(--line)}
.item.sel{background:var(--subjbg);font-weight:600}
.dot{width:8px;height:8px;border-radius:50%;background:var(--dim);flex:none}
.dot.done{background:var(--ok)}.dot.err{background:var(--err)}
.bar{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-bottom:10px;
 padding-bottom:10px;border-bottom:1px solid var(--line)}
button{font:inherit;padding:4px 9px;border:1px solid var(--line);border-radius:6px;
 background:var(--bg);color:var(--fg);cursor:pointer}
button:hover{background:var(--line)}
button.p{background:var(--subj);color:#fff;border-color:var(--subj)}
button.sm{padding:1px 6px;font-size:11px}
pre#doc{white-space:pre-wrap;word-break:break-word;background:var(--panel);
 border:1px solid var(--line);border-radius:8px;padding:12px;font:inherit;margin:0}
.s-subject{background:var(--subjbg);border-bottom:2px solid var(--subj)}
.s-action{background:var(--actbg);border-bottom:2px solid var(--act)}
.s-condition{background:var(--condbg);border-bottom:2px solid var(--cond)}
.s-premise{background:var(--condbg);border-bottom:2px dotted var(--cond)}
.s-alias{background:var(--actbg);outline:1px solid var(--act);font-weight:600}
.outside{opacity:.45}
/* Huy hiệu vai — chỗ trước đây thiếu hẳn: 49 CU trong danh sách trông y hệt nhau
   dù 9 cái là meta-CU, và 45 premise thì không hiện ra ở đâu cả. */
.tag{font-size:9.5px;font-weight:700;padding:0 4px;border-radius:4px;flex:none;
 letter-spacing:.03em;border:1px solid transparent}
.t-actor_cu{background:var(--subjbg);color:var(--subj);border-color:var(--subj)}
.t-meta_cu{background:var(--actbg);color:var(--act);border-color:var(--act)}
.t-premise{background:var(--condbg);color:var(--cond);border-color:var(--cond)}
.filt{display:flex;gap:3px;flex-wrap:wrap;margin-bottom:8px}
.filt button{font-size:11px;padding:2px 6px}
.filt button.on{background:var(--fg);color:var(--bg);border-color:var(--fg)}
.gate{font-size:11.5px;border-left:3px solid var(--act);padding:5px 8px;margin:4px 0;
 background:var(--actbg);border-radius:0 5px 5px 0}
.gate code{font-size:10.5px;word-break:break-all}
.no{color:var(--err);font-weight:600}
.f{border:1px solid var(--line);border-radius:8px;padding:8px;margin-bottom:8px;background:var(--bg)}
.f h3{margin:0 0 5px;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--dim)}
.q{font-size:12px;max-height:70px;overflow:auto;border-left:3px solid var(--line);padding-left:7px;margin:4px 0}
.meta{font-size:11px;color:var(--dim);font-family:ui-monospace,monospace}
label{font-size:12px;display:flex;gap:5px;align-items:center;margin:3px 0}
select,input[type=text],textarea{font:inherit;font-size:12px;padding:2px 5px;background:var(--bg);
 color:var(--fg);border:1px solid var(--line);border-radius:5px}
textarea{width:100%;min-height:44px}
.cond{border-top:1px dashed var(--line);padding-top:5px;margin-top:5px}
.warn{background:var(--errbg);border-left:3px solid var(--err);padding:6px 8px;border-radius:5px;
 font-size:11.5px;margin-bottom:8px}
.units{display:flex;flex-wrap:wrap;gap:3px;margin-top:6px}
.u{font-size:10.5px;padding:1px 5px;border:1px solid var(--line);border-radius:10px;cursor:pointer;
 background:var(--bg)}
.u:hover{background:var(--subjbg)}
.hint{font-size:11.5px;color:var(--dim);margin:6px 0}
#toast{position:fixed;bottom:14px;right:14px;background:var(--fg);color:var(--bg);padding:7px 13px;
 border-radius:7px;font-size:12.5px;opacity:0;transition:opacity .2s;pointer-events:none}
#toast.on{opacity:1}
</style>
</head>
<body>
<div id="app">
  <aside>
    <h1>Bộ nhãn <span id="prog" class="meta"></span></h1>
    <div class="filt" id="filt"></div>
    <div id="list"></div>
  </aside>
  <section>
    <div class="bar">
      <button onclick="go(-1)">◀</button><button onclick="go(1)">▶</button>
      <span id="who" class="meta"></span>
      <span style="flex:1"></span>
      <button class="p" onclick="save()">Lưu</button>
      <button onclick="dl()">Tải gold.jsonl</button>
      <label style="margin:0">Nhập<input type="file" id="imp" accept=".jsonl" style="display:none"></label>
      <button onclick="document.getElementById('imp').click()">Nhập JSONL</button>
    </div>
    <div class="hint" id="hint"></div>
    <div class="bar" id="tools" style="border:0;padding:0">
      <button onclick="assign('subject')">Gán Subject</button>
      <button onclick="assign('action')">Gán Action</button>
      <button onclick="addCond()">+ Điều kiện</button>
      <span id="sel" class="meta"></span>
    </div>
    <pre id="doc"></pre>
    <div class="units" id="units"></div>
  </section>
  <div id="side"></div>
</div>
<div id="toast"></div>
<script>
const DATA = __DATA__, CAN_SAVE = __CAN_SAVE__, FIELDS = __FIELDS__, PFIELDS = __PFIELDS__;
const KEY = "lexflow-gold-v2";   // v1 không có `role`/`kind` — đổi khoá để không trộn
let items = DATA.items, cur = 0, pendingCond = null, filt = "all";
const NHAN = {actor_cu: "ACTOR", meta_cu: "META", premise: "PREMISE"};
const loai = r => r.kind === "premise" ? "premise" : (r.role || "actor_cu");
const isPre = r => r.kind === "premise";
const flds = r => isPre(r) ? PFIELDS.concat(["kind"]) : FIELDS.concat(["kind"]);

// Khôi phục tiến độ đã lưu trong trình duyệt (chống mất khi lỡ đóng tab).
try {
  const raw = localStorage.getItem(KEY);
  if (raw) {
    const saved = JSON.parse(raw);
    const by = Object.fromEntries(saved.map(r => [r.id, r]));
    items = items.map(it => by[it.id] ? {...it, ...by[it.id]} : it);
  }
} catch (e) { console.warn("localStorage:", e); }

// Escape cả " và ' vì `alias` được nhả vào THUỘC TÍNH value= của ô nhập, không chỉ
// vào nội dung thẻ — thiếu hai ký tự này là một dấu nháy trong luật phá vỡ trang.
const esc = s => String(s).replace(/[&<>"']/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const it = () => items[cur];
const txt = () => DATA.fixtures[it().fixture_name].text;
const cut = sp => sp ? txt().slice(sp[0], sp[1]) : "";

function persist() {
  try { localStorage.setItem(KEY, JSON.stringify(items.map(r =>
    Object.fromEntries(flds(r).map(f => [f, r[f]]))))); } catch (e) { console.warn(e); }
}

function toast(m) {
  const t = document.getElementById("toast");
  t.textContent = m; t.classList.add("on"); setTimeout(() => t.classList.remove("on"), 1600);
}

/* --- Văn bản: cắt thành lát tại MỌI biên (đơn vị + span đã gán) nên mỗi lát là một
   text node có offset toàn cục xác định. Nhờ vậy selection -> offset là phép cộng. --- */
function spans() {
  const o = [];
  if (isPre(it())) {
    // Premise không có 4-tuple: tô nguyên khối + tô đậm riêng bí danh nếu có.
    if (it().raw_span) o.push([...it().raw_span, "premise"]);
    const al = (it()._may_de_xuat || {}).alias_span;
    if (al) o.push([...al, "alias"]);
    return o;
  }
  if (it().subject_span) o.push([...it().subject_span, "subject"]);
  if (it().action_span) o.push([...it().action_span, "action"]);
  (it().conditions || []).forEach(c => { if (c.span) o.push([...c.span, "condition"]); });
  return o;
}

function draw() {
  const t = txt(), sp = spans(), [ks, ke] = it().khoan_span;
  const cuts = new Set([0, t.length, ks, ke]);
  it().units.forEach(u => { cuts.add(u.start); cuts.add(u.end); });
  sp.forEach(s => { cuts.add(s[0]); cuts.add(s[1]); });
  const b = [...cuts].filter(x => x >= 0 && x <= t.length).sort((x, y) => x - y);
  let html = "";
  for (let i = 0; i < b.length - 1; i++) {
    const a = b[i], z = b[i + 1];
    if (a === z) continue;
    const hit = sp.filter(s => s[0] <= a && s[1] >= z)
                  .sort((p, q) => (p[1] - p[0]) - (q[1] - q[0]))[0];
    // Đơn vị [0] là tiêu đề Điều -> vẫn coi là trong phạm vi cho chủ ngữ kế thừa.
    const inScope = (a >= ks && z <= ke) || z <= it().units[0].end;
    const cls = (hit ? "s-" + hit[2] + " " : "") + (inScope ? "" : "outside");
    html += `<span data-s="${a}" class="${cls}">${esc(t.slice(a, z))}</span>`;
  }
  document.getElementById("doc").innerHTML = html;
  document.getElementById("units").innerHTML = it().units.map(u =>
    `<span class="u" onclick="pickUnit(${u.start},${u.end})">[${u.uid}] ${
      u.kind === "tieu_de" ? "tiêu đề" : (u.diem ? "điểm " + u.diem : "bao trùm")}</span>`).join("");
}

function nodeOff(n, o) {
  const el = n.nodeType === 3 ? n.parentElement : n;
  if (!el || el.dataset.s === undefined) return null;
  return parseInt(el.dataset.s, 10) + o;
}

function selection() {
  const s = window.getSelection();
  if (!s || s.isCollapsed) return null;
  const a = nodeOff(s.anchorNode, s.anchorOffset), z = nodeOff(s.focusNode, s.focusOffset);
  if (a === null || z === null) return null;
  let lo = Math.min(a, z), hi = Math.max(a, z), t = txt();
  while (lo < hi && /\s/.test(t[lo])) lo++;          // bỏ khoảng trắng ở rìa để
  while (hi > lo && /\s/.test(t[hi - 1])) hi--;      // span không dính xuống dòng
  return hi > lo ? [lo, hi] : null;
}

function need() {
  const s = selection();
  if (!s) { toast("Chưa bôi đen đoạn nào"); return null; }
  return s;
}
function assign(f) { const s = need(); if (!s) return; it()[f + "_span"] = s; sync(); }
function addCond() {
  const s = need(); if (!s) return;
  (it().conditions = it().conditions || []).push({source_diem: it().diem[0] || null, span: s});
  sync();
}
function pickUnit(a, z) {
  if (pendingCond !== null) { it().conditions[pendingCond].span = [a, z]; pendingCond = null; }
  else if (!it().subject_span) it().subject_span = [a, z];
  else it().action_span = [a, z];
  sync();
}

function set(f, v) { it()[f] = v; sync(); }
function setCond(i, f, v) { it().conditions[i][f] = f === "source_diem" && !v ? null : v; sync(); }
function delCond(i) { it().conditions.splice(i, 1); sync(); }
function clr(f) { it()[f] = null; sync(); }
function aimCond(i) { pendingCond = i; toast("Bấm một đơn vị để gán cho điều kiện này"); }
function condFromSel(i) { const s = need(); if (!s) return; it().conditions[i].span = s; sync(); }

// Cổng không có bên bị ràng buộc — giữ đồng bộ với
// `extractor._GATE_KHONG_CO_ACTOR`. `chu_the` KHÔNG nằm đây: role qualification có
// một vai cần định danh nên subject vẫn bắt buộc.
const GATE_KHONG_ACTOR = ["thoi_gian", "lanh_tho"];
const subjMien = r => r.role === "meta_cu" && (r.gates || []).length > 0 &&
  (r.gates || []).every(g => GATE_KHONG_ACTOR.includes(g.kind));
// Giữ đồng bộ với `extractor.conditions_khong_ap_dung`: thêm vế "Khoản không chẻ
// Điểm". TT40 Đ52 k6 cũng là cổng thời gian nhưng CÓ điểm a/b mang mốc thật.
const condMien = () => subjMien(it()) && !(it().diem || []).length;

function field(name, key, cls) {
  const sp = it()[key];
  // Ô trống HỢP LỆ phải đọc ra là "không áp dụng", không phải "chưa gán" — hai thứ
  // đó là hai trạng thái khác nhau, gộp lại thì trích hỏng núp được dưới vỏ hợp lệ.
  const mien = key === "subject_span" && subjMien(it());
  const rong = mien
    ? `<i>không áp dụng — cổng thời gian/lãnh thổ không có bên bị ràng buộc</i>`
    : "<i>—</i>";
  return `<div class="f"><h3 style="color:var(--${cls})">${name}</h3>
    <div class="meta">${sp ? sp[0] + "–" + sp[1] : (mien ? "không áp dụng" : "chưa gán")}
      ${sp ? `<button class="sm" onclick="clr('${key}')">xoá</button>` : ""}</div>
    <div class="q">${sp ? esc(cut(sp)) : rong}</div></div>`;
}

// Θ của cổng ở dạng cấu trúc. Span này do REGEX tách, không do mô hình chọn — nhưng
// regex vẫn sai được, nên vẫn phải bày ra cho người duyệt đối chiếu.
function dkcBox() {
  const d = it().dieu_kien_cong;
  if (!d) return "";
  const moc = d.moc === "ket_thuc" ? "KẾT THÚC hiệu lực" : "bắt đầu có hiệu lực";
  return `<div class="gate"><b>mốc thời gian</b> · ${esc(moc)}
    ${d.ngay ? `· <b>${esc(d.ngay)}</b>` : '<span class="no">· không có ngày</span>'}
    <br><code>${esc(d.raw_text || "")}</code>
    ${d.char_span ? `<br><span class="meta">${d.char_span[0]}–${d.char_span[1]}</span>` : ""}
    ${d.ghi_chu ? `<br><i>${esc(d.ghi_chu)}</i>` : ""}</div>`;
}

function gateBox() {
  const gs = it().gates || [];
  if (it().role !== "meta_cu") return "";
  if (!gs.length) return `<div class="warn">meta-CU nhưng <b>không có cổng</b> —
    máy không xác định được nó chặn cái gì.</div>`;
  return `<div class="f"><h3 style="color:var(--act)">Cổng chặn (${gs.length})</h3>` +
    dkcBox() +
    gs.map(g => `<div class="gate">
      <b>${esc(g.kind)}</b> · phủ cấp <b>${esc(g.pham_vi)}</b>
      ${g.phu_dinh ? '<span class="no">· LOẠI TRỪ (không áp dụng)</span>' : ""}
      ${g.suy_ra_duoc ? "" : '<span class="no">· chưa quy được về khoá node</span>'}
      ${g.targets && g.targets.length
        ? `<br>đích: <code>${g.targets.map(esc).join("<br>")}</code>`
        : "<br><i>đích: cả cấp trên, không liệt kê</i>"}
      ${g.ngoai_tru && g.ngoai_tru.length
        ? `<br>ngoại trừ: <code>${g.ngoai_tru.map(esc).join("<br>")}</code>` : ""}
      ${g.ghi_chu ? `<br><i>${esc(g.ghi_chu)}</i>` : ""}</div>`).join("") + `</div>`;
}

function roleBox() {
  return `<div class="f"><h3>Vai (bước phân loại)</h3>
    <label>role
      <select onchange="set('role',this.value)">
        ${["actor_cu", "meta_cu"].map(v =>
          `<option ${it().role === v ? "selected" : ""}>${v}</option>`).join("")}
      </select></label>
    <div class="hint" style="margin:2px 0 0">meta-CU được đánh giá <b>trước</b> và
      không bao giờ tự bị báo vi phạm. Gán nhầm vai là bản ghi không bao giờ bị phán định.</div>
  </div>${gateBox()}`;
}

function premiseSide() {
  const m = it()._may_de_xuat || {}, w = (m.errors || []).concat(m.warnings || []);
  return `
    <label><input type="checkbox" ${it().reviewed ? "checked" : ""}
      onchange="set('reviewed',this.checked)"> <b>Đã duyệt</b></label>
    <label><input type="checkbox" ${it().sai_loai ? "checked" : ""}
      onchange="set('sai_loai',this.checked)"> <b class="no">Không phải premise</b></label>
    <div class="f"><h3 style="color:var(--cond)">Loại premise</h3>
      <select onchange="set('premise_kind',this.value)">
        ${["dinh_nghia", "vai_tro", "pham_vi"].map(v =>
          `<option ${it().premise_kind === v ? "selected" : ""}>${v}</option>`).join("")}
      </select>
      <div class="hint" style="margin:4px 0 0">
        <b>dinh_nghia</b> định nghĩa thuật ngữ ·
        <b>vai_tro</b> khai báo một vai chủ thể ·
        <b>pham_vi</b> phát biểu phạm vi</div></div>
    <div class="f"><h3>Bí danh văn bản tự đặt</h3>
      <input type="text" style="width:100%" value="${esc(it().alias || "")}"
        placeholder="(không có)" onchange="set('alias',this.value||null)">
      <div class="hint" style="margin:4px 0 0">Ví dụ "(sau đây gọi là khách hàng)".
        Bôi vàng trong văn bản là chỗ máy bóc ra.</div></div>
    <div class="f"><h3>Nguyên văn</h3>
      <div class="meta">${it().raw_span ? it().raw_span[0] + "–" + it().raw_span[1] : "—"}</div>
      <div class="q">${esc(cut(it().raw_span))}</div></div>
    ${m.gop_vao_gate ? `<div class="f"><h3>Góp vào cổng</h3>
      <code class="meta">${esc(m.gop_vao_gate)}</code>
      <div class="hint" style="margin:4px 0 0">Khai báo vai trò này là một phần tử của
        tập chủ thể mà cổng mức Điều phủ — bản thân nó không phải cổng.</div></div>` : ""}
    ${w.length ? `<div class="warn"><b>Máy tự gắn cờ:</b><br>${
      w.map(x => esc(x)).join("<br>")}</div>` : ""}
    <div class="f"><h3>Ghi chú</h3>
      <textarea onchange="set('note',this.value)">${esc(it().note || "")}</textarea></div>`;
}

function side() {
  if (isPre(it())) { document.getElementById("side").innerHTML = premiseSide(); return; }
  const m = it()._may_de_xuat || {}, w = (m.errors || []).concat(m.warnings || []);
  const diemOpts = ["", ...it().diem].map(d =>
    `<option value="${d}">${d || "(không có điểm)"}</option>`).join("");
  document.getElementById("side").innerHTML = `
    <label><input type="checkbox" ${it().reviewed ? "checked" : ""}
      onchange="set('reviewed',this.checked)"> <b>Đã duyệt</b></label>
    ${roleBox()}
    ${field("Subject", "subject_span", "subj")}
    <div class="f"><h3>Thuộc tính</h3>
      <label>subject_source
        <select onchange="set('subject_source',this.value||null)">
          ${[["", "(không áp dụng)"], ["explicit", "explicit"], ["inherited", "inherited"]]
            .map(([v, t]) => `<option value="${v}" ${
              (it().subject_source || "") === v ? "selected" : ""}>${t}</option>`).join("")}
        </select></label>
      <label>logic
        <select onchange="set('logic',this.value)">
          ${["all", "any", "unknown"].map(v =>
            `<option ${it().logic === v ? "selected" : ""}>${v}</option>`).join("")}
        </select></label>
      <label><input type="checkbox" ${it().expect_hard_error ? "checked" : ""}
        onchange="set('expect_hard_error',this.checked)"> cố ý cài lỗi</label>
    </div>
    ${field("Action", "action_span", "act")}
    <div class="f"><h3 style="color:var(--cond)">Điều kiện (${(it().conditions || []).length})</h3>
      ${condMien() ? `<div class="hint" style="margin:0 0 4px"><i>không áp dụng</i> —
        mệnh đề hiệu lực ở khoản không chẻ Điểm thì không có điều kiện theo nghĩa
        nghĩa vụ. Ô rỗng ở đây là <b>có chủ ý</b>, không phải bỏ sót.</div>` : ""}
      ${(it().conditions || []).map((c, i) => `<div class="cond">
        <div class="meta">#${i + 1} ${c.span ? c.span[0] + "–" + c.span[1] : "chưa gán"}
          <select onchange="setCond(${i},'source_diem',this.value)">${
            diemOpts.replace(`value="${c.source_diem || ""}"`,
                             `value="${c.source_diem || ""}" selected`)}</select>
          <button class="sm" onclick="condFromSel(${i})">từ bôi đen</button>
          <button class="sm" onclick="aimCond(${i})">từ đơn vị</button>
          <button class="sm" onclick="delCond(${i})">xoá</button></div>
        <div class="q">${c.span ? esc(cut(c.span)) : "<i>—</i>"}</div></div>`).join("")}
    </div>
    ${w.length ? `<div class="warn"><b>Máy tự gắn cờ:</b><br>${
      w.map(x => esc(x)).join("<br>")}</div>` : ""}
    <div class="f"><h3>Ghi chú</h3>
      <textarea onchange="set('note',this.value)">${esc(it().note || "")}</textarea></div>`;
}

const hien = i => filt === "all" || loai(items[i]) === filt;

function list() {
  const dem = k => items.filter(r => loai(r) === k).length;
  document.getElementById("filt").innerHTML =
    [["all", "tất cả " + items.length], ["actor_cu", "actor " + dem("actor_cu")],
     ["meta_cu", "meta " + dem("meta_cu")], ["premise", "premise " + dem("premise")]]
    .map(([k, t]) => `<button class="${filt === k ? "on" : ""}" onclick="setFilt('${k}')"
      >${t}</button>`).join("");
  document.getElementById("list").innerHTML = items.map((r, i) => {
    if (!hien(i)) return "";
    const bad = (r._may_de_xuat && (r._may_de_xuat.errors || []).length) ? " err" : "";
    const l = loai(r);
    return `<div class="item ${i === cur ? "sel" : ""}" onclick="jump(${i})">
      <span class="dot${r.reviewed ? " done" : bad}"></span>
      <span class="tag t-${l}">${NHAN[l]}</span>
      <span>${esc(r.id.replace(/#than\//, " ").replace(/#khoan_/, " k"))}</span></div>`;
  }).join("");
  const n = items.filter(r => r.reviewed).length;
  document.getElementById("prog").textContent = n + "/" + items.length;
}

function setFilt(k) {
  filt = k;
  if (!hien(cur)) { const i = items.findIndex((_, j) => hien(j)); if (i >= 0) { jump(i); return; } }
  sync();
}

function sync() {
  persist(); draw(); side(); list();
  // Premise không có 4-tuple để gán span — ẩn hẳn thanh công cụ thay vì để nút chết.
  document.getElementById("tools").style.display = isPre(it()) ? "none" : "";
  document.getElementById("hint").innerHTML = isPre(it())
    ? `Đơn vị <b>premise</b>: không trích Subject/Action. Việc cần làm là xác nhận
       <b>phán quyết phân loại</b> bên phải — đúng loại chưa, bí danh có đúng không.`
    : `Bôi đen chữ trong văn bản rồi bấm nút gán bên phải. Hoặc bấm một
       <b>đơn vị</b> ở dưới để gán nhanh cả đơn vị. Phần mờ là ngoài Khoản đang xét.`;
}
function jump(i) {
  cur = i; pendingCond = null; sync();
  document.getElementById("who").textContent =
    NHAN[loai(it())] + " · " + it().id + " — " + it().dieu_title;
  window.scrollTo(0, 0);
  // Premise nằm cuối danh sách 94 mục — không kéo vào tầm nhìn thì bấm ▶ xong
  // không biết mình đang ở đâu.
  const sel = document.querySelector("#list .item.sel");
  if (sel) sel.scrollIntoView({block: "nearest"});
}
function go(d) {
  // Nhảy trong PHẠM VI ĐANG LỌC, nếu không thì ▶ sẽ rơi vào mục đang bị ẩn.
  const vis = items.map((_, i) => i).filter(hien);
  const at = vis.indexOf(cur);
  const nx = Math.min(vis.length - 1, Math.max(0, (at < 0 ? 0 : at) + d));
  if (vis.length) jump(vis[nx]);
}

// `rows()` giữ `kind` để server tách hai file. Lúc TẢI VỀ thì chiếu đúng bộ trường
// của từng hợp đồng, để file tải bằng trình duyệt khớp y file server ghi.
function rows() { return items.map(r => Object.fromEntries(flds(r).map(f => [f, r[f]]))); }
function chieu(r, fs) { return JSON.stringify(Object.fromEntries(fs.map(f => [f, r[f]]))); }
function jsonl() {
  return items.filter(r => !isPre(r)).map(r => chieu(r, FIELDS)).join("\n") + "\n";
}

function tai(ten, noi_dung) {
  const b = new Blob([noi_dung], {type: "application/x-ndjson;charset=utf-8"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(b); a.download = ten; a.click();
  URL.revokeObjectURL(a.href);
}

function dl() {
  tai("gold.jsonl", jsonl());
  // Hai hợp đồng khác nhau ⇒ hai file. Trộn chung sẽ làm `run_eval.py` đọc phải
  // bản ghi không có subject_span và im lặng tính sai.
  const pr = items.filter(isPre);
  if (pr.length) tai("gold.premise.jsonl",
                     pr.map(r => chieu(r, PFIELDS)).join("\n") + "\n");
  toast("Đã tải " + (pr.length ? "gold.jsonl + gold.premise.jsonl" : "gold.jsonl")
        + " — chép vào eval/ontology/");
}

async function save() {
  if (!CAN_SAVE) { dl(); return; }
  try {
    const r = await fetch("/", {method: "POST", headers: {"Content-Type": "application/json"},
                               body: JSON.stringify(rows())});
    const j = await r.json();
    toast("Đã ghi gold.jsonl — " + j.reviewed + " đã duyệt");
  } catch (e) { toast("Lưu hỏng: " + e); }
}

document.getElementById("imp").addEventListener("change", async ev => {
  const f = ev.target.files[0]; if (!f) return;
  const by = {};
  (await f.text()).split("\n").filter(l => l.trim()).forEach(l => {
    const r = JSON.parse(l); by[r.id] = r;
  });
  items = items.map(x => by[x.id] ? {...x, ...by[x.id]} : x);
  sync(); toast("Đã nhập " + Object.keys(by).length + " dòng");
});

document.addEventListener("selectionchange", () => {
  const s = selection();
  document.getElementById("sel").textContent = s ? "đang chọn " + s[0] + "–" + s[1] : "";
});
document.addEventListener("keydown", e => {
  if (e.ctrlKey && e.key === "s") { e.preventDefault(); save(); }
  if (e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") return;
  if (e.key === "j") go(1); if (e.key === "k") go(-1);
});

jump(0);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
