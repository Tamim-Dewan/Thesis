"""Reserve inventory loading and cache source accounting for V2.1."""

from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Optional, Sequence, Tuple

from ..planner import UAVAssignment, UAVConfig
from ..routing import RouteConfig, RoutePlanningError
from ..tasks import SurvivorTask
from ..v2.recourse import build_schedule
from .models import CacheCandidateEvidence, CacheLoadDecision, MissionCacheState


_EPSILON = 1e-9


def aggregate_inventory(tasks: Iterable[SurvivorTask]) -> Dict[str, int]:
    """Return the committed item count for a mission assignment."""

    inventory: Dict[str, int] = {}
    for task in tasks:
        for item, quantity in task.demand.items():
            inventory[item] = inventory.get(item, 0) + int(quantity)
    return {item: quantity for item, quantity in inventory.items() if quantity > 0}


def inventory_mass(inventory: Mapping[str, int], item_weights: Mapping[str, float]) -> float:
    return sum(float(item_weights.get(item, 0.0)) * int(quantity) for item, quantity in inventory.items())


def merge_inventory(*inventories: Mapping[str, int]) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for inventory in inventories:
        for item, quantity in inventory.items():
            result[item] = result.get(item, 0) + int(quantity)
    return {item: quantity for item, quantity in result.items() if quantity > 0}


def inventory_difference(total: Mapping[str, int], required: Mapping[str, int]) -> Dict[str, int]:
    """Return non negative inventory left after the required demand."""

    items = set(total) | set(required)
    return {
        item: max(0, int(total.get(item, 0)) - int(required.get(item, 0)))
        for item in items
        if max(0, int(total.get(item, 0)) - int(required.get(item, 0))) > 0
    }


def inventory_intersection(first: Mapping[str, int], second: Mapping[str, int]) -> Dict[str, int]:
    return {
        item: min(int(first.get(item, 0)), int(second.get(item, 0)))
        for item in set(first) | set(second)
        if min(int(first.get(item, 0)), int(second.get(item, 0))) > 0
    }


def demand_fits(required: Mapping[str, int], inventory: Mapping[str, int]) -> bool:
    return all(int(quantity) <= int(inventory.get(item, 0)) for item, quantity in required.items())


def subtract_inventory(inventory: Mapping[str, int], used: Mapping[str, int]) -> Dict[str, int]:
    result = {str(item): int(quantity) for item, quantity in inventory.items()}
    for item, quantity in used.items():
        result[item] = max(0, result.get(item, 0) - int(quantity))
    return {item: quantity for item, quantity in result.items() if quantity > 0}


def allocate_demand(
    demand: Mapping[str, int],
    released_pool: Mapping[str, int],
    cache_pool: Mapping[str, int],
) -> Tuple[Dict[str, int], Dict[str, int], Dict[str, int]]:
    """Consume released inventory first, then cache inventory.

    The residual quantity is deliberately returned.  A candidate may still
    be feasible through ordinary committed inventory, but that is not a full
    cache hit and must not be reported as one.
    """

    released_used: Dict[str, int] = {}
    cache_used: Dict[str, int] = {}
    residual: Dict[str, int] = {}
    for item, quantity in demand.items():
        required = int(quantity)
        from_released = min(required, int(released_pool.get(item, 0)))
        if from_released:
            released_used[item] = from_released
        required -= from_released
        from_cache = min(required, int(cache_pool.get(item, 0)))
        if from_cache:
            cache_used[item] = from_cache
        required -= from_cache
        if required:
            residual[item] = required
    return released_used, cache_used, residual


def choose_cache_item(
    item_types: Sequence[str],
    selection_policy: str = "configured_most_probable",
    item_prior: Optional[Mapping[str, float]] = None,
) -> Optional[str]:
    """Choose a reserve item without consulting future tasks.

    The default task generator is uniform over non empty subsets, so all
    configured item types have equal prior probability.  The configured item
    order is the deterministic tie break.  An explicit prior can be supplied
    for an experiment that has evidence for a different distribution.
    """

    if not item_types:
        return None
    if selection_policy != "configured_most_probable":
        raise ValueError("unsupported cache selection policy")
    prior = item_prior or {}
    return max(
        item_types,
        key=lambda item: (float(prior.get(item, 1.0)), -item_types.index(item)),
    )


