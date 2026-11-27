"""Ability -> agent, from game knowledge (not data). Abilities missing here are shown by name only."""
from __future__ import annotations

_AGENTS = {
    "Astra": ["stars", "gravity-well", "nova-pulse", "nebula-dissipate"],
    "Breach": ["aftershock", "flashpoint", "fault-line", "rolling-thunder"],
    "Brimstone": ["stim-beacon", "incendiary", "sky-smoke", "orbital-strike"],
    "Chamber": ["trademark", "headhunter", "rendezvous", "tour-de-force"],
    "Clove": ["meddle", "pick-me-up", "ruse", "not-dead-yet"],
    "Cypher": ["trapwire", "cyber-cage", "spycam", "neural-theft"],
    "Deadlock": ["barrier-mesh", "gravnet", "sonic-sensor", "annihilation"],
    "Fade": ["haunt", "prowler", "seize", "nightfall"],
    "Gekko": ["dizzy", "wingman", "mosh-pit", "thrash"],
    "Harbor": ["cascade", "cove", "high-tide", "reckoning"],
    "Iso": ["contingency", "double-tap", "undercut", "kill-contract"],
    "Jett": ["cloudburst", "updraft", "tailwind"],
    "KAY/O": ["frag-ment", "flash-drive", "zero-point", "null-cmd"],
    "Killjoy": ["alarmbot", "turret", "nanoswarm", "lockdown"],
    "Neon": ["fast-lane", "relay-bolt", "high-gear"],
    "Omen": ["paranoia", "dark-cover", "shrouded-step", "from-the-shadows"],
    "Phoenix": ["blaze", "curveball", "hot-hands"],
    "Raze": ["boom-bot", "blast-pack", "paint-shells", "showstopper"],
    "Reyna": ["leer", "devour"],
    "Sage": ["barrier-orb", "slow-orb", "healing-orb", "resurrection"],
    "Skye": ["regrowth", "trailblazer", "guiding-light", "seekers"],
    "Sova": ["owl-drone", "shock-bolt", "recon-bolt", "hunter's-fury"],
    "Tejo": ["stealth-drone", "special-delivery", "guided-salvo", "armageddon"],
    "Viper": ["poison-cloud", "toxic-screen", "snake-bite"],
    "Vyse": ["razorvine", "shear", "arc-rose", "steel-garden"],
    "Waylay": ["saturate", "light-speed", "refract", "convergent-paths"],
    "Yoru": ["fakeout", "blindside", "gatecrash", "dimensional-drift"],
}
ABILITY_AGENT = {a: agent for agent, abilities in _AGENTS.items() for a in abilities}


def agent_of(ability: str | None) -> str | None:
    return ABILITY_AGENT.get(ability or "")
