"""Monte Carlo match engine for one map, from the target team's point of view.

Runs on aggregates only (an opponent report plus the global economy model), so it can
run in the deployed API without any GRID data.

Model per round:
- Each team's buy (pistol / eco / half / full) follows its money; loadout values give a
  base attack-win probability from the economy model.
- When the opponent attacks, its site is drawn from its smoothed site mix.
- The coach's plan for that round shifts the defence win probability:
  * default: balanced setup, no shift
  * stack:X: an extra defender on X; helps if they hit X, hurts otherwise
  * read: hold the default, and rotate only when the in-round read is confident
    (top site probability >= 0.7); it then helps with that read's accuracy
The shift sizes are explicit assumptions (Assumptions) shown next to the results. With a
calibration from the data (liveread.sim_calibration) they are anchored to the measured
first-kill swing: an extra defender at the fight is worth a quarter of it, a rotation
75% of that (it arrives later), and a wrong call costs as much as a right one gains.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

ROUNDS_PER_HALF = 12
WIN_TARGET = 13


@dataclass
class Assumptions:
    stack_gain: float = 0.12   # defence win prob change when the stacked site is hit
    stack_cost: float = 0.08   # ... when another site is hit
    read_gain: float = 0.10    # when the read is right
    read_cost: float = 0.06    # when the read is wrong
    win_credits: int = 3000
    loss_credits: tuple[int, ...] = (1900, 2400, 2900)
    full_buy: int = 3900
    half_buy: int = 2000

    @classmethod
    def from_calibration(cls, cal: dict | None) -> "Assumptions":
        if cal and cal.get("measured_value"):
            # Measured: one more defender on the site at the plant (alive counts and loadouts held fixed).
            # A right call puts one there, a wrong one pulls one away; a stack works the same way.
            v = round(float(cal["measured_value"]), 3)
            return cls(stack_gain=v, stack_cost=v, read_gain=v, read_cost=v)
        if not cal or not cal.get("extra_defender_value"):
            return cls()
        v = float(cal["extra_defender_value"])
        r = v * float(cal.get("rotation_share", 0.75))
        return cls(stack_gain=round(v, 3), stack_cost=round(v, 3), read_gain=round(r, 3), read_cost=round(r, 3))


@dataclass
class Economy:
    intercept: float
    coef_att_load_k: float
    coef_def_load_k: float

    def p_attack_win(self, att_load: np.ndarray, def_load: np.ndarray) -> np.ndarray:
        z = self.intercept + self.coef_att_load_k * att_load / 1000 + self.coef_def_load_k * def_load / 1000
        return 1 / (1 + np.exp(-z))


@dataclass
class SimResult:
    map_win: float
    score_dist: dict[str, float]
    timeline: list[dict]
    assumptions: dict = field(default_factory=dict)


def _buy(money: np.ndarray, pistol: bool, a: Assumptions) -> tuple[np.ndarray, np.ndarray]:
    """Returns (loadout value, money after buying)."""
    if pistol:
        return np.full_like(money, 800.0), money - 800
    load = np.where(money >= a.full_buy, 4500.0, np.where(money >= a.half_buy, 2500.0, 900.0))
    spend = np.minimum(money, np.where(money >= a.full_buy, 3900, np.where(money >= a.half_buy, 2000, 400)))
    return load, money - spend


def plan_shift(plan: str, site: np.ndarray, read_acc: float, rng: np.random.Generator, a: Assumptions) -> np.ndarray:
    if plan.startswith("stack:"):
        target = plan.split(":", 1)[1]
        return np.where(site == target, a.stack_gain, -a.stack_cost)
    if plan == "read":
        right = rng.random(len(site)) < read_acc
        return np.where(right, a.read_gain, -a.read_cost)
    return np.zeros(len(site))


def _read(report: dict) -> tuple[float, float]:
    """(accuracy, coverage) of the read the coach acts on. Uses the confident read rule
    when the report has one; older reports fall back to acting on every contact read."""
    rule = report.get("read_rule") or {}
    if rule.get("acc") is not None and rule.get("coverage"):
        return float(rule["acc"]), float(rule["coverage"])
    acc = report["read_accuracy"].get("contact", {}).get("acc") or report["read_accuracy"]["baseline"]["acc"]
    return float(acc), 1.0


def expected_shift(plan: str, mix: dict[str, float], read_acc: float, a: Assumptions, coverage: float = 1.0) -> float:
    if plan.startswith("stack:"):
        p = mix.get(plan.split(":", 1)[1], 0.0)
        return p * a.stack_gain - (1 - p) * a.stack_cost
    if plan == "read":
        return coverage * (read_acc * a.read_gain - (1 - read_acc) * a.read_cost)
    return 0.0


def simulate(report: dict, economy: dict, plan: list[str], start_side: str = "defense",
             n: int = 5000, seed: int = 0, assumptions: Assumptions | None = None) -> SimResult:
    """plan[i] is the coach's call for regulation round i+1 (ignored on attack rounds)."""
    a = assumptions or Assumptions()
    eco = Economy(economy["intercept"], economy["coef_att_load_k"], economy["coef_def_load_k"])
    rng = np.random.default_rng(seed)
    sites = list(report["site_mix_smoothed"])
    mix = np.array([report["site_mix_smoothed"][s] for s in sites], dtype=float)
    mix = mix / mix.sum()
    acc, cov = _read(report)
    plan = (list(plan) + ["default"] * 24)[:24]

    us_money = np.full(n, 800.0)
    them_money = np.full(n, 800.0)
    us_score = np.zeros(n, int)
    them_score = np.zeros(n, int)
    us_streak = np.zeros(n, int)
    them_streak = np.zeros(n, int)
    alive = np.ones(n, bool)
    timeline = []

    for i in range(24):
        half_start = i % ROUNDS_PER_HALF == 0
        if half_start:
            us_money[:] = 800.0
            them_money[:] = 800.0
            us_streak[:] = 0
            them_streak[:] = 0
        first_half = i < ROUNDS_PER_HALF
        defending = (start_side == "defense") == first_half
        us_load, us_money = _buy(us_money, half_start, a)
        them_load, them_money = _buy(them_money, half_start, a)
        if defending:
            p_att = eco.p_attack_win(them_load, us_load)
            site = rng.choice(sites, size=n, p=mix)
            shift = plan_shift(plan[i], site, acc, rng, a)
            if plan[i] == "read":  # no confident read this round: default setup, no shift
                shift = np.where(rng.random(n) < cov, shift, 0.0)
            p_us = np.clip(1 - p_att + shift, 0.02, 0.98)
        else:
            p_us = eco.p_attack_win(us_load, them_load)
        us_won = rng.random(n) < p_us
        live = alive & (us_score < WIN_TARGET) & (them_score < WIN_TARGET)
        us_score += (us_won & live)
        them_score += (~us_won & live)
        us_streak = np.where(us_won, 0, np.minimum(us_streak + 1, len(a.loss_credits)))
        them_streak = np.where(us_won, np.minimum(them_streak + 1, len(a.loss_credits)), 0)
        loss = np.array(a.loss_credits)
        us_money = np.minimum(9000, us_money + np.where(us_won, a.win_credits, loss[np.maximum(us_streak - 1, 0)]))
        them_money = np.minimum(9000, them_money + np.where(us_won, loss[np.maximum(them_streak - 1, 0)], a.win_credits))

        entry = {"round": i + 1, "side": "defense" if defending else "attack",
                 "plan": plan[i] if defending else None,
                 "p_win": round(float(p_us[live].mean()) if live.any() else float(p_us.mean()), 3),
                 "p_reached": round(float(live.mean()), 3)}
        if defending:
            mixd = {s: float(p) for s, p in zip(sites, mix)}
            entry["likely_site"] = sites[int(np.argmax(mix))]
            entry["delta_vs_default"] = round(float(expected_shift(plan[i], mixd, acc, a, cov)), 3)
            entry["leak"] = bool(entry["delta_vs_default"] < 0)
            if plan[i].startswith("stack:"):
                entry["note"] = f"{1 - mixd.get(plan[i][6:], 0):.0%} of their attacks go elsewhere"
            elif plan[i] == "read":
                entry["note"] = f"confident read in {cov:.0%} of rounds, right {acc:.0%} of the time"
        timeline.append(entry)

    # Overtime at 12-12: decided by a single fair-ish round pair (average win chance).
    tied = (us_score == 12) & (them_score == 12)
    p_ot = np.mean([t["p_win"] for t in timeline])
    ot_win = rng.random(n) < p_ot
    us_final = np.where(tied, np.where(ot_win, 13, 12), us_score)
    them_final = np.where(tied, np.where(ot_win, 12, 13), them_score)
    won = us_final > them_final
    scores, counts = np.unique([f"{u}-{t}" for u, t in zip(us_final, them_final)], return_counts=True)
    top = sorted(zip(scores, counts), key=lambda x: -x[1])[:8]
    return SimResult(map_win=round(float(won.mean()), 3),
                     score_dist={s: round(c / n, 3) for s, c in top},
                     timeline=timeline, assumptions=asdict(a))


def suggest_plan(report: dict, assumptions: Assumptions | None = None) -> list[str]:
    """Best expected call per defence round given the report (same for every round)."""
    a = assumptions or Assumptions()
    mix = report["site_mix_smoothed"]
    acc, cov = _read(report)
    options = ["default", "read", *[f"stack:{s}" for s in mix]]
    best = max(options, key=lambda p: expected_shift(p, mix, acc, a, cov))
    return [best] * 24


def impact(report: dict, economy: dict, a: Assumptions | None = None, n: int = 2000, seed: int = 0) -> dict:
    """Map win chance on defence-first plans: default, rotate on read, stack the habit site."""
    a = a or Assumptions()
    mix = report["site_mix_smoothed"]
    habit = max(mix, key=mix.get)
    win = {name: simulate(report, economy, [plan] * 24, "defense", n, seed, a).map_win
           for name, plan in (("default", "default"), ("read", "read"), ("habit_stack", f"stack:{habit}"))}
    return {"map_win": win, "habit_site": habit}
