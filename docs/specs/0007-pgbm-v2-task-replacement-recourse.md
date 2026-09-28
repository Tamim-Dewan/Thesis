# 0007. PGBM V2 task replacement recourse

**Date**: 2026-09-28  
**Status**: Accepted

## Summary

Version 2 adds the limited task replacement recourse described by the selected full report and `problem_formulation_v5.tex`. When a new task arrives while all responder UAVs are active, the simulator evaluates one for one replacement of an uncompleted task in one active mission. Completed route segments remain fixed, the remaining route is recalculated, and a replacement is accepted only when it has positive remaining service value gain and satisfies item, route, energy, and safe return constraints.

The implementation will live beside the existing V1 path so that V1 remains an unchanged reference. Reserve inventory, base reload, full fleet reoptimization, and multiple task replacement remain outside V2 and are candidates for V3.

## Context

The current V1 event runner queues newly detected tasks while active missions continue unchanged. The existing replacement fixture adds a task and creates a new plan, but it does not represent the active mission state or the formulation rule for replacing one uncompleted task. V2 needs an executable recourse layer that can observe the mission at a recourse time and change only its uncompleted suffix.

The canonical sources define a narrow rule rather than a general rolling horizon optimizer. A new task is considered when all responder UAVs are deployed. For each active UAV and each uncompleted task, the planner builds a one for one replacement candidate. The newly arrived task must be serviceable from the UAV's current onboard items. The candidate route must remain feasible and return to the same physical base. The candidate is accepted only when the remaining mission value increases.

V1 already provides the scene, task, payload, energy, collision aware routing, event timing, and experiment contracts. A direct rewrite would risk changing the reference results. The safer change is a strangler implementation: add a V2 runtime and recourse layer that reuses the V1 environment, task, routing, and service value components, while preserving the V1 entry points and artifacts.

> Premise note: V2 must not become a full fleet reoptimizer or a base reload policy. Those changes would no longer implement the selected formulation. V2 is deliberately limited to one new task replacing one uncompleted task in one active mission.

## Requirements

**User stories**:

1. As a thesis researcher, I want a formulation aligned recourse episode so that I can measure whether a newly arriving high priority task should replace an uncompleted task.
2. As a thesis researcher, I want V1 and V2 to run on the same seeded scenario so that their differences are attributable to recourse.
3. As a thesis researcher, I want every accepted or rejected replacement recorded so that the result can be explained rather than treated as a black box.

**Acceptance criteria**:

1. **AC-1**: Existing V1 tests, entry points, artifacts, and results remain unchanged when V2 is not selected.
2. **AC-2**: The same scenario, seed, UAV configuration, route configuration, and V2 settings produce the same V2 event log, replacement decisions, routes, metrics, and report inputs.
3. **AC-3**: A recourse trigger is generated only for a newly detected task at or after its detection time, and the default active mission trigger is used when all responder UAVs are deployed.
4. **AC-4**: Each replacement candidate contains exactly one active UAV and exactly one uncompleted task to displace, together with the newly detected task.
5. **AC-5**: Completed tasks and the completed route prefix of the selected UAV cannot be changed by a recourse decision.
6. **AC-6**: A replacement is considered item feasible only when every required item quantity of the new task is available in the UAV's actual remaining onboard inventory. V2 does not add reserve inventory or future task information.
7. **AC-7**: The candidate remaining route is recalculated from the recourse state through the remaining task drop off waypoints and back to the same physical base. Every route leg uses the existing collision aware routing contract.
8. **AC-8**: A candidate is rejected when its remaining payload, carried mass evolution, travel time, service time, energy reserve, route feasibility, or return to base violates the selected configuration or 120 minute horizon.
9. **AC-9**: For every feasible candidate, the simulator calculates `J_old`, `J_new`, and `delta_J = J_new - J_old` using completion time service value. The best positive `delta_J` is accepted. If no positive candidate exists, active missions remain unchanged and the new task enters the waiting queue.
10. **AC-10**: When a replacement is accepted, the displaced task enters the waiting queue, the new task enters the selected active mission, and no task can be completed twice or assigned to two UAVs at the same time.
11. **AC-11**: V2 records a complete recourse decision trace, including trigger time, candidate UAV, displaced task, item feasibility, route feasibility, energy feasibility, old value, new value, gain, acceptance, and queue changes.
12. **AC-12**: V2 reports episode service value once per task using final completion times and separately reports event level replacement gains, avoiding objective double counting across replans.
13. **AC-13**: The V2 experiment runner executes the paired Synthetic and DU outdoor matrix using task loads 30, 60, and 90, UAV counts 3, 5, 8, and 10, and seeds 101 through 110. Each V2 run receives the same scenario and task realization as its V1 counterpart.
14. **AC-14**: V2 metrics include V1 versus V2 service value, served tasks, dropped parcels, delay, deferred tasks, distance, energy, safe return, runtime, recourse triggers, accepted replacements, rejected replacements, replacement gain, displaced tasks, and rejection reasons.
15. **AC-15**: The V2 report follows the V1 report flow, presents the V2 core features at the top, compares V1 and V2 results, explains each major result table, and records limitations and the V3 reserve inventory boundary.

