"""Extract one row per round from GRID VALORANT feeds.

Based on the team's first prototype. Output contains GRID data, so it is written
to OUT_DIR (outside the repo) and must never be committed.

Usage:
    python -m antistrat.extract.rounds                # all series in $STL_DATA_DIR/val
    python -m antistrat.extract.rounds --limit 5      # quick check on 5 series
"""
from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import os
from datetime import datetime
from pathlib import Path

import zstandard

from antistrat.config import DATA_DIR, OUT_DIR, assert_outside_repo


def _ts(s: str) -> float:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def _players_pos(state: dict, gid: str | None) -> dict:
    out = {}
    for g in state.get("games", []):
        if g.get("id") != gid:
            continue
        for t in g.get("teams", []):
            for p in t.get("players", []):
                pos = p.get("position")
                out[p["id"]] = (
                    t["id"],
                    t.get("side"),
                    pos["x"] if pos else None,
                    pos["y"] if pos else None,
                    p.get("alive"),
                )
    return out


def extract_series(path: Path) -> list[dict]:
    sid = path.name.split("_")[1]
    rows, rolled, mapname = [], set(), {}
    cur = None
    with zstandard.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            env = json.loads(line)
            t = _ts(env["occurredAt"])
            for e in env["events"]:
                ty = e["type"]
                ss = e.get("seriesState") or {}
                gs = ss.get("games") or []
                gid = gs[-1].get("id") if gs else None
                if ty == "series-!started-game":
                    rolled.add(e["target"]["id"])
                    continue
                if ty == "series-started-game" and e.get("includesFullState"):
                    for g in gs:
                        mapname[g["id"]] = (g.get("map") or {}).get("name")
                if ty == "round-ended-freezetime":
                    teams, rn = {}, None
                    for g in gs:
                        if g.get("id") != gid:
                            continue
                        for tm in g.get("teams", []):
                            teams[tm["id"]] = (
                                tm.get("side"),
                                tm.get("loadoutValue"),
                                tm.get("money"),
                                tm.get("score"),
                            )
                        segs = g.get("segments") or []
                        if segs:
                            rn = segs[-1].get("sequenceNumber")
                    cur = {"series": sid, "game": gid, "round": rn, "t0": t, "teams": teams,
                           "plant": None, "fk": None, "winner": None, "wintype": None}
                elif cur is None:
                    continue
                elif ty == "player-completed-plantBomb":
                    pp = _players_pos(ss, gid).get(e["actor"]["id"])
                    cur["plant"] = (round(t - cur["t0"], 1), pp[2] if pp else None, pp[3] if pp else None)
                elif ty == "player-killed-player" and cur["fk"] is None:
                    pos = ((e["target"].get("state") or {}).get("game") or {}).get("position") or {}
                    cur["fk"] = (round(t - cur["t0"], 1), e["actor"]["state"].get("side"),
                                 pos.get("x"), pos.get("y"))
                elif ty == "team-won-round":
                    a = e["actor"]
                    cur["winner"] = a["id"]
                    cur["winside"] = a["state"].get("side")
                    cur["wintype"] = a["state"].get("round", {}).get("winType")
                elif ty == "game-ended-round":
                    if cur["winner"]:
                        rows.append(cur)
                    cur = None

    out = []
    for r in rows:
        if r["game"] in rolled:
            continue
        att = [k for k, v in r["teams"].items() if v[0] == "attacker"]
        dfn = [k for k, v in r["teams"].items() if v[0] == "defender"]
        if not att or not dfn:
            continue
        a, d = att[0], dfn[0]
        plant, fk = r["plant"], r["fk"]
        out.append(dict(
            series=r["series"], game=r["game"], map=mapname.get(r["game"]), round=r["round"],
            att=a, dfn=d, att_load=r["teams"][a][1], def_load=r["teams"][d][1],
            plant_t=plant[0] if plant else None, plant_x=plant[1] if plant else None,
            plant_y=plant[2] if plant else None,
            fk_t=fk[0] if fk else None, fk_side=fk[1] if fk else None,
            fk_x=fk[2] if fk else None, fk_y=fk[3] if fk else None,
            winner=r["winner"], winside=r.get("winside"), wintype=r["wintype"],
        ))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=None, help="only process the first N series")
    ap.add_argument("--out", type=Path, default=OUT_DIR / "rounds.csv")
    args = ap.parse_args()

    files = sorted((DATA_DIR / "val").glob("events_*_grid.jsonl.zst"))[: args.limit]
    if not files:
        raise SystemExit(f"No feeds found in {DATA_DIR / 'val'}; set STL_DATA_DIR")
    out = assert_outside_repo(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    with mp.Pool(os.cpu_count()) as pool:
        rows = [row for series in pool.map(extract_series, files) for row in series]
    if not rows:
        raise SystemExit("No rounds extracted")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rounds from {len(files)} series -> {out}")


if __name__ == "__main__":
    main()
