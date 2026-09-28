"""Reusable components for the PGBM simulation."""

from .config import ExperimentConfig
from .environment import (
    Base,
    Environment,
    EnvironmentConfig,
    EnvironmentGenerationError,
    Obstacle,
    ObstacleProfile,
    World,
    generate_environment,
    is_valid_point,
    plot_environment,
)
from .metrics import MetricsRecord, write_metrics_csv
from .seeds import SeedManager
from .disaster_scene import (
    CandidateSite, DataSource, DisasterScene, IndoorConnection, IndoorRoom, RoadSegment,
    SceneConfig, SceneConfigurationError, ScenePreset, SceneTemplateError, Structure,
    generate_disaster_scene, is_valid_candidate_site, is_valid_indoor_route,
    load_scene_preset, load_scene_template, plot_building_layout, plot_collision_view, plot_damage_view, plot_disaster_scene, plot_map_view, validate_scene_geometry,
)
from .tasks import SurvivorTask, TaskConfig, TaskGenerationError, generate_tasks, service_value
from .scenario import UAVInitialState, Scenario, ScenarioValidationError, build_scenario, load_scenario, save_scenario, validate_scenario
from .planner import BruteForceConfig, Plan, UAVAssignment, UAVConfig, plan_dispatch, plan_tasks
from .routing import RouteConfig, RoutePlanningError, RouteResult, route_between, route_task_sequence
from .execution import ExecutionConfig, ExecutionEvent, ExecutionResult, RecourseResult, apply_recourse, execute_plan
from .event_simulation import EventSimulationConfig, EventSimulationResult, run_event_simulation
from .experiment import ExperimentConfig as ResearchExperimentConfig, run_experiment_matrix, run_experiments, write_experiment_matrix, write_experiment_metrics
from .v2 import V2Config, V2EpisodeResult, run_event_simulation_v2

__all__ = [
    "Base", "Environment", "EnvironmentConfig", "EnvironmentGenerationError",
    "ExperimentConfig", "MetricsRecord", "Obstacle", "ObstacleProfile", "SeedManager", "World",
    "generate_environment", "is_valid_point", "plot_environment", "write_metrics_csv",
    "CandidateSite", "DataSource", "DisasterScene", "IndoorConnection", "IndoorRoom",
    "RoadSegment", "SceneConfig", "SceneConfigurationError", "ScenePreset",
    "SceneTemplateError", "Structure", "generate_disaster_scene", "is_valid_candidate_site",
    "is_valid_indoor_route", "load_scene_preset", "load_scene_template", "plot_building_layout", "plot_collision_view", "plot_damage_view", "plot_disaster_scene", "plot_map_view", "validate_scene_geometry",
    "SurvivorTask", "TaskConfig", "TaskGenerationError", "generate_tasks", "service_value",
    "UAVInitialState", "Scenario", "ScenarioValidationError", "build_scenario", "load_scenario", "save_scenario", "validate_scenario",
    "BruteForceConfig", "Plan", "UAVAssignment", "UAVConfig", "plan_dispatch", "plan_tasks",
    "RouteConfig", "RoutePlanningError", "RouteResult", "route_between", "route_task_sequence",
    "ExecutionConfig", "ExecutionEvent", "ExecutionResult", "RecourseResult", "apply_recourse", "execute_plan",
    "EventSimulationConfig", "EventSimulationResult", "run_event_simulation",
    "ResearchExperimentConfig", "run_experiment_matrix", "run_experiments", "write_experiment_matrix", "write_experiment_metrics",
    "V2Config", "V2EpisodeResult", "run_event_simulation_v2",
]
