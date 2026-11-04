import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[2]))

from pgbm_sim.v2_1.experiment import (  # noqa: E402
    V21ExperimentConfig,
    run_paired_v21_episode,
    run_v21_matrix,
    write_v21_matrix,
)


def test_paired_episode_reuses_one_scenario_for_control_and_cache_variant():
    control, cache, payload = run_paired_v21_episode(
        "synthetic",
        5,
        12,
        3,
        V21ExperimentConfig(max_pending_tasks=8, max_candidate_plans=5000),
    )

    scenario, v2, v21 = payload
    assert control.base.scenario_fingerprint == cache.base.scenario_fingerprint
    assert control.base.scenario_fingerprint
    assert control.base.algorithm == "V2"
    assert cache.base.algorithm == "V2"
    assert control.base.objective_value >= 0.0
    assert v21.objective_value >= 0.0
    assert v2.events
    assert v21.cache_load_decisions
    assert scenario.scenario_id == control.base.scenario_id


def test_matrix_contains_control_and_each_cache_variant_with_shared_fingerprint():
    records, traces = run_v21_matrix(
        [5],
        modes=("synthetic",),
        task_counts=(12,),
        uav_counts=(3,),
    )

    assert len(records) == 3
    assert len(traces) == 1
    assert {record.as_dict()["algorithm"] for record in records} == {"V2_control", "V2.1"}
    assert {record.as_dict()["cache_variant"] for record in records} == {
        "v2_control",
        "uniform",
        "water_heavy_sensitivity",
    }
    assert len({record.as_dict()["scenario_fingerprint"] for record in records}) == 1
    assert set(traces[0]["v2_1"]) == {"uniform", "water_heavy_sensitivity"}


def test_matrix_worker_mode_preserves_scenario_order_and_fingerprints():
    serial_records, serial_traces = run_v21_matrix(
        [5, 6],
        modes=("synthetic",),
        task_counts=(12,),
        uav_counts=(3,),
        workers=1,
    )
    parallel_records, parallel_traces = run_v21_matrix(
        [5, 6],
        modes=("synthetic",),
        task_counts=(12,),
        uav_counts=(3,),
        workers=2,
    )

    assert [trace["scenario_fingerprint"] for trace in serial_traces] == [
        trace["scenario_fingerprint"] for trace in parallel_traces
    ]
    assert [record.as_dict()["scenario_fingerprint"] for record in serial_records] == [
        record.as_dict()["scenario_fingerprint"] for record in parallel_records
    ]


def test_matrix_writer_exports_metrics_traces_and_manifest(tmp_path):
    metrics_path = tmp_path / "metrics.csv"
    trace_path = tmp_path / "traces.jsonl"
    manifest_path = tmp_path / "manifest.json"
    records = write_v21_matrix(
        str(metrics_path),
        str(trace_path),
        str(manifest_path),
        [5],
        modes=("synthetic",),
        task_counts=(12,),
        uav_counts=(3,),
    )

    with metrics_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    with trace_path.open(encoding="utf-8") as handle:
        traces = [json.loads(line) for line in handle if line.strip()]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert len(rows) == len(records) == 3
    assert "cache_hit_rate" in rows[0]
    assert len(traces) == 1
    assert manifest["record_count"] == 3
    assert manifest["episode_count"] == 1
