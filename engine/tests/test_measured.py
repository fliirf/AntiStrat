import numpy as np
import pandas as pd

from antistrat.agents import agent_of
from antistrat.measured import at_plant, commit_times, plant_position_value, read_times
from antistrat.sim import Assumptions

C = {"haven": {"A": (0.0, 0.0), "B": (10000.0, 0.0)}}


def _tl(rows):
    return pd.DataFrame(rows)


def test_commit_time_majority_and_shift():
    base = {"series": "s", "game": "g", "round": 1, "plant_t": 40.0}
    tl = _tl([{**base, "snap": "s10", "def_alive": 5, "def_near": 1},
              {**base, "snap": "s20", "def_alive": 5, "def_near": 2},
              {**base, "snap": "s24", "def_alive": 4, "def_near": 3},
              {**base, "snap": "s42", "def_alive": 4, "def_near": 4}])  # after the plant: ignored
    c = commit_times(tl).iloc[0]
    assert c["commit_majority"] == 24.0   # 3 of 4 alive near the site
    assert c["commit_shift"] == 24.0      # 1 -> 3 near the site


def test_commit_time_censored_when_never():
    base = {"series": "s", "game": "g", "round": 1, "plant_t": 30.0}
    tl = _tl([{**base, "snap": "s10", "def_alive": 5, "def_near": 0},
              {**base, "snap": "s20", "def_alive": 5, "def_near": 1}])
    assert np.isnan(commit_times(tl).iloc[0]["commit_majority"])


def test_read_time_uses_first_confident_correct_read():
    oof = pd.DataFrame({"series": ["s"] * 3, "game": ["g"] * 3, "round": [1, 2, 3], "site": ["A", "A", "A"],
                        "pred_early": ["A", "B", "B"], "prob_early": [0.8, 0.5, 0.9],
                        "pred_contact": ["A", "A", "A"], "prob_contact": [0.9, 0.75, 0.9],
                        "fk_known": [1, 1, 1], "fk_t": [20.0, 25.0, 30.0]})
    r = read_times(oof).set_index("round")
    assert r.loc[1, "read_t"] == 15.0          # early read was already right and confident
    assert r.loc[2, "read_t"] == 25.0          # right only at first contact
    assert r.loc[3, "false_alarm"]             # a confident early read named the wrong site


def test_plant_position_value_recovers_planted_effect():
    rng = np.random.default_rng(1)
    n = 3000
    near = rng.integers(0, 4, n)
    alive = rng.integers(1, 6, n)
    p = 1 / (1 + np.exp(-(-1.5 + 0.4 * near + 0.2 * alive)))
    tl = pd.DataFrame({"series": [f"s{i % 300}" for i in range(n)], "game": "g", "round": range(n), "snap": "plant",
                       "map": rng.choice(["haven", "lotus"], n), "def_near": near, "def_alive": alive,
                       "att_alive": rng.integers(1, 6, n), "att_load": rng.uniform(2000, 4500, n),
                       "def_load": rng.uniform(2000, 4500, n),
                       "winside": np.where(rng.random(n) < p, "defender", "attacker")})
    v = plant_position_value(at_plant(tl), reps=20)["extra_defender_near_site"]
    assert 0.05 < v["est"] < 0.12 and v["lo"] < v["est"] < v["hi"]


def test_measured_calibration_takes_priority():
    a = Assumptions.from_calibration({"measured_value": 0.08, "extra_defender_value": 0.2})
    assert a.read_gain == a.read_cost == a.stack_gain == 0.08


def test_agents_map_known_abilities_only():
    assert agent_of("recon-bolt") == "Sova" and agent_of("dark-cover") == "Omen"
    assert agent_of("something-new") is None
