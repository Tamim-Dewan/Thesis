"""Paired V1 and V2 experiment execution and metric export."""

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

from ..event_simulation import EventSimulationConfig, run_event_simulation
from ..planner import UAVConfig
from ..scenario import build_scenario
from ..disaster_scene import SceneConfig
from ..tasks import TaskConfig
from .event_simulation import V2EpisodeResult, run_event_simulation_v2
from .models import V2Config


@dataclass(frozen=True)
class V2ExperimentConfig:
    name: str = "pgbm_v2_task_replacement_recourse"
    severity: str = "moderate"
    horizon_minutes: float = 120.0
    arrival_profile: str = "three_phase"
    phase_weights: Tuple[float, float, float] = (3.0, 2.0, 1.0)
    turnaround_minutes: float = 5.0
    payload_capacity: int = 4
    payload_weight_capacity: float = 2.0
    energy_capacity: float = 1000.0
    reserve_energy: float = 200.0
    max_pending_tasks: int = 8
    max_candidate_plans: int = 50000

    def as_dict(self) -> Dict[str, object]:
        values = asdict(self)
        values["phase_weights"] = list(self.phase_weights)
        return values


@dataclass(frozen=True)
class V2MetricsRecord:
    schema_version: str
    experiment_name: str
    environment: str
    severity: str
    seed: int
    scenario_id: str
    scenario_fingerprint: str
    algorithm: str
    status: str
    task_count: int
    uav_count: int
    horizon_minutes: float
    arrival_profile: str
    objective_value: float
    served_tasks: int
    deferred_tasks: int
    average_completion_delay: float
    total_distance: float
    total_travel_time: float
    total_energy: float
    requested_parcels: int
    dropped_parcels: int
    parcel_delivery_rate: float
    safe_return_rate: float
    runtime_seconds: float
    planner_runtime_seconds: float
    route_runtime_seconds: float
    recourse_runtime_seconds: float
    dispatch_count: int
    mission_count: int
    peak_queue_size: int
    candidate_count: int
    max_candidate_count: int
    max_pending_considered: int
    search_truncated_dispatches: int
    phase_high_tasks: int
    phase_medium_tasks: int
    phase_low_tasks: int
    recourse_trigger_count: int
    accepted_replacements: int
    rejected_replacements: int
    replacement_gain: float
    displaced_task_count: int
    rejection_reasons: str


METRIC_FIELDS = tuple(V2MetricsRecord.__dataclass_fields__.keys())


