---
date: YYYY-MM-DD
who: Rafli | Aisy
tool: Junie | Air | AI Assistant | Claude | other
issue: MUH-00            # Linear issue, or "-"
pr: "-"                  # PR number, or "-"
phase: plan | data | model | engine | ui | debug | docs | video
outcome: accepted | edited | rejected
minutes_ai: 0            # time spent prompting + reviewing
minutes_manual_est: 0    # honest guess: how long by hand
highlight: false         # true = candidate for the case study / video
---

# <One-line title: what we asked the AI to do>

## Goal
What we needed and why (1–2 sentences).

## Prompt / instruction
> Paste the key prompt (shorten it, but keep the wording). Link the Junie/Air
> session or `.junie/` file if there is one.

## What the AI produced
Files, functions, analysis, or decisions. Link the commit/PR.

## What we changed and why
The human part: what was wrong, missing, or risky, and how we fixed it.
This is the most important section for judges. "Accepted as-is" is fine too.

## Result
Did it work? Numbers if any (tests pass, accuracy, runtime). No raw GRID data.

## Lesson
One line: what we'd do differently, or a prompt pattern that worked.

## Evidence
- Screenshot: `screenshots/YYYY-MM-DD-slug.png` (cropped, no raw data)
- Commit / PR / Linear link
