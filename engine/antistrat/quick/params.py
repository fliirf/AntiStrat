"""Tunable coefficients of the quick-mode engine.

`Params.luau()` holds the values from the Luau prototype (as recorded in the project brief);
`Params()` holds the current tuned values. Every coefficient is an additive term on the
logit z of a duel unless noted otherwise:

    P(A wins duel) = 1 / (1 + exp(-z))
    z = skill_scale * (S_A - S_B) + weapon + armor + hold + post-plant + trade
        + manpower + clutch + side bias

S is the duel skill on the 1-20 attribute scale (see model.duel_skill), plus a per-map form
draw ~ N(0, form_noise * (21 - consistency)).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace


@dataclass(frozen=True)
class Params:
    # --- duel -----------------------------------------------------------------------
    skill_scale: float = 0.06
    hold_bonus: float = 0.28          # defender holding an angle vs an attacker before the plant
    postplant_bonus: float = 0.10     # attacker holding the planted spike vs a retaker
    trade_bonus: float = 0.60         # the trader in a trade duel
    clutch_scale: float = 0.04        # lone player: per point of (clutch+composure)/2 above 10
    form_noise: float = 0.06          # sd of per-map form = form_noise * (21 - consistency)
    manpower_edge: float = 0.25       # per extra alive teammate over the opponent (crossfire)
    # weapon edge by (stronger tier, weaker tier); tier 1 pistol, 2 SMG/shotgun/force, 3 rifle
    weapon_edge: dict = field(default_factory=lambda: {(3, 1): 0.6, (3, 2): 0.4, (2, 1): 0.8})
    armor_edge: float = 0.15          # per armor level (0 none, 1 light, 2 heavy)
    # --- round flow -----------------------------------------------------------------
    trade_base: float = 0.40          # chance a teammate is in position to trade a death
    trade_attr: float = 0.15          # + per 10 points of (trading+teamwork)/2 above 10
    plant_c: float = -0.9             # logit of planting before the next duel at even numbers
    plant_k: float = 0.9              # + per extra alive attacker
    defuse_time_ok: float = 0.92      # chance a retake that clears the site still has time to defuse
    save_threshold: int = 3           # lone attacker vs >= this many defenders, no plant: may save
    save_prob: float = 0.35           # chance they save instead of forcing the clutch
    # --- side bias per map (logit added to the attacker in every duel) ----------------
    use_map_bias: bool = True

    @classmethod
    def luau(cls) -> "Params":
        """Coefficients of the Luau prototype (brief: SKILL_SCALE 0.07, HOLD 0.55, POSTPLANT
        0.10, TRADE 0.60, CLUTCH 0.04, FORM_NOISE 0.15, WEAPON_EDGE 1.6/0.6/0.7, no side bias).
        Terms the Luau build did not have are switched off."""
        return cls(skill_scale=0.07, hold_bonus=0.55, postplant_bonus=0.10, trade_bonus=0.60, clutch_scale=0.04,
                   form_noise=0.15, manpower_edge=0.0,
                   weapon_edge={(3, 1): 1.6, (3, 2): 0.6, (2, 1): 0.7}, armor_edge=0.0,
                   save_prob=0.0, use_map_bias=False)

    def with_(self, **kw) -> "Params":
        return replace(self, **kw)

    def weapon(self, tier_a: int, tier_b: int) -> float:
        if tier_a == tier_b:
            return 0.0
        hi, lo = max(tier_a, tier_b), min(tier_a, tier_b)
        edge = self.weapon_edge.get((hi, lo), 0.0)
        return edge if tier_a > tier_b else -edge

    def as_dict(self) -> dict:
        d = asdict(self)
        d["weapon_edge"] = {f"{k[0]}v{k[1]}": v for k, v in self.weapon_edge.items()}
        return d
