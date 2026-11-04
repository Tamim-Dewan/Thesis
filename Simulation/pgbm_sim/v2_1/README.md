# PGBM Version 2.1

Version 2.1 is a separate execution path for testing cache aware recourse.
The canonical V1 and V2 runners are not changed.

At dispatch, the ordinary V2 planner first creates a feasible mission. If one
payload slot and enough payload mass remain, Version 2.1 selects one reserve
item from the configured item prior. The candidate is loaded only when the
full route still satisfies the energy reserve and horizon limits.

The reserve is loaded once at mission start. It is not refreshed in flight and
the runner does not inspect future task arrivals to choose it. A later active
mission replacement still uses the V2 one for one rule and accepts only a
feasible positive service value gain.

The result exposes separate evidence for reserve loading, cache matches, cache
use, partial assistance, ordinary inventory matches, and unused reserve parcels
returned with the UAV.

The default task generator uses a uniform non empty item subset, so the
default item prior is uniform and the configured item order is the tie break.
Experiments can pass `cache_item_prior` to test another prior without changing
the task arrival sequence.

The report package follows the V1 and V2 layout under
`Experiment Reports/V2.1/`. It contains the Bengali Markdown report, editable
XeLaTeX source, compiled PDF, build files, and four vector PDF figures under
`Experiment Reports/assets/v2_1/`. The package can be regenerated with
`Simulation/generate_pgbm_v21_report.py` from the repository root.
