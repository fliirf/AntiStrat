"""Opponent reports for a target team (default: Cloud9 main roster, VCT opponents).

Writes aggregate JSON only (shares, counts, accuracies), safe to commit and deploy.
"""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from antistrat.adaptation import team_adaptation
from antistrat.callsheet import map_call_sheet, opponent_traits
from antistrat.edges import confident_read, find_edges, team_specific_gain, timing
from antistrat.liveread import leaks, map_live_read, sim_calibration
from antistrat.sim import Assumptions, impact as sim_impact
from antistrat.scouting import op_profile, op_rounds, op_validation, util_bounds, util_map
from antistrat.sites import load_centers
from antistrat.model import FEATURE_SETS, _clf

PRIOR_WEIGHT = 30.0  # walk-forward: a team's own site mix barely beats the map's, so shrink hard
MIN_TELL_N = 5
MIN_TARGET_GAMES = 3  # only scout maps the target team actually plays


def load_team_names(data_dir: Path) -> dict[str, str]:
    path = data_dir / "meta" / "teams.csv"
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {r["team_id"]: r["name"] for r in csv.DictReader(f) if r.get("title", "val") == "val"}


def oof_predictions(df: pd.DataFrame, map_name: str, folds: int = 5) -> pd.DataFrame:
    """Out-of-fold site predictions (grouped by series) so per-team accuracy is honest."""
    d = df[(df["map"] == map_name) & df["site"].notna()].copy()
    sites = sorted(d["site"].unique())
    groups = d["series"].astype(str)
    k = min(folds, groups.nunique())
    for name, cols in FEATURE_SETS.items():
        pred = pd.Series(index=d.index, dtype=object)
        prob = pd.Series(index=d.index, dtype=float)
        if k >= 2:
            for tr, te in GroupKFold(n_splits=k).split(d, groups=groups):
                m = _clf().fit(d.iloc[tr][cols].astype(float), d.iloc[tr]["site"])
                X = d.iloc[te][cols].astype(float)
                pred.iloc[te] = m.predict(X)
                prob.iloc[te] = m.predict_proba(X).max(axis=1)
        d[f"pred_{name}"] = pred
        d[f"prob_{name}"] = prob
    d.attrs["sites"] = sites
    return d


def _mix(s: pd.Series, sites: list[str]) -> dict[str, float]:
    n = len(s)
    return {x: round(float((s == x).sum() / n), 3) if n else 0.0 for x in sites}


def _tells(team_rounds: pd.DataFrame, sites: list[str]) -> list[dict]:
    """Early-round signals followed by a plant on the same site, with hit rate and sample size."""
    base = _mix(team_rounds["site"], sites)
    out = []
    for s in sites:
        for k in (1, 2, 3):
            others = [f"util_aim_{o}" for o in sites if o != s]
            m = (team_rounds[f"util_aim_{s}"] >= k) & (team_rounds[f"util_aim_{s}"] > team_rounds[others].max(axis=1))
            n = int(m.sum())
            if n >= MIN_TELL_N:
                hit = float((team_rounds.loc[m, "site"] == s).mean())
                out.append({"kind": "utility", "site": s, "signal": f"{k}+ early utility aimed at {s}, more than elsewhere",
                            "hit_rate": round(hit, 3), "n": n, "base_rate": base[s]})
        m = team_rounds[f"fk_site_{s}"] == 1
        n = int(m.sum())
        if n >= MIN_TELL_N:
            hit = float((team_rounds.loc[m, "site"] == s).mean())
            out.append({"kind": "first_contact", "site": s, "signal": f"First kill near {s} before the plant",
                        "hit_rate": round(hit, 3), "n": n, "base_rate": base[s]})
    for t in out:
        t["lift"] = round(t["hit_rate"] - t["base_rate"], 3)
    # Keep the most informative per kind/site: high lift, enough rounds.
    out.sort(key=lambda t: t["lift"] * math.log1p(t["n"]), reverse=True)
    seen, best = set(), []
    for t in out:
        if (t["kind"], t["site"]) not in seen and t["lift"] > 0:
            seen.add((t["kind"], t["site"]))
            best.append(t)
    return best[:6]


