import json

import pandas as pd

from antistrat.sites import nearest_site
from synth import SITES


def test_extracts_every_round(pipeline_out):
    out, _ = pipeline_out
    rounds = pd.read_csv(out / "rounds.csv")
    assert len(rounds) == 12 * 20
    assert set(rounds["map"]) == {"haven", "lotus"}
    assert rounds["is_vct"].sum() == 4 * 20


def test_casts_only_early_attacker(pipeline_out):
    out, _ = pipeline_out
    casts = pd.read_csv(out / "casts.csv")
    assert len(casts) > 0
    assert casts["t_rel"].max() <= 15
    assert not casts["ability"].isin(["wall", "flash"]).any()


def test_sites_recovered(pipeline_out):
    _, centers_path = pipeline_out
    centers = json.loads(centers_path.read_text())
    for m, true in SITES.items():
        got = centers[m]["centers"]
        assert len(got) == 3
        for letter, (x, y) in true.items():
            assert nearest_site(x, y, {k: tuple(v) for k, v in got.items()}) == letter
        assert all(s["median_dist_m"] < 5 for s in centers[m]["stats"].values())


def test_features(pipeline_out):
    out, _ = pipeline_out
    df = pd.read_csv(out / "features.csv")
    planted = df.dropna(subset=["site"])
    assert 0.5 < len(planted) / len(df) < 0.9
    # Utility aimed at the true site should dominate in synthetic data.
    hit = [r[f"util_aim_{r['site']}"] for _, r in planted.iterrows()]
    assert sum(hit) / planted["util_n"].sum() > 0.6
