"""Reproducible validation and JSON export for complete experiment inputs."""

import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from .disaster_scene import DisasterScene, SceneConfig, generate_disaster_scene
from .environment import Point
from .tasks import SurvivorTask, TaskConfig, generate_tasks


SCENARIO_SCHEMA_VERSION = "scenario.v2"
SUPPLY_POLICY = "base_supply_sufficient"


class ScenarioValidationError(ValueError):
    """Raised when a scenario artifact cannot be trusted or reproduced."""


@dataclass(frozen=True)
class UAVInitialState:
    """The reproducible state of one responder UAV before planning starts."""

    uav_id: str
    position: Point
    battery_energy: float
    onboard_inventory: Mapping[str, int]
    payload_mass: float = 0.0
    status: str = "available"

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "UAVInitialState":
        return cls(
            uav_id=str(values["uav_id"]),
            position=tuple(float(value) for value in values["position"]),
            battery_energy=float(values["battery_energy"]),
            onboard_inventory={str(key): int(value) for key, value in values.get("onboard_inventory", {}).items()},
            payload_mass=float(values.get("payload_mass", 0.0)),
            status=str(values.get("status", "available")),
        )

    def as_dict(self) -> Dict[str, Any]:
        values = asdict(self)
        values["position"] = list(self.position)
        values["onboard_inventory"] = dict(self.onboard_inventory)
        return values


def _default_uav_config(scene: DisasterScene):
    from .planner import UAVConfig

    return UAVConfig(count=len(scene.uav_initial_positions))


def _default_route_config():
    from .routing import RouteConfig

    return RouteConfig()


def _default_execution_config():
    from .execution import ExecutionConfig

    return ExecutionConfig()


def _initial_uav_states(scene: DisasterScene, uav_config: Any) -> Tuple[UAVInitialState, ...]:
    if len(scene.uav_initial_positions) != uav_config.count:
        raise ScenarioValidationError("scene UAV positions do not match UAV configuration count")
    return tuple(
        UAVInitialState(
            uav_id="uav_{}".format(index + 1),
            position=position,
            battery_energy=uav_config.energy_capacity,
            onboard_inventory={},
            payload_mass=0.0,
            status="available",
        )
        for index, position in enumerate(scene.uav_initial_positions)
    )


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    scene: DisasterScene
    tasks: tuple
    scene_config: SceneConfig
    task_config: TaskConfig
    task_seed: int
    schema_version: str = SCENARIO_SCHEMA_VERSION
    uav_config: Any = None
    route_config: Any = None
    execution_config: Any = None
    uav_initial_states: Tuple[UAVInitialState, ...] = ()
    supply_policy: str = SUPPLY_POLICY

    def __post_init__(self) -> None:
        uav_config = self.uav_config or _default_uav_config(self.scene)
        route_config = self.route_config or _default_route_config()
        execution_config = self.execution_config or _default_execution_config()
        states = self.uav_initial_states or _initial_uav_states(self.scene, uav_config)
        object.__setattr__(self, "uav_config", uav_config)
        object.__setattr__(self, "route_config", route_config)
        object.__setattr__(self, "execution_config", execution_config)
        object.__setattr__(self, "uav_initial_states", tuple(states))

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "scenario_id": self.scenario_id,
            "scene_config": self.scene_config.as_dict(),
            "task_config": self.task_config.as_dict(),
            "task_seed": self.task_seed,
            "scene": self.scene.as_dict(),
            "tasks": [task.as_dict() for task in self.tasks],
            "uav_config": self.uav_config.as_dict(),
            "route_config": self.route_config.as_dict(),
            "execution_config": self.execution_config.as_dict(),
            "uav_initial_states": [state.as_dict() for state in self.uav_initial_states],
            "supply_policy": self.supply_policy,
        }


def build_scenario(
    scene_config: SceneConfig,
    task_config: Optional[TaskConfig] = None,
    scene_seed: Optional[int] = None,
    task_seed: Optional[int] = None,
    scenario_id: str = "scenario_1",
    uav_config: Any = None,
    route_config: Any = None,
    execution_config: Any = None,
) -> Scenario:
    from .planner import UAVConfig

    task_config = task_config or TaskConfig()
    scene = generate_disaster_scene(scene_config, scene_seed)
    actual_uav_config = uav_config or UAVConfig(count=scene_config.uav_count)
    actual_task_seed = task_config.seed if task_seed is None else int(task_seed)
    tasks = generate_tasks(scene, task_config, actual_task_seed)
    return Scenario(
        scenario_id,
        scene,
        tasks,
        scene_config,
        task_config,
        actual_task_seed,
        uav_config=actual_uav_config,
        route_config=route_config,
        execution_config=execution_config,
    )


def _validate_task(task: SurvivorTask, task_config: TaskConfig, uav_config: Any) -> None:
    if set(task.demand) != set(task_config.item_types):
        raise ScenarioValidationError("task demand must contain every configured item type")
    if any(quantity not in (0, 1) for quantity in task.demand.values()):
        raise ScenarioValidationError("task demand quantities must be zero or one")
    if sum(task.demand.values()) < 1:
        raise ScenarioValidationError("task demand must contain at least one item")
    expected_mass = sum(task_config.item_weights[item] * task.demand[item] for item in task_config.item_types)
    if not math.isclose(task.required_payload_mass, expected_mass, rel_tol=0.0, abs_tol=1e-9):
        raise ScenarioValidationError("task required_payload_mass does not match demand")
    if task.required_payload_mass > uav_config.payload_weight_capacity + 1e-9:
        raise ScenarioValidationError("task payload mass exceeds UAV payload capacity")
    if sum(task.demand.values()) > uav_config.payload_capacity:
        raise ScenarioValidationError("task parcel count exceeds UAV parcel capacity")
    if task.service_duration <= 0:
        raise ScenarioValidationError("task service_duration must be positive")


