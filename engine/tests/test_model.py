import json

import numpy as np
import pandas as pd

from antistrat.adaptation import benjamini_hochberg, team_adaptation


def test_model_beats_baseline(trained):
    metrics, _, _ = trained
    for m, d in metrics["maps"].items():
        assert d["early"]["acc"] > d["baseline_acc"], m
        assert d["contact"]["acc"] >= d["early"]["acc"] - 0.05, m


def test_economy(trained):
    metrics, _, _ = trained
    assert 0.3 < metrics["economy"]["attack_win_rate"] < 0.7


def test_reports(trained):
    _, index, agg = trained
    assert index["target"] == "Cloud9"
    assert index["opponents"], "Cloud9 should have VCT opponents in synthetic data"
    opp = index["opponents"][0]
    rep = json.loads((agg / f"{opp['id']}_{opp['maps'][0]}.json").read_text())
    assert abs(sum(rep["site_mix_smoothed"].values()) - 1) < 0.02
    assert rep["sample"]["plants"] <= rep["sample"]["attack_rounds"]
    assert all(t["n"] >= 5 for t in rep["tells"])
    assert "shown" in rep["adaptation"]
    # Aggregates only: no per-round rows or player ids.
    text = json.dumps(rep)
    assert "att_players" not in text and "p0_" not in text


def test_bh():
    q = benjamini_hochberg(np.array([0.01, 0.04, 0.03, 0.5]))
    assert np.all(q >= np.array([0.01, 0.04, 0.03, 0.5]))
    assert q[3] == 0.5


def test_adaptation_not_significant_on_random(pipeline_out):
    out, _ = pipeline_out
    df = pd.read_csv(out / "features.csv", dtype={"series": str, "game": str, "att": str, "winner": str})
    res = team_adaptation(df)
    assert not res["significant"].any()
