from antistrat.sim import Assumptions, expected_shift, simulate, suggest_plan

REPORT = {"site_mix_smoothed": {"A": 0.6, "B": 0.25, "C": 0.15},
          "read_accuracy": {"contact": {"acc": 0.65}, "baseline": {"acc": 0.6}}}
ECON = {"intercept": 0.0, "coef_att_load_k": 0.4, "coef_def_load_k": -0.4}


def test_stack_on_favourite_beats_wrong_stack():
    good = simulate(REPORT, ECON, ["stack:A"] * 24, n=4000)
    bad = simulate(REPORT, ECON, ["stack:C"] * 24, n=4000)
    assert good.map_win > bad.map_win


def test_timeline_shape_and_leaks():
    r = simulate(REPORT, ECON, ["stack:C"] * 12 + ["default"] * 12, n=500)
    assert len(r.timeline) == 24
    defence = [t for t in r.timeline if t["side"] == "defense"]
    assert len(defence) == 12 and all(t["leak"] for t in defence)
    assert all(t["side"] == "attack" for t in r.timeline[12:])
    assert 0 < sum(r.score_dist.values()) <= 1.0001
    assert all(int(s.split("-")[0]) == 13 or int(s.split("-")[1]) == 13 for s in r.score_dist)


def test_expected_shift_and_suggestion():
    a = Assumptions()
    assert expected_shift("stack:A", REPORT["site_mix_smoothed"], 0.65, a) > 0
    assert expected_shift("default", REPORT["site_mix_smoothed"], 0.65, a) == 0
    assert suggest_plan(REPORT)[0] in {"stack:A", "read"}


def test_deterministic_with_seed():
    a = simulate(REPORT, ECON, ["read"] * 24, n=300, seed=7)
    b = simulate(REPORT, ECON, ["read"] * 24, n=300, seed=7)
    assert a.map_win == b.map_win
