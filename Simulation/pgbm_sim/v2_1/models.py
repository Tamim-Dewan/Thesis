"""Runtime models for the cache aware PGBM Version 2.1 path.

Version 2.1 deliberately wraps the canonical Version 2 result and recourse
models.  The cache state is kept beside a mission rather than inserted into
the Version 2 schedule, which keeps the Version 2 evidence reproducible and
makes the reserve parcel visible in its own trace.
"""

from dataclasses import asdict, dataclass, field
from typing import Dict, Mapping, Optional, Tuple

from ..v2.event_simulation import V2EpisodeResult
from ..v2.models import V2Config
from ..v2.recourse import RecourseDecision


def _mapping_dict(values: Mapping[str, int]) -> Dict[str, int]:
    return {str(key): int(value) for key, value in values.items() if int(value) > 0}


@dataclass(frozen=True)
class V21Config:
    """Configuration for one deterministic Version 2.1 episode."""

    horizon_minutes: float = 120.0
    turnaround_minutes: float = 5.0
    planner_method: str = "pgbm_initial_bruteforce_v1"
    max_pending_tasks: int = 8
    max_candidate_plans: int = 50000
    recourse_enabled: bool = True
    one_for_one_replacement: bool = True
    cache_enabled: bool = True
    max_cache_slots: int = 1
    cache_selection_policy: str = "configured_most_probable"
    cache_item_prior: Optional[Mapping[str, float]] = None

    def validate(self) -> None:
        self.as_v2_config().validate()
        if self.max_cache_slots < 0 or self.max_cache_slots > 1:
            raise ValueError("V2.1 currently supports zero or one cache slot")
        if self.cache_selection_policy != "configured_most_probable":
            raise ValueError("V2.1 currently supports configured_most_probable cache selection")
        if self.cache_item_prior is not None:
            if any(float(value) < 0.0 for value in self.cache_item_prior.values()):
                raise ValueError("cache item prior values must be non negative")
            if not any(float(value) > 0.0 for value in self.cache_item_prior.values()):
                raise ValueError("cache item prior must contain a positive value")

    def as_v2_config(self) -> V2Config:
        return V2Config(
            horizon_minutes=self.horizon_minutes,
            turnaround_minutes=self.turnaround_minutes,
            planner_method=self.planner_method,
            max_pending_tasks=self.max_pending_tasks,
            max_candidate_plans=self.max_candidate_plans,
            recourse_enabled=self.recourse_enabled,
            one_for_one_replacement=self.one_for_one_replacement,
        )

    def as_dict(self) -> Dict[str, object]:
        values = asdict(self)
        values["cache_item_prior"] = (
            dict(self.cache_item_prior) if self.cache_item_prior is not None else None
        )
        return values


@dataclass(frozen=True)
class CacheLoadDecision:
    """Evidence for the dispatch time reserve loading decision."""

    mission_id: str
    uav_id: str
    trigger_time: float
    selected_item: Optional[str]
    loaded: bool
    reason: str
    committed_parcels: int
    cache_slots_available: int
    committed_mass: float
    cache_mass: float
    energy_without_cache: Optional[float]
    energy_with_cache: Optional[float]
    energy_overhead: float
    energy_margin: Optional[float]
    return_time: Optional[float]

    @property
    def loaded_parcels(self) -> int:
        return 1 if self.loaded else 0

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class MissionCacheState:
    """Mutable reserve and released inventory state for one mission."""

    mission_id: str
    uav_id: str
    loaded_at: float
    cache_inventory: Dict[str, int] = field(default_factory=dict)
    released_inventory: Dict[str, int] = field(default_factory=dict)
    used_inventory: Dict[str, int] = field(default_factory=dict)

    @property
    def remaining_cache_parcels(self) -> int:
        return sum(max(0, int(value)) for value in self.cache_inventory.values())

    @property
    def used_cache_parcels(self) -> int:
        return sum(max(0, int(value)) for value in self.used_inventory.values())

    def as_dict(self) -> Dict[str, object]:
        return {
            "mission_id": self.mission_id,
            "uav_id": self.uav_id,
            "loaded_at": self.loaded_at,
            "cache_inventory": _mapping_dict(self.cache_inventory),
            "released_inventory": _mapping_dict(self.released_inventory),
            "used_inventory": _mapping_dict(self.used_inventory),
            "remaining_cache_parcels": self.remaining_cache_parcels,
            "used_cache_parcels": self.used_cache_parcels,
        }


