"""Run one complete reproducible PGBM simulation episode and export its report."""

import argparse
import json
from dataclasses import replace
from pathlib import Path

from pgbm_sim import (
    SceneConfig,
    TaskConfig,
    UAVConfig,
    ExecutionConfig,
    apply_recourse,
    build_scenario,
    execute_plan,
    plan_tasks,
    save_scenario,
)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--mode", choices=("synthetic", "du_outdoor", "real_building", "laquila_informed", "heidata_full", "heidata_neighborhood"), default="du_outdoor")
parser.add_argument("--template-path", help="custom scene template or heiDATA full layout configuration")
parser.add_argument("--severity", choices=("light", "moderate", "severe"), default="severe")
parser.add_argument("--seed", type=int, default=20260924)
parser.add_argument("--task-count", type=int, default=6)
parser.add_argument("--uav-count", type=int, default=3)
parser.add_argument("--start-time", type=float, default=30.0, help="planning and execution start time in the scenario time unit")
parser.add_argument(
    "--planner",
    choices=("initial_snapshot_greedy_v1", "pgbm_heuristic_v1", "nearest_task_first"),
    default="pgbm_heuristic_v1",
    help="planner method used for the initial plan",
)
parser.add_argument("--output", default="results/complete_simulation_run.json")
parser.add_argument("--export-only", action="store_true", help="export only the scenario input without planning or execution")
parser.add_argument("--no-recourse", action="store_true", help="run only the initial plan and execution")
args = parser.parse_args()

uavs = UAVConfig(count=args.uav_count)
scenario = build_scenario(
    SceneConfig(mode=args.mode, severity=args.severity, seed=args.seed, uav_count=args.uav_count, template_path=args.template_path),
    TaskConfig(task_count=args.task_count, seed=args.seed + 1),
    scenario_id="{}_{}_{}".format(args.mode, args.severity, args.seed),
    uav_config=uavs,
    execution_config=ExecutionConfig(start_time=args.start_time),
)

output = Path(args.output)
output.parent.mkdir(parents=True, exist_ok=True)
if args.export_only:
    save_scenario(scenario, str(output))
    print("Scenario: {}".format(output))
    print("Schema: {}".format(scenario.schema_version))
    print("Tasks: {}".format(len(scenario.tasks)))
    raise SystemExit(0)

initial_plan = plan_tasks(scenario, uavs, method=args.planner)

if args.no_recourse:
    recourse = None
    combined = scenario
    final_plan = initial_plan
else:
    # One newly reported task is used to exercise the recourse path. It is selected
    # deterministically from a candidate site not already used by the initial set.
    used_positions = {task.dropoff_waypoint for task in scenario.tasks}
    replacement_site = next(site for site in scenario.scene.candidate_sites if site.position not in used_positions)
    replacement = replace(
        scenario.tasks[0],
        identifier="replacement_{}".format(args.seed),
        survivor_position=replacement_site.position,
        dropoff_waypoint=replacement_site.position,
    )
    recourse = apply_recourse(scenario, initial_plan, (replacement,), uavs)
    combined = replace(scenario, tasks=tuple(scenario.tasks) + (replacement,))
    final_plan = recourse.revised_plan
execution = execute_plan(combined, final_plan, uavs)

scenario_path = output.with_name(output.stem + ".scenario.json")
save_scenario(scenario, str(scenario_path))
report = {
    "schema_version": "simulation_run.v2",
    "scenario_file": str(scenario_path),
    "scenario": scenario.as_dict(),
    "uav_config": uavs.as_dict(),
    "initial_plan": initial_plan.as_dict(),
    "recourse": None if recourse is None else recourse.as_dict(),
    "execution": execution.as_dict(),
}
output.write_text(json.dumps(report, sort_keys=True, indent=2), encoding="utf-8")
print("Run report: {}".format(output))
print("Scenario: {}".format(scenario_path))
print("Initial tasks: {}".format(len(scenario.tasks)))
print("Recourse: {}".format("disabled" if recourse is None else "enabled"))
print("Served: {}".format(len(execution.served_task_ids)))
print("Missed: {}".format(len(execution.missed_task_ids)))
print("Safe return rate: {:.3f}".format(execution.safe_return_rate))
