"""Standard output schema for later planners and experiments."""

import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Tuple


@dataclass(frozen=True)
class MetricsRecord:
    schema_version: str
    experiment_name: str
    seed: int
    method: str
    scenario_id: str
    status: str
    objective_value: float
    served_tasks: int
    deferred_tasks: int
    average_completion_delay: float
    total_distance: float
    total_travel_time: float
    total_energy: float
    payload_utilization: float
    accepted_replacements: int
    rejected_replacements: int
    safe_return_rate: float
    runtime_seconds: float
    recourse_enabled: bool = False
    horizon_minutes: float = 0.0
    arrival_profile: str = ""
    task_count: int = 0
    uav_count: int = 0
    dispatch_count: int = 0
    peak_queue_size: int = 0
    candidate_count: int = 0
    planner_runtime_seconds: float = 0.0
    route_runtime_seconds: float = 0.0
    phase_high_tasks: int = 0
    phase_medium_tasks: int = 0
    phase_low_tasks: int = 0
    search_truncated_dispatches: int = 0
    max_candidate_count: int = 0
    max_pending_considered: int = 0
    requested_parcels: int = 0
    dropped_parcels: int = 0
    parcel_delivery_rate: float = 0.0


METRIC_FIELDS: Tuple[str, ...] = tuple(MetricsRecord.__dataclass_fields__.keys())


def write_metrics_csv(records: Iterable[MetricsRecord], path: str) -> None:
    rows = [asdict(record) for record in records]
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(METRIC_FIELDS))
        writer.writeheader()
        writer.writerows(rows)
