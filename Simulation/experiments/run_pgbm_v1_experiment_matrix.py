"""Run the PGBM V1 two hour multi seed experiment matrix."""

import argparse

from pgbm_sim import ResearchExperimentConfig, write_experiment_matrix


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--seeds", type=int, nargs="+", default=list(range(101, 111)))
parser.add_argument("--modes", nargs="+", choices=("synthetic", "du_outdoor"), default=["synthetic", "du_outdoor"])
parser.add_argument("--severity", choices=("light", "moderate", "severe"), default="moderate")
parser.add_argument("--task-counts", type=int, nargs="+", default=[30, 60, 90])
parser.add_argument("--uav-counts", type=int, nargs="+", default=[3, 5, 8, 10])
parser.add_argument("--horizon-minutes", type=float, default=120.0)
parser.add_argument("--phase-weights", type=float, nargs=3, default=[3.0, 2.0, 1.0], metavar=("HIGH", "MEDIUM", "LOW"))
parser.add_argument("--turnaround-minutes", type=float, default=5.0)
parser.add_argument("--max-pending-tasks", type=int, default=8)
parser.add_argument("--max-candidate-plans", type=int, default=50000)
parser.add_argument(
    "--output",
    default=(
        "results/pgbm_v1_two_hour_experiments/raw_metrics/"
        "pgbm_v1_two_hour_matrix_metrics_tasks_30_60_90_uavs_3_5_8_10_seeds_101_110.csv"
    ),
)
args = parser.parse_args()

config = ResearchExperimentConfig(
    name="pgbm_v1_two_hour_experiment_matrix",
    severity=args.severity,
    dynamic=True,
    horizon_minutes=args.horizon_minutes,
    arrival_profile="three_phase",
    phase_weights=tuple(args.phase_weights),
    turnaround_minutes=args.turnaround_minutes,
    max_pending_tasks=args.max_pending_tasks,
    max_candidate_plans=args.max_candidate_plans,
    planner_methods=("pgbm_initial_bruteforce_v1",),
)
records = write_experiment_matrix(
    args.seeds,
    args.output,
    modes=args.modes,
    task_counts=args.task_counts,
    uav_counts=args.uav_counts,
    config=config,
)
print("Experiment records: {}".format(len(records)))
print("Metrics: {}".format(args.output))
print("Horizon: {} minutes".format(args.horizon_minutes))
print("Arrival weights: {}".format(tuple(args.phase_weights)))
print("Seeds: {}".format(len(args.seeds)))