def _scenario_fingerprint(scenario) -> str:
    payload = json.dumps(scenario.as_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _from_v1(result, scenario, config: V2ExperimentConfig, mode: str, seed: int) -> V2MetricsRecord:
    return V2MetricsRecord(
        "pgbm_v2_paired_metrics.v1",
        config.name,
        mode,
        config.severity,
        int(seed),
        scenario.scenario_id,
        _scenario_fingerprint(scenario),
        "V1",
        "ok",
        scenario.task_config.task_count,
        scenario.uav_config.count,
        config.horizon_minutes,
        scenario.task_config.arrival_profile,
        result.objective_value,
        len(result.served_task_ids),
        len(result.deferred_task_ids),
        result.average_completion_delay,
        result.total_distance,
        result.total_travel_time,
        result.total_energy,
        result.requested_parcels,
        result.dropped_parcels,
        result.parcel_delivery_rate,
        result.safe_return_rate,
        result.runtime_seconds,
        result.planner_runtime_seconds,
        result.route_runtime_seconds,
        0.0,
        result.dispatch_count,
        sum(1 for plan in result.dispatch_plans for assignment in plan.assignments if assignment.task_ids),
        result.peak_queue_size,
        result.candidate_count,
        result.max_candidate_count,
        result.max_pending_considered,
        result.search_truncated_dispatches,
        result.phase_counts.get("high", 0),
        result.phase_counts.get("medium", 0),
        result.phase_counts.get("low", 0),
        0,
        0,
        0,
        0.0,
        0,
        "{}",
    )


def _from_v2(result: V2EpisodeResult, scenario, config: V2ExperimentConfig, mode: str, seed: int) -> V2MetricsRecord:
    return V2MetricsRecord(
        "pgbm_v2_paired_metrics.v1",
        config.name,
        mode,
        config.severity,
        int(seed),
        scenario.scenario_id,
        _scenario_fingerprint(scenario),
        "V2",
        "ok",
        scenario.task_config.task_count,
        scenario.uav_config.count,
        config.horizon_minutes,
        scenario.task_config.arrival_profile,
        result.objective_value,
        len(result.served_task_ids),
        len(result.deferred_task_ids),
        result.average_completion_delay,
        result.total_distance,
        result.total_travel_time,
        result.total_energy,
        result.requested_parcels,
        result.dropped_parcels,
        result.parcel_delivery_rate,
        result.safe_return_rate,
        result.runtime_seconds,
        result.planner_runtime_seconds,
        result.route_runtime_seconds,
        result.recourse_runtime_seconds,
        result.dispatch_count,
        result.mission_count,
        result.peak_queue_size,
        result.candidate_count,
        result.max_candidate_count,
        result.max_pending_considered,
        result.search_truncated_dispatches,
        result.phase_counts.get("high", 0),
        result.phase_counts.get("medium", 0),
        result.phase_counts.get("low", 0),
        result.recourse_trigger_count,
        result.accepted_replacements,
        result.rejected_replacements,
        result.replacement_gain,
        len(result.displaced_task_ids),
        json.dumps(dict(result.rejection_reasons), sort_keys=True),
    )


def build_experiment_scenario(mode: str, seed: int, task_count: int, uav_count: int, config: V2ExperimentConfig):
    task_config = TaskConfig(
        task_count=int(task_count),
        seed=int(seed) + 1,
        arrival_profile=config.arrival_profile,
        horizon_minutes=config.horizon_minutes,
        phase_weights=config.phase_weights,
    )
    uav_config = UAVConfig(
        count=int(uav_count),
        payload_capacity=config.payload_capacity,
        payload_weight_capacity=config.payload_weight_capacity,
        energy_capacity=config.energy_capacity,
        reserve_energy=config.reserve_energy,
    )
    return build_scenario(
        SceneConfig(mode=mode, severity=config.severity, seed=int(seed), uav_count=int(uav_count)),
        task_config,
        scenario_id="{}_tasks_{}_uavs_{}_seed_{}".format(mode, task_count, uav_count, seed),
        uav_config=uav_config,
    )


def run_paired_episode(
    mode: str,
    seed: int,
    task_count: int,
    uav_count: int,
    config: V2ExperimentConfig = V2ExperimentConfig(),
) -> Tuple[V2MetricsRecord, V2MetricsRecord, object]:
    """Run V1 and V2 on one identical in-memory scenario."""

    scenario = build_experiment_scenario(mode, seed, task_count, uav_count, config)
    v1 = run_event_simulation(
        scenario,
        scenario.uav_config,
        scenario.route_config,
        EventSimulationConfig(
            horizon_minutes=config.horizon_minutes,
            turnaround_minutes=config.turnaround_minutes,
            planner_method="pgbm_initial_bruteforce_v1",
            max_pending_tasks=config.max_pending_tasks,
            max_candidate_plans=config.max_candidate_plans,
        ),
    )
    v2 = run_event_simulation_v2(
        scenario,
        scenario.uav_config,
        scenario.route_config,
        V2Config(
            horizon_minutes=config.horizon_minutes,
            turnaround_minutes=config.turnaround_minutes,
            planner_method="pgbm_initial_bruteforce_v1",
            max_pending_tasks=config.max_pending_tasks,
            max_candidate_plans=config.max_candidate_plans,
            recourse_enabled=True,
        ),
    )
    return (
        _from_v1(v1, scenario, config, mode, seed),
        _from_v2(v2, scenario, config, mode, seed),
        (scenario, v1, v2),
    )


def run_v2_matrix(
    seeds: Iterable[int],
    modes: Sequence[str] = ("synthetic", "du_outdoor"),
    task_counts: Sequence[int] = (30, 60, 90),
    uav_counts: Sequence[int] = (3, 5, 8, 10),
    config: V2ExperimentConfig = V2ExperimentConfig(),
) -> Tuple[Tuple[V2MetricsRecord, ...], Tuple[Mapping[str, object], ...]]:
    """Run the paired heavy matrix and retain one trace object per V2 episode."""

    records: List[V2MetricsRecord] = []
    traces: List[Mapping[str, object]] = []
    for mode in modes:
        for task_count in task_counts:
            for uav_count in uav_counts:
                for seed in seeds:
                    v1_record, v2_record, payload = run_paired_episode(mode, int(seed), int(task_count), int(uav_count), config)
                    records.extend((v1_record, v2_record))
                    scenario, v1, v2 = payload
                    traces.append(
                        {
                            "environment": mode,
                            "task_count": int(task_count),
                            "uav_count": int(uav_count),
                            "seed": int(seed),
                            "scenario_id": scenario.scenario_id,
                            "scenario_fingerprint": v2_record.scenario_fingerprint,
                            "v2": v2.as_dict(),
                        }
                    )
    return tuple(records), tuple(traces)


def _reference_record(
    row: Mapping[str, str],
    scenario,
    config: V2ExperimentConfig,
    mode: str,
    seed: int,
) -> V2MetricsRecord:
    """Adapt one canonical V1 row without changing the preserved V1 file."""

    def number(name, converter=float):
        return converter(row[name])

    return V2MetricsRecord(
        "pgbm_v2_paired_metrics.v1",
        config.name,
        mode,
        config.severity,
        int(seed),
        row.get("scenario_id", scenario.scenario_id),
        _scenario_fingerprint(scenario),
        "V1",
        row.get("status", "ok"),
        number("task_count", int),
        number("uav_count", int),
        number("horizon_minutes"),
        row.get("arrival_profile", scenario.task_config.arrival_profile),
        number("objective_value"),
        number("served_tasks", int),
        number("deferred_tasks", int),
        number("average_completion_delay"),
        number("total_distance"),
        number("total_travel_time"),
        number("total_energy"),
        number("requested_parcels", int),
        number("dropped_parcels", int),
        number("parcel_delivery_rate"),
        number("safe_return_rate"),
        number("runtime_seconds"),
        number("planner_runtime_seconds"),
        number("route_runtime_seconds"),
        0.0,
        number("dispatch_count", int),
        0,
        number("peak_queue_size", int),
        number("candidate_count", int),
        number("max_candidate_count", int),
        number("max_pending_considered", int),
        number("search_truncated_dispatches", int),
        number("phase_high_tasks", int),
        number("phase_medium_tasks", int),
        number("phase_low_tasks", int),
        0,
        0,
        0,
        0.0,
        0,
        "{}",
    )


def run_v2_matrix_against_v1_reference(
    reference_path: str,
    seeds: Iterable[int],
    modes: Sequence[str] = ("synthetic", "du_outdoor"),
    task_counts: Sequence[int] = (30, 60, 90),
    uav_counts: Sequence[int] = (3, 5, 8, 10),
    config: V2ExperimentConfig = V2ExperimentConfig(),
) -> Tuple[Tuple[V2MetricsRecord, ...], Tuple[Mapping[str, object], ...]]:
    """Run V2 beside the preserved canonical V1 matrix.

    The V1 matrix is already validated evidence and is intentionally not
    overwritten or rerun here.  V2 is generated from the same local scene and
    task seed protocol.  ``run_paired_episode`` remains available for direct
    in-memory paired validation and is used by the focused tests.
    """

    with Path(reference_path).open("r", newline="", encoding="utf-8") as handle:
        reference_rows = list(csv.DictReader(handle))
    reference: Dict[Tuple[str, int, int, int], Mapping[str, str]] = {}
    for row in reference_rows:
        scenario_id = row.get("scenario_id", "")
        mode = "du_outdoor" if scenario_id.startswith("du_outdoor_") else "synthetic"
        key = (mode, int(row["seed"]), int(row["task_count"]), int(row["uav_count"]))
        reference[key] = row

    records: List[V2MetricsRecord] = []
    traces: List[Mapping[str, object]] = []
    for mode in modes:
        for task_count in task_counts:
            for uav_count in uav_counts:
                for seed in seeds:
                    key = (mode, int(seed), int(task_count), int(uav_count))
                    if key not in reference:
                        raise ValueError("missing canonical V1 row for {}".format(key))
                    scenario = build_experiment_scenario(mode, int(seed), int(task_count), int(uav_count), config)
                    v2 = run_event_simulation_v2(
                        scenario,
                        scenario.uav_config,
                        scenario.route_config,
                        V2Config(
                            horizon_minutes=config.horizon_minutes,
                            turnaround_minutes=config.turnaround_minutes,
                            planner_method="pgbm_initial_bruteforce_v1",
                            max_pending_tasks=config.max_pending_tasks,
                            max_candidate_plans=config.max_candidate_plans,
                            recourse_enabled=True,
                        ),
                    )
                    records.append(_reference_record(reference[key], scenario, config, mode, int(seed)))
                    records.append(_from_v2(v2, scenario, config, mode, int(seed)))
                    traces.append(
                        {
                            "environment": mode,
                            "task_count": int(task_count),
                            "uav_count": int(uav_count),
                            "seed": int(seed),
                            "scenario_id": scenario.scenario_id,
                            "scenario_fingerprint": _scenario_fingerprint(scenario),
                            "v1_reference": dict(reference[key]),
                            "v2": v2.as_dict(),
                        }
                    )
    return tuple(records), tuple(traces)


def write_v2_matrix_against_v1_reference(
    reference_path: str,
    path: str,
    trace_path: str,
    seeds: Iterable[int],
    modes: Sequence[str] = ("synthetic", "du_outdoor"),
    task_counts: Sequence[int] = (30, 60, 90),
    uav_counts: Sequence[int] = (3, 5, 8, 10),
    config: V2ExperimentConfig = V2ExperimentConfig(),
) -> Tuple[V2MetricsRecord, ...]:
    records, traces = run_v2_matrix_against_v1_reference(
        reference_path,
        seeds,
        modes,
        task_counts,
        uav_counts,
        config,
    )
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=METRIC_FIELDS)
        writer.writeheader()
        writer.writerows(asdict(record) for record in records)
    trace_output = Path(trace_path)
    trace_output.parent.mkdir(parents=True, exist_ok=True)
    with trace_output.open("w", encoding="utf-8") as handle:
        for trace in traces:
            handle.write(json.dumps(trace, sort_keys=True) + "\n")
    return records


def write_v2_matrix(
    path: str,
    trace_path: str,
    seeds: Iterable[int],
    modes: Sequence[str] = ("synthetic", "du_outdoor"),
    task_counts: Sequence[int] = (30, 60, 90),
    uav_counts: Sequence[int] = (3, 5, 8, 10),
    config: V2ExperimentConfig = V2ExperimentConfig(),
) -> Tuple[V2MetricsRecord, ...]:
    records, traces = run_v2_matrix(seeds, modes, task_counts, uav_counts, config)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=METRIC_FIELDS)
        writer.writeheader()
        writer.writerows(asdict(record) for record in records)
    trace_output = Path(trace_path)
    trace_output.parent.mkdir(parents=True, exist_ok=True)
    with trace_output.open("w", encoding="utf-8") as handle:
        for trace in traces:
            handle.write(json.dumps(trace, sort_keys=True) + "\n")
    return records
