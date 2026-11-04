"""Paired Version 2 control and Version 2.1 cache experiments."""

import csv
import json
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from ..v2.experiment import (
    V2ExperimentConfig,
    V2MetricsRecord,
    _from_v2,
    build_experiment_scenario,
    _scenario_fingerprint,
)
from ..v2.models import V2Config
from ..v2.event_simulation import run_event_simulation_v2
from .event_simulation import run_event_simulation_v21
from .models import V21Config, V21EpisodeResult


DEFAULT_CACHE_VARIANTS: Tuple[Tuple[str, Optional[Mapping[str, float]]], ...] = (
    ("uniform", None),
    ("water_heavy_sensitivity", {"food": 0.1, "water": 1.0, "medical": 0.1}),
)


@dataclass(frozen=True)
class V21ExperimentConfig(V2ExperimentConfig):
    """Shared scenario settings plus one cache policy label and prior."""

    name: str = "pgbm_v2_1_cache_aware_recourse"
    cache_variant: str = "uniform"
    cache_item_prior: Optional[Mapping[str, float]] = None
    cache_enabled: bool = True
    max_cache_slots: int = 1

    def validate(self) -> None:
        if not self.cache_variant:
            raise ValueError("cache_variant must not be empty")
        if self.max_cache_slots < 0 or self.max_cache_slots > 1:
            raise ValueError("V2.1 experiment supports zero or one cache slot")
        if self.cache_item_prior is not None and any(
            float(value) < 0.0 for value in self.cache_item_prior.values()
        ):
            raise ValueError("cache item prior values must be non negative")


@dataclass(frozen=True)
class V21MetricsRecord:
    """One CSV row for the V2 control or a V2.1 cache variant."""

    base: V2MetricsRecord
    cache_variant: str
    cache_enabled: bool
    cache_item_prior: Optional[Mapping[str, float]]
    cache_loaded_parcels: int
    cache_used_parcels: int
    cache_returned_parcels: int
    cache_match_count: int
    cache_hit_count: int
    cache_hit_rate: float
    cache_assisted_count: int
    cache_energy_overhead: float
    cache_load_rejections: Mapping[str, int]
    cache_miss_reasons: Mapping[str, int]

    def as_dict(self) -> Dict[str, object]:
        values = asdict(self.base)
        values["schema_version"] = "pgbm_v2_1_cache_metrics.v1"
        values["algorithm"] = "V2.1" if self.cache_enabled else "V2_control"
        values.update(
            {
                "cache_variant": self.cache_variant,
                "cache_enabled": self.cache_enabled,
                "cache_item_prior": json.dumps(
                    dict(self.cache_item_prior) if self.cache_item_prior is not None else {},
                    sort_keys=True,
                ),
                "cache_loaded_parcels": self.cache_loaded_parcels,
                "cache_used_parcels": self.cache_used_parcels,
                "cache_returned_parcels": self.cache_returned_parcels,
                "cache_match_count": self.cache_match_count,
                "cache_hit_count": self.cache_hit_count,
                "cache_hit_rate": self.cache_hit_rate,
                "cache_assisted_count": self.cache_assisted_count,
                "cache_energy_overhead": self.cache_energy_overhead,
                "cache_load_rejections": json.dumps(dict(self.cache_load_rejections), sort_keys=True),
                "cache_miss_reasons": json.dumps(dict(self.cache_miss_reasons), sort_keys=True),
            }
        )
        return values


V21_METRIC_FIELDS = tuple(V2MetricsRecord.__dataclass_fields__.keys()) + (
    "cache_variant",
    "cache_enabled",
    "cache_item_prior",
    "cache_loaded_parcels",
    "cache_used_parcels",
    "cache_returned_parcels",
    "cache_match_count",
    "cache_hit_count",
    "cache_hit_rate",
    "cache_assisted_count",
    "cache_energy_overhead",
    "cache_load_rejections",
    "cache_miss_reasons",
)


