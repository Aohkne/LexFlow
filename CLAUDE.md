# LexFlow — Legal Navigator (Hoa Tieu Phap Ly)

- **Commit & push**: follow `docs/COMMIT-CONVENTION.md` (Conventional Commits, messages in English, push rules for main).
- Backend (Python): run tests with `uv run pytest -q`, lint with `uv run ruff check .`.
- Web (Next.js 16): see `web/AGENTS.md` — always read `web/node_modules/next/dist/docs/` before writing web code.
- Key reference docs: `docs/ARCHITECTURE.md`, `docs/ROADMAP-SPRINT.md`, `docs/DESIGN-GAP.md`, `docs/CORPUS.md`.
- **Known-but-unfixed work lives in `docs/TASKLIST.md`** — read it before proposing work, and add an entry there (with the first concrete step) instead of leaving a finding only in chat.
- **Daily worklog**: at the end of a working session, append/update today's entry in `docs/WORKLOG.md` (format described in that file; `/worklog` command automates this).
- **Never commit the SBV-LawGraph dataset or anything derived from it** — the test set (`data/evaluate/svb_graph/sbv_testset_tvpl.json`) comes from the paper authors and needs their permission to redistribute. That includes eval outputs that embed its questions/`reference_answer` (e.g. `eval/results/*bo_sbv*.json`, `judge-sbv-*.json`, `answers-sbv.jsonl`) — all gitignored; regenerate locally, don't track. Analysis/metrics written in your own words (EVAL-IR.md, WORKLOG) are fine.
