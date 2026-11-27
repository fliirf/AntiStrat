#!/usr/bin/env python3
"""Create a new AI workflow log entry from docs/ai-workflow/TEMPLATE.md.

Usage:
  python scripts/ai-log/new_entry.py "cluster plant sites" --tool Junie --issue MUH-8 --who Rafli
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "ai-workflow"


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "entry"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("title")
    p.add_argument("--tool", default="Junie")
    p.add_argument("--issue", default="-")
    p.add_argument("--pr", default="-")
    p.add_argument("--who", default="Rafli")
    p.add_argument("--phase", default="engine")
    p.add_argument("--date", default=dt.date.today().isoformat())
    a = p.parse_args()

    path = DOCS / "log" / f"{a.date}-{slugify(a.title)}.md"
    if path.exists():
        raise SystemExit(f"already exists: {path.relative_to(ROOT)}")

    text = (DOCS / "TEMPLATE.md").read_text(encoding="utf-8")
    fields = {"date": a.date, "who": a.who, "tool": a.tool, "issue": a.issue,
              "pr": f'"{a.pr}"', "phase": a.phase, "outcome": "accepted"}
    for key, value in fields.items():
        text = re.sub(rf"^{key}:.*$", f"{key}: {value}", text, count=1, flags=re.M)
    text = text.replace("# <One-line title: what we asked the AI to do>", f"# {a.title}")
    text = text.replace("YYYY-MM-DD-slug", f"{a.date}-{slugify(a.title)}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
