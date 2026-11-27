# Junie guidelines for AntiStrat

## Project
VALORANT opponent-prep tool. Python (pandas, scikit-learn, FastAPI) in `engine/`,
Next.js in `web/`. See `README.md`.

## Hard rule: GRID data
Never create, copy or commit GRID data or anything extracted from it inside this repo:
no `.zst`, `.jsonl`, `.csv`, `.parquet`, pickles, or `meta/`. The data lives outside the repo
(`STL_DATA_DIR`). Never paste raw events or per-round rows into code, tests, docs or logs.
Tests use small synthetic fixtures. Run `scripts/check-no-data.sh` before finishing.

## Code style
- Python 3.11+, type hints, small pure functions, pytest tests next to new logic.
- Keep the engine importable without the data present.

## At the end of every task: draft an AI workflow log entry
We document how AI helped build this project (see `docs/ai-workflow/README.md`).
When you finish a task that changed code or produced an analysis, create
`docs/ai-workflow/log/<YYYY-MM-DD>-<short-slug>.md` from `docs/ai-workflow/TEMPLATE.md`:
- `tool: Junie`, `who:` leave as the developer who asked, `outcome: accepted`
  (the human will change it if they edit your work).
- Fill *Goal*, *Prompt / instruction* (the task you were given, shortened),
  *What the AI produced* (files and functions you changed, in a short list) and *Result*
  (tests run and their outcome).
- Leave *What we changed and why* and *Lesson* as `TODO (human)`.
- No raw GRID data in the entry; aggregate numbers only.
