"""Round-read model: predict the attack site from early-round signals.

Validation is a time split (train on older series, test on newer), compared with the
baseline of always guessing the map's most common site. Trained models contain no
raw rows but are fitted on GRID data, so they are saved to OUT_DIR, not the repo.
Only the metrics and aggregate parameters go into the repo.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, log_loss

from antistrat.features import CONTACT_COLS, EARLY_COLS

MVP_MAPS = ["haven", "lotus"]
MIN_MAP_PLANTS = 300  # maps with fewer planted rounds are too thin to train on
FEATURE_SETS = {"early": EARLY_COLS, "contact": CONTACT_COLS}


@dataclass
class MapModel:
    map: str
    sites: list[str]
    models: dict[str, HistGradientBoostingClassifier]

    def predict_proba(self, df: pd.DataFrame, feature_set: str) -> np.ndarray:
        m = self.models[feature_set]
        p = m.predict_proba(df[FEATURE_SETS[feature_set]].astype(float))
        out = np.zeros((len(df), len(self.sites)))
        for j, c in enumerate(m.classes_):
            out[:, self.sites.index(c)] = p[:, j]
        return out


def time_split(df: pd.DataFrame, frac: float = 0.8) -> tuple[pd.DataFrame, pd.DataFrame]:
    order = df.sort_values(["scheduled_start", "series"])
    series = order["series"].drop_duplicates().tolist()
    cut = set(series[: int(len(series) * frac)])
    return order[order["series"].isin(cut)], order[~order["series"].isin(cut)]


def _clf(seed: int = 0) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_depth=4,
                                          l2_regularization=1.0, random_state=seed)


def train_map(df: pd.DataFrame, map_name: str) -> tuple[MapModel, dict]:
    """Train on the older 80%, report metrics on the newer 20%, then refit on all rounds."""
    d = df[(df["map"] == map_name) & df["site"].notna()]
    sites = sorted(d["site"].unique())
    train, test = time_split(d)
    base_site = train["site"].value_counts().idxmax()
    metrics = {"map": map_name, "sites": sites, "n_train": len(train), "n_test": len(test),
               "baseline_acc": round(float((test["site"] == base_site).mean()), 4)}
    models = {}
    for name, cols in FEATURE_SETS.items():
        m = _clf().fit(train[cols].astype(float), train["site"])
        pred = m.predict(test[cols].astype(float))
        proba = m.predict_proba(test[cols].astype(float))
        metrics[name] = {
            "acc": round(float(accuracy_score(test["site"], pred)), 4),
            "log_loss": round(float(log_loss(test["site"], proba, labels=m.classes_)), 4),
            "confusion": confusion_matrix(test["site"], pred, labels=sites).tolist(),
        }
        models[name] = _clf().fit(d[cols].astype(float), d["site"])
    return MapModel(map_name, sites, models), metrics


def train_economy(df: pd.DataFrame) -> dict:
    """P(attackers win round) from loadout values. Used by the match engine."""
    d = df.dropna(subset=["att_load", "def_load", "winside"])
    X = d[["att_load", "def_load"]].astype(float) / 1000.0
    y = (d["winside"] == "attacker").astype(int)
    lr = LogisticRegression().fit(X, y)
    acc = accuracy_score(y, lr.predict(X))
    return {"intercept": float(lr.intercept_[0]), "coef_att_load_k": float(lr.coef_[0][0]),
            "coef_def_load_k": float(lr.coef_[0][1]), "train_acc": round(float(acc), 4),
            "attack_win_rate": round(float(y.mean()), 4), "n": int(len(d))}


def trainable_maps(features: pd.DataFrame, min_plants: int = MIN_MAP_PLANTS) -> list[str]:
    counts = features[features["site"].notna()].groupby("map").size()
    return sorted(m for m, n in counts.items() if m and n >= min_plants)


def train_all(features: pd.DataFrame, out_dir: Path, metrics_path: Path,
              maps: list[str] | None = None, min_plants: int = MIN_MAP_PLANTS) -> dict:
    """Train every map with enough planted rounds (or the given maps)."""
    maps = maps if maps is not None else trainable_maps(features, min_plants)
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {"maps": {}, "economy": train_economy(features)}
    for m in maps:
        if (features["map"] == m).sum() == 0:
            continue
        model, metrics = train_map(features, m)
        joblib.dump(model, out_dir / f"model_{m}.joblib")
        result["maps"][m] = metrics
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text(json.dumps(result, indent=2) + "\n")
    return result


def load_model(out_dir: Path, map_name: str) -> MapModel:
    return joblib.load(out_dir / f"model_{map_name}.joblib")