## Options considered

### Option 1: Modify the V1 event runner in place

This option would add active replacement logic directly to the existing V1 event loop.

**Pros**:

1. Fewer files and less initial plumbing.
2. Existing event helpers could be reused immediately.

**Cons**:

1. V1 reference behavior could change silently.
2. It would mix fixed mission execution with active mission replacement and make comparison harder to audit.

### Option 2: Add a V2 strangler layer around shared V1 components

This option adds V2 runtime state, recourse evaluation, event execution, experiment output, and tests in V2 specific modules while reusing the existing scene, task, routing, and service value contracts.

**Pros**:

1. Preserves V1 as a stable reference.
2. Matches the formulation boundary without copying the whole simulator.
3. Allows V3 inventory extensions to build on a clear runtime state.

**Cons**:

1. Some state and event adapters are needed.
2. V1 and V2 outputs must be maintained separately.

### Option 3: Replace the planner with a full fleet rolling horizon optimizer

This option would reoptimize all active and waiting tasks after every event.

**Pros**:

1. It could express a broader dynamic planning problem.

**Cons**:

1. It does not implement the selected one for one formulation rule.
2. It would obscure the effect of the intended recourse mechanism.
3. It would multiply the existing bounded route search cost before V1's bottleneck is addressed.

## Decision

**Chosen option**: Option 2, add a V2 strangler layer around shared V1 components.

V2 will implement formulation aligned one for one active mission task replacement. It will preserve completed work, reuse the existing route builder to recalculate only the remaining route, use actual onboard committed items without adding reserve inventory, accept only a positive remaining service value gain, and return displaced tasks to the waiting queue.

**Implementation skills**: `plotly` (`davila7/claude-code-templates`, `/Users/_d-one_/Desktop/Thesis/.agents/skills/plotly/`)

## Rationale

Option 2 is the smallest implementation that is faithful to the selected formulation and safe for the existing V1 evidence. The formulation explicitly limits recourse to one active UAV and one uncompleted task, keeps completed mission work fixed, checks existing onboard items, recalculates a feasible route back to the same base, and accepts only positive gain. A full fleet replan or a return to base for reload would change the research question.

The shared V1 components already encode the environment provenance, task drop off waypoints, service value, collision checks, payload limits, energy coefficients, and safe return convention. The V2 layer therefore needs to add state and decision history, not a second environment or a different routing concept.

## Feature design

**Data model sketch**:

1. `TaskRuntimeState`: task identifier, status, detection time, completion time, assigned UAV, and remaining demand. The immutable task definition remains in the scenario.
2. `UAVRuntimeState`: UAV identifier, status, current time, current position or current route link, completed route prefix, remaining route, remaining task identifiers, onboard inventory by item type, onboard payload mass, remaining energy, and mission identifier.
3. `MissionState`: mission identifier, UAV identifier, original task order, completed task identifiers, remaining task order, route polyline, route distance, estimated completion times, and return time.
4. `RecourseDecision`: decision identifier, trigger time, new task identifier, candidate UAV, displaced task identifier, item feasibility, route feasibility, energy feasibility, `J_old`, `J_new`, `delta_J`, accepted flag, rejection reason, and queue changes.
5. `V2EpisodeResult`: final task outcomes, final UAV outcomes, event log, mission history, recourse history, episode metrics, and configuration metadata.

There is no database. These objects are runtime values and JSON or CSV experiment artifacts. Scenario task identifiers are the stable references. A task may be assigned to at most one active mission at a time.

**State transitions**:

1. Task: `undetected` → `pending` → `assigned` → `in_service` → `completed`.
2. Task replacement: `assigned` → `pending` when displaced, or `pending` → `assigned` when the new task is accepted.
3. UAV: `available` → `active` → `serving` → `active` → `returned` → `turnaround` → `available`.
4. Recourse: `triggered` → `candidate_evaluated` → `accepted` or `rejected`.

