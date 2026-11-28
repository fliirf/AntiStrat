"""Calibration harness: simulate many maps between evenly matched teams and report the
statistics the GDD 'Kalibrasi' section tracks.

    python -m antistrat.quick.harness                 # tuned params, 2,000 maps
    python -m antistrat.quick.harness --luau          # Luau prototype coefficients
    python -m antistrat.quick.harness --compare       # both, side by side
    python -m antistrat.quick.harness --fit-bias      # refit per-map attack bias into maps.json
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict

from .match import MAPS_FILE, load_maps, play_map
from .model import Team
from .params import Params

# Targets from public pro stats (project brief / GDD). None = reported, not tuned.
TARGETS = {
    "attack_round_win": (0.49, 0.02),
    "round2_conversion": (0.90, 0.03),
    "clutch_rate": (0.155, 0.015),
    "eco_vs_full_win": (0.13, 0.03),
    "postplant_attack_win": (0.68, 0.03),
    "first_blood_conversion": (0.72, 0.03),
}


def _rate(c: Counter, key: str) -> float | None:
    n = c[key + "_n"]
    return round(c[key] / n, 4) if n else None


def run(p: Params, n_maps: int = 2000, seed: int = 1, maps: list[str] | None = None,
        shift_b: float = 0.0) -> dict:
    """Simulate `n_maps` maps between two random teams drawn from the same distribution
    (team B gets `shift_b` added to every attribute). Maps cycle through `maps`."""
    rng = random.Random(seed)
    maps = maps if maps is not None else list(load_maps())
    c: Counter = Counter()
    per_map: dict[str, Counter] = defaultdict(Counter)
    how = Counter()
    for i in range(n_maps):
        m = maps[i % len(maps)] if maps else None
        a = Team.random("A", rng)
        b = Team.random("B", rng, shift=shift_b)
        res = play_map(a, b, m, p, rng, a_attacks_first=rng.random() < 0.5)
        c["maps_n"] += 1
        c["b_map_win"] += res.winner == 1
        c["overtime"] += res.overtime
        prev = None
        for r in res.rounds:
            rr = r.result
            att_won = r.winner == r.attacker
            c["attack_round_win_n"] += 1
            c["attack_round_win"] += att_won
            per_map[m or "-"]["n"] += 1
            per_map[m or "-"]["atk"] += att_won
            c["plant_rate_n"] += 1
            c["plant_rate"] += rr.planted
            how[rr.how] += 1
            if rr.planted:
                c["postplant_attack_win_n"] += 1
                c["postplant_attack_win"] += att_won
            if rr.first_blood:
                fb_team = r.attacker if rr.first_blood == "atk" else 1 - r.attacker
                c["first_blood_conversion_n"] += 1
                c["first_blood_conversion"] += fb_team == r.winner
            for _, _, won in rr.clutches:
                c["clutch_rate_n"] += 1
                c["clutch_rate"] += won
            if r.no in (1, 13):
                c["pistol_attack_win_n"] += 1
                c["pistol_attack_win"] += att_won
            if prev is not None and r.no in (2, 14):
                c["round2_conversion_n"] += 1
                c["round2_conversion"] += r.winner == prev.winner
            if prev is not None and r.no in (3, 15) and r.no - 2 >= 1:
                two_back = res.rounds[r.no - 3]
                if two_back.winner == prev.winner:
                    c["bonus_conversion_n"] += 1
                    c["bonus_conversion"] += r.winner == prev.winner
            for t in (0, 1):
                if r.buys[t] == "eco" and r.buys[1 - t] == "full":
                    c["eco_vs_full_win_n"] += 1
                    c["eco_vs_full_win"] += r.winner == t
            prev = r
    total_rounds = sum(how.values())
    out = {
        "maps": n_maps,
        "attack_round_win": _rate(c, "attack_round_win"),
        "pistol_attack_win": _rate(c, "pistol_attack_win"),
        "plant_rate": _rate(c, "plant_rate"),
        "postplant_attack_win": _rate(c, "postplant_attack_win"),
        "eco_vs_full_win": _rate(c, "eco_vs_full_win"),
        "round2_conversion": _rate(c, "round2_conversion"),
        "bonus_conversion": _rate(c, "bonus_conversion"),
        "first_blood_conversion": _rate(c, "first_blood_conversion"),
        "clutch_rate": _rate(c, "clutch_rate"),
        "overtime_rate": round(c["overtime"] / n_maps, 4),
        "team_b_map_win": round(c["b_map_win"] / n_maps, 4),
        "round_end": {k: round(v / total_rounds, 4) for k, v in sorted(how.items())},
        "attack_by_map": {k: round(v["atk"] / v["n"], 4) for k, v in sorted(per_map.items())},
    }
    return out


def plus_one(p: Params, n_maps: int = 2000, seed: int = 2) -> float:
    """Map win rate of a team whose every attribute is +1 over an otherwise equal opponent."""
    return run(p, n_maps, seed, shift_b=1.0)["team_b_map_win"]


def fit_bias(p: Params, n_maps: int = 1200, iters: int = 5, seed: int = 11, write: bool = True) -> dict:
    """Fit each map's attack_bias so the attack round win rate hits its attack_target."""
    data = json.loads(MAPS_FILE.read_text())
    for m in data["maps"]:
        bias = 0.0
        for it in range(iters):
            m["attack_bias"] = round(bias, 3)
            MAPS_FILE.write_text(json.dumps(data, indent=2) + "\n")
            load_maps.cache_clear()
            obs = run(p, n_maps, seed + it, maps=[m["id"]])["attack_round_win"]
            bias += 1.3 * (m["attack_target"] - obs)   # round rate moves ~0.75 per logit of duel bias
        m["attack_bias"] = round(bias, 3)
    if write:
        MAPS_FILE.write_text(json.dumps(data, indent=2) + "\n")
    load_maps.cache_clear()
    return {m["id"]: m["attack_bias"] for m in data["maps"]}


