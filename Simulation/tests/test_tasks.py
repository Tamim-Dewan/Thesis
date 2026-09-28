import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from pgbm_sim import SceneConfig, TaskConfig, generate_disaster_scene, generate_tasks, service_value  # noqa: E402
from pgbm_sim.environment import _point_in_polygon, is_valid_point  # noqa: E402


def test_task_generation_is_reproducible_and_actionable():
    scene=generate_disaster_scene(SceneConfig(mode="du_outdoor",severity="moderate",seed=12))
    config=TaskConfig(task_count=6,seed=77)
    first=generate_tasks(scene,config); second=generate_tasks(scene,config)
    assert first==second
    assert len(first)==6
    assert len({task.dropoff_waypoint for task in first})==6
    assert all(task.survivor_position != task.dropoff_waypoint for task in first)
    assert all(task.survivor_position[:2] == task.dropoff_waypoint[:2] for task in first)
    assert all(2.0 <= task.dropoff_waypoint[2] - task.survivor_position[2] <= 4.0 for task in first)
    assert all(is_valid_point(scene.environment, task.dropoff_waypoint) for task in first)
    assert all(
        any(
            structure.scene_role == "target"
            and structure.damage_state in {"minor", "major", "destroyed"}
            and _point_in_polygon(task.survivor_position[0], task.survivor_position[1], structure.footprint)
            for structure in scene.structures
        )
        for task in first
    )
    assert all(task.task_type=="supply_delivery" for task in first)
    assert all(task.is_actionable(task.detected_at) for task in first)


def test_task_values_are_bounded_and_json_compatible():
    scene=generate_disaster_scene(SceneConfig(mode="synthetic",severity="severe",seed=3))
    tasks=generate_tasks(scene,TaskConfig(task_count=5,seed=4))
    for task in tasks:
        assert 0.35<=task.severity<=1.0
        assert all(item in {"food","water","medical"} for item in task.demand)
        assert set(task.demand)=={"food","water","medical"}
        assert all(quantity in {0,1} for quantity in task.demand.values())
        assert sum(task.demand.values())>=1
        assert task.required_payload_mass==sum(TaskConfig().item_weights[item] * quantity for item, quantity in task.demand.items())
        assert task.required_payload_mass<=2.0
        assert sum(task.demand.values())<=4
        assert task.service_duration>0
        assert task.required_payload_mass>0
        assert task.service_value_at_detection==task.severity
        assert isinstance(task.as_dict(),dict)
        assert "survivor_position" in task.as_dict()
        assert "dropoff_waypoint" in task.as_dict()
        assert "site_ref" not in task.as_dict()
        assert "site_kind" not in task.as_dict()


def test_task_payload_contract_uses_small_delivery_units():
    config=TaskConfig()
    assert config.item_weights=={"food":0.25,"water":0.5,"medical":0.5}
    assert config.max_task_parcels==4
    assert config.max_task_payload_mass==2.0
    scene=generate_disaster_scene(SceneConfig(mode="synthetic",severity="moderate",seed=13))
    tasks=generate_tasks(scene,TaskConfig(task_count=6,seed=14))
    assert any(sum(task.demand.values())<3 for task in tasks)
    assert all(task.service_duration==0.5*sum(task.demand.values()) for task in tasks)


def test_task_generation_can_reuse_damage_footprints_for_many_tasks():
    scene=generate_disaster_scene(SceneConfig(mode="synthetic",severity="light",seed=1))
    tasks=generate_tasks(scene,TaskConfig(task_count=100))
    assert len(tasks)==100
    assert all(task.survivor_position[:2] == task.dropoff_waypoint[:2] for task in tasks)


def test_common_exponential_service_value_data_is_monotone():
    value_at_detection=service_value(0.8, 10.0, 10.0)
    value_later=service_value(0.8, 10.0, 40.0)
    assert value_at_detection==0.8
    assert 0.0<value_later<value_at_detection
