"""Label bomb sites by clustering plant positions per map.

GRID has no site field, so sites are clusters of plant positions. The cluster centres
(a few coordinates per map) are aggregates and are safe to commit.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans

SITE_COUNTS = {"haven": 3, "lotus": 3}
DEFAULT_SITE_COUNT = 2
CENTERS_PATH = Path(__file__).parent / "data" / "site_centers.json"
LETTERS = "ABC"


def fit_sites(plants: dict[str, np.ndarray], seed: int = 0) -> dict:
    """plants: map -> (n, 2) array of plant x, y. Returns map -> site info."""
    out = {}
    for m, xy in plants.items():
        k = SITE_COUNTS.get(m, DEFAULT_SITE_COUNT)
        if len(xy) < k * 5:
            continue
        km = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(xy)
        # Deterministic letters: order clusters by x, then y. Real site names are
        # assigned in site_names below after checking against the minimap.
        order = sorted(range(k), key=lambda i: (km.cluster_centers_[i][0], km.cluster_centers_[i][1]))
        centers, stats = {}, {}
        for letter, i in zip(LETTERS, order):
            pts = xy[km.labels_ == i]
            c = km.cluster_centers_[i]
            d = np.hypot(pts[:, 0] - c[0], pts[:, 1] - c[1])
            centers[letter] = [round(float(c[0]), 1), round(float(c[1]), 1)]
            stats[letter] = {"plants": int(len(pts)), "median_dist_m": round(float(np.median(d)) / 100, 2)}
        out[m] = {"centers": centers, "stats": stats}
    return out


def save_centers(sites: dict, path: Path = CENTERS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sites, indent=2, sort_keys=True) + "\n")


def load_centers(path: Path = CENTERS_PATH) -> dict[str, dict[str, tuple[float, float]]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {m: {k: tuple(v) for k, v in d["centers"].items()} for m, d in data.items()}


def nearest_site(x: float | None, y: float | None, centers: dict[str, tuple[float, float]]) -> str | None:
    if x is None or y is None or not centers or (isinstance(x, float) and math.isnan(x)):
        return None
    return min(centers, key=lambda s: (centers[s][0] - x) ** 2 + (centers[s][1] - y) ** 2)
