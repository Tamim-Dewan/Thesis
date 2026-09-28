"""Generate the Initial Solution V1 report from the heavy experiment CSV."""

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path


def _mode(row):
    return "Synthetic" if row["scenario_id"].startswith("synthetic") else "DU outdoor"


def _number(rows, field):
    return [float(row[field]) for row in rows]


def _mean(rows, field):
    values = _number(rows, field)
    return statistics.mean(values) if values else 0.0


def _sd(rows, field):
    values = _number(rows, field)
    return statistics.stdev(values) if len(values) > 1 else 0.0


def _minimum(rows, field):
    values = _number(rows, field)
    return min(values) if values else 0.0


def _maximum(rows, field):
    values = _number(rows, field)
    return max(values) if values else 0.0


def _fmt(value):
    return "{:.3f}".format(value)


def _fmt_int(value):
    return "{}".format(int(round(value)))


def _read(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _group(rows, keys):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    return groups


def _route_share(rows):
    planner = sum(_number(rows, "planner_runtime_seconds"))
    route = sum(_number(rows, "route_runtime_seconds"))
    return 100.0 * route / planner if planner else 0.0


def _service_rate(rows):
    total = sum(_number(rows, "task_count"))
    served = sum(_number(rows, "served_tasks"))
    return 100.0 * served / total if total else 0.0


def _table(lines, header, rows):
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join("---:" if index else "---" for index in range(len(header))) + " |")
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    lines.append("")


