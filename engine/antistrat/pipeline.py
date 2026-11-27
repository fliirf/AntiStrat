"""Data pipeline: GRID feeds -> rounds/casts -> site labels -> features.

Everything written to OUT_DIR contains GRID data and stays outside the repo.
Only site_centers.json (cluster centres) is written inside the repo.

    python -m antistrat.pipeline extract [--limit N]
    python -m antistrat.pipeline sites
    python -m antistrat.pipeline features
    python -m antistrat.pipeline train            # metrics -> antistrat/data/model_metrics.json
    python -m antistrat.pipeline report           # aggregates -> web/public/aggregates/
    python -m antistrat.pipeline all [--limit N]
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
from antistrat.model import train_all
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


def train(out_dir: Path = OUT_DIR, metrics_path: Path = METRICS_PATH) -> dict:
    result = train_all(_features_df(out_dir), out_dir / "models", metrics_path)
    for m, d in result["maps"].items():
        print(f"{m}: baseline {d['baseline_acc']:.1%}, early {d['early']['acc']:.1%}, "
              f"contact {d['contact']['acc']:.1%} (test n={d['n_test']})")
    print("economy:", result["economy"])
    return result


def report(out_dir: Path = OUT_DIR, data_dir: Path = DATA_DIR, metrics_path: Path = METRICS_PATH,
           agg_dir: Path = AGGREGATES_DIR, target: str = "Cloud9",
           centers_path: Path = CENTERS_PATH) -> dict:
    import json
    metrics = json.loads(metrics_path.read_text())
    index = build_reports(_features_df(out_dir), metrics, data_dir, agg_dir, target=target)
    # Site centres (aggregate coordinates) let the UI draw a schematic minimap.
    if centers_path.exists():
        index["sites"] = json.loads(centers_path.read_text())
        (agg_dir / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    print(f"{len(index['opponents'])} opponents of {target} -> {agg_dir}")
    return index


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["extract", "sites", "features", "train", "report", "all"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--target", default="Cloud9", help="team whose opponents get reports")
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


if __name__ == "__main__":
    main()
