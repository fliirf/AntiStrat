import numpy as np
import pandas as pd

from antistrat.impact import marginal_effect, on_site_counts

CENTERS = {"haven": {"A": (0.0, 0.0), "B": (10000.0, 0.0)}}


def test_on_site_counts_uses_radius_and_heaviest_site():
    pos = pd.Series(["0,0;500,500;10000,0;20000,20000", "10000,0;10100,0;0,0"])
    n, heavy = on_site_counts(pos, pd.Series(["A", "A"]), pd.Series(["haven", "haven"]), CENTERS)
    assert list(n) == [2, 1]
    assert list(heavy) == [True, False]


def test_marginal_effect_recovers_a_planted_effect():
    rng = np.random.default_rng(0)
    n = 4000
    k = rng.integers(0, 4, n)
    p = 1 / (1 + np.exp(-(-0.8 + 0.5 * k)))
    d = pd.DataFrame({"n_on": k, "att_load": rng.uniform(2000, 4500, n), "def_load": rng.uniform(2000, 4500, n),
                      "map": rng.choice(["haven", "lotus"], n),
                      "winside": np.where(rng.random(n) < p, "defender", "attacker")})
    est = marginal_effect(d)
    assert 0.08 < est < 0.14  # true average marginal effect is about 0.11


def test_positions_extract_on_synthetic_feed(synth_data):
    from antistrat.extract.positions import extract_positions
    from antistrat.grid import feed_path, read_series_index

    sid = read_series_index(synth_data)[0]["series_id"]
    rows = extract_positions(feed_path(sid, synth_data))
    assert rows and {r["snap"] for r in rows} <= {"fk", "t20"}
    assert all(r["def_pos"].count(",") <= 5 for r in rows)
