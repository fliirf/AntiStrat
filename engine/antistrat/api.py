"""FastAPI app. Serves aggregate results only, never raw GRID data."""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from antistrat.config import AGGREGATES_DIR
from antistrat.sim import Assumptions, simulate, suggest_plan

app = FastAPI(title="AntiStrat API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ANTISTRAT_CORS", "http://localhost:3000").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

DEFAULT_MAPS = ["haven", "lotus"]
_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def agg_dir() -> Path:
    return Path(os.environ.get("ANTISTRAT_AGG_DIR", AGGREGATES_DIR))


def _read(name: str) -> dict:
    path = agg_dir() / name
    if not path.exists():
        raise HTTPException(404, f"{name} not found; run the pipeline report step")
    return json.loads(path.read_text())


def _maps() -> list[str]:
    path = agg_dir() / "index.json"
    if path.exists():
        return json.loads(path.read_text()).get("maps") or DEFAULT_MAPS
    return DEFAULT_MAPS


def _report(team: str, map_name: str) -> dict:
    if not _ID.match(team) or not _ID.match(map_name) or map_name not in _maps():
        raise HTTPException(400, "bad team or map")
    return _read(f"{team}_{map_name}.json")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/maps")
def maps() -> dict:
    return {"maps": _maps()}


@app.get("/index")
def index() -> dict:
    return _read("index.json")


@app.get("/report/{team}/{map_name}")
def report(team: str, map_name: str) -> dict:
    return _report(team, map_name)


@app.get("/suggest/{team}/{map_name}")
def suggest(team: str, map_name: str) -> dict:
    return {"plan": suggest_plan(_report(team, map_name), _assumptions())}


def _assumptions() -> Assumptions:
    path = agg_dir() / "index.json"
    cal = json.loads(path.read_text()).get("sim_calibration") if path.exists() else None
    return Assumptions.from_calibration(cal)


class SimRequest(BaseModel):
    team: str
    map: str
    plan: list[str] = Field(default_factory=list, max_length=24)
    start_side: str = Field("defense", pattern="^(defense|attack)$")
    n: int = Field(5000, ge=100, le=20000)
    seed: int = 0


@app.post("/simulate")
def run_simulation(req: SimRequest) -> dict:
    rep = _report(req.team, req.map)
    for p in req.plan:
        if p not in ("default", "read") and not (p.startswith("stack:") and p[6:] in rep["site_mix_smoothed"]):
            raise HTTPException(400, f"unknown plan '{p}'")
    idx = _read("index.json")
    economy = idx.get("economy")
    if not economy:
        raise HTTPException(404, "economy model missing from index.json")
    a = Assumptions.from_calibration(idx.get("sim_calibration"))
    return asdict(simulate(rep, economy, req.plan, req.start_side, req.n, req.seed, a))
