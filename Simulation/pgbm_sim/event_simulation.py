"""Seeded two hour event driven execution for Initial Solution V1."""

import time
from dataclasses import asdict, dataclass
from typing import Dict, Mapping, Optional, Tuple

from .execution import ExecutionEvent
from .planner import BruteForceConfig, Plan, UAVConfig, plan_dispatch
from .routing import RouteConfig
from .scenario import Scenario


@dataclass(frozen=True)
class EventSimulationConfig:
    horizon_minutes: float = 120.0
    turnaround_minutes: float = 5.0
    planner_method: str = "pgbm_initial_bruteforce_v1"
    max_pending_tasks: int = 8
    max_candidate_plans: int = 50000

    def validate(self) -> None:
        if self.horizon_minutes <= 0 or self.turnaround_minutes < 0:
            raise ValueError("event horizon must be positive and turnaround must be non negative")
        if self.planner_method != "pgbm_initial_bruteforce_v1":
            raise ValueError("event simulation currently supports the V1 brute force planner")
        BruteForceConfig(self.max_pending_tasks, self.max_candidate_plans).validate()

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class EventSimulationResult:
    plan_method: str
    events: Tuple[ExecutionEvent, ...]
    dispatch_plans: Tuple[Plan, ...]
    served_task_ids: Tuple[str, ...]
    deferred_task_ids: Tuple[str, ...]
    objective_value: float
    total_distance: float
    total_travel_time: float
    total_energy: float
    requested_parcels: int
    dropped_parcels: int
    parcel_delivery_rate: float
    safe_return_rate: float
    average_completion_delay: float
    peak_queue_size: int
    dispatch_count: int
    candidate_count: int
    planner_runtime_seconds: float
    route_runtime_seconds: float
    runtime_seconds: float
    phase_counts: Mapping[str, int]
    search_truncated_dispatches: int
    max_candidate_count: int
    max_pending_considered: int

    def as_dict(self) -> Dict[str, object]:
        return {
            "plan_method": self.plan_method,
            "events": [event.as_dict() for event in self.events],
            "dispatch_plans": [plan.as_dict() for plan in self.dispatch_plans],
            "served_task_ids": list(self.served_task_ids),
            "deferred_task_ids": list(self.deferred_task_ids),
            "objective_value": self.objective_value,
            "total_distance": self.total_distance,
            "total_travel_time": self.total_travel_time,
            "total_energy": self.total_energy,
            "requested_parcels": self.requested_parcels,
            "dropped_parcels": self.dropped_parcels,
            "parcel_delivery_rate": self.parcel_delivery_rate,
            "safe_return_rate": self.safe_return_rate,
            "average_completion_delay": self.average_completion_delay,
            "peak_queue_size": self.peak_queue_size,
            "dispatch_count": self.dispatch_count,
            "candidate_count": self.candidate_count,
            "planner_runtime_seconds": self.planner_runtime_seconds,
            "route_runtime_seconds": self.route_runtime_seconds,
            "runtime_seconds": self.runtime_seconds,
            "phase_counts": dict(self.phase_counts),
            "search_truncated_dispatches": self.search_truncated_dispatches,
            "max_candidate_count": self.max_candidate_count,
            "max_pending_considered": self.max_pending_considered,
        }


def _phase_for_time(time_value: float, boundaries: Tuple[float, ...]) -> str:
    if time_value < boundaries[1]:
        return "high"
    if time_value < boundaries[2]:
        return "medium"
    return "low"


def _event_priority(event: ExecutionEvent) -> Tuple[int, str, str]:
    priorities = {
        "task_detected": 0,
        "dispatch": 1,
        "arrive": 2,
        "service_complete": 3,
        "return_to_base": 4,
        "resupply_complete": 5,
    }
    return priorities.get(event.event, 99), event.uav_id, event.task_id or ""


