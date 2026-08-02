# Commit & push convention — LexFlow

Applies to every commit in this repo (humans and AI agents). Base standard: [Conventional Commits 1.0.0](https://www.conventionalcommits.org/en/v1.0.0/).

## Message structure

```
<type>(<scope>): <short description>

- detail 1 (body — optional, use when the change touches several points)
- detail 2
```

- **Short description ≤ 72 characters**, imperative mood ("add", not "added").
- **Write messages in English.**
- One commit = one complete unit of work. Do not mix a feature with unrelated reorganizing/formatting.

## Types

| Type | When to use |
|---|---|
| `feat` | new user-facing or API feature |
| `fix` | bug fix |
| `refactor` | code restructure without behavior change |
| `docs` | documentation only (`docs/`, README, comments) |
| `test` | tests only |
| `chore` | housekeeping: dependencies, helper scripts, cleanup |
| `perf` | performance improvement |
| `ci` | GitHub Actions, build/deploy config |
| `style` | formatting, no logic change (rare — linters handle this) |
| `revert` | revert a previous commit |

## Scopes (closed list)

`web` (Next.js) · `api` (FastAPI: `app/api`, `app/core`, `app/reasoning`) · `ingest` (`app/ingestion`) · `kg` (Neo4j / `app/knowledge`) · `ontology` (`app/ontology`: tầng chuẩn tắc — parser giữ offset, phân loại vai, trích Compliance Unit) · `eval` (benchmarks) · `design` (handoffs in `design/`) · `docs` · `scripts` · `data` (corpus) · `ci`

- Change spans multiple scopes → pick the main one; if there is no clear main scope, omit it (`feat: ...`) — and consider splitting the commit.
- Need a new scope → add it to this table in the same commit.

## Breaking changes

Add `!` after type/scope and a `BREAKING CHANGE:` line in the body:

```
feat(api)!: change ChatRequest schema

BREAKING CHANGE: removed `filters` field, clients must switch to `doc_ids`
```

## Examples

```
feat(web): integrate Lexi mascot (handoff v2) - chat avatar, review, favicon, 404
fix(web): compute chapter/section headings with a pure function - passes eslint react-hooks/immutability
chore(scripts): sync anchors into canonical corpus on Storage
docs: update DESIGN-GAP with Lexi section
```

## Push rules

1. **Push directly to `main`** (solo dev). When a teammate joins, switch to branch + PR — update this file then.
2. Before pushing, everything must be green locally: `uv run pytest -q` + `uv run ruff check .` (backend), and `npm run lint` + `npm run build` in `web/` (if web is touched).
3. After pushing, GitHub Actions CI must be green; if it goes red, fix it immediately with a new commit (highest priority).
4. **Never**: `push --force` to `main` · amend/rebase already-pushed commits · `--no-verify` to skip hooks.
5. Never commit secrets — credentials live only in `.env` (gitignored).
