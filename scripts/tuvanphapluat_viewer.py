"""Local browser UI for the phamson02/tuvanphapluat dataset.

Reads the parquet files downloaded into data/tuvanphapluat/ directly via
DuckDB (no full in-memory load — keeps RAM usage low) and serves a small
FastAPI app with a single-page vanilla-JS UI for browsing/searching the
corpus and the train/test question-answer splits (with category-tag
filtering, e.g. narrowing to banking/payment topics).

Setup (one-time, ~540MB download):
    uv run python scripts/download_tuvanphapluat.py

Run:
    uv run --with duckdb uvicorn scripts.tuvanphapluat_viewer:app --port 8765

Then open http://127.0.0.1:8765
"""

from __future__ import annotations

from pathlib import Path

import duckdb
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "tuvanphapluat"
PAGE_SIZE_DEFAULT = 25
PAGE_SIZE_MAX = 100

app = FastAPI(title="tuvanphapluat viewer")


def _connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(database=":memory:")
    for name in ("corpus", "train", "test"):
        path = DATA_DIR / f"{name}.parquet"
        if not path.exists():
            raise RuntimeError(f"Missing {path} — download the dataset first.")
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{path.as_posix()}')")
    return con


_con = _connect()

QA_SPLITS = {"train", "test"}


def _paginate(page: int, page_size: int) -> tuple[int, int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), PAGE_SIZE_MAX)
    return page_size, (page - 1) * page_size


@app.get("/api/meta")
def meta() -> dict:
    con = _con.cursor()
    counts = {
        name: con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        for name in ("corpus", "train", "test")
    }
    sources = con.execute(
        "SELECT dataset, count(*) FROM corpus GROUP BY dataset ORDER BY 2 DESC"
    ).fetchall()
    return {"counts": counts, "corpus_sources": [{"dataset": d, "count": c} for d, c in sources]}