def _v2_config(config: V21ExperimentConfig) -> V2Config:
    return V2Config(
        horizon_minutes=config.horizon_minutes,
        turnaround_minutes=config.turnaround_minutes,
        planner_method="pgbm_initial_bruteforce_v1",
        max_pending_tasks=config.max_pending_tasks,
        max_candidate_plans=config.max_candidate_plans,
        recourse_enabled=True,
    )


def _v21_config(config: V21ExperimentConfig) -> V21Config:
    return V21Config(
        horizon_minutes=config.horizon_minutes,
        turnaround_minutes=config.turnaround_minutes,
        planner_method="pgbm_initial_bruteforce_v1",
        max_pending_tasks=config.max_pending_tasks,
        max_candidate_plans=config.max_candidate_plans,
        recourse_enabled=True,
        cache_enabled=config.cache_enabled,
        max_cache_slots=config.max_cache_slots,
        cache_selection_policy="configured_most_probable",
        cache_item_prior=config.cache_item_prior,
    )


def _control_record(result, scenario, config: V21ExperimentConfig, mode: str, seed: int) -> V21MetricsRecord:
    base = _from_v2(result, scenario, config, mode, seed)
    return V21MetricsRecord(
        base,
        "v2_control",
        False,
        None,
        0,
        0,
        0,
        0,
        0,
        0.0,
        0,
        0.0,
        {},
        {},
    )


def _cache_record(
    result: V21EpisodeResult,
    scenario,
    config: V21ExperimentConfig,
    mode: str,
    seed: int,
) -> V21MetricsRecord:
    base = _from_v2(result.base_result, scenario, config, mode, seed)
    return V21MetricsRecord(
        base,
        config.cache_variant,
        config.cache_enabled,
        config.cache_item_prior,
        result.cache_loaded_parcels,
        result.cache_used_parcels,
        result.cache_returned_parcels,
        result.cache_match_count,
        result.cache_hit_count,
        result.cache_hit_rate,
        result.cache_assisted_count,
        result.cache_energy_overhead,
        result.cache_load_rejections,
        result.cache_miss_reasons,
    )


def run_paired_v21_episode(
    mode: str,
    seed: int,
    task_count: int,
    uav_count: int,
    config: V21ExperimentConfig = V21ExperimentConfig(),
) -> Tuple[V21MetricsRecord, V21MetricsRecord, object]:
    """Run V2 control and one V2.1 policy on the same in memory scenario."""

    config.validate()
    scenario = build_experiment_scenario(mode, seed, task_count, uav_count, config)
    v2 = run_event_simulation_v2(
        scenario,
        scenario.uav_config,
        scenario.route_config,
        _v2_config(config),
    )
    v21 = run_event_simulation_v21(
        scenario,
        scenario.uav_config,
        scenario.route_config,
        _v21_config(config),
    )
    return (
        _control_record(v2, scenario, config, mode, seed),
        _cache_record(v21, scenario, config, mode, seed),
        (scenario, v2, v21),
    )


def _run_v21_scenario_job(
    job: Tuple[
        str,
        int,
        int,
        int,
        V21ExperimentConfig,
        Tuple[Tuple[str, Optional[Mapping[str, float]]], ...],
    ]
) -> Tuple[Tuple[V21MetricsRecord, ...], Mapping[str, object]]:
    """Evaluate one scenario; top-level so it can run in a worker process."""

    mode, task_count, uav_count, seed, config, variants = job
    scenario = build_experiment_scenario(mode, seed, task_count, uav_count, config)
    v2 = run_event_simulation_v2(
        scenario,
        scenario.uav_config,
        scenario.route_config,
        _v2_config(config),
    )
    records: List[V21MetricsRecord] = [_control_record(v2, scenario, config, mode, seed)]
    variant_results: Dict[str, V21EpisodeResult] = {}
    for variant_name, prior in variants:
        variant_config = replace(
            config,
            cache_variant=str(variant_name),
            cache_item_prior=dict(prior) if prior is not None else None,
            cache_enabled=True,
        )
        variant_config.validate()
        result = run_event_simulation_v21(
            scenario,
            scenario.uav_config,
            scenario.route_config,
            _v21_config(variant_config),
        )
        records.append(_cache_record(result, scenario, variant_config, mode, seed))
        variant_results[str(variant_name)] = result
    trace = {
        "environment": mode,
        "task_count": int(task_count),
        "uav_count": int(uav_count),
        "seed": int(seed),
        "scenario_id": scenario.scenario_id,
        "scenario_fingerprint": _scenario_fingerprint(scenario),
        "v2_control": v2.as_dict(),
        "v2_1": {name: result.as_dict() for name, result in variant_results.items()},
    }
    return tuple(records), trace


