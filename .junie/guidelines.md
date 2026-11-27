# Guidelines for Junie / AI agents working on AntiStrat

## Never commit GRID data
- The GRID data lives outside this repo (`STL_DATA_DIR`, default `../stl-hackathon-2026-grid-starter`).
- Never add `.zst`, `.jsonl`, CSV/Parquet extracts, databases, caches or copies of `meta/` to git.
- Pipeline output goes to `ANTISTRAT_OUT_DIR` (default `../antistrat-out`), never inside the repo.
- Only aggregate results (JSON in `web/public/aggregates/`) may be committed or deployed.
- Before each commit, run `scripts/check-no-data.sh` and stage files by name, not with `git add -A`.

## Project
- `engine/`: Python 3.11+, pandas, scikit-learn, FastAPI. Tests: `cd engine && pytest`.
- `web/`: Next.js (App Router, TypeScript).
- MVP maps: Haven and Lotus. Demo opponents: Cloud9 GC's opponents.
- Read GRID feeds as streams (`zstandard.open(path, "rt")`), never fully decompressed.
- Linear issue keys look like `MUH-12`; put them in branch names and PR titles.
