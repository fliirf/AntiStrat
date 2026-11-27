import json

from antistrat.sim import expected_shift, simulate


def test_call_sheet_per_map_with_rules_measured_on_newer_rounds(trained):
    _, index, _ = trained
    cs = index["call_sheet"]
    assert set(cs) == set(index["map_detail"])
    for m, sheet in cs.items():
        assert sheet["fallback"] and sheet["timing"]["n"] > 0
        assert sheet["confident_read"]["min_prob"] == 0.7
        for r in sheet["rules"]:
            assert r["call"] in ("rotate", "lean")
            assert r["n_older"] >= 30 and r["rate_older"] >= 0.6
            assert r["site"] in r["text"]


def test_call_sheet_finds_utility_rules(pipeline_out):
    from antistrat.callsheet import map_call_sheet
    from antistrat.pipeline import _features_df

    out, _ = pipeline_out
    sheet = map_call_sheet(_features_df(out), "haven", ["A", "B", "C"], min_n=5)
    # Synthetic utility is aimed at the true site most of the time.
    kinds = {r["kind"] for r in sheet["rules"]}
    assert "early_utility" in kinds
    assert all(r["rate_older"] >= 0.6 for r in sheet["rules"])


def test_reports_have_traits_and_read_rule(trained):
    _, index, agg = trained
    opp = index["opponents"][0]
    rep = json.loads((agg / f"{opp['id']}_{opp['maps'][0]}.json").read_text())
    assert "site_mix_note" in rep and "read_rule" in rep
    for t in rep["traits"]:
        assert t["confidence"] in ("low", "medium") and t["text"]


def test_read_only_acts_on_confident_rounds():
    a_full = expected_shift("read", {"A": 1.0}, 0.8, __import__("antistrat.sim", fromlist=["Assumptions"]).Assumptions(), 1.0)
    a_half = expected_shift("read", {"A": 1.0}, 0.8, __import__("antistrat.sim", fromlist=["Assumptions"]).Assumptions(), 0.5)
    assert abs(a_half - a_full / 2) < 1e-9


def test_simulation_uses_read_rule(trained):
    _, index, agg = trained
    opp = index["opponents"][0]
    rep = json.loads((agg / f"{opp['id']}_{opp['maps'][0]}.json").read_text())
    res = simulate(rep, index["economy"], ["read"] * 24, n=500)
    note = next(t["note"] for t in res.timeline if t["side"] == "defense")
    assert "confident read" in note
