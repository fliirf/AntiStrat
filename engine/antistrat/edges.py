"""Edges a coaching staff can act on, kept only when they hold up.

An "edge" is a situation where one team behaves differently from its own norm (or from
the map norm) by enough to change a call: e.g. "after losing pistol they go B 70%",
"retakes on A against them fail 80%", "they plant before 30 s twice as often as average".

Two safeguards, because per-team samples are small and many situations are tested:
- significance: Fisher exact test per edge, Benjamini-Hochberg across all edges of a kind;
- persistence: for each kind of edge, find edges on a team's older games and check that the
  lift has the same sign on its newer games. Kinds whose edges don't persist are not shown.

Everything returned here is aggregate (rates, counts, medians), safe to commit.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact

from antistrat.adaptation import benjamini_hochberg

MIN_N = 8            # rounds in the situation before an edge is considered
MIN_CHECK_N = 3      # rounds in the newer period to check persistence
DISCOVER_FRAC = 0.6  # older share of a team's games used to discover edges
FAST_PLANT_S = 30.0  # plant this early counts as a fast execute
Q_MAX = 0.2          # BH q threshold for showing an edge
MIN_PERSIST = 0.6    # share of discovered edges that keep their sign in newer games


# ---------------------------------------------------------------- round context

def add_context(df: pd.DataFrame) -> pd.DataFrame:
    """Situation of each round, as the defending coach knows it before the round starts."""
    d = df.copy()
    r = d["round"].astype(float)
    d["half_round"] = np.where(r <= 12, r, np.where(r <= 24, r - 12, np.nan))
    d["pistol"] = d["half_round"] == 1
    hr = d["half_round"]
    d["phase"] = np.select([hr == 1, hr <= 4, hr <= 8, hr <= 12], ["pistol", "early", "mid", "late"], "ot")

    # Buy tier from the attackers' loadout, relative to the map (no item data needed).
    d["buy"] = "pistol"
    for m, g in d[~d["pistol"]].groupby("map"):
        lo, hi = g["att_load"].astype(float).quantile([0.25, 0.5]).to_numpy()
        load = g["att_load"].astype(float)
        d.loc[g.index, "buy"] = np.where(load <= lo, "eco", np.where(load <= hi, "force", "full"))

    # Previous round in the same game, from the attackers' point of view.
    d = d.sort_values(["game", "round"])
    prev = d.groupby("game").shift()
    same_att = prev["att"] == d["att"]
    d["prev_won"] = np.where(prev["winner"].isna(), None,
                             np.where(prev["winner"] == d["att"], "won", "lost"))
    d["prev_site"] = prev["site"].where(same_att)
    d["after_pistol"] = np.where(d["half_round"] == 2, d["prev_won"], None)
    diff = d["att_score"].astype(float) - d["def_score"].astype(float)
    d["score"] = np.select([diff >= 3, diff <= -3], ["ahead", "behind"], "even")
    d["fast"] = d["plant_t"] < FAST_PLANT_S
    return d.sort_index()


# Situations tested for the attackers' site choice: (name, column, value, label)
SITUATIONS = [
    ("pistol", "phase", "pistol", "on pistol rounds"),
    ("eco", "buy", "eco", "on eco rounds"),
    ("force", "buy", "force", "on force buys"),
    ("full", "buy", "full", "on full buys"),
    ("won_pistol", "after_pistol", "won", "in the bonus round after winning pistol"),
    ("lost_pistol", "after_pistol", "lost", "in round 2 after losing pistol"),
    ("prev_won", "prev_won", "won", "after winning the previous round"),
    ("prev_lost", "prev_won", "lost", "after losing the previous round"),
    ("late", "phase", "late", "late in the half (rounds 9-12)"),
    ("behind", "score", "behind", "when behind by 3+"),
    ("ahead", "score", "ahead", "when ahead by 3+"),
]


def _fisher(k1: int, n1: int, k0: int, n0: int) -> float:
    if n1 == 0 or n0 == 0:
        return 1.0
    return float(fisher_exact([[k1, n1 - k1], [k0, n0 - k0]])[1])


def _rate(k: int, n: int) -> float | None:
    return round(k / n, 3) if n else None


# ---------------------------------------------------------------- edge finders
# Each finder takes the rows of one team on one map and returns raw edges:
# {kind, key, n, k, rate, ref_rate, ref_n, lift, p, ...display fields}

def site_edges(team: pd.DataFrame, sites: list[str]) -> list[dict]:
    """Site choice in a situation vs the same team's other planted rounds."""
    planted = team[team["site"].notna()]
    out = []
    for name, col, val, label in SITUATIONS:
        mask = planted[col] == val
        inn, rest = planted[mask], planted[~mask]
        if len(inn) < MIN_N or len(rest) < MIN_N:
            continue
        for s in sites:
            k1, k0 = int((inn["site"] == s).sum()), int((rest["site"] == s).sum())
            rate, ref = k1 / len(inn), k0 / len(rest)
            out.append({"kind": "site", "key": f"{name}:{s}", "situation": name, "site": s,
                        "text": f"{label} they hit {s} {rate:.0%} (otherwise {ref:.0%})",
                        "n": len(inn), "k": k1, "rate": round(rate, 3), "ref_rate": round(ref, 3),
                        "ref_n": len(rest), "lift": round(rate - ref, 3), "p": _fisher(k1, len(inn), k0, len(rest))})
    # Site after losing a round on that site: do they come back or switch?
    pl = planted[planted["prev_site"].notna() & (planted["prev_won"] == "lost")]
    for s in sites:
        inn = pl[pl["prev_site"] == s]
        rest = planted.drop(inn.index)
        if len(inn) < MIN_N:
            continue
        k1, k0 = int((inn["site"] == s).sum()), int((rest["site"] == s).sum())
        rate, ref = k1 / len(inn), k0 / max(len(rest), 1)
        out.append({"kind": "site", "key": f"lost_on:{s}", "situation": f"lost_on_{s}", "site": s,
                    "text": f"after losing a round on {s} they go back to {s} {rate:.0%} (otherwise {ref:.0%})",
                    "n": len(inn), "k": k1, "rate": round(rate, 3), "ref_rate": round(ref, 3),
                    "ref_n": len(rest), "lift": round(rate - ref, 3), "p": _fisher(k1, len(inn), k0, len(rest))})
    return out


