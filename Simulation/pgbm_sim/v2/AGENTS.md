# PGBM Version 2 simulator context

This package contains the formulation aligned V2 event runner and its
one for one active mission task replacement recourse layer. It is a separate
execution path beside V1 and reuses the shared scene, task, routing, payload,
energy, and service value contracts.

## Commands

Run the full V2 paired matrix from `Simulation/` with:

```bash
PYTHONPATH=. python3 run_pgbm_v2_experiment_matrix.py \
  --modes synthetic du_outdoor \
  --task-counts 30 60 90 \
  --uav-counts 3 5 8 10 \
  --seeds 101 102 103 104 105 106 107 108 109 110
```

Run the focused V2 tests from the thesis root with:

```bash
python3 -m pytest -q Simulation/tests/v2 Simulation/tests/test_event_simulation.py
```

## Contract

V2 considers a newly detected task only when every responder UAV is active.
Each candidate changes one active mission by replacing one uncompleted task.
Completed work and the completed route prefix remain fixed. The revised suffix
must use the UAV's current onboard inventory, payload, route, energy reserve,
safe return, and horizon constraints. The largest positive remaining service
value gain is accepted; otherwise the new task stays in the waiting queue.

V2 does not add reserve inventory, base reload, multiple task replacement, or
full fleet reoptimization. Those changes belong to V3. V1 entry points and
canonical V1 result files must remain unchanged.

## Evidence

V2 metrics and decision traces belong under
`Simulation/results/pgbm_v2_recourse_experiments/`. The comparative report is
under `Experiment Reports/V2/`, and the governing contract is
`docs/specs/0007-pgbm-v2-task-replacement-recourse.md`.

_Drafted by /sync from the introducing change, worth a quick human pass._
