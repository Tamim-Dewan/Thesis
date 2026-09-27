"""Deterministic geometric environment generation for PGBM experiments."""

import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

Point = Tuple[float, float, float]
Range = Tuple[float, float]
Polygon2D = Tuple[Tuple[float, float], ...]

SUPPORTED_OBSTACLE_KINDS = (
    "building",
    "road_block",
    "ground_rubble",
    "broken_floor",
    "elevated_debris",
)
GROUND_OBSTACLE_KINDS = frozenset({"building", "road_block", "ground_rubble"})
ELEVATED_OBSTACLE_KINDS = frozenset({"broken_floor", "elevated_debris"})
OBSTACLE_COLORS = {
    "building": "#8c564b",
    "road_block": "#7f7f7f",
    "ground_rubble": "#bcbd22",
    "broken_floor": "#ff7f0e",
    "elevated_debris": "#9467bd",
}


class EnvironmentGenerationError(RuntimeError):
    """Raised when a valid environment cannot be generated."""


@dataclass(frozen=True)
class World:
    minimum: Point
    maximum: Point
    distance_unit: str


@dataclass(frozen=True)
class ObstacleProfile:
    """Sampling rules for one typed obstacle category."""

    kind: str
    weight: float
    width: Range
    depth: Range
    height: Range
    z_range: Range

    @classmethod
    def from_mapping(cls, kind: str, values: Mapping[str, Any]) -> "ObstacleProfile":
        if kind not in SUPPORTED_OBSTACLE_KINDS:
            raise ValueError("unknown obstacle kind: {}".format(kind))
        return cls(
            kind=kind,
            weight=float(values.get("weight", 1.0)),
            width=_range(values.get("width", [5.0, 20.0]), "{} width".format(kind)),
            depth=_range(values.get("depth", [5.0, 20.0]), "{} depth".format(kind)),
            height=_range(values.get("height", [1.0, 10.0]), "{} height".format(kind)),
            z_range=_range(values.get("z_range", [0.0, 0.0]), "{} z_range".format(kind)),
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "weight": self.weight,
            "width": list(self.width),
            "depth": list(self.depth),
            "height": list(self.height),
            "z_range": list(self.z_range),
        }


def _default_obstacle_profiles() -> Tuple[ObstacleProfile, ...]:
    return (
        ObstacleProfile("building", 0.35, (12.0, 25.0), (12.0, 25.0), (15.0, 40.0), (0.0, 0.0)),
        ObstacleProfile("road_block", 0.15, (10.0, 30.0), (4.0, 10.0), (1.0, 4.0), (0.0, 0.0)),
        ObstacleProfile("ground_rubble", 0.25, (5.0, 20.0), (5.0, 20.0), (1.0, 8.0), (0.0, 0.0)),
        ObstacleProfile("broken_floor", 0.15, (8.0, 20.0), (8.0, 20.0), (1.0, 5.0), (0.0, 35.0)),
        ObstacleProfile("elevated_debris", 0.10, (3.0, 12.0), (3.0, 12.0), (1.0, 8.0), (3.0, 35.0)),
    )


@dataclass(frozen=True)
class Obstacle:
    identifier: str
    kind: str
    minimum: Point
    width: float
    depth: float
    height: float
    parent_structure_id: Optional[str] = None
    road_segment_id: Optional[str] = None
    source_ref: Optional[str] = None
    footprint: Optional[Polygon2D] = None
    rotation_degrees: float = 0.0
    # Per-footprint-vertex fractions of ``height`` used only for visual meshes.
    # Collision remains the conservative enclosing volume given by ``maximum``.
    visual_top_profile: Tuple[float, ...] = ()
    # Named visual provenance for generated post-earthquake target geometry.
    # This is a modelling rule, not a claim that the geometry was surveyed at
    # the mapped site.
    damage_template_id: Optional[str] = None

    @property
    def maximum(self) -> Point:
        if self.footprint:
            return (
                max(point[0] for point in self.footprint),
                max(point[1] for point in self.footprint),
                self.minimum[2] + self.height,
            )
        return (
            self.minimum[0] + self.width,
            self.minimum[1] + self.depth,
            self.minimum[2] + self.height,
        )


