"""Extract one row per round from a GRID VALORANT feed.

The output contains GRID data, so it is written to OUT_DIR (outside the repo).
"""
from __future__ import annotations

from pathlib import Path

from antistrat.grid import read_jsonl_zst, ts

ROUND_FIELDS = [
    "series", "game", "map", "round", "t0", "t_end",
    "att", "dfn", "att_players", "att_load", "def_load", "att_money", "def_money",
    "att_score", "def_score",
    "plant_t", "plant_x", "plant_y",
    "fk_t", "fk_side", "fk_x", "fk_y",
    "winner", "winside", "wintype",
]


def _players_pos(state: dict, gid: str | None) -> dict:
    out = {}
    for g in state.get("games", []):
        if g.get("id") != gid:
            continue
        for t in g.get("teams", []):
            for p in t.get("players", []):
                pos = p.get("position")
                out[p["id"]] = (t["id"], t.get("side"),
                                pos["x"] if pos else None, pos["y"] if pos else None)
    return out


def extract_series(path: Path) -> list[dict]:
    """Rounds of one series. Rolled-back games and rounds without a winner are dropped."""
    sid = path.name.split("_")[1]
    rows, rolled, mapname = [], set(), {}
    cur = None
    for env in read_jsonl_zst(path):
        t = ts(env["occurredAt"])
        for e in env["events"]:
            ty = e["type"]
            ss = e.get("seriesState") or {}
            gs = ss.get("games") or []
            gid = gs[-1].get("id") if gs else None
            if ty == "series-!started-game":
                rolled.add(e["target"]["id"])
                continue
            if e.get("includesFullState"):
                for g in gs:
                    name = (g.get("map") or {}).get("name")
                    if name:
                        mapname[g["id"]] = name
            if ty == "round-ended-freezetime":
                teams, rn = {}, None
                for g in gs:
                    if g.get("id") != gid:
                        continue
                    for tm in g.get("teams", []):
                        teams[tm["id"]] = {
                            "side": tm.get("side"), "load": tm.get("loadoutValue"),
                            "money": tm.get("money"), "score": tm.get("score"),
                            "players": [p["id"] for p in tm.get("players", [])],
                        }
                    segs = g.get("segments") or []
                    if segs:
                        rn = segs[-1].get("sequenceNumber")
                cur = {"series": sid, "game": gid, "round": rn, "t0": t, "teams": teams,
                       "plant": None, "fk": None, "winner": None, "winside": None, "wintype": None}
            elif cur is None:
                continue
            elif ty == "player-completed-plantBomb":
                pp = _players_pos(ss, gid).get(e["actor"]["id"])
                cur["plant"] = (round(t - cur["t0"], 2), pp[2] if pp else None, pp[3] if pp else None)
            elif ty == "player-killed-player" and cur["fk"] is None:
                pos = ((e["target"].get("state") or {}).get("game") or {}).get("position") or {}
                cur["fk"] = (round(t - cur["t0"], 2), (e["actor"].get("state") or {}).get("side"),
                             pos.get("x"), pos.get("y"))
            elif ty == "team-won-round":
                a = e["actor"]
                cur["winner"] = a["id"]
                cur["winside"] = (a.get("state") or {}).get("side")
                cur["wintype"] = ((a.get("state") or {}).get("round") or {}).get("winType")
            elif ty == "game-ended-round":
                if cur["winner"]:
                    cur["t_end"] = t
                    rows.append(cur)
                cur = None

    out = []
    for r in rows:
        if r["game"] in rolled:
            continue
        att = [k for k, v in r["teams"].items() if v["side"] == "attacker"]
        dfn = [k for k, v in r["teams"].items() if v["side"] == "defender"]
        if not att or not dfn:
            continue
        A, D = r["teams"][att[0]], r["teams"][dfn[0]]
        plant, fk = r["plant"], r["fk"]
        out.append({
            "series": r["series"], "game": r["game"], "map": (mapname.get(r["game"]) or "").lower(),
            "round": r["round"], "t0": r["t0"], "t_end": r["t_end"],
            "att": att[0], "dfn": dfn[0], "att_players": ";".join(A["players"]),
            "att_load": A["load"], "def_load": D["load"], "att_money": A["money"], "def_money": D["money"],
            "att_score": A["score"], "def_score": D["score"],
            "plant_t": plant[0] if plant else None, "plant_x": plant[1] if plant else None,
            "plant_y": plant[2] if plant else None,
            "fk_t": fk[0] if fk else None, "fk_side": fk[1] if fk else None,
            "fk_x": fk[2] if fk else None, "fk_y": fk[3] if fk else None,
            "winner": r["winner"], "winside": r["winside"], "wintype": r["wintype"],
        })
    return out
