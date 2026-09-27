# PGBM planner, routing, execution, and comparison

**Status**: Assumed

## Purpose

This slice connects a validated scenario to a reproducible research run. It
provides a resource-aware first planner, polygon collision-aware UAV routes,
discrete execution events, replacement-task recourse, and a transparent
nearest-task baseline. It does not claim to be the final mathematical PGBM
optimization solver; that formulation must be ratified against the thesis
equations before replacing the heuristic.

## Current contract

- `plan_tasks` consumes a saved/reproducible `Scenario` and `UAVConfig`.
- `plan_tasks` considers only pending tasks whose detection time is at or
  before the scenario execution start time; later tasks remain unassigned.
- `pgbm_heuristic_v1` prioritizes synthetic severity while respecting parcel
  count, payload weight, route feasibility, battery reserve, and return-to-base
  distance.
- `nearest_task_first` is the comparison baseline.
- Routes use exact polygon obstacle footprints, horizontal grid A*, and
  explicit vertical clearance checks. A route is infeasible when no valid
  altitude and horizontal path are available.
- `execute_plan` emits arrival, service completion, route infeasible, and
  return-to-base events.
- `apply_recourse` adds uniquely identified newly detected tasks and replans;
  duplicate task identifiers are rejected explicitly.
- `run_experiments.py` writes one comparable metrics row per seed and method.
- `run_simulation.py` writes a complete scenario plus plan, recourse, event,
  and metric report for one episode.
- `run_simulation.py --no-recourse` writes and executes only the initial plan.

## Acceptance criteria

- **AC-1**: Identical scenario, UAV configuration, routing configuration, and
  planner method produce identical plans.
- **AC-2**: Every served assignment respects payload and energy capacity and
  contains a route beginning and ending at the base.
- **AC-3**: A route segment cannot pass through an active mapped polygon or
  cuboid obstacle; elevated task sites are approached from above their roof
  or support surface.
- **AC-4**: Execution consumes route distance, speed, energy, and service time
  rather than recomputing straight-line legs.
- **AC-5**: Replacement tasks are reported as accepted or rejected and are
  never silently duplicated.
- **AC-6**: Repeated seeded runs produce comparable rows for the heuristic and
  baseline, including served tasks, deferred tasks, energy, delay, distance,
  replacement outcomes, and safe-return rate.
- **AC-7**: A future exact PGBM solver can replace the method implementation
  without changing the scenario, route, execution, or metrics contracts.

## Deferred decision

The exact PGBM objective, binary/integer variables, time discretization, and
solver choice remain a research decision. The current heuristic is an honest
working integration boundary for validating the environment and experiment
pipeline; it must not be presented as an optimality result.
