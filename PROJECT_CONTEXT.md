# Project Context

## Objective

Create and run a transparent initial task allocation and routing solution on the DU and synthetic simulation environments. The first run will exclude dynamic recourse. Target date: 2026-09-26.

## Scope and Non-goals

In scope: readiness checks for the DU and synthetic environments, the relevant report and problem formulation, a naive allocation and routing baseline, reproducible run inputs, and visual simulation outputs.

Non-goal for this phase: recourse, an exact mathematical optimizer, L’Aquila execution, heiDATA mission planning, and high fidelity physical modelling.

## Success Criteria

- DU and synthetic environments pass the readiness checks.
- The initial algorithm and its assumptions are documented.
- Both environments produce reproducible allocations, feasible routes, and execution results.
- A visual output makes task selection, UAV assignment, route, service, and return understandable.
- Limitations and deferred recourse work are clearly recorded.

## Constraints

- Preserve the current dirty worktree and existing user files.
- Keep source-faithful heiDATA evidence separate from synthetic simulation assumptions.
- Do not describe the initial solution as the final mathematical PGBM optimizer.
- Use the existing collision-aware routing layer where possible.
- Keep the first algorithm deterministic, simple, and easy to inspect.
- Use the current date, 2026-09-26, for this audit checklist.

## Project Plan

Plan status: Active  
Run date: 2026-09-26

- [x] 1. Check that the DU and synthetic environments are ready for an initial run. Approved on 2026-09-26.
  - [x] Run the relevant tests and readiness checks. Focused environment and execution checks passed: 54 passed, 2 L’Aquila tests deselected.
  - [x] Export or build one DU scenario and one synthetic scenario. Both exported valid `scenario.v2` inputs with six tasks.
  - [x] Inspect geometry, tasks, candidate drop off points, base, and route feasibility, then resolve the task timing issue. Full suite now passes: 84 passed.
- [x] 2. Read the report and problem formulation for the minimum initial logic. Approved on 2026-09-26.
  - [x] Record the task priority inputs and resource constraints that the initial solution will use.
  - [x] Define the naive allocation rule and route construction rule for the `t = 30` snapshot.
  - [x] Explicitly exclude recourse from this version.
- [x] 3. Organize the initial run. Completed on 2026-09-27.
  - [x] Prepare fixed seeds, scenario files, algorithm configuration, and output locations.
  - [x] Define a small output record for assignments, routes, service events, and metrics.
  - [x] Add or adapt visual rendering for tasks, UAV assignments, routes, service, and return.
- [x] 4. Run and explain the initial solution. Completed on 2026-09-27.
  - [x] Run it on the DU environment. Six of six tasks served, zero missed, safe return rate 1.000, total distance 1601.3 metres, 15 execution events.
  - [x] Run it on the synthetic environment. Six of six tasks served, zero missed, safe return rate 1.000, total distance 605.9 metres, 15 execution events.
  - [x] Inspect the visual and JSON results. Both reports contain assignments, collision aware routes, service events, and disabled recourse.
  - [x] Add a step by step replay. The report now stores planner decision traces, candidate UAV checks, assignment states, route states, and execution event replay frames.
  - [x] Record what worked, what failed, and what should become the next improvement. The snapshot is reproducible and feasible; the DU route is longer and slower than the synthetic route, and the next improvement should examine completion value, route ordering, and dynamic arrivals.
- [x] 5. Improve the initial replay visuals. Completed on 2026-09-27.
  - [x] Slow playback, remove the interactive trace legend, and replace the raw title with a structured status panel.
  - [x] Add route based UAV interpolation, planned versus travelled route styling, and active leg highlighting for both DU and synthetic outputs.
  - [x] Regenerate both HTML replays and add renderer regression tests.
  - [x] Add a five second visual hold and a task popup at every UAV arrival.

## Active Decisions

