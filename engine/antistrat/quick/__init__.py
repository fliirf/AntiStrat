"""Quick-mode ("mode Cepat") match engine: VALORANT rounds as chains of logistic duels with
the real economy, trades, plant/post-plant/defuse, clutches and overtime. Port of the Luau
prototype; see params.py for the coefficients and harness.py for calibration."""
from .match import MapResult, play_map
from .model import Player, Team
from .params import Params

__all__ = ["MapResult", "Params", "Player", "Team", "play_map"]
