"""Event driven PGBM Version 2 execution with formulation aligned recourse."""

import json
import time
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Tuple

from ..execution import ExecutionEvent
from ..planner import BruteForceConfig, Plan, UAVConfig, plan_dispatch
from ..routing import RouteConfig
from ..scenario import Scenario
from ..tasks import SurvivorTask, service_value
from .models import MissionState, V2Config
from .recourse import (
    RecourseDecision,
    apply_recourse_candidate,
    build_schedule,
    project_mission,
    select_recourse,
)


def _phase_for_time(time_value: float, boundaries: Tuple[float, ...]) -> str:
    if time_value < boundaries[1]:
        return "high"
    if time_value < boundaries[2]:
        return "medium"
    return "low"


def _aggregate_inventory(tasks: Iterable[SurvivorTask]) -> Dict[str, int]:
    inventory: Dict[str, int] = {}
    for task in tasks:
        for item, quantity in task.demand.items():
            inventory[item] = inventory.get(item, 0) + int(quantity)
    return inventory


def _event_detail(value: Mapping[str, object]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _mission_next_time(
    mission: MissionState,
    now: float,
    turnaround_at: Mapping[str, float],
) -> Optional[float]:
    if mission.status == "turnaround":
        return turnaround_at.get(mission.mission_id)
    if mission.status != "active":
        return None
    future_times = [
        value
        for task_id, value in mission.schedule.arrival_times.items()
        if task_id not in mission.emitted_arrivals and value > now + 1e-9
    ]
    future_times.extend(
        value
        for task_id, value in mission.schedule.completion_times.items()
        if task_id not in mission.emitted_completions and value > now + 1e-9
    )
    if not mission.schedule.completion_times or mission.schedule.return_time > now + 1e-9:
        future_times.append(mission.schedule.return_time)
    return min(future_times) if future_times else None


@dataclass(frozen=True)
class V2EpisodeResult:
    """Serializable output of one V2 episode."""

    plan_method: str
    events: Tuple[ExecutionEvent, ...]
    dispatch_plans: Tuple[Plan, ...]
    recourse_decisions: Tuple[RecourseDecision, ...]
    mission_history: Tuple[Mapping[str, object], ...]
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
    mission_count: int
    candidate_count: int
    planner_runtime_seconds: float
    route_runtime_seconds: float
    recourse_runtime_seconds: float
    runtime_seconds: float
    phase_counts: Mapping[str, int]
    search_truncated_dispatches: int
    max_candidate_count: int
    max_pending_considered: int
    recourse_trigger_count: int
    accepted_replacements: int
    rejected_replacements: int
    replacement_gain: float
    displaced_task_ids: Tuple[str, ...]
    rejection_reasons: Mapping[str, int]

    def as_dict(self) -> Dict[str, object]:
        return {
            "plan_method": self.plan_method,
            "events": [event.as_dict() for event in self.events],
            "dispatch_plans": [plan.as_dict() for plan in self.dispatch_plans],
            "recourse_decisions": [decision.as_dict() for decision in self.recourse_decisions],
            "mission_history": list(self.mission_history),
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
            "mission_count": self.mission_count,
            "candidate_count": self.candidate_count,
            "planner_runtime_seconds": self.planner_runtime_seconds,
            "route_runtime_seconds": self.route_runtime_seconds,
            "recourse_runtime_seconds": self.recourse_runtime_seconds,
            "runtime_seconds": self.runtime_seconds,
            "phase_counts": dict(self.phase_counts),
            "search_truncated_dispatches": self.search_truncated_dispatches,
            "max_candidate_count": self.max_candidate_count,
            "max_pending_considered": self.max_pending_considered,
            "recourse_trigger_count": self.recourse_trigger_count,
            "accepted_replacements": self.accepted_replacements,
            "rejected_replacements": self.rejected_replacements,
            "replacement_gain": self.replacement_gain,
            "displaced_task_ids": list(self.displaced_task_ids),
            "rejection_reasons": dict(self.rejection_reasons),
        }


def _create_mission(
    scenario: Scenario,
    assignment,
    task_by_id: Mapping[str, SurvivorTask],
    now: float,
    uav_config: UAVConfig,
    route_config: RouteConfig,
    mission_index: int,
) -> MissionState:
    tasks = tuple(task_by_id[task_id] for task_id in assignment.task_ids)
    inventory = _aggregate_inventory(tasks)
    base = scenario.scene.environment.base.position
    schedule = build_schedule(
        scenario.scene.environment,
        base,
        assignment.route,
        tasks,
        now,
        base,
        inventory,
        0.0,
        0.0,
        uav_config,
        route_config,
        scenario.task_config.item_weights,
        scenario.task_config.service_value_decay_rate,
    )
    return MissionState(
        "mission_{}".format(mission_index),
        assignment.uav_id,
        tuple(assignment.task_ids),
        set(),
        schedule,
    )


def _record_due_mission_events(
    missions: Dict[str, MissionState],
    turnaround_at: Dict[str, float],
    task_by_id: Mapping[str, SurvivorTask],
    now: float,
    base,
    uav_status: Dict[str, str],
    available_at: Dict[str, float],
    turnaround_minutes: float,
    events: List[ExecutionEvent],
    mission_history: List[Mapping[str, object]],
    finalized_totals: List[Mapping[str, float]],
    speed: float,
) -> None:
    """Emit due arrival, service, return, and turnaround events."""

    for uav_id in sorted(tuple(missions)):
        mission = missions[uav_id]
        if mission.status == "active":
            projection = project_mission(mission, task_by_id, now, speed)
            for task_id in mission.schedule.task_ids:
                task = task_by_id[task_id]
                arrival_time = mission.schedule.arrival_times[task_id]
                if arrival_time <= now + 1e-9 and task_id not in mission.emitted_arrivals:
                    mission.emitted_arrivals.add(task_id)
                    events.append(ExecutionEvent(uav_id, task_id, "arrive", arrival_time, task.dropoff_waypoint))
                completion_time = mission.schedule.completion_times[task_id]
                if completion_time <= now + 1e-9 and task_id not in mission.emitted_completions:
                    mission.emitted_completions.add(task_id)
                    mission.completed_task_ids.add(task_id)
                    events.append(ExecutionEvent(uav_id, task_id, "service_complete", completion_time, task.dropoff_waypoint))
            if mission.schedule.return_time <= now + 1e-9:
                mission.status = "turnaround"
                uav_status[uav_id] = "turnaround"
                available_at[uav_id] = mission.schedule.return_time + turnaround_minutes
                turnaround_at[mission.mission_id] = available_at[uav_id]
                events.append(ExecutionEvent(uav_id, None, "return_to_base", mission.schedule.return_time, base))
                finalized_totals.append(
                    {
                        "distance": projection.distance_consumed,
                        "energy": projection.energy_consumed,
                        "returned": 1.0,
                    }
                )
                record = mission.as_dict()
                record["final_distance"] = projection.distance_consumed
                record["final_energy"] = projection.energy_consumed
                record["returned"] = True
                mission_history.append(record)
        elif mission.status == "turnaround" and available_at[uav_id] <= now + 1e-9:
            events.append(ExecutionEvent(uav_id, None, "resupply_complete", now, base))
            uav_status[uav_id] = "available"
            mission.status = "complete"
            missions.pop(uav_id, None)


def run_event_simulation_v2(
    scenario: Scenario,
    uav_config: Optional[UAVConfig] = None,
    route_config: Optional[RouteConfig] = None,
    config: Optional[V2Config] = None,
) -> V2EpisodeResult:
    """Run one deterministic two hour V2 episode."""

    simulation_config = config or V2Config()
    simulation_config.validate()
    uavs = uav_config or scenario.uav_config or UAVConfig()
    uavs.validate()
    route_config = route_config or scenario.route_config or RouteConfig()
    route_config.validate()
    tasks = tuple(sorted(scenario.tasks, key=lambda task: (task.detected_at, task.identifier)))
    task_by_id = {task.identifier: task for task in tasks}
    uav_ids = tuple("uav_{}".format(index + 1) for index in range(uavs.count))
    base = scenario.scene.environment.base.position
    uav_status = {uav_id: "available" for uav_id in uav_ids}
    available_at = {uav_id: 0.0 for uav_id in uav_ids}
    pending: Dict[str, SurvivorTask] = {}
    missions: Dict[str, MissionState] = {}
    turnaround_at: Dict[str, float] = {}
    events: List[ExecutionEvent] = []
    dispatch_plans: List[Plan] = []
    recourse_decisions: List[RecourseDecision] = []
    mission_history: List[Mapping[str, object]] = []
    finalized_totals: List[Mapping[str, float]] = []
    phase_counts = {"high": 0, "medium": 0, "low": 0}
    rejection_reasons: Counter = Counter()
    displaced_task_ids: List[str] = []
    task_index = 0
    now = 0.0
    first_iteration = True
    peak_queue = 0
    mission_index = 0
    decision_index = 0
    recourse_candidate_count = 0
    recourse_runtime = 0.0
    replacement_gain = 0.0
    search_truncated_dispatches = 0
    max_candidate_count = 0
    max_pending_considered = 0
    planner_runtime = 0.0
    route_runtime = 0.0
    started = time.perf_counter()

    while True:
        _record_due_mission_events(
            missions,
            turnaround_at,
            task_by_id,
            now,
            base,
            uav_status,
            available_at,
            simulation_config.turnaround_minutes,
            events,
            mission_history,
            finalized_totals,
            uavs.speed,
        )

        arrivals_processed = False
        while task_index < len(tasks) and tasks[task_index].detected_at <= now + 1e-9:
            task = tasks[task_index]
            pending[task.identifier] = task
            phase_counts[_phase_for_time(task.detected_at, scenario.task_config.phase_boundaries)] += 1
            events.append(ExecutionEvent("system", task.identifier, "task_detected", task.detected_at, task.dropoff_waypoint))
            task_index += 1
            arrivals_processed = True

            active_missions = {
                uav_id: mission
                for uav_id, mission in missions.items()
                if mission.status == "active"
            }
            all_deployed = bool(active_missions) and all(uav_status[uav_id] == "active" for uav_id in uav_ids)
            if simulation_config.recourse_enabled and all_deployed:
                decision_index += 1
                recourse_started = time.perf_counter()
                decision, selected = select_recourse(
                    active_missions,
                    task,
                    task_by_id,
                    scenario.scene.environment,
                    base,
                    route_config,
                    uavs,
                    scenario.task_config.item_weights,
                    scenario.task_config.service_value_decay_rate,
                    simulation_config.horizon_minutes,
                    now,
                    decision_index,
                )
                recourse_runtime += time.perf_counter() - recourse_started
                recourse_decisions.append(decision)
                recourse_candidate_count += len(decision.candidates)
                if not decision.accepted:
                    rejection_reasons[decision.reason] += 1
                    events.append(
                        ExecutionEvent(
                            "system",
                            task.identifier,
                            "recourse_rejected",
                            now,
                            task.dropoff_waypoint,
                            _event_detail({"reason": decision.reason, "candidate_count": len(decision.candidates)}),
                        )
                    )
                else:
                    assert selected is not None
                    mission = active_missions[selected.uav_id]
                    apply_recourse_candidate(mission, selected, now)
                    pending.pop(task.identifier, None)
                    pending[selected.displaced_task_id] = task_by_id[selected.displaced_task_id]
                    displaced_task_ids.append(selected.displaced_task_id)
                    replacement_gain += selected.delta_value
                    events.append(
                        ExecutionEvent(
                            selected.uav_id,
                            task.identifier,
                            "recourse_accepted",
                            now,
                            task.dropoff_waypoint,
                            _event_detail(
                                {
                                    "displaced_task_id": selected.displaced_task_id,
                                    "delta_J": selected.delta_value,
                                    "return_time": selected.return_time,
                                }
                            ),
                        )
                    )

        peak_queue = max(peak_queue, len(pending))
        available_uavs = tuple(uav_id for uav_id in uav_ids if uav_status[uav_id] == "available")
        trigger_dispatch = first_iteration or arrivals_processed or any(
            event.event == "resupply_complete" and abs(event.time - now) <= 1e-9 for event in events[-len(uav_ids) :]
        )
        if trigger_dispatch and pending and available_uavs:
            plan_started = time.perf_counter()
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
            planner_runtime += time.perf_counter() - plan_started
            dispatch_plans.append(plan)
            plan_candidate_count = int(plan.metadata.get("candidate_count", 0))
            max_candidate_count = max(max_candidate_count, plan_candidate_count)
            max_pending_considered = max(max_pending_considered, int(plan.metadata.get("search_task_count", 0)))
            recourse_candidate_count += 0
            if bool(plan.metadata.get("search_truncated", False)):
                search_truncated_dispatches += 1
            for assignment in plan.assignments:
                if not assignment.task_ids:
                    continue
                for task_id in assignment.task_ids:
                    pending.pop(task_id, None)
                mission_index += 1
                mission = _create_mission(
                    scenario,
                    assignment,
                    task_by_id,
                    now,
                    uavs,
                    route_config,
                    mission_index,
                )
                missions[assignment.uav_id] = mission
                uav_status[assignment.uav_id] = "active"
                available_at[assignment.uav_id] = mission.schedule.return_time + simulation_config.turnaround_minutes
                events.append(ExecutionEvent(assignment.uav_id, None, "dispatch", now, base))
            first_iteration = False
        else:
            first_iteration = False

        future_times: List[float] = []
        if task_index < len(tasks):
            future_times.append(tasks[task_index].detected_at)
        for mission in missions.values():
            next_time = _mission_next_time(mission, now, turnaround_at)
            if next_time is not None and next_time > now + 1e-9:
                future_times.append(next_time)
        if not future_times:
            break
        next_time = min(future_times)
        if next_time > simulation_config.horizon_minutes + 1e-9:
            break
        now = next_time

    # Close metrics at the horizon without inventing service completions.
    for mission in tuple(missions.values()):
        projection = project_mission(mission, task_by_id, min(now, simulation_config.horizon_minutes), uavs.speed)
        if not any(record.get("mission_id") == mission.mission_id for record in mission_history):
            record = mission.as_dict()
            record["final_distance"] = projection.distance_consumed
            record["final_energy"] = projection.energy_consumed
            record["returned"] = mission.status == "turnaround"
            mission_history.append(record)
            finalized_totals.append(
                {
                    "distance": projection.distance_consumed,
                    "energy": projection.energy_consumed,
                    "returned": 1.0 if mission.status == "turnaround" else 0.0,
                }
            )

    completion_times = {
        event.task_id: event.time
        for event in events
        if event.event == "service_complete" and event.task_id is not None
    }
    served_ids = tuple(sorted(completion_times))
    deferred_ids = tuple(sorted(task.identifier for task in tasks if task.identifier not in completion_times))
    objective_value = sum(
        service_value(
            task_by_id[task_id].severity,
            task_by_id[task_id].detected_at,
            completion_time,
            scenario.task_config.service_value_decay_rate,
        )
        for task_id, completion_time in completion_times.items()
    )
    requested_parcels = sum(sum(task.demand.values()) for task in tasks)
    dropped_parcels = sum(sum(task_by_id[task_id].demand.values()) for task_id in served_ids)
    delays = [completion_times[task_id] - task_by_id[task_id].detected_at for task_id in served_ids]
    mission_count = len(finalized_totals)
    returned_count = sum(int(record.get("returned", 0.0)) for record in finalized_totals)
    runtime = time.perf_counter() - started
    events.sort(key=lambda event: (event.time, event.event, event.uav_id, event.task_id or ""))
    accepted_count = sum(1 for decision in recourse_decisions if decision.accepted)
    rejected_count = len(recourse_decisions) - accepted_count
    total_candidate_count = sum(int(plan.metadata.get("candidate_count", 0)) for plan in dispatch_plans) + recourse_candidate_count
    max_candidate_count = max(max_candidate_count, max((len(decision.candidates) for decision in recourse_decisions), default=0))
    return V2EpisodeResult(
        "pgbm_initial_bruteforce_v2_recourse" if simulation_config.recourse_enabled else "pgbm_initial_bruteforce_v2_fixed",
        tuple(events),
        tuple(dispatch_plans),
        tuple(recourse_decisions),
        tuple(mission_history),
        served_ids,
        deferred_ids,
        objective_value,
        sum(float(record.get("distance", 0.0)) for record in finalized_totals),
        sum(float(record.get("distance", 0.0)) for record in finalized_totals) / uavs.speed,
        sum(float(record.get("energy", 0.0)) for record in finalized_totals),
        requested_parcels,
        dropped_parcels,
        dropped_parcels / requested_parcels if requested_parcels else 0.0,
        returned_count / mission_count if mission_count else 1.0,
        sum(delays) / len(delays) if delays else 0.0,
        peak_queue,
        len(dispatch_plans),
        mission_count,
        total_candidate_count,
        planner_runtime,
        sum(float(plan.metadata.get("route_runtime_seconds", 0.0)) for plan in dispatch_plans),
        recourse_runtime,
        runtime,
        phase_counts,
        search_truncated_dispatches,
        max_candidate_count,
        max_pending_considered,
        len(recourse_decisions),
        accepted_count,
        rejected_count,
        replacement_gain,
        tuple(displaced_task_ids),
        dict(rejection_reasons),
    )
