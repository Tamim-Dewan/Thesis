"""Render one uncluttered simulation-world inspection view."""

import argparse
from pathlib import Path

from pgbm_sim import (
    SceneConfig,
    generate_disaster_scene,
    plot_building_layout,
    plot_collision_view,
    plot_damage_view,
    plot_map_view,
)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--mode", choices=("du_outdoor", "synthetic", "laquila_informed"), default="du_outdoor")
parser.add_argument("--severity", choices=("light", "moderate", "severe"), default="moderate")
parser.add_argument("--seed", type=int, default=20260924)
parser.add_argument("--view", choices=("map", "layout", "damage", "collision"), required=True)
parser.add_argument("--output")
args = parser.parse_args()

scene = generate_disaster_scene(SceneConfig(mode=args.mode, severity=args.severity, seed=args.seed))
figures = {
    "map": plot_map_view,
    "layout": plot_building_layout,
    "damage": plot_damage_view,
    "collision": plot_collision_view,
}
output = Path(args.output or "results/{}_{}_view.html".format(args.mode, args.view))
output.parent.mkdir(parents=True, exist_ok=True)
figures[args.view](scene).write_html(str(output), include_plotlyjs=True)
print("View: {}".format(output))
