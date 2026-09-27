import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from pgbm_sim import (ExecutionConfig, SceneConfig, TaskConfig, UAVConfig, apply_recourse, build_scenario, execute_plan, plan_tasks)  # noqa: E402


def test_execution_produces_service_events_and_metrics():
    scenario=build_scenario(SceneConfig(mode="du_outdoor",severity="moderate",seed=10),TaskConfig(task_count=4,seed=11))
    config=UAVConfig(count=3)
    plan=plan_tasks(scenario,config)
    result=execute_plan(scenario,plan,config)
    assert result.total_distance>=0
    assert result.total_energy>=0
    assert len(result.served_task_ids)+len(result.missed_task_ids)<=4
    assert result.safe_return_rate==1.0
    assert all(event.event in {"arrive","service_complete","service_unavailable","return_to_base"} for event in result.events)


def test_recourse_accepts_new_unique_tasks_when_capacity_allows():
    scenario=build_scenario(SceneConfig(mode="synthetic",severity="light",seed=20),TaskConfig(task_count=3,seed=21))
    config=UAVConfig(count=3,payload_capacity=100)
    plan=plan_tasks(scenario,config)
    replacement=build_scenario(SceneConfig(mode="synthetic",severity="light",seed=22),TaskConfig(task_count=1,seed=23)).tasks[0]
    result=apply_recourse(scenario,plan,(replacement,),config)
    assert replacement.identifier in result.accepted_replacement_ids or replacement.identifier in result.rejected_replacement_ids
    assert not (set(result.accepted_replacement_ids)&set(result.rejected_replacement_ids))


def test_execution_uses_scenario_start_time():
    scenario=build_scenario(
        SceneConfig(mode="synthetic",severity="light",seed=24),
        TaskConfig(task_count=1,seed=25,detection_time_range=(0.0,0.0)),
        execution_config=ExecutionConfig(start_time=30.0),
    )
    plan=plan_tasks(scenario,UAVConfig(count=1))
    result=execute_plan(scenario,plan,UAVConfig(count=1))
    assert result.events
    assert min(event.time for event in result.events)>=30.0
