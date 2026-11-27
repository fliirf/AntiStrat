import json

import pandas as pd

from antistrat.edges import confident_read, summarize_persistence, timing


def test_reports_carry_edges_timing_and_confident_read(trained):
    _, index, agg = trained
    assert "edge_validation" in index and "map_detail" in index
    assert index["self"], "the target team is scouted too"
    opp = index["opponents"][0]
    rep = json.loads((agg / f"{opp['id']}_{opp['maps'][0]}.json").read_text())
    assert {"edges", "timing", "confident_read"} <= rep.keys()
    for e in rep["edges"]:
        assert {"kind", "text", "n", "lift", "q", "shown"} <= e.keys()
        assert 0 <= e["q"] <= 1
    cr = rep["confident_read"]["contact"]
    assert [r["min_prob"] for r in cr] == [0.5, 0.6, 0.7, 0.8]
    assert all(a["coverage"] >= b["coverage"] for a, b in zip(cr, cr[1:]))


def test_confident_read_coverage_and_accuracy():
    pred = pd.Series(["A", "B", "A", "B"])
    prob = pd.Series([0.9, 0.55, 0.75, 0.65])
    truth = pd.Series(["A", "A", "A", "B"])
    out = {r["min_prob"]: r for r in confident_read(pred, prob, truth)}
    assert out[0.5]["coverage"] == 1.0 and out[0.5]["acc"] == 0.75
    assert out[0.7]["n"] == 2 and out[0.7]["acc"] == 1.0
    assert out[0.8]["n"] == 1


def test_persistence_trust_needs_enough_edges_that_hold():
    rows = [{"kind": "fast", "lift_discover": 0.2, "lift_check": 0.1, "held": True}] * 4
    rows += [{"kind": "fast", "lift_discover": 0.2, "lift_check": -0.1, "held": False}]
    rows += [{"kind": "site", "lift_discover": 0.2, "lift_check": 0.1, "held": True}] * 3
    s = summarize_persistence(pd.DataFrame(rows))
    assert s["fast"]["held"] == 0.8 and s["fast"]["trusted"]
    assert not s["site"]["trusted"]  # too few edges checked


def test_timing_gap_only_counts_contact_before_plant():
    rows = pd.DataFrame({"fk_t": [20.0, 50.0, None], "plant_t": [45.0, 40.0, 30.0]})
    t = timing(rows)
    assert t["contact_to_plant_s"] == 25.0
    assert t["plant_s"] == 40.0


def test_team_specific_read_is_scored(pipeline_out):
    from antistrat.edges import team_specific_gain
    from antistrat.pipeline import _features_df

    out, _ = pipeline_out
    f = _features_df(out)
    tsr = team_specific_gain(f, ["haven", "lotus"], sorted(f["att"].unique()), min_team_rows=5, min_test=5)
    assert tsr
    for res in tsr.values():
        for name in ("early", "contact"):
            assert {"generic", "prior", "team_feature"} <= res[name].keys()
            assert 0 <= res[name]["prior"]["acc"] <= 1
