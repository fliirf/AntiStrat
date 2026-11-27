"""Per-round features for reading the attack site.

Two feature sets, matching what a defender could know at each moment:
- early: attacker utility in the first 15 s + economy (known by ~15 s)
- contact: early + where the first kill happened, if it happened before the plant
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from antistrat.sites import nearest_site



def aimed_site(x, y, vx, vy, centers: dict) -> str | None:
    """Site whose centre lies closest to the caster's aim direction (largest cosine)."""
    if not centers or any(v is None or v != v for v in (x, y, vx, vy)) or (vx == 0 and vy == 0):
        return None
    best, best_cos = None, -2.0
    for s, (cx, cy) in centers.items():
        dx, dy = cx - x, cy - y
        d = (dx * dx + dy * dy) ** 0.5 or 1.0
        cos = (dx * vx + dy * vy) / (d * (vx * vx + vy * vy) ** 0.5)
        if cos > best_cos:
            best, best_cos = s, cos
    return best


def label_sites(rounds: pd.DataFrame, centers: dict) -> pd.Series:
    return rounds.apply(
        lambda r: nearest_site(r["plant_x"], r["plant_y"], centers.get(r["map"], {}))
        if pd.notna(r["plant_x"]) else None, axis=1)


def build_features(rounds: pd.DataFrame, casts: pd.DataFrame, centers: dict) -> pd.DataFrame:
    """One row per round with features, `site` label (None if no plant) and keys."""
    df = rounds.copy()
    df["site"] = label_sites(df, centers)
    key = ["game", "round"]

    c = casts.copy()
    if len(c):
        c = c.merge(df[key + ["map"]], on=key, how="inner")
        c["pos_site"] = [nearest_site(x, y, centers.get(m, {})) for x, y, m in zip(c["x"], c["y"], c["map"])]
        c["aim_site"] = [aimed_site(x, y, vx, vy, centers.get(m, {}))
                         for x, y, vx, vy, m in zip(c["x"], c["y"], c["view_x"], c["view_y"], c["map"])]

    agg = {}
    for (g, r), grp in (c.groupby(key) if len(c) else []):
        row = {"util_n": len(grp), "util_mean_x": grp["x"].mean(), "util_mean_y": grp["y"].mean(),
               "util_first_t": grp["t_rel"].min()}
        for s in "ABC":
            row[f"util_pos_{s}"] = int((grp["pos_site"] == s).sum())
            row[f"util_aim_{s}"] = int((grp["aim_site"] == s).sum())
        agg[(g, r)] = row
    util = pd.DataFrame.from_dict(agg, orient="index")
    if len(util):
        util.index = pd.MultiIndex.from_tuples(util.index, names=key)
        df = df.merge(util.reset_index(), on=key, how="left")
    for col in ["util_n", *[f"util_{k}_{s}" for k in ("pos", "aim") for s in "ABC"]]:
        df[col] = df[col].fillna(0) if col in df else 0
    for col in ["util_mean_x", "util_mean_y", "util_first_t"]:
        if col not in df:
            df[col] = np.nan
    n = df["util_n"].replace(0, np.nan)
    for s in "ABC":
        df[f"util_aim_share_{s}"] = (df[f"util_aim_{s}"] / n).fillna(0)

    # First contact, only if it happened before the plant (otherwise it leaks the answer).
    before = df["fk_t"].notna() & (df["plant_t"].isna() | (df["fk_t"] < df["plant_t"]))
    fk_site = [nearest_site(x, y, centers.get(m, {})) if b else None
               for x, y, m, b in zip(df["fk_x"], df["fk_y"], df["map"], before)]
    for s in "ABC":
        df[f"fk_site_{s}"] = [int(v == s) for v in fk_site]
    df["fk_known"] = before.astype(int)
    df["fk_t_known"] = df["fk_t"].where(before)
    df["fk_by_att"] = ((df["fk_side"] == "attacker") & before).astype(int)
    df["load_diff"] = df["att_load"].astype(float) - df["def_load"].astype(float)
    return df


EARLY_COLS = ["util_n", "util_mean_x", "util_mean_y", "util_first_t",
              *[f"util_{k}_{s}" for k in ("pos", "aim") for s in "ABC"],
              *[f"util_aim_share_{s}" for s in "ABC"], "att_load", "def_load", "load_diff"]
CONTACT_COLS = EARLY_COLS + ["fk_known", "fk_t_known", "fk_by_att", "fk_site_A", "fk_site_B", "fk_site_C"]
