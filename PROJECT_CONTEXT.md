# Project Context

## Objective

Complete the formulation-aligned PGBM simulation study through Initial Solution V1 and Version 2. V1 is the preserved no-recourse reference. V2 will implement one-for-one active-mission task-replacement recourse, run paired with V1 on the same seeded 120-minute DU and synthetic scenarios, and produce a comparative findings report. Target phase start: 2026-09-28.

## Scope and Non-goals

In scope: the preserved V1 reference, formulation-faithful V2 one-for-one task replacement recourse, reproducible 120-minute event-driven runs, paired multiple-seed comparisons, UAV/task-load sensitivity experiments, recourse decision traces, runtime profiling, and the V2 comparative report. V2 must follow the full report and `problem_formulation_v5.tex` recourse rule rather than introduce a new routing interpretation.

Non-goal for this phase: reserve inventory or speculative future inventory, multiple-task replacement, full fleet reoptimization, base reload during an active mission, an exact mathematical optimizer, L’Aquila execution, heiDATA mission planning, and high fidelity physical modelling.

## Success Criteria

- DU and synthetic environments pass the readiness checks.
- The initial algorithm and its assumptions are documented.
- Both environments produce reproducible allocations, feasible routes, and execution results.
- A visual output makes task selection, UAV assignment, route, service, and return understandable.
- Limitations and deferred recourse work are clearly recorded.
- Results are aggregated across multiple seeds rather than inferred from one run.
- The effect of UAV count and task load is reported separately from the main baseline.
- Total runtime and planner bottlenecks are measured so the next efficient solution has an evidence-based target.
- V1 remains reproducible and unchanged after V2 is added.
- V2 accepts a new task only through a feasible one-for-one replacement with positive service-value gain, or places it in the waiting queue.
- Completed route prefixes, completed tasks, current onboard inventory, payload, energy reserve, collision-aware routing, and return-to-base feasibility are respected in every recourse decision.
- Paired V1 and V2 results use identical environment, task-load, fleet-size, and seed combinations so improvements are attributable to recourse.
- The V2 report explains the recourse mechanism before presenting comparative results and separates operational gains from runtime overhead.

## Constraints

- Preserve the current dirty worktree and existing user files.
- Keep source-faithful heiDATA evidence separate from synthetic simulation assumptions.
- Do not describe the initial solution as the final mathematical PGBM optimizer.
- Use the existing collision-aware routing layer where possible.
- Keep the first algorithm deterministic, simple, and easy to inspect.
- Use a configurable arrival-rate profile with high intensity in minutes 0-40, medium intensity in minutes 40-80, and low intensity in minutes 80-120.
- Use the same seeded arrival schedule when comparing planners or configuration variants, unless an experiment explicitly studies a different load.
- Use the current date, 2026-09-28, for this audit checklist.

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
- [x] 6. Implement PGBM Initial Solution V1 from the full report and
  `problem_formulation_v5.tex`. Completed on 2026-09-27.
  - [x] Freeze the configurable V1 assumptions, including the default `3:2:1`
    phase weights and five minute base turnaround.
  - [x] Build the equation to code mapping for assignment, completion value,
    routing, payload, and energy.
  - [x] Implement the seeded two hour event clock and high, medium, and low
    task arrival phases.
  - [x] Implement joint bounded brute force assignment and task ordering for
    each dispatch decision without active mission recourse or rerouting.
  - [x] Implement the UAV lifecycle, fixed route execution, queue handling,
    base turnaround, and complete event log.
  - [x] Add planner, route, candidate enumeration, queue, and whole run timing.
  - [x] Verify the planner against hand checked cases and the existing route
    and execution contracts.
- [x] 7. Run the multi-seed experiment and bottleneck study. Completed on 2026-09-27.
  - [x] Run the main 120-minute arrival profile over multiple seeds and aggregate
    served tasks, deferred tasks, completion value, delay, distance, energy,
    safe return, and queue backlog.
  - [x] Repeat controlled variants with different UAV counts and task loads,
    keeping the scenario seed comparable across configurations.
  - [x] Measure total run time, planner time per dispatch, candidate counts,
    and route-evaluation time where available.
  - [x] Identify the dominant runtime and feasibility bottlenecks and write the
    findings report before selecting a more efficient solution.
