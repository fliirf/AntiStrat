---
date: 2026-11-27
who: Rafli & Aisy
tool: Claude
issue: -
pr: "-"
phase: plan
outcome: edited
minutes_ai: 180          # time spent prompting + reviewing
minutes_manual_est: 900    # honest guess: how long by hand
highlight: true         # true = candidate for the case study / video
---

# Scope the idea against real data and plan the build

## Goal
Before writing product code, check whether our "read the opponent" idea is actually
supported by the GRID data, then turn it into a plan we can finish by 10 Jan.

## Prompt / instruction
> Test which signals predict the attack site: round history and between-round adaptation,
> or in-round tells (first-15-second utility, first contact). Then split the work into
> Linear issues with milestones for a two-person team.

## What the AI produced
- A quick analysis on the full dataset (run outside the repo; only aggregates kept).
- A project brief, a Linear project with 5 milestones and issues MUH-5..MUH-24.
- The repo skeleton: LICENSE, data-guard `.gitignore`, CI check (MUH-5).

## What we changed and why
- The first concept leaned on modelling how teams adapt between rounds. The numbers said
  that signal is mostly noise, so we moved the core of the engine to in-round tells and
  only show adaptation when it is statistically significant.
- Cut the MVP to Haven + Lotus (most samples, 3 sites) and set a 20 Dec MVP gate with a
  fallback (scouting + round-read only) if the match engine slips.
- Rebalanced the task split between the two of us.

## Result
Aggregate findings that shaped the product:
- Site guess from history: 48.6% vs 49.3% map baseline (no gain).
- First-15-second attacker utility: Haven 42.9% → 57.4%, Lotus 40.2% → 54.7%.
- First-kill location (median at 21 s): 49.1% → 66.7%.

## Lesson
Validate the core assumption with the data on day one; the AI made that a 3-hour job
instead of a week, and it changed the product.

## Evidence
- Linear project: VALORANT Tactical Manager (milestones M1–M5)
- Commit 69072f1 (repo skeleton)
