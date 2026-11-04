"""Event driven PGBM Version 2.1 execution with one slot cache recourse."""

import json
import time
from collections import Counter
from dataclasses import replace
from typing import Dict, List, Mapping, Optional, Tuple

from ..execution import ExecutionEvent
from ..planner import BruteForceConfig, Plan, UAVConfig, plan_dispatch
from ..routing import RouteConfig
from ..scenario import Scenario
from ..tasks import SurvivorTask, service_value
from ..v2.event_simulation import (
    V2EpisodeResult,
    _aggregate_inventory,
    _event_detail,
    _mission_next_time,
    _phase_for_time,
    run_event_simulation_v2,
)
from ..v2.models import MissionState
from ..v2.recourse import apply_recourse_candidate, build_schedule, project_mission, select_recourse
from .cache import (
    CacheLoadResult,
    aggregate_inventory,
    classify_candidate,
    prepare_cache_load,
    update_cache_state_after_acceptance,
)
from .models import (
    CacheCandidateEvidence,
    CacheLoadDecision,
    MissionCacheState,
    V21Config,
    V21EpisodeResult,
    V21RecourseDecision,
)


def _create_mission_v21(
    scenario: Scenario,
    assignment,
    task_by_id: Mapping[str, SurvivorTask],
    now: float,
    uav_config: UAVConfig,
    route_config: RouteConfig,
    mission_index: int,
    config: V21Config,
) -> Tuple[MissionState, MissionCacheState, CacheLoadDecision]:
    mission_id = "mission_{}".format(mission_index)
    tasks = tuple(task_by_id[task_id] for task_id in assignment.task_ids)
    load_result = prepare_cache_load(
        scenario.scene.environment,
        scenario.scene.environment.base.position,
        assignment,
        tasks,
        now,
        config.horizon_minutes,
        uav_config,
        route_config,
        scenario.task_config.item_types,
        scenario.task_config.item_weights,
        scenario.task_config.service_value_decay_rate,
        config.cache_enabled,
        config.max_cache_slots,
        config.cache_selection_policy,
        config.cache_item_prior,
    )
    load_decision = replace(load_result.decision, mission_id=mission_id)
    if load_result.schedule is None:
        schedule = build_schedule(
            scenario.scene.environment,
            scenario.scene.environment.base.position,
            assignment.route,
            tasks,
            now,
            scenario.scene.environment.base.position,
            load_result.inventory,
            0.0,
            0.0,
            uav_config,
            route_config,
            scenario.task_config.item_weights,
            scenario.task_config.service_value_decay_rate,
        )
    else:
        schedule = load_result.schedule
    mission = MissionState(
        mission_id,
        assignment.uav_id,
        tuple(assignment.task_ids),
        set(),
        schedule,
    )
    cache_state = MissionCacheState(
        mission_id,
        assignment.uav_id,
        now,
        dict(load_result.cache_inventory),
    )
    return mission, cache_state, load_decision


def _record_due_mission_events_v21(
    missions: Dict[str, MissionState],
    cache_states: Dict[str, MissionCacheState],
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
    returned_cache_parcels: List[int],
    speed: float,
) -> None:
    """Emit due execution events and close missions that return to base."""

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
                cache_state = cache_states.get(mission.mission_id)
                if cache_state is not None:
                    returned_cache_parcels.append(cache_state.remaining_cache_parcels)
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
                record["cache"] = cache_state.as_dict() if cache_state is not None else {}
                mission_history.append(record)
        elif mission.status == "turnaround" and available_at[uav_id] <= now + 1e-9:
            events.append(ExecutionEvent(uav_id, None, "resupply_complete", now, base))
            uav_status[uav_id] = "available"
            mission.status = "complete"
            cache_states.pop(mission.mission_id, None)
            missions.pop(uav_id, None)


def _selected_cache_evidence(
    decision,
    evidence: Tuple[CacheCandidateEvidence, ...],
) -> Optional[CacheCandidateEvidence]:
    if not decision.accepted:
        return None
    for candidate in evidence:
        if (
            candidate.uav_id == decision.selected_uav_id
            and candidate.displaced_task_id == decision.displaced_task_id
        ):
            return candidate
    return None


def _cache_event_detail(
    decision,
    evidence: Tuple[CacheCandidateEvidence, ...],
) -> Dict[str, object]:
    selected = _selected_cache_evidence(decision, evidence)
    if selected is not None:
        return {
            "cache_match": selected.cache_match,
            "cache_assisted": selected.cache_assisted,
            "cache_used": dict(selected.cache_used),
            "cache_source": selected.source,
        }
    return {
        "cache_match": any(item.cache_match for item in evidence),
        "cache_assisted": any(item.cache_assisted for item in evidence),
        "cache_used": {},
        "cache_source": "candidate_not_selected",
    }


