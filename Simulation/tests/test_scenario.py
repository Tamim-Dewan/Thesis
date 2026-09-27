import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from pgbm_sim import SceneConfig, TaskConfig, build_scenario, load_scenario, save_scenario, validate_scenario  # noqa: E402


def test_scenario_export_load_and_validation_round_trip(tmp_path):
    scenario=build_scenario(SceneConfig(mode="du_outdoor",severity="moderate",seed=42),TaskConfig(task_count=5,seed=43),scenario_id="du_case_42")
    validate_scenario(scenario)
    path=tmp_path/"du_case_42.json"
    save_scenario(scenario,str(path))
    restored=load_scenario(str(path))
    assert restored.as_dict()==scenario.as_dict()
    assert scenario.schema_version=="scenario.v2"
    assert scenario.uav_config.payload_capacity==4
    assert scenario.uav_config.payload_weight_capacity==2.0
    assert len(scenario.uav_initial_states)==scenario.uav_config.count
    assert all(state.onboard_inventory=={} for state in scenario.uav_initial_states)
    assert all(state.battery_energy==scenario.uav_config.energy_capacity for state in scenario.uav_initial_states)


def test_v1_scenario_is_rejected(tmp_path):
    path=tmp_path/"old.json"
    path.write_text('{"schema_version":"scenario.v1"}',encoding="utf-8")
    with pytest.raises(Exception,match="scenario.v2"):
        load_scenario(str(path))