def defense_edges(team_def: pd.DataFrame, map_rows: pd.DataFrame, sites: list[str]) -> list[dict]:
    """This team on defense: how often attackers win once they plant on each site (retake
    weakness), and where this team's opening duels happen, vs everyone else on the map."""
    out = []
    others = map_rows.drop(team_def.index)
    for s in sites:
        inn = team_def[team_def["site"] == s]
        ref = others[others["site"] == s]
        if len(inn) >= MIN_N and len(ref) >= MIN_N:
            k1 = int((inn["winside"] == "attacker").sum())
            k0 = int((ref["winside"] == "attacker").sum())
            rate, rr = k1 / len(inn), k0 / len(ref)
            out.append({"kind": "post_plant_def", "key": f"post_plant_def:{s}", "site": s,
                        "text": f"once attackers plant {s} against them, attackers win {rate:.0%} (map {rr:.0%})",
                        "n": len(inn), "k": k1, "rate": round(rate, 3), "ref_rate": round(rr, 3),
                        "ref_n": len(ref), "lift": round(rate - rr, 3), "p": _fisher(k1, len(inn), k0, len(ref))})
        # Attackers' plants on each site against this team vs the map: where they get hit.
        k1 = int((team_def["site"] == s).sum())
        n1 = int(team_def["site"].notna().sum())
        k0 = int((others["site"] == s).sum())
        n0 = int(others["site"].notna().sum())
        if n1 >= MIN_N and n0 >= MIN_N:
            rate, rr = k1 / n1, k0 / n0
            out.append({"kind": "targeted_def", "key": f"targeted_def:{s}", "site": s,
                        "text": f"opponents plant {s} against them {rate:.0%} of the time (map {rr:.0%})",
                        "n": n1, "k": k1, "rate": round(rate, 3), "ref_rate": round(rr, 3), "ref_n": n0,
                        "lift": round(rate - rr, 3), "p": _fisher(k1, n1, k0, n0)})
    # Opening duel won by this team as defender, vs the map.
    fk = team_def[team_def["fk_side"].notna()]
    fko = others[others["fk_side"].notna()]
    if len(fk) >= MIN_N and len(fko) >= MIN_N:
        k1, k0 = int((fk["fk_side"] == "defender").sum()), int((fko["fk_side"] == "defender").sum())
        rate, rr = k1 / len(fk), k0 / len(fko)
        out.append({"kind": "opening_def", "key": "opening_def", "site": None,
                    "text": f"they win the opening duel on defense {rate:.0%} (map {rr:.0%})",
                    "n": len(fk), "k": k1, "rate": round(rate, 3), "ref_rate": round(rr, 3), "ref_n": len(fko),
                    "lift": round(rate - rr, 3), "p": _fisher(k1, len(fk), k0, len(fko))})
    return out


