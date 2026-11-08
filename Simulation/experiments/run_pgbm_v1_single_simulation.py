"""Run one two hour Initial Solution V1 event episode."""

import argparse
import json
from pathlib import Path

from pgbm_sim import (
    EventSimulationConfig,
    SceneConfig,
    TaskConfig,
    UAVConfig,
    build_scenario,
    run_event_simulation,
    save_scenario,
)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--mode", choices=("synthetic", "du_outdoor"), default="du_outdoor")
parser.add_argument("--severity", choices=("light", "moderate", "severe"), default="moderate")
parser.add_argument("--seed", type=int, default=20260924)
parser.add_argument("--task-count", type=int, default=6)
parser.add_argument("--uav-count", type=int, default=3)
parser.add_argument("--horizon-minutes", type=float, default=120.0)
parser.add_argument("--phase-weights", type=float, nargs=3, default=[3.0, 2.0, 1.0], metavar=("HIGH", "MEDIUM", "LOW"))
parser.add_argument("--turnaround-minutes", type=float, default=5.0)
parser.add_argument("--max-pending-tasks", type=int, default=8)
parser.add_argument("--max-candidate-plans", type=int, default=50000)
parser.add_argument(
    "--output",
    default=(
        "results/pgbm_v1_two_hour_experiments/visualizations/single_run/"
        "pgbm_v1_single_run_report.json"
    ),
)
args = parser.parse_args()

uavs = UAVConfig(count=args.uav_count)
scenario = build_scenario(
    SceneConfig(mode=args.mode, severity=args.severity, seed=args.seed, uav_count=args.uav_count),
    TaskConfig(
        task_count=args.task_count,
        seed=args.seed + 1,
        arrival_profile="three_phase",
        horizon_minutes=args.horizon_minutes,
        phase_weights=tuple(args.phase_weights),
    ),
    scenario_id="{}_{}_v1_{}".format(args.mode, args.severity, args.seed),
    uav_config=uavs,
)
result = run_event_simulation(
    scenario,
    uavs,
    config=EventSimulationConfig(
        horizon_minutes=args.horizon_minutes,
        turnaround_minutes=args.turnaround_minutes,
        max_pending_tasks=args.max_pending_tasks,
        max_candidate_plans=args.max_candidate_plans,
    ),
)

output = Path(args.output)
output.parent.mkdir(parents=True, exist_ok=True)
scenario_path = output.with_name(output.stem + ".scenario.json")
save_scenario(scenario, str(scenario_path))
report = {
    "schema_version": "simulation_run.v3",
    "scenario_file": str(scenario_path),
    "scenario": scenario.as_dict(),
    "simulation_config": EventSimulationConfig(
        horizon_minutes=args.horizon_minutes,
        turnaround_minutes=args.turnaround_minutes,
        max_pending_tasks=args.max_pending_tasks,
        max_candidate_plans=args.max_candidate_plans,
    ).as_dict(),
    "result": result.as_dict(),
}
output.write_text(json.dumps(report, sort_keys=True, indent=2), encoding="utf-8")
print("Run report: {}".format(output))
print("Scenario: {}".format(scenario_path))
print("Arrival phases: {}".format(result.phase_counts))
print("Served: {}".format(len(result.served_task_ids)))
print("Deferred: {}".format(len(result.deferred_task_ids)))
print("Dispatches: {}".format(result.dispatch_count))
print("Runtime: {:.6f}s".format(result.runtime_seconds))