def report(p: Params, n_maps: int, seed: int) -> dict:
    r = run(p, n_maps, seed)
    r["plus_one_map_win"] = plus_one(p, n_maps, seed + 1)
    return r


def _fmt(v) -> str:
    return "-" if v is None else (f"{v:.1%}" if isinstance(v, float) else str(v))


def compare_table(before: dict, after: dict) -> str:
    keys = ["attack_round_win", "pistol_attack_win", "plant_rate", "postplant_attack_win",
            "eco_vs_full_win", "round2_conversion", "bonus_conversion", "first_blood_conversion",
            "clutch_rate", "overtime_rate", "plus_one_map_win"]
    lines = ["| Statistic | Luau | Tuned | Target |", "| --- | ---: | ---: | ---: |"]
    for k in keys:
        t = TARGETS.get(k)
        tgt = f"{t[0]:.1%} ± {t[1]:.1%}".replace(".0%", "%") if t else "-"
        lines.append(f"| {k} | {_fmt(before.get(k))} | {_fmt(after.get(k))} | {tgt} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--maps", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--luau", action="store_true")
    ap.add_argument("--compare", action="store_true")
    ap.add_argument("--fit-bias", action="store_true")
    ap.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = ap.parse_args(argv)
    if args.fit_bias:
        print(json.dumps(fit_bias(Params()), indent=2))
        return
    if args.compare:
        before, after = report(Params.luau(), args.maps, args.seed), report(Params(), args.maps, args.seed)
        if args.json:
            print(json.dumps({"luau": before, "tuned": after}, indent=2))
        else:
            print(compare_table(before, after))
            print("\nAttack round win by map (tuned):")
            for k, v in after["attack_by_map"].items():
                print(f"  {k:8s} {v:.1%}")
            print("\nRound end (tuned):", {k: f"{v:.1%}" for k, v in after["round_end"].items()})
        return
    r = report(Params.luau() if args.luau else Params(), args.maps, args.seed)
    print(json.dumps(r, indent=2))


if __name__ == "__main__":
    main()