def attack_edges(team_att: pd.DataFrame, map_rows: pd.DataFrame, sites: list[str]) -> list[dict]:
    """This team on attack vs the map: fast executes and post-plant conversion per site."""
    out = []
    others = map_rows.drop(team_att.index)
    p1, p0 = team_att[team_att["plant_t"].notna()], others[others["plant_t"].notna()]
    if len(p1) >= MIN_N and len(p0) >= MIN_N:
        k1, k0 = int(p1["fast"].sum()), int(p0["fast"].sum())
        rate, rr = k1 / len(p1), k0 / len(p0)
        out.append({"kind": "fast", "key": "fast", "site": None,
                    "text": f"they plant before {FAST_PLANT_S:.0f} s in {rate:.0%} of planted rounds (map {rr:.0%})",
                    "n": len(p1), "k": k1, "rate": round(rate, 3), "ref_rate": round(rr, 3), "ref_n": len(p0),
                    "lift": round(rate - rr, 3), "p": _fisher(k1, len(p1), k0, len(p0))})
    # Round 2 after losing pistol: do they force (buy anything) or save?
    r2, r2o = team_att[team_att["after_pistol"] == "lost"], others[others["after_pistol"] == "lost"]
    if len(r2) >= 5 and len(r2o) >= MIN_N:
        k1, k0 = int((r2["buy"] != "eco").sum()), int((r2o["buy"] != "eco").sum())
        rate, rr = k1 / len(r2), k0 / len(r2o)
        out.append({"kind": "force_after_pistol", "key": "force_after_pistol", "site": None,
                    "text": f"after losing pistol they force round 2 {rate:.0%} of the time (map {rr:.0%})",
                    "n": len(r2), "k": k1, "rate": round(rate, 3), "ref_rate": round(rr, 3), "ref_n": len(r2o),
                    "lift": round(rate - rr, 3), "p": _fisher(k1, len(r2), k0, len(r2o))})
    for s in sites:
        inn, ref = team_att[team_att["site"] == s], others[others["site"] == s]
        if len(inn) >= MIN_N and len(ref) >= MIN_N:
            k1, k0 = int((inn["winside"] == "attacker").sum()), int((ref["winside"] == "attacker").sum())
            rate, rr = k1 / len(inn), k0 / len(ref)
            out.append({"kind": "post_plant_att", "key": f"post_plant_att:{s}", "site": s,
                        "text": f"after planting {s} they win {rate:.0%} (map {rr:.0%})",
                        "n": len(inn), "k": k1, "rate": round(rate, 3), "ref_rate": round(rr, 3),
                        "ref_n": len(ref), "lift": round(rate - rr, 3), "p": _fisher(k1, len(inn), k0, len(ref))})
    return out


def _team_map_edges(d: pd.DataFrame, team: str, m: str, sites: list[str]) -> list[dict]:
    mr = d[d["map"] == m]
    att, dfn = mr[mr["att"] == team], mr[mr["dfn"] == team]
    edges = []
    if len(att):
        edges += site_edges(att, sites) + attack_edges(att, mr, sites)
    if len(dfn):
        edges += defense_edges(dfn, mr, sites)
    for e in edges:
        e["team"], e["map"] = team, m
    return edges


