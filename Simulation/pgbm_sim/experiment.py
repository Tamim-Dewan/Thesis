"""Repeatable scenario, planner, baseline, and execution experiments."""

import time
from dataclasses import dataclass, replace
from typing import Iterable, Tuple

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


def run_experiments(seeds: Iterable[int], config: ExperimentConfig = ExperimentConfig()) -> Tuple[MetricsRecord, ...]:
    records=[]
    for seed in seeds:
        scenario=build_scenario(SceneConfig(mode=config.mode,severity=config.severity,seed=int(seed)),TaskConfig(task_count=config.task_count,seed=int(seed)+1),scenario_id="{}_{}".format(config.mode,seed),execution_config=ExecutionConfig(start_time=config.start_time))
        uav_config=UAVConfig(count=config.uav_count,payload_capacity=config.payload_capacity,payload_weight_capacity=config.payload_weight_capacity,energy_capacity=config.energy_capacity)
        replacement_site=next(site for site in scenario.scene.candidate_sites if site.position not in {task.dropoff_waypoint for task in scenario.tasks})
        replacement=replace(scenario.tasks[0],identifier="replacement_{}".format(seed),survivor_position=replacement_site.position,dropoff_waypoint=replacement_site.position)
        for method in ("pgbm_heuristic_v1","nearest_task_first"):
            started=time.perf_counter(); plan=plan_tasks(scenario,uav_config,method); recourse=apply_recourse(scenario,plan,(replacement,),uav_config); combined_scenario=replace(scenario,tasks=tuple(scenario.tasks)+(replacement,)); result=execute_plan(combined_scenario,recourse.revised_plan,uav_config); elapsed=time.perf_counter()-started
            payload_used=sum(item.payload for item in recourse.revised_plan.assignments); payload_total=max(1,config.uav_count*config.payload_capacity)
            records.append(MetricsRecord("experiment.v1",config.name,int(seed),method,scenario.scenario_id,"ok",recourse.revised_plan.objective_value,len(result.served_task_ids),len(recourse.revised_plan.unassigned_task_ids)+len(result.missed_task_ids),result.average_completion_delay,result.total_distance,result.total_travel_time,result.total_energy,payload_used/payload_total,len(recourse.accepted_replacement_ids),len(recourse.rejected_replacement_ids),result.safe_return_rate,elapsed))
    return tuple(records)


def write_experiment_metrics(seeds: Iterable[int], path: str, config: ExperimentConfig = ExperimentConfig()) -> Tuple[MetricsRecord, ...]:
    records=run_experiments(seeds,config); write_metrics_csv(records,path); return records