def validate_scenario(scenario: Scenario) -> None:
    if not scenario.scenario_id or scenario.schema_version != SCENARIO_SCHEMA_VERSION:
        raise ScenarioValidationError("unsupported or incomplete scenario metadata")
    if scenario.supply_policy != SUPPLY_POLICY:
        raise ScenarioValidationError("unsupported supply policy")
    scenario.scene_config.validate()
    scenario.task_config.validate()
    scenario.uav_config.validate()
    scenario.route_config.validate()
    scenario.execution_config.validate()
    if len(scenario.tasks) != scenario.task_config.task_count:
        raise ScenarioValidationError("scenario task count does not match task configuration")
    if len(scenario.uav_initial_states) != scenario.uav_config.count:
        raise ScenarioValidationError("scenario UAV state count does not match UAV configuration")
    if len(scenario.scene.uav_initial_positions) != scenario.uav_config.count:
        raise ScenarioValidationError("scene UAV position count does not match UAV configuration")
    if len({task.identifier for task in scenario.tasks}) != len(scenario.tasks):
        raise ScenarioValidationError("scenario task identifiers must be unique")
    if len({state.uav_id for state in scenario.uav_initial_states}) != len(scenario.uav_initial_states):
        raise ScenarioValidationError("scenario UAV identifiers must be unique")
    for task in scenario.tasks:
        _validate_task(task, scenario.task_config, scenario.uav_config)
    base_position = scenario.scene.environment.base.position
    for state in scenario.uav_initial_states:
        if state.position != base_position:
            raise ScenarioValidationError("initial UAV states must start at the base")
        if not math.isclose(state.battery_energy, scenario.uav_config.energy_capacity, rel_tol=0.0, abs_tol=1e-9):
            raise ScenarioValidationError("initial UAV batteries must be full")
        if state.onboard_inventory:
            raise ScenarioValidationError("initial UAV inventories must be empty")
        if state.payload_mass != 0.0 or state.status != "available":
            raise ScenarioValidationError("initial UAV payload and status are invalid")
    regenerated = build_scenario(
        scenario.scene_config,
        scenario.task_config,
        scenario.scene.environment.seed,
        scenario.task_seed,
        scenario.scenario_id,
        uav_config=scenario.uav_config,
        route_config=scenario.route_config,
        execution_config=scenario.execution_config,
    )
    if regenerated.as_dict() != scenario.as_dict():
        raise ScenarioValidationError("scenario is not reproducible from its stored local inputs")


def save_scenario(scenario: Scenario, path: str) -> None:
    validate_scenario(scenario)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(target.parent),
            prefix=".{}.".format(target.name),
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(scenario.as_dict(), temporary, sort_keys=True, indent=2)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, target)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def load_scenario(path: str) -> Scenario:
    try:
        values = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ScenarioValidationError("scenario file is unavailable or corrupt") from error
    if values.get("schema_version") != SCENARIO_SCHEMA_VERSION:
        raise ScenarioValidationError("unsupported scenario schema; expected scenario.v2")
    try:
        from .execution import ExecutionConfig
        from .planner import UAVConfig
        from .routing import RouteConfig

        scene_config = SceneConfig(**values["scene_config"])
        task_config = TaskConfig.from_mapping(values["task_config"])
        uav_config = UAVConfig.from_mapping(values["uav_config"])
        route_config = RouteConfig.from_mapping(values["route_config"])
        execution_config = ExecutionConfig.from_mapping(values["execution_config"])
        generated = build_scenario(
            scene_config,
            task_config,
            int(values["scene"]["environment"]["seed"]),
            int(values["task_seed"]),
            str(values["scenario_id"]),
            uav_config=uav_config,
            route_config=route_config,
            execution_config=execution_config,
        )
        tasks = tuple(
            SurvivorTask(
                identifier=str(task["identifier"]),
                task_type=str(task["task_type"]),
                survivor_position=tuple(float(value) for value in task["survivor_position"]),
                dropoff_waypoint=tuple(float(value) for value in task["dropoff_waypoint"]),
                detected_at=float(task["detected_at"]),
                severity=float(task["severity"]),
                demand={str(key): int(value) for key, value in task["demand"].items()},
                required_payload_mass=float(task["required_payload_mass"]),
                service_duration=float(task["service_duration"]),
                service_value_at_detection=float(task["service_value_at_detection"]),
                status=str(task.get("status", "pending")),
            )
            for task in values["tasks"]
        )
        states = tuple(UAVInitialState.from_mapping(state) for state in values["uav_initial_states"])
        scenario = Scenario(
            str(values["scenario_id"]),
            generated.scene,
            tasks,
            scene_config,
            task_config,
            int(values["task_seed"]),
            schema_version=SCENARIO_SCHEMA_VERSION,
            uav_config=uav_config,
            route_config=route_config,
            execution_config=execution_config,
            uav_initial_states=states,
            supply_policy=str(values["supply_policy"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ScenarioValidationError("scenario file is missing required scenario.v2 data") from error
    validate_scenario(scenario)
    return scenario