@dataclass(frozen=True)
class Base:
    identifier: str
    position: Point


@dataclass(frozen=True)
class EnvironmentConfig:
    world_bounds: Tuple[float, float, float, float, float, float]
    ground_level: float = 0.0
    distance_unit: str = "meter"
    obstacle_count: Tuple[int, int] = (0, 4)
    obstacle_profiles: Tuple[ObstacleProfile, ...] = field(default_factory=_default_obstacle_profiles)
    base_identifier: str = "base_1"
    max_generation_attempts: int = 1000
    base_seed: int = 0

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "EnvironmentConfig":
        bounds = _fixed_float_tuple(values.get("world_bounds"), 6, "world_bounds")
        count = _fixed_int_tuple(values.get("obstacle_count", [0, 4]), 2, "obstacle_count")
        profiles = _profiles_from_mapping(values.get("obstacle_profiles"))
        config = cls(
            world_bounds=bounds,  # type: ignore[arg-type]
            ground_level=float(values.get("ground_level", 0.0)),
            distance_unit=str(values.get("distance_unit", "meter")),
            obstacle_count=count,  # type: ignore[arg-type]
            obstacle_profiles=profiles,
            base_identifier=str(values.get("base_identifier", "base_1")),
            max_generation_attempts=int(values.get("max_generation_attempts", 1000)),
            base_seed=int(values.get("base_seed", 0)),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if len(self.world_bounds) != 6:
            raise ValueError("world_bounds must contain six values")
        if any(not math.isfinite(value) for value in self.world_bounds):
            raise ValueError("world_bounds must contain finite values")
        if any(self.world_bounds[index] >= self.world_bounds[index + 3] for index in range(3)):
            raise ValueError("world bounds must have positive extent on every axis")
        if self.ground_level != 0.0 or self.world_bounds[2] != 0.0:
            raise ValueError("ground_level and the world minimum z must be 0")
        if not self.distance_unit:
            raise ValueError("distance_unit must not be empty")
        if len(self.obstacle_count) != 2:
            raise ValueError("obstacle_count must contain a minimum and maximum")
        if self.obstacle_count[0] < 0 or self.obstacle_count[0] > self.obstacle_count[1]:
            raise ValueError("obstacle_count must be a non-negative increasing pair")
        if not self.obstacle_profiles:
            raise ValueError("obstacle_profiles must contain at least one profile")

        extents = (
            self.world_bounds[3] - self.world_bounds[0],
            self.world_bounds[4] - self.world_bounds[1],
            self.world_bounds[5] - self.world_bounds[2],
        )
        total_weight = 0.0
        for profile in self.obstacle_profiles:
            self._validate_profile(profile, extents)
            total_weight += profile.weight
        if total_weight <= 0.0:
            raise ValueError("obstacle profile weights must contain a positive total")

        if not self.base_identifier:
            raise ValueError("base_identifier must not be empty")
        if self.max_generation_attempts < 1:
            raise ValueError("max_generation_attempts must be positive")
        if self.base_seed < 0:
            raise ValueError("base_seed must be non-negative")

    def _validate_profile(self, profile: ObstacleProfile, extents: Tuple[float, float, float]) -> None:
        if profile.kind not in SUPPORTED_OBSTACLE_KINDS:
            raise ValueError("unknown obstacle kind: {}".format(profile.kind))
        if not math.isfinite(profile.weight) or profile.weight < 0.0:
            raise ValueError("{} weight must be non-negative and finite".format(profile.kind))
        for name, values in (
            ("width", profile.width),
            ("depth", profile.depth),
            ("height", profile.height),
        ):
            _validate_positive_range(values, "{} {}".format(profile.kind, name))
        _validate_non_negative_range(profile.z_range, "{} z_range".format(profile.kind))
        if profile.width[1] > extents[0]:
            raise ValueError("maximum {} width exceeds world extent".format(profile.kind))
        if profile.depth[1] > extents[1]:
            raise ValueError("maximum {} depth exceeds world extent".format(profile.kind))
        if profile.z_range[1] + profile.height[1] > extents[2]:
            raise ValueError("maximum {} height and z position exceed world extent".format(profile.kind))
        if profile.kind in GROUND_OBSTACLE_KINDS and profile.z_range != (0.0, 0.0):
            raise ValueError("{} must start at ground level z = 0".format(profile.kind))
        if profile.kind == "elevated_debris" and profile.z_range[0] <= self.ground_level:
            raise ValueError("elevated_debris must start above ground level")

    def profile_by_kind(self) -> Dict[str, ObstacleProfile]:
        return {profile.kind: profile for profile in self.obstacle_profiles}

    def as_dict(self) -> Dict[str, Any]:
        return {
            "world_bounds": list(self.world_bounds),
            "ground_level": self.ground_level,
            "distance_unit": self.distance_unit,
            "obstacle_count": list(self.obstacle_count),
            "obstacle_profiles": {
                profile.kind: profile.as_dict() for profile in self.obstacle_profiles
            },
            "base_identifier": self.base_identifier,
            "max_generation_attempts": self.max_generation_attempts,
            "base_seed": self.base_seed,
        }


@dataclass(frozen=True)
class Environment:
    world: World
    obstacles: Tuple[Obstacle, ...]
    base: Base
    seed: int
    effective_config: Dict[str, Any]
    generation_metadata: Dict[str, Any]


def _range(values: Any, name: str) -> Range:
    try:
        result = (float(values[0]), float(values[1]))
    except (IndexError, KeyError, TypeError, ValueError) as error:
        raise ValueError("{} must contain two numeric values".format(name)) from error
    if any(not math.isfinite(value) for value in result):
        raise ValueError("{} must contain finite values".format(name))
    return result


def _fixed_float_tuple(values: Any, length: int, name: str) -> Tuple[float, ...]:
    try:
        result = tuple(float(value) for value in values)
    except (TypeError, ValueError) as error:
        raise ValueError("{} must contain numeric values".format(name)) from error
    if len(result) != length:
        raise ValueError("{} must contain {} values".format(name, length))
    if any(not math.isfinite(value) for value in result):
        raise ValueError("{} must contain finite values".format(name))
    return result


def _fixed_int_tuple(values: Any, length: int, name: str) -> Tuple[int, ...]:
    try:
        result = tuple(int(value) for value in values)
    except (TypeError, ValueError) as error:
        raise ValueError("{} must contain integer values".format(name)) from error
    if len(result) != length:
        raise ValueError("{} must contain {} values".format(name, length))
    return result


def _profiles_from_mapping(values: Any) -> Tuple[ObstacleProfile, ...]:
    if values is None:
        return _default_obstacle_profiles()
    if isinstance(values, Mapping):
        entries = values.items()
    elif isinstance(values, (list, tuple)):
        if any(not isinstance(entry, Mapping) for entry in values):
            raise ValueError("each obstacle profile must be a mapping")
        entries = ((entry.get("kind"), entry) for entry in values)
    else:
        raise ValueError("obstacle_profiles must be a mapping or list")

    profiles = []
    for kind, profile_values in entries:
        if not isinstance(kind, str):
            raise ValueError("each obstacle profile must have a string kind")
        if not isinstance(profile_values, Mapping):
            raise ValueError("obstacle profile {} must be a mapping".format(kind))
        profiles.append(ObstacleProfile.from_mapping(kind, profile_values))
    return tuple(profiles)


def _validate_positive_range(values: Range, name: str) -> None:
    if any(not math.isfinite(value) for value in values) or values[0] <= 0.0 or values[0] > values[1]:
        raise ValueError("{} must contain positive increasing values".format(name))


def _validate_non_negative_range(values: Range, name: str) -> None:
    if any(not math.isfinite(value) for value in values) or values[0] < 0.0 or values[0] > values[1]:
        raise ValueError("{} must contain non-negative increasing values".format(name))


def _point(values: Any) -> Point:
    result = _fixed_float_tuple(values, 3, "point")
    return result  # type: ignore[return-value]


def _world(config: EnvironmentConfig) -> World:
    return World(
        minimum=_point(config.world_bounds[:3]),
        maximum=_point(config.world_bounds[3:]),
        distance_unit=config.distance_unit,
    )


def _choose_profile(config: EnvironmentConfig, rng: random.Random) -> ObstacleProfile:
    profiles = tuple(profile for profile in config.obstacle_profiles if profile.weight > 0.0)
    total_weight = sum(profile.weight for profile in profiles)
    target = rng.random() * total_weight
    cumulative = 0.0
    for profile in profiles:
        cumulative += profile.weight
        if target < cumulative:
            return profile
    return profiles[-1]


def _sample_obstacle(config: EnvironmentConfig, rng: random.Random, index: int) -> Obstacle:
    world = _world(config)
    profile = _choose_profile(config, rng)
    width = rng.uniform(*profile.width)
    depth = rng.uniform(*profile.depth)
    height = rng.uniform(*profile.height)
    z_min = rng.uniform(*profile.z_range)
    minimum = (
        rng.uniform(world.minimum[0], world.maximum[0] - width),
        rng.uniform(world.minimum[1], world.maximum[1] - depth),
        z_min,
    )
    return Obstacle(
        identifier="obstacle_{}".format(index + 1),
        kind=profile.kind,
        minimum=minimum,
        width=width,
        depth=depth,
        height=height,
    )


def _obstacle_cluster_bounds(obstacles: Tuple[Obstacle, ...]) -> Optional[Tuple[Point, Point]]:
    if not obstacles:
        return None
    minimum = tuple(min(obstacle.minimum[index] for obstacle in obstacles) for index in range(3))
    maximum = tuple(max(obstacle.maximum[index] for obstacle in obstacles) for index in range(3))
    return minimum, maximum  # type: ignore[return-value]


def is_valid_point(environment: Environment, point: Point) -> bool:
    """Return whether a point is inside the world and outside all obstacles."""
    point = _point(point)
    world = environment.world
    if any(point[index] < world.minimum[index] or point[index] > world.maximum[index] for index in range(3)):
        return False
    for obstacle in environment.obstacles:
        inside_xy = (
            _point_in_polygon(point[0], point[1], obstacle.footprint)
            if obstacle.footprint else
            obstacle.minimum[0] <= point[0] <= obstacle.maximum[0]
            and obstacle.minimum[1] <= point[1] <= obstacle.maximum[1]
        )
        if inside_xy and obstacle.minimum[2] <= point[2] <= obstacle.maximum[2]:
            return False
    return True


def _base_is_usable(environment: Environment, point: Point) -> bool:
    if point[2] != environment.world.minimum[2] or not is_valid_point(environment, point):
        return False
    cluster = _obstacle_cluster_bounds(environment.obstacles)
    if cluster is None:
        return True
    minimum, maximum = cluster
    return (
        point[0] < minimum[0]
        or point[0] > maximum[0]
        or point[1] < minimum[1]
        or point[1] > maximum[1]
    )


def _point_in_polygon(x: float, y: float, polygon: Optional[Polygon2D]) -> bool:
    if not polygon or len(polygon) < 3:
        return False
    inside = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        crosses = (y1 > y) != (y2 > y)
        if crosses and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1:
            inside = not inside
        previous = current
    return inside


def generate_environment(config: EnvironmentConfig, seed: Optional[int] = None) -> Environment:
    """Generate one immutable, deterministic environment."""
    config.validate()
    actual_seed = config.base_seed if seed is None else int(seed)
    if actual_seed < 0:
        raise ValueError("seed must be non-negative")
    rng = random.Random(actual_seed)
    world = _world(config)
    count = rng.randint(config.obstacle_count[0], config.obstacle_count[1])
    obstacles = tuple(_sample_obstacle(config, rng, index) for index in range(count))
    provisional = Environment(
        world,
        obstacles,
        Base(config.base_identifier, (world.minimum[0], world.minimum[1], config.ground_level)),
        actual_seed,
        config.as_dict(),
        {},
    )
    base = None
    base_sampling_attempts = 0
    for base_sampling_attempts in range(1, config.max_generation_attempts + 1):
        point = (
            rng.uniform(world.minimum[0], world.maximum[0]),
            rng.uniform(world.minimum[1], world.maximum[1]),
            config.ground_level,
        )
        if _base_is_usable(provisional, point):
            base = Base(config.base_identifier, point)
            break
    if base is None:
        raise EnvironmentGenerationError(
            "no valid ground base position exists for this environment configuration"
        )
    return Environment(
        world=world,
        obstacles=obstacles,
        base=base,
        seed=actual_seed,
        effective_config=config.as_dict(),
        generation_metadata={
            "obstacle_count": count,
            "obstacle_kinds": [obstacle.kind for obstacle in obstacles],
            "base_sampling_attempts": base_sampling_attempts,
            "placement_adjustments": [],
        },
    )


def _cuboid_trace(obstacle: Obstacle):
    import plotly.graph_objects as go

    x0, y0, z0 = obstacle.minimum
    x1, y1, z1 = obstacle.maximum
    vertices = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]
    faces = (
        (0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6),
        (0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2),
        (2, 6, 7), (2, 7, 3), (4, 0, 3), (4, 3, 7),
    )
    label = "{} ({})".format(obstacle.kind, obstacle.identifier)
    return go.Mesh3d(
        x=[vertex[0] for vertex in vertices],
        y=[vertex[1] for vertex in vertices],
        z=[vertex[2] for vertex in vertices],
        i=[face[0] for face in faces],
        j=[face[1] for face in faces],
        k=[face[2] for face in faces],
        name=label,
        opacity=0.62,
        color=OBSTACLE_COLORS[obstacle.kind],
        hovertext=label,
        hoverinfo="text",
    )


