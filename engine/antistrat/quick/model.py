"""Players and teams for the quick-mode engine (visible attributes 1-20, GDD 'Model pemain')."""
from __future__ import annotations

import random
from dataclasses import dataclass, field

ATTRS = ("aim", "reaksi", "headshot", "spray", "movement", "positioning",
         "trading", "teamwork", "clutch", "composure", "konsistensi")

# GDD 'Rumus duel': S = 0.35 Aim + 0.20 Reaksi + 0.15 HS + 0.10 Spray + 0.10 Movement + 0.10 Positioning
DUEL_WEIGHTS = {"aim": 0.35, "reaksi": 0.20, "headshot": 0.15, "spray": 0.10,
                "movement": 0.10, "positioning": 0.10}


@dataclass
class Player:
    name: str
    attrs: dict[str, float]

    def a(self, key: str) -> float:
        return float(self.attrs.get(key, 10))

    @property
    def duel_skill(self) -> float:
        return sum(w * self.a(k) for k, w in DUEL_WEIGHTS.items())


@dataclass
class Team:
    name: str
    players: list[Player] = field(default_factory=list)

    @classmethod
    def uniform(cls, name: str, level: float = 13.0, **overrides: float) -> "Team":
        """Five identical players with every attribute at `level` (handy for tests)."""
        attrs = {k: level for k in ATTRS}
        attrs.update(overrides)
        return cls(name, [Player(f"{name}{i + 1}", dict(attrs)) for i in range(5)])

    @classmethod
    def random(cls, name: str, rng: random.Random, mean: float = 13.0, sd: float = 2.0,
               shift: float = 0.0) -> "Team":
        """Five players with attributes ~ N(mean, sd), clipped to 1-20; `shift` adds to every
        attribute except consistency (used for the 'team +1 attribute' check)."""
        players = []
        for i in range(5):
            attrs = {}
            for k in ATTRS:
                v = rng.gauss(mean, sd) + (0 if k == "konsistensi" else shift)
                attrs[k] = min(20.0, max(1.0, v))
            players.append(Player(f"{name}{i + 1}", attrs))
        return cls(name, players)