# ---------------------------------------------------------------- persistence + selection

def _team_games_split(d: pd.DataFrame, team: str, frac: float = DISCOVER_FRAC) -> tuple[set, set]:
    g = d[(d["att"] == team) | (d["dfn"] == team)][["game", "scheduled_start"]].drop_duplicates("game")
    g = g.sort_values("scheduled_start")["game"].tolist()
    cut = int(len(g) * frac)
    return set(g[:cut]), set(g[cut:])


def persistence(d: pd.DataFrame, teams: list[str], maps_sites: dict[str, list[str]]) -> pd.DataFrame:
    """Discover edges (p < 0.05) on each team's older games; check the sign on its newer games."""
    rows = []
    for team in teams:
        old, new = _team_games_split(d, team)
        if not old or not new:
            continue
        # Team rows from one period; other teams' games stay in both as the map reference.
        neutral = ~d["game"].isin(old | new)
        d_old, d_new = d[d["game"].isin(old) | neutral], d[d["game"].isin(new) | neutral]
        for m, sites in maps_sites.items():
            found = {e["key"]: e for e in _team_map_edges(d_old, team, m, sites) if e["p"] < 0.05}
            if not found:
                continue
            check = {e["key"]: e for e in _team_map_edges(d_new, team, m, sites)}
            for key, e in found.items():
                c = check.get(key)
                if c is None or c["n"] < MIN_CHECK_N:
                    continue
                rows.append({"kind": e["kind"], "team": team, "map": m, "key": key,
                             "lift_discover": e["lift"], "lift_check": c["lift"], "n_check": c["n"],
                             "held": bool(np.sign(c["lift"]) == np.sign(e["lift"]) and c["lift"] != 0)})
    return pd.DataFrame(rows)


def summarize_persistence(p: pd.DataFrame) -> dict:
    out = {}
    if not len(p):
        return out
    for kind, g in p.groupby("kind"):
        out[kind] = {"edges_checked": int(len(g)), "held": round(float(g["held"].mean()), 3),
                     "mean_lift_discover": round(float(g["lift_discover"].abs().mean()), 3),
                     "mean_lift_check_same_sign": round(float((g["lift_check"] * np.sign(g["lift_discover"])).mean()), 3)}
        out[kind]["trusted"] = out[kind]["held"] >= MIN_PERSIST and out[kind]["edges_checked"] >= 5
    return out


def find_edges(features: pd.DataFrame, teams: list[str], maps_sites: dict[str, list[str]]) -> tuple[pd.DataFrame, dict]:
    """All edges for these teams on these maps (full data), with BH q per kind, and the
    persistence summary per kind. Edges get `shown` when significant and of a trusted kind."""
    d = add_context(features)
    edges = [e for t in teams for m, s in maps_sites.items() for e in _team_map_edges(d, t, m, s)]
    df = pd.DataFrame(edges)
    summary = summarize_persistence(persistence(d, teams, maps_sites))
    if len(df):
        df["q"] = 1.0
        for kind, idx in df.groupby("kind").groups.items():
            df.loc[idx, "q"] = benjamini_hochberg(df.loc[idx, "p"].to_numpy(float))
        trusted = {k for k, v in summary.items() if v.get("trusted")}
        df["shown"] = (df["q"] < Q_MAX) & df["kind"].isin(trusted)
    return df, summary


# ---------------------------------------------------------------- timing and confident reads

def timing(rows: pd.DataFrame) -> dict:
    """Medians in seconds after the buy phase: first kill, plant, and the gap between them."""
    fk = rows["fk_t"].dropna()
    pl = rows["plant_t"].dropna()
    both = rows.dropna(subset=["fk_t", "plant_t"])
    both = both[both["fk_t"] < both["plant_t"]]
    gap = both["plant_t"] - both["fk_t"]
    med = lambda s: round(float(s.median()), 1) if len(s) else None  # noqa: E731
    return {"first_kill_s": med(fk), "plant_s": med(pl), "contact_to_plant_s": med(gap),
            "gap_10s_plus": round(float((gap >= 10).mean()), 3) if len(gap) else None,
            "fast_plant_share": round(float((pl < FAST_PLANT_S).mean()), 3) if len(pl) else None,
            "n": int(len(rows))}


