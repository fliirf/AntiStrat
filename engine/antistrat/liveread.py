"""Live read from aggregates only: a per-map lookup table of attack-site counts.

An analyst enters what they see (where the attackers' early utility leads, where the first
kill was and who won it) and gets site probabilities. The table holds counts per cell, never
rows, so it can ship with the web app; cells with few rounds back off to coarser keys.
Its accuracy is measured on the newest 20% of series against the gradient-boosted model.
Also: which signals give a team's own site away (anti-read) and the sim calibration anchor.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from antistrat.features import CONTACT_COLS
from antistrat.model import _clf, time_split

MIN_CELL = 20   # rounds needed before a cell is trusted; else back off
MIN_STORE = 10  # cells below this are not written out (they would never be used)
MIN_LEAK_N = 6


def util_key(df: pd.DataFrame, sites: list[str]) -> pd.Series:
    """'A2' = utility leads to A with 2+ casts, 'A1' = one cast, 'none' = no clear lead."""
    aim = df[[f"util_aim_{s}" for s in sites]].to_numpy(float)
    top = aim.argmax(axis=1)
    best = aim.max(axis=1)
    second = np.sort(aim, axis=1)[:, -2] if len(sites) > 1 else np.zeros(len(df))
    lead = (best >= 1) & (best > second)
    return pd.Series([f"{sites[t]}{2 if b >= 2 else 1}" if ok else "none"
                      for t, b, ok in zip(top, best, lead)], index=df.index)


def fk_key(df: pd.DataFrame, sites: list[str]) -> pd.Series:
    """'Ba' = first kill near B won by the attackers, 'Bd' = by the defenders, 'none' = no contact yet."""
    out = pd.Series("none", index=df.index)
    for s in sites:
        m = (df["fk_known"] == 1) & (df[f"fk_site_{s}"] == 1)
        out[m] = s + np.where(df.loc[m, "fk_by_att"] == 1, "a", "d")
    return out


def _keys(u: str, f: str) -> list[str]:
    return [f"{u}|{f}", f"*|{f}", f"{u}|*", "*|*"]


def build_table(d: pd.DataFrame, sites: list[str]) -> dict[str, dict]:
    u, f = util_key(d, sites), fk_key(d, sites)
    cells: dict[str, dict] = {}
    for key_u, key_f in (("u", "f"), ("*", "f"), ("u", "*"), ("*", "*")):
        gu = u if key_u == "u" else pd.Series("*", index=d.index)
        gf = f if key_f == "f" else pd.Series("*", index=d.index)
        for (a, b), g in d.groupby([gu, gf]):
            if len(g) >= MIN_STORE:
                cells[f"{a}|{b}"] = {"n": int(len(g)), "counts": {s: int((g["site"] == s).sum()) for s in sites}}
    return cells


def lookup(cells: dict, u: str, f: str, min_n: int = MIN_CELL) -> tuple[str, dict]:
    for k in _keys(u, f):
        c = cells.get(k)
        if c and c["n"] >= min_n:
            return k, c
    return "*|*", cells["*|*"]


def proba(cell: dict, sites: list[str]) -> np.ndarray:
    c = np.array([cell["counts"][s] for s in sites], float)
    return (c + 1) / (c.sum() + len(sites))


def map_live_read(features: pd.DataFrame, m: str) -> dict:
    """Table from all planted rounds + its accuracy on the newest 20% (table fitted on the older 80%)."""
    d = features[(features["map"] == m) & features["site"].notna()]
    sites = sorted(d["site"].unique())
    train, test = time_split(d)
    cells_tr = build_table(train, sites)
    ut, ft = util_key(test, sites), fk_key(test, sites)
    p = np.array([proba(lookup(cells_tr, a, b)[1], sites) for a, b in zip(ut, ft)])
    pred = np.array(sites)[p.argmax(axis=1)]
    truth = test["site"].to_numpy()
    conf = p.max(axis=1) >= 0.7
    gbm = _clf().fit(train[CONTACT_COLS].astype(float), train["site"])
    gbm_pred = gbm.predict(test[CONTACT_COLS].astype(float))
    base = train["site"].value_counts().idxmax()
    validation = {
        "n_test": int(len(test)),
        "table_acc": round(float((pred == truth).mean()), 3),
        "gbm_acc": round(float((gbm_pred == truth).mean()), 3),
        "baseline_acc": round(float((truth == base).mean()), 3),
        "table_confident": {"min_prob": 0.7, "coverage": round(float(conf.mean()), 3),
                            "acc": round(float((pred[conf] == truth[conf]).mean()), 3) if conf.any() else None},
    }
    return {"sites": sites, "min_cell": MIN_CELL, "cells": build_table(d, sites), "validation": validation}


def leaks(features: pd.DataFrame, team_ids: set[str], m: str, sites: list[str]) -> list[dict]:
    """Signals after which a team's attack site is more predictable than the league's."""
    d = features[(features["map"] == m) & features["site"].notna()]
    u, f = util_key(d, sites), fk_key(d, sites)
    ours = d["att"].isin(team_ids)
    out = []
    for s in sites:
        signals = [(u.isin([f"{s}2"]), f"2+ early utility leads to {s}"),
                   (u.isin([f"{s}1", f"{s}2"]), f"Early utility leads to {s}"),
                   (f == f"{s}a", f"First kill near {s}, won by the attackers"),
                   (f == f"{s}d", f"First kill near {s}, won by the defenders")]
        for mask, text in signals:
            mine = d[mask & ours]
            if len(mine) < MIN_LEAK_N:
                continue
            rate = float((mine["site"] == s).mean())
            league = float((d[mask]["site"] == s).mean())
            out.append({"signal": text, "site": s, "n": int(len(mine)), "rate": round(rate, 3),
                        "league_rate": round(league, 3), "diff": round(rate - league, 3)})
    # Only signals where we are easier to read than the league, biggest gap (weighted by n) first.
    out = [r for r in out if r["diff"] > 0]
    out.sort(key=lambda r: r["diff"] * np.sqrt(r["n"]), reverse=True)
    return out[:5]


def sim_calibration(features: pd.DataFrame) -> dict:
    """Anchor for the match engine: how much one player at the first fight swings a defence round."""
    d = features[features["fk_known"] == 1]
    if d["fk_by_att"].nunique() < 2:
        return {"n": int(len(d)), "extra_defender_value": None}  # cannot measure: engine keeps its defaults
    def_fk = float((d.loc[d["fk_by_att"] == 0, "winside"] == "defender").mean())
    att_fk = float((d.loc[d["fk_by_att"] == 1, "winside"] == "defender").mean())
    swing = def_fk - att_fk
    return {"def_win_after_def_first_kill": round(def_fk, 3), "def_win_after_att_first_kill": round(att_fk, 3),
            "first_kill_swing": round(swing, 3), "n": int(len(d)),
            # A stack or a rotation changes the site fight by about one player for part of the
            # round, so it is credited a quarter of a first-kill swing; a wrong call costs the same.
            "extra_defender_value": round(swing / 4, 3), "rotation_share": 0.75}