@dataclass(frozen=True)
class CacheCandidateEvidence:
    """Cache classification for one ordinary V2 replacement candidate."""

    uav_id: str
    displaced_task_id: str
    new_task_id: str
    cache_match: bool
    cache_available: Mapping[str, int]
    released_available: Mapping[str, int]
    displaced_inventory: Mapping[str, int]
    cache_used: Mapping[str, int]
    released_used: Mapping[str, int]
    residual_demand: Mapping[str, int]
    source: str
    reason: str

    @property
    def cache_assisted(self) -> bool:
        return sum(int(value) for value in self.cache_used.values()) > 0

    def as_dict(self) -> Dict[str, object]:
        return {
            "uav_id": self.uav_id,
            "displaced_task_id": self.displaced_task_id,
            "new_task_id": self.new_task_id,
            "cache_match": self.cache_match,
            "cache_assisted": self.cache_assisted,
            "cache_available": _mapping_dict(self.cache_available),
            "released_available": _mapping_dict(self.released_available),
            "displaced_inventory": _mapping_dict(self.displaced_inventory),
            "cache_used": _mapping_dict(self.cache_used),
            "released_used": _mapping_dict(self.released_used),
            "residual_demand": _mapping_dict(self.residual_demand),
            "source": self.source,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class V21RecourseDecision:
    """V2 recourse trace enriched with cache evidence."""

    decision: RecourseDecision
    cache_match: bool
    cache_assisted: bool
    cache_used: Mapping[str, int]
    cache_source: str
    candidates: Tuple[CacheCandidateEvidence, ...]

    def as_dict(self) -> Dict[str, object]:
        values = self.decision.as_dict()
        values.update(
            {
                "cache_match": self.cache_match,
                "cache_assisted": self.cache_assisted,
                "cache_used": _mapping_dict(self.cache_used),
                "cache_source": self.cache_source,
                "cache_candidates": [candidate.as_dict() for candidate in self.candidates],
            }
        )
        return values


@dataclass(frozen=True)
class V21EpisodeResult:
    """Canonical V2 metrics plus cache specific evidence."""

    base_result: V2EpisodeResult
    cache_load_decisions: Tuple[CacheLoadDecision, ...] = ()
    cache_recourse_decisions: Tuple[V21RecourseDecision, ...] = ()
    cache_loaded_parcels: int = 0
    cache_used_parcels: int = 0
    cache_returned_parcels: int = 0
    cache_match_count: int = 0
    cache_hit_count: int = 0
    cache_assisted_count: int = 0
    cache_energy_overhead: float = 0.0
    cache_load_rejections: Mapping[str, int] = field(default_factory=dict)
    cache_miss_reasons: Mapping[str, int] = field(default_factory=dict)

    @property
    def cache_hit_rate(self) -> float:
        denominator = self.base_result.accepted_replacements
        return self.cache_hit_count / denominator if denominator else 0.0

    def __getattr__(self, name: str):
        """Keep the ordinary V2 metric surface available to callers."""

        return getattr(self.base_result, name)

    def as_dict(self) -> Dict[str, object]:
        values = self.base_result.as_dict()
        values.update(
            {
                "cache_load_decisions": [decision.as_dict() for decision in self.cache_load_decisions],
                "cache_recourse_decisions": [decision.as_dict() for decision in self.cache_recourse_decisions],
                "cache_loaded_parcels": self.cache_loaded_parcels,
                "cache_used_parcels": self.cache_used_parcels,
                "cache_returned_parcels": self.cache_returned_parcels,
                "cache_match_count": self.cache_match_count,
                "cache_hit_count": self.cache_hit_count,
                "cache_assisted_count": self.cache_assisted_count,
                "cache_hit_rate": self.cache_hit_rate,
                "cache_energy_overhead": self.cache_energy_overhead,
                "cache_load_rejections": dict(self.cache_load_rejections),
                "cache_miss_reasons": dict(self.cache_miss_reasons),
            }
        )
        return values
