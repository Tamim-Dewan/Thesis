"""One-for-one active mission replacement for PGBM Version 2.

This module deliberately reuses the V1 route contract instead of creating a
second routing interpretation.  A candidate route starts at the UAV's
projected current position, visits the revised remaining task sequence, and
returns to the same physical base through :func:`route_between`.
"""

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from ..planner import UAVConfig
from ..routing import RouteConfig, RoutePlanningError, route_between
from ..tasks import SurvivorTask, service_value
from .models import (
    MissionProjection,
    MissionSchedule,
    MissionState,
    Point,
    TimelineSegment,
)


_EPSILON = 1e-9


def _distance(first: Point, second: Point) -> float:
    return math.sqrt(sum((first[index] - second[index]) ** 2 for index in range(3)))


def _polyline_distance(points: Sequence[Point]) -> float:
    return sum(_distance(first, second) for first, second in zip(points, points[1:]))


def _positive_ascent(points: Sequence[Point]) -> float:
    return sum(max(0.0, second[2] - first[2]) for first, second in zip(points, points[1:]))


def _extend_route(target: List[Point], segment: Sequence[Point]) -> None:
    if not target:
        target.extend(segment)
    elif segment:
        target.extend(segment[1:])


def _find_target_index(route: Sequence[Point], start_index: int, target: Point) -> int:
    if start_index < len(route) and route[start_index] == target:
        return start_index
    for index in range(start_index + 1, len(route)):
        if route[index] == target:
            return index
    raise RoutePlanningError("mission route does not contain the requested task waypoint")


def _demand_fits(required: Mapping[str, int], inventory: Mapping[str, int]) -> bool:
    return all(int(required.get(item, 0)) <= int(inventory.get(item, 0)) for item in required)


def _scheduled_demand(tasks: Iterable[SurvivorTask]) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for task in tasks:
        for item, quantity in task.demand.items():
            result[item] = result.get(item, 0) + int(quantity)
    return result


def _inventory_mass(inventory: Mapping[str, int], item_weights: Mapping[str, float]) -> float:
    return sum(float(item_weights.get(item, 0.0)) * int(quantity) for item, quantity in inventory.items())


def _subtract_demand(inventory: Dict[str, int], task: SurvivorTask) -> None:
    for item, quantity in task.demand.items():
        inventory[item] = int(inventory.get(item, 0)) - int(quantity)
        if inventory[item] < 0:
            raise ValueError("mission inventory became negative for {}".format(item))


def build_route_from_position(
    environment,
    current_position: Point,
    tasks: Sequence[SurvivorTask],
    base: Point,
    route_config: RouteConfig,
) -> Tuple[Point, ...]:
    """Build a collision-aware route from a current position through tasks to base."""

    route: List[Point] = [current_position]
    current = current_position
    for task in tasks:
        leg = route_between(environment, current, task.dropoff_waypoint, route_config)
        _extend_route(route, leg.route)
        current = task.dropoff_waypoint
    if current != base:
        return_leg = route_between(environment, current, base, route_config)
        _extend_route(route, return_leg.route)
    return tuple(route)


def _travel_segment(
    path: Sequence[Point],
    start_time: float,
    carried_mass: float,
    uav_config: UAVConfig,
    task_id: Optional[str] = None,
) -> TimelineSegment:
    distance = _polyline_distance(path)
    duration = distance / uav_config.speed
    energy = (
        distance * uav_config.energy_per_meter
        + distance * carried_mass * uav_config.payload_energy_per_kg_meter
        + _positive_ascent(path) * uav_config.ascent_energy_per_meter
    )
    return TimelineSegment(
        "travel",
        task_id,
        tuple(path),
        start_time,
        start_time + duration,
        distance,
        energy,
        carried_mass,
    )


def _service_segment(
    task: SurvivorTask,
    start_time: float,
    duration: float,
    uav_config: UAVConfig,
) -> TimelineSegment:
    return TimelineSegment(
        "service",
        task.identifier,
        (task.dropoff_waypoint,),
        start_time,
        start_time + duration,
        0.0,
        duration * uav_config.service_energy_per_minute,
        task.required_payload_mass,
    )