The completed route prefix and completed task states are immutable after execution. V2 does not interrupt service already in progress.

**API surface**:

| Action | Key inputs | Key outputs | Key errors |
|---|---|---|---|
| `build_v2_episode_state` | scenario, UAV configuration, route configuration | initial episode state | invalid scenario, invalid initial state |
| `evaluate_replacement` | episode state, new task, active UAV, displaced task | candidate decision and revised mission suffix | missing task, duplicate task, invalid state |
| `select_recourse` | episode state, new task, active missions | accepted decision or queue decision | route planning failure is recorded as candidate rejection |
| `run_event_simulation_v2` | scenario, UAV configuration, V2 configuration | V2 episode result | invalid configuration, impossible state |
| `run_pgbm_v2_recourse_matrix` | seeds, environments, task loads, UAV counts | raw metrics, manifests, decision traces | invalid matrix or missing local scenario |

**Value sourcing**:

| Action | Value produced | Source |
|---|---|---|
| Task eligibility | detected task set | scenario task `detected_at` and current event time |
| Item feasibility | remaining onboard item quantity | initial mission demand minus completed task demand |
| Remaining route | task waypoint sequence and route polyline | uncompleted mission tasks, new task drop off waypoint, existing routing layer |
| Completion time | task service completion time | current recourse time, route travel time, service duration |
| Service value | `v_i(C_i)` | task severity, detection time, completion time, configured decay rate |
| Old mission value | `J_old` | current uncompleted tasks and their current completion predictions |
| New mission value | `J_new` | replacement task set and recalculated remaining route |
| Energy feasibility | remaining mission energy | route links, carried payload mass, ascent, service duration, UAV energy coefficients, remaining battery, reserve energy |
| Queue update | pending task identifiers | accepted replacement decision and displaced or rejected task identifiers |
| Final episode objective | one service value per completed task | final completion events, never the sum of repeated plan snapshots |

**Key invariants**:

1. V1 entry points and V1 artifacts are not changed by importing or running V2.
2. A new task cannot be used before its detection time.
3. Future undetected tasks are invisible to the planner.
4. One recourse candidate changes one active mission and replaces one uncompleted task.
5. Completed tasks, completed route segments, and delivered parcel quantities cannot be undone.
6. The new task demand must be covered by current onboard inventory for every item type.
7. The revised route must use collision free legs, respect payload and energy limits, and return to the same physical base.
8. No replacement is accepted when `delta_J` is zero or negative.
9. A task identifier is never simultaneously completed, queued, and assigned.
10. Every recourse decision has an explicit accepted or rejected outcome and reason.

**Security model**:

This is a local research simulation. It has no network API, user accounts, secrets, or regulated data path. Inputs are local scenario files and configuration values. Generated reports and raw metrics remain research artifacts.

**Configuration required**:

1. `recourse_enabled`: select V2 recourse or a V2 fixed mission control.
2. `one_for_one_replacement`: fixed true for the formulation aligned V2 run.
3. `max_pending_tasks` and `max_candidate_plans`: retain bounded V1 search limits for comparable runtime evidence.
4. `horizon_minutes`: default 120.
5. `turnaround_minutes`: retain the existing configurable five minute V1 assumption.

**Critical test scenarios**:

1. A new task with matching onboard item demand produces a feasible positive gain and replaces one uncompleted task, verifies **AC-4**, **AC-6**, **AC-9**, and **AC-10**.
2. A new task with an unavailable item is rejected and remains in the queue, verifies **AC-6** and **AC-11**.
3. A candidate that violates energy reserve or safe return is rejected, verifies **AC-8**.
4. A candidate with nonpositive gain leaves the active mission unchanged, verifies **AC-9**.
5. A task arriving while a service is in progress does not interrupt that service, verifies **AC-5**.
6. Repeated same seed runs produce identical event logs and replacement traces, verifies **AC-2**.
7. V1 tests and a V1 matrix run produce the existing reference behavior after V2 modules are added, verifies **AC-1**.
8. Final episode service value counts each task once even when multiple recourse decisions occur, verifies **AC-12**.

## Build plan

The project uses a Skateboard approach. The first slice will run one complete V2 episode end to end using a small hand checked scenario. Later slices add the full matrix and report only after the recourse trace and metrics are trustworthy.

