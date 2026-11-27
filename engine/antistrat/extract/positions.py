"""Defender and attacker positions at first contact and at 20 s, one row per round and snapshot.

Positions come from the player states carried on feed events; the latest known position
per player is kept and dead players are dropped. Output contains GRID data, so it is
written to OUT_DIR (outside the repo) like the other extracts.
"""
from __future__ import annotations

from pathlib import Path

from antistrat.grid import read_jsonl_zst, ts

POSITION_FIELDS = ["series", "game", "round", "snap", "t", "def_pos", "att_pos"]
SNAP_T = 20.0
TIMELINE = tuple(range(10, 102, 2))  # s10, s12, ... until the plant (none after it)


def _update(pos: dict, state: dict, gid: str | None) -> None:
    for g in state.get("games", []) or []:
        if g.get("id") != gid:
            continue
        for tm in g.get("teams", []) or []:
            for p in tm.get("players", []) or []:
                xy = p.get("position")
                if xy and xy.get("x") is not None:
                    pos[p["id"]] = (float(xy["x"]), float(xy["y"]))


def extract_positions(path: Path, timeline: bool = False) -> list[dict]:
    """Snapshots t20 and fk; with timeline=True also every 2 s from 10 s until the plant, and at the plant."""
    sid = path.name.split("_")[1]
    rows, rolled = [], set()
    pos: dict[str, tuple[float, float]] = {}
    cur = None
    for env in read_jsonl_zst(path):
        t = ts(env["occurredAt"])
        for e in env["events"]:
            ty = e["type"]
            ss = e.get("seriesState") or {}
            gs = ss.get("games") or []
            gid = gs[-1].get("id") if gs else (cur or {}).get("game")
            if ty == "series-!started-game":
                rolled.add(e["target"]["id"])
                continue
            if ty == "round-ended-freezetime":
                pos.clear()
                defenders, attackers, rn = [], [], None
                for g in gs:
                    if g.get("id") != gid:
                        continue
                    for tm in g.get("teams", []):
                        ids = [p["id"] for p in tm.get("players", [])]
                        if tm.get("side") == "defender":
                            defenders = ids
                        elif tm.get("side") == "attacker":
                            attackers = ids
                    segs = g.get("segments") or []
                    if segs:
                        rn = segs[-1].get("sequenceNumber")
                cur = {"game": gid, "round": rn, "t0": t, "def": defenders, "att": attackers, "dead": set(), "snaps": {},
                       "planted": False, "next": 0}
            if cur is None:
                continue
            rel = t - cur["t0"]
            if "t20" not in cur["snaps"] and rel >= SNAP_T:
                cur["snaps"]["t20"] = (round(rel, 2), _alive(cur, pos), _alive(cur, pos, "att"))
            while timeline and not cur["planted"] and cur["next"] < len(TIMELINE) and rel >= TIMELINE[cur["next"]]:
                # State as of just before this event: the latest positions at that second.
                cur["snaps"][f"s{TIMELINE[cur['next']]}"] = (float(TIMELINE[cur["next"]]), _alive(cur, pos),
                                                              _alive(cur, pos, "att"))
                cur["next"] += 1
            _update(pos, ss, cur["game"])  # the kill event's own state: positions at the moment of contact
            if ty == "player-completed-plantBomb" and not cur["planted"]:
                cur["planted"] = True
                if timeline:
                    cur["snaps"]["plant"] = (round(rel, 2), _alive(cur, pos), _alive(cur, pos, "att"))
            if ty == "player-killed-player":
                if "fk" not in cur["snaps"]:
                    cur["snaps"]["fk"] = (round(rel, 2), _alive(cur, pos), _alive(cur, pos, "att"))
                cur["dead"].add((e.get("target") or {}).get("id"))
            elif ty == "game-ended-round":
                for snap, (st, dxy, axy) in cur["snaps"].items():
                    rows.append({"series": sid, "game": cur["game"], "round": cur["round"], "snap": snap,
                                 "t": st, "def_pos": _fmt(dxy), "att_pos": _fmt(axy)})
                cur = None
    return [r for r in rows if r["game"] not in rolled]


def _alive(cur: dict, pos: dict, side: str = "def") -> list[tuple[float, float]]:
    return [pos[p] for p in cur[side] if p not in cur["dead"] and p in pos]


def _fmt(xy: list[tuple[float, float]]) -> str:
    return ";".join(f"{x:.0f},{y:.0f}" for x, y in xy)