def build_schedule(
    environment,
    base: Point,
    route: Sequence[Point],
    tasks: Sequence[SurvivorTask],
    start_time: float,
    start_position: Point,
    initial_inventory: Mapping[str, int],
    distance_before: float,
    energy_before: float,
    uav_config: UAVConfig,
    route_config: RouteConfig,
    item_weights: Mapping[str, float],
    decay_rate: float,
    fixed_service_task_id: Optional[str] = None,
    service_remaining: float = 0.0,
) -> MissionSchedule:
    """Create a route timeline from a recourse state.

    ``initial_inventory`` is the actual inventory still on the UAV at
    ``start_time``.  A task already being serviced can be kept as the first
    task with only its remaining service time applied.
    """

    if not route or route[0] != start_position:
        raise RoutePlanningError("mission route must start at the projected UAV position")
    if route[-1] != base:
        raise RoutePlanningError("mission route must return to the same physical base")

    inventory = {str(item): int(quantity) for item, quantity in initial_inventory.items()}
    segments: List[TimelineSegment] = []
    arrival_times: Dict[str, float] = {}
    completion_times: Dict[str, float] = {}
    current_time = float(start_time)
    cursor_index = 0
    total_distance = 0.0
    total_energy = 0.0
    objective_value = 0.0

    for task_index, task in enumerate(tasks):
        target_index = _find_target_index(route, cursor_index, task.dropoff_waypoint)
        path = tuple(route[cursor_index : target_index + 1])
        carried_mass = _inventory_mass(inventory, item_weights)
        travel = _travel_segment(path, current_time, carried_mass, uav_config, task.identifier)
        if travel.distance > _EPSILON:
            segments.append(travel)
        current_time = travel.end_time
        total_distance += travel.distance
        total_energy += travel.energy
        arrival_times[task.identifier] = current_time

        if task_index == 0 and task.identifier == fixed_service_task_id:
            duration = max(0.0, float(service_remaining))
        else:
            duration = float(task.service_duration)
        if duration <= _EPSILON:
            raise ValueError("task service duration must remain positive")
        service = _service_segment(task, current_time, duration, uav_config)
        segments.append(service)
        current_time = service.end_time
        total_energy += service.energy
        completion_times[task.identifier] = current_time
        objective_value += service_value(task.severity, task.detected_at, current_time, decay_rate)
        _subtract_demand(inventory, task)
        cursor_index = target_index

    return_path = tuple(route[cursor_index:])
    carried_mass = _inventory_mass(inventory, item_weights)
    return_segment = _travel_segment(return_path, current_time, carried_mass, uav_config)
    if return_segment.distance > _EPSILON:
        segments.append(return_segment)
    current_time = return_segment.end_time
    total_distance += return_segment.distance
    total_energy += return_segment.energy

    return MissionSchedule(
        tuple(task.identifier for task in tasks),
        tuple(route),
        float(start_time),
        start_position,
        float(distance_before),
        float(energy_before),
        dict(initial_inventory),
        tuple(segments),
        dict(arrival_times),
        dict(completion_times),
        current_time,
        total_distance,
        total_energy,
        objective_value,
    )


def _position_on_path(path: Sequence[Point], distance: float) -> Point:
    if not path:
        raise ValueError("cannot project an empty path")
    if len(path) == 1 or distance <= _EPSILON:
        return path[0]
    remaining = min(distance, _polyline_distance(path))
    for first, second in zip(path, path[1:]):
        leg = _distance(first, second)
        if remaining <= leg + _EPSILON:
            if leg <= _EPSILON:
                return second
            ratio = max(0.0, min(1.0, remaining / leg))
            return tuple(first[index] + ratio * (second[index] - first[index]) for index in range(3))  # type: ignore[return-value]
        remaining -= leg
    return path[-1]


def _project_segment(segment: TimelineSegment, time_value: float, speed: float) -> Tuple[Point, float, float]:
    if segment.kind == "service" or segment.end_time <= segment.start_time + _EPSILON:
        ratio = 1.0 if time_value >= segment.end_time else 0.0
        return segment.path[0], segment.energy * ratio, 0.0
    ratio = max(0.0, min(1.0, (time_value - segment.start_time) / (segment.end_time - segment.start_time)))
    return _position_on_path(segment.path, segment.distance * ratio), segment.energy * ratio, segment.distance * ratio


