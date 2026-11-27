#!/usr/bin/env bash
# Fails if any GRID data (or a likely extract of it) is tracked or staged.
set -euo pipefail
pattern='\.(zst|jsonl|parquet|sqlite|duckdb|feather|pkl|joblib|csv)$|stl-hackathon-2026-grid-starter|(^|/)meta/'
bad=$( { git ls-files; git diff --cached --name-only 2>/dev/null || true; } | sort -u | grep -Ei "$pattern" || true)
if [ -n "$bad" ]; then
  echo "ERROR: data files must not be committed:" >&2
  echo "$bad" >&2
  exit 1
fi
echo "OK: no GRID data tracked."
