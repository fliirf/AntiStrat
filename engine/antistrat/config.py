"""Paths for the GRID data and pipeline output.

Both live OUTSIDE the repository so licensed data can never be committed.
"""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Local clone of the GRID starter repo (never inside this repo).
DATA_DIR = Path(
    os.environ.get("STL_DATA_DIR", REPO_ROOT.parent / "stl-hackathon-2026-grid-starter")
)

# Extracted tables (contain GRID data, so also kept outside the repo).
OUT_DIR = Path(os.environ.get("ANTISTRAT_OUT_DIR", REPO_ROOT.parent / "antistrat-out"))

# Aggregates that are safe to commit and deploy (no raw rows).
AGGREGATES_DIR = REPO_ROOT / "web" / "public" / "aggregates"


def assert_outside_repo(path: Path) -> Path:
    """Refuse to write extracted data inside the repository."""
    resolved = path.resolve()
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        raise ValueError(f"{resolved} is inside the repo; extracted data must live outside it")
    return resolved