- [x] 8. Produce the findings report. Completed on 2026-09-27.
  - [x] Summarize the algorithm, simulation assumptions, and provenance.
  - [x] Present multi-seed aggregates for Synthetic and DU.
  - [x] Present UAV count and task load sensitivity results.
  - [x] Present runtime scaling and the dominant bottlenecks.
  - [x] Record limitations, validity boundaries, and the deferred recourse plan.
- [x] 9. Replace the small V1 evidence with the heavy experiment report. Completed on 2026-09-27.
  - [x] Confirm the agreed matrix: Synthetic and DU, 30/60/90 tasks, 2/3/4 UAVs, and 10 seeds.
  - [x] Run pilot cases and confirm that the workload is executable.
  - [x] Run the complete 180 row matrix and preserve raw CSV evidence.
  - [x] Aggregate mean, standard deviation, range, queue, service, payload, runtime, and search evidence.
  - [x] Update the Markdown and LaTeX report in `Experiment Reports/V1/`.
  - [x] Compile and visually inspect the new PDF, then run the relevant tests.
- [x] 10. Implement and evaluate formulation-aligned PGBM Version 2 recourse. Completed on 2026-09-28.
  - [x] Write the V2 design specification in `docs/specs/0007-pgbm-v2-task-replacement-recourse.md`.
  - [x] Preserve the V1 namespace, outputs, and behavior while adding a separate V2 execution path.
  - [x] Track runtime task state, active mission state, completed route prefix, current onboard inventory, payload, energy, and waiting queue.
  - [x] Implement one-for-one candidate replacement, remaining-route recalculation, delta service value, positive-gain acceptance, and displaced-task queueing.
  - [x] Add unit and integration tests for accepted, rejected, infeasible, tied, and deterministic recourse cases.
  - [x] Run the paired 240-configuration matrix: two environments, three task loads (30, 60, 90), four fleet sizes (3, 5, 8, 10), and ten seeds (101 through 110), for V1 and V2; merge 480 metrics rows and 240 decision traces.
  - [x] Produce, compile, and visually verify the V2 report in the V1 report flow with V2 core features at the top and V1 versus V2 comparison tables and findings.

## Active Decisions

- D-002 — 2026-09-26 — The immediate goal is a DU and synthetic initial allocation and routing run without recourse. Status: Active.
- D-003 — 2026-09-26 — The first approved solution is a transparent `t = 30` snapshot. It ranks eligible pending tasks by current exponential service value, greedily appends each task to a feasible UAV tour, preserves payload and energy reserve, uses collision-aware routing, and excludes recourse. Status: Active.
- D-004 — 2026-09-26 — The future continuous simulation should use a seeded event-driven clock over a 120-minute window, a reproducible task arrival schedule, a complete decision event log, and a separate replay visualizer. Status: Proposed for future work.
- D-005 — 2026-09-27 — The canonical problem formulation for Initial Solution V1 is the full report together with `Research Source/Problem Formulation/problem_formulation_v5.tex`. The open `mathematical_model.tex` and other formulation drafts are excluded from this implementation unless explicitly selected later. V1 uses the severity based exponential service value at task completion, joint task allocation and three dimensional routing, payload and energy feasibility, and no active mission recourse or rerouting. Status: Active.
- D-006 — 2026-09-27 — Initial Solution V1 will run over a seeded two hour event driven horizon. Dynamic task arrivals are included in the task queue. The planner is called at dispatch opportunities, such as task detection when an idle UAV is available and UAV return or resupply completion. A dispatched mission remains fixed until completion; newly arriving tasks cannot replace or reroute an active mission in V1. Status: Active.
- D-007 — 2026-09-27 — The 120-minute scenario will use a phase-based task detection/request arrival profile: high rate from minutes 0-40, medium rate from minutes 40-80, and low rate from minutes 80-120. The initial relative default is `3:2:1`; total task load remains a separate configurable experiment factor, and all schedules are seed-controlled. Status: Active.
- D-008 — 2026-09-27 — V1 conclusions will be based on multiple seeded runs and controlled sensitivity experiments, including changes to UAV count and task load. The same seed and arrival schedule should be reused across comparable algorithm/configuration variants. Status: Active.
- D-009 — 2026-09-27 — Runtime is an experiment outcome, not only an implementation detail. The study will record whole-run time and planner-level timing, then identify bottlenecks in candidate enumeration, route evaluation, feasibility checks, or execution for the later efficient solution. Status: Active.
- D-010 — 2026-09-27 — The first executable V1 assumption is a configurable five minute base turnaround for resupply and recharge, with sufficient base supply. It is an experiment assumption, not a validated physical claim. Status: Active.
- D-011 — 2026-09-27 — The earlier small V1 result set is not sufficient evidence. The canonical replacement experiment uses 180 rows: two environments, three task loads (30, 60, 90), three fleet sizes (2, 3, 4), and ten seeds (101 through 110). It keeps the existing individual task model, 3:2:1 phase quotas, 2 kg UAV payload limit, five minute turnaround, and no recourse. Status: Completed for V1; retain as the reference protocol for later comparisons.
- D-012 — 2026-09-28 — V2 is a separate strangler implementation and must not modify V1 behavior or overwrite V1 evidence. The V2 contract is the one-for-one active-mission replacement rule from the full report and `problem_formulation_v5.tex`. Status: Active.
- D-013 — 2026-09-28 — V2 uses only current committed onboard inventory when checking a replacement task. It does not add reserve inventory, base reload, or speculative future demand; those are deferred to V3. Status: Active.
- D-014 — 2026-09-28 — The paired V2 comparison uses the current heavy V1 matrix protocol: Synthetic and DU outdoor, task loads 30, 60, and 90, fleet sizes 3, 5, 8, and 10, seeds 101 through 110. Each configuration runs once with V1 and once with V2. Status: Active.

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
- `Research Source/Problem Formulation/problem_formulation_v5.tex`
- `Simulation/results/`

