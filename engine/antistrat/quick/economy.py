"""VALORANT economy as in the GDD table 'Aturan asli yang dipakai apa adanya'.

Each player carries credits, a weapon tier and an armor level. Survivors keep their kit into
the next round; dead players lose it. The team decides one buy type per round and richer
players drop for poorer ones (credits are pooled when paying).
"""
from __future__ import annotations

from dataclasses import dataclass

START_CREDITS = 800
MAX_CREDITS = 9000
OT_CREDITS = 5000
WIN_CREDITS = 3000
LOSS_CREDITS = (1900, 2400, 2900)
KILL_CREDITS = 200
PLANT_CREDITS = 300
SURVIVE_LOSS_CREDITS = 1000

RIFLE, SMG, PISTOL = 3, 2, 1          # weapon tiers
NO_ARMOR, LIGHT, HEAVY = 0, 1, 2
WEAPON_COST = {PISTOL: 0, SMG: 1600, RIFLE: 2900}
ARMOR_COST = {NO_ARMOR: 0, LIGHT: 400, HEAVY: 1000}

FULL, FORCE, ECO, PISTOL_ROUND = "full", "force", "eco", "pistol"


@dataclass
class Kit:
    credits: int = START_CREDITS
    tier: int = PISTOL
    armor: int = NO_ARMOR


def _upgrade_cost(k: Kit, tier: int, armor: int) -> int:
    return (WEAPON_COST[tier] if k.tier < tier else 0) + (ARMOR_COST[armor] if k.armor < armor else 0)


def _pay(kits: list[Kit], costs: list[int]) -> None:
    """Each player pays their own kit; what they cannot cover is dropped by the richest."""
    due = 0
    for k, c in zip(kits, costs):
        own = min(k.credits, c)
        k.credits -= own
        due += c - own
    for k in sorted(kits, key=lambda k: -k.credits):
        take = min(k.credits, due)
        k.credits -= take
        due -= take


def _apply(kits: list[Kit], tier: int, armor: int) -> None:
    costs = [_upgrade_cost(k, tier, armor) for k in kits]
    _pay(kits, costs)
    for k in kits:
        k.tier, k.armor = max(k.tier, tier), max(k.armor, armor)


def decide_and_buy(kits: list[Kit], loss_streak: int, pistol: bool, must_force: bool = False) -> str:
    """Choose a buy type, buy, and return it.

    - pistol round: light armor + pistol for everyone.
    - full: rifle + heavy for all five, if the pooled credits cover it.
    - eco: after a loss, if saving now still gives a full buy next round even after losing
      again (a team that just won bonus-buys SMGs instead).
    - force: SMG + light armor (or what the money allows) otherwise, or when the round is a
      must-win (`must_force`: last round of a half or facing map point).
    """
    if pistol:
        for k in kits:
            k.tier, k.armor = PISTOL, LIGHT
            k.credits -= ARMOR_COST[LIGHT]
        return PISTOL_ROUND
    total = sum(k.credits for k in kits)
    if total >= sum(_upgrade_cost(k, RIFLE, HEAVY) for k in kits):
        _apply(kits, RIFLE, HEAVY)
        return FULL
    next_loss = LOSS_CREDITS[min(loss_streak, len(LOSS_CREDITS) - 1)]
    full_cost_from_scratch = 5 * (WEAPON_COST[RIFLE] + ARMOR_COST[HEAVY])
    # A team that just won (no loss streak) bonus-buys SMGs instead of saving.
    if not must_force and loss_streak > 0 and total + 5 * next_loss >= full_cost_from_scratch:
        return ECO
    if total >= sum(_upgrade_cost(k, SMG, LIGHT) for k in kits):
        _apply(kits, SMG, LIGHT)
        return FORCE
    if total >= sum(_upgrade_cost(k, PISTOL, LIGHT) for k in kits):
        _apply(kits, PISTOL, LIGHT)
    return ECO


def loss_credits(streak: int) -> int:
    """Credits after the `streak`-th loss in a row (1-based)."""
    return LOSS_CREDITS[min(max(streak, 1), len(LOSS_CREDITS)) - 1]


def pay_round(kits: list[Kit], won: bool, streak_after: int, survived: list[bool],
              survivor_flat: bool) -> None:
    """Round-end income. `survivor_flat`: losing survivors get 1000 flat instead of loss
    credits (attack: lost without plant; defense: lost to detonation)."""
    for k, alive in zip(kits, survived):
        if won:
            k.credits += WIN_CREDITS
        elif alive and survivor_flat:
            k.credits += SURVIVE_LOSS_CREDITS
        else:
            k.credits += loss_credits(streak_after)
        k.credits = min(MAX_CREDITS, k.credits)
        if not alive:
            k.tier, k.armor = PISTOL, NO_ARMOR
