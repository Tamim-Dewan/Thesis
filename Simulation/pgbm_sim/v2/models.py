"""Runtime data models for the formulation aligned PGBM Version 2 path.

The V2 models are deliberately separate from the V1 event runner.  They keep
the immutable scenario definitions in the existing modules and add only the
runtime state needed to observe an active mission and replace one uncompleted
task.
"""

from dataclasses import asdict, dataclass, field
from typing import Dict, Mapping, Optional, Set, Tuple


Point = Tuple[float, float, float]


@dataclass(frozen=True)
class V2Config:
    """Configuration for a V2 event episode."""

    horizon_minutes: float = 120.0
    turnaround_minutes: float = 5.0
    planner_method: str = "pgbm_initial_bruteforce_v1"
    max_pending_tasks: int = 8
    max_candidate_plans: int = 50000
    recourse_enabled: bool = True
    one_for_one_replacement: bool = True

    def validate(self) -> None:
        if self.horizon_minutes <= 0.0:
            raise ValueError("V2 horizon must be positive")
        if self.turnaround_minutes < 0.0:
            raise ValueError("V2 turnaround must be non negative")
        if self.planner_method != "pgbm_initial_bruteforce_v1":
            raise ValueError("V2 currently reuses the V1 brute force dispatch planner")
        if self.max_pending_tasks < 1 or self.max_candidate_plans < 1:
            raise ValueError("V2 search limits must be positive")
        if not self.one_for_one_replacement:
            raise ValueError("V2 requires one_for_one_replacement=True")

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class TimelineSegment:
    """One travel or service segment in the current mission schedule."""

    kind: str
    task_id: Optional[str]
    path: Tuple[Point, ...]
    start_time: float
    end_time: float
    distance: float
    energy: float
    carried_mass: float

    def as_dict(self) -> Dict[str, object]:
        values = asdict(self)
        values["path"] = [list(point) for point in self.path]
        return values


@dataclass(frozen=True)
class MissionSchedule:
    """A route and time schedule from the current recourse state."""

    task_ids: Tuple[str, ...]
    route: Tuple[Point, ...]
    start_time: float
    start_position: Point
    distance_before: float
    energy_before: float
    initial_inventory: Mapping[str, int]
    segments: Tuple[TimelineSegment, ...]
    arrival_times: Mapping[str, float]
    completion_times: Mapping[str, float]
    return_time: float
    additional_distance: float
    additional_energy: float
    objective_value: float

    def as_dict(self) -> Dict[str, object]:
        return {
            "task_ids": list(self.task_ids),
            "route": [list(point) for point in self.route],
            "start_time": self.start_time,
            "start_position": list(self.start_position),
            "distance_before": self.distance_before,
            "energy_before": self.energy_before,
            "initial_inventory": dict(self.initial_inventory),
            "segments": [segment.as_dict() for segment in self.segments],
            "arrival_times": dict(self.arrival_times),
            "completion_times": dict(self.completion_times),
            "return_time": self.return_time,
            "additional_distance": self.additional_distance,
            "additional_energy": self.additional_energy,
            "objective_value": self.objective_value,
        }


@dataclass(frozen=True)
class MissionProjection:
    """Mission state observed at a recourse or event time."""

    time: float
    position: Point
    completed_task_ids: Tuple[str, ...]
    remaining_task_ids: Tuple[str, ...]
    current_task_id: Optional[str]
    service_in_progress: bool
    service_remaining: float
    onboard_inventory: Mapping[str, int]
    distance_consumed: float
    energy_consumed: float
    segment_kind: str


@dataclass
class MissionState:
    """Mutable runtime state for one active UAV mission."""

    mission_id: str
    uav_id: str
    task_ids: Tuple[str, ...]
    completed_task_ids: Set[str]
    schedule: MissionSchedule
    emitted_arrivals: Set[str] = field(default_factory=set)
    emitted_completions: Set[str] = field(default_factory=set)
    status: str = "active"
    generation: int = 0
    history: list = field(default_factory=list)

    def as_dict(self) -> Dict[str, object]:
        return {
            "mission_id": self.mission_id,
            "uav_id": self.uav_id,
            "task_ids": list(self.task_ids),
            "completed_task_ids": sorted(self.completed_task_ids),
            "schedule": self.schedule.as_dict(),
            "emitted_arrivals": sorted(self.emitted_arrivals),
            "emitted_completions": sorted(self.emitted_completions),
            "status": self.status,
            "generation": self.generation,
            "history": list(self.history),
        }
