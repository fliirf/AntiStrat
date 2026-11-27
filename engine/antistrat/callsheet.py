"""Call sheet: the rules a coaching staff can prepare before a match and execute in it.

The data showed that a generic in-round read (early utility, first contact) beats knowing
the opponent's site habits, so the rules here are per map and learned from every team.
Every rule is found on the older 80% of series and its hit rate is re-measured on the
newer 20%, which is the number shown. Opponent-specific traits are limited to the ones
that stayed stable over time (pace, round 2 after a lost pistol, retakes), each with a
confidence label. All output is aggregate.
"""
from __future__ import annotations

import pandas as pd

from antistrat.edges import FAST_PLANT_S, add_context, timing
from antistrat.model import time_split

MIN_RULE_N = 30       # older rounds needed to state a rule
MIN_RULE_RATE = 0.6   # a rule must name a site at least this often to be worth a call
ROTATE_RATE = 0.75    # at or above this (on newer rounds), the call is a rotation
MIN_TRAIT_N = 10


def _rule(train: pd.DataFrame, test: pd.DataFrame, mask_tr, mask_te, site: str, when: str, kind: str,
          min_n: int = MIN_RULE_N) -> dict | None:
    tr, te = train[mask_tr], test[mask_te]
    if len(tr) < min_n:
        return None
    rate = float((tr["site"] == site).mean())
    if rate < MIN_RULE_RATE:
        return None
    checked = len(te) >= 10
    shown_rate = float((te["site"] == site).mean()) if checked else rate
    if checked and shown_rate < MIN_RULE_RATE:
        return None  # did not hold up on newer matches
    call = "rotate" if shown_rate >= ROTATE_RATE else "lean"
    return {"kind": kind, "when": when, "site": site, "rate": round(shown_rate, 3),
            "rate_older": round(rate, 3), "n_older": int(len(tr)), "n_newer": int(len(te)),
            "rate_source": "newer" if checked else "older",
            "call": call,
            "text": f"{when}: they plant {site} {shown_rate:.0%} of the time. "
                    + (f"Rotate to {site}." if call == "rotate" else f"Lean one player toward {site}, keep the rest.")}


def map_call_sheet(features: pd.DataFrame, m: str, sites: list[str], min_n: int = MIN_RULE_N) -> dict:
    d = features[(features["map"] == m) & features["site"].notna()]
    train, test = time_split(d)
    rules = []
    for s in sites:
        others = [o for o in sites if o != s]
        for k in (2, 3):
            def aimed(df, k=k, s=s, others=others):
                return (df[f"util_aim_{s}"] >= k) & (df[f"util_aim_{s}"] > df[[f"util_aim_{o}" for o in others]].max(axis=1))
            r = _rule(train, test, aimed(train), aimed(test), s,
                      f"In the first 15 s, {k}+ attacker utility aimed at {s} (more than elsewhere)", "early_utility", min_n)
            if r:
                rules.append(r)
        for by_att, who in ((1, "attackers"), (0, "defenders")):
            def contact(df, s=s, by_att=by_att):
                return (df[f"fk_site_{s}"] == 1) & (df["fk_by_att"] == by_att)
            r = _rule(train, test, contact(train), contact(test), s,
                      f"First kill near {s} before the plant, won by the {who}", "contact", min_n)
            if r:
                rules.append(r)
    # Keep the stronger utility rule per site (2+ vs 3+) unless the stricter one rotates.
    best: dict[tuple, dict] = {}
    for r in rules:
        key = (r["kind"], r["site"], r["when"].split(",")[-1] if r["kind"] == "contact" else "")
        if key not in best or (r["call"] == "rotate" and best[key]["call"] != "rotate") or \
                (r["call"] == best[key]["call"] and r["n_older"] > best[key]["n_older"]):
            best[key] = r
    rules = sorted(best.values(), key=lambda r: (r["kind"] != "early_utility", -r["rate"]))
    all_rows = features[features["map"] == m]
    return {"map": m, "rules": rules, "timing": timing(all_rows),
            "fallback": "No trigger: hold the default setup. Their site habits are close to the map "
                        "average, so don't stack on habit alone.",
            "n_older": int(len(train)), "n_newer": int(len(test))}


def opponent_traits(features: pd.DataFrame, team: str, m: str, sites: list[str]) -> list[dict]:
    """Traits that stayed stable across periods in the data, with a confidence label."""
    d = add_context(features[features["map"] == m])
    att, dfn = d[d["att"] == team], d[d["dfn"] == team]
    out = []
    pl, pl_map = att["plant_t"].dropna(), d["plant_t"].dropna()
    if len(pl) >= MIN_TRAIT_N:
        diff = float(pl.median() - pl_map.median())
        pace = "faster than" if diff < -3 else "slower than" if diff > 3 else "about the same pace as"
        out.append({"trait": "pace", "confidence": "medium", "n": int(len(pl)),
                    "value": round(float(pl.median()), 1), "map_value": round(float(pl_map.median()), 1),
                    "fast_share": round(float((pl < FAST_PLANT_S).mean()), 3),
                    "text": f"They plant at {pl.median():.0f} s on average ({pace} the map's "
                            f"{pl_map.median():.0f} s); {(pl < FAST_PLANT_S).mean():.0%} of plants come before "
                            f"{FAST_PLANT_S:.0f} s."})
    r2 = att[att["after_pistol"] == "lost"]
    r2m = d[d["after_pistol"] == "lost"]
    if len(r2) >= 5:
        rate, mr = float((r2["buy"] != "eco").mean()), float((r2m["buy"] != "eco").mean())
        conf = "medium" if len(r2) >= 15 else "low"
        out.append({"trait": "force_after_pistol", "confidence": conf, "n": int(len(r2)),
                    "value": round(rate, 3), "map_value": round(mr, 3),
                    "text": f"After losing their attack pistol they buy in round 2 {rate:.0%} of the time "
                            f"(map {mr:.0%}). " + ("Expect a force: play for trades, not anti-eco." if rate >= 0.5
                                                   else "Expect a save: anti-eco positions are worth it.")})
    for s in sites:
        inn, ref = dfn[dfn["site"] == s], d[(d["site"] == s) & (d["dfn"] != team)]
        if len(inn) >= MIN_TRAIT_N and len(ref) >= MIN_TRAIT_N:
            rate, mr = float((inn["winside"] == "attacker").mean()), float((ref["winside"] == "attacker").mean())
            if abs(rate - mr) >= 0.1:
                out.append({"trait": "retake", "site": s, "confidence": "low", "n": int(len(inn)),
                            "value": round(rate, 3), "map_value": round(mr, 3),
                            "text": f"When attackers plant {s} against them, attackers win {rate:.0%} (map {mr:.0%}): "
                                    + (f"their {s} retake is weak, a plant there is worth fighting for."
                                       if rate > mr else f"their {s} retake is strong.")})
    return out
