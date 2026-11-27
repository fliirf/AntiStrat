"""Operator profiler and utility placement, per team and map. Aggregates only.

- Operator: how often a team opens rounds with an Operator kill on each side, where its
  defensive Operator opens from, how concentrated the Op is on one player, and whether the
  opening rate held steady between older and newer matches (league-wide split-half check).
- Utility: where a team's early attack utility (first 15 s) and defensive utility (first
  30 s) is cast from, as counts on a coarse grid per map, plus its most used abilities.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from antistrat.sites import nearest_site

OP = "operator"
ZONE_M = 20.0          # an Op kill within this many metres of a site centre counts for that site
GRID = 16              # utility heatmap cells per side
MIN_CELL = 3           # cells with fewer casts are left out (noise, and keeps files small)
MIN_TEAM_ROUNDS = 20


def _rounds(features: pd.DataFrame) -> pd.DataFrame:
    return features[["series", "game", "round", "map", "att", "dfn", "winner", "scheduled_start"]]


def op_rounds(features: pd.DataFrame, kills: pd.DataFrame) -> pd.DataFrame:
    """One row per (round, team, side) with whether the team got the round's first kill with an Op."""
    r = _rounds(features)
    first = kills[kills["first"].astype(str) == "True"][["game", "round", "killer_team", "weapon",
                                                          "killer_x", "killer_y"]]
    r = r.merge(first, on=["game", "round"], how="left")
    rows = []
    for side, col in (("defense", "dfn"), ("attack", "att")):
        x = r.rename(columns={col: "team"}).copy()
        x["side"] = side
        x["op_open"] = (x["killer_team"] == x["team"]) & (x["weapon"] == OP)
        x["won"] = x["winner"] == x["team"]
        rows.append(x[["series", "game", "round", "map", "team", "side", "op_open", "won",
                       "killer_x", "killer_y", "scheduled_start"]])
    return pd.concat(rows, ignore_index=True)


def op_validation(orounds: pd.DataFrame, maps: list[str]) -> dict:
    """Does a team's Op-opening rate hold between its older and newer rounds? (Spearman across teams.)"""
    out = {}
    for m in maps:
        a, b = [], []
        for _, g in orounds[(orounds["map"] == m) & (orounds["side"] == "defense")].groupby("team"):
            if len(g) < 2 * MIN_TEAM_ROUNDS:
                continue
            g = g.sort_values("scheduled_start")
            h = len(g) // 2
            a.append(g["op_open"].iloc[:h].mean())
            b.append(g["op_open"].iloc[h:].mean())
        if len(a) >= 8:
            r, p = stats.spearmanr(a, b)
            out[m] = {"teams": len(a), "r": round(float(r), 3), "p": round(float(p), 4),
                      "stable": bool(r > 0.3 and p < 0.05)}
        else:
            out[m] = {"teams": len(a), "r": None, "p": None, "stable": False}
    return out


def op_profile(orounds: pd.DataFrame, kills: pd.DataFrame, team: str, m: str, centers: dict,
               stable: bool) -> dict | None:
    t = orounds[(orounds["team"] == team) & (orounds["map"] == m)]
    lg = orounds[orounds["map"] == m]
    if len(t) < MIN_TEAM_ROUNDS:
        return None
    sides = {}
    for side in ("defense", "attack"):
        ts_, ls = t[t["side"] == side], lg[lg["side"] == side]
        opens = ts_[ts_["op_open"]]
        sides[side] = {"rounds": int(len(ts_)), "op_open_rate": round(float(ts_["op_open"].mean()), 3),
                       "league_rate": round(float(ls["op_open"].mean()), 3),
                       "win_after_op_open": round(float(opens["won"].mean()), 3) if len(opens) >= 5 else None,
                       "n_op_open": int(len(opens))}
    d = t[(t["side"] == "defense") & t["op_open"]]
    zones = {}
    if len(d):
        r2 = (ZONE_M * 100) ** 2
        c = centers.get(m, {})
        for x, y in zip(d["killer_x"], d["killer_y"]):
            s = nearest_site(x, y, c) if pd.notna(x) else None
            z = s if s and (x - c[s][0]) ** 2 + (y - c[s][1]) ** 2 <= r2 else "mid / other"
            zones[z] = zones.get(z, 0) + 1
        zones = {k: round(v / len(d), 3) for k, v in sorted(zones.items())}
    tk = kills[(kills["killer_team"] == team) & (kills["weapon"] == OP)
               & kills["game"].isin(t["game"].unique())]
    top_share = round(float(tk["killer"].value_counts(normalize=True).iloc[0]), 3) if len(tk) >= 10 else None
    rate, ref = sides["defense"]["op_open_rate"], sides["defense"]["league_rate"]
    conf = "medium" if stable and sides["defense"]["rounds"] >= 40 else "low"
    text = (f"On defence they open {rate:.0%} of rounds with an Operator kill (league {ref:.0%})"
            + (f"; {max(zones, key=zones.get)} is their most common Op opening spot." if zones else "."))
    return {"sides": sides, "def_open_zones": zones, "one_player_share": top_share, "n_op_kills": int(len(tk)),
            "confidence": conf, "text": text}


def _bounds(xy: np.ndarray) -> list[float]:
    lo, hi = np.percentile(xy, [1, 99], axis=0)
    return [round(float(lo[0]), 0), round(float(lo[1]), 0), round(float(hi[0]), 0), round(float(hi[1]), 0)]


def util_bounds(casts: pd.DataFrame, dcasts: pd.DataFrame, features: pd.DataFrame, maps: list[str]) -> dict:
    key = features[["game", "round", "map"]]
    out = {}
    both = pd.concat([casts, dcasts])[["game", "round", "x", "y"]].merge(key, on=["game", "round"])
    for m in maps:
        xy = both[both["map"] == m][["x", "y"]].dropna().to_numpy(float)
        if len(xy) >= 100:
            out[m] = _bounds(xy)
    return out


def _grid(c: pd.DataFrame, b: list[float]) -> dict[str, int]:
    gx = np.clip(((c["x"] - b[0]) / (b[2] - b[0]) * GRID).astype(int), 0, GRID - 1)
    gy = np.clip(((c["y"] - b[1]) / (b[3] - b[1]) * GRID).astype(int), 0, GRID - 1)
    cnt = pd.Series(1, index=pd.MultiIndex.from_arrays([gx, gy])).groupby(level=[0, 1]).sum()
    return {f"{i},{j}": int(v) for (i, j), v in cnt.items() if v >= MIN_CELL}


def util_map(casts: pd.DataFrame, dcasts: pd.DataFrame, features: pd.DataFrame, team: str, m: str,
             bounds: dict) -> dict | None:
    if m not in bounds:
        return None
    rk = features[features["map"] == m][["game", "round", "att", "dfn"]]
    att = casts.merge(rk[rk["att"] == team], on=["game", "round"]).dropna(subset=["x", "y"])
    dfn = dcasts.merge(rk[rk["dfn"] == team], on=["game", "round"]).dropna(subset=["x", "y"])
    out = {"grid": GRID, "bounds": bounds[m]}
    for side, c, rounds in (("attack", att, (rk["att"] == team).sum()), ("defense", dfn, (rk["dfn"] == team).sum())):
        top = c["ability"].value_counts(normalize=True).head(5).round(3).to_dict() if len(c) else {}
        out[side] = {"casts": int(len(c)), "rounds": int(rounds), "cells": _grid(c, bounds[m]) if len(c) else {},
                     "top_abilities": top}
    return out
