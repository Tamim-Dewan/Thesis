import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from pgbm_sim import ExperimentConfig, MetricsRecord, SeedManager, write_metrics_csv


def test_default_config_is_valid_and_round_trips():
    path = Path(__file__).parents[1] / "configs" / "phase1_default.json"
    config = ExperimentConfig.from_json(str(path))
    assert config.task_count == 6
    assert len(config.workspace_bounds) == 6
    assert config.as_dict()["workspace_bounds"] == list(config.workspace_bounds)
    assert config.as_dict()["environment"]["world_bounds"] == list(config.workspace_bounds)


def test_component_seeds_are_stable_and_distinct():
    first = SeedManager(20260921).manifest(["environment", "tasks", "uavs"])
    second = SeedManager(20260921).manifest(["environment", "tasks", "uavs"])
    assert first == second
    assert len(set(first.values())) == 3


def test_metrics_schema_writes_all_declared_columns(tmp_path):
    record = MetricsRecord(
        "phase1.v1", "test", 1, "reference", "scenario_1", "ok", 1.0,
        1, 0, 2.0, 10.0, 1.0, 5.0, 0.5, 0, 0, 1.0, 0.01,
    )
    output = tmp_path / "metrics.csv"
    write_metrics_csv([record], str(output))
    header = output.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header == list(MetricsRecord.__dataclass_fields__.keys())
