# 0008. PGBM V2.1 cache-aware recourse

**Date**: 2026-10-07  
**Status**: Accepted for the first slice

## Summary

Version 2.1 adds a separate, bounded cache-aware recourse path beside the
canonical V1 and V2 implementations. After an ordinary V2 mission is planned,
the UAV may load at most one reserve parcel at dispatch. The reserve item is
selected from a configured prior, and loading is accepted only when payload
slots, payload mass, full-route energy plus reserve, return feasibility, and
the 120-minute horizon remain feasible.

The reserve is not chosen from undetected future tasks, is not reloaded during
flight, and does not change V2's one-for-one positive-gain replacement rule.
The implementation records cache loading, cache matches, cache-assisted
replacements, rejected cache candidates, and unused reserve parcels returned
with the UAV.

## Requirements

1. V1 and canonical V2 entry points, behavior, and evidence remain unchanged.
2. V2.1 supports zero or one cache slot; more than one slot is rejected until
   a separate policy is designed and evaluated.
3. The default cache item prior is uniform because the current task generator
   uses a uniform non-empty item subset. A water-heavy prior is allowed only as
   an explicitly labelled sensitivity policy, not as a calibrated probability.
4. Loading is attempted only after the ordinary mission route is feasible.
5. Loading must respect parcel count, payload mass, full route energy,
   configured energy reserve, return-to-base feasibility, and horizon.
6. Cache inventory and released displaced-task inventory are tracked separately
   from the ordinary committed inventory.
7. A cache match is not automatically a hit: the ordinary V2 candidate must
   still pass route, payload, energy, horizon, and positive service-value gain
   checks before acceptance.
8. Undetected future demand must not influence item selection or cache loading.
9. A reserve parcel that is loaded but not used is returned and counted as
   unused cache inventory, not as a successful hit.
10. Cache evidence is exported separately from ordinary V2 recourse evidence.

## Runtime contract

The cache-aware path wraps the V2 episode result and recourse decision types.
Its dispatch transition is:

1. Build the ordinary V2 mission.
2. Identify the configured most-probable item using deterministic item-order
   tie-breaking.
3. Check the free payload slot and remaining mass capacity.
4. Re-evaluate the full mission route with the reserve parcel included.
5. Check energy margin and return time against the reserve and horizon.
6. Load one parcel only when every guard passes; otherwise record the explicit
   rejection reason and dispatch the ordinary mission.
7. During later V2 recourse, classify whether the candidate uses cache or
   released displaced inventory, then apply the unchanged V2 acceptance rule.
8. At mission completion, count unused reserve inventory as returned.

The cache-specific trace includes the mission, UAV, trigger time, selected
item, load decision, rejection reason, committed and cache mass, energy before
and after loading, energy margin, return time, candidate source, and cache use.

## Experiment contract

V2 control and each V2.1 policy receive the same in-memory seeded scenario.
The completed evidence matrix uses:

- environments: `synthetic`, `du_outdoor`;
- task loads: 30, 60, 90;
- fleet sizes: 3, 5, 8, 10;
- seeds: 101 through 110;
- cache policies: `uniform` and `water_heavy_sensitivity`;
- bounded planner settings: `max_pending_tasks=4`,
  `max_candidate_plans=5000`;
- outputs: 720 metric rows, 240 paired traces, one manifest, one summary CSV,
  and four Plotly charts.

The paired comparison reports objective, served and deferred tasks, completion
delay, delivery rate, energy, safe return, cache load/use/return counts, cache
hit rate, assisted acceptance, miss reasons, and cache energy overhead.

## Acceptance criteria

1. Focused V2.1 tests cover item-prior tie-breaking, one-slot validation,
   disabled-control equivalence, deterministic traces, cache-hit distinction,
   capacity/energy/horizon guards, matrix output, and worker ordering.
2. The full `Simulation` test suite passes without changing canonical V1/V2
   behavior.
3. Every matrix scenario has exactly one V2 control row and one row for each
   V2.1 policy, with a shared scenario fingerprint.
4. The findings note explains paired core findings rather than filling result
   tables with unrelated prose.
5. A second slot or adaptive prior is added only when the evidence shows a
   consistent service benefit without unacceptable returned inventory or energy
   overhead.

## Decision after the first evidence matrix

The one-slot policy is retained. The uniform policy produced a mean objective
delta of `+0.238` and `+0.288` served tasks per episode versus its paired V2
control, with a `0.143` hit rate. The water-heavy sensitivity produced
`+0.328` and `+0.454`, with a `0.148` hit rate, but increased cache energy
overhead. Most loaded reserve parcels returned unused in both policies.

This supports keeping V2.1 as a one-slot experimental mechanism while
deferring a second slot and adaptive priors. The values are bounded-search
simulation evidence, not an unrestricted optimality claim or a calibrated
real-world item probability.
