import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from pgbm_sim import (  # noqa: E402
    EventSimulationConfig,
    SceneConfig,
    TaskConfig,
    UAVConfig,
    build_scenario,
    generate_disaster_scene,
    generate_tasks,
    plan_tasks,
    run_event_simulation,
)
from pgbm_sim.tasks import service_value  # noqa: E402


def test_three_phase_arrivals_are_seeded_and_follow_the_rate_weights():
    scene = generate_disaster_scene(SceneConfig(mode="synthetic", severity="moderate", seed=7))
    config = TaskConfig(task_count=12, seed=8, arrival_profile="three_phase")
    first = generate_tasks(scene, config)
    second = generate_tasks(scene, config)
    assert first == second
    counts = (
        sum(task.detected_at < 40.0 for task in first),
        sum(40.0 <= task.detected_at < 80.0 for task in first),
        sum(80.0 <= task.detected_at <= 120.0 for task in first),
    )
    assert counts == (6, 4, 2)


def test_dropoff_duration_is_fixed_per_parcel_and_not_severity_based():
    scene = generate_disaster_scene(SceneConfig(mode="synthetic", severity="moderate", seed=70))
    low_severity = TaskConfig(
        task_count=8,
        seed=71,
        severity_range=(0.35, 0.35),
        drop_time_per_parcel=0.5,
    )
    high_severity = TaskConfig(
        task_count=8,
        seed=71,
        severity_range=(1.0, 1.0),
        drop_time_per_parcel=0.5,
    )
    low_tasks = generate_tasks(scene, low_severity)
    high_tasks = generate_tasks(scene, high_severity)

    assert [task.demand for task in low_tasks] == [task.demand for task in high_tasks]
    assert [task.service_duration for task in low_tasks] == [
        pytest.approx(0.5 * sum(task.demand.values())) for task in low_tasks
    ]
    assert [task.service_duration for task in low_tasks] == [
        task.service_duration for task in high_tasks
    ]


def test_bruteforce_plan_is_deterministic_and_uses_completion_value():
    scenario = build_scenario(
        SceneConfig(mode="synthetic", severity="light", seed=12, uav_count=2),
        TaskConfig(task_count=3, seed=13, detection_time_range=(0.0, 0.0)),
        uav_config=UAVConfig(count=2),
    )
    first = plan_tasks(scenario, scenario.uav_config, method="pgbm_initial_bruteforce_v1")
    second = plan_tasks(scenario, scenario.uav_config, method="pgbm_initial_bruteforce_v1")
    assert first.assignments == second.assignments
    assert first.unassigned_task_ids == second.unassigned_task_ids
    assert first.objective_value == second.objective_value
    assert first.metadata["priority_rule"] == "joint_completion_value_bruteforce_v1"
    assert first.metadata["candidate_count"] > 1
    expected = 0.0
    for uav_id, timeline in first.metadata["assignment_timelines"].items():
        for task_id, completion_time in timeline["completion_times"].items():
            task = next(item for item in scenario.tasks if item.identifier == task_id)
            expected += service_value(task.severity, task.detected_at, completion_time, scenario.task_config.service_value_decay_rate)
    assert first.objective_value == pytest.approx(expected)


def test_event_runner_replans_after_turnaround_without_active_rerouting():
    scenario = build_scenario(
        SceneConfig(mode="synthetic", severity="light", seed=20, uav_count=1),
        TaskConfig(task_count=4, seed=21, arrival_profile="three_phase"),
        uav_config=UAVConfig(count=1),
    )
    result = run_event_simulation(
        scenario,
        scenario.uav_config,
        config=EventSimulationConfig(turnaround_minutes=1.0, max_pending_tasks=4),
    )
    assigned = [task_id for plan in result.dispatch_plans for task_id in plan.served_task_ids]
    assert len(assigned) == len(set(assigned))
    assert result.dispatch_count >= 1
    assert any(event.event == "task_detected" for event in result.events)
    assert all(
        event.event != "resupply_complete" or event.time >= 0.0
        for event in result.events
    )
    for plan in result.dispatch_plans:
        for assignment in plan.assignments:
            if assignment.task_ids:
                timeline = plan.metadata["assignment_timelines"][assignment.uav_id]
                assert max(timeline["completion_times"].values()) <= timeline["return_time"]


def test_event_runner_reproduces_the_same_episode():
    scenario = build_scenario(
        SceneConfig(mode="du_outdoor", severity="moderate", seed=30, uav_count=2),
        TaskConfig(task_count=3, seed=31, arrival_profile="three_phase"),
        uav_config=UAVConfig(count=2),
    )
    config = EventSimulationConfig(max_pending_tasks=3)
    first = run_event_simulation(scenario, scenario.uav_config, config=config)
    second = run_event_simulation(scenario, scenario.uav_config, config=config)
    assert first.events == second.events
    assert first.served_task_ids == second.served_task_ids
    assert first.deferred_task_ids == second.deferred_task_ids
    assert first.objective_value == second.objective_value
    assert first.requested_parcels == sum(sum(task.demand.values()) for task in scenario.tasks)
    assert first.dropped_parcels == sum(
        sum(next(task for task in scenario.tasks if task.identifier == task_id).demand.values())
        for task_id in first.served_task_ids
    )
    assert first.parcel_delivery_rate == pytest.approx(
        first.dropped_parcels / first.requested_parcels
    )
    assert [plan.assignments for plan in first.dispatch_plans] == [plan.assignments for plan in second.dispatch_plans]