def run_v21_matrix(
    seeds: Iterable[int],
    modes: Sequence[str] = ("synthetic", "du_outdoor"),
    task_counts: Sequence[int] = (30, 60, 90),
    uav_counts: Sequence[int] = (3, 5, 8, 10),
    config: V21ExperimentConfig = V21ExperimentConfig(),
    variants: Sequence[Tuple[str, Optional[Mapping[str, float]]]] = DEFAULT_CACHE_VARIANTS,
    workers: int = 1,
) -> Tuple[Tuple[V21MetricsRecord, ...], Tuple[Mapping[str, object], ...]]:
    """Run paired V2 and V2.1 variants over identical seeded scenarios."""

    config.validate()
    if workers < 1:
        raise ValueError("workers must be at least one")
    seeds = tuple(int(seed) for seed in seeds)
    variants = tuple((str(name), dict(prior) if prior is not None else None) for name, prior in variants)
    jobs = tuple(
        (mode, int(task_count), int(uav_count), seed, config, variants)
        for mode in modes
        for task_count in task_counts
        for uav_count in uav_counts
        for seed in seeds
    )
    records: List[V21MetricsRecord] = []
    traces: List[Mapping[str, object]] = []
    if workers == 1:
        results = map(_run_v21_scenario_job, jobs)
        for scenario_records, trace in results:
            records.extend(scenario_records)
            traces.append(trace)
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            for scenario_records, trace in executor.map(_run_v21_scenario_job, jobs):
                records.extend(scenario_records)
                traces.append(trace)
    return tuple(records), tuple(traces)


def write_v21_matrix(
    path: str,
    trace_path: str,
    manifest_path: str,
    seeds: Iterable[int],
    modes: Sequence[str] = ("synthetic", "du_outdoor"),
    task_counts: Sequence[int] = (30, 60, 90),
    uav_counts: Sequence[int] = (3, 5, 8, 10),
    config: V21ExperimentConfig = V21ExperimentConfig(),
    variants: Sequence[Tuple[str, Optional[Mapping[str, float]]]] = DEFAULT_CACHE_VARIANTS,
    workers: int = 1,
) -> Tuple[V21MetricsRecord, ...]:
    seeds = tuple(int(seed) for seed in seeds)
    records, traces = run_v21_matrix(
        seeds,
        modes,
        task_counts,
        uav_counts,
        config,
        variants,
        workers,
    )
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=V21_METRIC_FIELDS)
        writer.writeheader()
        writer.writerows(record.as_dict() for record in records)
    trace_output = Path(trace_path)
    trace_output.parent.mkdir(parents=True, exist_ok=True)
    with trace_output.open("w", encoding="utf-8") as handle:
        for trace in traces:
            handle.write(json.dumps(trace, sort_keys=True) + "\n")
    manifest_output = Path(manifest_path)
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": "pgbm_v2_1_cache_manifest.v1",
        "config": config.as_dict(),
        "seeds": list(seeds),
        "modes": list(modes),
        "task_counts": [int(value) for value in task_counts],
        "uav_counts": [int(value) for value in uav_counts],
        "variants": [
            {
                "name": str(name),
                "item_prior": dict(prior) if prior is not None else None,
            }
            for name, prior in variants
        ],
        "record_count": len(records),
        "episode_count": len(traces),
    }
    manifest_output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return records
