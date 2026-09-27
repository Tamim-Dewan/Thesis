"""Deterministic synthetic survivor assistance task generation."""

import math
import random
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

from .disaster_scene import DisasterScene
from .environment import Point, Polygon2D, _point_in_polygon


class TaskGenerationError(ValueError):
    """Raised when the requested task set cannot be generated."""


TASK_DAMAGE_STATES = ("minor", "major", "destroyed")


@dataclass(frozen=True)
class TaskConfig:
    task_count: int = 6
    item_types: Tuple[str, ...] = ("food", "water", "medical")
    item_weights: Mapping[str, float] = field(default_factory=lambda: {"food": 0.25, "water": 0.5, "medical": 0.5})
    detection_time_range: Tuple[float, float] = (0.0, 30.0)
    severity_range: Tuple[float, float] = (0.35, 1.0)
    item_presence_model: str = "uniform_non_empty_subset"
    max_task_parcels: int = 4
    max_task_payload_mass: float = 2.0
    survivor_offset_range: Tuple[float, float] = (1.0, 5.0)
    dropoff_height_range: Tuple[float, float] = (2.0, 4.0)
    time_unit: str = "minute"
    distance_unit: str = "meter"
    payload_unit: str = "kilogram"
    energy_unit: str = "joule"
    service_value_model: str = "common_exponential"
    service_value_decay_rate: float = 0.011997
    service_duration_base: float = 2.0
    service_duration_per_parcel: float = 0.5
    service_duration_per_severity: float = 1.0
    seed: int = 0

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "TaskConfig":
        config=cls(
            task_count=int(values.get("task_count",6)),
            item_types=tuple(str(item) for item in values.get("item_types",("food","water","medical"))),
            item_weights={str(key): float(value) for key,value in values.get("item_weights", {"food": 0.25, "water": 0.5, "medical": 0.5}).items()},
            detection_time_range=tuple(float(item) for item in values.get("detection_time_range",(0.0,30.0))),
            severity_range=tuple(float(item) for item in values.get("severity_range",(0.35,1.0))),
            item_presence_model=str(values.get("item_presence_model", "uniform_non_empty_subset")),
            max_task_parcels=int(values.get("max_task_parcels", 4)),
            max_task_payload_mass=float(values.get("max_task_payload_mass", 2.0)),
            survivor_offset_range=tuple(float(item) for item in values.get("survivor_offset_range",(1.0,5.0))),
            dropoff_height_range=tuple(float(item) for item in values.get("dropoff_height_range",(2.0,4.0))),
            time_unit=str(values.get("time_unit", "minute")),
            distance_unit=str(values.get("distance_unit", "meter")),
            payload_unit=str(values.get("payload_unit", "kilogram")),
            energy_unit=str(values.get("energy_unit", "joule")),
            service_value_model=str(values.get("service_value_model", "common_exponential")),
            service_value_decay_rate=float(values.get("service_value_decay_rate", 0.011997)),
            service_duration_base=float(values.get("service_duration_base", 2.0)),
            service_duration_per_parcel=float(values.get("service_duration_per_parcel", 0.5)),
            service_duration_per_severity=float(values.get("service_duration_per_severity", 1.0)),
            seed=int(values.get("seed",0)),
        )
        config.validate(); return config

    def validate(self) -> None:
        if self.task_count<1: raise TaskGenerationError("task_count must be positive")
        if set(self.item_types) != {"food", "water", "medical"}: raise TaskGenerationError("item_types must contain food, water, and medical")
        if set(self.item_weights) != set(self.item_types) or any(weight <= 0 for weight in self.item_weights.values()): raise TaskGenerationError("item_weights must define one positive weight for every item type")
        for name, values in (("detection_time_range",self.detection_time_range),("severity_range",self.severity_range),("survivor_offset_range",self.survivor_offset_range)):
            if len(values)!=2 or values[0]<0 or values[0]>values[1]: raise TaskGenerationError("{} must be an increasing non negative range".format(name))
        if len(self.dropoff_height_range)!=2 or self.dropoff_height_range[0] <= 0 or self.dropoff_height_range[0] > self.dropoff_height_range[1]:
            raise TaskGenerationError("dropoff_height_range must be a positive increasing range")
        if self.item_presence_model != "uniform_non_empty_subset": raise TaskGenerationError("unsupported item presence model")
        if self.max_task_parcels < 1 or len(self.item_types) > self.max_task_parcels: raise TaskGenerationError("max_task_parcels must fit one of every configured item")
        if self.max_task_payload_mass <= 0 or sum(self.item_weights.values()) > self.max_task_payload_mass + 1e-9: raise TaskGenerationError("configured item weights exceed max_task_payload_mass")
        if not all((self.time_unit, self.distance_unit, self.payload_unit, self.energy_unit)): raise TaskGenerationError("data units must not be empty")
        if self.service_value_model != "common_exponential" or self.service_value_decay_rate <= 0: raise TaskGenerationError("unsupported service value configuration")
        if self.service_duration_base <= 0 or self.service_duration_per_parcel < 0 or self.service_duration_per_severity < 0: raise TaskGenerationError("service duration parameters are invalid")
        if self.seed<0: raise TaskGenerationError("seed must be non negative")

    def as_dict(self) -> Dict[str, Any]: return asdict(self)