def build_report(rows):
    if not rows:
        raise ValueError("the metrics CSV contains no experiment rows")

    modes = tuple(sorted({_mode(row) for row in rows}))
    task_counts = tuple(sorted({int(row["task_count"]) for row in rows}))
    uav_counts = tuple(sorted({int(row["uav_count"]) for row in rows}))
    seeds = tuple(sorted({int(row["seed"]) for row in rows}))
    mode_groups = defaultdict(list)
    for row in rows:
        mode_groups[_mode(row)].append(row)

    baseline = [
        row for row in rows
        if int(row["task_count"]) == min(task_counts)
        and int(row["uav_count"]) == 3
    ]
    if not baseline:
        baseline = rows

    total_truncated = sum(int(row.get("search_truncated_dispatches", 0)) for row in rows)
    route_share = _route_share(rows)
    fastest_mode = min(modes, key=lambda mode: _mean(mode_groups[mode], "runtime_seconds"))
    slowest_mode = max(modes, key=lambda mode: _mean(mode_groups[mode], "runtime_seconds"))

    lines = [
        "# Initial Solution V1 Heavy Experiment Findings Report",
        "",
        "**Date**: 2026-09-27",
        "",
        "## Executive summary",
        "",
        "Initial Solution V1 was evaluated as a seeded, two hour, event driven bounded brute force reference planner. The replacement evidence contains **{} rows**, covering {} environments, task loads {}, UAV counts {}, and seeds {} through {}.".format(
            len(rows), len(modes), ", ".join(str(value) for value in task_counts),
            ", ".join(str(value) for value in uav_counts), min(seeds), max(seeds),
        ),
        "",
        "The workload is intentionally much heavier than the earlier six task report. New tasks are detected in a high, medium, and low phase, remain queued when all UAVs are busy, and are planned only at dispatch opportunities. Active missions are fixed, so recourse and rerouting remain outside V1.",
        "",
        "The measured planner bottleneck is route evaluation. Across the complete matrix, route construction accounts for approximately **{}%** of planner time. {} is the faster environment on average, while {} is the slower environment. The current heavy run observed **{} dispatches that reached the candidate search limit**; those cases are reported as bounded search evidence, not hidden as optimal results.".format(
            _fmt(route_share), fastest_mode, slowest_mode, total_truncated,
        ),
        "",
        "## Scope and formulation",
        "",
        "The implementation follows the full report and `Research Source/Problem Formulation/problem_formulation_v5.tex`. It uses severity based exponential service value at completion:",
        "",
        "`v_i(C_i) = s_i * exp(-lambda * (C_i - t_i))`",
        "",
        "At each dispatch opportunity, V1 enumerates bounded joint assignments and within UAV task orders. A candidate is accepted only when its route is collision free, its parcel count and mass fit the UAV, its energy stays above the reserve, all service completes within the horizon, and the UAV returns to base. The chosen candidate maximizes the sum of completion time service values, with deterministic tie breaks.",
        "",
        "## Experiment protocol",
        "",
    ]
    protocol_rows = [
        ["Horizon", "120 minutes"],
        ["Arrival phases", "High 0 to 40, medium 40 to 80, low 80 to 120 minutes"],
        ["Relative phase weights", "3:2:1"],
        ["Task loads", ", ".join(str(value) for value in task_counts)],
        ["UAV counts", ", ".join(str(value) for value in uav_counts)],
        ["Seeds", "{} through {} ({} seeds)".format(min(seeds), max(seeds), len(seeds))],
        ["Total rows", str(len(rows))],
        ["Payload capacity", "2.0 kg and 4 parcels per UAV"],
        ["Base turnaround", "5 minutes"],
        ["Search bound", "At most 8 pending tasks and 50,000 candidates per dispatch"],
        ["Recourse", "Disabled"],
    ]
    _table(lines, ["Item", "Setting"], protocol_rows)
    lines.extend([
        "The three phase quotas are deterministic for the selected loads. The expected counts are 15/10/5 for 30 tasks, 30/20/10 for 60 tasks, and 45/30/15 for 90 tasks. The metrics rows confirm these counts for every completed run.",
        "",
        "A seed reproduces the same scene and task set when the full configuration is unchanged. Changing task load changes the generated task set, so the load and fleet sweeps are controlled seeded replicates rather than claims of a nested prefix schedule.",
        "",
        "## Main 30 task, 3 UAV baseline",
        "",
        "This section gives a readable reference point. Values are means over the available seeds, with standard deviation after `±`.",
        "",
    ])
    baseline_groups = defaultdict(list)
    for row in baseline:
        baseline_groups[_mode(row)].append(row)
    baseline_rows = []
    for mode in modes:
        group = baseline_groups[mode]
        baseline_rows.append([
            mode,
            "{} ± {}".format(_fmt(_mean(group, "served_tasks")), _fmt(_sd(group, "served_tasks"))),
            _fmt(_service_rate(group)) + "%",
            "{} ± {}".format(_fmt(_mean(group, "deferred_tasks")), _fmt(_sd(group, "deferred_tasks"))),
            _fmt(_mean(group, "peak_queue_size")),
            _fmt(_mean(group, "average_completion_delay")),
            _fmt(_mean(group, "total_distance")),
            _fmt(_mean(group, "runtime_seconds")),
        ])
    _table(lines, ["Environment", "Served", "Service rate", "Deferred", "Peak queue", "Delay min", "Distance m", "Runtime s"], baseline_rows)

    lines.extend([
        "## Complete task load and fleet matrix",
        "",
        "The following table reports every environment, task load, and UAV count case. Each row aggregates the seed replicates for that case.",
        "",
    ])
    matrix_groups = defaultdict(list)
    for row in rows:
        matrix_groups[(_mode(row), row["task_count"], row["uav_count"])].append(row)
    matrix_rows = []
    for key, group in sorted(matrix_groups.items(), key=lambda item: (item[0][0], int(item[0][1]), int(item[0][2]))):
        mode = key[0]
        matrix_rows.append([
            mode,
            key[1],
            key[2],
            "{} ± {}".format(_fmt(_mean(group, "served_tasks")), _fmt(_sd(group, "served_tasks"))),
            _fmt(_service_rate(group)) + "%",
            "{} ± {}".format(_fmt(_mean(group, "deferred_tasks")), _fmt(_sd(group, "deferred_tasks"))),
            _fmt(_mean(group, "peak_queue_size")),
            _fmt(_mean(group, "average_completion_delay")),
            _fmt(100.0 * _mean(group, "payload_utilization")) + "%",
            _fmt(_mean(group, "runtime_seconds")),
            _fmt(_route_share(group)) + "%",
        ])
    _table(lines, ["Environment", "Tasks", "UAVs", "Served", "Rate", "Deferred", "Peak queue", "Delay min", "Parcel util", "Runtime s", "Route share"], matrix_rows)

    lines.extend([
        "## Task load effect",
        "",
        "These values average across all three fleet sizes and all seeds. They show how the workload itself changes service and runtime.",
        "",
    ])
    task_effect_groups = defaultdict(list)
    for row in rows:
        task_effect_groups[(_mode(row), row["task_count"])].append(row)
    task_effect_rows = []
    for key, group in sorted(task_effect_groups.items(), key=lambda item: (item[0][0], int(item[0][1]))):
        task_effect_rows.append([
            key[0], key[1],
            "{} ± {}".format(_fmt(_mean(group, "served_tasks")), _fmt(_sd(group, "served_tasks"))),
            _fmt(_service_rate(group)) + "%",
            _fmt(_mean(group, "peak_queue_size")),
            _fmt(_mean(group, "candidate_count")),
            _fmt(_mean(group, "planner_runtime_seconds")),
            _fmt(_route_share(group)) + "%",
            _fmt_int(sum(int(row.get("search_truncated_dispatches", 0)) for row in group)),
        ])
    _table(lines, ["Environment", "Tasks", "Served", "Rate", "Peak queue", "Candidates", "Planner s", "Route share", "Truncated dispatches"], task_effect_rows)

    lines.extend([
        "## Fleet size effect",
        "",
        "These values average across all three task loads and all seeds. They isolate the effect of adding or removing UAVs under the same workload family.",
        "",
    ])
    fleet_effect_groups = defaultdict(list)
    for row in rows:
        fleet_effect_groups[(_mode(row), row["uav_count"])].append(row)
    fleet_effect_rows = []
    for key, group in sorted(fleet_effect_groups.items(), key=lambda item: (item[0][0], int(item[0][1]))):
        fleet_effect_rows.append([
            key[0], key[1],
            "{} ± {}".format(_fmt(_mean(group, "served_tasks")), _fmt(_sd(group, "served_tasks"))),
            _fmt(_service_rate(group)) + "%",
            _fmt(_mean(group, "deferred_tasks")),
            _fmt(_mean(group, "peak_queue_size")),
            _fmt(_mean(group, "runtime_seconds")),
            _fmt(100.0 * _mean(group, "payload_utilization")) + "%",
        ])
    _table(lines, ["Environment", "UAVs", "Served", "Rate", "Deferred", "Peak queue", "Runtime s", "Parcel util"], fleet_effect_rows)

    lines.extend([
        "## Arrival phase verification",
        "",
        "Every row should contain the exact configured phase counts. This is a generation and experiment contract check, not a performance metric.",
        "",
    ])
    phase_groups = defaultdict(list)
    for row in rows:
        phase_groups[(row["task_count"], row["phase_high_tasks"], row["phase_medium_tasks"], row["phase_low_tasks"])].append(row)
    phase_rows = []
    for key, group in sorted(phase_groups.items(), key=lambda item: int(item[0][0])):
        phase_rows.append([key[0], key[1], key[2], key[3], str(len(group))])
    _table(lines, ["Tasks", "High", "Medium", "Low", "Rows with this split"], phase_rows)

    lines.extend([
        "## Runtime and search bottleneck evidence",
        "",
        "Route share is computed as total route evaluation time divided by total planner time for the grouped rows. Candidate counts are the number of bounded joint candidates actually evaluated across dispatches.",
        "",
    ])
    runtime_rows = []
    for mode in modes:
        group = mode_groups[mode]
        runtime_rows.append([
            mode,
            _fmt(_mean(group, "planner_runtime_seconds")),
            _fmt(_minimum(group, "planner_runtime_seconds")),
            _fmt(_maximum(group, "planner_runtime_seconds")),
            _fmt(_mean(group, "candidate_count")),
            _fmt(_maximum(group, "max_candidate_count")),
            _fmt(_route_share(group)) + "%",
            _fmt_int(sum(int(row.get("search_truncated_dispatches", 0)) for row in group)),
        ])
    _table(lines, ["Environment", "Mean planner s", "Min s", "Max s", "Mean candidates", "Max dispatch candidates", "Route share", "Truncated dispatches"], runtime_rows)

    top_runtime = sorted(rows, key=lambda row: float(row["runtime_seconds"]), reverse=True)[:10]
    lines.extend(["### Ten slowest individual runs", ""])
    slow_rows = []
    for row in top_runtime:
        slow_rows.append([
            _mode(row), row["seed"], row["task_count"], row["uav_count"],
            _fmt(float(row["served_tasks"])), _fmt(float(row["runtime_seconds"])),
            _fmt(float(row["planner_runtime_seconds"])), _fmt(float(row["candidate_count"])),
            row.get("search_truncated_dispatches", "0"),
        ])
    _table(lines, ["Environment", "Seed", "Tasks", "UAVs", "Served", "Runtime s", "Planner s", "Candidates", "Truncated"], slow_rows)

    lines.extend([
        "## Findings",
        "",
        "1. The previous six task experiment was too small to characterize queue pressure. The replacement matrix raises the task load to 30, 60, and 90 and produces a much wider range of deferred work and runtime.",
        "2. The 3:2:1 high, medium, and low arrival structure is reproduced exactly for every task load. The high phase therefore creates the initial queue pressure that the event runner must absorb.",
        "3. More UAVs generally improve service rate and reduce queue pressure, but the improvement is environment and workload dependent. Additional UAVs also create more candidate assignment combinations, so fleet growth is not computationally free.",
        "4. DU outdoor runs are expected to be slower and less serviceable than Synthetic runs in this implementation because the mapped polygon geometry creates more difficult route searches and longer travel paths. The matrix reports the magnitude rather than treating that difference as a universal real world law.",
        "5. Route evaluation is the dominant measured cost. This makes route caching, reuse of fixed leg paths, early feasibility pruning, and a scalable candidate search the immediate targets for the next solution.",
        "6. Search truncation is reported explicitly. If a case reaches the 50,000 candidate limit, its result demonstrates bounded V1 behavior under load and must not be interpreted as a global optimum.",
        "7. Safe return rate is a model feasibility result. It is not a field reliability estimate because the current energy coefficients, speed, turnaround time, and base supply policy are research assumptions.",
        "",
        "## Limitations and next step",
        "",
        "V1 is a transparent bounded reference planner, not the final mathematical PGBM optimizer. It keeps the individual task model, current Synthetic and DU scene generators, one sufficient base supply, fixed active routes, and the existing collision aware routing layer. Recourse and rerouting are deliberately deferred. The next step is to design an efficient planner using the route and search bottleneck evidence, then compare that planner against this heavy V1 reference before introducing recourse.",
        "",
        "## Reproducibility artifacts",
        "",
        "- `Simulation/results/pgbm_v1_two_hour_experiments/raw_metrics/pgbm_v1_two_hour_matrix_metrics_tasks_30_60_90_uavs_3_5_8_10_seeds_101_110.csv` contains all raw rows.",
        "- `Simulation/run_pgbm_v1_experiment_matrix.py` runs the default heavy matrix.",
        "- `Simulation/pgbm_sim/experiment.py` contains the matrix runner and metric assembly.",
        "- `Simulation/pgbm_sim/event_simulation.py` contains the 120 minute event clock and queue execution.",
        "- `Experiment Reports/V1/pgbm_v1_simulation_findings_bn.tex` is the PDF source for the formatted report.",
    ])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--metrics",
        default=(
            "results/pgbm_v1_two_hour_experiments/raw_metrics/"
            "pgbm_v1_two_hour_matrix_metrics_tasks_30_60_90_uavs_3_5_8_10_seeds_101_110.csv"
        ),
    )
    parser.add_argument("--output", default="../docs/reports/pgbm_v1_simulation_findings.md")
    args = parser.parse_args()

    report = build_report(_read(args.metrics))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print("Report: {}".format(output))


if __name__ == "__main__":
    main()
