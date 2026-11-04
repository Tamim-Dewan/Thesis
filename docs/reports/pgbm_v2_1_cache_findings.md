# PGBM Version 2.1 Cache Aware Recourse Findings

This is a separate evidence note for the cache aware Version 2.1 path. Canonical V1 and V2 evidence are not overwritten.

## Experimental contract

The V2 control and every V2.1 variant use the same seeded scenario. V2.1 loads at most one reserve parcel at dispatch, checks payload, energy reserve, route return, and horizon, then keeps the V2 one for one positive gain rule.

The water heavy prior is a sensitivity policy, not a field calibrated probability. The default uniform prior follows the current uniform non empty subset task generator.

## Aggregate performance

| Algorithm | Variant | Episodes | Objective | Delivery rate | Safe return | Energy | Mean delay |
| --- | --- | --- | --- | --- | --- | --- | --- |
| V2.1 | uniform | 240 | 17.2490 | 0.4896 | 1.0000 | 5679.4835 | 17.8556 |
| V2_control | v2_control | 240 | 17.0110 | 0.4817 | 1.0000 | 5613.9421 | 18.2312 |
| V2.1 | water_heavy_sensitivity | 240 | 17.3388 | 0.4925 | 1.0000 | 5704.7735 | 18.0681 |

## Paired core findings

Each V2.1 row below is compared with the V2 control from the identical environment, task load, fleet size, and seed.

| Variant | Paired episodes | Delta objective | Delta served | Delta deferred | Delta delay | Delta delivery | Delta energy | Cache energy overhead |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| uniform | 240 | 0.2380 | 0.2875 | -0.2875 | -0.3756 | 0.0078 | 65.5414 | 45.7640 |
| water_heavy_sensitivity | 240 | 0.3278 | 0.4542 | -0.4542 | -0.1631 | 0.0108 | 90.8314 | 89.5940 |

## Cache behavior

| Variant | Loaded | Used | Returned | Matches | Accepted hits | Hit rate | Cache energy overhead |
| --- | --- | --- | --- | --- | --- | --- | --- |
| uniform | 12.6333 | 1.4375 | 11.1958 | 5.7833 | 1.4375 | 0.1428 | 45.7640 |
| water_heavy_sensitivity | 12.4750 | 1.4792 | 10.9958 | 5.1167 | 1.4792 | 0.1479 | 89.5940 |

## Core interpretation

The control row is the reference for judging whether reserve inventory changes service performance rather than merely changing traces.
Cache loaded but unused parcels are reported as returned, so loading alone is not counted as a successful cache hit.
The reported cache hit rate is accepted cache hits divided by all accepted replacements; it is not the fraction of loaded parcels that were used.
A cache match is distinct from an accepted replacement. The replacement must still satisfy route, payload, energy, horizon, and positive gain checks.
Across this bounded matrix, both one-slot policies show a small service gain but return most loaded reserve parcels unused; the water-heavy sensitivity costs more cache energy. The evidence therefore supports retaining one slot and deferring a second slot or adaptive prior.

## Charts

* [Cache activity](<../../Simulation/results/pgbm_v2_1_cache_experiments/charts_bounded_workers8/cache_activity.html>)
* [Performance comparison](<../../Simulation/results/pgbm_v2_1_cache_experiments/charts_bounded_workers8/performance_comparison.html>)
* [Cache hit rate by environment](<../../Simulation/results/pgbm_v2_1_cache_experiments/charts_bounded_workers8/cache_hit_rate_by_environment.html>)
* [Cache energy overhead](<../../Simulation/results/pgbm_v2_1_cache_experiments/charts_bounded_workers8/cache_energy_overhead.html>)

## Evidence files

* Metrics CSV: `Simulation/results/pgbm_v2_1_cache_experiments/raw_metrics/`
* Decision traces: `Simulation/results/pgbm_v2_1_cache_experiments/decision_traces/`
* Configuration manifest: `Simulation/results/pgbm_v2_1_cache_experiments/manifests/pgbm_v2_1_cache_manifest_bounded_workers8.json`

## Limitations

The matrix does not establish a real world item probability. It compares a generator aligned uniform prior with one named sensitivity prior.
The planner bounds used for this evidence run are recorded in the manifest; results should be interpreted as bounded-search evidence rather than an unrestricted optimality claim.
The current implementation intentionally stops at one reserve slot. A second slot or adaptive prior should be added only if the matrix shows consistent benefit without unacceptable energy or return cost.
