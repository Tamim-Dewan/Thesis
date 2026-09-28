import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))

from pgbm_sim import EventSimulationConfig, SceneConfig, TaskConfig, UAVConfig, build_scenario, run_event_simulation  # noqa: E402
from pgbm_sim.v2 import V2Config, run_event_simulation_v2  # noqa: E402


def _scenario(seed=5, task_count=12, uav_count=3):
    return build_scenario(
        SceneConfig(mode="synthetic", severity="moderate", seed=seed, uav_count=uav_count),
        TaskConfig(task_count=task_count, seed=seed + 100, arrival_profile="three_phase"),
        uav_config=UAVConfig(count=uav_count),
    )


def _v2_config(recourse=True):
    return V2Config(
        max_pending_tasks=8,
        max_candidate_plans=5000,
        recourse_enabled=recourse,
    )


def test_v2_fixed_control_matches_v1_reference_episode():
    scenario = _scenario(seed=5, task_count=12, uav_count=3)
    v1 = run_event_simulation(
        scenario,
        scenario.uav_config,
        scenario.route_config,
        EventSimulationConfig(max_pending_tasks=8, max_candidate_plans=5000),
    )
    v2 = run_event_simulation_v2(scenario, scenario.uav_config, scenario.route_config, _v2_config(False))
    assert v2.served_task_ids == v1.served_task_ids
    assert v2.deferred_task_ids == v1.deferred_task_ids
    assert v2.objective_value == pytest.approx(v1.objective_value)
    assert v2.total_distance == pytest.approx(v1.total_distance)
    assert v2.total_energy == pytest.approx(v1.total_energy)
    assert v2.candidate_count == v1.candidate_count
    assert v2.recourse_decisions == ()


def test_v2_recourses_one_for_one_and_keeps_unique_completion():
    scenario = _scenario()
    first = run_event_simulation_v2(scenario, scenario.uav_config, scenario.route_config, _v2_config())
    second = run_event_simulation_v2(scenario, scenario.uav_config, scenario.route_config, _v2_config())

    assert first.events == second.events
    assert first.recourse_decisions == second.recourse_decisions
    assert first.accepted_replacements > 0
    assert first.accepted_replacements + first.rejected_replacements == first.recourse_trigger_count
    completed = [event.task_id for event in first.events if event.event == "service_complete"]
    assert len(completed) == len(set(completed))
    for decision in first.recourse_decisions:
        if not decision.accepted:
            assert decision.queue_changes == (("kept_in_queue", decision.new_task_id),)
            continue
        assert decision.selected_uav_id is not None
        assert decision.displaced_task_id is not None
        assert decision.delta_value > 0.0
        assert ("assigned_to_mission", decision.new_task_id) in decision.queue_changes
        assert ("returned_to_queue", decision.displaced_task_id) in decision.queue_changes
        assert any(
            candidate.uav_id == decision.selected_uav_id
            and candidate.displaced_task_id == decision.displaced_task_id
            and candidate.delta_value == pytest.approx(decision.delta_value)
            for candidate in decision.candidates
        )


def test_v2_records_inventory_and_service_protection_rejections():
    result = run_event_simulation_v2(_scenario(), config=_v2_config())
    reasons = {
        candidate.rejection_reason.split(":", 1)[0]
        for decision in result.recourse_decisions
        for candidate in decision.candidates
    }
    assert "onboard_inventory" in reasons
    assert "service_in_progress" in reasons


def test_v2_final_objective_counts_completed_tasks_once():
    scenario = _scenario(seed=6, task_count=10, uav_count=3)
    result = run_event_simulation_v2(scenario, config=_v2_config())
    completion_events = [event for event in result.events if event.event == "service_complete"]
    assert len(completion_events) == len(result.served_task_ids)
    assert len({event.task_id for event in completion_events}) == len(completion_events)
    assert result.objective_value >= 0.0
