"""Data pipeline: GRID feeds -> rounds/casts -> site labels -> features.

Everything written to OUT_DIR contains GRID data and stays outside the repo.
Only site_centers.json (cluster centres) is written inside the repo.

    python -m antistrat.pipeline extract [--limit N]
    python -m antistrat.pipeline sites
    python -m antistrat.pipeline features
    python -m antistrat.pipeline train            # metrics -> antistrat/data/model_metrics.json
    python -m antistrat.pipeline report           # aggregates -> web/public/aggregates/
    python -m antistrat.pipeline all [--limit N]
    python -m antistrat.pipeline positions [--limit N]  # defender positions (local only)
    python -m antistrat.pipeline impact                 # measured value of a defender on site
    python -m antistrat.pipeline extras [--limit N]     # kills with weapons + defender utility (local only)
    python -m antistrat.pipeline sitecheck              # SVG per map to check site letters (local only)
    python -m antistrat.pipeline measure                # measured impact studies (needs positions; run before report)
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import os
from pathlib import Path

import numpy as np
import pandas as pd

from antistrat.config import AGGREGATES_DIR, DATA_DIR, OUT_DIR, assert_outside_repo
from antistrat.extract.rounds import ROUND_FIELDS, extract_series
from antistrat.extract.utility import CAST_FIELDS, extract_casts
from antistrat.features import build_features
from antistrat.grid import feed_path, is_vct, read_series_index, supplement_path
from antistrat.model import MIN_MAP_PLANTS, train_all
from antistrat.report import build_reports
from antistrat.sites import CENTERS_PATH, fit_sites, load_centers, save_centers

METRICS_PATH = Path(__file__).parent / "data" / "model_metrics.json"


def _one(args: tuple[str, Path]) -> tuple[list[dict], list[dict]]:
    sid, data_dir = args
    feed = feed_path(sid, data_dir)
    if not feed.exists():
        return [], []
    rounds = extract_series(feed)
    sup = supplement_path(sid, data_dir)
    casts = extract_casts(sup, rounds) if sup.exists() and rounds else []
    return rounds, casts


def extract(data_dir: Path = DATA_DIR, out_dir: Path = OUT_DIR, limit: int | None = None,
            workers: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    out_dir = assert_outside_repo(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    index = read_series_index(data_dir)[:limit]
    meta = {r["series_id"]: r for r in index}
    jobs = [(r["series_id"], data_dir) for r in index]
    if workers == 1:
        results = list(map(_one, jobs))
    else:
        with mp.Pool(workers or os.cpu_count()) as pool:
            results = pool.map(_one, jobs)
    rounds = pd.DataFrame([r for rs, _ in results for r in rs], columns=ROUND_FIELDS)
    casts = pd.DataFrame([c for _, cs in results for c in cs], columns=CAST_FIELDS)
    rounds["event"] = rounds["series"].map(lambda s: meta[s]["event"])
    rounds["scheduled_start"] = rounds["series"].map(lambda s: meta[s]["scheduled_start"])
    rounds["is_vct"] = rounds["event"].map(is_vct)
    rounds.to_csv(out_dir / "rounds.csv", index=False)
    casts.to_csv(out_dir / "casts.csv", index=False)
    print(f"{len(rounds)} rounds, {len(casts)} early attacker casts from {len(index)} series -> {out_dir}")
    return rounds, casts


def _positions_one(args: tuple[str, Path]) -> list[dict]:
    from antistrat.extract.positions import extract_positions
    sid, data_dir = args
    feed = feed_path(sid, data_dir)
    return extract_positions(feed, timeline=True) if feed.exists() else []


def positions(data_dir: Path = DATA_DIR, out_dir: Path = OUT_DIR, limit: int | None = None,
              workers: int | None = None) -> pd.DataFrame:
    from antistrat.extract.positions import POSITION_FIELDS
    out_dir = assert_outside_repo(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = [(r["series_id"], data_dir) for r in read_series_index(data_dir)[:limit]]
    if workers == 1:
        results = list(map(_positions_one, jobs))
    else:
        with mp.Pool(workers or os.cpu_count()) as pool:
            results = pool.map(_positions_one, jobs)
    df = pd.DataFrame([r for rs in results for r in rs], columns=POSITION_FIELDS)
    df.to_csv(out_dir / "positions.csv", index=False)
    print(f"{len(df)} position snapshots from {len(jobs)} series -> {out_dir}")
    return df


DEF_CAST_WINDOW_S = 30.0


def _extras_one(args: tuple[str, Path]) -> tuple[list[dict], list[dict]]:
    from antistrat.extract.kills import extract_kills
    sid, data_dir = args
    feed = feed_path(sid, data_dir)
    if not feed.exists():
        return [], []
    sup = supplement_path(sid, data_dir)
    rounds = extract_series(feed)
    casts = extract_casts(sup, rounds, DEF_CAST_WINDOW_S, side="def") if sup.exists() and rounds else []
    return extract_kills(feed), casts


def extras(data_dir: Path = DATA_DIR, out_dir: Path = OUT_DIR, limit: int | None = None,
           workers: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Kills with weapons (Operator profiler) and defender utility in the first 30 s (utility map)."""
    from antistrat.extract.kills import KILL_FIELDS
    out_dir = assert_outside_repo(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = [(r["series_id"], data_dir) for r in read_series_index(data_dir)[:limit]]
    if workers == 1:
        results = list(map(_extras_one, jobs))
    else:
        with mp.Pool(workers or os.cpu_count()) as pool:
            results = pool.map(_extras_one, jobs)
    kills = pd.DataFrame([k for ks, _ in results for k in ks], columns=KILL_FIELDS)
    dcasts = pd.DataFrame([c for _, cs in results for c in cs], columns=CAST_FIELDS)
    kills.to_csv(out_dir / "kills.csv", index=False)
    dcasts.to_csv(out_dir / "def_casts.csv", index=False)
    print(f"{len(kills)} kills, {len(dcasts)} defender casts from {len(jobs)} series -> {out_dir}")
    return kills, dcasts


def measure(out_dir: Path = OUT_DIR, centers_path: Path = CENTERS_PATH, agg_dir: Path = AGGREGATES_DIR,
            reps: int = 200) -> dict:
    """Measured impact studies -> web/public/aggregates/measured.json (git-ignored, local only)."""
    import json
    from antistrat import measured as ms
    from antistrat.report import oof_predictions
    centers = load_centers(centers_path)
    feats = _features_df(out_dir)
    metrics = json.loads(METRICS_PATH.read_text()) if METRICS_PATH.exists() else {"maps": {}}
    maps = [m for m in metrics.get("maps", {}) if m in centers]
    feats = feats[feats["map"].isin(maps)]
    pos = pd.read_csv(out_dir / "positions.csv", dtype={"series": str, "game": str})
    casts = pd.read_csv(out_dir / "casts.csv", dtype={"series": str, "game": str, "player": str})
    oof = {m: oof_predictions(feats, m) for m in maps}
    tl = ms.round_timeline(feats, pos, centers)
    reads = pd.concat([ms.read_times(o) for o in oof.values()], ignore_index=True)
    p = ms.at_plant(tl)
    result = {"lead_time": ms.lead_time(feats, tl, oof, reps), "headroom": ms.headroom(p, reads, reps),
              "plant_position": ms.plant_position_value(p, reps), "utility_leaks": ms.utility_leaks(feats, casts, centers),
              "definitions": {"near_site_m": ms.NEAR_M, "confident": ms.CONF, "early_read_ready_s": ms.EARLY_READY_S}}
    agg_dir.mkdir(parents=True, exist_ok=True)
    (agg_dir / "measured.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "utility_leaks"}, indent=2))
    return result


def sitecheck(out_dir: Path = OUT_DIR, centers_path: Path = CENTERS_PATH) -> list[Path]:
    from antistrat.sitecheck import draw
    f = _features_df(out_dir)
    paths = draw(f[f["site"].notna()], load_centers(centers_path), assert_outside_repo(out_dir / "site_check"))
    print(f"{len(paths)} maps drawn -> {out_dir / 'site_check'} (local only; open in a browser)")
    return paths


def impact(out_dir: Path = OUT_DIR, centers_path: Path = CENTERS_PATH, reps: int = 200) -> dict:
    """Prints aggregate numbers only; nothing is written to the repo."""
    import json
    from antistrat.impact import impact_table
    pos = pd.read_csv(out_dir / "positions.csv", dtype={"series": str, "game": str})
    feats = _features_df(out_dir)
    from antistrat.impact import measured_presence
    centers = load_centers(centers_path)
    result = {snap: impact_table(feats, pos, centers, snap, reps) for snap in ("fk", "t20")}
    result["presence_before_contact"] = measured_presence(feats, pos, centers, reps)
    print(json.dumps(result, indent=2))
    return result


def sites(out_dir: Path = OUT_DIR, centers_path: Path = CENTERS_PATH) -> dict:
    rounds = pd.read_csv(out_dir / "rounds.csv", dtype={"series": str, "game": str})
    plants = rounds.dropna(subset=["plant_x", "plant_y"])
    by_map = {m: g[["plant_x", "plant_y"]].to_numpy(float) for m, g in plants.groupby("map")}
    result = fit_sites(by_map)
    save_centers(result, centers_path)
    for m, d in sorted(result.items()):
        print(m, {s: f"{v['plants']} plants, median {v['median_dist_m']} m" for s, v in d["stats"].items()})
    return result


def features(out_dir: Path = OUT_DIR, centers_path: Path = CENTERS_PATH) -> pd.DataFrame:
    rounds = pd.read_csv(out_dir / "rounds.csv", dtype={"series": str, "game": str, "att": str, "dfn": str,
                                                         "winner": str, "att_players": str})
    casts = pd.read_csv(out_dir / "casts.csv", dtype={"series": str, "game": str, "player": str})
    df = build_features(rounds, casts, load_centers(centers_path))
    df.to_csv(out_dir / "features.csv", index=False)
    planted = df["site"].notna()
    print(f"{len(df)} rounds, {planted.sum()} with a plant ({planted.mean():.0%}) -> {out_dir / 'features.csv'}")
    return df


def _features_df(out_dir: Path) -> pd.DataFrame:
    return pd.read_csv(out_dir / "features.csv", dtype={"series": str, "game": str, "att": str, "dfn": str,
                                                        "winner": str, "att_players": str})


def train(out_dir: Path = OUT_DIR, metrics_path: Path = METRICS_PATH, min_plants: int = MIN_MAP_PLANTS) -> dict:
    result = train_all(_features_df(out_dir), out_dir / "models", metrics_path, min_plants=min_plants)
    for m, d in result["maps"].items():
        print(f"{m}: baseline {d['baseline_acc']:.1%}, early {d['early']['acc']:.1%}, "
              f"contact {d['contact']['acc']:.1%} (test n={d['n_test']})")
    print("economy:", result["economy"])
    return result


def report(out_dir: Path = OUT_DIR, data_dir: Path = DATA_DIR, metrics_path: Path = METRICS_PATH,
           agg_dir: Path = AGGREGATES_DIR, target: str = "Cloud9",
           centers_path: Path = CENTERS_PATH, min_target_games: int = 3, vct_only: bool | None = None) -> dict:
    import json
    metrics = json.loads(metrics_path.read_text())
    extras = {}
    for key, name, dt in (("kills", "kills.csv", {"series": str, "game": str, "killer": str, "killer_team": str}),
                          ("casts", "casts.csv", {"series": str, "game": str, "player": str}),
                          ("def_casts", "def_casts.csv", {"series": str, "game": str, "player": str})):
        if (out_dir / name).exists():
            extras[key] = pd.read_csv(out_dir / name, dtype=dt)
    if (agg_dir / "measured.json").exists():
        extras["measured"] = json.loads((agg_dir / "measured.json").read_text())
    else:
        print("note: run `pipeline measure` for measured impact numbers")
    if (out_dir / "positions.csv").exists():
        extras["positions"] = pd.read_csv(out_dir / "positions.csv", dtype={"series": str, "game": str})
    if "kills" not in extras or "def_casts" not in extras:
        print("note: run `pipeline extras` for the Operator and utility sections")
    index = build_reports(_features_df(out_dir), metrics, data_dir, agg_dir, target=target,
                          min_target_games=min_target_games, extras=extras,
                          vct_only=("GC" not in target) if vct_only is None else vct_only,
                          centers=load_centers(centers_path))
    # Site centres (aggregate coordinates) let the UI draw a schematic minimap.
    if centers_path.exists():
        index["sites"] = json.loads(centers_path.read_text())
        (agg_dir / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    print(f"{len(index['opponents'])} opponents of {target} -> {agg_dir}")
    return index


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["extract", "sites", "features", "train", "report", "all", "positions", "impact", "extras", "sitecheck", "measure"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--target", default="Cloud9",
                    help='team whose opponents get reports, e.g. "Cloud9 GC" (GC targets use all events)')
    a = ap.parse_args()
    if a.step in ("extract", "all"):
        extract(limit=a.limit)
    if a.step in ("sites", "all"):
        sites()
    if a.step in ("features", "all"):
        features()
    if a.step in ("train", "all"):
        train()
    if a.step in ("report", "all"):
        report(target=a.target)
    if a.step == "positions":
        positions(limit=a.limit)
    if a.step == "impact":
        impact()
    if a.step == "extras":
        extras(limit=a.limit)
    if a.step == "sitecheck":
        sitecheck()
    if a.step == "measure":
        measure()


if __name__ == "__main__":
    main()
