"""Render a seeded synthetic or DU disaster scene as standalone interactive HTML."""
import argparse
from pathlib import Path
from pgbm_sim import SceneConfig, TaskConfig, build_scenario, generate_disaster_scene, plot_disaster_scene

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--mode", choices=("synthetic","du_outdoor","real_building","laquila_informed","heidata_neighborhood"), default="du_outdoor")
parser.add_argument("--severity", choices=("light","moderate","severe"), default="moderate")
parser.add_argument("--seed", type=int, default=20260924)
parser.add_argument("--output", default="results/disaster_scene_preview.html")
parser.add_argument("--with-tasks", action="store_true", help="add random tasks inside damaged building footprints and vertical drop-off waypoints")
parser.add_argument("--with-simulation", action="store_true", help="legacy alias for --with-tasks; planner output is not rendered")
parser.add_argument("--show-context", action="store_true", help="include quiet static context buildings for diagnostics")
parser.add_argument("--show-candidate-sites", action="store_true", help="include all unused candidate landing sites")
parser.add_argument("--hide-elevation-guides", action="store_true", help="hide vertical guides for elevated debris")
args=parser.parse_args()
scene=generate_disaster_scene(SceneConfig(mode=args.mode,severity=args.severity,seed=args.seed))
output=Path(args.output); output.parent.mkdir(parents=True,exist_ok=True)
include_tasks=args.with_tasks or args.with_simulation
if include_tasks:
    scenario=build_scenario(SceneConfig(mode=args.mode,severity=args.severity,seed=args.seed), TaskConfig(task_count=6,seed=args.seed+1))
    figure=plot_disaster_scene(
        scene,
        tasks=scenario.tasks,
        show_context=args.show_context,
        show_candidate_sites=args.show_candidate_sites,
        show_elevation_guides=not args.hide_elevation_guides,
    )
else:
    figure=plot_disaster_scene(
        scene,
        show_context=args.show_context,
        show_candidate_sites=args.show_candidate_sites,
        show_elevation_guides=not args.hide_elevation_guides,
    )
figure.write_html(str(output),include_plotlyjs=True)
print("Preview: {}".format(output)); print("Mode: {}".format(args.mode)); print("Obstacles: {}".format(len(scene.environment.obstacles)))
if include_tasks: print("Generated tasks: {}".format(len(scenario.tasks))); print("UAV assignment and route planning: excluded from this environment preview")
