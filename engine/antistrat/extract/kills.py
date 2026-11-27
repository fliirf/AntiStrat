"""Kills with weapon, side and positions, one row per kill (for the Operator profiler).

Output contains GRID data, so it is written to OUT_DIR (outside the repo).
"""
from __future__ import annotations

from pathlib import Path

from antistrat.grid import read_jsonl_zst, ts

KILL_FIELDS = ["series", "game", "round", "t_rel", "killer", "killer_team", "killer_side", "weapon",
               "killer_x", "killer_y", "victim_x", "victim_y", "first"]


def _weapon(actor: dict) -> str | None:
    wk = (((actor.get("stateDelta") or {}).get("round") or {}).get("weaponKills") or {})
    return next(iter(wk), None)


def extract_kills(path: Path) -> list[dict]:
    sid = path.name.split("_")[1]
    rows, rolled, cur = [], set(), None
    team_of: dict[str, tuple[str, str]] = {}
    pos: dict[str, tuple[float, float]] = {}
    for env in read_jsonl_zst(path):
        t = ts(env["occurredAt"])
        for e in env["events"]:
            ty = e["type"]
            gs = (e.get("seriesState") or {}).get("games") or []
            gid = gs[-1].get("id") if gs else (cur or {}).get("game")
            if ty == "series-!started-game":
                rolled.add(e["target"]["id"])
                continue
            for g in gs:
                if g.get("id") != gid:
                    continue
                for tm in g.get("teams", []) or []:
                    for p in tm.get("players", []) or []:
                        xy = p.get("position")
                        if xy and xy.get("x") is not None:
                            pos[p["id"]] = (float(xy["x"]), float(xy["y"]))
            if ty == "round-ended-freezetime":
                team_of.clear()
                rn = None
                for g in gs:
                    if g.get("id") != gid:
                        continue
                    for tm in g.get("teams", []):
                        for p in tm.get("players", []):
                            team_of[p["id"]] = (tm["id"], tm.get("side"))
                    segs = g.get("segments") or []
                    if segs:
                        rn = segs[-1].get("sequenceNumber")
                cur = {"game": gid, "round": rn, "t0": t, "kills": []}
            elif cur is None:
                continue
            elif ty == "player-killed-player":
                kid = e["actor"]["id"]
                team, side = team_of.get(kid, (None, None))
                vpos = ((e["target"].get("state") or {}).get("game") or {}).get("position") or {}
                kx, ky = pos.get(kid, (None, None))
                cur["kills"].append({"series": sid, "game": cur["game"], "round": cur["round"],
                                     "t_rel": round(t - cur["t0"], 2), "killer": kid, "killer_team": team,
                                     "killer_side": side, "weapon": _weapon(e["actor"]),
                                     "killer_x": kx, "killer_y": ky,
                                     "victim_x": vpos.get("x"), "victim_y": vpos.get("y"),
                                     "first": not cur["kills"]})
            elif ty == "game-ended-round":
                rows.extend(cur["kills"])
                cur = None
    return [r for r in rows if r["game"] not in rolled]
