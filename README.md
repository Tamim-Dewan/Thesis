# PGBM Thesis and Simulation

This repository contains the thesis sources, the reproducible PGBM simulation,
and a separate heiDATA reference benchmark.

## Repository layout

- `Research Source/` contains the thesis report, mathematical formulations,
  figures, and working drafts.
- `docs/` contains project scope and implementation specifications.
- `Simulation/pgbm_sim/` contains the main deterministic simulator.
- `Simulation/heidata_benchmark/` contains the separate source faithful mesh
  and OSM benchmark. It does not modify the main simulator.
- `Simulation/data/` contains local templates and benchmark assets.
- `Simulation/tests/` contains tests for the main simulator and benchmark.
- `Simulation/results/` contains generated scenarios, reports, metrics, and
  visual previews. See its README for the artifact groups.
- `PROJECT_CONTEXT.md` records the current working plan and decisions.

## Initial no recourse run

The first baseline run plans only tasks already detected by the selected
planning time. The default task detection window ends at time `30`, so the
initial run starts at time `30` and disables recourse:

```bash
python3 Simulation/run_simulation.py \
  --mode du_outdoor --severity moderate --seed 20260924 \
  --task-count 6 --uav-count 3 --start-time 30 \
  --planner initial_snapshot_greedy_v1 --no-recourse \
  --output Simulation/results/pgbm_v1_two_hour_experiments/visualizations/initial_solution_snapshot_2026-09-27/du_outdoor_initial_solution_report.json
```

Use `--mode synthetic` for the fully generated environment.

The approved DU and synthetic snapshot inputs are also available as one
reproducible run manifest:

~~~bash
python3 Simulation/run_initial_snapshot.py
~~~

## Tests

```bash
python3 -m pytest -q Simulation
```

The current planner is an initial heuristic baseline. It is not the final
mathematical PGBM optimizer. Initial Solution V1 is the preserved no-recourse
reference, while Version 2 adds a separate formulation-aligned one-for-one
task replacement recourse path under `Simulation/pgbm_sim/v2/`.