def run_event_simulation_v21(
    scenario: Scenario,
    uav_config: Optional[UAVConfig] = None,
    route_config: Optional[RouteConfig] = None,
    config: Optional[V21Config] = None,
) -> V21EpisodeResult:
    """Run one deterministic two hour Version 2.1 episode.

    With cache loading disabled, this delegates to the canonical V2 runner so
    the control path remains exactly comparable.  The cache enabled path is a
    small copy of the V2 event loop with dispatch time reserve state added.
    """

    simulation_config = config or V21Config()
    simulation_config.validate()
    if not simulation_config.cache_enabled or simulation_config.max_cache_slots == 0:
        base_result = run_event_simulation_v2(
            scenario,
            uav_config,
            route_config,
            simulation_config.as_v2_config(),
        )
        return V21EpisodeResult(base_result)

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
    cache_states: Dict[str, MissionCacheState] = {}
    turnaround_at: Dict[str, float] = {}
    events: List[ExecutionEvent] = []
    dispatch_plans: List[Plan] = []
    recourse_decisions = []
    cache_recourse_decisions: List[V21RecourseDecision] = []
    cache_load_decisions: List[CacheLoadDecision] = []
    mission_history: List[Mapping[str, object]] = []
    finalized_totals: List[Mapping[str, float]] = []
    phase_counts = {"high": 0, "medium": 0, "low": 0}
    rejection_reasons: Counter = Counter()
    cache_load_rejections: Counter = Counter()
    cache_miss_reasons: Counter = Counter()
    displaced_task_ids: List[str] = []
    returned_cache_parcels: List[int] = []
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
    started = time.perf_counter()
    cache_loaded_parcels = 0
    cache_used_parcels = 0
    cache_match_count = 0
    cache_hit_count = 0
    cache_assisted_count = 0
    cache_energy_overhead = 0.0

    while True:
        _record_due_mission_events_v21(
            missions,
            cache_states,
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
            returned_cache_parcels,
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
                candidate_evidence = tuple(
                    classify_candidate(
                        candidate,
                        cache_states[active_missions[candidate.uav_id].mission_id],
                        task_by_id,
                    )
                    for candidate in decision.candidates
                )
                if any(item.cache_match for item in candidate_evidence):
                    cache_match_count += 1
                selected_evidence = _selected_cache_evidence(decision, candidate_evidence)
                if not decision.accepted:
                    rejection_reasons[decision.reason] += 1
                    if not any(item.cache_match for item in candidate_evidence):
                        cache_miss_reasons[decision.reason] += 1
                    else:
                        cache_miss_reasons["cache_match_not_selected"] += 1
                    events.append(
                        ExecutionEvent(
                            "system",
                            task.identifier,
                            "recourse_rejected",
                            now,
                            task.dropoff_waypoint,
                            _event_detail(
                                {
                                    "reason": decision.reason,
                                    "candidate_count": len(decision.candidates),
                                    **_cache_event_detail(decision, candidate_evidence),
                                }
                            ),
                        )
                    )
                else:
                    assert selected is not None
                    assert selected_evidence is not None
                    mission = active_missions[selected.uav_id]
                    apply_recourse_candidate(mission, selected, now)
                    update_cache_state_after_acceptance(
                        cache_states[mission.mission_id],
                        selected,
                        selected_evidence,
                        task_by_id,
                    )
                    pending.pop(task.identifier, None)
                    pending[selected.displaced_task_id] = task_by_id[selected.displaced_task_id]
                    displaced_task_ids.append(selected.displaced_task_id)
                    replacement_gain += selected.delta_value
                    if selected_evidence.cache_match:
                        cache_hit_count += 1
                    if selected_evidence.cache_assisted:
                        cache_assisted_count += 1
                        cache_used_parcels += sum(selected_evidence.cache_used.values())
                    if not selected_evidence.cache_match:
                        cache_miss_reasons[selected_evidence.reason] += 1
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
                                    **_cache_event_detail(decision, candidate_evidence),
                                }
                            ),
                        )
                    )
                cache_recourse_decisions.append(
                    V21RecourseDecision(
                        decision,
                        bool(selected_evidence and selected_evidence.cache_match),
                        bool(selected_evidence and selected_evidence.cache_assisted),
                        dict(selected_evidence.cache_used) if selected_evidence is not None else {},
                        selected_evidence.source if selected_evidence is not None else "none",
                        candidate_evidence,
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
            if bool(plan.metadata.get("search_truncated", False)):
                search_truncated_dispatches += 1
            for assignment in plan.assignments:
                if not assignment.task_ids:
                    continue
                for task_id in assignment.task_ids:
                    pending.pop(task_id, None)
                mission_index += 1
                mission, cache_state, load_decision = _create_mission_v21(
                    scenario,
                    assignment,
                    task_by_id,
                    now,
                    uavs,
                    route_config,
                    mission_index,
                    simulation_config,
                )
                missions[assignment.uav_id] = mission
                cache_states[mission.mission_id] = cache_state
                cache_load_decisions.append(load_decision)
                if load_decision.loaded:
                    cache_loaded_parcels += load_decision.loaded_parcels
                    cache_energy_overhead += load_decision.energy_overhead
                else:
                    cache_load_rejections[load_decision.reason] += 1
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

    for mission in tuple(missions.values()):
        projection = project_mission(mission, task_by_id, min(now, simulation_config.horizon_minutes), uavs.speed)
        if not any(record.get("mission_id") == mission.mission_id for record in mission_history):
            record = mission.as_dict()
            record["final_distance"] = projection.distance_consumed
            record["final_energy"] = projection.energy_consumed
            record["returned"] = mission.status == "turnaround"
            cache_state = cache_states.get(mission.mission_id)
            record["cache"] = cache_state.as_dict() if cache_state is not None else {}
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
    base_result = V2EpisodeResult(
        "pgbm_initial_bruteforce_v2_1_cache_recourse" if simulation_config.recourse_enabled else "pgbm_initial_bruteforce_v2_1_cache_fixed",
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
    return V21EpisodeResult(
        base_result,
        tuple(cache_load_decisions),
        tuple(cache_recourse_decisions),
        cache_loaded_parcels,
        cache_used_parcels,
        sum(returned_cache_parcels),
        cache_match_count,
        cache_hit_count,
        cache_assisted_count,
        cache_energy_overhead,
        dict(cache_load_rejections),
        dict(cache_miss_reasons),
    )
