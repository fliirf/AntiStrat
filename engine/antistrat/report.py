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
from antistrat.model import FEATURE_SETS, MVP_MAPS, _clf

PRIOR_WEIGHT = 5.0
MIN_TELL_N = 5


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
        if k >= 2:
            for tr, te in GroupKFold(n_splits=k).split(d, groups=groups):
                m = _clf().fit(d.iloc[tr][cols].astype(float), d.iloc[tr]["site"])
                pred.iloc[te] = m.predict(d.iloc[te][cols].astype(float))
        d[f"pred_{name}"] = pred
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


def build_reports(features: pd.DataFrame, metrics: dict, data_dir: Path, out_dir: Path,
                  target: str = "Cloud9", maps: list[str] = MVP_MAPS, vct_only: bool = True) -> dict:
    names = load_team_names(data_dir)
    target_ids = {tid for tid, n in names.items() if n == target}
    scope = features[features["is_vct"]] if vct_only else features
    played = scope[scope["att"].isin(target_ids) | scope["dfn"].isin(target_ids)]
    opponents = sorted((set(played["att"]) | set(played["dfn"])) - target_ids)

    adapt = team_adaptation(features)
    oof = {m: oof_predictions(features, m) for m in maps if (features["map"] == m).any()}
    out_dir.mkdir(parents=True, exist_ok=True)
    index = {"target": target, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "scope": "VCT" if vct_only else "all", "metrics": metrics.get("maps", {}),
             "economy": metrics.get("economy", {}), "opponents": []}

    for team in opponents:
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
                "economy": {"attack_win_rate": round(float((attack["winside"] == "attacker").mean()), 3),
                            "plant_rate": round(n / len(attack), 3)},
            }
            (out_dir / f"{team}_{m}.json").write_text(json.dumps(report, indent=2) + "\n")
            entry["maps"].append(m)
        if entry["maps"]:
            index["opponents"].append(entry)
    (out_dir / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    return index
