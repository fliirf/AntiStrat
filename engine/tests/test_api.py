import pytest
from fastapi.testclient import TestClient

from antistrat.api import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_maps():
    assert client.get("/maps").json() == {"maps": ["haven", "lotus"]}


@pytest.fixture
def api_with_data(trained, monkeypatch):
    _, index, agg = trained
    monkeypatch.setenv("ANTISTRAT_AGG_DIR", str(agg))
    return index


def test_report_and_simulate(api_with_data):
    opp = api_with_data["opponents"][0]
    team, m = opp["id"], opp["maps"][0]
    assert client.get("/index").json()["target"] == "Cloud9"
    rep = client.get(f"/report/{team}/{m}").json()
    assert rep["map"] == m
    plan = client.get(f"/suggest/{team}/{m}").json()["plan"]
    r = client.post("/simulate", json={"team": team, "map": m, "plan": plan, "n": 300})
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body["map_win"] <= 1 and len(body["timeline"]) == 24


def test_rejects_bad_input(api_with_data):
    opp = api_with_data["opponents"][0]
    assert client.get("/report/..%2Fetc/haven").status_code in (400, 404)
    assert client.get(f"/report/{opp['id']}/ascent").status_code == 400
    r = client.post("/simulate", json={"team": opp["id"], "map": opp["maps"][0], "plan": ["stack:Z"]})
    assert r.status_code == 400


def test_simulate_every_call_type(api_with_data):
    opp = api_with_data["opponents"][0]
    rep = client.get(f"/report/{opp['id']}/{opp['maps'][0]}").json()
    plan = ["default", "read"] + [f"stack:{s}" for s in rep["site_mix_smoothed"]]
    r = client.post("/simulate", json={"team": opp["id"], "map": opp["maps"][0], "plan": (plan * 5)[:24], "n": 200})
    assert r.status_code == 200, r.text
