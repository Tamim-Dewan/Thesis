"""Repeatable scenario, planner, baseline, and execution experiments."""

import time
from dataclasses import dataclass, replace
from typing import Iterable, Sequence, Tuple

from .event_simulation import EventSimulationConfig, run_event_simulation
from .execution import ExecutionConfig, apply_recourse, execute_plan
from .metrics import MetricsRecord, write_metrics_csv
from .planner import UAVConfig, plan_tasks
from .scenario import build_scenario
from .disaster_scene import SceneConfig
from .tasks import TaskConfig


@dataclass(frozen=True)
class ExperimentConfig:
    name: str = "pgbm_research_v1"
    mode: str = "du_outdoor"
    severity: str = "moderate"
    task_count: int = 6
    uav_count: int = 3
    payload_capacity: int = 4
    payload_weight_capacity: float = 2.0
    energy_capacity: float = 1000.0
    start_time: float = 30.0
    recourse_enabled: bool = False
    dynamic: bool = False
    horizon_minutes: float = 120.0
    arrival_profile: str = "uniform"
    phase_weights: Tuple[float, float, float] = (3.0, 2.0, 1.0)
    turnaround_minutes: float = 5.0
    max_pending_tasks: int = 8
    max_candidate_plans: int = 50000
    planner_methods: Tuple[str, ...] = ("pgbm_heuristic_v1", "nearest_task_first")


def run_experiments(seeds: Iterable[int], config: ExperimentConfig = ExperimentConfig()) -> Tuple[MetricsRecord, ...]:
    if config.dynamic and config.recourse_enabled:
        raise ValueError("dynamic V1 experiments do not enable active recourse")
    records=[]
    for seed in seeds:
        task_config = TaskConfig(
            task_count=config.task_count,
            seed=int(seed) + 1,
            arrival_profile=config.arrival_profile,
            horizon_minutes=config.horizon_minutes,
            phase_weights=config.phase_weights,
        )
        scenario=build_scenario(SceneConfig(mode=config.mode,severity=config.severity,seed=int(seed)),task_config,scenario_id="{}_{}".format(config.mode,seed),execution_config=ExecutionConfig(start_time=config.start_time))
        uav_config=UAVConfig(count=config.uav_count,payload_capacity=config.payload_capacity,payload_weight_capacity=config.payload_weight_capacity,energy_capacity=config.energy_capacity)
        replacement=None
        if config.recourse_enabled:
            replacement_site=next(site for site in scenario.scene.candidate_sites if site.position not in {task.dropoff_waypoint for task in scenario.tasks})
            replacement=replace(scenario.tasks[0],identifier="replacement_{}".format(seed),survivor_position=replacement_site.position,dropoff_waypoint=replacement_site.position)
        for method in config.planner_methods:
            started=time.perf_counter()
            if config.dynamic:
                dynamic_result = run_event_simulation(
                    scenario,
                    uav_config,
                    scenario.route_config,
                    EventSimulationConfig(
                        horizon_minutes=config.horizon_minutes,
                        turnaround_minutes=config.turnaround_minutes,
                        planner_method=method,
                        max_pending_tasks=config.max_pending_tasks,
                        max_candidate_plans=config.max_candidate_plans,
                    ),
                )
                final_plan = dynamic_result.dispatch_plans[-1] if dynamic_result.dispatch_plans else plan_tasks(scenario, uav_config, "pgbm_initial_bruteforce_v1")
                result = dynamic_result
                accepted_replacements = 0
                rejected_replacements = 0
                elapsed = dynamic_result.runtime_seconds
                payload_utilization = max(
                    (sum(assignment.payload for assignment in plan.assignments) / max(1, config.uav_count * config.payload_capacity))
                    for plan in dynamic_result.dispatch_plans
                ) if dynamic_result.dispatch_plans else 0.0
                objective_value = dynamic_result.objective_value
                served_tasks = len(dynamic_result.served_task_ids)
                deferred_tasks = len(dynamic_result.deferred_task_ids)
                average_delay = dynamic_result.average_completion_delay
                total_distance = dynamic_result.total_distance
                total_travel_time = dynamic_result.total_travel_time
                total_energy = dynamic_result.total_energy
                requested_parcels = dynamic_result.requested_parcels
                dropped_parcels = dynamic_result.dropped_parcels
                parcel_delivery_rate = dynamic_result.parcel_delivery_rate
                safe_return_rate = dynamic_result.safe_return_rate
                dispatch_count = dynamic_result.dispatch_count
                peak_queue = dynamic_result.peak_queue_size
                candidate_count = dynamic_result.candidate_count
                planner_runtime = dynamic_result.planner_runtime_seconds
                route_runtime = dynamic_result.route_runtime_seconds
                phase_high_tasks = int(dynamic_result.phase_counts.get("high", 0))
                phase_medium_tasks = int(dynamic_result.phase_counts.get("medium", 0))
                phase_low_tasks = int(dynamic_result.phase_counts.get("low", 0))
                search_truncated_dispatches = dynamic_result.search_truncated_dispatches
                max_candidate_count = dynamic_result.max_candidate_count
                max_pending_considered = dynamic_result.max_pending_considered
            else:
                plan=plan_tasks(scenario,uav_config,method)
                if config.recourse_enabled:
                    recourse=apply_recourse(scenario,plan,(replacement,),uav_config)
                    combined_scenario=replace(scenario,tasks=tuple(scenario.tasks)+(replacement,))
                    final_plan=recourse.revised_plan
                    accepted_replacements=len(recourse.accepted_replacement_ids)
                    rejected_replacements=len(recourse.rejected_replacement_ids)
                else:
                    recourse=None
                    combined_scenario=scenario
                    final_plan=plan
                    accepted_replacements=0
                    rejected_replacements=0
                result=execute_plan(combined_scenario,final_plan,uav_config)
                elapsed=time.perf_counter()-started
                payload_used=sum(item.payload for item in final_plan.assignments)
                payload_total=max(1,config.uav_count*config.payload_capacity)
                payload_utilization=payload_used/payload_total
                objective_value=final_plan.objective_value
                served_tasks=len(result.served_task_ids)
                deferred_tasks=len(final_plan.unassigned_task_ids)+len(result.missed_task_ids)
                average_delay=result.average_completion_delay
                total_distance=result.total_distance
                total_travel_time=result.total_travel_time
                total_energy=result.total_energy
                task_by_id = {task.identifier: task for task in combined_scenario.tasks}
                requested_parcels = sum(sum(task.demand.values()) for task in combined_scenario.tasks)
                dropped_parcels = sum(
                    sum(task_by_id[task_id].demand.values())
                    for task_id in result.served_task_ids
                )
                parcel_delivery_rate = dropped_parcels / requested_parcels if requested_parcels else 0.0
                safe_return_rate=result.safe_return_rate
                dispatch_count=1
                peak_queue=deferred_tasks
                candidate_count=0
                planner_runtime=elapsed
                route_runtime=0.0
                phase_high_tasks = 0
                phase_medium_tasks = 0
                phase_low_tasks = 0
                search_truncated_dispatches = 0
                max_candidate_count = 0
                max_pending_considered = 0
            records.append(MetricsRecord(
                "experiment.v1", config.name, int(seed), method, scenario.scenario_id, "ok",
                objective_value, served_tasks, deferred_tasks, average_delay,
                total_distance, total_travel_time, total_energy, payload_utilization,
                accepted_replacements, rejected_replacements, safe_return_rate, elapsed,
                config.recourse_enabled, config.horizon_minutes if config.dynamic else 0.0,
                config.arrival_profile if config.dynamic else "snapshot", config.task_count,
                config.uav_count, dispatch_count, peak_queue, candidate_count,
                planner_runtime, route_runtime,
                phase_high_tasks, phase_medium_tasks, phase_low_tasks,
                search_truncated_dispatches, max_candidate_count,
                max_pending_considered,
                requested_parcels, dropped_parcels, parcel_delivery_rate,
            ))
    return tuple(records)


