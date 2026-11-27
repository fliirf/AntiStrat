"""Attacker ability casts in the first seconds of each round, from the ability supplement."""
from __future__ import annotations

import bisect
from collections import defaultdict
from pathlib import Path

from antistrat.grid import read_jsonl_zst, ts

EARLY_WINDOW_S = 15.0

CAST_FIELDS = ["series", "game", "round", "player", "ability", "t_rel",
               "x", "y", "z", "view_x", "view_y", "quality"]


def extract_casts(supplement: Path, rounds: list[dict], window: float = EARLY_WINDOW_S) -> list[dict]:
    """Casts by the attacking team within `window` seconds after freeze time ends."""
    by_game: dict[str, list[dict]] = defaultdict(list)
    for r in rounds:
        by_game[r["game"]].append(r)
    starts = {}
    for g, rs in by_game.items():
        rs.sort(key=lambda r: r["t0"])
        starts[g] = [r["t0"] for r in rs]

    out = []
    for c in read_jsonl_zst(supplement):
        g = c.get("game_id")
        if g not in by_game or c.get("quality") == "missing":
            continue
        t = ts(c["occurred_at"])
        i = bisect.bisect_right(starts[g], t) - 1
        if i < 0:
            continue
        r = by_game[g][i]
        t_rel = t - r["t0"]
        if t_rel > window or t > r["t_end"]:
            continue
        if c.get("player_id") not in r["att_players"].split(";"):
            continue
        interp = c.get("interpolated") or {}
        pos, view = interp.get("position") or {}, interp.get("view") or {}
        if pos.get("x") is None:
            continue
        out.append({
            "series": r["series"], "game": g, "round": r["round"], "player": c["player_id"],
            "ability": c.get("ability"), "t_rel": round(t_rel, 2),
            "x": pos.get("x"), "y": pos.get("y"), "z": pos.get("z"),
            "view_x": view.get("x"), "view_y": view.get("y"), "quality": c.get("quality"),
        })
    return out