@dataclass(frozen=True)
class SurvivorTask:
    identifier: str
    task_type: str
    survivor_position: Point
    dropoff_waypoint: Point
    detected_at: float
    severity: float
    demand: Mapping[str, int]
    required_payload_mass: float
    service_duration: float
    service_value_at_detection: float
    status: str = "pending"

    @property
    def position(self) -> Point:
        """Backward compatible route position, now explicitly the drop off waypoint."""
        return self.dropoff_waypoint

    @property
    def urgency(self) -> float:
        """Backward compatible alias for older callers; not serialized."""
        return self.severity

    def is_actionable(self, time: float) -> bool:
        return self.status=="pending" and time>=self.detected_at

    def as_dict(self) -> Dict[str, Any]:
        values=asdict(self)
        values["survivor_position"]=list(self.survivor_position)
        values["dropoff_waypoint"]=list(self.dropoff_waypoint)
        values["demand"]=dict(self.demand)
        return values


def service_value(severity: float, detected_at: float, at_time: float, decay_rate: float = 0.011997) -> float:
    """Return the report's common exponential service value."""
    if at_time < detected_at:
        raise ValueError("service value time cannot precede detection time")
    return severity * math.exp(-decay_rate * (at_time - detected_at))


def _service_duration(demand: Mapping[str, int], severity: float, config: TaskConfig) -> float:
    parcel_count = sum(demand.values())
    return (
        config.service_duration_base
        + config.service_duration_per_parcel * parcel_count
        + config.service_duration_per_severity * severity
    )


def _validate_generated_task(task: SurvivorTask, config: TaskConfig) -> None:
    if set(task.demand) != set(config.item_types):
        raise TaskGenerationError("task demand must contain every configured item type")
    if any(quantity not in (0, 1) for quantity in task.demand.values()):
        raise TaskGenerationError("task demand quantities must be zero or one")
    if sum(task.demand.values()) < 1:
        raise TaskGenerationError("task demand must contain at least one item")
    if sum(task.demand.values()) > config.max_task_parcels:
        raise TaskGenerationError("task demand exceeds parcel limit")
    expected_mass = sum(config.item_weights[item] * task.demand[item] for item in config.item_types)
    if abs(task.required_payload_mass - expected_mass) > 1e-9:
        raise TaskGenerationError("task payload mass does not match item demand")
    if task.required_payload_mass > config.max_task_payload_mass + 1e-9:
        raise TaskGenerationError("task payload mass exceeds configured limit")
    if task.service_duration <= 0:
        raise TaskGenerationError("task service duration must be positive")


def _structure_footprint(structure: Any) -> Polygon2D:
    if structure.footprint:
        return structure.footprint
    x, y, _ = structure.minimum
    return (
        (x, y),
        (x + structure.width, y),
        (x + structure.width, y + structure.depth),
        (x, y + structure.depth),
    )