1. Create the V2 code namespace, report folder, results folder, README files, and configuration contract without changing V1, satisfying **AC-1** and **AC-13**.
2. Implement runtime task, UAV, mission, and episode state using the existing scenario, task, planner, and route contracts, satisfying **AC-2**, **AC-5**, **AC-6**, and **AC-10**.
3. Implement current route progress, carried item accounting, remaining payload mass, remaining energy, and completion prediction, satisfying **AC-5**, **AC-6**, **AC-7**, and **AC-8**.
4. Implement one for one candidate generation and replacement evaluation using `J_old`, `J_new`, and positive `delta_J`, satisfying **AC-3**, **AC-4**, **AC-6**, **AC-8**, and **AC-9**.
5. Implement the V2 event runner with deterministic task detection, active mission observation, queue update, service completion, return, and turnaround events, satisfying **AC-3**, **AC-5**, **AC-10**, and **AC-11**.
6. Add focused fixtures and tests for accepted replacement, item mismatch, infeasible route, energy failure, nonpositive gain, service protection, duplicate prevention, determinism, and V1 isolation, satisfying **AC-1**, **AC-2**, **AC-5**, **AC-6**, **AC-8**, **AC-9**, and **AC-10**.
7. Add V2 metrics, decision trace export, paired V1 and V2 matrix execution, and configuration manifests. Use two environments, three task loads, four UAV counts, and ten seeds, satisfying **AC-11**, **AC-12**, **AC-13**, and **AC-14**.
8. Run the complete paired experiment, aggregate mean and standard deviation, and preserve raw event and metric evidence under the V2 results folder, satisfying **AC-13** and **AC-14**.
9. Create the V2 report in the V1 format. Put the V2 core features at the top, explain the formulation aligned routing and replacement rule, present V1 versus V2 tables and figures, interpret every major result, and record V3 reserve inventory as a boundary, satisfying **AC-15**.
10. Compile, render, and visually inspect the report, run the complete Simulation test suite, run `git diff --check`, and record the verified status in the project context, satisfying **AC-1**, **AC-2**, and **AC-15**.

## Consequences

**Positive**:

1. V2 directly tests the recourse rule already written in the selected formulation.
2. V1 remains a stable comparison baseline.
3. The event trace explains why each replacement was accepted or rejected.
4. The same architecture can later support reserve inventory without changing the replacement contract.

**Negative and tradeoffs**:

1. One for one replacement is narrower than a full dynamic optimizer.
2. Active mission state and route progress add implementation and testing work.
3. Bounded brute force can become slower when recourse events increase, so V2 must measure recourse planning time separately.
4. Current task generation limits and synthetic item demand remain experiment assumptions.

**Neutral**:

1. V2 will produce separate report and result artifacts rather than replacing V1.
2. No database or external service is needed.

## Follow-up

1. Add reserve inventory and active inventory-aware reassignment in Version 3.
2. Consider multiple task replacement only after the one for one results are validated.
3. Compare a scalable planner against the bounded reference after route and recourse runtime evidence is available.
4. Calibrate energy coefficients before treating energy values as physical measurements.

## References

**Project sources**:

1. `Research Source/Problem Formulation/problem_formulation_v5.tex`, sections on task replacement recourse, payload evolution, energy, and three dimensional routing.
2. `Research Source/Full Report/Chapters/problem_formulation.tex`, canonical formulation chapter and recourse rule.
3. `Research Source/Full Report/Chapters/implementations.tex`, planned optimization and recourse workflow and metrics.
4. `docs/specs/0005-pgbm-planner-execution.md`, existing V1 planner and execution contract.
5. `Simulation/AGENTS.md`, simulator and provenance conventions.

**Practices and standards**:

1. Strangler implementation for preserving a validated reference path while adding a new execution path.
2. Seeded paired experiments for fair algorithm comparison.
3. Event traceability for stateful simulation decisions.

## Migration plan

**Strategy**: strangler, with no scenario schema migration.

**Phases**:

1. Add V2 modules and artifacts beside V1. Keep V1 entry points unchanged.
2. Run a small V2 fixture and focused tests.
3. Run paired V1 and V2 experiments from the same scenario inputs.
4. Generate and verify the V2 comparative report.

**Rollback**: remove or disable V2 runner selection. Existing V1 modules, scenarios, results, and report remain usable.

**Risks**: Incorrect current route progress, accidental future task visibility, repeated objective counting, or mutation of V1 shared state could invalidate the comparison. Tests must explicitly cover these risks before the full matrix is run.
