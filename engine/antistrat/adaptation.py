"""Between-round adaptation: does a team change site after losing a round?

Shown only when statistically significant after Benjamini-Hochberg correction across
teams, because in the full data this effect is small and mostly noise.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact


def _pairs(df: pd.DataFrame) -> pd.DataFrame:
    """Consecutive planted attack rounds of the same team in the same game."""
    d = df[df["site"].notna()].sort_values(["game", "att", "round"])
    d = d.assign(prev_site=d.groupby(["game", "att"])["site"].shift(),
                 prev_round=d.groupby(["game", "att"])["round"].shift())
    # Outcome of the immediately preceding round (any round, not just planted ones).
    res = df.assign(att_won=df["winner"] == df["att"])[["game", "att", "round", "att_won"]]
    res = res.rename(columns={"round": "prev_round", "att_won": "prev_won"})
    d = d.merge(res, on=["game", "att", "prev_round"], how="left")
    d = d.dropna(subset=["prev_site", "prev_won"])
    d["repeat"] = d["site"] == d["prev_site"]
    return d


def benjamini_hochberg(p: np.ndarray) -> np.ndarray:
    n = len(p)
    if n == 0:
        return p
    order = np.argsort(p)
    ranked = p[order] * n / (np.arange(n) + 1)
    q = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(q, 1.0)
    return out


def team_adaptation(df: pd.DataFrame, alpha: float = 0.05, min_pairs: int = 10) -> pd.DataFrame:
    """Per (team, map): repeat rate after a loss vs after a win, Fisher p and BH q."""
    pairs = _pairs(df)
    rows = []
    for (team, m), g in pairs.groupby(["att", "map"]):
        if len(g) < min_pairs:
            continue
        lost, won = g[~g["prev_won"].astype(bool)], g[g["prev_won"].astype(bool)]
        table = [[lost["repeat"].sum(), (~lost["repeat"]).sum()],
                 [won["repeat"].sum(), (~won["repeat"]).sum()]]
        p = fisher_exact(table)[1] if len(lost) and len(won) else 1.0
        rows.append({"team": team, "map": m, "n": len(g),
                     "repeat_after_loss": lost["repeat"].mean() if len(lost) else None,
                     "repeat_after_win": won["repeat"].mean() if len(won) else None,
                     "n_after_loss": len(lost), "n_after_win": len(won), "p": p})
    out = pd.DataFrame(rows)
    if len(out):
        out["q"] = benjamini_hochberg(out["p"].to_numpy(float))
        out["significant"] = out["q"] < alpha
    return out
