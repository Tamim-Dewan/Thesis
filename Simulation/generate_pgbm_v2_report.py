"""Generate the Bangla PGBM V2 comparative findings report."""

import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = ROOT / "Simulation/results/pgbm_v2_recourse_experiments/raw_metrics/pgbm_v2_paired_matrix_metrics_tasks_30_60_90_uavs_3_5_8_10_seeds_101_110.csv"
OUTPUT_DIR = ROOT / "Experiment Reports/V2"
RESULTS_DIR = ROOT / "Simulation/results/pgbm_v2_recourse_experiments"
TRACE_PATH = RESULTS_DIR / "decision_traces/pgbm_v2_decision_traces.jsonl"


NUMERIC_FIELDS = {
    "seed": int,
    "task_count": int,
    "uav_count": int,
    "horizon_minutes": float,
    "objective_value": float,
    "served_tasks": int,
    "deferred_tasks": int,
    "average_completion_delay": float,
    "total_distance": float,
    "total_travel_time": float,
    "total_energy": float,
    "requested_parcels": int,
    "dropped_parcels": int,
    "parcel_delivery_rate": float,
    "safe_return_rate": float,
    "runtime_seconds": float,
    "planner_runtime_seconds": float,
    "route_runtime_seconds": float,
    "recourse_runtime_seconds": float,
    "dispatch_count": int,
    "mission_count": int,
    "peak_queue_size": int,
    "candidate_count": int,
    "max_candidate_count": int,
    "max_pending_considered": int,
    "search_truncated_dispatches": int,
    "phase_high_tasks": int,
    "phase_medium_tasks": int,
    "phase_low_tasks": int,
    "recourse_trigger_count": int,
    "accepted_replacements": int,
    "rejected_replacements": int,
    "replacement_gain": float,
    "displaced_task_count": int,
}


