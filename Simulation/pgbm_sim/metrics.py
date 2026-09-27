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


METRIC_FIELDS: Tuple[str, ...] = tuple(MetricsRecord.__dataclass_fields__.keys())


def write_metrics_csv(records: Iterable[MetricsRecord], path: str) -> None:
    rows = [asdict(record) for record in records]
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(METRIC_FIELDS))
        writer.writeheader()
        writer.writerows(rows)
