# PGBM planner, routing, execution, and comparison

**Status**: In Progress

## Purpose

This slice connects a validated scenario to a reproducible two hour earthquake
response experiment. It provides a formulation aligned initial solution, joint
assignment and route enumeration for small decision sets, collision aware UAV
routes, dynamic task arrivals, fixed active missions, repeated seeded runs, and
runtime evidence. It does not claim to be the final mathematical PGBM
optimization solver. Active mission recourse and rerouting remain deferred.

## Current contract

- `plan_tasks` consumes a saved/reproducible `Scenario` and `UAVConfig`.
- `plan_tasks` considers only pending tasks whose detection time is at or
  before the scenario execution start time; later tasks remain unassigned.
- `pgbm_initial_bruteforce_v1` evaluates joint task assignment and task order
  candidates for the current pending queue and available UAVs. It uses the
  completion time service value from the full report and
  `problem_formulation_v5.tex`, together with route, payload, energy, and safe
  return feasibility.
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
  Initial comparisons disable recourse by default. The current one replacement
  fixture is enabled only with `--with-recourse` and each metrics row records
  `recourse_enabled`.
- The V1 event runner uses a seeded 120 minute horizon. Task detection rate is
  high from minutes 0 to 40, medium from minutes 40 to 80, and low from
  minutes 80 to 120. The first configurable default uses relative weights
  `3:2:1` while separate task load experiments vary the total task count.
- The event runner calls the planner when a task batch arrives and an idle UAV
  is available, or when a UAV completes its base turnaround. A dispatched
  route remains fixed until the mission returns. New tasks wait in the queue.
- Multi seed experiment rows include task load, UAV count, dispatch count,
  queue backlog, planner runtime, route evaluation runtime, candidate counts,
  and total runtime. Visualization time is recorded separately from planner
  runtime.
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
- **AC-8**: An initial comparison does not inject replacement tasks unless
  recourse is explicitly enabled, and its output records that mode.
- **AC-9**: A V1 event run covers exactly the configured 120 minute horizon,
  emits seeded task detections in high, medium, and low arrival phases, and
  reproduces the same schedule for the same seed.
- **AC-10**: The V1 dispatcher plans only pending detected tasks and available
  UAVs, removes selected tasks from the queue, leaves unselected tasks queued,
  and never changes a dispatched active route.
- **AC-11**: The V1 reference planner evaluates joint assignment and task
  order candidates and ranks feasible candidates by the sum of severity based
  exponential service values at task completion, with deterministic tie breaks.
- **AC-12**: Every V1 mission respects route collision checks, payload count and
  mass, energy reserve, task service timing, and return to base before the
  horizon. Base turnaround resets the UAV for a later dispatch.
- **AC-13**: The experiment runner executes the Synthetic and DU environments
  over multiple seeds and controlled UAV count and task load variants, using
  comparable seeded inputs and writing one row per run configuration.
- **AC-14**: Runtime instrumentation separates whole run time, planner time,
  route evaluation time, candidate count, dispatch count, and peak queue size.
- **AC-15**: The findings report presents aggregate performance, sensitivity
  results, runtime scaling, dominant bottlenecks, assumptions, and deferred
  recourse work.

## V1 decision

Initial Solution V1 is an event driven, bounded brute force reference planner.
At each dispatch opportunity it enumerates assignment and task order candidates
for detected pending tasks and idle UAVs. Each candidate constructs a route from
the base through the ordered task waypoints and back to the base, then checks
payload, energy, service timing, collision free routing, and horizon feasibility.
The selected candidate maximizes

`sum_i s_i * exp(-lambda * (C_i - t_i))`

where `C_i` is the simulated completion time and `t_i` is the task detection
time. Deterministic task identifiers, lower energy, and shorter distance are
used as tie breaks. Active missions are immutable until return.

The event horizon is 120 minutes. The default arrival profile allocates task
detection times across three phases with relative rate weights `3:2:1` for
minutes `0:40`, `40:80`, and `80:120`. The profile and total task count are
configuration values. The first base turnaround assumption is a configurable
five minute resupply and recharge interval with sufficient base supply.

## Build plan

1. Extend task generation with a reproducible three phase arrival schedule and
   preserve the legacy uniform detection range for earlier snapshot tests,
   satisfying **AC-1**, **AC-9**.
2. Add the formulation aligned completion value, payload evolution, energy
   terms, deterministic candidate enumeration, and bounded search metadata,
   satisfying **AC-2**, **AC-3**, **AC-11**, **AC-12**.
3. Add the 120 minute event runner with task queue, UAV lifecycle, fixed active
   missions, base turnaround, and event logs, satisfying **AC-4**, **AC-10**,
   **AC-12**.
4. Extend metrics and the experiment runner for multiple seeds, Synthetic and
   DU scenarios, UAV count and task load variants, and separate runtime
   measurements, satisfying **AC-6**, **AC-13**, **AC-14**.
5. Add focused unit tests and run the full Simulation suite, satisfying
   **AC-1** through **AC-14**.
6. Run the experiment matrix, aggregate results, identify bottlenecks, and
   write the findings report, satisfying **AC-15**.

## Follow-up

- Calibrate the numeric energy coefficients against the available thesis
  assumptions before treating energy values as physical measurements.
- Replace bounded enumeration with a scalable method only after the runtime
  evidence identifies the dominant bottleneck.
- Add active mission recourse and rerouting after the V1 findings are stable.

## Deferred decision

The exact PGBM objective, binary/integer variables, time discretization, and
solver choice remain a research decision. The current heuristic is an honest
working integration boundary for validating the environment and experiment
pipeline; it must not be presented as an optimality result.
