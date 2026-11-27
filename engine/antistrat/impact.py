"""Measured impact: what one more defender on the site that gets hit is worth.

For each planted round, count defenders within ON_SITE_M of the plant site's centre at
first contact, and model the defence round win with that count, controlling for both
teams' loadouts and the map. The average marginal effect of one more defender, with a
bootstrap interval over series, replaces the match engine's assumed shift size.
Results are aggregate numbers; they are printed or kept local, never committed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

ON_SITE_M = 15.0  # metres from the site centre (positions are in centimetres)


def on_site_counts(pos: pd.Series, sites: pd.Series, maps: pd.Series, centers: dict,
                   radius_m: float = ON_SITE_M) -> tuple[np.ndarray, np.ndarray]:
    """(defenders near the given site, whether the site held the most defenders of any site)."""
    r2 = (radius_m * 100) ** 2
    n_on, heaviest = [], []
    for p, s, m in zip(pos, sites, maps):
        c = centers.get(m, {})
        pts = [tuple(map(float, xy.split(","))) for xy in str(p).split(";") if "," in xy]
        per = {k: sum((x - cx) ** 2 + (y - cy) ** 2 <= r2 for x, y in pts) for k, (cx, cy) in c.items()}
        n = per.get(s, 0)
        n_on.append(n)
        heaviest.append(n > 0 and n == max(per.values()))
    return np.array(n_on), np.array(heaviest)


def _design(d: pd.DataFrame, n: np.ndarray, maps: list[str]) -> np.ndarray:
    cols = [n, d["att_load"].to_numpy(float) / 1000, d["def_load"].to_numpy(float) / 1000]
    cols += [(d["map"] == m).to_numpy(float) for m in maps[1:]]
    return np.column_stack(cols)


def marginal_effect(d: pd.DataFrame, col: str = "n_on") -> float:
    """Average change in P(defence wins) when the count goes up by one, other things equal."""
    maps = sorted(d["map"].unique())
    y = (d["winside"] == "defender").to_numpy(int)
    n = d[col].to_numpy(float)
    lr = LogisticRegression(C=10.0, max_iter=1000).fit(_design(d, n, maps), y)
    p0 = lr.predict_proba(_design(d, n, maps))[:, 1]
    p1 = lr.predict_proba(_design(d, n + 1, maps))[:, 1]
    return float((p1 - p0).mean())


def bootstrap(d: pd.DataFrame, fn, reps: int = 200, seed: int = 0) -> tuple[float, float, float]:
    """Point estimate and 95% interval, resampling whole series."""
    rng = np.random.default_rng(seed)
    groups = {k: g for k, g in d.groupby("series")}
    keys = list(groups)
    est = fn(d)
    draws = []
    for _ in range(reps):
        sample = pd.concat([groups[k] for k in rng.choice(keys, size=len(keys))], ignore_index=True)
        try:
            draws.append(fn(sample))
        except ValueError:
            continue
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return round(est, 4), round(float(lo), 4), round(float(hi), 4)


def impact_table(features: pd.DataFrame, positions: pd.DataFrame, centers: dict, snap: str = "fk",
                 reps: int = 200) -> dict:
    p = positions[positions["snap"] == snap][["series", "game", "round", "def_pos"]]
    d = features[features["site"].notna()].merge(p, on=["series", "game", "round"], how="inner")
    d = d.dropna(subset=["att_load", "def_load"])
    d["n_on"], heavy = on_site_counts(d["def_pos"], d["site"], d["map"], centers)
    d["heaviest"] = heavy.astype(int)
    full = d["att_load"].astype(float) >= d["att_load"].astype(float).median()
    by_n = (d[full].assign(k=d["n_on"].clip(upper=3)).groupby("k")["winside"]
            .agg(lambda s: (s == "defender").mean()).round(3).to_dict())
    counts = d[full].assign(k=d["n_on"].clip(upper=3)).groupby("k").size().to_dict()
    return {
        "snap": snap, "n": int(len(d)), "radius_m": ON_SITE_M,
        "mean_defenders_on_hit_site": round(float(d["n_on"].mean()), 2),
        "extra_defender": bootstrap(d, marginal_effect, reps),
        "right_site_heaviest": bootstrap(d, lambda x: marginal_effect(x, "heaviest"), reps),
        "share_right_site_heaviest": round(float(d["heaviest"].mean()), 3),
        "def_win_by_count_upper_half_buys": {int(k): {"win": v, "n": int(counts[k])} for k, v in by_n.items()},
    }


CONTACT_NEAR_M = 20.0
PRE_CONTACT_S = 22.0  # first kill after this, so the 20 s positions come before the fight


def presence_frame(features: pd.DataFrame, positions: pd.DataFrame, centers: dict) -> pd.DataFrame:
    """Rounds whose first fight was at a site after 22 s, with defenders and attackers within
    CONTACT_NEAR_M of that site at 20 s (before the fight)."""
    from antistrat.sites import nearest_site
    f = features[features["fk_x"].notna() & (features["fk_t"] > PRE_CONTACT_S)
                 & features["map"].isin(centers)].dropna(subset=["att_load", "def_load"])
    p = positions[positions["snap"] == "t20"][["series", "game", "round", "def_pos", "att_pos"]]
    d = f.merge(p, on=["series", "game", "round"])
    d["csite"] = [nearest_site(x, y, centers[m]) for x, y, m in zip(d["fk_x"], d["fk_y"], d["map"])]
    cx = np.array([centers[m][s][0] for m, s in zip(d["map"], d["csite"])])
    cy = np.array([centers[m][s][1] for m, s in zip(d["map"], d["csite"])])
    d = d[np.hypot(d["fk_x"] - cx, d["fk_y"] - cy) <= CONTACT_NEAR_M * 100].copy()
    d["n_on"], _ = on_site_counts(d["def_pos"].fillna(""), d["csite"], d["map"], centers, CONTACT_NEAR_M)
    d["n_att"], _ = on_site_counts(d["att_pos"].fillna(""), d["csite"], d["map"], centers, CONTACT_NEAR_M)
    return d


def presence_effect(d: pd.DataFrame) -> float:
    """Average change in P(defence wins) for one more defender at the contested site, holding attackers there."""
    maps = sorted(d["map"].unique())
    y = (d["winside"] == "defender").to_numpy(int)

    def X(n):
        return np.column_stack([n, d["n_att"].to_numpy(float), d["att_load"].to_numpy(float) / 1000,
                                d["def_load"].to_numpy(float) / 1000,
                                *[(d["map"] == m).to_numpy(float) for m in maps[1:]]])
    n = d["n_on"].to_numpy(float)
    lr = LogisticRegression(C=10.0, max_iter=1000).fit(X(n), y)
    return float((lr.predict_proba(X(n + 1))[:, 1] - lr.predict_proba(X(n))[:, 1]).mean())


def measured_presence(features: pd.DataFrame, positions: pd.DataFrame, centers: dict, reps: int = 100) -> dict:
    d = presence_frame(features, positions, centers)
    est, lo, hi = bootstrap(d, presence_effect, reps)
    return {"extra_defender": est, "ci95": [lo, hi], "n": int(len(d)),
            "design": "defenders within 20 m of the site where the first fight happened, at 20 s and before "
                      "that fight; logistic model with attackers there, both loadouts and the map; "
                      "95% interval from resampling series"}