def project_mission(
    mission: MissionState,
    task_by_id: Mapping[str, SurvivorTask],
    time_value: float,
    speed: float,
) -> MissionProjection:
    """Project route position, inventory, energy, and task state at a time."""

    schedule = mission.schedule
    completed = set(mission.completed_task_ids)
    for task_id, completion_time in schedule.completion_times.items():
        if completion_time <= time_value + _EPSILON:
            completed.add(task_id)
    remaining = tuple(task_id for task_id in schedule.task_ids if task_id not in completed)
    inventory = {str(item): int(quantity) for item, quantity in schedule.initial_inventory.items()}
    for task_id in schedule.task_ids:
        if task_id in completed:
            _subtract_demand(inventory, task_by_id[task_id])

    distance_consumed = schedule.distance_before
    energy_consumed = schedule.energy_before
    position = schedule.start_position
    current_task_id: Optional[str] = None
    service_in_progress = False
    service_remaining = 0.0
    segment_kind = "waiting"
    for segment in schedule.segments:
        if time_value >= segment.end_time - _EPSILON:
            distance_consumed += segment.distance
            energy_consumed += segment.energy
            continue
        if time_value < segment.start_time - _EPSILON:
            break
        position, segment_energy, segment_distance = _project_segment(segment, time_value, speed)
        distance_consumed += segment_distance
        energy_consumed += segment_energy
        current_task_id = segment.task_id
        segment_kind = segment.kind
        if segment.kind == "service":
            service_in_progress = True
            service_remaining = max(0.0, segment.end_time - time_value)
        break
    else:
        position = schedule.route[-1]
        segment_kind = "returned"

    return MissionProjection(
        float(time_value),
        position,
        tuple(sorted(completed)),
        remaining,
        current_task_id,
        service_in_progress,
        service_remaining,
        inventory,
        distance_consumed,
        energy_consumed,
        segment_kind,
    )


def remaining_objective(
    mission: MissionState,
    task_by_id: Mapping[str, SurvivorTask],
    time_value: float,
    decay_rate: float,
) -> float:
    """Evaluate the current remaining mission without double counting completed work."""

    return sum(
        service_value(task_by_id[task_id].severity, task_by_id[task_id].detected_at, completion_time, decay_rate)
        for task_id, completion_time in mission.schedule.completion_times.items()
        if completion_time > time_value + _EPSILON
    )


@dataclass(frozen=True)
class ReplacementCandidate:
    """One UAV and one displaced task considered at a recourse trigger."""

    uav_id: str
    displaced_task_id: str
    new_task_id: str
    item_feasible: bool
    payload_feasible: bool
    route_feasible: bool
    energy_feasible: bool
    horizon_feasible: bool
    old_value: float
    new_value: float
    delta_value: float
    rejection_reason: str
    revised_task_ids: Tuple[str, ...] = ()
    route: Tuple[Point, ...] = ()
    return_time: Optional[float] = None
    additional_distance: float = 0.0
    additional_energy: float = 0.0
    schedule: Optional[MissionSchedule] = None
    projection: Optional[MissionProjection] = None

    @property
    def feasible(self) -> bool:
        return self.item_feasible and self.payload_feasible and self.route_feasible and self.energy_feasible and self.horizon_feasible

    def as_dict(self) -> Dict[str, object]:
        return {
            "uav_id": self.uav_id,
            "displaced_task_id": self.displaced_task_id,
            "new_task_id": self.new_task_id,
            "item_feasible": self.item_feasible,
            "payload_feasible": self.payload_feasible,
            "route_feasible": self.route_feasible,
            "energy_feasible": self.energy_feasible,
            "horizon_feasible": self.horizon_feasible,
            "feasible": self.feasible,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "delta_value": self.delta_value,
            "rejection_reason": self.rejection_reason,
            "revised_task_ids": list(self.revised_task_ids),
            "route": [list(point) for point in self.route],
            "return_time": self.return_time,
            "additional_distance": self.additional_distance,
            "additional_energy": self.additional_energy,
        }


@dataclass(frozen=True)
class RecourseDecision:
    """Trace for one newly detected task."""

    decision_id: int
    trigger_time: float
    new_task_id: str
    accepted: bool
    selected_uav_id: Optional[str]
    displaced_task_id: Optional[str]
    old_value: float
    new_value: float
    delta_value: float
    reason: str
    candidates: Tuple[ReplacementCandidate, ...]
    queue_changes: Tuple[Tuple[str, str], ...] = ()

    def as_dict(self) -> Dict[str, object]:
        return {
            "decision_id": self.decision_id,
            "trigger_time": self.trigger_time,
            "new_task_id": self.new_task_id,
            "accepted": self.accepted,
            "selected_uav_id": self.selected_uav_id,
            "displaced_task_id": self.displaced_task_id,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "delta_value": self.delta_value,
            "reason": self.reason,
            "candidates": [candidate.as_dict() for candidate in self.candidates],
            "queue_changes": [
                {"action": action, "task_id": task_id}
                for action, task_id in self.queue_changes
            ],
        }


