from fastapi.testclient import TestClient

from antistrat.api import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_maps():
    assert client.get("/maps").json() == {"maps": ["haven", "lotus"]}
