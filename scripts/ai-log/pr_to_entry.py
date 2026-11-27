#!/usr/bin/env python3
"""Turn the 'AI usage' section of a merged PR into docs/ai-workflow/log/auto/pr-<n>.md.

Reads PR_NUMBER, PR_TITLE, PR_BODY, PR_AUTHOR, PR_MERGED_AT from the environment
(set by .github/workflows/ai-log.yml). Exits quietly if the section is empty.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIELDS = ["Tool", "Prompt / instruction", "What the AI produced", "What we changed and why",
          "Time with AI (min)", "Estimated by hand (min)"]


def field(section: str, name: str) -> str:
    m = re.search(rf"^\s*[-*]\s*\*\*{re.escape(name)}:\*\*[ \t]*(.*)$", section, re.M)
    value = (m.group(1).strip() if m else "")
    return "" if value.startswith("<!--") else value


def num(value: str) -> int:
    m = re.search(r"\d+", value)
    return int(m.group(0)) if m else 0


def main() -> None:
    body = os.environ.get("PR_BODY", "").replace("\r\n", "\n")
    m = re.search(r"^## AI usage\s*\n(.*?)(?=^## |\Z)", body, re.S | re.M)
    if not m:
        print("no AI usage section"); return
    section = m.group(1)
    values = {f: field(section, f) for f in FIELDS}
    if not values["Tool"] or values["Tool"].lower() in {"none", "-", "n/a"}:
        print("AI usage section empty"); return

    n = os.environ["PR_NUMBER"]
    date = os.environ.get("PR_MERGED_AT", "")[:10]
    issue = re.search(r"\bMUH-\d+\b", os.environ.get("PR_TITLE", "") + " " + body)
    text = f"""---
date: {date}
who: {os.environ.get('PR_AUTHOR', '-')}
tool: {values['Tool']}
issue: {issue.group(0) if issue else '-'}
pr: "#{n}"
phase: -
outcome: {'edited' if values['What we changed and why'] else 'accepted'}
minutes_ai: {num(values['Time with AI (min)'])}
minutes_manual_est: {num(values['Estimated by hand (min)'])}
highlight: false
---

# {os.environ.get('PR_TITLE', f'PR #{n}')}

_Auto-captured from PR #{n} when it was merged._

## Prompt / instruction
{values['Prompt / instruction'] or '-'}

## What the AI produced
{values['What the AI produced'] or '-'}

## What we changed and why
{values['What we changed and why'] or '-'}
"""
    out = ROOT / "docs" / "ai-workflow" / "log" / "auto" / f"pr-{n}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(out.relative_to(ROOT))


if __name__ == "__main__":
    main()
