# AntiStrat: VALORANT Tactical Manager

Opponent-prep tool for VALORANT coaches, in the spirit of Football Manager. Built for the
**Cloud9 × JetBrains "Sky's the Limit" 2026** hackathon, Category 1 (VALORANT Tactical Scouting).

- **Call sheet:** per-map rules a coach prepares before the match and executes in it: which early utility and
  which first contact mean "rotate", how many seconds there are to react, and when to hold the default.
- **Opponent report:** the traits that stay true about an opponent over time (pace, round 2 after a lost pistol,
  retakes), each with a confidence label.
- **Tactics screen and match engine:** plan every round and see, over thousands of simulated maps, where the plan
  costs win chance.

Scope: Cloud9's VCT 2025 opponents on the 7 maps where the read beats the baseline and Cloud9 played at least 3 times
(Ascent, Corrode, Fracture, Haven, Icebox, Lotus, Pearl). Models train on all rounds (VCT + Game Changers).

### What the data says (and why the product looks like this)
Walk-forward tests on the full dataset showed that a team's own site habits do not predict its next rounds better
than the map average, while the in-round read (early utility, first contact) does, with time to act on it. So the
tool builds per-map rules from the in-round read and limits opponent traits to the ones that held up over time.
Exact figures are shown to judges in the demo and video (GRID license, section 4(b)).

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

## Pipeline (runs on your machine, next to the GRID data)

```bash
cd engine && source .venv/bin/activate
export STL_DATA_DIR=../../stl-hackathon-2026-grid-starter   # default: ../stl-hackathon-2026-grid-starter
python -m antistrat.pipeline extract --limit 5   # quick check on 5 series
python -m antistrat.pipeline all                 # extract -> sites -> features -> train -> report
```

| Step | Reads | Writes |
|---|---|---|
| `extract` | GRID feeds + ability supplement | `../antistrat-out/rounds.csv`, `casts.csv` (GRID data, outside the repo) |
| `sites` | plant positions | `engine/antistrat/data/site_centers.json` (cluster centres only) |
| `features` | rounds, casts, site centres | `../antistrat-out/features.csv` |
| `train` | features | models in `../antistrat-out/models/`, metrics in `engine/antistrat/data/model_metrics.json` |
| `report` | features, models, `meta/teams.csv` | aggregate JSON in `web/public/aggregates/` |

`web/public/aggregates/` is filled by the `report` step on your machine and is git-ignored: everything derived from the
GRID data stays local (license section 3(a)). Without it, `python engine/scripts/make_sample_aggregates.py` writes
synthetic sample data and the UI shows a "Sample data" banner.

### Method in short
- **Sites:** GRID has no site field, so plants are clustered per map (KMeans, 3 sites on Haven and Lotus).
- **Round read:** gradient-boosted classifier on attacker utility in the first 15 s (where it was thrown from and
  which site it was aimed at, from the ability supplement) plus economy; a second model adds the first kill if it
  happened before the plant. Validated on a time split (older 80% train, newer 20% test) against always guessing the
  map's most common site. Per-team accuracy in reports is out-of-fold (grouped by series).
- **Adaptation** between rounds (repeat site after a loss vs a win) is shown only when a Fisher test survives
  Benjamini-Hochberg correction across teams.
- **Call sheet rules** are learned on the older 80% of series per map and re-measured on the newest 20%; a rule that
  falls below 60% there is dropped. **Edges** (situational habits, opponent traits) are discovered on a team's older
  games and kept only when edges of that kind hold their sign on its newer games (`engine/antistrat/edges.py`).
- **Match engine:** Monte Carlo over one map with buy logic and an economy model fitted on loadout values; the coach's
  call per defense round (default, rotate on a confident read, stack a site) shifts win probability by explicit,
  adjustable assumptions (`engine/antistrat/sim.py`).
- **Scope:** reports cover Cloud9's VCT 2025 opponents; the models train on all rounds (VCT + Game Changers).
  A map is trained when it has 300+ planted rounds, and scouted when the read beats the baseline and Cloud9 played it
  at least 3 times in VCT 2025.

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
