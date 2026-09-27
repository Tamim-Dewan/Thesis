"""Deterministic payload and energy aware task assignment planners."""

import math
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, Mapping, Optional, Tuple

from .routing import RouteConfig, RoutePlanningError, route_task_sequence
from .scenario import Scenario
from .tasks import SurvivorTask, service_value


@dataclass(frozen=True)
class UAVConfig:
    count: int = 3
    payload_capacity: int = 4
    payload_weight_capacity: float = 2.0
    energy_capacity: float = 1000.0
    reserve_energy: float = 200.0
    speed: float = 10.0
    energy_per_meter: float = 1.0
    time_unit: str = "minute"
    distance_unit: str = "meter"
    payload_unit: str = "kilogram"
    energy_unit: str = "joule"

    @property
    def parcel_capacity(self) -> int:
        """Explicit name for the parcel count capacity."""
        return self.payload_capacity

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "UAVConfig":
        config = cls(
            count=int(values.get("count", 3)),
            payload_capacity=int(values.get("payload_capacity", 4)),
            payload_weight_capacity=float(values.get("payload_weight_capacity", 2.0)),
            energy_capacity=float(values.get("energy_capacity", 1000.0)),
            reserve_energy=float(values.get("reserve_energy", 200.0)),
            speed=float(values.get("speed", 10.0)),
            energy_per_meter=float(values.get("energy_per_meter", 1.0)),
            time_unit=str(values.get("time_unit", "minute")),
            distance_unit=str(values.get("distance_unit", "meter")),
            payload_unit=str(values.get("payload_unit", "kilogram")),
            energy_unit=str(values.get("energy_unit", "joule")),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if min(self.count,self.payload_capacity) < 1 or self.payload_weight_capacity <= 0 or self.energy_capacity <= 0 or self.reserve_energy < 0 or self.reserve_energy >= self.energy_capacity or self.speed <= 0 or self.energy_per_meter <= 0: raise ValueError("UAV configuration values must be positive and reserve must be below energy capacity")

    def as_dict(self): return asdict(self)


@dataclass(frozen=True)
class UAVAssignment:
    uav_id: str
    task_ids: Tuple[str, ...]
    route: Tuple[Tuple[float,float,float], ...]
    payload: int
    distance: float
    energy: float
    feasible: bool
    payload_weight: float = 0.0

    def as_dict(self): return asdict(self)


@dataclass(frozen=True)
class Plan:
    method: str
    assignments: Tuple[UAVAssignment, ...]
    unassigned_task_ids: Tuple[str, ...]
    objective_value: float
    metadata: Mapping[str, object]

    @property
    def served_task_ids(self) -> Tuple[str, ...]: return tuple(task_id for assignment in self.assignments if assignment.feasible for task_id in assignment.task_ids)

    def as_dict(self): return {"method":self.method,"assignments":[item.as_dict() for item in self.assignments],"unassigned_task_ids":list(self.unassigned_task_ids),"objective_value":self.objective_value,"metadata":dict(self.metadata)}


def _distance(first, second) -> float:
    return math.sqrt(sum((first[index]-second[index])**2 for index in range(3)))


def _task_payload(task: SurvivorTask) -> int: return sum(task.demand.values())


def _task_payload_weight(task: SurvivorTask) -> float: return task.required_payload_mass


def _route_distance(base, positions: Iterable[Tuple[float,float,float]]) -> float:
    current=base; distance=0.0
    for position in positions: distance+=_distance(current,position); current=position
    return distance+_distance(current,base) if current!=base else 0.0


def _ordered_tasks(
    tasks: Iterable[SurvivorTask],
    method: str,
    base: Tuple[float, float, float],
    planning_time: float,
    decay_rate: float,
) -> Tuple[SurvivorTask, ...]:
    if method=="nearest_task_first": return tuple(sorted(tasks,key=lambda task:(_distance(base,task.dropoff_waypoint),task.identifier)))
    if method=="initial_snapshot_greedy_v1":
        return tuple(sorted(
            tasks,
            key=lambda task: (
                -service_value(task.severity, task.detected_at, planning_time, decay_rate),
                -task.severity,
                task.detected_at,
                task.identifier,
            ),
        ))
    return tuple(sorted(tasks,key=lambda task:(-task.severity,task.identifier)))


def _route_snapshot(environment, base, routes, route_config):
    snapshots = {}
    for index, positions in enumerate(routes):
        if positions:
            try:
                route = route_task_sequence(environment, base, positions, route_config)
                points = route.route
            except RoutePlanningError:
                points = (base,)
        else:
            points = (base,)
        snapshots["uav_{}".format(index + 1)] = tuple(points)
    return snapshots


def _assignment_snapshot(tasks_by_uav):
    return {
        "uav_{}".format(index + 1): tuple(task_ids)
        for index, task_ids in enumerate(tasks_by_uav)
    }


def plan_tasks(
    scenario: Scenario,
    uav_config: Optional[UAVConfig] = None,
    method: str = "pgbm_heuristic_v1",
    route_config: Optional[RouteConfig] = None,
) -> Plan:
    config=uav_config or UAVConfig(count=len(scenario.scene.uav_initial_positions)); config.validate()
    if method not in ("pgbm_heuristic_v1", "initial_snapshot_greedy_v1", "nearest_task_first"):
        raise ValueError("unknown planner method: {}".format(method))
    route_config=route_config or RouteConfig()
    route_config.validate()
    planning_time = float(scenario.execution_config.start_time)
    eligible_tasks = tuple(task for task in scenario.tasks if task.is_actionable(planning_time))
    base=scenario.scene.environment.base.position
    routes=[[] for _ in range(config.count)]
    payload=[0]*config.count
    payload_weights=[0.0]*config.count
    tasks_by_uav=[[] for _ in range(config.count)]
    unassigned=[task.identifier for task in scenario.tasks if task not in eligible_tasks]
    energies=[0.0]*config.count
    decision_trace=[]
    ordered_tasks = _ordered_tasks(
        eligible_tasks,
        method,
        base,
        planning_time,
        scenario.task_config.service_value_decay_rate,
    )
    for step, task in enumerate(ordered_tasks, 1):
        demand=_task_payload(task)
        demand_weight=_task_payload_weight(task)
        priority=service_value(
            task.severity,
            task.detected_at,
            planning_time,
            scenario.task_config.service_value_decay_rate,
        )
        best=None
        candidates=[]
        for index in range(config.count):
            candidate_record={"uav_id":"uav_{}".format(index + 1),"feasible":False}
            reasons=[]
            if payload[index]+demand>config.payload_capacity:
                reasons.append("parcel_capacity")
            if payload_weights[index]+demand_weight>config.payload_weight_capacity:
                reasons.append("payload_weight_capacity")
            if reasons:
                candidate_record["reasons"]=tuple(reasons)
                candidates.append(candidate_record)
                continue
            candidate=routes[index]+[task.dropoff_waypoint]
            try:
                route=route_task_sequence(scenario.scene.environment,base,candidate,route_config)
            except RoutePlanningError as error:
                candidate_record["reasons"]=("route_infeasible",)
                candidate_record["route_error"]=str(error)
                candidates.append(candidate_record)
                continue
            distance=route.distance; energy=distance*config.energy_per_meter
            if energy + config.reserve_energy > config.energy_capacity:
                candidate_record["reasons"]=("energy_reserve",)
                candidate_record["candidate_distance"]=distance
                candidate_record["candidate_energy"]=energy
                candidates.append(candidate_record)
                continue
            previous_distance = energies[index] / config.energy_per_meter
            if method == "initial_snapshot_greedy_v1":
                score = (distance - previous_distance, distance, index)
            elif method == "pgbm_heuristic_v1":
                score = (distance + (1-task.severity)*20, distance, index)
            else:
                score = (distance, index)
            candidate_record.update({
                "feasible":True,
                "candidate_distance":distance,
                "candidate_energy":energy,
                "marginal_distance":distance-previous_distance,
                "score":score,
            })
            candidates.append(candidate_record)
            if best is None or score<best[0]: best=(score,index,distance,energy)
        if best is None:
            unassigned.append(task.identifier)
            decision_trace.append({
                "step":step,
                "task_id":task.identifier,
                "detected_at":task.detected_at,
                "severity":task.severity,
                "current_service_value":priority,
                "candidates":tuple(candidates),
                "decision":"unassigned",
                "selected_uav":None,
                "assignment_state":_assignment_snapshot(tasks_by_uav),
                "route_state":_route_snapshot(scenario.scene.environment,base,routes,route_config),
            })
            continue
        _,index,distance,energy=best
        routes[index].append(task.dropoff_waypoint)
        payload[index]+=demand
        payload_weights[index]+=demand_weight
        energies[index]=energy
        tasks_by_uav[index].append(task.identifier)
        decision_trace.append({
            "step":step,
            "task_id":task.identifier,
            "detected_at":task.detected_at,
            "severity":task.severity,
            "current_service_value":priority,
            "candidates":tuple(candidates),
            "decision":"assigned",
            "selected_uav":"uav_{}".format(index + 1),
            "selected_distance":distance,
            "selected_energy":energy,
            "assignment_state":_assignment_snapshot(tasks_by_uav),
            "route_state":_route_snapshot(scenario.scene.environment,base,routes,route_config),
        })
    assignments=[]
    for index in range(config.count):
        if routes[index]:
            try:
                route=route_task_sequence(scenario.scene.environment,base,routes[index],route_config)
                route_points=route.route; distance=route.distance; feasible=route.feasible
            except RoutePlanningError:
                route_points=(base,); distance=0.0; feasible=False
        else:
            route_points=(base,); distance=0.0; feasible=True
        assignments.append(UAVAssignment("uav_{}".format(index+1),tuple(tasks_by_uav[index]),tuple(route_points),payload[index],distance,distance*config.energy_per_meter,feasible,payload_weights[index]))
    served=sum(len(assignment.task_ids) for assignment in assignments if assignment.feasible); objective=served*100.0-sum(assignment.distance for assignment in assignments if assignment.feasible)*.1-sum(assignment.energy for assignment in assignments if assignment.feasible)*.01
    priority_rule = {
        "initial_snapshot_greedy_v1": "current_exponential_service_value_then_marginal_route_distance",
        "pgbm_heuristic_v1": "severity_then_total_route_distance_penalty",
        "nearest_task_first": "base_distance",
    }[method]
    return Plan(method,tuple(assignments),tuple(unassigned),objective,{"parcel_capacity":config.parcel_capacity,"payload_weight_capacity":config.payload_weight_capacity,"energy_capacity":config.energy_capacity,"reserve_energy":config.reserve_energy,"planning_time":planning_time,"eligible_task_count":len(eligible_tasks),"priority_rule":priority_rule,"service_value_decay_rate":scenario.task_config.service_value_decay_rate,"ordered_task_ids":tuple(task.identifier for task in ordered_tasks),"decision_trace":tuple(decision_trace),"deferred_task_ids":tuple(task.identifier for task in scenario.tasks if task not in eligible_tasks),"units":{"time":config.time_unit,"distance":config.distance_unit,"payload":config.payload_unit,"energy":config.energy_unit},"task_count":len(scenario.tasks),"routing":"grid_astar_polygon_collision_v1","route_config":route_config.as_dict()})
