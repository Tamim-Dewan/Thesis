import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from pgbm_sim import SceneConfig, TaskConfig, UAVConfig, build_scenario, plan_tasks  # noqa: E402
from pgbm_sim.routing import RouteResult  # noqa: E402


def test_planner_is_deterministic_and_respects_resources():
    scenario=build_scenario(SceneConfig(mode="du_outdoor",severity="moderate",seed=5),TaskConfig(task_count=6,seed=6))
    config=UAVConfig(count=3,energy_capacity=1000)
    first=plan_tasks(scenario,config); second=plan_tasks(scenario,config)
    assert first==second
    assert len(first.served_task_ids)+len(first.unassigned_task_ids)==6
    assert all(item.payload<=config.payload_capacity and item.energy + config.reserve_energy <= config.energy_capacity for item in first.assignments)
    assert all(item.payload_weight<=config.payload_weight_capacity for item in first.assignments)
    assert all(item.route[0]==scenario.scene.environment.base.position and item.route[-1]==scenario.scene.environment.base.position for item in first.assignments if item.task_ids)


def test_planner_rejects_a_second_full_task_when_weight_limit_is_two_kg():
    scenario=build_scenario(SceneConfig(mode="synthetic",severity="light",seed=18),TaskConfig(task_count=2,seed=19,detection_time_range=(0.0,0.0)))
    full_demand={"food":1,"water":1,"medical":1}
    scenario=replace(scenario,tasks=tuple(replace(task,demand=full_demand,required_payload_mass=1.25) for task in scenario.tasks))
    config=UAVConfig(count=1)
    plan=plan_tasks(scenario,config)
    assignment=plan.assignments[0]
    assert assignment.payload_weight==1.25
    assert len(assignment.task_ids)==1
    assert len(plan.unassigned_task_ids)==1


def test_nearest_baseline_has_a_distinguishable_method():
    scenario=build_scenario(SceneConfig(mode="synthetic",severity="light",seed=8),TaskConfig(task_count=5,seed=9))
    plan=plan_tasks(scenario,UAVConfig(count=2),method="nearest_task_first")
    assert plan.method=="nearest_task_first"
    assert len(plan.assignments)==2


def test_initial_snapshot_uses_current_service_value_order():
    scenario=build_scenario(
        SceneConfig(mode="synthetic",severity="light",seed=40),
        TaskConfig(task_count=2,seed=41,detection_time_range=(0.0,0.0)),
    )
    older=replace(
        scenario.tasks[0],
        severity=0.8,
        detected_at=0.0,
        service_value_at_detection=0.8,
    )
    recent=replace(
        scenario.tasks[1],
        severity=0.7,
        detected_at=30.0,
        service_value_at_detection=0.7,
    )
    scenario=replace(scenario,tasks=(older,recent),execution_config=replace(scenario.execution_config,start_time=30.0))
    plan=plan_tasks(scenario,UAVConfig(count=1),method="initial_snapshot_greedy_v1")
    assert plan.method=="initial_snapshot_greedy_v1"
    assert plan.assignments[0].task_ids[0]==recent.identifier
    assert plan.metadata["priority_rule"]=="current_exponential_service_value_then_marginal_route_distance"


def test_initial_snapshot_records_assignment_decision_trace():
    scenario=build_scenario(
        SceneConfig(mode="synthetic",severity="light",seed=42),
        TaskConfig(task_count=3,seed=43,detection_time_range=(0.0,0.0)),
    )
    scenario=replace(scenario,execution_config=replace(scenario.execution_config,start_time=30.0))
    plan=plan_tasks(scenario,UAVConfig(count=2),method="initial_snapshot_greedy_v1")
    trace=plan.metadata["decision_trace"]
    assert len(trace)==3
    assert [item["step"] for item in trace]==[1,2,3]
    assert all(item["candidates"] for item in trace)
    assert all(item["assignment_state"] for item in trace)
    assert all(item["route_state"] for item in trace)


def test_planner_defers_tasks_not_detected_at_planning_time():
    scenario=build_scenario(
        SceneConfig(mode="synthetic",severity="light",seed=30),
        TaskConfig(task_count=2,seed=31,detection_time_range=(10.0,10.0)),
    )
    plan=plan_tasks(scenario,UAVConfig(count=1))
    assert plan.served_task_ids==()
    assert set(plan.unassigned_task_ids)=={task.identifier for task in scenario.tasks}
    assert plan.metadata["planning_time"]==0.0
    assert plan.metadata["eligible_task_count"]==0


def test_planner_preserves_energy_reserve(monkeypatch):
    scenario=build_scenario(
        SceneConfig(mode="synthetic",severity="light",seed=32),
        TaskConfig(task_count=1,seed=33,detection_time_range=(0.0,0.0)),
    )
    base=scenario.scene.environment.base.position

    def expensive_route(environment, start, task_positions, config):
        return RouteResult((base, base), 900.0, True)

    monkeypatch.setattr("pgbm_sim.planner.route_task_sequence", expensive_route)
    plan=plan_tasks(scenario,UAVConfig(count=1,energy_capacity=1000.0,reserve_energy=200.0))
    assert plan.served_task_ids==()
    assert plan.unassigned_task_ids==(scenario.tasks[0].identifier,)