@dataclass(frozen=True)
class CacheLoadResult:
    decision: CacheLoadDecision
    inventory: Mapping[str, int]
    cache_inventory: Mapping[str, int]
    schedule: object = None


def prepare_cache_load(
    environment,
    base,
    assignment: UAVAssignment,
    tasks: Sequence[SurvivorTask],
    now: float,
    horizon_minutes: float,
    uav_config: UAVConfig,
    route_config: RouteConfig,
    item_types: Sequence[str],
    item_weights: Mapping[str, float],
    decay_rate: float,
    enabled: bool,
    max_cache_slots: int,
    selection_policy: str,
    item_prior: Optional[Mapping[str, float]],
) -> CacheLoadResult:
    """Evaluate and, if feasible, prepare one dispatch time reserve parcel."""

    mission_id = "pending_mission"
    committed = aggregate_inventory(tasks)
    committed_parcels = sum(committed.values())
    committed_mass = inventory_mass(committed, item_weights)
    slots_available = max(0, uav_config.parcel_capacity - committed_parcels)

    def rejected(
        reason: str,
        selected_item: Optional[str] = None,
        cache_mass: float = 0.0,
        energy_without_cache: Optional[float] = None,
        energy_with_cache: Optional[float] = None,
        energy_margin: Optional[float] = None,
        return_time: Optional[float] = None,
    ) -> CacheLoadResult:
        decision = CacheLoadDecision(
            mission_id,
            assignment.uav_id,
            now,
            selected_item,
            False,
            reason,
            committed_parcels,
            slots_available,
            committed_mass,
            cache_mass,
            energy_without_cache,
            energy_with_cache,
            (energy_with_cache - energy_without_cache)
            if energy_with_cache is not None and energy_without_cache is not None
            else 0.0,
            energy_margin,
            return_time,
        )
        return CacheLoadResult(decision, committed, {}, None)

    if not enabled:
        return rejected("cache_disabled")
    if max_cache_slots == 0:
        return rejected("cache_slots_disabled")
    if slots_available < max_cache_slots:
        return rejected("no_free_slot")

    selected_item = choose_cache_item(item_types, selection_policy, item_prior)
    if selected_item is None:
        return rejected("no_configured_item")
    selected_weight = float(item_weights[selected_item])
    free_mass = uav_config.payload_weight_capacity - committed_mass
    if selected_weight > free_mass + _EPSILON:
        return rejected("payload_weight_capacity", selected_item, selected_weight)

    try:
        committed_schedule = build_schedule(
            environment,
            base,
            assignment.route,
            tasks,
            now,
            base,
            committed,
            0.0,
            0.0,
            uav_config,
            route_config,
            item_weights,
            decay_rate,
        )
    except (RoutePlanningError, ValueError) as error:
        return rejected("baseline_route_infeasible:{}".format(error), selected_item, selected_weight * max_cache_slots)
    cache_inventory = {selected_item: max_cache_slots}
    combined = merge_inventory(committed, cache_inventory)
    try:
        cache_schedule = build_schedule(
            environment,
            base,
            assignment.route,
            tasks,
            now,
            base,
            combined,
            0.0,
            0.0,
            uav_config,
            route_config,
            item_weights,
            decay_rate,
        )
    except (RoutePlanningError, ValueError) as error:
        return rejected(
            "route_infeasible:{}".format(error),
            selected_item,
            selected_weight * max_cache_slots,
            committed_schedule.additional_energy,
        )

    energy_without = committed_schedule.additional_energy
    energy_with = cache_schedule.additional_energy
    energy_margin = uav_config.energy_capacity - uav_config.reserve_energy - energy_with
    if energy_margin < -_EPSILON:
        return rejected(
            "energy_reserve",
            selected_item,
            selected_weight * max_cache_slots,
            energy_without,
            energy_with,
            energy_margin,
            cache_schedule.return_time,
        )
    if cache_schedule.return_time > horizon_minutes + _EPSILON:
        return rejected(
            "horizon",
            selected_item,
            selected_weight * max_cache_slots,
            energy_without,
            energy_with,
            energy_margin,
            cache_schedule.return_time,
        )

    decision = CacheLoadDecision(
        mission_id,
        assignment.uav_id,
        now,
        selected_item,
        True,
        "loaded",
        committed_parcels,
        slots_available,
        committed_mass,
        selected_weight * max_cache_slots,
        energy_without,
        energy_with,
        energy_with - energy_without,
        energy_margin,
        cache_schedule.return_time,
    )
    return CacheLoadResult(decision, combined, cache_inventory, cache_schedule)