def write_experiment_metrics(seeds: Iterable[int], path: str, config: ExperimentConfig = ExperimentConfig()) -> Tuple[MetricsRecord, ...]:
    records=run_experiments(seeds,config); write_metrics_csv(records,path); return records


def run_experiment_matrix(
    seeds: Iterable[int],
    modes: Sequence[str] = ("synthetic", "du_outdoor"),
    task_counts: Sequence[int] = (6,),
    uav_counts: Sequence[int] = (3,),
    config: ExperimentConfig = ExperimentConfig(
        name="pgbm_v1_two_hour_experiment_matrix",
        dynamic=True,
        arrival_profile="three_phase",
        planner_methods=("pgbm_initial_bruteforce_v1",),
    ),
) -> Tuple[MetricsRecord, ...]:
    """Run the approved multi seed and configuration matrix."""
    records = []
    for mode in modes:
        for task_count in task_counts:
            for uav_count in uav_counts:
                variant = replace(config, mode=mode, task_count=int(task_count), uav_count=int(uav_count))
                records.extend(run_experiments(seeds, variant))
    return tuple(records)


def write_experiment_matrix(
    seeds: Iterable[int],
    path: str,
    modes: Sequence[str] = ("synthetic", "du_outdoor"),
    task_counts: Sequence[int] = (6,),
    uav_counts: Sequence[int] = (3,),
    config: ExperimentConfig = ExperimentConfig(
        name="pgbm_v1_two_hour_experiment_matrix",
        dynamic=True,
        arrival_profile="three_phase",
        planner_methods=("pgbm_initial_bruteforce_v1",),
    ),
) -> Tuple[MetricsRecord, ...]:
    records = run_experiment_matrix(seeds, modes, task_counts, uav_counts, config)
    write_metrics_csv(records, path)
    return records