def run_event_simulation(
    scenario: Scenario,
    uav_config: Optional[UAVConfig] = None,
    route_config: Optional[RouteConfig] = None,
    config: Optional[EventSimulationConfig] = None,
) -> EventSimulationResult:
    """Run a deterministic no recourse event episode over a fixed horizon."""
    simulation_config = config or EventSimulationConfig()
    simulation_config.validate()
    uavs = uav_config or scenario.uav_config or UAVConfig()
    uavs.validate()
    route_config = route_config or scenario.route_config or RouteConfig()
    route_config.validate()
    tasks = tuple(sorted(scenario.tasks, key=lambda task: (task.detected_at, task.identifier)))
    task_by_id = {task.identifier: task for task in tasks}
    uav_ids = tuple("uav_{}".format(index + 1) for index in range(uavs.count))
    base = scenario.scene.environment.base.position
    status = {uav_id: "available" for uav_id in uav_ids}
    available_at = {uav_id: 0.0 for uav_id in uav_ids}
    pending: Dict[str, object] = {}
    events = []
    dispatch_plans = []
    served = set()
    phase_counts = {"high": 0, "medium": 0, "low": 0}
    task_index = 0
    now = 0.0
    first_iteration = True
    peak_queue = 0
    search_truncated_dispatches = 0
    max_candidate_count = 0
    max_pending_considered = 0
    total_started = time.perf_counter()

    while True:
        arrivals_processed = False
        while task_index < len(tasks) and tasks[task_index].detected_at <= now + 1e-9:
            task = tasks[task_index]
            pending[task.identifier] = task
            phase_counts[_phase_for_time(task.detected_at, scenario.task_config.phase_boundaries)] += 1
            events.append(ExecutionEvent("system", task.identifier, "task_detected", task.detected_at, task.dropoff_waypoint))
            task_index += 1
            arrivals_processed = True

        released = []
        for uav_id in uav_ids:
            if status[uav_id] == "busy" and available_at[uav_id] <= now + 1e-9:
                status[uav_id] = "available"
                released.append(uav_id)
                events.append(ExecutionEvent(uav_id, None, "resupply_complete", now, base))

        available_uavs = tuple(uav_id for uav_id in uav_ids if status[uav_id] == "available")
        peak_queue = max(peak_queue, len(pending))
        trigger = first_iteration or arrivals_processed or bool(released)
        if trigger and pending and available_uavs:
            plan = plan_dispatch(
                scenario,
                tuple(pending.values()),
                available_uavs,
                now,
                uavs,
                route_config,
                method=simulation_config.planner_method,
                horizon_minutes=simulation_config.horizon_minutes,
                search_config=BruteForceConfig(
                    simulation_config.max_pending_tasks,
                    simulation_config.max_candidate_plans,
                ),
            )
            dispatch_plans.append(plan)
            candidate_count = int(plan.metadata.get("candidate_count", 0))
            max_candidate_count = max(max_candidate_count, candidate_count)
            max_pending_considered = max(
                max_pending_considered,
                int(plan.metadata.get("search_task_count", 0)),
            )
            if bool(plan.metadata.get("search_truncated", False)):
                search_truncated_dispatches += 1
            selected = set(plan.served_task_ids)
            for task_id in selected:
                pending.pop(task_id, None)
                served.add(task_id)
            for assignment in plan.assignments:
                if not assignment.task_ids:
                    continue
                timeline = plan.metadata["assignment_timelines"][assignment.uav_id]
                status[assignment.uav_id] = "busy"
                available_at[assignment.uav_id] = float(timeline["return_time"]) + simulation_config.turnaround_minutes
                events.append(ExecutionEvent(assignment.uav_id, None, "dispatch", now, base))
                for task_id in assignment.task_ids:
                    task = task_by_id[task_id]
                    events.append(
                        ExecutionEvent(
                            assignment.uav_id,
                            task_id,
                            "arrive",
                            float(timeline["arrival_times"][task_id]),
                            task.dropoff_waypoint,
                        )
                    )
                    events.append(
                        ExecutionEvent(
                            assignment.uav_id,
                            task_id,
                            "service_complete",
                            float(timeline["completion_times"][task_id]),
                            task.dropoff_waypoint,
                        )
                    )
                events.append(
                    ExecutionEvent(
                        assignment.uav_id,
                        None,
                        "return_to_base",
                        float(timeline["return_time"]),
                        base,
                    )
                )
            first_iteration = False
        else:
            first_iteration = False

        future_times = []
        if task_index < len(tasks):
            future_times.append(tasks[task_index].detected_at)
        future_times.extend(
            available_at[uav_id]
            for uav_id in uav_ids
            if status[uav_id] == "busy" and available_at[uav_id] > now + 1e-9
        )
        if not future_times:
            break
        next_time = min(future_times)
        if next_time > simulation_config.horizon_minutes + 1e-9:
            break
        now = next_time

    dispatch_plans = tuple(dispatch_plans)
    completed_task_ids = {
        event.task_id
        for event in events
        if event.event == "service_complete" and event.task_id is not None
    }
    served_ids = tuple(sorted(completed_task_ids))
    deferred_ids = tuple(sorted(task.identifier for task in tasks if task.identifier not in completed_task_ids))
    objective_value = sum(plan.objective_value for plan in dispatch_plans)
    total_distance = sum(assignment.distance for plan in dispatch_plans for assignment in plan.assignments)
    total_energy = sum(assignment.energy for plan in dispatch_plans for assignment in plan.assignments)
    total_travel_time = total_distance / uavs.speed
    delays = []
    for plan in dispatch_plans:
        for timeline in plan.metadata.get("assignment_timelines", {}).values():
            for task_id, completion_time in timeline.get("completion_times", {}).items():
                delays.append(float(completion_time) - task_by_id[task_id].detected_at)
    mission_count = sum(1 for plan in dispatch_plans for assignment in plan.assignments if assignment.task_ids)
    return_count = sum(1 for event in events if event.event == "return_to_base")
    requested_parcels = sum(sum(task.demand.values()) for task in tasks)
    dropped_parcels = sum(sum(task_by_id[task_id].demand.values()) for task_id in completed_task_ids)
    runtime = time.perf_counter() - total_started
    events.sort(key=lambda event: (event.time, _event_priority(event)))
    return EventSimulationResult(
        simulation_config.planner_method,
        tuple(events),
        dispatch_plans,
        served_ids,
        deferred_ids,
        objective_value,
        total_distance,
        total_travel_time,
        total_energy,
        requested_parcels,
        dropped_parcels,
        dropped_parcels / requested_parcels if requested_parcels else 0.0,
        return_count / mission_count if mission_count else 1.0,
        sum(delays) / len(delays) if delays else 0.0,
        peak_queue,
        len(dispatch_plans),
        sum(int(plan.metadata.get("candidate_count", 0)) for plan in dispatch_plans),
        sum(float(plan.metadata.get("planner_runtime_seconds", 0.0)) for plan in dispatch_plans),
        sum(float(plan.metadata.get("route_runtime_seconds", 0.0)) for plan in dispatch_plans),
        runtime,
        phase_counts,
        search_truncated_dispatches,
        max_candidate_count,
        max_pending_considered,
    )