def _ground_trace(world: World):
    import plotly.graph_objects as go

    x0, y0, z0 = world.minimum
    x1, y1, _ = world.maximum
    return go.Mesh3d(
        x=[x0, x1, x1, x0],
        y=[y0, y0, y1, y1],
        z=[z0, z0, z0, z0],
        i=[0, 0],
        j=[1, 2],
        k=[2, 3],
        name="ground plane",
        opacity=0.12,
        color="#bdbdbd",
        hoverinfo="skip",
        showlegend=False,
    )


def plot_environment(environment: Environment):
    """Return an interactive Plotly figure for an environment."""
    import plotly.graph_objects as go

    world = environment.world
    figure = go.Figure()
    figure.add_trace(_ground_trace(world))
    for obstacle in environment.obstacles:
        figure.add_trace(_cuboid_trace(obstacle))
    figure.add_trace(go.Scatter3d(
        x=[environment.base.position[0]],
        y=[environment.base.position[1]],
        z=[environment.base.position[2]],
        mode="markers+text",
        marker={"size": 8, "color": "#1f77b4", "symbol": "diamond"},
        text=[environment.base.identifier],
        textposition="top center",
        name=environment.base.identifier,
        hovertext=["base at ground level"],
        hoverinfo="text",
    ))
    figure.update_layout(
        title="PGBM simulation environment",
        scene={
            "xaxis": {"title": "x", "range": [world.minimum[0], world.maximum[0]]},
            "yaxis": {"title": "y", "range": [world.minimum[1], world.maximum[1]]},
            "zaxis": {"title": "z", "range": [world.minimum[2], world.maximum[2]]},
            "aspectmode": "data",
        },
        showlegend=True,
    )
    return figure