- D-002 — 2026-09-26 — The immediate goal is a DU and synthetic initial allocation and routing run without recourse. Status: Active.
- D-003 — 2026-09-26 — The first approved solution is a transparent `t = 30` snapshot. It ranks eligible pending tasks by current exponential service value, greedily appends each task to a feasible UAV tour, preserves payload and energy reserve, uses collision-aware routing, and excludes recourse. Status: Active.
- D-004 — 2026-09-26 — The future continuous simulation should use a seeded event-driven clock over a 120-minute window, a reproducible task arrival schedule, a complete decision event log, and a separate replay visualizer. Status: Proposed for future work.

## Superseded Decisions

- D-001 — 2026-09-26 — The audit-first plan was superseded by the initial-solution execution plan requested by the researcher. The audit material remains available for reference.

## Resources and Source Files

- `Simulation/README.md`
- `Simulation/AGENTS.md`
- `Simulation/pgbm_sim/`
- `Simulation/heidata_benchmark/`
- `docs/scope/`
- `docs/specs/`
- `Research Source/Full Report/`
- `Research Source/Problem Formulation/`
- `Simulation/results/`

## Previous Work

The repository was inventoried on 2026-09-26. The current source, specifications, thesis material, tests, generated artifacts, and Git state are known well enough to begin the initial run preparation. A correctness and organization pass then added task eligibility filtering, battery reserve enforcement, scenario execution time propagation, a no recourse run option, a root project map, and a results index.

Task 1 completed on 2026-09-26. The inventory found 161 files under `Simulation`, 15 documentation files, 48 research-source files, 14 simulation test modules, and 62 result artifacts. The main entry points are `run_simulation.py`, `run_experiments.py`, `run_phase1.py`, and the rendering scripts. The complete-episode CLI exposes `synthetic`, `du_outdoor`, `real_building`, and `laquila_informed`; the experiment CLI supports `synthetic`, `du_outdoor`, and `laquila_informed`. The worktree remains dirty with tracked mathematical-model deletions and untracked current project material.

## Current Implementation

The repository contains deterministic synthetic and DU scene generation, task generation, scenario export, collision-aware routing, a heuristic planner, execution, and visual rendering. The planner now assigns only tasks detected by the scenario execution start time, enforces the declared battery reserve, and records a decision trace for replay. The execution layer uses the scenario start time when no override is passed. Initial no recourse runs at start time 30 served 6 of 6 tasks in both DU and Synthetic, with 15 events and safe return rate 1.000. Step by step HTML replays show assignment choices first, then interpolate UAV movement along the planned route through flight, service, and return states. The replay keeps planned routes muted, travelled routes solid, and the active leg orange, with a structured status panel and no interactive trace legend.

## Future Simulation Direction

The long-term simulation will not generate uncontrolled live randomness inside the visualizer. A seeded scenario will define task arrival events over `t = 0` to `t = 120`. An event-driven simulator will update task and UAV state at task detection, planner decision, arrival, service completion, return, and recourse events. It will write a complete event log, and a separate visualizer will replay that log in fast, step-by-step, or adjustable-speed modes. This future direction is deferred until the single-snapshot initial solution is complete.

## Next Implementation

The approved single snapshot phase and its visual replay improvements are complete. The next concrete action is to inspect the regenerated DU and synthetic replays, including the five second arrival holds and task popups, then choose whether to compare this initial planner against the existing heuristic and nearest task baseline, improve the greedy scoring and route ordering, or begin the deferred event driven simulation design.

## Open Questions and Blockers

- How should the initial snapshot output directory distinguish DU and synthetic artifacts?
- Which route, service, and decision details must appear in the first visual output?
- Which exact event log fields should be retained now so the future replay visualizer can reuse them?

## Session Handoff

Environment readiness, the approved `t = 30` snapshot rule, the fixed manifest, the explicit initial planner, the report runner, the route renderer, and the improved step by step replay renderer are complete. Both DU and synthetic runs produced feasible six task solutions with safe return. The updated replays use slower playback, a structured status panel, compact controls, route based movement interpolation, five second arrival holds, and task serving popups. Focused renderer tests and the full 94 test simulation suite pass. The future 120-minute event driven simulator is recorded as deferred work. Recourse remains deferred from the current run.

## Last Updated

2026-09-27