## Previous Work

The repository was inventoried on 2026-09-26. The current source, specifications, thesis material, tests, generated artifacts, and Git state are known well enough to begin the initial run preparation. A correctness and organization pass then added task eligibility filtering, battery reserve enforcement, scenario execution time propagation, a no recourse run option, a root project map, and a results index.

Task 1 completed on 2026-09-26. The inventory found 161 files under `Simulation`, 15 documentation files, 48 research-source files, 14 simulation test modules, and 62 result artifacts. The main entry points are `run_simulation.py`, `run_experiments.py`, `run_phase1.py`, and the rendering scripts. The complete-episode CLI exposes `synthetic`, `du_outdoor`, `real_building`, and `laquila_informed`; the experiment CLI supports `synthetic`, `du_outdoor`, and `laquila_informed`. The worktree remains dirty with tracked mathematical-model deletions and untracked current project material.

## Current Implementation

The repository contains deterministic synthetic and DU scene generation, task generation, scenario export, collision-aware routing, the original snapshot heuristics, the formulation aligned Initial Solution V1 planner, event driven execution, and visual rendering. Initial Solution V1 now uses joint bounded brute force assignment and task ordering, completion time service value, payload evolution, four energy components, collision aware routes, and fixed active missions over a seeded 120 minute horizon. The event runner records task detection, dispatch, arrival, service completion, return, and base turnaround events. The heavy V1 replacement experiment is complete with 180 validated rows, preserved raw parts, phase counts, and bounded search truncation evidence.

The repeated experiment runner now separates the initial comparison from the
current one replacement recourse fixture. Recourse is disabled by default,
`--with-recourse` enables the fixture, and each metrics row records
`recourse_enabled`. The new evidence files are
`Simulation/results/research_metrics_initial.csv` and
`Simulation/results/research_metrics_recourse.csv`.

The formulation source decision is now explicit. Initial Solution V1 follows
the full report and `problem_formulation_v5.tex`. Its primary value is
the severity based exponential service value evaluated at task completion.
The harmonic value formulation in the open `mathematical_model.tex` is not
part of V1. The governing planner contract is being extended in place in
`docs/specs/0005-pgbm-planner-execution.md`. The canonical V1 experiment
contains 240 rows from ten seeds across Synthetic and DU outdoor environments.
The generated report is `docs/reports/pgbm_v1_simulation_findings.md`,
with the LaTeX source and PDF in `Experiment Reports/V1/`. It identifies route
evaluation as the dominant measured runtime cost, especially in DU outdoor,
and records 75 dispatches that reached the 50,000 candidate search bound.

