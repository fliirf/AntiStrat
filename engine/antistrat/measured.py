"""Measured impact studies (real rounds, no model assumptions about value).

1. Lead time: when does a confident, correct read name the site, versus when do the
   defenders commit to it (from player positions every 2 s)?
2. Headroom: in rounds the read got right, how often were defenders still mostly
   elsewhere at the plant, and how did those rounds end compared with aligned ones?
3. Position at plant: what one more defender near the plant site at the plant is worth,
   holding alive counts and loadouts fixed. This calibrates the match engine.
4. Utility leaks: per ability (and agent), how much early utility aimed at a site raises
   that site's probability, found on older series and re-measured on newer ones.

Every interval is a 95% bootstrap over whole series. Outputs are aggregates; they stay
local (web/public/aggregates is git-ignored) and are never committed.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from antistrat.agents import agent_of
from antistrat.features import aimed_site
from antistrat.model import time_split

NEAR_M = 20.0          # a defender within this many metres of the site centre is "on the site"
CONF = 0.7             # a read counts when its top site probability is at least this
EARLY_READY_S = 15.0   # the early-utility read is complete at 15 s
MIN_LEAK_N = 30
MIN_TEAM_LEAK_N = 12


# ---------- helpers ----------

def _pts(s: str) -> list[tuple[float, float]]:
    return [tuple(map(float, xy.split(","))) for xy in str(s).split(";") if "," in xy]


def _near(pts: list[tuple[float, float]], c: tuple[float, float], m: float = NEAR_M) -> int:
    r2 = (m * 100) ** 2
    return sum((x - c[0]) ** 2 + (y - c[1]) ** 2 <= r2 for x, y in pts)


def bootstrap(d: pd.DataFrame, fn, reps: int = 200, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    groups = [g for _, g in d.groupby("series")]
    est = fn(d)
    draws = []
    for _ in range(reps):
        idx = rng.integers(0, len(groups), len(groups))
        try:
            draws.append(fn(pd.concat([groups[i] for i in idx], ignore_index=True)))
        except (ValueError, ZeroDivisionError):
            continue
    draws = [x for x in draws if x is not None and not (isinstance(x, float) and math.isnan(x))]
    lo, hi = (np.percentile(draws, [2.5, 97.5]) if draws else (np.nan, np.nan))
    return {"est": round(float(est), 4), "lo": round(float(lo), 4), "hi": round(float(hi), 4), "n": int(len(d))}


def _ame(d: pd.DataFrame, col: str, controls: list[str]) -> float:
    """Average change in P(defence wins) when `col` goes up by one, holding the controls and map fixed."""
    maps = sorted(d["map"].unique())
    y = (d["winside"] == "defender").to_numpy(int)

    def X(v):
        return np.column_stack([v, *[d[c].to_numpy(float) for c in controls],
                                *[(d["map"] == m).to_numpy(float) for m in maps[1:]]])
    v = d[col].to_numpy(float)
    lr = LogisticRegression(C=10.0, max_iter=2000).fit(X(v), y)
    return float((lr.predict_proba(X(v + 1))[:, 1] - lr.predict_proba(X(v))[:, 1]).mean())


# ---------- per-round timeline ----------

def round_timeline(features: pd.DataFrame, positions: pd.DataFrame, centers: dict) -> pd.DataFrame:
    """Planted rounds with, per snapshot, defenders alive and near the eventual site."""
    pl = features[features["site"].notna() & features["map"].isin(centers)]
    pl = pl[["series", "game", "round", "map", "site", "plant_t", "fk_t", "fk_known", "winside",
             "att_load", "def_load", "scheduled_start"]]
    p = positions[positions["series"].isin(pl["series"].unique())]
    d = p.merge(pl, on=["series", "game", "round"])
    c = [centers[m][s] for m, s in zip(d["map"], d["site"])]
    dp = [_pts(x) for x in d["def_pos"].fillna("")]
    ap = [_pts(x) for x in d["att_pos"].fillna("")]
    d["def_alive"] = [len(x) for x in dp]
    d["att_alive"] = [len(x) for x in ap]
    d["def_near"] = [_near(x, cc) for x, cc in zip(dp, c)]
    return d.drop(columns=["def_pos", "att_pos"])


def commit_times(tl: pd.DataFrame) -> pd.DataFrame:
    """First second at which defenders commit to the eventual site, two definitions:
    majority: at least half the alive defenders (and 2+) are near the site;
    shift: the count near the site is 2+ higher than at 10 s.
    Rounds that never commit before the plant get NaN (censored at the plant)."""
    s = tl[tl["snap"].str.match(r"^s\d+$")].copy()
    s["t"] = s["snap"].str[1:].astype(float)
    s = s[s["t"] < s["plant_t"]]
    s = s.sort_values(["series", "game", "round", "t"])
    base = s.groupby(["series", "game", "round"])["def_near"].transform("first")
    s["majority"] = (s["def_near"] >= 2) & (s["def_near"] >= np.ceil(s["def_alive"] / 2))
    s["shift"] = (s["def_near"] - base) >= 2
    out = []
    for key, g in s.groupby(["series", "game", "round"]):
        row = dict(zip(["series", "game", "round"], key))
        for k in ("majority", "shift"):
            hit = g.loc[g[k], "t"]
            row[f"commit_{k}"] = float(hit.iloc[0]) if len(hit) else np.nan
        out.append(row)
    return pd.DataFrame(out)


def read_times(oof: pd.DataFrame) -> pd.DataFrame:
    """First second at which a confident read names the eventual site (out-of-fold predictions)."""
    d = oof.copy()
    early_ok = (d["pred_early"] == d["site"]) & (d["prob_early"] >= CONF)
    contact_ok = (d["fk_known"] == 1) & (d["pred_contact"] == d["site"]) & (d["prob_contact"] >= CONF)
    d["read_t"] = np.where(early_ok, EARLY_READY_S, np.where(contact_ok, d["fk_t"], np.nan))
    # A confident read that named another site first is a false alarm, whatever happens later.
    d["false_alarm"] = (d["prob_early"] >= CONF) & (d["pred_early"] != d["site"])
    return d[["series", "game", "round", "read_t", "false_alarm"]]


# ---------- study 1: lead time ----------

def lead_time(features: pd.DataFrame, tl: pd.DataFrame, oof_by_map: dict, reps: int = 200) -> dict:
    reads = pd.concat([read_times(o) for o in oof_by_map.values()], ignore_index=True)
    commits = commit_times(tl)
    planted = features[features["site"].notna()][["series", "game", "round", "map", "plant_t"]]
    d = planted.merge(reads, on=["series", "game", "round"]).merge(commits, on=["series", "game", "round"], how="left")
    out = {"rounds": int(len(d)),
           "confident_correct_share": bootstrap(d, lambda x: float(x["read_t"].notna().mean()), reps),
           "false_alarm_share": bootstrap(d, lambda x: float(x["false_alarm"].mean()), reps)}
    r = d[d["read_t"].notna()].copy()
    for k in ("majority", "shift"):
        c = r[f"commit_{k}"].fillna(r["plant_t"])           # never committed: censored at the plant
        r[f"lead_{k}"] = c - r["read_t"]
        r[f"never_{k}"] = r[f"commit_{k}"].isna()
        out[k] = {
            "median_lead_s": bootstrap(r, lambda x, k=k: float(x[f"lead_{k}"].median()), reps),
            "read_first_share": bootstrap(r, lambda x, k=k: float((x[f"lead_{k}"] > 0).mean()), reps),
            "never_committed_before_plant": bootstrap(r, lambda x, k=k: float(x[f"never_{k}"].mean()), reps),
            # Uncensored: only rounds where the defence did commit before the plant.
            "committed_median_lead_s": bootstrap(r[~r[f"never_{k}"]], lambda x, k=k: float(x[f"lead_{k}"].median()), reps),
            "committed_read_first_share": bootstrap(r[~r[f"never_{k}"]],
                                                    lambda x, k=k: float((x[f"lead_{k}"] > 0).mean()), reps),
            "per_map": {m: {"median_lead_s": round(float(g[f"lead_{k}"].median()), 1),
                            "read_first_share": round(float((g[f"lead_{k}"] > 0).mean()), 3), "n": int(len(g))}
                        for m, g in r.groupby("map")},
        }
    out["read_time_median_s"] = round(float(r["read_t"].median()), 1) if len(r) else None
    out["plant_time_median_s"] = round(float(r["plant_t"].median()), 1) if len(r) else None
    return out


# ---------- studies 2 and 3: at the plant ----------

def at_plant(tl: pd.DataFrame) -> pd.DataFrame:
    p = tl[tl["snap"] == "plant"].dropna(subset=["att_load", "def_load"]).copy()
    p["att_load_k"] = p["att_load"].astype(float) / 1000
    p["def_load_k"] = p["def_load"].astype(float) / 1000
    p["aligned"] = (p["def_near"] >= np.ceil(p["def_alive"] / 2)) & (p["def_near"] >= 1)
    return p[p["def_alive"] > 0]


CONTROLS = ["def_alive", "att_alive", "att_load_k", "def_load_k"]


def headroom(p: pd.DataFrame, reads: pd.DataFrame, reps: int = 200) -> dict:
    d = p.merge(reads, on=["series", "game", "round"])
    d = d[d["read_t"].notna()].copy()           # the read was confident and right
    d["aligned_i"] = d["aligned"].astype(int)
    win = lambda x: float((x["winside"] == "defender").mean())  # noqa: E731
    return {
        "rounds_read_right": int(len(d)),
        "misaligned_share": bootstrap(d, lambda x: float((~x["aligned"]).mean()), reps),
        "def_win_aligned": bootstrap(d[d["aligned"]], win, reps),
        "def_win_misaligned": bootstrap(d[~d["aligned"]], win, reps),
        "aligned_effect_adjusted": bootstrap(d, lambda x: _ame(x, "aligned_i", CONTROLS), reps),
        "note": "Selection: only planted rounds (the attackers already reached the site), and defenders who "
                "are on the site at the plant may have survived because the fight went well. The adjusted "
                "effect holds alive counts and loadouts fixed but is not causal.",
    }


def plant_position_value(p: pd.DataFrame, reps: int = 200) -> dict:
    by = p.assign(k=p["def_near"].clip(upper=3)).groupby("k")
    table = {int(k): {"def_win": round(float((g["winside"] == "defender").mean()), 3), "n": int(len(g))}
             for k, g in by}
    return {"extra_defender_near_site": bootstrap(p, lambda x: _ame(x, "def_near", CONTROLS), reps),
            "by_defenders_near_site": table,
            "controls": "alive defenders, alive attackers, both loadouts, map"}


# ---------- study 4: utility leaks ----------

def utility_leaks(features: pd.DataFrame, casts: pd.DataFrame, centers: dict) -> dict:
    """Per map and ability: P(site | that ability aimed at the site in the first 15 s) vs the base rate.
    Found on the older 80% of series, rate re-measured on the newer 20%."""
    pl = features[features["site"].notna() & features["map"].isin(centers)][
        ["series", "game", "round", "map", "site", "att", "scheduled_start"]]
    c = casts.merge(pl, on=["game", "round"], suffixes=("_c", ""))
    c["aim"] = [aimed_site(x, y, vx, vy, centers[m]) for x, y, vx, vy, m in
                zip(c["x"], c["y"], c["view_x"], c["view_y"], c["map"])]
    c = c.dropna(subset=["aim", "ability"]).drop_duplicates(["game", "round", "ability", "aim"])
    out = {}
    for m, g in c.groupby("map"):
        train, test = time_split(pl[pl["map"] == m])  # per map: map pools rotate over time
        tr_keys, te_keys = set(train["game"]), set(test["game"])
        base_tr = train["site"].value_counts(normalize=True)
        base_te = test["site"].value_counts(normalize=True)
        leaks = []
        for (ab, s), h in g.groupby(["ability", "aim"]):
            tr, te = h[h["game"].isin(tr_keys)], h[h["game"].isin(te_keys)]
            if len(tr) < MIN_LEAK_N:
                continue
            rate = float((tr["site"] == s).mean())
            lift = rate - float(base_tr.get(s, 0))
            if lift <= 0:
                continue
            rate_new = float((te["site"] == s).mean()) if len(te) >= 10 else None
            held = rate_new is not None and rate_new - float(base_te.get(s, 0)) > 0
            leaks.append({"ability": ab, "agent": agent_of(ab), "site": s, "n_older": int(len(tr)),
                          "rate_older": round(rate, 3), "base_older": round(float(base_tr.get(s, 0)), 3),
                          "lift": round(lift, 3), "n_newer": int(len(te)),
                          "rate_newer": round(rate_new, 3) if rate_new is not None else None,
                          "base_newer": round(float(base_te.get(s, 0)), 3), "held": bool(held)})
        leaks.sort(key=lambda r: (r["held"], r["lift"] * math.sqrt(r["n_older"])), reverse=True)
        out[m] = leaks[:12]
    return out


def team_utility_leaks(features: pd.DataFrame, casts: pd.DataFrame, centers: dict, team: str, m: str) -> list[dict]:
    """Same for one attacking team on one map (all its rounds), against the map's base rate."""
    pl = features[(features["map"] == m) & features["site"].notna()][["game", "round", "site", "att"]]
    base = pl["site"].value_counts(normalize=True)
    t = pl[pl["att"] == team]
    c = casts.merge(t, on=["game", "round"])
    if not len(c) or m not in centers:
        return []
    c["aim"] = [aimed_site(x, y, vx, vy, centers[m]) for x, y, vx, vy in zip(c["x"], c["y"], c["view_x"], c["view_y"])]
    c = c.dropna(subset=["aim", "ability"]).drop_duplicates(["game", "round", "ability", "aim"])
    out = []
    for (ab, s), h in c.groupby(["ability", "aim"]):
        if len(h) < MIN_TEAM_LEAK_N:
            continue
        rate = float((h["site"] == s).mean())
        if rate - float(base.get(s, 0)) > 0.1:
            out.append({"ability": ab, "agent": agent_of(ab), "site": s, "n": int(len(h)), "rate": round(rate, 3),
                        "base": round(float(base.get(s, 0)), 3)})
    out.sort(key=lambda r: (r["rate"] - r["base"]) * math.sqrt(r["n"]), reverse=True)
    return out[:5]
