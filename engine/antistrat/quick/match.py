"""One map in quick mode: first to 13, side swap after round 12, overtime win-by-2 with
5,000 credits per player each overtime round (GDD 'Aturan asli')."""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from . import economy as eco
from .model import Team
from .params import Params
from .round_sim import ATK, DEF, RoundResult, Side, play_round

HALF = 12
TARGET = 13
OT_ROUND_CAP = 40   # safety cap on overtime rounds; never reached in practice

MAPS_FILE = Path(__file__).parent / "data" / "maps.json"


@lru_cache(maxsize=None)
def load_maps(path: str = str(MAPS_FILE)) -> dict:
    return {m["id"]: m for m in json.loads(Path(path).read_text())["maps"]}


def side_bias(map_id: str | None, p: Params) -> float:
    if not map_id or not p.use_map_bias:
        return 0.0
    return float(load_maps().get(map_id, {}).get("attack_bias", 0.0))


@dataclass
class RoundLog:
    no: int
    attacker: int                 # 0 = team A attacks, 1 = team B attacks
    buys: tuple[str, str]         # (team A, team B)
    winner: int
    result: RoundResult


@dataclass
class MapResult:
    map_id: str | None
    score: tuple[int, int]
    rounds: list[RoundLog] = field(default_factory=list)

    @property
    def winner(self) -> int:
        return 0 if self.score[0] > self.score[1] else 1

    @property
    def overtime(self) -> bool:
        return len(self.rounds) > 2 * HALF


def _form(team: Team, p: Params, rng: random.Random) -> list[float]:
    return [rng.gauss(0.0, p.form_noise * (21 - pl.a("konsistensi"))) for pl in team.players]


def play_map(a: Team, b: Team, map_id: str | None = None, p: Params | None = None,
             rng: random.Random | None = None, a_attacks_first: bool = True) -> MapResult:
    p = p or Params()
    rng = rng or random.Random()
    bias = side_bias(map_id, p)
    teams = (a, b)
    form = (_form(a, p, rng), _form(b, p, rng))
    kits = ([eco.Kit() for _ in range(5)], [eco.Kit() for _ in range(5)])
    streak = [0, 0]                       # consecutive losses
    score = [0, 0]
    out = MapResult(map_id, (0, 0))
    n = 0
    while True:
        n += 1
        reg = n <= 2 * HALF
        if reg and max(score) >= TARGET:
            break
        if not reg and abs(score[0] - score[1]) >= 2:
            break
        if n > 2 * HALF + OT_ROUND_CAP:
            break
        if reg:
            first_half = n <= HALF
            attacker = (0 if a_attacks_first else 1) if first_half else (1 if a_attacks_first else 0)
            pistol = n in (1, HALF + 1)
            if pistol:
                for t in (0, 1):
                    for k in kits[t]:
                        k.credits, k.tier, k.armor = eco.START_CREDITS, eco.PISTOL, eco.NO_ARMOR
                    streak[t] = 0
        else:
            # overtime: sides alternate every round, everyone reset to 5,000
            attacker = (0 if a_attacks_first else 1) if (n - 2 * HALF) % 2 == 1 else (1 if a_attacks_first else 0)
            pistol = False
            for t in (0, 1):
                for k in kits[t]:
                    k.credits, k.tier, k.armor = eco.OT_CREDITS, eco.PISTOL, eco.NO_ARMOR
        buys = []
        for t in (0, 1):
            must = reg and (n in (HALF, 2 * HALF) or score[1 - t] == TARGET - 1)
            buys.append(eco.decide_and_buy(kits[t], streak[t], pistol, must))
        att, dfn = attacker, 1 - attacker
        rs = play_round(Side(teams[att].players, kits[att], form[att]),
                        Side(teams[dfn].players, kits[dfn], form[dfn]), p, rng, bias)
        winner = att if rs.winner == ATK else dfn
        loser = 1 - winner
        score[winner] += 1
        streak[winner] = 0
        streak[loser] = min(streak[loser] + 1, len(eco.LOSS_CREDITS))
        lost_side = ATK if loser == att else DEF
        flat = (lost_side == ATK and not rs.planted) or (lost_side == DEF and rs.how == "detonate")
        surv = {att: rs.survived_atk, dfn: rs.survived_def}
        eco.pay_round(kits[winner], True, 0, surv[winner], False)
        eco.pay_round(kits[loser], False, streak[loser], surv[loser], flat)
        out.rounds.append(RoundLog(n, att, (buys[0], buys[1]), winner, rs))
    out.score = (score[0], score[1])
    return out