The V2 implementation is complete beside V1. It observes a new
detected task only when all responder UAVs are active, evaluates one-for-one
replacement of an uncompleted task on each active mission, keeps the completed
route prefix fixed, recalculates the remaining collision-aware route, checks
current onboard inventory and energy reserve, and accepts only the largest
positive service-value gain. The displaced task returns to the waiting queue.
The displaced task returns to the waiting queue. The paired heavy matrix has
480 validated metrics rows and 240 deterministic decision traces; the Bangla
comparative report is compiled and visually verified. The full Simulation test
suite passes with 121 tests.

## Simulation Direction

The simulation will not generate uncontrolled live randomness inside the visualizer. A seeded scenario will define task arrival events over `t = 0` to `t = 120`, with a configurable high-rate phase in minutes 0-40, medium-rate phase in minutes 40-80, and low-rate phase in minutes 80-120. Initial Solution V1 will update task and UAV state at task detection, planner dispatch, arrival, service completion, return, and resupply or recharge events. A dispatched route remains fixed. The event log will record newly arrived tasks that wait because all UAVs are active, without applying recourse or rerouting. Comparable algorithms and configuration variants will receive the same seed-controlled schedule. A separate visualizer will replay the log in fast, step-by-step, or adjustable-speed modes.

## Next Implementation

The approved single snapshot phase, visual replay improvements, separated
initial experiment comparison, Initial Solution V1 implementation, the heavy
V1 experiment report, and the V2 one-for-one task replacement recourse study
are complete. The current evidence includes the paired V1 versus V2 matrix,
decision traces, and the compiled comparative report. V3 reserve inventory and
broader reassignment remain deferred.

## Open Questions and Blockers

- Which energy coefficient defaults should be calibrated before reporting
  physical energy comparisons?
- At what task count or candidate limit should the bounded reference planner
  hand off to a scalable method?
- Should the next efficiency study compare V1 only, or add a dynamic version of
  the existing heuristic and nearest task baselines?
- Should the V2 report include a separate event-level recourse trace table in
  addition to the aggregate matrix? The design currently requires both event
  counts and aggregate performance metrics.

## Session Handoff

Environment readiness, the approved `t = 30` snapshot rule, the fixed manifest, the original planner, the report runner, the route renderer, and the improved step by step replay renderer are complete. Initial Solution V1 is implemented as a two hour event driven bounded brute force planner. The earlier small experiment and report are treated as historical evidence only. The canonical 240-row V1 matrix and the paired 480-row V1/V2 matrix ran successfully in both environments; raw parts, merged CSVs, manifests, Markdown reports, LaTeX sources, and the verified V2 PDF are preserved. The full Simulation suite passes with 121 tests. V2 recourse is complete; reserve inventory and broader reassignment remain deferred to V3.

The researcher selected the full report and `problem_formulation_v5.tex` as the
only formulation sources for Initial Solution V1. The next build must use
completion time service value and must not use the open harmonic formulation.
The researcher clarified that dynamic arrivals are required over a two hour
window. V1 will queue new tasks and plan them when UAVs are available, without
changing an active mission. The researcher then specified a high/medium/low
arrival-rate profile across the first, second, and third 40-minute blocks of
the horizon, requested multiple-seed comparisons and UAV/task-count sweeps,
and made runtime bottleneck identification a required part of the initial
study and findings report. The implementation now uses a configurable `3:2:1`
relative phase default and a configurable five minute base turnaround, with
both assumptions reported explicitly. The researcher then requested a stronger
replacement report with heavy experimental values. The agreed replacement
matrix is two environments times three task loads times three fleet sizes times
ten seeds, with the existing simple individual task model preserved.

The researcher then selected V2 recourse as the next core feature and
confirmed that the V2 report should follow the V1 report flow, put the V2 core
features at the top, and compare V1 and V2 using the same scenarios. The V2
specification was cross-checked and accepted. The implementation, paired heavy
matrix, decision traces, comparative report, local LaTeX compilation, visual
QA, and full test suite are complete. Reserve inventory and broader active
reassignment remain the next V3 design decision.

## Last Updated

2026-09-28
