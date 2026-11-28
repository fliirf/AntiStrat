import random

from antistrat.quick import Params, Team, play_map
from antistrat.quick import economy as eco
from antistrat.quick.harness import TARGETS, run
from antistrat.quick.round_sim import ATK, DEF, Side, play_round


def _side(team: Team, kits=None) -> Side:
    return Side(team.players, kits or [eco.Kit() for _ in range(5)], [0.0] * 5)


def test_map_rules_first_to_13_and_overtime_by_two():
    rng = random.Random(0)
    saw_ot = False
    for _ in range(300):
        r = play_map(Team.uniform("A"), Team.uniform("B"), None, Params(), rng)
        hi, lo = max(r.score), min(r.score)
        assert len(r.rounds) == sum(r.score)
        if r.overtime:
            saw_ot = True
            assert hi - lo == 2 and lo >= 12
        else:
            assert hi == 13 and lo <= 11
    assert saw_ot


def test_sides_swap_after_round_12_and_pistols():
    r = play_map(Team.uniform("A"), Team.uniform("B"), None, Params(), random.Random(3), a_attacks_first=True)
    assert all(x.attacker == 0 for x in r.rounds[:12])
    assert all(x.attacker == 1 for x in r.rounds[12:24])
    assert r.rounds[0].buys == ("pistol", "pistol")
    if len(r.rounds) > 12:
        assert r.rounds[12].buys == ("pistol", "pistol")


def test_economy_income_and_cap():
    kits = [eco.Kit(credits=8500) for _ in range(5)]
    eco.pay_round(kits, True, 0, [True] * 5, False)
    assert all(k.credits == eco.MAX_CREDITS for k in kits)
    kits = [eco.Kit(credits=0) for _ in range(5)]
    eco.pay_round(kits, False, 3, [True, False, False, False, False], survivor_flat=True)
    assert kits[0].credits == 1000 and kits[1].credits == 2900
    assert kits[1].tier == eco.PISTOL and kits[1].armor == eco.NO_ARMOR


def test_buy_decisions():
    rich = [eco.Kit(credits=4000) for _ in range(5)]
    assert eco.decide_and_buy(rich, 0, False) == eco.FULL
    assert all(k.tier == eco.RIFLE and k.armor == eco.HEAVY and k.credits == 100 for k in rich)
    # lost the pistol: save, because the loss bonus pays for a full buy next round
    broke = [eco.Kit(credits=2300) for _ in range(5)]
    assert eco.decide_and_buy(broke, 1, False) == eco.ECO
    # won the pistol: bonus-buy SMGs instead of saving
    winners = [eco.Kit(credits=3600, armor=eco.LIGHT) for _ in range(5)]
    assert eco.decide_and_buy(winners, 0, False) == eco.FORCE
    assert all(k.tier == eco.SMG for k in winners)


def test_round_ends_with_one_side_and_counts_kills():
    rng = random.Random(1)
    for _ in range(200):
        a, d = _side(Team.uniform("A")), _side(Team.uniform("B"))
        rr = play_round(a, d, Params(), rng)
        assert rr.winner in (ATK, DEF)
        assert sum(rr.kills.values()) == sum(rr.deaths.values()) <= 9
        if rr.how == "elim" and rr.winner == ATK:
            assert not any(rr.survived_def)
        if rr.how == "defuse":
            assert rr.planted and not any(rr.survived_atk)


def test_better_weapons_and_players_win_more():
    rng = random.Random(2)
    p = Params().with_(form_noise=0.0)

    def atk_rate(a_team, d_team, a_tier, d_tier, n=1500):
        wins = 0
        for _ in range(n):
            a = _side(a_team, [eco.Kit(tier=a_tier, armor=eco.HEAVY) for _ in range(5)])
            d = _side(d_team, [eco.Kit(tier=d_tier, armor=eco.HEAVY) for _ in range(5)])
            wins += play_round(a, d, p, rng).winner == ATK
        return wins / n

    even = atk_rate(Team.uniform("A"), Team.uniform("B"), eco.RIFLE, eco.RIFLE)
    assert atk_rate(Team.uniform("A"), Team.uniform("B"), eco.RIFLE, eco.PISTOL) > even + 0.15
    assert atk_rate(Team.uniform("A", 16), Team.uniform("B", 10), eco.RIFLE, eco.RIFLE) > even + 0.15


def test_deterministic_with_seed():
    a, b = Team.uniform("A"), Team.uniform("B")
    r1 = play_map(a, b, "ascent", Params(), random.Random(42))
    r2 = play_map(a, b, "ascent", Params(), random.Random(42))
    assert r1.score == r2.score and [x.winner for x in r1.rounds] == [x.winner for x in r2.rounds]


def test_luau_params_are_the_brief_constants():
    p = Params.luau()
    assert (p.skill_scale, p.hold_bonus, p.postplant_bonus, p.trade_bonus, p.clutch_scale, p.form_noise) == \
        (0.07, 0.55, 0.10, 0.60, 0.04, 0.15)
    assert p.weapon(3, 1) == 1.6 and p.weapon(1, 3) == -1.6 and p.weapon(2, 2) == 0


def test_tuned_engine_hits_calibration_targets():
    """Small harness run; tolerance widened for the smaller sample."""
    r = run(Params(), n_maps=400, seed=9)
    for key, (target, tol) in TARGETS.items():
        assert abs(r[key] - target) <= tol + 0.025, (key, r[key], target)
