"""Discrete event execution and task replacement recourse for planned missions."""

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, Optional, Tuple

from .planner import Plan, UAVConfig, plan_tasks
from .scenario import Scenario
from .tasks import SurvivorTask


@dataclass(frozen=True)
class ExecutionConfig:
    start_time: float = 0.0
    return_to_base: bool = True
    service_time: Optional[float] = None

    @classmethod
    def from_mapping(cls, values: Dict[str, Any]) -> "ExecutionConfig":
        service_time = values.get("service_time")
        config = cls(
            start_time=float(values.get("start_time", 0.0)),
            return_to_base=bool(values.get("return_to_base", True)),
            service_time=None if service_time is None else float(service_time),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if (self.service_time is not None and self.service_time < 0) or self.start_time < 0: raise ValueError("execution times must be non negative")

    def as_dict(self) -> Dict[str, Any]:
        values = {"start_time": self.start_time, "return_to_base": self.return_to_base}
        if self.service_time is not None:
            values["legacy_service_time"] = self.service_time
        values["service_duration_source"] = "task.service_duration"
        return values


@dataclass(frozen=True)
class ExecutionEvent:
    uav_id: str
    task_id: Optional[str]
    event: str
    time: float
    position: Tuple[float,float,float]
    detail: str = ""

    def as_dict(self): return asdict(self)


@dataclass(frozen=True)
class ExecutionResult:
    plan_method: str
    events: Tuple[ExecutionEvent, ...]
    served_task_ids: Tuple[str, ...]
    missed_task_ids: Tuple[str, ...]
    total_distance: float
    total_travel_time: float
    total_energy: float
    safe_return_rate: float
    average_completion_delay: float

    def as_dict(self):
        values=asdict(self); values["events"]=[event.as_dict() for event in self.events]; return values


def _distance(first, second): return math.sqrt(sum((first[index]-second[index])**2 for index in range(3)))


def _polyline_distance(points):
    return sum(_distance(first, second) for first, second in zip(points, points[1:]))


def _route_leg(route, start_index, target):
    """Return the route slice ending at a task waypoint."""
    for index in range(start_index + 1, len(route)):
        if route[index] == target:
            return route[start_index:index + 1], index
    return (route[start_index], target), start_index


def execute_plan(scenario: Scenario, plan: Plan, uav_config: Optional[UAVConfig] = None, config: Optional[ExecutionConfig] = None) -> ExecutionResult:
    config=config or scenario.execution_config or ExecutionConfig(); config.validate(); uav_config=uav_config or UAVConfig(count=len(plan.assignments)); uav_config.validate()
    tasks={task.identifier:task for task in scenario.tasks}; events=[]; served=[]; missed=[]; total_distance=0.; total_time=0.; total_energy=0.; returns=0; delays=[]
    for assignment in plan.assignments:
        if not assignment.task_ids: returns+=1; continue
        if not assignment.feasible:
            missed.extend(assignment.task_ids)
            events.append(ExecutionEvent(assignment.uav_id,None,"route_infeasible",config.start_time,assignment.route[0],"planner could not produce a collision-free route"))
            continue
        current=assignment.route[0]; time=config.start_time; route_index=0
        for task_id in assignment.task_ids:
            task=tasks[task_id]; next_position=task.dropoff_waypoint; leg,route_index=_route_leg(assignment.route,route_index,next_position); distance=_polyline_distance(leg); travel=distance/uav_config.speed; time+=travel; total_distance+=distance; total_time+=travel; total_energy+=distance*uav_config.energy_per_meter
            events.append(ExecutionEvent(assignment.uav_id,task_id,"arrive",time,next_position))
            service_duration = getattr(task, "service_duration", None)
            if service_duration is None:
                if config.service_time is None:
                    raise ValueError("task service_duration is required when execution service_time is not configured")
                service_duration = config.service_time
            completion=time+service_duration; time=completion
            if completion>=task.detected_at:
                served.append(task_id); delays.append(max(0.,completion-task.detected_at)); events.append(ExecutionEvent(assignment.uav_id,task_id,"service_complete",completion,next_position))
            else:
                missed.append(task_id); events.append(ExecutionEvent(assignment.uav_id,task_id,"service_unavailable",completion,next_position))
            current=next_position
        if config.return_to_base:
            leg=assignment.route[route_index:]
            distance=_polyline_distance(leg) if len(leg)>1 else _distance(current,scenario.scene.environment.base.position); time+=distance/uav_config.speed; total_distance+=distance; total_time+=distance/uav_config.speed; total_energy+=distance*uav_config.energy_per_meter; returns+=1; events.append(ExecutionEvent(assignment.uav_id,None,"return_to_base",time,scenario.scene.environment.base.position))
    return ExecutionResult(plan.method,tuple(events),tuple(served),tuple(missed),total_distance,total_time,total_energy,returns/max(1,len(plan.assignments)),sum(delays)/len(delays) if delays else 0.)


@dataclass(frozen=True)
class RecourseResult:
    initial_plan: Plan
    revised_plan: Plan
    accepted_replacement_ids: Tuple[str, ...]
    rejected_replacement_ids: Tuple[str, ...]

    def as_dict(self): return {"initial_plan":self.initial_plan.as_dict(),"revised_plan":self.revised_plan.as_dict(),"accepted_replacement_ids":list(self.accepted_replacement_ids),"rejected_replacement_ids":list(self.rejected_replacement_ids)}


def apply_recourse(scenario: Scenario, initial_plan: Plan, replacement_tasks: Iterable[SurvivorTask], uav_config: Optional[UAVConfig] = None) -> RecourseResult:
    replacements=tuple(replacement_tasks); existing_ids={task.identifier for task in scenario.tasks}; unique=tuple(task for task in replacements if task.identifier not in existing_ids)
    combined=Scenario(scenario.scenario_id,scenario.scene,tuple(scenario.tasks)+unique,scenario.scene_config,scenario.task_config,scenario.task_seed,uav_config=scenario.uav_config,route_config=scenario.route_config,execution_config=scenario.execution_config,uav_initial_states=scenario.uav_initial_states,supply_policy=scenario.supply_policy)
    revised=plan_tasks(combined,uav_config,initial_plan.method)
    accepted=tuple(task.identifier for task in unique if task.identifier in revised.served_task_ids); rejected=tuple(task.identifier for task in replacements if task.identifier not in accepted)
    return RecourseResult(initial_plan,revised,accepted,rejected)