def load_rows(path: Path) -> List[Dict[str, object]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        rows = []
        for raw in csv.DictReader(handle):
            row: Dict[str, object] = dict(raw)
            for field, converter in NUMERIC_FIELDS.items():
                row[field] = converter(raw[field])
            row["rejection_reasons_dict"] = json.loads(raw.get("rejection_reasons", "{}") or "{}")
            rows.append(row)
    return rows


def load_traces(path: Path) -> List[Dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def grouped(rows: Iterable[Mapping[str, object]], keys: Sequence[str]):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    return groups


def mean(rows: Sequence[Mapping[str, object]], field: str) -> float:
    return statistics.mean(float(row[field]) for row in rows) if rows else 0.0


def std(rows: Sequence[Mapping[str, object]], field: str) -> float:
    values = [float(row[field]) for row in rows]
    return statistics.stdev(values) if len(values) > 1 else 0.0


def mean_pm(rows: Sequence[Mapping[str, object]], field: str, digits: int = 2) -> str:
    return "{0:.{d}f} $\\pm$ {1:.{d}f}".format(mean(rows, field), std(rows, field), d=digits)


def plain_mean_pm(rows: Sequence[Mapping[str, object]], field: str, digits: int = 2) -> str:
    return "{0:.{d}f} ± {1:.{d}f}".format(mean(rows, field), std(rows, field), d=digits)


def metric_value(row: Mapping[str, object], field: str) -> float:
    """Return a stored or per-episode derived metric for report aggregation."""

    if field == "task_rate":
        denominator = float(row["task_count"])
        return float(row["served_tasks"]) / denominator if denominator else 0.0
    if field == "energy_per_served_task":
        denominator = float(row["served_tasks"])
        return float(row["total_energy"]) / denominator if denominator else 0.0
    if field == "energy_per_dropped_parcel":
        denominator = float(row["dropped_parcels"])
        return float(row["total_energy"]) / denominator if denominator else 0.0
    return float(row[field])


def metric_mean(rows: Sequence[Mapping[str, object]], field: str) -> float:
    return statistics.mean(metric_value(row, field) for row in rows) if rows else 0.0


def metric_std(rows: Sequence[Mapping[str, object]], field: str) -> float:
    values = [metric_value(row, field) for row in rows]
    return statistics.stdev(values) if len(values) > 1 else 0.0


def metric_pm(rows: Sequence[Mapping[str, object]], field: str, digits: int = 2) -> str:
    return "{0:.{d}f} ± {1:.{d}f}".format(metric_mean(rows, field), metric_std(rows, field), d=digits)


def metric_percent_pm(rows: Sequence[Mapping[str, object]], field: str, digits: int = 1) -> str:
    return "{0:.{d}f}% ± {1:.{d}f}%".format(
        100.0 * metric_mean(rows, field),
        100.0 * metric_std(rows, field),
        d=digits,
    )


def tex_metric_pm(rows: Sequence[Mapping[str, object]], field: str, digits: int = 2) -> str:
    return "{0:.{d}f} $\\pm$ {1:.{d}f}".format(metric_mean(rows, field), metric_std(rows, field), d=digits)


def tex_metric_percent_pm(rows: Sequence[Mapping[str, object]], field: str, digits: int = 1) -> str:
    return "{0:.{d}f}\\% $\\pm$ {1:.{d}f}\\%".format(
        100.0 * metric_mean(rows, field),
        100.0 * metric_std(rows, field),
        d=digits,
    )


def pct(value: float, digits: int = 1) -> str:
    return "{0:.{d}f}\\%".format(100.0 * value, d=digits)


def latex_text(value: object) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def table_group(rows: Sequence[Mapping[str, object]], environment: str, task_count: int, uav_count: int):
    return [
        row
        for row in rows
        if row["environment"] == environment and row["task_count"] == task_count and row["uav_count"] == uav_count
    ]


def build_aggregates(rows: Sequence[Mapping[str, object]]):
    matrix = []
    for environment in ("DU outdoor", "Synthetic"):
        mode = "du_outdoor" if environment == "DU outdoor" else "synthetic"
        for task_count in (30, 60, 90):
            for uav_count in (3, 5, 8, 10):
                cell = table_group(rows, mode, task_count, uav_count)
                v1 = [row for row in cell if row["algorithm"] == "V1"]
                v2 = [row for row in cell if row["algorithm"] == "V2"]
                if len(v1) != 10 or len(v2) != 10:
                    raise ValueError("expected ten seeds for {} {} {}".format(mode, task_count, uav_count))
                matrix.append(
                    {
                        "environment": environment,
                        "mode": mode,
                        "task_count": task_count,
                        "uav_count": uav_count,
                        "v1": v1,
                        "v2": v2,
                    }
                )
    return matrix


def rejection_totals(rows: Sequence[Mapping[str, object]]) -> Counter:
    result = Counter()
    for row in rows:
        if row["algorithm"] != "V2":
            continue
        result.update(row["rejection_reasons_dict"])
    return result


def _phase_for_trigger(trigger_time: float) -> str:
    if trigger_time < 40.0:
        return "High"
    if trigger_time < 80.0:
        return "Medium"
    return "Low"


def _candidate_reason(reason: str) -> str:
    return str(reason).split(":", 1)[0]


def _trace_group_summary(decisions: Sequence[Mapping[str, object]]) -> Dict[str, object]:
    gains = [float(decision["delta_value"]) for decision in decisions if bool(decision["accepted"])]
    accepted = sum(1 for decision in decisions if bool(decision["accepted"]))
    return {
        "triggers": len(decisions),
        "accepted": accepted,
        "rejected": len(decisions) - accepted,
        "rate": accepted / len(decisions) if decisions else 0.0,
        "gain_mean": statistics.mean(gains) if gains else 0.0,
        "gain_std": statistics.stdev(gains) if len(gains) > 1 else 0.0,
    }


def trace_evidence(traces: Sequence[Mapping[str, object]]) -> Dict[str, object]:
    by_environment: Dict[str, List[Mapping[str, object]]] = defaultdict(list)
    by_task_count: Dict[int, List[Mapping[str, object]]] = defaultdict(list)
    by_uav_count: Dict[int, List[Mapping[str, object]]] = defaultdict(list)
    by_phase: Dict[str, List[Mapping[str, object]]] = defaultdict(list)
    all_decisions: List[Mapping[str, object]] = []
    candidate_reasons: Counter = Counter()
    displaced_events: List[Tuple[str, str, bool]] = []
    accepted_examples: List[Mapping[str, object]] = []
    rejected_examples: List[Mapping[str, object]] = []

    for trace in traces:
        v2 = trace["v2"]
        scenario_id = str(trace["scenario_id"])
        decisions = v2.get("recourse_decisions", [])
        for decision in decisions:
            enriched = dict(decision)
            enriched["environment"] = trace["environment"]
            enriched["task_count"] = int(trace["task_count"])
            enriched["uav_count"] = int(trace["uav_count"])
            enriched["scenario_id"] = scenario_id
            enriched["phase"] = _phase_for_trigger(float(decision["trigger_time"]))
            all_decisions.append(enriched)
            by_environment[str(trace["environment"])].append(enriched)
            by_task_count[int(trace["task_count"])].append(enriched)
            by_uav_count[int(trace["uav_count"])].append(enriched)
            by_phase[str(enriched["phase"])].append(enriched)
            for candidate in decision.get("candidates", []):
                candidate_reasons[_candidate_reason(str(candidate.get("rejection_reason", "unknown")))] += 1
            if bool(decision["accepted"]):
                accepted_examples.append(enriched)
                displaced_events.append(
                    (
                        scenario_id,
                        str(decision["displaced_task_id"]),
                        str(decision["displaced_task_id"]) in set(v2.get("served_task_ids", [])),
                    )
                )
            elif len(rejected_examples) < 3:
                rejected_examples.append(enriched)

    unique_displaced = {}
    for scenario_id, task_id, completed in displaced_events:
        unique_displaced[(scenario_id, task_id)] = completed
    accepted_gains = [float(decision["delta_value"]) for decision in all_decisions if bool(decision["accepted"])]
    return {
        "all": _trace_group_summary(all_decisions),
        "by_environment": {key: _trace_group_summary(value) for key, value in sorted(by_environment.items())},
        "by_task_count": {key: _trace_group_summary(value) for key, value in sorted(by_task_count.items())},
        "by_uav_count": {key: _trace_group_summary(value) for key, value in sorted(by_uav_count.items())},
        "by_phase": {key: _trace_group_summary(value) for key, value in (("High", by_phase["High"]), ("Medium", by_phase["Medium"]), ("Low", by_phase["Low"]))},
        "candidate_reasons": candidate_reasons,
        "accepted_gain_mean": statistics.mean(accepted_gains) if accepted_gains else 0.0,
        "accepted_gain_std": statistics.stdev(accepted_gains) if len(accepted_gains) > 1 else 0.0,
        "unique_displaced": len(unique_displaced),
        "unique_displaced_completed": sum(1 for completed in unique_displaced.values() if completed),
        "unique_displaced_deferred": sum(1 for completed in unique_displaced.values() if not completed),
        "displaced_event_count": len(displaced_events),
        "repeated_displacement_events": len(displaced_events) - len(unique_displaced),
        "accepted_example": accepted_examples[0] if accepted_examples else None,
        "rejected_example": next((item for item in rejected_examples if item.get("reason") == "no_positive_gain"), rejected_examples[0] if rejected_examples else None),
    }


def validation_evidence(rows: Sequence[Mapping[str, object]]) -> Dict[str, object]:
    """Build visible validation evidence from the paired matrix and a small replay fixture."""

    pairs = grouped(rows, ("environment", "task_count", "uav_count", "seed"))
    paired_groups = [group for group in pairs.values() if len(group) == 2]
    fingerprint_match = bool(paired_groups) and all(
        len({str(row["scenario_fingerprint"]) for row in group}) == 1
        and {str(row["algorithm"]) for row in group} == {"V1", "V2"}
        for group in paired_groups
    )
    evidence: Dict[str, object] = {
        "paired_count": len(paired_groups),
        "fingerprint_match": fingerprint_match,
        "same_seed_task_realization": fingerprint_match and len(paired_groups) == 240,
    }

    try:
        from pgbm_sim import EventSimulationConfig
        from pgbm_sim.event_simulation import run_event_simulation
        from pgbm_sim.tasks import service_value
        from pgbm_sim.v2 import V2Config, run_event_simulation_v2
        from pgbm_sim.v2.experiment import V2ExperimentConfig, build_experiment_scenario

        experiment_config = V2ExperimentConfig(max_candidate_plans=5000)
        scenario = build_experiment_scenario("synthetic", 5, 12, 3, experiment_config)
        v1 = run_event_simulation(
            scenario,
            scenario.uav_config,
            scenario.route_config,
            EventSimulationConfig(max_pending_tasks=8, max_candidate_plans=5000),
        )
        fixed = run_event_simulation_v2(
            scenario,
            scenario.uav_config,
            scenario.route_config,
            V2Config(max_pending_tasks=8, max_candidate_plans=5000, recourse_enabled=False),
        )
        replay_a = run_event_simulation_v2(
            scenario,
            scenario.uav_config,
            scenario.route_config,
            V2Config(max_pending_tasks=8, max_candidate_plans=5000, recourse_enabled=True),
        )
        replay_b = run_event_simulation_v2(
            scenario,
            scenario.uav_config,
            scenario.route_config,
            V2Config(max_pending_tasks=8, max_candidate_plans=5000, recourse_enabled=True),
        )
        close = lambda left, right: math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-9)
        completion_events = [event for event in replay_a.events if event.event == "service_complete" and event.task_id is not None]
        completed_ids = [event.task_id for event in completion_events]
        task_by_id = {task.identifier: task for task in scenario.tasks}
        recomputed_objective = sum(
            service_value(task_by_id[event.task_id].severity, task_by_id[event.task_id].detected_at, event.time, scenario.task_config.service_value_decay_rate)
            for event in completion_events
        )
        fixed_matches = {
            "objective": close(v1.objective_value, fixed.objective_value),
            "served": v1.served_task_ids == fixed.served_task_ids,
            "distance": close(v1.total_distance, fixed.total_distance),
            "energy": close(v1.total_energy, fixed.total_energy),
            "candidate_count": v1.candidate_count == fixed.candidate_count,
        }
        evidence.update(
            {
                "fixture": "synthetic, seed 5, 12 tasks, 3 UAV",
                "v1_objective": float(v1.objective_value),
                "fixed_objective": float(fixed.objective_value),
                "fixed_matches": fixed_matches,
                "fixed_all_match": all(fixed_matches.values()),
                "deterministic_replay": replay_a.events == replay_b.events and replay_a.recourse_decisions == replay_b.recourse_decisions,
                "duplicate_completion_free": len(completed_ids) == len(set(completed_ids)) and set(completed_ids) == set(replay_a.served_task_ids),
                "reported_objective": float(replay_a.objective_value),
                "recomputed_objective": float(recomputed_objective),
                "objective_once": close(replay_a.objective_value, recomputed_objective),
            }
        )
    except Exception as error:  # pragma: no cover - report generation should still expose the matrix evidence
        evidence["fixture_error"] = str(error)
    return evidence


def _environment_algorithm_rows(rows: Sequence[Mapping[str, object]], mode: str, algorithm: str):
    return [row for row in rows if row["environment"] == mode and row["algorithm"] == algorithm]


def detailed_markdown_sections(
    rows: Sequence[Mapping[str, object]],
    matrix,
    traces: Sequence[Mapping[str, object]],
    validation: Mapping[str, object],
) -> List[str]:
    trace_stats = trace_evidence(traces)
    lines = [
        "",
        "## Energy model এবং energy ফলাফল",
        "",
        "V1 এবং V2 উভয় version-এ energy একটি configured accounting model দিয়ে গণনা করা হয়েছে। কোনো travel segment-এর জন্য `d` হলো route distance, `m` হলো বহন করা payload mass এবং `a+` হলো positive ascent distance।",
        "",
        "```text",
        "E_travel = d * e_distance + d * m * e_payload + a+ * e_ascent",
        "E_service = service_time * e_service",
        "E_mission = sum(E_travel) + sum(E_service)",
        "```",
        "",
        "এই run-এ `e_distance = 1.0 J/m`, `e_payload = 0.05 J/(kg m)`, `e_ascent = 0.20 J/m` এবং `e_service = 0.50 J/min`। প্রতিটি initial বা recourse candidate-এর জন্য UAV-এর ইতিমধ্যে ব্যবহৃত energy-এর সঙ্গে revised route-এর additional energy যোগ করে check করা হয়: `energy_consumed + additional_energy + reserve_energy <= energy_capacity`। এখানে capacity 1000 J এবং reserve 200 J; তাই projected remaining energy-এর অন্তত reserve অংশ mission শেষে অবশিষ্ট থাকতে হয়।",
        "",
        "`Total energy` হলো পুরো episode-এ সম্পন্ন বা horizon পর্যন্ত চলা সব mission-এর cumulative energy। এটি কোনো একক UAV-এর একবারের battery state নয়। প্রতিটি UAV base-এ ফিরে resupply/turnaround শেষ করলে পরের mission-এ নতুন full capacity থেকে শুরু করে; V1/V2-তে battery degradation বা mission-to-mission persistent battery depletion model করা হয়নি।",
        "",
        "| Environment | Algorithm | Total energy (J) | Energy/served task (J) | Energy/dropped parcel (J) | Distance (m) | Travel time (min) |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for environment, mode in (("DU outdoor", "du_outdoor"), ("Synthetic", "synthetic")):
        for algorithm in ("V1", "V2"):
            subset = _environment_algorithm_rows(rows, mode, algorithm)
            lines.append(
                "| {} | {} | {} | {} | {} | {} | {} |".format(
                    environment,
                    algorithm,
                    metric_pm(subset, "total_energy", 1),
                    metric_pm(subset, "energy_per_served_task", 1),
                    metric_pm(subset, "energy_per_dropped_parcel", 1),
                    metric_pm(subset, "total_distance", 1),
                    metric_pm(subset, "total_travel_time", 1),
                )
            )
    du_v1 = _environment_algorithm_rows(rows, "du_outdoor", "V1")
    du_v2 = _environment_algorithm_rows(rows, "du_outdoor", "V2")
    sy_v1 = _environment_algorithm_rows(rows, "synthetic", "V1")
    sy_v2 = _environment_algorithm_rows(rows, "synthetic", "V2")
    lines.extend(
        [
            "",
            "Energy result-এর মূল trade-off হলো: DU outdoor-এ V2 total energy 6142.4 J থেকে 6078.6 J-এ এবং distance 5928.2 m থেকে 5854.1 m-এ কমেছে, কারণ V2 কিছু lower-value task replace/queue করে এবং infeasible বা energy-expensive candidate গ্রহণ করে না। কিন্তু completed task ও parcel কম হওয়ায় প্রতি served task energy 310.2 থেকে 314.7 J এবং প্রতি dropped parcel 199.3 থেকে 224.5 J হয়েছে। Synthetic-এ V2 total energy 5319.7 J থেকে 5368.8 J এবং distance 5041.4 m থেকে 5083.6 m-এ সামান্য বেড়েছে; accepted recourse-এর revised route এই অতিরিক্ত movement তৈরি করেছে। তাই শুধু total energy দিয়ে efficiency বিচার করা যাবে না; cumulative energy, energy per completed service এবং distance একসঙ্গে দেখতে হবে।",
            "",
            "## Expanded V1 বনাম V2 result matrix",
            "",
            "নিচের দুইটি matrix-এ প্রতিটি cell-এর ১০টি seed-এর mean ± standard deviation দেওয়া হয়েছে। ফলে objective, served task, parcel volume, queue, energy, recourse এবং runtime-এর seed variability একই সঙ্গে দেখা যায়।",
            "",
            "### Service, parcel এবং queue metrics",
            "",
            "| Environment | Task | UAV | Alg | Objective | Served | Task rate | Req. parcel | Dropped parcel | Deferred | Delay min | Peak queue |",
            "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for cell in matrix:
        for algorithm, group in (("V1", cell["v1"]), ("V2", cell["v2"])):
            lines.append(
                "| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                    cell["environment"],
                    cell["task_count"],
                    cell["uav_count"],
                    algorithm,
                    metric_pm(group, "objective_value", 2),
                    metric_pm(group, "served_tasks", 2),
                    metric_percent_pm(group, "task_rate", 1),
                    metric_pm(group, "requested_parcels", 1),
                    metric_pm(group, "dropped_parcels", 1),
                    metric_pm(group, "deferred_tasks", 2),
                    metric_pm(group, "average_completion_delay", 2),
                    metric_pm(group, "peak_queue_size", 1),
                )
            )
    lines.extend(
        [
            "",
            "### Resource এবং recourse metrics",
            "",
            "| Environment | Task | UAV | Alg | Distance m | Travel min | Energy J | Energy/served | Energy/parcel | Safe return | Trigger | Accepted | Rejected | Gain | Runtime s |",
            "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for cell in matrix:
        for algorithm, group in (("V1", cell["v1"]), ("V2", cell["v2"])):
            lines.append(
                "| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                    cell["environment"],
                    cell["task_count"],
                    cell["uav_count"],
                    algorithm,
                    metric_pm(group, "total_distance", 1),
                    metric_pm(group, "total_travel_time", 1),
                    metric_pm(group, "total_energy", 1),
                    metric_pm(group, "energy_per_served_task", 1),
                    metric_pm(group, "energy_per_dropped_parcel", 1),
                    metric_percent_pm(group, "safe_return_rate", 1),
                    metric_pm(group, "recourse_trigger_count", 1),
                    metric_pm(group, "accepted_replacements", 1),
                    metric_pm(group, "rejected_replacements", 1),
                    metric_pm(group, "replacement_gain", 3),
                    metric_pm(group, "runtime_seconds", 3),
                )
            )
    lines.extend(
        [
            "",
            "এই expanded matrix-এ absolute requested/dropped parcel, task rate, deferred task এবং peak queue সরাসরি দেওয়া হয়েছে; parcel rate একা দেখে service volume অনুমান করতে হবে না। Resource table-এ distance এবং energy পাশাপাশি থাকায় route length বাড়ার সঙ্গে payload/ascent/service energy কীভাবে বদলেছে সেটিও দেখা যায়।",
            "",
            "## Recourse evidence: environment, load, fleet এবং phase",
            "",
            "Trigger-level মোট outcome-এর পাশাপাশি trace থেকে acceptance rate আলাদা করে হিসাব করা হয়েছে। Accepted gain-এর mean ± standard deviation এখানে accepted event-এর `delta_J`; episode-level `replacement_gain` তার থেকে আলাদা cumulative quantity।",
            "",
            "| Group type | Group | Trigger | Accepted | Acceptance rate | Rejected | Accepted gain mean ± std |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    grouped_trace_stats = []
    for group_type, groups in (
        ("Environment", (("DU outdoor", trace_stats["by_environment"].get("du_outdoor", {})), ("Synthetic", trace_stats["by_environment"].get("synthetic", {})))),
        ("Task load", tuple((str(key), trace_stats["by_task_count"][key]) for key in sorted(trace_stats["by_task_count"]))),
        ("UAV count", tuple((str(key), trace_stats["by_uav_count"][key]) for key in sorted(trace_stats["by_uav_count"]))),
        ("Arrival phase", tuple((key, trace_stats["by_phase"][key]) for key in ("High", "Medium", "Low"))),
    ):
        for label, summary in groups:
            grouped_trace_stats.append((group_type, label, summary))
            lines.append(
                "| {} | {} | {} | {} | {:.1f}% | {} | {:.3f} ± {:.3f} |".format(
                    group_type,
                    label,
                    summary.get("triggers", 0),
                    summary.get("accepted", 0),
                    100.0 * summary.get("rate", 0.0),
                    summary.get("rejected", 0),
                    summary.get("gain_mean", 0.0),
                    summary.get("gain_std", 0.0),
                )
            )
    total_candidates = sum(trace_stats["candidate_reasons"].values())
    lines.extend(
        [
            "",
            "### Candidate-level rejection breakdown",
            "",
            "একটি trigger-এর ভিতরে একাধিক candidate থাকতে পারে। তাই নিচের count candidate-level; আগের rejection table-এর count trigger-level final reason।",
            "",
            "| Candidate outcome/reason | Count | Share of candidate evaluations |",
            "|---|---:|---:|",
        ]
    )
    reason_labels = (
        ("onboard_inventory", "Onboard inventory"),
        ("payload_capacity", "Payload capacity"),
        ("route_infeasible", "Route infeasible"),
        ("energy_reserve", "Energy reserve"),
        ("horizon", "Horizon"),
        ("service_in_progress", "Service in progress"),
        ("non_positive_gain", "Non-positive gain"),
        ("feasible_positive_gain", "Feasible positive gain"),
    )
    for key, label in reason_labels:
        count = int(trace_stats["candidate_reasons"].get(key, 0))
        lines.append("| {} | {} | {:.1f}% |".format(label, count, 100.0 * count / total_candidates if total_candidates else 0.0))
    unique_total = int(trace_stats["unique_displaced"])
    unique_completed = int(trace_stats["unique_displaced_completed"])
    unique_deferred = int(trace_stats["unique_displaced_deferred"])
    lines.extend(
        [
            "",
            "Accepted replacement-এর পরে {}টি unique displaced-task instance-এর মধ্যে {}টি ({:.1f}%) horizon-এর মধ্যে পরে complete হয়েছে এবং {}টি ({:.1f}%) deferred থেকেছে। মোট accepted event ছিল {}; এর মধ্যে {}টি repeated displacement event, তাই event count এবং unique task count আলাদা করে report করা হয়েছে।".format(
                unique_total,
                unique_completed,
                100.0 * unique_completed / unique_total if unique_total else 0.0,
                unique_deferred,
                100.0 * unique_deferred / unique_total if unique_total else 0.0,
                trace_stats["all"]["accepted"],
                trace_stats["repeated_displacement_events"],
            ),
        ]
    )
    accepted_example = trace_stats.get("accepted_example")
    rejected_example = trace_stats.get("rejected_example")
    if accepted_example:
        lines.append(
            "Accepted trace example: `{}`-এ t={:.2f} min-এ {} দ্বারা `{}` task-কে সরিয়ে `{}` task বসানো হয়েছে; old value {:.3f}, new value {:.3f}, gain +{:.3f}।".format(
                accepted_example["scenario_id"],
                float(accepted_example["trigger_time"]),
                accepted_example.get("selected_uav_id"),
                accepted_example.get("displaced_task_id"),
                accepted_example.get("new_task_id"),
                float(accepted_example.get("old_value", 0.0)),
                float(accepted_example.get("new_value", 0.0)),
                float(accepted_example.get("delta_value", 0.0)),
            )
        )
    if rejected_example:
        candidate = next(
            (item for item in rejected_example.get("candidates", []) if _candidate_reason(str(item.get("rejection_reason", ""))) == "non_positive_gain"),
            rejected_example.get("candidates", [{}])[0],
        )
        lines.append(
            "Rejected trace example: `{}`-এ t={:.2f} min-এ `{}` task-এর জন্য selected candidate-এর gain {:.3f}; candidate feasible হলেও gain positive নয়, তাই final reason `{}` এবং task queue-তে রাখা হয়েছে।".format(
                rejected_example["scenario_id"],
                float(rejected_example["trigger_time"]),
                rejected_example.get("new_task_id"),
                float(candidate.get("delta_value", 0.0)),
                rejected_example.get("reason"),
            )
        )
    lines.extend(
        [
            "",
            "## Validation evidence",
            "",
            "একটি sentence-এর বদলে paired matrix এবং ছোট deterministic replay fixture-এর evidence নিচে দেওয়া হলো। Fixed-control fixture-এ V1 এবং V2 recourse-disabled একই scenario-তে চালানো হয়েছে; heavy matrix-এর ২৪০টি pair-এ scenario fingerprint match আলাদা করে যাচাই করা হয়েছে।",
            "",
            "| Validation check | Evidence | Result |",
            "|---|---|---|",
            "| Same scenario fingerprint এবং task realization | {}টি paired cell-এর fingerprint match | {} |".format(validation.get("paired_count", 0), "PASS" if validation.get("same_seed_task_realization") else "FAIL"),
            "| Fixed-control objective | V1 {:.6f}; V2 fixed {:.6f} | {} |".format(validation.get("v1_objective", 0.0), validation.get("fixed_objective", 0.0), "PASS" if validation.get("fixed_matches", {}).get("objective") else "FAIL"),
            "| Fixed-control served task | Same served-task ID set | {} |".format("PASS" if validation.get("fixed_matches", {}).get("served") else "FAIL"),
            "| Fixed-control distance and energy | Both values match within tolerance | {} |".format("PASS" if validation.get("fixed_matches", {}).get("distance") and validation.get("fixed_matches", {}).get("energy") else "FAIL"),
            "| Fixed-control candidate count | Same candidate count | {} |".format("PASS" if validation.get("fixed_matches", {}).get("candidate_count") else "FAIL"),
            "| Deterministic replay | Repeated V2 run produced identical events and decisions | {} |".format("PASS" if validation.get("deterministic_replay") else "FAIL"),
            "| Duplicate completion | Completed event IDs are unique | {} |".format("PASS" if validation.get("duplicate_completion_free") else "FAIL"),
            "| Objective double-counting | Reported {:.6f}; direct final-completion sum {:.6f} | {} |".format(validation.get("reported_objective", 0.0), validation.get("recomputed_objective", 0.0), "PASS" if validation.get("objective_once") else "FAIL"),
            "",
            "Validation fixture: `{}`। এটি report-এর reproducibility check; full result matrix-এর performance estimate নয়।".format(validation.get("fixture", "unavailable")),
        ]
    )
    return lines


def generate_markdown(
    rows: Sequence[Mapping[str, object]],
    matrix,
    traces: Sequence[Mapping[str, object]],
    validation: Mapping[str, object],
) -> str:
    v2_rows = [row for row in rows if row["algorithm"] == "V2"]
    v1_rows = [row for row in rows if row["algorithm"] == "V1"]
    reasons = rejection_totals(rows)
    lines = [
        "# PGBM Initial Solution V2: task replacement recourse findings",
        "",
        "## V2-এর core feature",
        "",
        "V2 হলো formulation-aligned one-for-one active-mission task replacement recourse। নতুন task আসলে সব responder UAV active থাকলে প্রতিটি active mission-এর uncompleted task একবার করে replace করার candidate পরীক্ষা করা হয়। Completed task এবং completed route prefix অপরিবর্তিত থাকে। নতুন task-এর item demand current onboard inventory দিয়ে মেটানো সম্ভব হতে হয়; remaining route existing collision-aware 3D routing layer দিয়ে একই base-এ ফেরত তৈরি হয়; এবং শুধু positive `ΔJ = J_new - J_old` হলে সর্বোচ্চ gain-এর candidate গ্রহণ করা হয়। Displaced task waiting queue-তে ফিরে যায়।",
        "",
        "V2-তে reserve inventory, base reload, multiple-task replacement, full fleet reoptimization বা future task information ব্যবহার করা হয়নি। এগুলো Version 3 scope। V1-এর entry point এবং evidence অপরিবর্তিত রাখা হয়েছে।",
        "",
        "## Experiment-এর সংক্ষিপ্ত চিত্র",
        "",
        "| বিষয় | ব্যবহৃত configuration |",
        "|---|---|",
        "| Environment | Synthetic এবং DU outdoor |",
        "| Operation window | ১২০ মিনিট |",
        "| Arrival phase | ০–৪০ high, ৪০–৮০ medium, ৮০–১২০ low |",
        "| Task load | ৩০, ৬০, ৯০ |",
        "| UAV count | ৩, ৫, ৮, ১০ |",
        "| Seed | ১০১–১১০ |",
        "| Configuration | ২৪০টি; প্রতি configuration-এ V1 এবং V2 paired row |",
        "| Evidence | ৪৮০ metrics row এবং ২৪০ V2 decision trace |",
        "",
        "V1-এর preserved canonical matrix থেকে comparison row নেওয়া হয়েছে। V2 একই local scene এবং task seed protocol-এ চালানো হয়েছে। In-memory paired validation-এ recourse disabled করলে V2 fixed control-এর objective, served task, distance, energy এবং candidate count V1-এর সঙ্গে মিলে গেছে।",
        "",
        "## V2 algorithm কীভাবে assignment এবং recourse ঠিক করে",
        "",
        "V2-এর initial dispatch V1-এর bounded brute-force assignment এবং task-order rule ব্যবহার করে। নতুন task arrival হলে V2 পুরো fleet replan করে না। Current mission state থেকে প্রতিটি active UAV এবং প্রতিটি uncompleted task-এর জন্য একটি candidate তৈরি হয়।",
        "",
        "1. Current time-এ UAV-এর position, completed task, remaining task, onboard item, payload এবং consumed energy project করা হয়।",
        "2. একটি uncompleted task সরিয়ে নতুন task-টি একই mission position-এ বসানো হয়।",
        "3. যদি service ইতিমধ্যে চলতে থাকে, সেই service interrupt করা হয় না; candidate current service শেষ হওয়ার পরের suffix পরিবর্তন করে।",
        "4. New task এবং remaining mission-এর item demand current onboard inventory দিয়ে মেটানো যায় কি না পরীক্ষা করা হয়।",
        "5. Current position থেকে revised task sequence এবং একই physical base পর্যন্ত collision-aware 3D route তৈরি হয়।",
        "6. Payload, route, energy reserve এবং ১২০ মিনিটের horizon feasibility পরীক্ষা হয়।",
        "7. Old remaining mission value এবং revised remaining mission value হিসাব করে `ΔJ` বের করা হয়।",
        "8. সব candidate-এর মধ্যে সর্বোচ্চ positive `ΔJ` গ্রহণ করা হয়; positive candidate না থাকলে নতুন task queue-তে থাকে।",
        "",
        "এখানে final episode objective প্রত্যেক completed task-এর service value একবার গণনা করে। Replanning-এর সময়ের intermediate objective যোগ করে double counting করা হয়নি।",
        "",
        "## Simulation environment এবং route flow",
        "",
        "V2 একই V1 scene, task, parcel, drop-off waypoint, payload, energy এবং route contracts ব্যবহার করে। প্রতিটি task individual delivery request; task-এর food, water এবং medical demand, ২–৪ m vertical drop-off waypoint এবং ০.৫ মিনিট per parcel service duration অপরিবর্তিত আছে।",
        "",
        "একটি active mission-এর route হলো Base → task waypoint sequence → Base। Recourse trigger হলে completed route অংশকে আবার plan করা হয় না। UAV-এর projected current position থেকে শুধু remaining suffix নতুন করে route করা হয়। প্রতিটি leg existing cruise-altitude check, direct line check, blocked হলে grid A* এবং vertical clearance check অনুসরণ করে।",
        "",
        "## Result বোঝার জন্য প্রধান metric",
        "",
        "* `Objective`: completion-time exponential service value; বেশি মানে priority-weighted assistance value বেশি।",
        "* `Served task` এবং `Dropped parcel`: task এবং parcel আলাদা unit; parcel rate item delivery pressure দেখায়।",
        "* `Deferred`: horizon শেষে complete না হওয়া task।",
        "* `Accepted replacement`: positive `ΔJ` সহ গৃহীত task replacement।",
        "* `Replacement gain`: accepted replacement-গুলোর `ΔJ` যোগফল; এটি episode objective নয়, event-level recourse evidence।",
        "* `Runtime`, `Planner`, `Route`, `Recourse`: computation কোথায় সময় নিচ্ছে তা আলাদা করে দেখায়।",
        "",
        "## Environment-level V1 বনাম V2 ফলাফল",
        "",
        "| Environment | Algorithm | Objective | Served | Task rate | Parcel rate | Deferred | Delay min | Runtime s | Accepted replacement |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for environment, mode in (("DU outdoor", "du_outdoor"), ("Synthetic", "synthetic")):
        for algorithm in ("V1", "V2"):
            subset = [row for row in rows if row["environment"] == mode and row["algorithm"] == algorithm]
            lines.append(
                "| {} | {} | {} | {} | {} | {} | {} | {} | {:.3f} | {} |".format(
                    environment,
                    algorithm,
                    plain_mean_pm(subset, "objective_value"),
                    plain_mean_pm(subset, "served_tasks"),
                    pct(mean(subset, "served_tasks") / mean(subset, "task_count")),
                    pct(mean(subset, "parcel_delivery_rate")),
                    plain_mean_pm(subset, "deferred_tasks"),
                    plain_mean_pm(subset, "average_completion_delay"),
                    mean(subset, "runtime_seconds"),
                    plain_mean_pm(subset, "accepted_replacements"),
                )
            )
    lines.extend(
        [
            "",
            "এই table থেকে কয়েকটি ফলাফল পরিষ্কার। DU outdoor-এ V2 objective 10.43 থেকে 11.70 হয়েছে (প্রায় 12.2% বৃদ্ধি), যদিও served task 20.12 থেকে 19.63 এবং parcel rate 36.6% থেকে 33.4%-এ সামান্য কমেছে। Synthetic-এ objective 23.48 থেকে 23.84 (প্রায় 1.5%) বেড়েছে, কিন্তু served task এবং parcel rate-ও সামান্য কমেছে। অর্থাৎ V2-এর লাভ raw task count নয়; active mission-এর মধ্যে কোন task আগে complete করলে time-sensitive service value বেশি হবে, সেটি বেছে নেওয়া।",
            "সবচেয়ে গুরুত্বপূর্ণ পরিবর্তনটি Delay min-এ। DU outdoor-এ average delay 31.64 থেকে 23.21 মিনিটে (8.43 মিনিট বা প্রায় 26.6%) এবং Synthetic-এ 18.30 থেকে 16.08 মিনিটে (2.22 মিনিট বা প্রায় 12.1%) কমেছে। Delay min হলো task detect হওয়ার সময় থেকে delivery complete হওয়া পর্যন্ত গড় সময়। নতুন task এলে V2 শুধু সেই replacement নেয় যার revised remaining mission value পুরনো mission-এর চেয়ে বেশি; ফলে অপেক্ষমাণ high-value task অনেক ক্ষেত্রে আগের completion position পায়। তবে এটি সব task-এর delay কমেছে—এমন দাবি নয়; কিছু lower-value displaced task queue-তে ফেরত যায়, তাই served count কমেও average completed-task delay কমতে পারে।",
            "এর বিপরীতে V2 runtime DU outdoor-এ 20.225 থেকে 59.408 s এবং Synthetic-এ 3.733 থেকে 10.355 s হয়েছে। কারণ প্রতিটি recourse trigger-এ সম্ভাব্য active UAV ও displaced task-এর জন্য feasibility এবং revised route পরীক্ষা করা হয়। তাই V2-এর মূল trade-off হলো—priority-weighted service value এবং completion delay উন্নত করার বিনিময়ে অতিরিক্ত computation।",
            "",
            "## Task load পরিবর্তনের প্রভাব",
            "",
            "| Environment | Tasks | V1 objective | V2 objective | Δ objective | V1 task rate | V2 task rate | V1 parcel rate | V2 parcel rate | V2 accepted |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for environment, mode in (("DU outdoor", "du_outdoor"), ("Synthetic", "synthetic")):
        for task_count in (30, 60, 90):
            v1 = [row for row in rows if row["environment"] == mode and row["algorithm"] == "V1" and row["task_count"] == task_count]
            v2 = [row for row in rows if row["environment"] == mode and row["algorithm"] == "V2" and row["task_count"] == task_count]
            lines.append(
                "| {} | {} | {:.2f} | {:.2f} | {:.2f} | {:.1f}% | {:.1f}% | {:.1f}% | {:.1f}% | {:.2f} |".format(
                    environment,
                    task_count,
                    mean(v1, "objective_value"),
                    mean(v2, "objective_value"),
                    mean(v2, "objective_value") - mean(v1, "objective_value"),
                    100.0 * mean(v1, "served_tasks") / task_count,
                    100.0 * mean(v2, "served_tasks") / task_count,
                    100.0 * mean(v1, "parcel_delivery_rate"),
                    100.0 * mean(v2, "parcel_delivery_rate"),
                    mean(v2, "accepted_replacements"),
                )
            )
    lines.extend(
        [
            "",
            "Task load বাড়লে queue pressure বাড়ে এবং V1 ও V2 দুই version-এর service rate সাধারণত কমে। V2-এর expected value হলো arrival চলাকালীন high-value task এলে existing mission-এর lower-value uncompleted task-এর জায়গায় সেটিকে আনা; তাই improvement সবচেয়ে অর্থপূর্ণ হবে সেই configuration-এ যেখানে active mission এবং নতুন task overlap বেশি।",
            "",
            "## UAV সংখ্যা পরিবর্তনের প্রভাব",
            "",
            "| Environment | UAV | V1 objective | V2 objective | Δ objective | V1 served | V2 served | V1 runtime s | V2 runtime s | V2 accepted |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for environment, mode in (("DU outdoor", "du_outdoor"), ("Synthetic", "synthetic")):
        for uav_count in (3, 5, 8, 10):
            v1 = [row for row in rows if row["environment"] == mode and row["algorithm"] == "V1" and row["uav_count"] == uav_count]
            v2 = [row for row in rows if row["environment"] == mode and row["algorithm"] == "V2" and row["uav_count"] == uav_count]
            lines.append(
                "| {} | {} | {:.2f} | {:.2f} | {:.2f} | {:.2f} | {:.2f} | {:.3f} | {:.3f} | {:.2f} |".format(
                    environment,
                    uav_count,
                    mean(v1, "objective_value"),
                    mean(v2, "objective_value"),
                    mean(v2, "objective_value") - mean(v1, "objective_value"),
                    mean(v1, "served_tasks"),
                    mean(v2, "served_tasks"),
                    mean(v1, "runtime_seconds"),
                    mean(v2, "runtime_seconds"),
                    mean(v2, "accepted_replacements"),
                )
            )
    lines.extend(
        [
            "",
            "UAV সংখ্যা বাড়ালে available capacity বাড়ে, ফলে recourse trigger-এর সুযোগ কমতেও পারে, কারণ নতুন task queue-তে না থেকে idle UAV-তে dispatch হতে পারে। এই কারণে V2 accepted replacement সবসময় fleet size-এর সঙ্গে monotonic হবে না। V2-এর meaningful comparison হলো একই fleet size-এ V1-এর তুলনায় objective, delay, served task এবং parcel delivery কীভাবে বদলেছে।",
            "",
            "## সম্পূর্ণ task load এবং fleet matrix",
            "",
            "নিচের matrix-এ দশটি seed-এর average দেওয়া হয়েছে। `ΔObj` হলো V2 objective minus V1 objective, `ΔServed` হলো served task-এর পার্থক্য, এবং `ΔParcel` হলো parcel delivery rate-এর percentage-point difference।",
            "",
            "| Environment | Task | UAV | V1 Obj | V2 Obj | ΔObj | V1 Served | V2 Served | ΔServed | V1 Parcel | V2 Parcel | ΔParcel | V2 Repl | V2 Runtime |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for cell in matrix:
        v1 = cell["v1"]
        v2 = cell["v2"]
        lines.append(
            "| {} | {} | {} | {:.2f} | {:.2f} | {:.2f} | {:.2f} | {:.2f} | {:.2f} | {:.1f}% | {:.1f}% | {:+.1f} pp | {:.2f} | {:.3f} |".format(
                cell["environment"],
                cell["task_count"],
                cell["uav_count"],
                mean(v1, "objective_value"),
                mean(v2, "objective_value"),
                mean(v2, "objective_value") - mean(v1, "objective_value"),
                mean(v1, "served_tasks"),
                mean(v2, "served_tasks"),
                mean(v2, "served_tasks") - mean(v1, "served_tasks"),
                100.0 * mean(v1, "parcel_delivery_rate"),
                100.0 * mean(v2, "parcel_delivery_rate"),
                100.0 * (mean(v2, "parcel_delivery_rate") - mean(v1, "parcel_delivery_rate")),
                mean(v2, "accepted_replacements"),
                mean(v2, "runtime_seconds"),
            )
        )
    lines.extend(
        [
            "",
            "এই matrix-এর প্রধান patternগুলো হলো: (১) DU outdoor-এর ১২টি configuration-এর সবকটিতেই V2 objective V1-এর চেয়ে বেশি। বিশেষ করে ৯০ task-এ gain 1.30 থেকে 2.59 পর্যন্ত, অর্থাৎ load বাড়লে recourse-এর priority benefit বেশি দৃশ্যমান হয়। (২) DU outdoor-এ ৬০ task/৩ UAV ছাড়া served task সামান্য কমেছে বা প্রায় অপরিবর্তিত থেকেছে; parcel rate-ও সব cell-এ কমেছে। কারণ V2 কিছু lower-value active task সরিয়ে বেশি time-sensitive task বসায়—এটি throughput-maximization rule নয়। (৩) Synthetic-এ low load এবং বেশি UAV থাকলে V1-এর capacity প্রায় যথেষ্ট; ৩০ task/১০ UAV-এ accepted replacement গড় ০ এবং objective পরিবর্তন ০.০০। তাই সেখানে V2-এর বাড়তি লাভ সীমিত। (৪) Synthetic-এর ৬০ task/১০ UAV cell-এ একমাত্র সামান্য negative objective change (-0.09) দেখা গেছে—এই configuration-এ replacement-এর লাভ computation/queue trade-off পুরোপুরি offset করতে পারেনি। (৫) ৯০ task-এ accepted replacement এবং runtime সাধারণত বাড়ে; DU outdoor-এ ৯০ task/১০ UAV runtime 134.039 s পর্যন্ত উঠেছে।",
            "সুতরাং matrix দেখায় যে V2-এর value সবচেয়ে বেশি congestion বা active-mission overlap থাকা configuration-এ। UAV বাড়ালে service capacity বাড়ে, কিন্তু নতুন task idle UAV-তে সরাসরি dispatch হলে replacement দরকার কমে; তাই accepted replacement fleet size-এর সঙ্গে সবসময় monotonic হয় না।",
            "",
            "## Recourse decision এবং rejection evidence",
            "",
        "V2 decision trace-এ প্রতিটি trigger-এর জন্য candidate UAV, displaced task, item feasibility, route feasibility, energy feasibility, old value, new value, gain এবং final decision রাখা হয়েছে। নিচের table-এ trigger-level rejection reason দেওয়া হলো; candidate-level কারণ সম্পূর্ণ JSON trace-এ দেখা যাবে।",
            "",
        "| Trigger-level rejection reason | Evidence count |",
            "|---|---:|",
        ]
    )
    for reason, count in reasons.most_common():
        lines.append("| {} | {} |".format(reason, count))
    lines.extend(
        [
            "",
            "এই অংশটির সহজ অর্থ হলো: নতুন task আসার সময় যদি UAV-গুলো active থাকে, V2 দেখে কোনো চলমান mission-এর একটি uncompleted task সরিয়ে নতুন task বসালে সত্যিই লাভ হবে কি না। একটি trigger-এ একাধিক candidate পরীক্ষা হতে পারে; তাই table-এর সংখ্যা candidate count নয়, trigger-level final outcome। মোট ৬৬৩৯টি trigger-এর মধ্যে ২২৫১টি replacement গৃহীত এবং ৪৩৮৮টি গৃহীত হয়নি—অর্থাৎ acceptance rate প্রায় 33.9%।",
            "`no_positive_gain` (2113) সবচেয়ে বেশি দেখা গেছে। অর্থাৎ candidate route ও item-এর দিক থেকে সম্ভব হলেও পুরনো task সরিয়ে নতুন task বসালে remaining service value বাড়েনি; তাই বর্তমান mission অপরিবর্তিত রাখা হয়েছে। `no_feasible_candidate` (1842) মানে কোনো candidate-ই item/inventory, route, energy reserve, return বা horizon-এর সব শর্ত একসঙ্গে পূরণ করতে পারেনি। `no_uncompleted_active_task` (433) মানে active mission-এ সরানোর মতো uncompleted task ছিল না। এই rejection-এ নতুন task হারিয়ে যায় না—pending queue-তে থেকে পরবর্তী dispatch-এর জন্য অপেক্ষা করে। Candidate-level কারণগুলো JSON decision trace-এ আলাদা করে রাখা হয়েছে।",
            "",
            "## Runtime এবং bottleneck",
            "",
            "V2 runtime-কে তিনটি অংশে পড়া হয়েছে: initial dispatch planner time, dispatch route evaluation time এবং recourse candidate evaluation time। V2-এর recourse runtime আলাদা রাখা হয়েছে, যাতে নতুন feature-এর computational overhead V1-এর route search-এর সঙ্গে মিশে না যায়।",
            "",
            "| Environment | Algorithm | Runtime s | Planner s | Route s | Recourse s | Candidate | Search truncated | Safe return |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for environment, mode in (("DU outdoor", "du_outdoor"), ("Synthetic", "synthetic")):
        for algorithm in ("V1", "V2"):
            subset = [row for row in rows if row["environment"] == mode and row["algorithm"] == algorithm]
            lines.append(
                "| {} | {} | {:.3f} | {:.3f} | {:.3f} | {:.3f} | {:.0f} | {:.1f} | {:.1f}% |".format(
                    environment,
                    algorithm,
                    mean(subset, "runtime_seconds"),
                    mean(subset, "planner_runtime_seconds"),
                    mean(subset, "route_runtime_seconds"),
                    mean(subset, "recourse_runtime_seconds"),
                    mean(subset, "candidate_count"),
                    mean(subset, "search_truncated_dispatches"),
                    100.0 * mean(subset, "safe_return_rate"),
                )
            )
    lines.extend(
        [
            "",
            "এখানে Runtime s বলতে simulation program-এর computation time বোঝায়; এটি UAV-এর real flight time বা task delay নয়। Planner s হলো initial assignment search-এর সময়, Route s হলো collision-aware route তৈরি/মূল্যায়নের সময়, আর Recourse s হলো V2-তে নতুন task replacement candidate পরীক্ষা করার অতিরিক্ত সময়।",
            "Table-এর প্রধান bottleneck হলো route evaluation। V1-এ DU outdoor-এর 20.225 s runtime-এর মধ্যে route অংশ 19.566 s (প্রায় 96.7%); Synthetic-এ 3.561 s (প্রায় 95.4%)। তবে V2-এর Runtime, Planner, Route এবং Recourse timer-গুলো mutually exclusive নয়। Planner-এর মধ্যে route evaluation থাকতে পারে এবং recourse candidate যাচাইয়ের সময়ও route check চলে; তাই এগুলো সরাসরি যোগ করে total runtime ধরা যাবে না। উদাহরণ হিসেবে DU outdoor V2-তে Route 44.692 s + Recourse 12.784 s = 57.476 s, যেখানে total Runtime 59.408 s; বাকি 1.932 s event handling, dispatch bookkeeping এবং অন্যান্য overhead। Synthetic-এ 8.513 + 1.326 = 9.839 s, total 10.355 s; residual 0.516 s। অর্থাৎ breakdown-টি bottleneck বোঝার diagnostic view, additive accounting নয়। এই ফল দেখায় V2-এর বাড়তি computation-এর বড় অংশ repeated route feasibility পরীক্ষা, আর underlying route search-ই এখনও প্রধান cost centre।",
            "DU outdoor Synthetic-এর তুলনায় অনেক ধীর, কারণ DU-তে polygon obstacle geometry এবং blocked হলে grid A* path search বেশি কাজ করে। V2 runtime V1-এর তুলনায় DU-তে প্রায় 2.94 গুণ এবং Synthetic-এ প্রায় 2.77 গুণ হয়েছে। Safe return 100% মানে simulation-এর feasibility filter পেরিয়ে সব executed mission base-এ ফিরেছে; এটি field-flight reliability-এর প্রমাণ নয়। `Search truncated` হলো যেসব dispatch ৫০,০০০ candidate limit-এ পৌঁছেছে তার গড় সংখ্যা, আর Candidate হলো পরীক্ষিত candidate plan-এর গড় count। তাই পরবর্তী efficiency কাজের প্রধান দিক হবে route reuse/cache hit measurement, early feasibility pruning এবং scalable candidate search।",
        ]
    )
    lines.extend(detailed_markdown_sections(rows, matrix, traces, validation))
    lines.extend(
        [
            "",
            "## V2 result-এর অর্থ এবং limitation",
            "",
            "1. V2 প্রথমবার active mission-এর uncompleted suffix পরিবর্তন করে নতুন task-এর priority value বিবেচনা করেছে।",
            "2. Accepted replacement-এ displaced task queue-তে ফিরে যায়; এটি task হারিয়ে ফেলা নয়।",
            "3. V2 current onboard inventory ব্যবহার করে, তাই নতুন task-এর item demand feasible না হলে recourse গ্রহণ করে না।",
            "4. Completed route prefix এবং completed delivery immutable রাখা হয়েছে।",
            "5. V2 objective final completion event থেকে একবার গণনা করা হয়েছে; replanning snapshot যোগ করে inflated করা হয়নি।",
            "6. Safe return rate planner-এর route এবং energy filter-এর ফল; এটি field flight reliability নয়।",
            "7. Energy values এখনও configured coefficients-এর ফল, field-calibrated physical battery measurement নয়।",
            "8. V2 one-for-one rule পূর্ণ mathematical optimizer বা full fleet rolling-horizon optimizer নয়।",
            "9. Reserve inventory, base reload, multiple replacement এবং broader reassignment V3-এর জন্য রাখা হয়েছে।",
            "",
            "## উপসংহার এবং পরবর্তী কাজ",
            "",
            "V1 একটি fixed active-mission reference হিসেবে অপরিবর্তিত রাখা হয়েছে। V2 সেই reference-এর উপর formulation-এর সীমিত recourse rule যোগ করেছে: নতুন high-value task এলে feasible হলে একটি active mission-এর একটি uncompleted task replace করা যায়। Paired matrix V1 এবং V2-এর operational outcome এবং recourse overhead একসঙ্গে দেখাবে।",
            "",
            "পরবর্তী version-এ reserve inventory এবং active inventory-aware reassignment যোগ করার আগে V2-এর accepted এবং rejected decision trace, service-value gain, runtime overhead এবং environment sensitivity বিশ্লেষণ করা হবে।",
            "",
            "## Reproducibility artifacts",
            "",
            "* `Simulation/results/pgbm_v2_recourse_experiments/raw_metrics/pgbm_v2_paired_matrix_metrics_tasks_30_60_90_uavs_3_5_8_10_seeds_101_110.csv`: V1 এবং V2-এর ৪৮০টি metrics row।",
            "* `Simulation/results/pgbm_v2_recourse_experiments/decision_traces/pgbm_v2_decision_traces.jsonl`: প্রতি V2 episode-এর complete recourse trace।",
            "* `Simulation/run_pgbm_v2_experiment_matrix.py`: paired matrix execution script।",
            "* `Simulation/pgbm_sim/v2/`: V2 runtime state, recourse evaluator, event runner এবং paired experiment logic।",
            "* `docs/specs/0007-pgbm-v2-task-replacement-recourse.md`: accepted formulation-aligned design specification।",
        ]
    )
    return "\n".join(lines) + "\n"


def tex_table(rows: Sequence[Mapping[str, object]], environment: str, mode: str, algorithm: str) -> str:
    subset = [row for row in rows if row["environment"] == mode and row["algorithm"] == algorithm]
    return (
        "{} & {} & {} & {} & {} & {} & {} & {} & {} \\\\\n".format(
            latex_text(environment),
            algorithm,
            plain_mean_pm(subset, "objective_value"),
            plain_mean_pm(subset, "served_tasks"),
            pct(mean(subset, "served_tasks") / mean(subset, "task_count")),
            pct(mean(subset, "parcel_delivery_rate")),
            plain_mean_pm(subset, "deferred_tasks"),
            plain_mean_pm(subset, "average_completion_delay"),
            "{:.3f}".format(mean(subset, "runtime_seconds")),
        )
    )


def detailed_tex_sections(
    rows: Sequence[Mapping[str, object]],
    matrix,
    traces: Sequence[Mapping[str, object]],
    validation: Mapping[str, object],
) -> List[str]:
    trace_stats = trace_evidence(traces)
    lines = [
        r"\section{Energy model এবং energy ফলাফল}",
        r"V1 এবং V2 উভয় version-এ energy একটি configured accounting model দিয়ে গণনা করা হয়েছে। কোনো travel segment-এর জন্য $d$ হলো route distance, $m$ হলো বহন করা payload mass এবং $a^+$ হলো positive ascent distance।",
        r"\[ E_{travel}=d e_{distance}+d m e_{payload}+a^+ e_{ascent}, \qquad E_{service}=\tau e_{service}, \qquad E_{mission}=\sum E_{travel}+\sum E_{service}. \]",
        r"এই run-এ $e_{distance}=1.0$ J/m, $e_{payload}=0.05$ J/(kg m), $e_{ascent}=0.20$ J/m এবং $e_{service}=0.50$ J/min। প্রতিটি initial বা recourse candidate-এর জন্য UAV-এর ইতিমধ্যে ব্যবহৃত energy-এর সঙ্গে revised route-এর additional energy যোগ করে check করা হয়: $E_{consumed}+E_{additional}+E_{reserve}\leq E_{capacity}$। Capacity 1000 J এবং reserve 200 J; তাই projected remaining energy-এর অন্তত reserve অংশ mission শেষে অবশিষ্ট থাকতে হয়।",
        r"$Total\ energy$ পুরো episode-এ সম্পন্ন বা horizon পর্যন্ত চলা সব mission-এর cumulative energy। এটি কোনো একক UAV-এর একবারের battery state নয়। প্রতিটি UAV base-এ ফিরে resupply/turnaround শেষ করলে পরের mission-এ নতুন full capacity থেকে শুরু করে; V1/V2-তে battery degradation বা mission-to-mission persistent battery depletion model করা হয়নি।",
        r"\begin{table}[H]\centering\scriptsize\begin{tabular}{@{}llrrrrr@{}}\toprule Environment & Algorithm & Energy J & Energy/task J & Energy/parcel J & Distance m & Travel min\\\midrule",
    ]
    for environment, mode in (("DU outdoor", "du_outdoor"), ("Synthetic", "synthetic")):
        for algorithm in ("V1", "V2"):
            subset = _environment_algorithm_rows(rows, mode, algorithm)
            lines.append(
                r"{} & {} & {} & {} & {} & {} & {} \\".format(
                    latex_text(environment),
                    algorithm,
                    tex_metric_pm(subset, "total_energy", 1),
                    tex_metric_pm(subset, "energy_per_served_task", 1),
                    tex_metric_pm(subset, "energy_per_dropped_parcel", 1),
                    tex_metric_pm(subset, "total_distance", 1),
                    tex_metric_pm(subset, "total_travel_time", 1),
                )
            )
    lines.extend(
        [
            r"\bottomrule\end{tabular}\end{table}",
            r"Energy result-এর মূল trade-off হলো: DU outdoor-এ V2 total energy 6142.4 J থেকে 6078.6 J-এ এবং distance 5928.2 m থেকে 5854.1 m-এ কমেছে, কারণ V2 কিছু lower-value task replace বা queue করে এবং infeasible বা energy-expensive candidate গ্রহণ করে না। কিন্তু completed task ও parcel কম হওয়ায় প্রতি served task energy 310.2 থেকে 314.7 J এবং প্রতি dropped parcel 199.3 থেকে 224.5 J হয়েছে। Synthetic-এ V2 total energy 5319.7 J থেকে 5368.8 J এবং distance 5041.4 m থেকে 5083.6 m-এ সামান্য বেড়েছে; accepted recourse-এর revised route এই অতিরিক্ত movement তৈরি করেছে। তাই শুধু total energy দিয়ে efficiency বিচার করা যাবে না; cumulative energy, energy per completed service এবং distance একসঙ্গে দেখতে হবে।",
            r"\section{Expanded V1 বনাম V2 result matrix}",
            r"নিচের দুইটি matrix-এ প্রতিটি cell-এর ১০টি seed-এর mean $\pm$ standard deviation দেওয়া হয়েছে। ফলে objective, served task, parcel volume, queue, energy, recourse এবং runtime-এর seed variability একই সঙ্গে দেখা যায়।",
            r"\begin{landscape}\begin{longtable}{@{}lrrlrrrrrrrr@{}}",
            r"\caption{Service, parcel এবং queue metrics: mean $\pm$ standard deviation।}\label{tab:v2-service-metrics}\\",
            r"\toprule Environment & Task & UAV & Alg & Obj & Served & Task rate & Req. parcel & Drop parcel & Deferred & Delay & Peak queue\\\midrule",
            r"\endfirsthead\toprule Environment & Task & UAV & Alg & Obj & Served & Task rate & Req. parcel & Drop parcel & Deferred & Delay & Peak queue\\\midrule\endhead",
        ]
    )
    for cell in matrix:
        for algorithm, group in (("V1", cell["v1"]), ("V2", cell["v2"])):
            lines.append(
                r"{} & {} & {} & {} & {} & {} & {} & {} & {} & {} & {} & {} \\".format(
                    latex_text(cell["environment"]),
                    cell["task_count"],
                    cell["uav_count"],
                    algorithm,
                    tex_metric_pm(group, "objective_value", 2),
                    tex_metric_pm(group, "served_tasks", 2),
                    tex_metric_percent_pm(group, "task_rate", 1),
                    tex_metric_pm(group, "requested_parcels", 1),
                    tex_metric_pm(group, "dropped_parcels", 1),
                    tex_metric_pm(group, "deferred_tasks", 2),
                    tex_metric_pm(group, "average_completion_delay", 2),
                    tex_metric_pm(group, "peak_queue_size", 1),
                )
            )
    lines.extend(
        [
            r"\bottomrule\end{longtable}\end{landscape}",
            r"\begin{landscape}\begin{longtable}{@{}lrrlrrrrrr@{}}",
            r"\caption{Resource metrics: mean $\pm$ standard deviation।}\label{tab:v2-resource-metrics}\\",
            r"\toprule Environment & Task & UAV & Alg & Distance & Travel & Energy & E/task & E/parcel & Safe return\\\midrule",
            r"\endfirsthead\toprule Environment & Task & UAV & Alg & Distance & Travel & Energy & E/task & E/parcel & Safe return\\\midrule\endhead",
        ]
    )
    for cell in matrix:
        for algorithm, group in (("V1", cell["v1"]), ("V2", cell["v2"])):
            lines.append(
                r"{} & {} & {} & {} & {} & {} & {} & {} & {} & {} \\".format(
                    latex_text(cell["environment"]),
                    cell["task_count"],
                    cell["uav_count"],
                    algorithm,
                    tex_metric_pm(group, "total_distance", 1),
                    tex_metric_pm(group, "total_travel_time", 1),
                    tex_metric_pm(group, "total_energy", 1),
                    tex_metric_pm(group, "energy_per_served_task", 1),
                    tex_metric_pm(group, "energy_per_dropped_parcel", 1),
                    tex_metric_percent_pm(group, "safe_return_rate", 1),
                )
            )
    lines.extend(
        [
            r"\bottomrule\end{longtable}\end{landscape}",
            r"\begin{landscape}\begin{longtable}{@{}lrrlrrrrr@{}}",
            r"\caption{Recourse এবং runtime metrics: mean $\pm$ standard deviation।}\label{tab:v2-recourse-metrics}\\",
            r"\toprule Environment & Task & UAV & Alg & Trigger & Accepted & Rejected & Gain & Runtime\\\midrule",
            r"\endfirsthead\toprule Environment & Task & UAV & Alg & Trigger & Accepted & Rejected & Gain & Runtime\\\midrule\endhead",
        ]
    )
    for cell in matrix:
        for algorithm, group in (("V1", cell["v1"]), ("V2", cell["v2"])):
            lines.append(
                r"{} & {} & {} & {} & {} & {} & {} & {} & {} \\".format(
                    latex_text(cell["environment"]),
                    cell["task_count"],
                    cell["uav_count"],
                    algorithm,
                    tex_metric_pm(group, "recourse_trigger_count", 1),
                    tex_metric_pm(group, "accepted_replacements", 1),
                    tex_metric_pm(group, "rejected_replacements", 1),
                    tex_metric_pm(group, "replacement_gain", 3),
                    tex_metric_pm(group, "runtime_seconds", 3),
                )
            )
    lines.extend(
        [
            r"\bottomrule\end{longtable}\end{landscape}",
            r"এই expanded matrix-এ absolute requested/dropped parcel, task rate, deferred task এবং peak queue সরাসরি দেওয়া হয়েছে; parcel rate একা দেখে service volume অনুমান করতে হবে না। Resource table-এ distance এবং energy পাশাপাশি থাকায় route length বাড়ার সঙ্গে payload, ascent এবং service energy কীভাবে বদলেছে সেটিও দেখা যায়। Recourse table-এ trigger, accepted/rejected replacement, gain এবং runtime আলাদা করে দেখানো হয়েছে।",
            r"\section{Recourse evidence: environment, load, fleet এবং phase}",
            r"Trigger-level মোট outcome-এর পাশাপাশি trace থেকে acceptance rate আলাদা করে হিসাব করা হয়েছে। Accepted gain-এর mean $\pm$ standard deviation এখানে accepted event-এর $\Delta J$; episode-level $replacement\_gain$ তার থেকে আলাদা cumulative quantity।",
            r"\begin{table}[H]\centering\scriptsize\begin{tabular}{@{}llrrrrr@{}}\toprule Group type & Group & Trigger & Accepted & Rate & Rejected & Gain mean $\pm$ std\\\midrule",
        ]
    )
    grouped_trace_stats = []
    for group_type, groups in (
        ("Environment", (("DU outdoor", trace_stats["by_environment"].get("du_outdoor", {})), ("Synthetic", trace_stats["by_environment"].get("synthetic", {})))),
        ("Task load", tuple((str(key), trace_stats["by_task_count"][key]) for key in sorted(trace_stats["by_task_count"]))),
        ("UAV count", tuple((str(key), trace_stats["by_uav_count"][key]) for key in sorted(trace_stats["by_uav_count"]))),
        ("Arrival phase", tuple((key, trace_stats["by_phase"][key]) for key in ("High", "Medium", "Low"))),
    ):
        for label, summary in groups:
            grouped_trace_stats.append((group_type, label, summary))
            lines.append(
                r"{} & {} & {} & {} & {:.1f}\% & {} & {:.3f} $\pm$ {:.3f} \\".format(
                    latex_text(group_type),
                    latex_text(label),
                    summary.get("triggers", 0),
                    summary.get("accepted", 0),
                    100.0 * summary.get("rate", 0.0),
                    summary.get("rejected", 0),
                    summary.get("gain_mean", 0.0),
                    summary.get("gain_std", 0.0),
                )
            )
    total_candidates = sum(trace_stats["candidate_reasons"].values())
    lines.extend(
        [
            r"\bottomrule\end{tabular}\end{table}",
            r"\subsection{Candidate-level rejection breakdown}",
            r"একটি trigger-এর ভিতরে একাধিক candidate থাকতে পারে। তাই নিচের count candidate-level; আগের rejection table-এর count trigger-level final reason।",
            r"\begin{table}[H]\centering\scriptsize\begin{tabular}{@{}lrr@{}}\toprule Candidate outcome/reason & Count & Share\\\midrule",
        ]
    )
    reason_labels = (
        ("onboard_inventory", "Onboard inventory"),
        ("payload_capacity", "Payload capacity"),
        ("route_infeasible", "Route infeasible"),
        ("energy_reserve", "Energy reserve"),
        ("horizon", "Horizon"),
        ("service_in_progress", "Service in progress"),
        ("non_positive_gain", "Non-positive gain"),
        ("feasible_positive_gain", "Feasible positive gain"),
    )
    for key, label in reason_labels:
        count = int(trace_stats["candidate_reasons"].get(key, 0))
        lines.append(r"{} & {} & {:.1f}\% \\".format(latex_text(label), count, 100.0 * count / total_candidates if total_candidates else 0.0))
    unique_total = int(trace_stats["unique_displaced"])
    unique_completed = int(trace_stats["unique_displaced_completed"])
    unique_deferred = int(trace_stats["unique_displaced_deferred"])
    lines.extend(
        [
            r"\bottomrule\end{tabular}\end{table}",
            r"Accepted replacement-এর পরে {}টি unique displaced-task instance-এর মধ্যে {}টি ({:.1f}\%) horizon-এর মধ্যে পরে complete হয়েছে এবং {}টি ({:.1f}\%) deferred থেকেছে। মোট accepted event ছিল {}; এর মধ্যে {}টি repeated displacement event, তাই event count এবং unique task count আলাদা করে report করা হয়েছে।".format(
                unique_total,
                unique_completed,
                100.0 * unique_completed / unique_total if unique_total else 0.0,
                unique_deferred,
                100.0 * unique_deferred / unique_total if unique_total else 0.0,
                trace_stats["all"]["accepted"],
                trace_stats["repeated_displacement_events"],
            ),
        ]
    )
    accepted_example = trace_stats.get("accepted_example")
    rejected_example = trace_stats.get("rejected_example")
    if accepted_example:
        lines.append(
            r"Accepted trace example: \texttt{{{}}}-এ $t={:.2f}$ min-এ {} দ্বারা \texttt{{{}}} task-কে সরিয়ে \texttt{{{}}} task বসানো হয়েছে; old value {:.3f}, new value {:.3f}, gain +{:.3f}.".format(
                latex_text(accepted_example["scenario_id"]),
                float(accepted_example["trigger_time"]),
                latex_text(accepted_example.get("selected_uav_id")),
                latex_text(accepted_example.get("displaced_task_id")),
                latex_text(accepted_example.get("new_task_id")),
                float(accepted_example.get("old_value", 0.0)),
                float(accepted_example.get("new_value", 0.0)),
                float(accepted_example.get("delta_value", 0.0)),
            )
        )
    if rejected_example:
        candidate = next(
            (item for item in rejected_example.get("candidates", []) if _candidate_reason(str(item.get("rejection_reason", ""))) == "non_positive_gain"),
            rejected_example.get("candidates", [{}])[0],
        )
        lines.append(
            r"Rejected trace example: \texttt{{{}}}-এ $t={:.2f}$ min-এ \texttt{{{}}} task-এর জন্য candidate gain {:.3f}; candidate feasible হলেও gain positive নয়, তাই final reason \texttt{{{}}} এবং task queue-তে রাখা হয়েছে.".format(
                latex_text(rejected_example["scenario_id"]),
                float(rejected_example["trigger_time"]),
                latex_text(rejected_example.get("new_task_id")),
                float(candidate.get("delta_value", 0.0)),
                latex_text(rejected_example.get("reason")),
            )
        )
    lines.extend(
        [
            r"\section{Validation evidence}",
            r"একটি sentence-এর বদলে paired matrix এবং ছোট deterministic replay fixture-এর evidence নিচে দেওয়া হলো। Fixed-control fixture-এ V1 এবং V2 recourse-disabled একই scenario-তে চালানো হয়েছে; heavy matrix-এর ২৪০টি pair-এ scenario fingerprint match আলাদা করে যাচাই করা হয়েছে।",
            r"\begin{table}[H]\centering\scriptsize\begin{tabular}{@{}p{0.31\textwidth}p{0.43\textwidth}l@{}}\toprule Validation check & Evidence & Result\\\midrule",
            r"Same scenario fingerprint এবং task realization & {}টি paired cell-এর fingerprint match & {}\\".format(validation.get("paired_count", 0), "PASS" if validation.get("same_seed_task_realization") else "FAIL"),
            r"Fixed-control objective & V1 {:.6f}; V2 fixed {:.6f} & {}\\".format(validation.get("v1_objective", 0.0), validation.get("fixed_objective", 0.0), "PASS" if validation.get("fixed_matches", {}).get("objective") else "FAIL"),
            r"Fixed-control served task & Same served-task ID set & {}\\".format("PASS" if validation.get("fixed_matches", {}).get("served") else "FAIL"),
            r"Fixed-control distance and energy & Both values match within tolerance & {}\\".format("PASS" if validation.get("fixed_matches", {}).get("distance") and validation.get("fixed_matches", {}).get("energy") else "FAIL"),
            r"Fixed-control candidate count & Same candidate count & {}\\".format("PASS" if validation.get("fixed_matches", {}).get("candidate_count") else "FAIL"),
            r"Deterministic replay & Repeated V2 run produced identical events and decisions & {}\\".format("PASS" if validation.get("deterministic_replay") else "FAIL"),
            r"Duplicate completion & Completed event IDs are unique & {}\\".format("PASS" if validation.get("duplicate_completion_free") else "FAIL"),
            r"Objective double-counting & Reported {:.6f}; direct final-completion sum {:.6f} & {}\\".format(validation.get("reported_objective", 0.0), validation.get("recomputed_objective", 0.0), "PASS" if validation.get("objective_once") else "FAIL"),
            r"\bottomrule\end{tabular}\end{table}",
            r"Validation fixture: \texttt{{{}}}. এটি report-এর reproducibility check; full result matrix-এর performance estimate নয়.".format(latex_text(validation.get("fixture", "unavailable"))),
        ]
    )
    return lines


def generate_tex(
    rows: Sequence[Mapping[str, object]],
    matrix,
    traces: Sequence[Mapping[str, object]],
    validation: Mapping[str, object],
) -> str:
    v2_rows = [row for row in rows if row["algorithm"] == "V2"]
    reasons = rejection_totals(rows)
    lines = [
        r"% Bangla comparative report for PGBM Initial Solution V2.",
        r"\documentclass[10pt,a4paper]{article}",
        r"\usepackage{fontspec}",
        r"\usepackage{polyglossia}",
        r"\setmainlanguage{bengali}",
        r"\setotherlanguage{english}",
        r"\setmainfont[Script=Bengali]{Siyam Rupali}",
        r"\setsansfont[Script=Bengali]{Siyam Rupali}",
        r"\newfontfamily\bengalifonttt[Script=Bengali]{Siyam Rupali}",
        r"\usepackage[a4paper,margin=20mm,headheight=24pt]{geometry}",
        r"\usepackage{amsmath,array,booktabs,enumitem,fancyhdr,float,longtable,pdflscape,tabularx,titlesec,xcolor,hyperref}",
        r"\definecolor{navy}{HTML}{17365D}",
        r"\definecolor{bluegray}{HTML}{EAF1F8}",
        r"\definecolor{lightgray}{HTML}{F4F6F8}",
        r"\definecolor{midgray}{HTML}{5B6573}",
        r"\definecolor{rulegray}{HTML}{C9D1D9}",
        r"\hypersetup{colorlinks=true,linkcolor=navy,urlcolor=navy,pdftitle={PGBM Initial Solution V2 Comparative Report},pdfauthor={PGBM Thesis Simulation Work}}",
        r"\setlist[itemize]{label={-},leftmargin=*,itemsep=1pt,topsep=2pt}",
        r"\setlist[enumerate]{leftmargin=*,itemsep=3pt,topsep=2pt}",
        r"\titleformat{\section}{\Large\bfseries}{\thesection}{0.75em}{}",
        r"\titlespacing*{\section}{0pt}{2.5ex plus 0.4ex minus 0.2ex}{1ex plus 0.2ex}",
        r"\setlength{\parindent}{0pt}",
        r"\setlength{\parskip}{4pt}",
        r"\setlength{\emergencystretch}{2em}",
        r"\pagestyle{fancy}",
        r"\fancyhf{}",
        r"\fancyhead[L]{\textcolor{midgray}{PGBM Thesis Simulation}}",
        r"\fancyhead[R]{\textcolor{midgray}{Initial Solution V2}}",
        r"\fancyfoot[C]{\textcolor{midgray}{\thepage}}",
        r"\renewcommand{\headrulewidth}{0.4pt}",
        r"\renewcommand{\headrule}{\hbox to\headwidth{\color{rulegray}\leaders\hrule height \headrulewidth\hfill}}",
        r"\newcommand{\code}[1]{\path{#1}}",
        r"\begin{document}",
        r"\begin{titlepage}",
        r"\thispagestyle{empty}",
        r"\vspace*{18mm}",
        r"{\color{navy}\rule{\textwidth}{1.5pt}}\\[10mm]",
        r"{\color{navy}\sffamily\bfseries\fontsize{25}{32}\selectfont Initial Solution V2\\Comparative Simulation Report\par}",
        r"\vspace{6mm}",
        r"{\color{midgray}\sffamily\Large Task replacement recourse, paired experiment এবং ফলাফল\par}",
        r"\vfill",
        r"\begin{tabular}{@{}ll@{}}",
        r"\textbf{Project:} & PGBM thesis and simulation work\\",
        r"\textbf{সমাধানের ধরন:} & Formulation aligned one-for-one recourse\\",
        r"\textbf{Environment:} & Synthetic এবং DU outdoor\\",
        r"\textbf{মোট configuration:} & ২৪০টি paired configuration, ৪৮০টি row\\",
        r"\textbf{Seed:} & ১০১--১১০\\",
        r"\textbf{Report date:} & ২৮ সেপ্টেম্বর ২০২৬",
        r"\end{tabular}",
        r"\vfill",
        r"\begin{center}",
        r"\colorbox{bluegray}{\begin{minipage}{0.88\textwidth}",
        r"এই report-এ V2-এর core recourse rule, runtime state, paired experiment এবং V1 বনাম V2 ফলাফল একই flow-তে ব্যাখ্যা করা হয়েছে।",
        r"\end{minipage}}",
        r"\end{center}",
        r"\vspace{12mm}",
        r"{\color{navy}\rule{\textwidth}{1.5pt}}",
        r"\end{titlepage}",
        r"\tableofcontents",
        r"\clearpage",
        r"\section{V2-এর core feature}",
        r"V2 হলো formulation-aligned one-for-one active-mission task replacement recourse। নতুন task আসলে সব responder UAV active থাকলে প্রতিটি active mission-এর uncompleted task একবার করে replace করার candidate পরীক্ষা করা হয়। Completed task এবং completed route prefix অপরিবর্তিত থাকে। New task-এর item demand current onboard inventory দিয়ে মেটানো সম্ভব হতে হয়; remaining route existing collision-aware 3D routing layer দিয়ে একই base-এ ফেরত তৈরি হয়; এবং শুধু positive $\Delta J=J_{\mathrm{new}}-J_{\mathrm{old}}$ হলে সর্বোচ্চ gain-এর candidate গ্রহণ করা হয়। Displaced task waiting queue-তে ফিরে যায়।",
        r"\begin{itemize}",
        r"\item One-for-one replacement: একটি active UAV এবং একটি uncompleted task।",
        r"\item Completed prefix protection: completed delivery এবং route segment পরিবর্তন করা হয় না।",
        r"\item Current onboard inventory: reserve inventory বা base reload V2-তে নেই।",
        r"\item Remaining route recourse: current position থেকে task suffix এবং একই base-এ return route নতুন করে তৈরি হয়।",
        r"\item Positive service-value gain: $\Delta J>0$ না হলে active mission অপরিবর্তিত থাকে।",
        r"\item V1 isolation: V1 entry point এবং canonical evidence overwrite করা হয়নি।",
        r"\end{itemize}",
        r"Reserve inventory, base reload, multiple-task replacement এবং full fleet reoptimization Version 3 scope।",
        r"\section{Experiment-এর সংক্ষিপ্ত চিত্র}",
        r"V2 একই ১২০ মিনিটের seeded event-driven protocol ব্যবহার করে: ০--৪০ মিনিট high, ৪০--৮০ মিনিট medium এবং ৮০--১২০ মিনিট low arrival phase। দুইটি environment, ৩০/৬০/৯০ task load, ৩/৫/৮/১০ UAV এবং ১০টি seed (১০১--১১০) ব্যবহার করা হয়েছে। ফলে ২৪০টি configuration-এ V1 এবং V2-এর ৪৮০টি metrics row এবং ২৪০টি V2 decision trace তৈরি হয়েছে।",
        r"V1-এর preserved canonical matrix comparison row হিসেবে রাখা হয়েছে। V2 একই local scene এবং task seed protocol-এ চালানো হয়েছে। In-memory paired validation-এ recourse disabled করলে V2 fixed control-এর objective, served task, distance, energy এবং candidate count V1-এর সঙ্গে মিলে গেছে।",
        r"\section{V2 algorithm কীভাবে assignment এবং recourse ঠিক করে}",
        r"V2-এর initial dispatch V1-এর bounded brute-force assignment এবং task-order rule ব্যবহার করে। নতুন task arrival হলে V2 পুরো fleet replan করে না। Current mission state থেকে প্রতিটি active UAV এবং প্রতিটি uncompleted task-এর জন্য একটি candidate তৈরি হয়।",
        r"\begin{enumerate}",
        r"\item Current time-এ UAV-এর position, completed task, remaining task, onboard item, payload এবং consumed energy project করা হয়।",
        r"\item একটি uncompleted task সরিয়ে নতুন task-টি একই mission position-এ বসানো হয়।",
        r"\item Service চলতে থাকলে তা interrupt করা হয় না; candidate current service শেষ হওয়ার পরের suffix পরিবর্তন করে।",
        r"\item New task এবং revised mission-এর item demand current onboard inventory দিয়ে মেটানো যায় কি না পরীক্ষা করা হয়।",
        r"\item Current position থেকে revised task sequence এবং একই physical base পর্যন্ত collision-aware 3D route তৈরি হয়।",
        r"\item Payload, route, energy reserve এবং ১২০ মিনিটের horizon feasibility পরীক্ষা হয়।",
        r"\item Old remaining value, new remaining value এবং $\Delta J$ হিসাব করা হয়।",
        r"\item সর্বোচ্চ positive $\Delta J$ গ্রহণ করা হয়; positive candidate না থাকলে নতুন task queue-তে থাকে।",
        r"\end{enumerate}",
        r"Final episode objective প্রত্যেক completed task-এর service value একবার গণনা করে; replanning snapshot যোগ করে double counting করা হয় না।",
        r"\section{Simulation environment এবং route flow}",
        r"V2 একই V1 scene, task, parcel, drop-off waypoint, payload, energy এবং route contracts ব্যবহার করে। প্রতিটি task individual delivery request; task-এর food, water এবং medical demand, ২--৪ m vertical drop-off waypoint এবং ০.৫ মিনিট per parcel service duration অপরিবর্তিত আছে।",
        r"একটি active mission-এর route হলো Base $\rightarrow$ task waypoint sequence $\rightarrow$ Base। Recourse trigger হলে completed route অংশকে আবার plan করা হয় না। UAV-এর projected current position থেকে শুধু remaining suffix নতুন করে route করা হয়। প্রতিটি leg existing cruise-altitude check, direct line check, blocked হলে grid A* এবং vertical clearance check অনুসরণ করে।",
        r"\section{Result বোঝার জন্য প্রধান metric}",
        r"Objective completion-time exponential service value; served task এবং dropped parcel আলাদা unit; accepted replacement positive $\Delta J$-এর count; replacement gain event-level evidence; runtime, planner, route এবং recourse সময়ের আলাদা breakdown।",
        r"\section{Environment-level V1 বনাম V2 ফলাফল}",
        r"\begin{table}[htbp]\centering\scriptsize",
        r"\caption{Environment-level V1 এবং V2 aggregate result।}",
        r"\begin{tabular}{@{}llrrrrrrr@{}}\toprule",
        r"Environment & Algorithm & Objective & Served & Task rate & Parcel rate & Deferred & Delay min & Runtime s\\\midrule",
    ]
    for environment, mode in (("DU outdoor", "du_outdoor"), ("Synthetic", "synthetic")):
        for algorithm in ("V1", "V2"):
            lines.append(tex_table(rows, environment, mode, algorithm))
    lines.extend(
        [
            r"\bottomrule\end{tabular}\end{table}",
            r"এই table থেকে কয়েকটি ফলাফল পরিষ্কার। DU outdoor-এ V2 objective 10.43 থেকে 11.70 হয়েছে (প্রায় 12.2\% বৃদ্ধি), যদিও served task 20.12 থেকে 19.63 এবং parcel rate 36.6\% থেকে 33.4\%-এ সামান্য কমেছে। Synthetic-এ objective 23.48 থেকে 23.84 (প্রায় 1.5\%) বেড়েছে, কিন্তু served task এবং parcel rate-ও সামান্য কমেছে। অর্থাৎ V2-এর লাভ raw task count নয়; active mission-এর মধ্যে কোন task আগে complete করলে time-sensitive service value বেশি হবে, সেটি বেছে নেওয়া।",
            r"সবচেয়ে গুরুত্বপূর্ণ পরিবর্তনটি Delay min-এ। DU outdoor-এ average delay 31.64 থেকে 23.21 মিনিটে (8.43 মিনিট বা প্রায় 26.6\%) এবং Synthetic-এ 18.30 থেকে 16.08 মিনিটে (2.22 মিনিট বা প্রায় 12.1\%) কমেছে। Delay min হলো task detect হওয়ার সময় থেকে delivery complete হওয়া পর্যন্ত গড় সময়। নতুন task এলে V2 শুধু সেই replacement নেয় যার revised remaining mission value পুরনো mission-এর চেয়ে বেশি; ফলে অপেক্ষমাণ high-value task অনেক ক্ষেত্রে আগের completion position পায়। তবে এটি সব task-এর delay কমেছে—এমন দাবি নয়; কিছু lower-value displaced task queue-তে ফেরত যায়, তাই served count কমেও average completed-task delay কমতে পারে।",
            r"এর বিপরীতে V2 runtime DU outdoor-এ 20.225 থেকে 59.408 s এবং Synthetic-এ 3.733 থেকে 10.355 s হয়েছে। কারণ প্রতিটি recourse trigger-এ সম্ভাব্য active UAV ও displaced task-এর জন্য feasibility এবং revised route পরীক্ষা করা হয়। তাই V2-এর মূল trade-off হলো—priority-weighted service value এবং completion delay উন্নত করার বিনিময়ে অতিরিক্ত computation।",
            r"\section{Task load এবং UAV sensitivity}",
            r"Task load বাড়লে queue pressure বাড়ে এবং V1 ও V2 দুই version-এর service rate সাধারণত কমে। UAV সংখ্যা বাড়ালে available capacity বাড়ে, কিন্তু নতুন task idle UAV-তে dispatch হয়ে গেলে recourse trigger-এর সুযোগ কমতেও পারে। তাই V2 accepted replacement fleet size-এর সঙ্গে monotonic হওয়া আবশ্যক নয়।",
            r"\begin{landscape}\begin{longtable}{@{}llrrrrrrrrrrrr@{}}",
            r"\caption{সম্পূর্ণ V1 বনাম V2 task load এবং fleet matrix।}\label{tab:v2-full-matrix}\\",
            r"\toprule Environment & Task & UAV & V1 Obj & V2 Obj & $\Delta$Obj & V1 Served & V2 Served & $\Delta$Served & V1 Parcel & V2 Parcel & $\Delta$Parcel & V2 Repl & V2 Runtime\\\midrule",
            r"\endfirsthead\toprule Environment & Task & UAV & V1 Obj & V2 Obj & $\Delta$Obj & V1 Served & V2 Served & $\Delta$Served & V1 Parcel & V2 Parcel & $\Delta$Parcel & V2 Repl & V2 Runtime\\\midrule\endhead",
        ]
    )
    for cell in matrix:
        v1 = cell["v1"]
        v2 = cell["v2"]
        lines.append(
            "{} & {} & {} & {:.2f} & {:.2f} & {:+.2f} & {:.2f} & {:.2f} & {:+.2f} & {:.1f}\% & {:.1f}\% & {:+.1f} pp & {:.2f} & {:.3f} \\\\\n".format(
                cell["environment"],
                cell["task_count"],
                cell["uav_count"],
                mean(v1, "objective_value"),
                mean(v2, "objective_value"),
                mean(v2, "objective_value") - mean(v1, "objective_value"),
                mean(v1, "served_tasks"),
                mean(v2, "served_tasks"),
                mean(v2, "served_tasks") - mean(v1, "served_tasks"),
                100.0 * mean(v1, "parcel_delivery_rate"),
                100.0 * mean(v2, "parcel_delivery_rate"),
                100.0 * (mean(v2, "parcel_delivery_rate") - mean(v1, "parcel_delivery_rate")),
                mean(v2, "accepted_replacements"),
                mean(v2, "runtime_seconds"),
            )
        )
    lines.extend(
        [
            r"\bottomrule\end{longtable}\end{landscape}",
            r"এই matrix-এর প্রধান patternগুলো হলো: (১) DU outdoor-এর ১২টি configuration-এর সবকটিতেই V2 objective V1-এর চেয়ে বেশি। বিশেষ করে ৯০ task-এ gain 1.30 থেকে 2.59 পর্যন্ত, অর্থাৎ load বাড়লে recourse-এর priority benefit বেশি দৃশ্যমান হয়। (২) DU outdoor-এ ৬০ task/৩ UAV ছাড়া served task সামান্য কমেছে বা প্রায় অপরিবর্তিত থেকেছে; parcel rate-ও সব cell-এ কমেছে। কারণ V2 কিছু lower-value active task সরিয়ে বেশি time-sensitive task বসায়—এটি throughput-maximization rule নয়। (৩) Synthetic-এ low load এবং বেশি UAV থাকলে V1-এর capacity প্রায় যথেষ্ট; ৩০ task/১০ UAV-এ accepted replacement গড় ০ এবং objective পরিবর্তন ০.০০। তাই সেখানে V2-এর বাড়তি লাভ সীমিত। (৪) Synthetic-এর ৬০ task/১০ UAV cell-এ একমাত্র সামান্য negative objective change (-0.09) দেখা গেছে—এই configuration-এ replacement-এর লাভ computation/queue trade-off পুরোপুরি offset করতে পারেনি। (৫) ৯০ task-এ accepted replacement এবং runtime সাধারণত বাড়ে; DU outdoor-এ ৯০ task/১০ UAV runtime 134.039 s পর্যন্ত উঠেছে।",
            r"সুতরাং matrix দেখায় যে V2-এর value সবচেয়ে বেশি congestion বা active-mission overlap থাকা configuration-এ। UAV বাড়ালে service capacity বাড়ে, কিন্তু নতুন task idle UAV-তে সরাসরি dispatch হলে replacement দরকার কমে; তাই accepted replacement fleet size-এর সঙ্গে সবসময় monotonic হয় না।",
            r"\section{Recourse decision এবং rejection evidence}",
            r"প্রতিটি trigger-এর candidate UAV, displaced task, item feasibility, route feasibility, energy feasibility, old value, new value, gain এবং final decision decision trace-এ রাখা হয়েছে। নিচের table-এ trigger-level rejection reason দেওয়া হলো; candidate-level কারণ সম্পূর্ণ JSON trace-এ দেখা যাবে।",
            r"\begin{table}[htbp]\centering\scriptsize\begin{tabular}{@{}lr@{}}\toprule Trigger-level rejection reason & Evidence count\\\midrule",
        ]
    )
    for reason, count in reasons.most_common():
        lines.append("{} & {} \\\\\n".format(latex_text(reason), count))
    lines.extend(
        [
            r"\bottomrule\end{tabular}\end{table}",
            r"এই অংশটির সহজ অর্থ হলো: নতুন task আসার সময় যদি UAV-গুলো active থাকে, V2 দেখে কোনো চলমান mission-এর একটি uncompleted task সরিয়ে নতুন task বসালে সত্যিই লাভ হবে কি না। একটি trigger-এ একাধিক candidate পরীক্ষা হতে পারে; তাই table-এর সংখ্যা candidate count নয়, trigger-level final outcome। মোট ৬৬৩৯টি trigger-এর মধ্যে ২২৫১টি replacement গৃহীত এবং ৪৩৮৮টি গৃহীত হয়নি—অর্থাৎ acceptance rate প্রায় 33.9\%।",
            r"$\texttt{no\_positive\_gain}$ (2113) সবচেয়ে বেশি দেখা গেছে। অর্থাৎ candidate route ও item-এর দিক থেকে সম্ভব হলেও পুরনো task সরিয়ে নতুন task বসালে remaining service value বাড়েনি; তাই বর্তমান mission অপরিবর্তিত রাখা হয়েছে। $\texttt{no\_feasible\_candidate}$ (1842) মানে কোনো candidate-ই item/inventory, route, energy reserve, return বা horizon-এর সব শর্ত একসঙ্গে পূরণ করতে পারেনি। $\texttt{no\_uncompleted\_active\_task}$ (433) মানে active mission-এ সরানোর মতো uncompleted task ছিল না। এই rejection-এ নতুন task হারিয়ে যায় না—pending queue-তে থেকে পরবর্তী dispatch-এর জন্য অপেক্ষা করে। Candidate-level কারণগুলো JSON decision trace-এ আলাদা করে রাখা হয়েছে।",
            r"\section{Runtime এবং প্রধান bottleneck}",
            r"এখানে Runtime s বলতে simulation program-এর computation time বোঝায়; এটি UAV-এর real flight time বা task delay নয়। Planner s হলো initial assignment search-এর সময়, Route s হলো collision-aware route তৈরি/মূল্যায়নের সময়, আর Recourse s হলো V2-তে নতুন task replacement candidate পরীক্ষা করার অতিরিক্ত সময়।",
            r"\begin{table}[H]\centering\scriptsize\begin{tabular}{@{}llrrrrrrr@{}}\toprule Environment & Algorithm & Runtime s & Planner s & Route s & Recourse s & Candidate & Truncated & Safe return\\\midrule",
        ]
    )
    for environment, mode in (("DU outdoor", "du_outdoor"), ("Synthetic", "synthetic")):
        for algorithm in ("V1", "V2"):
            subset = [row for row in rows if row["environment"] == mode and row["algorithm"] == algorithm]
            lines.append(
                "{} & {} & {:.3f} & {:.3f} & {:.3f} & {:.3f} & {:.0f} & {:.1f} & {:.1f}\% \\\\\n".format(
                    environment,
                    algorithm,
                    mean(subset, "runtime_seconds"),
                    mean(subset, "planner_runtime_seconds"),
                    mean(subset, "route_runtime_seconds"),
                    mean(subset, "recourse_runtime_seconds"),
                    mean(subset, "candidate_count"),
                    mean(subset, "search_truncated_dispatches"),
                    100.0 * mean(subset, "safe_return_rate"),
                )
            )
    lines.extend(
        [
            r"\bottomrule\end{tabular}\end{table}",
            r"Table-এর প্রধান bottleneck হলো route evaluation। V1-এ DU outdoor-এর 20.225 s runtime-এর মধ্যে route অংশ 19.566 s (প্রায় 96.7\%); Synthetic-এ 3.561 s (প্রায় 95.4\%)। তবে V2-এর Runtime, Planner, Route এবং Recourse timer-গুলো mutually exclusive নয়। Planner-এর মধ্যে route evaluation থাকতে পারে এবং recourse candidate যাচাইয়ের সময়ও route check চলে; তাই এগুলো সরাসরি যোগ করে total runtime ধরা যাবে না। উদাহরণ হিসেবে DU outdoor V2-তে Route 44.692 s + Recourse 12.784 s = 57.476 s, যেখানে total Runtime 59.408 s; বাকি 1.932 s event handling, dispatch bookkeeping এবং অন্যান্য overhead। Synthetic-এ 8.513 + 1.326 = 9.839 s, total 10.355 s; residual 0.516 s। অর্থাৎ breakdown-টি bottleneck বোঝার diagnostic view, additive accounting নয়। এই ফল দেখায় V2-এর বাড়তি computation-এর বড় অংশ repeated route feasibility পরীক্ষা, আর underlying route search-ই এখনও প্রধান cost centre।",
            r"DU outdoor Synthetic-এর তুলনায় অনেক ধীর, কারণ DU-তে polygon obstacle geometry এবং blocked হলে grid A* path search বেশি কাজ করে। V2 runtime V1-এর তুলনায় DU-তে প্রায় 2.94 গুণ এবং Synthetic-এ প্রায় 2.77 গুণ হয়েছে। Safe return 100\% মানে simulation-এর feasibility filter পেরিয়ে সব executed mission base-এ ফিরেছে; এটি field-flight reliability-এর প্রমাণ নয়। `Search truncated` হলো যেসব dispatch ৫০,০০০ candidate limit-এ পৌঁছেছে তার গড় সংখ্যা, আর Candidate হলো পরীক্ষিত candidate plan-এর গড় count। তাই পরবর্তী efficiency কাজের প্রধান দিক হবে route reuse/cache hit measurement, early feasibility pruning এবং scalable candidate search।",
        ]
    )
    lines.extend(detailed_tex_sections(rows, matrix, traces, validation))
    lines.extend(
        [
            r"\section{V2 result-এর অর্থ এবং limitation}",
            r"\begin{enumerate}",
            r"\item V2 active mission-এর uncompleted suffix পরিবর্তন করে নতুন task-এর priority value বিবেচনা করেছে।",
            r"\item Accepted replacement-এ displaced task queue-তে ফিরে যায়; task হারিয়ে যায় না।",
            r"\item Current onboard inventory না মিললে V2 replacement গ্রহণ করে না।",
            r"\item Completed route prefix এবং completed delivery immutable রাখা হয়েছে।",
            r"\item Final objective completed task-এর service value থেকে একবার গণনা করা হয়েছে।",
            r"\item Safe return rate এবং energy value configured simulation model-এর ফল, field flight reliability নয়।",
            r"\item One-for-one V2 full mathematical optimizer বা full fleet rolling-horizon optimizer নয়।",
            r"\item Reserve inventory, base reload, multiple replacement এবং broader reassignment V3 scope।",
            r"\end{enumerate}",
            r"\section{উপসংহার এবং পরবর্তী কাজ}",
            r"V1 একটি fixed active-mission reference হিসেবে অপরিবর্তিত রাখা হয়েছে। V2 formulation-এর সীমিত recourse rule যোগ করেছে: নতুন high-value task এলে feasible হলে একটি active mission-এর একটি uncompleted task replace করা যায়। Paired matrix V1 এবং V2-এর operational outcome এবং recourse overhead একসঙ্গে দেখাবে। পরবর্তী version-এ reserve inventory এবং active inventory-aware reassignment যোগ করার আগে V2-এর decision trace, service-value gain এবং runtime overhead বিশ্লেষণ করা হবে।",
            r"\section{Reproducibility artifacts}",
            r"\begin{itemize}",
            r"\scriptsize\sloppy",
            r"\item \code{Simulation/results/pgbm_v2_recourse_experiments/raw_metrics/pgbm_v2_paired_matrix_metrics_tasks_30_60_90_uavs_3_5_8_10_seeds_101_110.csv}: ৪৮০টি metrics row।",
            r"\item \code{Simulation/results/pgbm_v2_recourse_experiments/decision_traces/pgbm_v2_decision_traces.jsonl}: ২৪০টি V2 decision trace।",
            r"\item \code{Simulation/run_pgbm_v2_experiment_matrix.py}: matrix execution script।",
            r"\item \code{Simulation/pgbm_sim/v2/}: V2 runtime, recourse এবং experiment modules।",
            r"\item \code{docs/specs/0007-pgbm-v2-task-replacement-recourse.md}: accepted design specification।",
            r"\end{itemize}",
            r"\end{document}",
        ]
    )
    return "\n".join(lines) + "\n"


def write_outputs(
    rows: Sequence[Mapping[str, object]],
    matrix,
    traces: Sequence[Mapping[str, object]],
    validation: Mapping[str, object],
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    markdown = generate_markdown(rows, matrix, traces, validation)
    tex = generate_tex(rows, matrix, traces, validation)
    (OUTPUT_DIR / "pgbm_v2_comparative_findings_bn.md").write_text(markdown, encoding="utf-8")
    (OUTPUT_DIR / "pgbm_v2_comparative_findings_bn.tex").write_text(tex, encoding="utf-8")

    aggregate_rows = []
    for cell in matrix:
        for algorithm, group in (("V1", cell["v1"]), ("V2", cell["v2"])):
            aggregate_rows.append(
                {
                    "environment": cell["mode"],
                    "task_count": cell["task_count"],
                    "uav_count": cell["uav_count"],
                    "algorithm": algorithm,
                    "seed_count": len(group),
                    "objective_mean": mean(group, "objective_value"),
                    "objective_std": std(group, "objective_value"),
                    "served_mean": mean(group, "served_tasks"),
                    "served_std": std(group, "served_tasks"),
                    "parcel_rate_mean": mean(group, "parcel_delivery_rate"),
                    "parcel_rate_std": std(group, "parcel_delivery_rate"),
                    "requested_parcels_mean": mean(group, "requested_parcels"),
                    "requested_parcels_std": std(group, "requested_parcels"),
                    "dropped_parcels_mean": mean(group, "dropped_parcels"),
                    "dropped_parcels_std": std(group, "dropped_parcels"),
                    "deferred_mean": mean(group, "deferred_tasks"),
                    "deferred_std": std(group, "deferred_tasks"),
                    "total_distance_mean": mean(group, "total_distance"),
                    "total_distance_std": std(group, "total_distance"),
                    "total_energy_mean": mean(group, "total_energy"),
                    "total_energy_std": std(group, "total_energy"),
                    "runtime_mean": mean(group, "runtime_seconds"),
                    "runtime_std": std(group, "runtime_seconds"),
                    "accepted_mean": mean(group, "accepted_replacements"),
                    "accepted_std": std(group, "accepted_replacements"),
                    "replacement_gain_mean": mean(group, "replacement_gain"),
                    "replacement_gain_std": std(group, "replacement_gain"),
                }
            )
    aggregate_path = RESULTS_DIR / "aggregated_metrics.csv"
    with aggregate_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(aggregate_rows[0].keys()))
        writer.writeheader()
        writer.writerows(aggregate_rows)

    manifest = {
        "report": "Experiment Reports/V2/pgbm_v2_comparative_findings_bn.tex",
        "markdown": "Experiment Reports/V2/pgbm_v2_comparative_findings_bn.md",
        "paired_metrics": str(METRICS_PATH.relative_to(ROOT)),
        "configuration_count": len(matrix),
        "metrics_row_count": len(rows),
        "seeds": sorted({int(row["seed"]) for row in rows}),
        "environments": sorted({str(row["environment"]) for row in rows}),
        "task_counts": sorted({int(row["task_count"]) for row in rows}),
        "uav_counts": sorted({int(row["uav_count"]) for row in rows}),
        "algorithms": sorted({str(row["algorithm"]) for row in rows}),
        "accepted_replacements": sum(int(row["accepted_replacements"]) for row in rows),
        "rejected_replacements": sum(int(row["rejected_replacements"]) for row in rows),
        "rejection_reasons": dict(rejection_totals(rows)),
        "trace_count": len(traces),
        "validation": dict(validation),
    }
    (RESULTS_DIR / "pgbm_v2_report_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    if not METRICS_PATH.exists():
        raise SystemExit("V2 metrics file is missing: {}".format(METRICS_PATH))
    rows = load_rows(METRICS_PATH)
    if len(rows) != 480:
        raise SystemExit("Expected 480 paired rows, found {}".format(len(rows)))
    if not TRACE_PATH.exists():
        raise SystemExit("V2 decision trace file is missing: {}".format(TRACE_PATH))
    traces = load_traces(TRACE_PATH)
    if len(traces) != 240:
        raise SystemExit("Expected 240 V2 decision traces, found {}".format(len(traces)))
    matrix = build_aggregates(rows)
    validation = validation_evidence(rows)
    write_outputs(rows, matrix, traces, validation)
    print("Wrote V2 Markdown and LaTeX reports to {}".format(OUTPUT_DIR))
    print("Configuration cells: {}".format(len(matrix)))
    print("Rows: {}".format(len(rows)))


if __name__ == "__main__":
    main()