def confident_read(pred: pd.Series, proba: pd.Series, truth: pd.Series,
                   thresholds=(0.5, 0.6, 0.7, 0.8)) -> list[dict]:
    """Accuracy and coverage when the model's top site probability is at least a threshold."""
    ok = pred.notna() & proba.notna()
    pred, proba, truth = pred[ok], proba[ok].astype(float), truth[ok]
    out = []
    for th in thresholds:
        m = proba >= th
        n = int(m.sum())
        out.append({"min_prob": th, "coverage": round(n / len(pred), 3) if len(pred) else 0.0,
                    "acc": round(float((pred[m] == truth[m]).mean()), 3) if n else None, "n": n})
    return out


# ---------------------------------------------------------------- does knowing the team help the read?

def team_specific_gain(features: pd.DataFrame, maps: list[str], teams: list[str],
                       min_team_rows: int = 40, prior_weight: float = 20.0, min_test: int = 30) -> dict:
    """Walk-forward (time split 80/20 per map): the generic in-round read vs two ways of adding
    what we know about the attacking team, scored on the newer rounds of the given teams.

    - prior: generic probabilities re-weighted by the team's smoothed site mix / map mix;
    - team_feature: generic features plus a one-hot of the attacking team (teams with
      at least `min_team_rows` older planted rounds on the map).
    """
    from sklearn.metrics import log_loss

    from antistrat.model import FEATURE_SETS, _clf, time_split

    out = {}
    for m in maps:
        d = features[(features["map"] == m) & features["site"].notna()]
        if not len(d):
            continue
        train, test = time_split(d)
        test = test[test["att"].isin(teams)]
        if len(test) < min_test:
            continue
        sites = sorted(d["site"].unique())
        map_mix = train["site"].value_counts(normalize=True).reindex(sites).fillna(0).to_numpy()
        res = {"n_test": int(len(test))}
        for name, cols in FEATURE_SETS.items():
            g = _clf().fit(train[cols].astype(float), train["site"])
            idx = [list(g.classes_).index(s) if s in g.classes_ else None for s in sites]
            P = np.column_stack([g.predict_proba(test[cols].astype(float))[:, i] if i is not None
                                 else np.zeros(len(test)) for i in idx])
            # Prior re-weighting with the team's older rounds only.
            counts = train.groupby("att")["site"].value_counts().unstack(fill_value=0).reindex(columns=sites, fill_value=0)
            W = []
            for t in test["att"]:
                c = counts.loc[t].to_numpy(float) if t in counts.index else np.zeros(len(sites))
                team_mix = (c + prior_weight * map_mix) / (c.sum() + prior_weight)
                W.append(team_mix / np.where(map_mix > 0, map_mix, 1))
            Q = P * np.array(W)
            Q = Q / Q.sum(axis=1, keepdims=True)
            # Team one-hot features.
            big = [t for t, n in train["att"].value_counts().items() if n >= min_team_rows]
            oh = lambda df: pd.concat([df[cols].astype(float)] + [(df["att"] == t).astype(float).rename(f"team_{t}") for t in big], axis=1)  # noqa: E731
            h = _clf().fit(oh(train), train["site"])
            idx_h = [list(h.classes_).index(s) if s in h.classes_ else None for s in sites]
            R = np.column_stack([h.predict_proba(oh(test))[:, i] if i is not None else np.zeros(len(test)) for i in idx_h])
            y = test["site"].to_numpy()

            def score(M):
                M = np.clip(M, 1e-6, 1)
                M = M / M.sum(axis=1, keepdims=True)
                return {"acc": round(float((np.array(sites)[M.argmax(axis=1)] == y).mean()), 4),
                        "log_loss": round(float(log_loss(y, M, labels=sites)), 4)}

            res[name] = {"generic": score(P), "prior": score(Q), "team_feature": score(R)}
        out[m] = res
    return out
