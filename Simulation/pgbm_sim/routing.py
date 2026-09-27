"""Deterministic collision-aware UAV routing for disaster scenes.

The first planner used Euclidean legs, which was useful for the assignment
smoke test but could let a UAV fly through a mapped building.  This module
keeps the routing deliberately lightweight: it uses a visibility grid in the
horizontal plane and explicit vertical clearance checks.  It is therefore
reproducible and dependency-free while still respecting the polygon obstacle
geometry used by the scene model.
"""

import heapq
import math
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .environment import Environment, Obstacle, Point, Polygon2D, _point_in_polygon


_ROUTE_CACHE = {}


class RoutePlanningError(ValueError):
    """Raised when a collision-free route cannot be found."""


@dataclass(frozen=True)
class RouteConfig:
    """Routing resolution and flight-clearance policy."""

    grid_resolution: float = 5.0
    cruise_altitude: float = 12.0
    altitude_margin: float = 1.0
    max_expanded_nodes: int = 20000

    @classmethod
    def from_mapping(cls, values: Dict[str, object]) -> "RouteConfig":
        config = cls(
            grid_resolution=float(values.get("grid_resolution", 5.0)),
            cruise_altitude=float(values.get("cruise_altitude", 12.0)),
            altitude_margin=float(values.get("altitude_margin", 1.0)),
            max_expanded_nodes=int(values.get("max_expanded_nodes", 20000)),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.grid_resolution <= 0.0:
            raise RoutePlanningError("grid_resolution must be positive")
        if self.cruise_altitude < 0.0 or self.altitude_margin < 0.0:
            raise RoutePlanningError("flight altitudes and margin must be non-negative")
        if self.max_expanded_nodes < 1:
            raise RoutePlanningError("max_expanded_nodes must be positive")

    def as_dict(self) -> Dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class RouteResult:
    """A route polyline and the associated feasibility information."""

    route: Tuple[Point, ...]
    distance: float
    feasible: bool
    expanded_nodes: int = 0
    cruise_altitude: float = 0.0

    def as_dict(self) -> Dict[str, object]:
        return {
            "route": [list(point) for point in self.route],
            "distance": self.distance,
            "feasible": self.feasible,
            "expanded_nodes": self.expanded_nodes,
            "cruise_altitude": self.cruise_altitude,
        }


def _distance(first: Point, second: Point) -> float:
    return math.sqrt(sum((first[index] - second[index]) ** 2 for index in range(3)))


def _polyline_distance(route: Iterable[Point]) -> float:
    points = tuple(route)
    return sum(_distance(first, second) for first, second in zip(points, points[1:]))


def _point_on_segment(point: Tuple[float, float], first: Tuple[float, float], second: Tuple[float, float]) -> bool:
    cross = (point[0] - first[0]) * (second[1] - first[1]) - (point[1] - first[1]) * (second[0] - first[0])
    if abs(cross) > 1e-9:
        return False
    return (
        min(first[0], second[0]) - 1e-9 <= point[0] <= max(first[0], second[0]) + 1e-9
        and min(first[1], second[1]) - 1e-9 <= point[1] <= max(first[1], second[1]) + 1e-9
    )


def _orientation(first: Tuple[float, float], second: Tuple[float, float], third: Tuple[float, float]) -> float:
    return (second[0] - first[0]) * (third[1] - first[1]) - (second[1] - first[1]) * (third[0] - first[0])


def _segments_intersect(
    first_start: Tuple[float, float],
    first_end: Tuple[float, float],
    second_start: Tuple[float, float],
    second_end: Tuple[float, float],
) -> bool:
    values = (
        _orientation(first_start, first_end, second_start),
        _orientation(first_start, first_end, second_end),
        _orientation(second_start, second_end, first_start),
        _orientation(second_start, second_end, first_end),
    )
    if values[0] == 0.0 and _point_on_segment(second_start, first_start, first_end):
        return True
    if values[1] == 0.0 and _point_on_segment(second_end, first_start, first_end):
        return True
    if values[2] == 0.0 and _point_on_segment(first_start, second_start, second_end):
        return True
    if values[3] == 0.0 and _point_on_segment(first_end, second_start, second_end):
        return True
    return ((values[0] > 0.0) != (values[1] > 0.0)) and ((values[2] > 0.0) != (values[3] > 0.0))


def _xy_inside(obstacle: Obstacle, x: float, y: float) -> bool:
    if x < obstacle.minimum[0] or x > obstacle.maximum[0] or y < obstacle.minimum[1] or y > obstacle.maximum[1]:
        return False
    if obstacle.footprint:
        return _point_in_polygon(x, y, obstacle.footprint) or any(
            _point_on_segment((x, y), obstacle.footprint[index - 1], obstacle.footprint[index])
            for index in range(len(obstacle.footprint))
        )
    return obstacle.minimum[0] <= x <= obstacle.maximum[0] and obstacle.minimum[1] <= y <= obstacle.maximum[1]


def _active_at(obstacle: Obstacle, z: float) -> bool:
    # A UAV may finish on a building roof at z == maximum z.  The open upper
    # bound also keeps a route at an exact roof height from being rejected.
    return obstacle.minimum[2] <= z < obstacle.maximum[2]


def _point_free(environment: Environment, x: float, y: float, z: float) -> bool:
    world = environment.world
    if not (world.minimum[0] <= x <= world.maximum[0] and world.minimum[1] <= y <= world.maximum[1]):
        return False
    if not (world.minimum[2] <= z <= world.maximum[2]):
        return False
    return not any(_active_at(obstacle, z) and _xy_inside(obstacle, x, y) for obstacle in environment.obstacles)


def _horizontal_segment_free(environment: Environment, first: Tuple[float, float], second: Tuple[float, float], z: float) -> bool:
    segment_min_x, segment_max_x = sorted((first[0], second[0]))
    segment_min_y, segment_max_y = sorted((first[1], second[1]))
    for obstacle in environment.obstacles:
        if not _active_at(obstacle, z):
            continue
        if segment_max_x < obstacle.minimum[0] or segment_min_x > obstacle.maximum[0] or segment_max_y < obstacle.minimum[1] or segment_min_y > obstacle.maximum[1]:
            continue
        if _xy_inside(obstacle, first[0], first[1]) or _xy_inside(obstacle, second[0], second[1]):
            return False
        if not obstacle.footprint:
            x0, y0 = obstacle.minimum[0], obstacle.minimum[1]
            x1, y1 = obstacle.maximum[0], obstacle.maximum[1]
            if _segments_intersect(first, second, (x0, y0), (x1, y0)) or _segments_intersect(first, second, (x1, y0), (x1, y1)) or _segments_intersect(first, second, (x1, y1), (x0, y1)) or _segments_intersect(first, second, (x0, y1), (x0, y0)):
                return False
            continue
        polygon = obstacle.footprint
        for index in range(len(polygon)):
            if _segments_intersect(first, second, polygon[index - 1], polygon[index]):
                return False
    return True


def _vertical_segment_free(environment: Environment, x: float, y: float, first_z: float, second_z: float) -> bool:
    lower, upper = sorted((first_z, second_z))
    for obstacle in environment.obstacles:
        if not _xy_inside(obstacle, x, y):
            continue
        if max(lower, obstacle.minimum[2]) < min(upper, obstacle.maximum[2]):
            return False
    return True


def _axis_values(lower: float, upper: float, resolution: float, extras: Iterable[float]) -> Tuple[float, ...]:
    values = [lower]
    current = lower + resolution
    while current < upper - 1e-9:
        values.append(current)
        current += resolution
    values.append(upper)
    values.extend(value for value in extras if lower <= value <= upper)
    return tuple(sorted(set(round(value, 8) for value in values)))


def _grid_route(
    environment: Environment,
    first: Tuple[float, float],
    second: Tuple[float, float],
    z: float,
    config: RouteConfig,
) -> Tuple[Tuple[Tuple[float, float], ...], int]:
    if first == second:
        if _point_free(environment, first[0], first[1], z):
            return (first,), 0
        raise RoutePlanningError("horizontal route endpoint is blocked")
    if _horizontal_segment_free(environment, first, second, z):
        return (first, second), 0

    world = environment.world
    x_values = _axis_values(world.minimum[0], world.maximum[0], config.grid_resolution, (first[0], second[0]))
    y_values = _axis_values(world.minimum[1], world.maximum[1], config.grid_resolution, (first[1], second[1]))
    start = (first[0], first[1])
    goal = (second[0], second[1])
    x_index = {value: index for index, value in enumerate(x_values)}
    y_index = {value: index for index, value in enumerate(y_values)}
    start_key = (x_index[round(start[0], 8)], y_index[round(start[1], 8)])
    goal_key = (x_index[round(goal[0], 8)], y_index[round(goal[1], 8)])

    def coordinate(key: Tuple[int, int]) -> Tuple[float, float]:
        return x_values[key[0]], y_values[key[1]]

    def heuristic(key: Tuple[int, int]) -> float:
        point = coordinate(key)
        return math.hypot(point[0] - goal[0], point[1] - goal[1])

    open_set: List[Tuple[float, Tuple[int, int]]] = [(heuristic(start_key), start_key)]
    came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
    g_score: Dict[Tuple[int, int], float] = {start_key: 0.0}
    closed: Set[Tuple[int, int]] = set()
    expanded = 0
    while open_set:
        _, current = heapq.heappop(open_set)
        if current in closed:
            continue
        closed.add(current)
        expanded += 1
        if expanded > config.max_expanded_nodes:
            raise RoutePlanningError("route search exceeded max_expanded_nodes")
        if current == goal_key:
            path = [current]
            while path[-1] != start_key:
                path.append(came_from[path[-1]])
            path.reverse()
            return tuple(coordinate(key) for key in path), expanded
        for x_step in (-1, 0, 1):
            for y_step in (-1, 0, 1):
                if x_step == 0 and y_step == 0:
                    continue
                neighbour = (current[0] + x_step, current[1] + y_step)
                if not (0 <= neighbour[0] < len(x_values) and 0 <= neighbour[1] < len(y_values)):
                    continue
                if neighbour in closed:
                    continue
                neighbour_point = coordinate(neighbour)
                is_goal = neighbour == goal_key
                if not is_goal and not _point_free(environment, neighbour_point[0], neighbour_point[1], z):
                    continue
                current_point = coordinate(current)
                if not _horizontal_segment_free(environment, current_point, neighbour_point, z):
                    continue
                step = math.hypot(neighbour_point[0] - current_point[0], neighbour_point[1] - current_point[1])
                candidate = g_score[current] + step
                if candidate < g_score.get(neighbour, float("inf")):
                    came_from[neighbour] = current
                    g_score[neighbour] = candidate
                    heapq.heappush(open_set, (candidate + heuristic(neighbour), neighbour))
    raise RoutePlanningError("no collision-free horizontal route exists")


def _candidate_altitudes(environment: Environment, first: Point, second: Point, config: RouteConfig) -> Tuple[float, ...]:
    world_top = environment.world.maximum[2]
    preferred = min(world_top, max(config.cruise_altitude, first[2], second[2]))
    highest = max((obstacle.maximum[2] for obstacle in environment.obstacles), default=0.0)
    fallback = min(world_top, highest + config.altitude_margin)
    values = (preferred, fallback, world_top)
    return tuple(dict.fromkeys(round(value, 8) for value in values if value >= max(first[2], second[2])))


def route_between(environment: Environment, first: Point, second: Point, config: Optional[RouteConfig] = None) -> RouteResult:
    config = config or RouteConfig()
    config.validate()
    cache_key=(id(environment),first,second,config)
    cached=_ROUTE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    last_error: Optional[Exception] = None
    for altitude in _candidate_altitudes(environment, first, second, config):
        if not _vertical_segment_free(environment, first[0], first[1], first[2], altitude):
            continue
        if not _vertical_segment_free(environment, second[0], second[1], second[2], altitude):
            continue
        try:
            horizontal, expanded = _grid_route(environment, (first[0], first[1]), (second[0], second[1]), altitude, config)
        except RoutePlanningError as error:
            last_error = error
            continue
        route: List[Point] = []
        start_cruise = (first[0], first[1], altitude)
        end_cruise = (second[0], second[1], altitude)
        route.append(first)
        if first != start_cruise:
            route.append(start_cruise)
        route.extend((x, y, altitude) for x, y in horizontal[1:])
        if route[-1] != end_cruise:
            route.append(end_cruise)
        if end_cruise != second:
            route.append(second)
        result=RouteResult(tuple(route), _polyline_distance(route), True, expanded, altitude)
        _ROUTE_CACHE[cache_key]=result
        return result
    raise RoutePlanningError("no collision-free 3D route exists: {}".format(last_error or "altitude is unavailable"))


def route_task_sequence(environment: Environment, base: Point, task_positions: Iterable[Point], config: Optional[RouteConfig] = None) -> RouteResult:
    config = config or RouteConfig()
    config.validate()
    positions = tuple(task_positions)
    route: List[Point] = [base]
    total_expanded = 0
    cruise_altitudes = []
    current = base
    for target in positions:
        leg = route_between(environment, current, target, config)
        route.extend(leg.route[1:])
        total_expanded += leg.expanded_nodes
        cruise_altitudes.append(leg.cruise_altitude)
        current = target
    if positions:
        return_leg = route_between(environment, current, base, config)
        route.extend(return_leg.route[1:])
        total_expanded += return_leg.expanded_nodes
        cruise_altitudes.append(return_leg.cruise_altitude)
    return RouteResult(tuple(route), _polyline_distance(route), True, total_expanded, max(cruise_altitudes, default=0.0))
