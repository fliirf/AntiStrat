# AntiStrat: VALORANT Tactical Manager

Opponent-prep tool for VALORANT coaches, in the spirit of Football Manager. Built for the
**Cloud9 × JetBrains "Sky's the Limit" 2026** hackathon, Category 1 (VALORANT Tactical Scouting).

- **Opponent report:** habits and early-round *tells* (first-15-second utility, first contact) that give away the attack site.
- **Tactics screen:** the coach plans round by round.
- **Match engine:** Monte Carlo simulation of one map (round-read model + economy).

MVP scope: Haven + Lotus, opponents of Cloud9 GC.

## Layout

```
engine/   Python: data pipeline, models, FastAPI
web/      Next.js UI
scripts/  repo checks (data guard)
```

## Data (read this first)

The GRID data is licensed for the hackathon only and **must never be committed**, including
decompressed files and anything extracted from it. Clone it next to this repo, not inside it:

```
hackathon/
├── stl-hackathon-2026-grid-starter/   ← GRID data (never commit)
├── antistrat-out/                     ← pipeline output (default, outside the repo)
└── AntiStrat/                         ← this repo
```

Point the engine at it with `STL_DATA_DIR` (default `../stl-hackathon-2026-grid-starter`).
Only aggregate results are committed or deployed. Before pushing, run `scripts/check-no-data.sh`;
CI runs it on every push and PR.

## Run locally

```bash
# engine
cd engine
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn antistrat.api:app --reload        # http://localhost:8000/health

# web
cd web
npm install
npm run dev                               # http://localhost:3000
```

## License

Code: [MIT](LICENSE). The GRID data is not part of this repository and is under its own license.
