"""One round in quick mode: a chain of 1v1 duels with trades, plant, post-plant, retake/defuse
and clutches (GDD 'Urutan satu round', steps 4-9; buy is done by the caller)."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from .economy import KILL_CREDITS, PLANT_CREDITS, Kit
from .model import Player
from .params import Params

ATK, DEF = "atk", "def"


@dataclass
class Side:
    players: list[Player]
    kits: list[Kit]
    form: list[float]                 # per-map form, in attribute points
    alive: set[int] = field(default_factory=set)

    def skill(self, i: int) -> float:
        return self.players[i].duel_skill + self.form[i]


@dataclass
class RoundResult:
    winner: str
    how: str                          # elim | detonate | defuse | time
    planted: bool
    first_blood: str | None
    clutches: list[tuple[str, int, bool]]   # (side, opponents alive when lone, won)
    survived_atk: list[bool]
    survived_def: list[bool]
    kills: dict[tuple[str, int], int]
    deaths: dict[tuple[str, int], int]


def _sigmoid(z: float) -> float:
    return 1.0 / (1.0 + math.exp(-z))


class _Round:
    def __init__(self, atk: Side, dfn: Side, p: Params, rng: random.Random, side_bias: float):
        self.s = {ATK: atk, DEF: dfn}
        self.p, self.rng, self.bias = p, rng, side_bias
        self.planted = False
        self.first_blood: str | None = None
        self.lone_seen: dict[str, int] = {}
        self.kills: dict[tuple[str, int], int] = {}
        self.deaths: dict[tuple[str, int], int] = {}

    def _other(self, side: str) -> str:
        return DEF if side == ATK else ATK

    def z_attacker(self, ai: int, di: int, trade_for: str | None) -> float:
        p, a, d = self.p, self.s[ATK], self.s[DEF]
        ka, kd = a.kits[ai], d.kits[di]
        na, nd = len(a.alive), len(d.alive)
        z = p.skill_scale * (a.skill(ai) - d.skill(di))
        z += p.weapon(ka.tier, kd.tier) + p.armor_edge * (ka.armor - kd.armor)
        z += self.bias + p.manpower_edge * (na - nd)
        if trade_for == ATK:
            z += p.trade_bonus
        elif trade_for == DEF:
            z -= p.trade_bonus
        elif self.planted:
            z += p.postplant_bonus
        else:
            z -= p.hold_bonus
        if na == 1:
            pl = a.players[ai]
            z += p.clutch_scale * ((pl.a("clutch") + pl.a("composure")) / 2 - 10)
        if nd == 1:
            pl = d.players[di]
            z -= p.clutch_scale * ((pl.a("clutch") + pl.a("composure")) / 2 - 10)
        return z

    def _kill(self, side: str, killer: int, victim: int) -> None:
        other = self._other(side)
        self.s[other].alive.discard(victim)
        self.s[side].kits[killer].credits += KILL_CREDITS
        self.kills[(side, killer)] = self.kills.get((side, killer), 0) + 1
        self.deaths[(other, victim)] = self.deaths.get((other, victim), 0) + 1
        if self.first_blood is None:
            self.first_blood = side
        for sd in (ATK, DEF):
            if len(self.s[sd].alive) == 1 and sd not in self.lone_seen and self.s[self._other(sd)].alive:
                self.lone_seen[sd] = len(self.s[self._other(sd)].alive)

    def fight(self, ai: int, di: int, trade_for: str | None = None, depth: int = 0) -> None:
        atk_wins = self.rng.random() < _sigmoid(self.z_attacker(ai, di, trade_for))
        if atk_wins:
            self._kill(ATK, ai, di)
            self._maybe_trade(DEF, killer=ai, depth=depth)
        else:
            self._kill(DEF, di, ai)
            self._maybe_trade(ATK, killer=di, depth=depth)

    def _maybe_trade(self, side: str, killer: int, depth: int) -> None:
        """`side` just lost a player to `killer`; a teammate in range may trade."""
        mates = sorted(self.s[side].alive)
        if depth >= 2 or not mates or not self.s[self._other(side)].alive:
            return
        t = self.rng.choice(mates)
        pl = self.s[side].players[t]
        p_trade = self.p.trade_base + self.p.trade_attr * ((pl.a("trading") + pl.a("teamwork")) / 2 - 10) / 10
        if self.rng.random() < p_trade:
            if side == ATK:
                self.fight(t, killer, trade_for=ATK, depth=depth + 1)
            else:
                self.fight(killer, t, trade_for=DEF, depth=depth + 1)

    def play(self) -> RoundResult:
        p, rng, a, d = self.p, self.rng, self.s[ATK], self.s[DEF]
        how = None
        first = True
        while a.alive and d.alive:
            na, nd = len(a.alive), len(d.alive)
            if not self.planted and not first:
                if rng.random() < _sigmoid(p.plant_c + p.plant_k * (na - nd)):
                    self.planted = True
                    for k in a.kits:
                        k.credits += PLANT_CREDITS
                    continue
                if na == 1 and nd >= p.save_threshold and rng.random() < p.save_prob:
                    how = "time"          # lone attacker saves; defense wins on time
                    break
            self.fight(rng.choice(sorted(a.alive)), rng.choice(sorted(d.alive)))
            first = False
        if how == "time":
            winner = DEF
        elif not d.alive:
            winner, how = ATK, "elim"
        elif self.planted:
            ok = rng.random() < p.defuse_time_ok
            winner, how = (DEF, "defuse") if ok else (ATK, "detonate")
        else:
            winner, how = DEF, "elim"
        clutches = [(sd, x, sd == winner) for sd, x in self.lone_seen.items()]
        return RoundResult(winner, how, self.planted, self.first_blood, clutches,
                           [i in a.alive for i in range(5)], [i in d.alive for i in range(5)],
                           self.kills, self.deaths)


def play_round(atk: Side, dfn: Side, p: Params, rng: random.Random, side_bias: float = 0.0) -> RoundResult:
    atk.alive = set(range(len(atk.players)))
    dfn.alive = set(range(len(dfn.players)))
    return _Round(atk, dfn, p, rng, side_bias).play()
