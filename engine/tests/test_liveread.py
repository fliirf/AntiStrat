from antistrat.liveread import lookup, proba
from antistrat.sim import Assumptions


def test_live_read_table_is_aggregate_and_validated(trained):
    _, index, _ = trained
    for m, lr in index["live_read"].items():
        cells = lr["cells"]
        assert "*|*" in cells and all(c["n"] >= 10 for c in cells.values())
        assert all(sum(c["counts"].values()) == c["n"] for c in cells.values())
        v = lr["validation"]
        assert v["n_test"] > 0 and 0 <= v["table_acc"] <= 1 and 0 <= v["gbm_acc"] <= 1
        # Unknown signals back off to the map-wide cell.
        key, cell = lookup(cells, "Z9", "Zx")
        assert key == "*|*"
        assert abs(proba(cell, lr["sites"]).sum() - 1) < 1e-9


def test_lookup_backs_off_from_thin_cells():
    cells = {"A2|Ba": {"n": 3, "counts": {"A": 3, "B": 0}},
             "*|Ba": {"n": 40, "counts": {"A": 10, "B": 30}},
             "*|*": {"n": 100, "counts": {"A": 50, "B": 50}}}
    assert lookup(cells, "A2", "Ba")[0] == "*|Ba"


def test_anti_read_and_calibration(trained):
    _, index, agg = trained
    import json
    cal = {"extra_defender_value": 0.1, "rotation_share": 0.75}
    a = Assumptions.from_calibration(cal)
    assert a.stack_gain == a.stack_cost == 0.1 and a.read_gain == 0.075
    assert Assumptions.from_calibration(index["sim_calibration"]) is not None
    assert Assumptions.from_calibration(None) == Assumptions()
    for entry in index["self"]:
        for m in entry["maps"]:
            rep = json.loads((agg / f"{entry['id']}_{m}.json").read_text())
            assert "leaks" in rep
            assert "read_avg" in index["map_detail"][m]
