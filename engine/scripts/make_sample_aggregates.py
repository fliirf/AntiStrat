"""Write SYNTHETIC sample aggregates so the UI works before the real pipeline runs.

The real `python -m antistrat.pipeline report` overwrites them. Every file is marked
"is_sample": true and the UI shows a banner while they are in use.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from synth import make_dataset  # noqa: E402

from antistrat import pipeline  # noqa: E402
from antistrat.config import AGGREGATES_DIR  # noqa: E402


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        data = make_dataset(tmp / "grid", n_series=30, rounds_per_game=24, signal=0.35)
        out = tmp / "out"
        pipeline.extract(data, out, workers=1)
        pipeline.sites(out, out / "centers.json")
        pipeline.features(out, out / "centers.json")
        pipeline.train(out, out / "metrics.json")
        pipeline.report(out, data, out / "metrics.json", AGGREGATES_DIR, centers_path=out / "centers.json")
    for f in AGGREGATES_DIR.glob("*.json"):
        d = json.loads(f.read_text())
        d["is_sample"] = True
        f.write_text(json.dumps(d, indent=2) + "\n")
    print("sample aggregates ->", AGGREGATES_DIR)


if __name__ == "__main__":
    main()
