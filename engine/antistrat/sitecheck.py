"""Draw each map's plant clusters as a local SVG so the A/B/C letters can be checked against
the in-game minimap. Written to OUT_DIR/site_check (outside the repo): it plots GRID positions.
"""
from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

COLORS = {"A": "#ff4655", "B": "#4aa3ff", "C": "#3fb950"}
SIZE = 600


def draw(plants: pd.DataFrame, centers: dict, out_dir: Path, sample: int = 1500, seed: int = 0) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for m, g in plants.groupby("map"):
        if m not in centers:
            continue
        g = g.sample(min(sample, len(g)), random_state=seed)
        xs, ys = g["plant_x"].astype(float), g["plant_y"].astype(float)
        lo_x, hi_x, lo_y, hi_y = xs.min(), xs.max(), ys.min(), ys.max()
        span = max(hi_x - lo_x, hi_y - lo_y) or 1.0
        sx = lambda x: 20 + (x - lo_x) / span * (SIZE - 40)  # noqa: E731
        sy = lambda y: SIZE - 20 - (y - lo_y) / span * (SIZE - 40)  # noqa: E731
        dots = "".join(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="2" fill="{COLORS.get(s, "#999")}" opacity=".5"/>'
                       for x, y, s in zip(xs, ys, g["site"]))
        labels = "".join(f'<text x="{sx(cx):.1f}" y="{sy(cy):.1f}" font-size="28" font-weight="700" fill="#fff" '
                         f'stroke="#000" stroke-width="1" text-anchor="middle">{s}</text>'
                         for s, (cx, cy) in centers[m].items())
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{SIZE}" height="{SIZE + 30}">'
               f'<rect width="100%" height="100%" fill="#0f1419"/>{dots}{labels}'
               f'<text x="10" y="{SIZE + 22}" fill="#ccc" font-size="14">{m}: plant positions by site letter '
               f'(x right, y up as in the feed). Compare with the minimap; swap letters in site_letters.json.</text></svg>')
        p = out_dir / f"{m}.svg"
        p.write_text(svg)
        paths.append(p)
    return paths
