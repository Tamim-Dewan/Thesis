import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from pgbm_sim import (  # noqa: E402
    EnvironmentConfig,
    EnvironmentGenerationError,
    generate_environment,
    is_valid_point,
    plot_environment,
)


def default_environment_config():
    return EnvironmentConfig.from_mapping({
        "world_bounds": [0, 0, 0, 100, 100, 60],
        "ground_level": 0,
        "obstacle_count": [2, 5],
        "obstacle_profiles": {
            "building": {
                "weight": 0.35,
                "width": [12, 25],
                "depth": [12, 25],
                "height": [15, 40],
                "z_range": [0, 0],
            },
            "road_block": {
                "weight": 0.15,
                "width": [10, 30],
                "depth": [4, 10],
                "height": [1, 4],
                "z_range": [0, 0],
            },
            "ground_rubble": {
                "weight": 0.25,
                "width": [5, 20],
                "depth": [5, 20],
                "height": [1, 8],
                "z_range": [0, 0],
            },
            "broken_floor": {
                "weight": 0.15,
                "width": [8, 20],
                "depth": [8, 20],
                "height": [1, 5],
                "z_range": [0, 35],
            },
            "elevated_debris": {
                "weight": 0.10,
                "width": [3, 12],
                "depth": [3, 12],
                "height": [1, 8],
                "z_range": [3, 35],
            },
        },
        "max_generation_attempts": 1000,
        "base_seed": 20260921,
    })


def fixed_profile(kind, z_range=(0, 0), weight=1.0, size=4, height=4):
    return {
        kind: {
            "weight": weight,
            "width": [size, size],
            "depth": [size, size],
            "height": [height, height],
            "z_range": list(z_range),
        }
    }


def test_environment_generation_is_reproducible():
    config = default_environment_config()
    first = generate_environment(config, seed=7)
    second = generate_environment(config, seed=7)
    assert first == second
    assert first.generation_metadata["obstacle_kinds"] == [obstacle.kind for obstacle in first.obstacles]


def test_obstacles_are_typed_positive_inside_world_and_base_is_grounded_outside_cluster():
    environment = generate_environment(default_environment_config(), seed=11)
    for obstacle in environment.obstacles:
        assert obstacle.kind in {
            "building", "road_block", "ground_rubble", "broken_floor", "elevated_debris",
        }
        assert obstacle.width > 0
        assert obstacle.depth > 0
        assert obstacle.height > 0
        assert all(obstacle.minimum[index] >= environment.world.minimum[index] for index in range(3))
        assert all(obstacle.maximum[index] <= environment.world.maximum[index] for index in range(3))
    assert environment.base.position[2] == 0
    assert is_valid_point(environment, environment.base.position)
    cluster_min = tuple(min(obstacle.minimum[index] for obstacle in environment.obstacles) for index in range(3))
    cluster_max = tuple(max(obstacle.maximum[index] for obstacle in environment.obstacles) for index in range(3))
    assert (
        environment.base.position[0] < cluster_min[0]
        or environment.base.position[0] > cluster_max[0]
        or environment.base.position[1] < cluster_min[1]
        or environment.base.position[1] > cluster_max[1]
    )


@pytest.mark.parametrize("kind", ["building", "road_block", "ground_rubble"])
def test_ground_obstacle_kinds_start_at_ground_level(kind):
    config = EnvironmentConfig.from_mapping({
        "world_bounds": [0, 0, 0, 40, 40, 40],
        "obstacle_count": [1, 1],
        "obstacle_profiles": fixed_profile(kind),
    })
    obstacle = generate_environment(config, seed=1).obstacles[0]
    assert obstacle.kind == kind
    assert obstacle.minimum[2] == 0