def evaluate_replacement(
    mission: MissionState,
    new_task: SurvivorTask,
    displaced_task_id: str,
    task_by_id: Mapping[str, SurvivorTask],
    environment,
    base: Point,
    route_config: RouteConfig,
    uav_config: UAVConfig,
    item_weights: Mapping[str, float],
    decay_rate: float,
    horizon_minutes: float,
    trigger_time: float,
) -> ReplacementCandidate:
    """Evaluate exactly one active mission and one uncompleted task replacement."""

    projection = project_mission(mission, task_by_id, trigger_time, uav_config.speed)
    old_value = remaining_objective(mission, task_by_id, trigger_time, decay_rate)
    if displaced_task_id not in projection.remaining_task_ids:
        return ReplacementCandidate(
            mission.uav_id,
            displaced_task_id,
            new_task.identifier,
            False,
            False,
            False,
            False,
            False,
            old_value,
            0.0,
            0.0,
            "task_not_uncompleted",
            projection=projection,
        )
    if projection.service_in_progress and displaced_task_id == projection.current_task_id:
        return ReplacementCandidate(
            mission.uav_id,
            displaced_task_id,
            new_task.identifier,
            False,
            False,
            False,
            False,
            False,
            old_value,
            0.0,
            0.0,
            "service_in_progress",
            projection=projection,
        )

    item_feasible = _demand_fits(new_task.demand, projection.onboard_inventory)
    revised_ids = list(projection.remaining_task_ids)
    revised_ids[revised_ids.index(displaced_task_id)] = new_task.identifier
    revised_tasks = tuple(new_task if task_id == new_task.identifier else task_by_id[task_id] for task_id in revised_ids)
    scheduled = _scheduled_demand(revised_tasks)
    scheduled_item_feasible = _demand_fits(scheduled, projection.onboard_inventory)
    item_feasible = item_feasible and scheduled_item_feasible
    parcel_feasible = sum(projection.onboard_inventory.values()) <= uav_config.parcel_capacity
    payload_feasible = _inventory_mass(projection.onboard_inventory, item_weights) <= uav_config.payload_weight_capacity + _EPSILON
    payload_feasible = payload_feasible and all(
        task.required_payload_mass <= uav_config.payload_weight_capacity + _EPSILON for task in revised_tasks
    )
    if not item_feasible:
        return ReplacementCandidate(
            mission.uav_id,
            displaced_task_id,
            new_task.identifier,
            False,
            parcel_feasible and payload_feasible,
            False,
            False,
            False,
            old_value,
            0.0,
            0.0,
            "onboard_inventory",
            tuple(revised_ids),
            projection=projection,
        )

    try:
        route = build_route_from_position(environment, projection.position, revised_tasks, base, route_config)
        schedule = build_schedule(
            environment,
            base,
            route,
            revised_tasks,
            trigger_time,
            projection.position,
            projection.onboard_inventory,
            projection.distance_consumed,
            projection.energy_consumed,
            uav_config,
            route_config,
            item_weights,
            decay_rate,
            fixed_service_task_id=projection.current_task_id if projection.service_in_progress else None,
            service_remaining=projection.service_remaining,
        )
        route_feasible = True
    except (RoutePlanningError, ValueError) as error:
        return ReplacementCandidate(
            mission.uav_id,
            displaced_task_id,
            new_task.identifier,
            item_feasible,
            parcel_feasible and payload_feasible,
            False,
            False,
            False,
            old_value,
            0.0,
            0.0,
            "route_infeasible:{}".format(error),
            tuple(revised_ids),
            projection=projection,
        )

    energy_feasible = schedule.energy_before + schedule.additional_energy + uav_config.reserve_energy <= uav_config.energy_capacity + _EPSILON
    horizon_feasible = schedule.return_time <= horizon_minutes + _EPSILON
    new_value = schedule.objective_value
    delta_value = new_value - old_value
    if not parcel_feasible or not payload_feasible:
        reason = "payload_capacity"
    elif not energy_feasible:
        reason = "energy_reserve"
    elif not horizon_feasible:
        reason = "horizon"
    elif delta_value <= _EPSILON:
        reason = "non_positive_gain"
    else:
        reason = "feasible_positive_gain"
    return ReplacementCandidate(
        mission.uav_id,
        displaced_task_id,
        new_task.identifier,
        item_feasible,
        parcel_feasible and payload_feasible,
        route_feasible,
        energy_feasible,
        horizon_feasible,
        old_value,
        new_value,
        delta_value,
        reason,
        tuple(revised_ids),
        tuple(route),
        schedule.return_time,
        schedule.additional_distance,
        schedule.additional_energy,
        schedule,
        projection,
    )


