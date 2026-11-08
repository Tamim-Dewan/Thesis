"""Run the paired PGBM Version 2 control and Version 2.1 cache matrix."""

import argparse

from pgbm_sim.v2_1.experiment import (
    DEFAULT_CACHE_VARIANTS,
    V21ExperimentConfig,
    write_v21_matrix,
)


def main() -> None:
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
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--variants",
        nargs="+",
        choices=("uniform", "water_heavy_sensitivity"),
        default=[name for name, _ in DEFAULT_CACHE_VARIANTS],
    )
    parser.add_argument(
        "--output",
        default=(
            "results/pgbm_v2_1_cache_experiments/raw_metrics/"
            "pgbm_v2_1_cache_matrix_metrics_tasks_30_60_90_uavs_3_5_8_10_seeds_101_110.csv"
        ),
    )
    parser.add_argument(
        "--trace-output",
        default="results/pgbm_v2_1_cache_experiments/decision_traces/pgbm_v2_1_cache_decision_traces.jsonl",
    )
    parser.add_argument(
        "--manifest-output",
        default="results/pgbm_v2_1_cache_experiments/manifests/pgbm_v2_1_cache_manifest.json",
    )
    args = parser.parse_args()

    variant_lookup = {name: prior for name, prior in DEFAULT_CACHE_VARIANTS}
    variants = tuple((name, variant_lookup[name]) for name in args.variants)
    config = V21ExperimentConfig(
        name="pgbm_v2_1_cache_aware_recourse",
        severity=args.severity,
        horizon_minutes=args.horizon_minutes,
        arrival_profile="three_phase",
        phase_weights=tuple(args.phase_weights),
        turnaround_minutes=args.turnaround_minutes,
        max_pending_tasks=args.max_pending_tasks,
        max_candidate_plans=args.max_candidate_plans,
        cache_variant="matrix",
        cache_enabled=True,
        max_cache_slots=1,
    )
    records = write_v21_matrix(
        args.output,
        args.trace_output,
        args.manifest_output,
        args.seeds,
        modes=args.modes,
        task_counts=args.task_counts,
        uav_counts=args.uav_counts,
        config=config,
        variants=variants,
        workers=args.workers,
    )
    print("Paired records: {}".format(len(records)))
    print("Episodes: {}".format(len(records) // (1 + len(variants))))
    print("Variants: {}".format(", ".join(args.variants)))
    print("Metrics: {}".format(args.output))
    print("Decision traces: {}".format(args.trace_output))
    print("Manifest: {}".format(args.manifest_output))


if __name__ == "__main__":
    main()
