"""Validated experiment configuration shared by all simulation phases."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

from .environment import EnvironmentConfig


@dataclass(frozen=True)
class ExperimentConfig:
    schema_version: str
    experiment_name: str
    base_seed: int
    time_unit: str
    distance_unit: str
    energy_unit: str
    payload_unit: str
    workspace_bounds: Tuple[float, float, float, float, float, float]
    planning_time: float
    decay_rate: float
    task_count: int
    uav_count: int
    reserve_fraction: float
    metrics_output: str
    manifest_output: str
    environment: EnvironmentConfig

    @classmethod
    def from_mapping(cls, values: Dict[str, Any]) -> "ExperimentConfig":
        required = {
            "schema_version", "experiment_name", "base_seed", "time_unit",
            "distance_unit", "energy_unit", "payload_unit", "workspace_bounds",
            "planning_time", "decay_rate", "task_count", "uav_count",
            "reserve_fraction", "metrics_output", "manifest_output",
        }
        missing = sorted(required - set(values))
        if missing:
            raise ValueError("missing configuration fields: {}".format(", ".join(missing)))
        environment_values = dict(values.get("environment", {}))
        environment_values.setdefault("world_bounds", values["workspace_bounds"])
        environment_values.setdefault("base_seed", values["base_seed"])
        config = cls(
            schema_version=str(values["schema_version"]),
            experiment_name=str(values["experiment_name"]),
            base_seed=int(values["base_seed"]),
            time_unit=str(values["time_unit"]),
            distance_unit=str(values["distance_unit"]),
            energy_unit=str(values["energy_unit"]),
            payload_unit=str(values["payload_unit"]),
            workspace_bounds=tuple(float(value) for value in values["workspace_bounds"]),
            planning_time=float(values["planning_time"]),
            decay_rate=float(values["decay_rate"]),
            task_count=int(values["task_count"]),
            uav_count=int(values["uav_count"]),
            reserve_fraction=float(values["reserve_fraction"]),
            metrics_output=str(values["metrics_output"]),
            manifest_output=str(values["manifest_output"]),
            environment=EnvironmentConfig.from_mapping(environment_values),
        )
        config.validate()
        return config

    @classmethod
    def from_json(cls, path: str) -> "ExperimentConfig":
        with Path(path).open("r", encoding="utf-8") as handle:
            return cls.from_mapping(json.load(handle))

    def validate(self) -> None:
        if len(self.workspace_bounds) != 6:
            raise ValueError("workspace_bounds must contain xmin, ymin, zmin, xmax, ymax, zmax")
        if any(self.workspace_bounds[index] >= self.workspace_bounds[index + 3] for index in range(3)):
            raise ValueError("workspace bounds must have positive extent on every axis")
        if self.base_seed < 0:
            raise ValueError("base_seed must be non-negative")
        if self.planning_time < 0:
            raise ValueError("planning_time must be non-negative")
        if self.decay_rate <= 0:
            raise ValueError("decay_rate must be positive")
        if self.task_count < 1 or self.uav_count < 1:
            raise ValueError("task_count and uav_count must be positive")
        if not 0 <= self.reserve_fraction < 1:
            raise ValueError("reserve_fraction must be in [0, 1)")
        self.environment.validate()

    def as_dict(self) -> Dict[str, Any]:
        values = asdict(self)
        values["workspace_bounds"] = list(self.workspace_bounds)
        values["environment"] = self.environment.as_dict()
        return values