def classify_candidate(
    candidate,
    state: MissionCacheState,
    task_by_id: Mapping[str, SurvivorTask],
) -> CacheCandidateEvidence:
    """Classify whether a V2 candidate is served by reserve inventory."""

    displaced = task_by_id.get(candidate.displaced_task_id)
    projection = candidate.projection
    if displaced is None or projection is None:
        return CacheCandidateEvidence(
            candidate.uav_id,
            candidate.displaced_task_id,
            candidate.new_task_id,
            False,
            {},
            {},
            {},
            {},
            {},
            {},
            "none",
            candidate.rejection_reason,
        )

    remaining_tasks = tuple(task_by_id[task_id] for task_id in projection.remaining_task_ids)
    scheduled = aggregate_inventory(remaining_tasks)
    extra = inventory_difference(projection.onboard_inventory, scheduled)
    cache_available = inventory_intersection(state.cache_inventory, extra)
    released_available = inventory_difference(extra, cache_available)
    displaced_inventory = dict(displaced.demand)
    releasable = merge_inventory(released_available, displaced_inventory)
    released_used, cache_used, residual = allocate_demand(
        task_by_id[candidate.new_task_id].demand,
        releasable,
        cache_available,
    )
    full_cache_pool = merge_inventory(releasable, cache_available)
    full_match = demand_fits(task_by_id[candidate.new_task_id].demand, full_cache_pool)
    cache_match = bool(cache_used) and full_match
    if cache_match and released_used:
        source = "cache_plus_released_inventory"
        reason = "cache_hit"
    elif cache_match:
        source = "cache"
        reason = "cache_hit"
    elif released_used and not residual:
        source = "released_inventory"
        reason = "released_inventory_match"
    elif not residual and candidate.feasible:
        source = "committed_inventory_reallocation"
        reason = "ordinary_inventory_match"
    elif cache_used:
        source = "partial_cache_assist"
        reason = "partial_cache_match"
    else:
        source = "none"
        reason = candidate.rejection_reason
    return CacheCandidateEvidence(
        candidate.uav_id,
        candidate.displaced_task_id,
        candidate.new_task_id,
        cache_match,
        cache_available,
        released_available,
        displaced_inventory,
        cache_used,
        released_used,
        residual,
        source,
        reason,
    )


def update_cache_state_after_acceptance(
    state: MissionCacheState,
    candidate,
    evidence: CacheCandidateEvidence,
    task_by_id: Mapping[str, SurvivorTask],
) -> None:
    """Consume cache units and reconcile released inventory after a commit."""

    projection = candidate.projection
    if projection is None:
        return
    remaining_before = tuple(task_by_id[task_id] for task_id in projection.remaining_task_ids)
    extra_before = inventory_difference(projection.onboard_inventory, aggregate_inventory(remaining_before))
    cache_available = inventory_intersection(state.cache_inventory, extra_before)
    cache_after = subtract_inventory(cache_available, evidence.cache_used)
    revised_tasks = tuple(task_by_id[task_id] for task_id in candidate.revised_task_ids)
    extra_after = inventory_difference(projection.onboard_inventory, aggregate_inventory(revised_tasks))
    state.cache_inventory = cache_after
    state.released_inventory = inventory_difference(extra_after, cache_after)
    for item, quantity in evidence.cache_used.items():
        state.used_inventory[item] = state.used_inventory.get(item, 0) + int(quantity)