def select_recourse(
    missions: Mapping[str, MissionState],
    new_task: SurvivorTask,
    task_by_id: Mapping[str, SurvivorTask],
    environment,
    base: Point,
    route_config: RouteConfig,
    uav_config: UAVConfig,
    item_weights: Mapping[str, float],
    decay_rate: float,
    horizon_minutes: float,
    trigger_time: float,
    decision_id: int,
) -> Tuple[RecourseDecision, Optional[ReplacementCandidate]]:
    """Evaluate all one-for-one candidates and return the best positive gain."""

    candidates: List[ReplacementCandidate] = []
    for uav_id in sorted(missions):
        mission = missions[uav_id]
        projection = project_mission(mission, task_by_id, trigger_time, uav_config.speed)
        for displaced_task_id in projection.remaining_task_ids:
            candidates.append(
                evaluate_replacement(
                    mission,
                    new_task,
                    displaced_task_id,
                    task_by_id,
                    environment,
                    base,
                    route_config,
                    uav_config,
                    item_weights,
                    decay_rate,
                    horizon_minutes,
                    trigger_time,
                )
            )

    positive = [candidate for candidate in candidates if candidate.feasible and candidate.delta_value > _EPSILON]
    if positive:
        selected = max(
            positive,
            key=lambda candidate: (
                candidate.delta_value,
                candidate.new_value,
                -candidate.additional_energy,
                -candidate.additional_distance,
                candidate.uav_id,
                candidate.displaced_task_id,
            ),
        )
        decision = RecourseDecision(
            decision_id,
            trigger_time,
            new_task.identifier,
            True,
            selected.uav_id,
            selected.displaced_task_id,
            selected.old_value,
            selected.new_value,
            selected.delta_value,
            "positive_gain_selected",
            tuple(candidates),
            queue_changes=(
                ("assigned_to_mission", new_task.identifier),
                ("returned_to_queue", selected.displaced_task_id),
            ),
        )
        return decision, selected

    if not candidates:
        reason = "no_uncompleted_active_task"
    elif not any(candidate.feasible for candidate in candidates):
        reason = "no_feasible_candidate"
    else:
        reason = "no_positive_gain"
    decision = RecourseDecision(
        decision_id,
        trigger_time,
        new_task.identifier,
        False,
        None,
        None,
        max((candidate.old_value for candidate in candidates), default=0.0),
        0.0,
        max((candidate.delta_value for candidate in candidates), default=0.0),
        reason,
        tuple(candidates),
        queue_changes=(("kept_in_queue", new_task.identifier),),
    )
    return decision, None


def apply_recourse_candidate(mission: MissionState, candidate: ReplacementCandidate, trigger_time: float) -> None:
    """Commit a selected candidate without modifying the completed prefix."""

    if not candidate.feasible or candidate.schedule is None or candidate.projection is None:
        raise ValueError("only a feasible candidate can be committed")
    mission.completed_task_ids.update(candidate.projection.completed_task_ids)
    mission.history.append(
        {
            "trigger_time": trigger_time,
            "displaced_task_id": candidate.displaced_task_id,
            "new_task_id": candidate.new_task_id,
            "completed_task_ids": sorted(mission.completed_task_ids),
            "completed_position": list(candidate.projection.position),
            "previous_route_return_time": mission.schedule.return_time,
            "new_route_return_time": candidate.schedule.return_time,
        }
    )
    mission.task_ids = candidate.revised_task_ids
    mission.schedule = candidate.schedule
    mission.generation += 1
    mission.status = "active"