@app.get("/api/corpus")
def list_corpus(
    q: str = Query("", description="substring search over text"),
    dataset: str = Query("", description="filter by source dataset"),
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> dict:
    con = _con.cursor()
    limit, offset = _paginate(page, page_size)
    where = []
    params: list = []
    if q:
        where.append("text ILIKE ?")
        params.append(f"%{q}%")
    if dataset:
        where.append("dataset = ?")
        params.append(dataset)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    total = con.execute(f"SELECT count(*) FROM corpus {clause}", params).fetchone()[0]
    rows = con.execute(
        f"""SELECT oid, dataset, text FROM corpus {clause}
            ORDER BY oid LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    ).fetchall()
    items = [{"oid": r[0], "dataset": r[1], "text": r[2]} for r in rows]
    return {"total": total, "page": page, "page_size": limit, "items": items}


@app.get("/api/corpus/{oid}")
def get_corpus_item(oid: int) -> dict:
    row = _con.cursor().execute(
        "SELECT oid, dataset, text FROM corpus WHERE oid = ?", [oid]
    ).fetchone()
    if row is None:
        raise HTTPException(404, "not found")
    return {"oid": row[0], "dataset": row[1], "text": row[2]}


@app.get("/api/qa/{split}")
def list_qa(
    split: str,
    q: str = Query(""),
    category: str = Query("", description="exact category tag to filter on"),
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> dict:
    if split not in QA_SPLITS:
        raise HTTPException(404, "unknown split")
    con = _con.cursor()
    limit, offset = _paginate(page, page_size)
    where, params = [], []
    if q:
        where.append("(question ILIKE ? OR answer ILIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if category:
        where.append("EXISTS (SELECT 1 FROM unnest(category) t(c) WHERE lower(c) = lower(?))")
        params.append(category)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    total = con.execute(f"SELECT count(*) FROM {split} {clause}", params).fetchone()[0]
    rows = con.execute(
        f"""SELECT questionoid, question, answer, category, url FROM {split} {clause}
            ORDER BY questionoid LIMIT ? OFFSET ?""",
        [*params, limit, offset],
    ).fetchall()
    items = [
        {"questionoid": r[0], "question": r[1], "answer": r[2], "category": r[3], "url": r[4]}
        for r in rows
    ]
    return {"total": total, "page": page, "page_size": limit, "items": items}


@app.get("/api/categories/{split}")
def list_categories(split: str, q: str = Query(""), limit: int = 30) -> dict:
    if split not in QA_SPLITS:
        raise HTTPException(404, "unknown split")
    con = _con.cursor()
    where, params = "", []
    if q:
        where = "WHERE c ILIKE ?"
        params = [f"%{q}%"]
    rows = con.execute(
        f"""SELECT c, count(*) n FROM (SELECT unnest(category) AS c FROM {split}) {where}
            GROUP BY c ORDER BY n DESC LIMIT ?""",
        [*params, limit],
    ).fetchall()
    return {"items": [{"category": c, "count": n} for c, n in rows]}


@app.get("/api/qa/{split}/{questionoid}")
def get_qa_item(split: str, questionoid: int) -> dict:
    if split not in QA_SPLITS:
        raise HTTPException(404, "unknown split")
    con = _con.cursor()
    row = con.execute(
        f"""SELECT questionoid, question, segmented_question, answer, long_answer,
                   category, context, reference, contextoid, url
            FROM {split} WHERE questionoid = ?""",
        [questionoid],
    ).fetchone()
    if row is None:
        raise HTTPException(404, "not found")
    contextoid = row[8] or []
    linked = []
    if contextoid:
        placeholders = ",".join("?" * len(contextoid))
        linked_rows = con.execute(
            f"SELECT oid, dataset, text FROM corpus WHERE oid IN ({placeholders})",
            list(contextoid),
        ).fetchall()
        linked = [{"oid": r[0], "dataset": r[1], "text": r[2]} for r in linked_rows]
    return {
        "questionoid": row[0],
        "question": row[1],
        "segmented_question": row[2],
        "answer": row[3],
        "long_answer": row[4],
        "category": row[5],
        "context": row[6],
        "reference": row[7],
        "contextoid": contextoid,
        "url": row[9],
        "linked_corpus": linked,
    }


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _INDEX_HTML


_INDEX_HTML = r"""<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>tuvanphapluat — dataset browser</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
    margin: 0; display: flex; height: 100vh; overflow: hidden;
    background: light-dark(#f7f7f8, #17181c); color: light-dark(#1a1a1a, #e6e6e6);
  }
  aside { width: 260px; flex: none; border-right: 1px solid light-dark(#ddd,#333);
    padding: 16px; overflow-y: auto; }
  main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
  h1 { font-size: 15px; margin: 0 0 12px; }
  .tabs { display: flex; gap: 6px; margin-bottom: 12px; }
  .tab { padding: 6px 10px; border-radius: 6px; cursor: pointer; font-size: 13px;
    border: 1px solid light-dark(#ccc,#444); background: light-dark(#fff,#222); }
  .tab.active { background: light-dark(#2563eb,#3b82f6); color: #fff; border-color: transparent; }
  .toolbar { display: flex; gap: 8px; padding: 12px 16px; border-bottom: 1px solid light-dark(#ddd,#333); }
  input[type=text] { flex: 1; padding: 8px 10px; border-radius: 6px; border: 1px solid light-dark(#ccc,#444);
    background: light-dark(#fff,#222); color: inherit; font-size: 14px; }
  button { padding: 8px 12px; border-radius: 6px; border: 1px solid light-dark(#ccc,#444);
    background: light-dark(#fff,#222); color: inherit; cursor: pointer; font-size: 13px; }
  button:disabled { opacity: .4; cursor: default; }
  .content { flex: 1; display: flex; overflow: hidden; }
  .list { flex: 1; overflow-y: auto; padding: 8px 16px; }
  .row { padding: 10px 12px; border-radius: 8px; margin-bottom: 6px; cursor: pointer;
    background: light-dark(#fff,#1f2024); border: 1px solid light-dark(#e5e5e5,#2a2b30); }
  .row:hover { border-color: light-dark(#2563eb,#3b82f6); }
  .row .meta { font-size: 11px; opacity: .6; margin-bottom: 4px; }
  .row .preview { font-size: 13px; line-height: 1.4; }
  .detail { width: 46%; flex: none; border-left: 1px solid light-dark(#ddd,#333);
    overflow-y: auto; padding: 16px; font-size: 13px; line-height: 1.55; }
  .detail h2 { font-size: 15px; margin-top: 0; }
  .detail h3 { font-size: 12px; text-transform: uppercase; opacity: .6; margin: 16px 0 6px; }
  .badge { display: inline-block; font-size: 11px; background: light-dark(#eef,#28304a);
    color: light-dark(#3040a0,#a9bbff); border-radius: 4px; padding: 2px 6px; margin: 0 4px 4px 0; }
  .ctx { background: light-dark(#fafafa,#232429); border-radius: 6px; padding: 8px 10px; margin-bottom: 8px;
    white-space: pre-wrap; }
  .pager { display: flex; align-items: center; gap: 10px; padding: 10px 16px; border-top: 1px solid light-dark(#ddd,#333); font-size: 13px; }
  .empty { opacity: .5; padding: 40px; text-align: center; }
  a { color: light-dark(#2563eb,#6ea8fe); }
  .catbar { display: none; padding: 0 16px 12px; border-bottom: 1px solid light-dark(#ddd,#333); }
  .catbar.show { display: block; }
  .catbar input { width: 100%; padding: 6px 10px; border-radius: 6px; border: 1px solid light-dark(#ccc,#444);
    background: light-dark(#fff,#222); color: inherit; font-size: 13px; margin-bottom: 6px; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .chip { font-size: 12px; padding: 4px 8px; border-radius: 12px; cursor: pointer;
    background: light-dark(#eef,#28304a); color: light-dark(#3040a0,#a9bbff); border: none; }
  .chip:hover { background: light-dark(#dde,#334066); }
  .chip.active { background: light-dark(#2563eb,#3b82f6); color: #fff; }
  .chip .x { margin-left: 4px; opacity: .7; }
</style>
</head>
<body>
<aside>
  <h1>tuvanphapluat</h1>
  <div class="tabs">
    <div class="tab active" data-split="corpus">Corpus</div>
    <div class="tab" data-split="train">Train</div>
    <div class="tab" data-split="test">Test</div>
  </div>
  <div id="meta" style="font-size:12px; opacity:.7; line-height:1.6;"></div>
</aside>
<main>
  <div class="toolbar">
    <input id="q" type="text" placeholder="Tìm kiếm...">
    <button id="searchBtn">Tìm</button>
  </div>
  <div id="catbar" class="catbar">
    <input id="catQ" type="text" placeholder="Lọc theo danh mục (vd: ngân hàng, thanh toán)...">
    <div id="catChips" class="chips"></div>
  </div>
  <div class="content">
    <div id="list" class="list"><div class="empty">Đang tải...</div></div>
    <div id="detail" class="detail"><div class="empty">Chọn một dòng để xem chi tiết</div></div>
  </div>
  <div class="pager">
    <button id="prev">&larr; Trước</button>
    <span id="pageInfo"></span>
    <button id="next">Sau &rarr;</button>
  </div>
</main>
<script>
const state = { split: "corpus", q: "", category: "", page: 1, pageSize: 25, total: 0 };

function esc(s) {
  return (s ?? "").toString().replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
}
function truncate(s, n) { s = s ?? ""; return s.length > n ? s.slice(0, n) + "…" : s; }

async function loadMeta() {
  const r = await fetch("/api/meta"); const d = await r.json();
  document.getElementById("meta").innerHTML =
    `Corpus: ${d.counts.corpus.toLocaleString()}<br>Train: ${d.counts.train.toLocaleString()}<br>Test: ${d.counts.test.toLocaleString()}` +
    `<br><br><b>Nguồn corpus:</b><br>` +
    d.corpus_sources.map(s => `${esc(s.dataset)}: ${s.count.toLocaleString()}`).join("<br>");
}

async function loadList() {
  const listEl = document.getElementById("list");
  listEl.innerHTML = '<div class="empty">Đang tải...</div>';
  const params = new URLSearchParams({ q: state.q, page: state.page, page_size: state.pageSize });
  if (state.split !== "corpus" && state.category) params.set("category", state.category);
  const url = state.split === "corpus" ? `/api/corpus?${params}` : `/api/qa/${state.split}?${params}`;
  const r = await fetch(url); const d = await r.json();
  state.total = d.total;
  if (d.items.length === 0) { listEl.innerHTML = '<div class="empty">Không có kết quả</div>'; }
  else {
    listEl.innerHTML = d.items.map(item => {
      if (state.split === "corpus") {
        return `<div class="row" data-id="${item.oid}">
          <div class="meta">#${item.oid} · ${esc(item.dataset)}</div>
          <div class="preview">${esc(truncate(item.text, 220))}</div></div>`;
      }
      return `<div class="row" data-id="${item.questionoid}">
        <div class="meta">#${item.questionoid}${item.category?.length ? " · " + item.category.map(esc).join(", ") : ""}</div>
        <div class="preview"><b>${esc(truncate(item.question, 160))}</b><br>${esc(truncate(item.answer, 160))}</div></div>`;
    }).join("");
    listEl.querySelectorAll(".row").forEach(row => row.onclick = () => loadDetail(row.dataset.id));
  }
  const pages = Math.max(1, Math.ceil(state.total / state.pageSize));
  document.getElementById("pageInfo").textContent = `Trang ${state.page}/${pages} · ${state.total.toLocaleString()} kết quả`;
  document.getElementById("prev").disabled = state.page <= 1;
  document.getElementById("next").disabled = state.page >= pages;
}

async function loadDetail(id) {
  const detailEl = document.getElementById("detail");
  detailEl.innerHTML = '<div class="empty">Đang tải...</div>';
  if (state.split === "corpus") {
    const r = await fetch(`/api/corpus/${id}`); const d = await r.json();
    detailEl.innerHTML = `<h2>#${d.oid} <span class="badge">${esc(d.dataset)}</span></h2>
      <div class="ctx">${esc(d.text)}</div>`;
    return;
  }
  const r = await fetch(`/api/qa/${state.split}/${id}`); const d = await r.json();
  detailEl.innerHTML = `
    <h2>${esc(d.question)}</h2>
    ${(d.category || []).map(c => `<span class="badge">${esc(c)}</span>`).join("")}
    <h3>Trả lời ngắn</h3><div class="ctx">${esc(d.answer)}</div>
    ${d.long_answer ? `<h3>Trả lời chi tiết</h3><div class="ctx">${esc(d.long_answer)}</div>` : ""}
    <h3>Ngữ cảnh (context)</h3>
    ${(d.context || []).map(c => `<div class="ctx">${esc(c)}</div>`).join("")}
    ${d.linked_corpus.length ? `<h3>Corpus liên kết (contextoid)</h3>` +
      d.linked_corpus.map(c => `<div class="ctx"><div class="meta" style="margin-bottom:4px;">#${c.oid} · ${esc(c.dataset)}</div>${esc(c.text)}</div>`).join("") : ""}
    ${d.reference?.length ? `<h3>Tham chiếu</h3>` + d.reference.map(r => `<div>${esc(r)}</div>`).join("") : ""}
    ${d.url ? `<h3>Nguồn</h3><a href="${esc(d.url)}" target="_blank" rel="noopener">${esc(d.url)}</a>` : ""}
  `;
}

async function loadCategoryChips() {
  const chipsEl = document.getElementById("catChips");
  if (state.split === "corpus") { chipsEl.innerHTML = ""; return; }
  const q = document.getElementById("catQ").value.trim();
  const active = state.category
    ? `<span class="chip active" data-cat="">${esc(state.category)} <span class="x">✕</span></span>` : "";
  if (!q && !state.category) { chipsEl.innerHTML = ""; return; }
  const r = await fetch(`/api/categories/${state.split}?${new URLSearchParams({ q, limit: 20 })}`);
  const d = await r.json();
  const suggestions = d.items
    .filter(it => it.category !== state.category)
    .map(it => `<span class="chip" data-cat="${esc(it.category)}">${esc(it.category)} (${it.count.toLocaleString()})</span>`)
    .join("");
  chipsEl.innerHTML = active + suggestions;
  chipsEl.querySelectorAll(".chip").forEach(chip => {
    chip.onclick = () => {
      state.category = chip.dataset.cat; // "" clears when clicking the active chip
      state.page = 1;
      document.getElementById("catQ").value = "";
      loadCategoryChips();
      loadList();
    };
  });
}

let catDebounce;
document.getElementById("catQ").addEventListener("input", () => {
  clearTimeout(catDebounce);
  catDebounce = setTimeout(loadCategoryChips, 200);
});

document.querySelectorAll(".tab").forEach(tab => {
  tab.onclick = () => {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    state.split = tab.dataset.split; state.page = 1; state.category = "";
    document.getElementById("catQ").value = "";
    document.getElementById("catbar").classList.toggle("show", state.split !== "corpus");
    document.getElementById("detail").innerHTML = '<div class="empty">Chọn một dòng để xem chi tiết</div>';
    loadCategoryChips();
    loadList();
  };
});
document.getElementById("searchBtn").onclick = () => { state.q = document.getElementById("q").value.trim(); state.page = 1; loadList(); };
document.getElementById("q").addEventListener("keydown", e => { if (e.key === "Enter") document.getElementById("searchBtn").click(); });
document.getElementById("prev").onclick = () => { if (state.page > 1) { state.page--; loadList(); } };
document.getElementById("next").onclick = () => { state.page++; loadList(); };

loadMeta();
loadList();
</script>
</body>
</html>
"""
