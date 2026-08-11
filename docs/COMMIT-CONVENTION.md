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

`web` (Next.js) · `api` (FastAPI: `app/api`, `app/core`, `app/reasoning`) · `ingest` (`app/ingestion`) · `kg` (Neo4j / `app/knowledge`) · `ontology` (`app/ontology`: tầng chuẩn tắc — parser giữ offset, phân loại vai, trích Compliance Unit) · `db` (Supabase schema/RLS: `supabase/migrations/`) · `eval` (benchmarks) · `design` (handoffs in `design/`) · `docs` · `scripts` · `data` (corpus) · `ci`

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

1. **`main` only ever receives a PR.** Nobody pushes to it directly — see rule 2 for why this changed.
2. **Two long-lived branches, one worktree each**, so the tracks never fight over the same checkout:

   | Track | Branch | Worktree |
   |---|---|---|
   | AI: ontology, KG, ingestion, retrieval, eval | `feat/ai` | `../LexFlow-ai` |
   | Software: API surface, web | `feat/software` | `../LexFlow-sw` |

   ```bash
   git worktree add -b feat/ai ../LexFlow-ai main   # first time only
   ```

   The AI track used to push straight to `main`. That stopped being safe once both tracks ran at
   once: `main` gained commits while `feat/software` had an open PR, the PR merged without the
   branch's later work, and two commits sat stranded until someone noticed. A PR per track makes
   that visible instead of silent.

   **Setting up a worktree** — git only carries tracked files, so also:
   - copy `.env` and `web/.env.local` from an existing checkout;
   - `uv sync`, and `npm install --prefix web` only if the track touches `web/`;
   - link the crawl artefacts, needed to rebuild `data/overlay/lop_phu.json` — `data/raw/vbpl/raw/`
     is gitignored so it exists in exactly one checkout. Link rather than copy, one source of truth:
     ```powershell
     New-Item -ItemType Junction -Path data\raw\vbpl\raw -Target <checkout-khac>\data\raw\vbpl\raw
     ```
     It also un-skips ~52 tests that are guarded on that directory existing.

   Merge back into `main` with a PR when the branch is green. Rebase on `main` before opening the
   PR; **never rebase after pushing** — merge `main` in instead.
3. Before pushing, everything must be green locally: `uv run pytest -q` + `uv run ruff check .` (backend), and `npm run lint` + `npm run build` in `web/` (if web is touched).
4. After pushing, GitHub Actions CI must be green; if it goes red, fix it immediately with a new commit (highest priority).
5. **Never**: `push --force` to `main` · amend/rebase already-pushed commits · `--no-verify` to skip hooks.
6. Never commit secrets — credentials live only in `.env` (gitignored).

## Deploy rules

**Deploy from `main` only, after the PR merges.** Never from a track branch.

`gcloud run deploy --source .` builds the **working directory**, not a git ref. With one worktree
per track, whoever deploys last wins and the other track's work disappears from production with
no error and no warning. The symptom is not obviously a deploy problem either: on 11/08, had the
AI track deployed from its own worktree, uploading a `.json` file in `/admin` would have returned
`422 Extract thất bại: ...` — indistinguishable from a bad crawl file.

```powershell
git -C <worktree-main> pull                # or: git worktree add ../LexFlow-deploy main
uv run pytest -q                           # green before shipping
gcloud run deploy lexflow-api --source . --region asia-southeast1 --allow-unauthenticated `
  --update-env-vars "GIT_SHA=$(git rev-parse --short HEAD)"
```

`--update-env-vars`, never `--set-env-vars`. The latter **replaces the whole list**: the service
carries 16 variables (Gemini, Neo4j, LanceDB, Supabase, Langfuse, `FRONTEND_ORIGIN`) and none of
them live in git, so setting one would drop the other fifteen and take production down.

`GIT_SHA` is what `/health` reports back, so "which commit is production running?" stays a
question with an answer. Deploying without it leaves `commit: "không rõ"` — which is honest, and
is also the sign someone deployed by hand from an unknown tree.

Two things the working directory carries that git does not: **uncommitted files ship too** (check
`git status` first), and a branch that is behind `main` silently rolls production back — check
with `git log HEAD..origin/main` before deploying, expect zero commits.