@pytest.mark.parametrize("kind", ["broken_floor", "elevated_debris"])
def test_elevated_obstacle_kinds_can_start_above_ground(kind):
    config = EnvironmentConfig.from_mapping({
        "world_bounds": [0, 0, 0, 40, 40, 40],
        "obstacle_count": [1, 1],
        "obstacle_profiles": fixed_profile(kind, z_range=(8, 8)),
    })
    obstacle = generate_environment(config, seed=1).obstacles[0]
    assert obstacle.kind == kind
    assert obstacle.minimum[2] == 8


def test_overlapping_obstacles_are_allowed():
    config = EnvironmentConfig.from_mapping({
        "world_bounds": [0, 0, 0, 30, 30, 20],
        "obstacle_count": [2, 2],
        "obstacle_profiles": fixed_profile("building", size=18, height=8),
    })
    overlaps = []
    for seed in range(20):
        environment = generate_environment(config, seed=seed)
        first, second = environment.obstacles
        overlaps.append(all(
            first.minimum[index] < second.maximum[index]
            and second.minimum[index] < first.maximum[index]
            for index in range(3)
        ))
    assert any(overlaps)


def test_point_on_obstacle_boundary_is_blocked():
    config = EnvironmentConfig.from_mapping({
        "world_bounds": [0, 0, 0, 10, 10, 10],
        "obstacle_count": [1, 1],
        "obstacle_profiles": fixed_profile("building", size=2, height=2),
        "max_generation_attempts": 100,
    })
    environment = generate_environment(config, seed=3)
    obstacle = environment.obstacles[0]
    assert not is_valid_point(environment, obstacle.minimum)
    assert is_valid_point(environment, environment.world.minimum)
    assert not is_valid_point(environment, (11, 0, 0))


def test_json_configuration_uses_nested_profiles():
    config = default_environment_config()
    values = config.as_dict()
    restored = EnvironmentConfig.from_mapping(values)
    assert restored == config
    assert set(values["obstacle_profiles"]) == {
        "building", "road_block", "ground_rubble", "broken_floor", "elevated_debris",
    }


def test_invalid_obstacle_ranges_raise_validation_error():
    with pytest.raises(ValueError, match="positive"):
        EnvironmentConfig.from_mapping({
            "world_bounds": [0, 0, 0, 10, 10, 10],
            "obstacle_count": [1, 1],
            "obstacle_profiles": fixed_profile("building", size=0),
        })


def test_invalid_ground_level_and_unknown_kind_raise_validation_errors():
    with pytest.raises(ValueError, match="ground_level"):
        EnvironmentConfig.from_mapping({
            "world_bounds": [0, 0, 0, 10, 10, 10],
            "ground_level": 1,
        })
    with pytest.raises(ValueError, match="unknown obstacle kind"):
        EnvironmentConfig.from_mapping({
            "world_bounds": [0, 0, 0, 10, 10, 10],
            "obstacle_profiles": {"fallen_tree": fixed_profile("building")["building"]},
        })


def test_impossible_base_placement_raises_generation_error():
    config = EnvironmentConfig.from_mapping({
        "world_bounds": [0, 0, 0, 10, 10, 10],
        "obstacle_count": [1, 1],
        "obstacle_profiles": fixed_profile("building", size=10, height=10),
        "max_generation_attempts": 5,
    })
    with pytest.raises(EnvironmentGenerationError):
        generate_environment(config, seed=2)


def test_plot_environment_returns_typed_figure_with_ground_and_base():
    environment = generate_environment(default_environment_config(), seed=5)
    figure = plot_environment(environment)
    assert figure.__class__.__name__ == "Figure"
    assert len(figure.data) == len(environment.obstacles) + 2
    obstacle_traces = [trace for trace in figure.data if "obstacle_" in str(trace.name)]
    assert len(obstacle_traces) == len(environment.obstacles)
    assert len({trace.color for trace in obstacle_traces}) >= 2
    assert any(trace.name == environment.base.identifier for trace in figure.data)
    assert any(trace.name == "ground plane" for trace in figure.data)
