import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))

from pgbm_sim import SceneConfig, TaskConfig, UAVConfig, build_scenario  # noqa: E402
from pgbm_sim.v2 import V2Config, run_event_simulation_v2  # noqa: E402
from pgbm_sim.v2_1 import V21Config, run_event_simulation_v21  # noqa: E402
from pgbm_sim.planner import BruteForceConfig, plan_dispatch  # noqa: E402
from pgbm_sim.v2_1.cache import choose_cache_item, prepare_cache_load  # noqa: E402


def _scenario(seed=5, task_count=12, uav_count=3):
    return build_scenario(
        SceneConfig(mode="synthetic", severity="moderate", seed=seed, uav_count=uav_count),
        TaskConfig(task_count=task_count, seed=seed + 100, arrival_profile="three_phase"),
        uav_config=UAVConfig(count=uav_count),
    )


def _config(**values):
    defaults = {
        "max_pending_tasks": 8,
        "max_candidate_plans": 5000,
    }
    defaults.update(values)
    return V21Config(**defaults)


def _single_assignment(scenario):
    available_tasks = tuple(task for task in scenario.tasks if task.detected_at <= 30.0)
    plan = plan_dispatch(
        scenario,
        available_tasks,
        ("uav_1",),
        30.0,
        scenario.uav_config,
        scenario.route_config,
        method="pgbm_initial_bruteforce_v1",
        horizon_minutes=120.0,
        search_config=BruteForceConfig(8, 5000),
    )
    assignment = next(item for item in plan.assignments if item.task_ids)
    task_by_id = {task.identifier: task for task in scenario.tasks}
    return assignment, tuple(task_by_id[task_id] for task_id in assignment.task_ids)


def test_cache_selection_uses_configured_prior_and_deterministic_tie_break():
    items = ("food", "water", "medical")
    assert choose_cache_item(items) == "food"
    assert choose_cache_item(items, item_prior={"food": 0.2, "water": 1.0, "medical": 0.3}) == "water"
    assert choose_cache_item(items, item_prior={"food": 1.0, "water": 1.0, "medical": 1.0}) == "food"


def test_v21_rejects_multiple_cache_slots_until_policy_is_extended():
    with pytest.raises(ValueError, match="one cache slot"):
        _config(max_cache_slots=2).validate()


def test_cache_disabled_is_the_v2_control_path():
    scenario = _scenario()
    v2 = run_event_simulation_v2(
        scenario,
        scenario.uav_config,
        scenario.route_config,
        V2Config(max_pending_tasks=8, max_candidate_plans=5000, recourse_enabled=True),
    )
    v21 = run_event_simulation_v21(
        scenario,
        scenario.uav_config,
        scenario.route_config,
        _config(cache_enabled=False),
    )
    assert v21.events == v2.events
    assert v21.recourse_decisions == v2.recourse_decisions
    assert v21.served_task_ids == v2.served_task_ids
    assert v21.deferred_task_ids == v2.deferred_task_ids
    assert v21.objective_value == pytest.approx(v2.objective_value)
    assert v21.total_distance == pytest.approx(v2.total_distance)
    assert v21.total_energy == pytest.approx(v2.total_energy)
    assert v21.cache_load_decisions == ()
    assert v21.cache_recourse_decisions == ()


def test_v21_is_deterministic_and_records_one_slot_cache_evidence():
    scenario = _scenario()
    config = _config(cache_item_prior={"food": 0.1, "water": 1.0, "medical": 0.1})
    first = run_event_simulation_v21(scenario, config=config)
    second = run_event_simulation_v21(scenario, config=config)

    assert first.events == second.events
    assert first.cache_load_decisions == second.cache_load_decisions
    assert first.cache_recourse_decisions == second.cache_recourse_decisions
    assert first.served_task_ids == second.served_task_ids
    assert first.total_energy == pytest.approx(second.total_energy)
    assert all(decision.loaded_parcels in (0, 1) for decision in first.cache_load_decisions)
    assert first.cache_loaded_parcels == sum(decision.loaded_parcels for decision in first.cache_load_decisions)
    assert first.cache_used_parcels <= first.cache_loaded_parcels
    assert first.cache_returned_parcels <= first.cache_loaded_parcels


def test_cache_hit_is_distinct_from_ordinary_positive_gain_recourse():
    result = run_event_simulation_v21(
        _scenario(),
        config=_config(cache_item_prior={"food": 0.1, "water": 1.0, "medical": 0.1}),
    )

    selected_hits = [decision for decision in result.cache_recourse_decisions if decision.cache_match]
    assert selected_hits
    assert all(decision.decision.accepted for decision in selected_hits)
    assert all(decision.cache_assisted for decision in selected_hits)
    assert result.cache_hit_count == len(selected_hits)
    assert result.cache_assisted_count >= result.cache_hit_count
    assert any(
        candidate.source == "released_inventory"
        for decision in result.cache_recourse_decisions
        for candidate in decision.candidates
    )


def test_cache_load_rejections_expose_capacity_reason():
    result = run_event_simulation_v21(_scenario(), config=_config())
    assert result.cache_load_rejections.get("no_free_slot", 0) > 0
    for decision in result.cache_load_decisions:
        if decision.loaded:
            assert decision.energy_margin is not None
            assert decision.energy_margin >= -1e-9


@pytest.mark.parametrize(
    ("uav_config", "horizon_minutes", "expected_reason"),
    [
        (UAVConfig(count=3, payload_weight_capacity=0.8), 120.0, "payload_weight_capacity"),
        (UAVConfig(count=3, energy_capacity=300.0, reserve_energy=200.0), 120.0, "energy_reserve"),
        (UAVConfig(count=3), 30.0, "horizon"),
    ],
)
def test_cache_loading_rejects_each_feasibility_guard(uav_config, horizon_minutes, expected_reason):
    scenario = _scenario()
    assignment, tasks = _single_assignment(scenario)

    result = prepare_cache_load(
        scenario.scene.environment,
        scenario.scene.environment.base.position,
        assignment,
        tasks,
        30.0,
        horizon_minutes,
        uav_config,
        scenario.route_config,
        scenario.task_config.item_types,
        scenario.task_config.item_weights,
        scenario.task_config.service_value_decay_rate,
        True,
        1,
        "configured_most_probable",
        None,
    )

    assert not result.decision.loaded
    assert result.decision.reason == expected_reason