def _point_in_or_on_polygon(x: float, y: float, polygon: Polygon2D) -> bool:
    if _point_in_polygon(x, y, polygon):
        return True
    for index, current in enumerate(polygon):
        previous = polygon[index - 1]
        cross = (x - previous[0]) * (current[1] - previous[1]) - (y - previous[1]) * (current[0] - previous[0])
        if abs(cross) > 1e-8:
            continue
        if min(previous[0], current[0]) - 1e-8 <= x <= max(previous[0], current[0]) + 1e-8 and min(previous[1], current[1]) - 1e-8 <= y <= max(previous[1], current[1]) + 1e-8:
            return True
    return False


def _local_surface_z(scene: DisasterScene, x: float, y: float) -> float:
    """Return the top of the local solid surface below a task point."""
    top = scene.environment.world.minimum[2]
    for obstacle in scene.environment.obstacles:
        if x < obstacle.minimum[0] or x > obstacle.maximum[0] or y < obstacle.minimum[1] or y > obstacle.maximum[1]:
            continue
        if obstacle.footprint and not _point_in_or_on_polygon(x, y, obstacle.footprint):
            continue
        top = max(top, obstacle.maximum[2])
    return top


def _task_position_in_damage_footprint(scene: DisasterScene, structure: Any, rng: random.Random) -> Point:
    """Sample a task surface inside the selected damaged footprint."""
    polygon = _structure_footprint(structure)
    x_values = [point[0] for point in polygon]
    y_values = [point[1] for point in polygon]
    for _ in range(256):
        x = rng.uniform(min(x_values), max(x_values))
        y = rng.uniform(min(y_values), max(y_values))
        if _point_in_or_on_polygon(x, y, polygon):
            return (x, y, _local_surface_z(scene, x, y))
    x = sum(x_values) / len(x_values)
    y = sum(y_values) / len(y_values)
    if _point_in_or_on_polygon(x, y, polygon):
        return (x, y, _local_surface_z(scene, x, y))
    return (polygon[0][0], polygon[0][1], _local_surface_z(scene, polygon[0][0], polygon[0][1]))


def _vertical_dropoff_waypoint(scene: DisasterScene, task_position: Point, rng: random.Random, config: TaskConfig) -> Point:
    """Place the parcel drop point directly above the task by the configured clearance."""
    vertical_distance = rng.uniform(*config.dropoff_height_range)
    z = task_position[2] + vertical_distance
    if z > scene.environment.world.maximum[2]:
        raise TaskGenerationError("dropoff waypoint exceeds the scene vertical bound")
    return (task_position[0], task_position[1], z)


def generate_tasks(scene: DisasterScene, config: Optional[TaskConfig] = None, seed: Optional[int] = None) -> Tuple[SurvivorTask, ...]:
    config=config or TaskConfig(); config.validate(); actual_seed=config.seed if seed is None else int(seed)
    if actual_seed<0: raise TaskGenerationError("seed must be non negative")
    eligible_structures=[structure for structure in scene.structures if structure.scene_role=="target" and structure.damage_state in TASK_DAMAGE_STATES]
    if not eligible_structures: raise TaskGenerationError("scene has no minor, major, or destroyed damage footprints for tasks")
    rng=random.Random(actual_seed); tasks=[]
    for index in range(1, config.task_count + 1):
        structure=rng.choice(eligible_structures)
        detected=rng.uniform(*config.detection_time_range); severity=rng.uniform(*config.severity_range)
        subset_mask = rng.randrange(1, 1 << len(config.item_types))
        demand = {
            item: 1 if subset_mask & (1 << item_index) else 0
            for item_index, item in enumerate(config.item_types)
        }
        payload_mass=sum(config.item_weights[item] * quantity for item,quantity in demand.items())
        survivor_position=_task_position_in_damage_footprint(scene,structure,rng)
        task = SurvivorTask(
            "task_{}".format(index),
            "supply_delivery",
            survivor_position,
            _vertical_dropoff_waypoint(scene,survivor_position,rng,config),
            detected,
            severity,
            demand,
            payload_mass,
            _service_duration(demand, severity, config),
            service_value(severity,detected,detected,config.service_value_decay_rate),
        )
        _validate_generated_task(task, config)
        tasks.append(task)
    return tuple(tasks)
