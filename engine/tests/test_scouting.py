import pandas as pd

from antistrat.scouting import op_profile, op_rounds, util_bounds, util_map

CENTERS = {"haven": {"A": (0.0, 0.0), "B": (10000.0, 0.0)}}


def _features(n=40):
    return pd.DataFrame({"series": ["s"] * n, "game": ["g"] * n, "round": range(1, n + 1), "map": ["haven"] * n,
                         "att": ["t2"] * n, "dfn": ["t1"] * n, "winner": ["t1", "t2"] * (n // 2),
                         "scheduled_start": ["2025-01-01"] * n})


def test_operator_profile_counts_defensive_op_openings():
    f = _features()
    # t1 opens every 4th round with an Op kill near A; other first kills are rifles by t2.
    kills = pd.DataFrame([{"game": "g", "round": r, "first": "True", "killer": "p1" if r % 4 == 0 else "q1",
                           "killer_team": "t1" if r % 4 == 0 else "t2",
                           "weapon": "operator" if r % 4 == 0 else "vandal",
                           "killer_x": 100.0, "killer_y": 0.0} for r in range(1, 41)])
    orounds = op_rounds(f, kills)
    prof = op_profile(orounds, kills, "t1", "haven", CENTERS, stable=False)
    assert prof["sides"]["defense"]["op_open_rate"] == 0.25
    assert prof["def_open_zones"] == {"A": 1.0}
    assert prof["one_player_share"] == 1.0 and prof["confidence"] == "low"
    assert op_profile(orounds, kills, "nobody", "haven", CENTERS, stable=True) is None


def test_utility_map_bins_casts_and_drops_sparse_cells():
    f = _features()
    att = pd.DataFrame({"game": "g", "round": list(range(1, 41)) * 3, "x": [0.0] * 120, "y": [0.0] * 120,
                        "ability": ["smoke"] * 120})
    dfn = pd.DataFrame({"game": "g", "round": [1, 2], "x": [9000.0, 9000.0], "y": [100.0, 100.0],
                        "ability": ["wall", "wall"]})
    bounds = util_bounds(att, pd.concat([dfn] * 50), f, ["haven"])
    u = util_map(att, dfn, f, "t2", "haven", bounds)
    assert u["attack"]["casts"] == 120 and sum(u["attack"]["cells"].values()) == 120
    assert u["attack"]["top_abilities"] == {"smoke": 1.0}
    assert u["defense"]["casts"] == 0  # t2 never defends here
    u1 = util_map(att, dfn, f, "t1", "haven", bounds)
    assert u1["defense"]["casts"] == 2 and u1["defense"]["cells"] == {}  # below MIN_CELL