EDGE_FIELDS = ["kind", "key", "text", "site", "n", "rate", "ref_rate", "lift", "q", "shown"]


def _edges_for(edges: pd.DataFrame, team: str, m: str) -> list[dict]:
    """Shown edges first (strongest first), then the near misses for transparency."""
    if not len(edges):
        return []
    e = edges[(edges["team"] == team) & (edges["map"] == m)].copy()
    e = e[(e["shown"]) | (e["q"] < 0.5)]
    e["score"] = e["lift"].abs() * np.sqrt(e["n"])
    e = e.sort_values(["shown", "score"], ascending=[False, False]).head(12)
    out = []
    for r in e[EDGE_FIELDS].to_dict("records"):
        r["q"] = round(float(r["q"]), 4)
        r["shown"] = bool(r["shown"])
        r["n"] = int(r["n"])
        r["site"] = r["site"] if isinstance(r["site"], str) else None
        out.append(r)
    return out


def build_reports(features: pd.DataFrame, metrics: dict, data_dir: Path, out_dir: Path,
                  target: str = "Cloud9", maps: list[str] | None = None, vct_only: bool = True,
                  min_target_games: int = MIN_TARGET_GAMES, extras: dict | None = None,
                  centers: dict | None = None) -> dict:
    """extras: optional {"kills", "casts", "def_casts"} tables for the Operator and utility sections."""
    names = load_team_names(data_dir)
    extras = extras or {}
    centers = load_centers() if centers is None else centers
    target_ids = {tid for tid, n in names.items() if n == target}
    scope = features[features["is_vct"]] if vct_only else features
    played = scope[scope["att"].isin(target_ids) | scope["dfn"].isin(target_ids)]
    opponents = sorted((set(played["att"]) | set(played["dfn"])) - target_ids)
    if maps is None:
        # Maps where the read beats guessing the usual site and the target plays often enough.
        target_games = played.groupby("map")["game"].nunique()
        maps = sorted(m for m, d in metrics.get("maps", {}).items()
                      if d["contact"]["acc"] > d["baseline_acc"]
                      and target_games.get(m, 0) >= min_target_games)

    adapt = team_adaptation(features)
    oof = {m: oof_predictions(features, m) for m in maps if (features["map"] == m).any()}
    maps_sites = {m: d.attrs["sites"] for m, d in oof.items()}
    edges, edge_summary = find_edges(features, opponents + sorted(target_ids), maps_sites)
    out_dir.mkdir(parents=True, exist_ok=True)
    index = {"target": target, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "scope": "VCT" if vct_only else "all", "metrics": metrics.get("maps", {}),
             "economy": metrics.get("economy", {}), "maps": [], "opponents": [],
             "edge_validation": {**edge_summary,
                                 "team_specific_read": team_specific_gain(features, list(oof), opponents)},
             "map_detail": {m: {"timing": timing(features[features["map"] == m]),
                                "confident_read": {name: confident_read(d[f"pred_{name}"], d[f"prob_{name}"], d["site"])
                                                   for name in FEATURE_SETS}}
                            for m, d in oof.items()},
             "call_sheet": {m: map_call_sheet(features, m, d.attrs["sites"]) for m, d in oof.items()},
             "live_read": {m: map_live_read(features, m) for m in oof},
             "sim_calibration": sim_calibration(features)}
    for m, d in oof.items():  # league readability, to compare the target team against
        index["map_detail"][m]["read_avg"] = {
            name: round(float((d[f"pred_{name}"] == d["site"])[d[f"pred_{name}"].notna()].mean()), 3)
            for name in FEATURE_SETS}
    read_rule = {}
    for m, d in oof.items():
        r = confident_read(d["pred_contact"], d["prob_contact"], d["site"], thresholds=(0.7,))[0]
        read_rule[m] = r
        index["call_sheet"][m]["confident_read"] = r

    kills, casts, dcasts = extras.get("kills"), extras.get("casts"), extras.get("def_casts")
    orounds = op_rounds(features, kills) if kills is not None else None
    if orounds is not None:
        index["op_validation"] = op_validation(orounds, list(oof))
    ubounds = util_bounds(casts, dcasts, features, list(oof)) if casts is not None and dcasts is not None else {}

    if extras.get("positions") is not None:
        from antistrat.impact import measured_presence
        index["sim_calibration"]["measured_presence"] = measured_presence(features, extras["positions"], centers)
    assumptions = Assumptions.from_calibration(index["sim_calibration"])
    assumptions_basis = ("Assumption: moving one defender to the right site is worth a quarter of a first-kill "
                         "swing (measured from all rounds).")

    index["self"] = []  # the target scouted like an opponent: how readable are we?
    for team in opponents + sorted(target_ids):
        entry = {"id": team, "name": names.get(team, team), "maps": []}
        for m, d in oof.items():
            sites = d.attrs["sites"]
            attack = features[(features["att"] == team) & (features["map"] == m)]
            tr = d[d["att"] == team]
            if len(attack) == 0:
                continue
            map_mix = _mix(d["site"], sites)
            counts = {s: int((tr["site"] == s).sum()) for s in sites}
            n = sum(counts.values())
            smooth = {s: round((counts[s] + PRIOR_WEIGHT * map_mix[s]) / (n + PRIOR_WEIGHT), 3) for s in sites}
            read = {}
            for name in FEATURE_SETS:
                col = tr[f"pred_{name}"].dropna()
                read[name] = {"acc": round(float((col == tr.loc[col.index, "site"]).mean()), 3) if len(col) else None,
                              "n": int(len(col))}
            read["baseline"] = {"acc": round(max(map_mix.values()), 3)}
            a = adapt[(adapt["team"] == team) & (adapt["map"] == m)] if len(adapt) else adapt
            adaptation = {"shown": False, "reason": "not statistically significant"}
            if len(a) and bool(a.iloc[0]["significant"]):
                r = a.iloc[0]
                adaptation = {"shown": True, "repeat_after_loss": round(float(r["repeat_after_loss"]), 3),
                              "repeat_after_win": round(float(r["repeat_after_win"]), 3),
                              "n": int(r["n"]), "q": round(float(r["q"]), 4)}
            elif not len(a):
                adaptation["reason"] = "too few consecutive planted rounds"
            report = {
                "team": {"id": team, "name": names.get(team, team)}, "map": m, "target": target,
                "sample": {"attack_rounds": int(len(attack)), "plants": n,
                           "games": int(attack["game"].nunique())},
                "site_mix": _mix(tr["site"], sites), "site_mix_smoothed": smooth, "map_site_mix": map_mix,
                "site_counts": counts, "tells": _tells(tr, sites), "read_accuracy": read,
                "adaptation": adaptation,
                "edges": _edges_for(edges, team, m),
                "traits": opponent_traits(features, team, m, sites),
                "read_rule": read_rule[m],
                "site_mix_note": "Close to the map average: in a walk-forward test, a team's own site mix "
                                 "did not predict its next rounds better than the map's.",
                "timing": timing(attack),
                "confident_read": {name: confident_read(tr[f"pred_{name}"], tr[f"prob_{name}"], tr["site"])
                                   for name in FEATURE_SETS},
                "economy": {"attack_win_rate": round(float((attack["winside"] == "attacker").mean()), 3),
                            "plant_rate": round(n / len(attack), 3)},
            }
            if index["economy"]:
                report["impact"] = {**sim_impact(report, index["economy"], assumptions),
                                    "basis": assumptions_basis}
            if orounds is not None:
                report["operator"] = op_profile(orounds, kills, team, m, centers,
                                                index["op_validation"].get(m, {}).get("stable", False))
            if ubounds:
                report["utility"] = util_map(casts, dcasts, features, team, m, ubounds)
            if team in target_ids:  # anti-read: what gives our own site away
                report["leaks"] = leaks(features, target_ids, m, sites)
            (out_dir / f"{team}_{m}.json").write_text(json.dumps(report, indent=2) + "\n")
            entry["maps"].append(m)
        if entry["maps"]:
            index["self" if team in target_ids else "opponents"].append(entry)
    index["maps"] = sorted({m for o in index["opponents"] for m in o["maps"]})
    (out_dir / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    return index
