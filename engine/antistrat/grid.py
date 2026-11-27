"""Helpers for reading GRID feeds and the ability supplement (streamed, never decompressed)."""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Iterator

import zstandard

from antistrat.config import DATA_DIR


def ts(s: str) -> float:
    """ISO-8601 UTC timestamp -> epoch seconds."""
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def read_jsonl_zst(path: Path) -> Iterator[dict]:
    with zstandard.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def feed_path(series_id: str, data_dir: Path = DATA_DIR) -> Path:
    return data_dir / "val" / f"events_{series_id}_grid.jsonl.zst"


def supplement_path(series_id: str, data_dir: Path = DATA_DIR) -> Path:
    return data_dir / "val-ability-supplements" / f"{series_id}.jsonl.zst"


def read_series_index(data_dir: Path = DATA_DIR) -> list[dict]:
    with open(data_dir / "val" / "series.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def is_vct(event: str) -> bool:
    """True for top-tier VCT events (Americas league and Masters), False for Game Changers."""
    e = event.lower()
    return "game changers" not in e and ("vct" in e or "masters" in e or "champions" in e)
