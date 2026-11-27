"""Synthetic GRID-like data for tests. Not real data: generated from scratch here."""
from __future__ import annotations

import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import zstandard

SITES = {"haven": {"A": (-3000.0, 2000.0), "B": (0.0, 0.0), "C": (3000.0, 2000.0)},
         "lotus": {"A": (-2500.0, -1500.0), "B": (0.0, 1500.0), "C": (2500.0, -1500.0)}}
SPAWN = (0.0, -5000.0)


def _iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _write_zst(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = "".join(json.dumps(r) + "\n" for r in rows).encode()
    path.write_bytes(zstandard.ZstdCompressor().compress(data))


def make_dataset(root: Path, n_series: int = 12, rounds_per_game: int = 20, seed: int = 1,
                 signal: float = 0.8) -> Path:
    """Write val/series.csv, feeds and supplements under `root`. Returns root."""
    rng = random.Random(seed)
    teams = [f"t{i}" for i in range(1, 5)]
    # Each team prefers one site on attack.
    pref = {t: "ABC"[i % 3] for i, t in enumerate(teams)}
    index = []
    for s in range(n_series):
        sid = str(1000 + s)
        m = ["haven", "lotus"][s % 2]
        a, b = rng.sample(teams, 2)
        event = "VCT Americas - Stage 1 2025" if s % 3 == 0 else "Game Changers NA - Split 1 2025"
        start = datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=s)
        gid = f"g{sid}"
        players = {a: [f"{a}p{i}_{sid}" for i in range(5)], b: [f"{b}p{i}_{sid}" for i in range(5)]}
        envs, sup, seq, t = [], [], 0, start

        def env(events):
            nonlocal seq
            seq += 1
            envs.append({"id": f"e{sid}-{seq}", "occurredAt": _iso(t), "seriesId": sid,
                         "sequenceNumber": seq, "events": events})

        env([{"id": f"ev{sid}-start", "type": "series-started-game", "includesFullState": True,
              "actor": {"type": "series", "id": sid}, "target": {"type": "game", "id": gid},
              "seriesState": {"games": [{"id": gid, "map": {"name": m.capitalize()}, "teams": []}]}}])
        score = {a: 0, b: 0}
        for rn in range(1, rounds_per_game + 1):
            att, dfn = (a, b) if rn <= rounds_per_game // 2 else (b, a)
            t += timedelta(seconds=30)
            site = pref[att] if rng.random() < 0.6 else rng.choice("ABC")
            plant = rng.random() < 0.7

            def team_state(tm, side):
                return {"id": tm, "side": side, "loadoutValue": rng.randint(2000, 4500),
                        "money": rng.randint(0, 9000), "score": score[tm],
                        "players": [{"id": p, "position": {"x": SPAWN[0], "y": SPAWN[1]}} for p in players[tm]]}

            env([{"id": f"ev{sid}-{rn}-fz", "type": "round-ended-freezetime", "includesFullState": True,
                  "actor": {"type": "round", "id": str(rn)}, "target": {"type": "freezetime", "id": "f"},
                  "seriesState": {"games": [{"id": gid, "map": {"name": m.capitalize()},
                                             "segments": [{"sequenceNumber": rn}],
                                             "teams": [team_state(att, "attacker"), team_state(dfn, "defender")]}]}}])
            t0 = t
            # Early utility: mostly aimed at the true site.
            for k in range(rng.randint(2, 6)):
                ct = t0 + timedelta(seconds=rng.uniform(1, 14))
                aim_site = site if rng.random() < signal else rng.choice("ABC")
                tx, ty = SITES[m][aim_site]
                px, py = tx * 0.4 + rng.gauss(0, 300), ty * 0.4 - 2500 + rng.gauss(0, 300)
                vx, vy = tx - px, ty - py
                n = (vx * vx + vy * vy) ** 0.5
                sup.append({"series_id": sid, "game_id": gid, "grid_event_id": f"ab{sid}-{rn}-{k}",
                            "in_grid": True, "occurred_at": _iso(ct), "player_id": rng.choice(players[att]),
                            "ability": "smoke", "slot": "ABILITY_1",
                            "interpolated": {"position": {"x": px, "y": py, "z": 0},
                                             "view": {"x": vx / n, "y": vy / n, "z": 0}},
                            "quality": "ok"})
            # A defender cast and a late attacker cast that must be ignored.
            sup.append({"series_id": sid, "game_id": gid, "grid_event_id": f"abd{sid}-{rn}", "in_grid": True,
                        "occurred_at": _iso(t0 + timedelta(seconds=5)), "player_id": players[dfn][0],
                        "ability": "wall", "interpolated": {"position": {"x": 0, "y": 0, "z": 0},
                                                            "view": {"x": 1, "y": 0, "z": 0}}, "quality": "ok"})
            sup.append({"series_id": sid, "game_id": gid, "grid_event_id": f"abl{sid}-{rn}", "in_grid": True,
                        "occurred_at": _iso(t0 + timedelta(seconds=25)), "player_id": players[att][0],
                        "ability": "flash", "interpolated": {"position": {"x": 0, "y": 0, "z": 0},
                                                             "view": {"x": 1, "y": 0, "z": 0}}, "quality": "ok"})
            # First kill near the site at ~20 s.
            t = t0 + timedelta(seconds=20)
            fx, fy = SITES[m][site]
            env([{"id": f"ev{sid}-{rn}-k", "type": "player-killed-player", "includesFullState": False,
                  "actor": {"type": "player", "id": players[att][0], "state": {"side": "attacker"}},
                  "target": {"type": "player", "id": players[dfn][0],
                             "state": {"game": {"position": {"x": fx + rng.gauss(0, 400), "y": fy + rng.gauss(0, 400)}}}},
                  "seriesState": {"games": [{"id": gid}]}}])
            if plant:
                t = t0 + timedelta(seconds=40)
                px, py = SITES[m][site]
                planter = players[att][1]
                env([{"id": f"ev{sid}-{rn}-p", "type": "player-completed-plantBomb", "includesFullState": True,
                      "actor": {"type": "player", "id": planter}, "target": {"type": "bomb", "id": "b"},
                      "seriesState": {"games": [{"id": gid, "teams": [
                          {"id": att, "side": "attacker", "players": [
                              {"id": planter, "position": {"x": px + rng.gauss(0, 200), "y": py + rng.gauss(0, 200)}}]}]}]}}])
            win = att if rng.random() < 0.5 else dfn
            score[win] += 1
            t = t0 + timedelta(seconds=60)
            env([{"id": f"ev{sid}-{rn}-w", "type": "team-won-round", "includesFullState": False,
                  "actor": {"type": "team", "id": win, "state": {"side": "attacker" if win == att else "defender",
                                                                "round": {"winType": "eliminated"}}},
                  "target": {"type": "round", "id": str(rn)}, "seriesState": {"games": [{"id": gid}]}}])
            env([{"id": f"ev{sid}-{rn}-e", "type": "game-ended-round", "includesFullState": False,
                  "actor": {"type": "game", "id": gid}, "target": {"type": "round", "id": str(rn)},
                  "seriesState": {"games": [{"id": gid}]}}])
        _write_zst(root / "val" / f"events_{sid}_grid.jsonl.zst", envs)
        _write_zst(root / "val-ability-supplements" / f"{sid}.jsonl.zst", sup)
        index.append({"series_id": sid, "event": event, "stage": "Regular Season",
                      "scheduled_start": _iso(start), "teams": f"{a} vs {b}",
                      "file": f"val/events_{sid}_grid.jsonl.zst",
                      "ability_supplement": f"val-ability-supplements/{sid}.jsonl.zst"})
    with open(root / "val" / "series.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(index[0]))
        w.writeheader()
        w.writerows(index)
    meta = root / "meta"
    meta.mkdir(exist_ok=True)
    with open(meta / "teams.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["title", "team_id", "name"])
        for i, tm in enumerate(teams):
            w.writerow(["val", tm, "Cloud9" if i == 0 else f"Team {tm.upper()}"])
    return root
