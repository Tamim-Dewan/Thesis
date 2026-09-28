"""Run the paired PGBM V1 and V2 task replacement recourse matrix."""

import argparse

from pgbm_sim.v2.experiment import (
    V2ExperimentConfig,
    write_v2_matrix,
    write_v2_matrix_against_v1_reference,
)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--seeds", type=int, nargs="+", default=list(range(101, 111)))
parser.add_argument("--modes", nargs="+", choices=("synthetic", "du_outdoor"), default=["synthetic", "du_outdoor"])
parser.add_argument("--task-counts", type=int, nargs="+", default=[30, 60, 90])
parser.add_argument("--uav-counts", type=int, nargs="+", default=[3, 5, 8, 10])
parser.add_argument("--severity", choices=("light", "moderate", "severe"), default="moderate")
parser.add_argument("--horizon-minutes", type=float, default=120.0)
parser.add_argument("--phase-weights", type=float, nargs=3, default=[3.0, 2.0, 1.0], metavar=("HIGH", "MEDIUM", "LOW"))
parser.add_argument("--turnaround-minutes", type=float, default=5.0)
parser.add_argument("--max-pending-tasks", type=int, default=8)
parser.add_argument("--max-candidate-plans", type=int, default=50000)
parser.add_argument(
    "--output",
    default="results/pgbm_v2_recourse_experiments/raw_metrics/pgbm_v2_paired_matrix_metrics_tasks_30_60_90_uavs_3_5_8_10_seeds_101_110.csv",
)
parser.add_argument(
    "--trace-output",
    default="results/pgbm_v2_recourse_experiments/decision_traces/pgbm_v2_decision_traces.jsonl",
)
parser.add_argument(
    "--v1-reference",
    default=(
        "results/pgbm_v1_two_hour_experiments/raw_metrics/"
        "pgbm_v1_two_hour_matrix_metrics_tasks_30_60_90_uavs_3_5_8_10_seeds_101_110.csv"
    ),
    help="Canonical preserved V1 matrix used for the comparison rows.",
)
parser.add_argument(
    "--rerun-v1",
    action="store_true",
    help="Rerun V1 in memory for every case instead of reusing the preserved V1 matrix.",
)
args = parser.parse_args()

config = V2ExperimentConfig(
    name="pgbm_v2_task_replacement_recourse",
    severity=args.severity,
    horizon_minutes=args.horizon_minutes,
    arrival_profile="three_phase",
    phase_weights=tuple(args.phase_weights),
    turnaround_minutes=args.turnaround_minutes,
    max_pending_tasks=args.max_pending_tasks,
    max_candidate_plans=args.max_candidate_plans,
)
if args.rerun_v1:
    records = write_v2_matrix(
        args.output,
        args.trace_output,
        args.seeds,
        modes=args.modes,
        task_counts=args.task_counts,
        uav_counts=args.uav_counts,
        config=config,
    )
else:
    records = write_v2_matrix_against_v1_reference(
        args.v1_reference,
        args.output,
        args.trace_output,
        args.seeds,
        modes=args.modes,
        task_counts=args.task_counts,
        uav_counts=args.uav_counts,
        config=config,
    )
print("Paired records: {}".format(len(records)))
print("Episodes: {}".format(len(records) // 2))
print("Metrics: {}".format(args.output))
print("Decision traces: {}".format(args.trace_output))
