import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from pgbm_sim import ResearchExperimentConfig, run_experiments  # noqa: E402


def test_experiment_runner_produces_comparable_records():
    records=run_experiments([1,2],ResearchExperimentConfig(mode="synthetic",severity="moderate",task_count=4,uav_count=2))
    assert len(records)==4
    assert {record.method for record in records}=={"pgbm_heuristic_v1","nearest_task_first"}
    assert all(record.status=="ok" for record in records)
    assert all(0<=record.safe_return_rate<=1 for record in records)
    assert all(not record.recourse_enabled for record in records)
    assert all(record.accepted_replacements==0 for record in records)
    assert all(record.rejected_replacements==0 for record in records)
    assert all(record.requested_parcels >= record.dropped_parcels >= 0 for record in records)
    assert all(0.0 <= record.parcel_delivery_rate <= 1.0 for record in records)


def test_experiment_runner_can_enable_the_recourse_fixture():
    records=run_experiments(
        [3],
        ResearchExperimentConfig(
            mode="synthetic",
            severity="moderate",
            task_count=4,
            uav_count=2,
            recourse_enabled=True,
        ),
    )
    assert len(records)==2
    assert all(record.recourse_enabled for record in records)
    assert all(record.accepted_replacements+record.rejected_replacements==1 for record in records)
