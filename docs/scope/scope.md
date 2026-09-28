# Scope: PGBM simulation environment

This project will provide a reproducible simulation environment for the PGBM thesis. The first usable version will create synthetic three dimensional disaster environments and generate survivor assistance tasks for later planning experiments.

**Build approach:** Skateboard (build the smallest usable environment and task generator, then expand it).
**Workflow:** Beta (build, verify with real scenarios, then test).

These are recommendations to keep the work orderly. You can skip a step when the decision is already clear.

## At a glance

| # | Feature | Phase | Status |
|---|---------|-------|--------|
| 1 | Experiment contract | Existing | existing |
| 2 | Reproducible seeds and metrics schema | Existing | existing |
| 3 | Environment configuration and geometry | Foundation | done |
| 4 | Synthetic disaster environment generation | Slice 1 | in-progress |
| 5 | Synthetic survivor assistance task generation | Slice 1 | done |
| 6 | Scenario validation and export | Slice 1 | done |
| 7 | PGBM planner integration | Later | in-progress |
| 8 | Simulation execution and event recourse | Later | done |
| 9 | Baselines and comparative experiments | Later | done |
| 10 | L’Aquila informed synthetic environment | Slice 1 | done |
| 11 | PGBM V2 one-for-one task replacement recourse | Later | done |
| 12 | V3 reserve inventory and active reassignment | Deferred | planned |

## Existing foundation

### 1. Experiment contract · existing

The current simulation package validates experiment configuration and defines the shared units, workspace bounds, task count, UAV count, reserve fraction, and output locations. Code area: `Simulation/pgbm_sim/config.py`, `Simulation/configs/phase1_default.json`.

### 2. Reproducible seeds and metrics schema · existing

The current package provides stable component seeds and a metrics record for future planners and experiments. The Phase 1 checks pass, but the metrics file has no experiment records yet. Code area: `Simulation/pgbm_sim/seeds.py`, `Simulation/pgbm_sim/metrics.py`, `Simulation/tests/test_phase1.py`.

## Foundation

### 3. Environment configuration and geometry · done

Define the continuous bounded three dimensional world, rectangular obstacles, and one safe base position for later task generation.

**Done when:** a versioned configuration can describe world bounds and obstacle parameters, generated geometry stays inside the world, the base is valid, and free space can be queried for a point.

- [x] Design it (spec): `/architect environment configuration and geometry`
- [x] Build it: `/develop environment configuration and geometry`
  - [x] Add typed obstacle kinds and category profiles, including JSON support (AC-2, AC-4, AC-5, AC-7, AC-10, AC-11)
  - [x] Generate seeded ground and elevated obstacles, then place the base at ground level (AC-1, AC-3, AC-6, AC-7, AC-8, AC-12, AC-13)
  - [x] Update point validation, Plotly colors, labels, and focused tests (AC-9, AC-14)
- [x] Verify it: `/check verify environment configuration and geometry`
- [x] Test it: `/test environment configuration and geometry` (skipped by user after verification passed)

Spec [0001](../specs/0001-environment-configuration-geometry/index.md) · code in `Simulation/pgbm_sim/`

## Slice 1: Environment and task generation

### 4. Synthetic disaster environment generation · in-progress

Generate seeded disaster scenes for a DU outdoor environment and a real building environment, including obstacles, free regions, bases, indoor connections, and valid locations where tasks and UAVs may be placed.

**Done when:** the same seed produces the same outdoor or real building scene, different seeds produce different valid damage states, geometry and connections remain valid, and both environments can be inspected through saved previews.

- [x] Design it (spec): `/architect synthetic disaster environment generation`
- [x] Build it: `/develop synthetic disaster environment generation` for the available outdoor modes
  - [x] Add the scene model, preset schema, configuration validation, provenance, and backward compatible environment extensions (AC-1, AC-2, AC-4, AC-11, AC-14, AC-16)
  - [x] Generate structured synthetic roads, buildings, damage geometry, base and UAV starts, and candidate sites with guaranteed built in presets (AC-1, AC-3, AC-5, AC-6, AC-7, AC-8, AC-9)
  - [x] Add Plotly scene inspection, route overlays, and one preprocessed DU OSM template with deterministic scale preserving loading (AC-2, AC-10, AC-11, AC-12, AC-13, AC-15)
  - [ ] Add one preprocessed real building template with exterior and interior geometry, Matterport3D first and ScanNet fallback, plus indoor damage and route validation (AC-17 through AC-21)
  - [x] Add compatibility, determinism, geometry, failure, offline, and visualization checks plus previews for the available outdoor environments (AC-1 through AC-16)
- [ ] Verify it: `/check verify synthetic disaster environment generation`
- [x] Test it: `/test synthetic disaster environment generation`

Spec [0002](../specs/0002-synthetic-disaster-environment-generation/index.md)

### 10. Exact georeferenced L’Aquila reconstruction · done

Use the local L’Aquila OSM snapshot and `scenario.v1` as the one source of
truth: preserve all 17 nonredundant source footprints in their original local
ENU relationship, use accepted heiDATA templates only where explicitly bound,
and label missing 3D information as derived geometry. This is one exact
source reconstruction, not a second synthetic L’Aquila mode.

**Done when:** the canonical mode uses source coordinates and footprints,
preserves the recorded overlap exclusion and damage annotations, keeps roads
out of the active airborne scene, aligns rubble with its parent footprint,
supports tasks/collision checks and `scenario.v2`, and exports browser views
that clearly distinguish source assets from derived footprint geometry.

- [x] Design it (spec): `/architect exact georeferenced L’Aquila reconstruction`
- [x] Build it: `/develop exact georeferenced L’Aquila reconstruction`
  - [x] Audit the local OSM, source scenario, OBJ manifest, and review boundary
  - [x] Replace the synthetic grid configuration with the source scenario
  - [x] Reuse the geospatial loader and exact local ENU source positions
  - [x] Convert all 17 active records into PGBM structures with provenance
  - [x] Derive source bounds and a validated free base; keep roads inactive
  - [x] Reuse shared damage, task, collision, and `scenario.v2` contracts
- [x] Verify it: regenerate previews and inspect source positions, labels, attached rubble, and geometry in a browser
- [x] Test it: focused exactness/export checks and 48 relevant geospatial/disaster/render tests pass; full suite remains a later project-wide check

Spec [0006](../specs/0006-laquila-informed-synthetic-environment.md)

### 5. Synthetic survivor assistance task generation · done

Generate survivor assistance tasks from configurable random distributions within valid free space. Each task will include a detected survivor position, a UAV drop off waypoint, detection time, synthetic severity, item demand, required payload mass, and service value at detection. The scenario will also record item weights, UAV parcel and payload capacity, reserve energy, and shared units.

**Done when:** a seeded run produces valid tasks with bounded values, tasks are placed in free space, task demand is represented by item type, and task generation settings are recorded with the scenario.

- [x] Record the initial task contract: [0003](../specs/0003-synthetic-survivor-assistance-tasks.md)
- [x] Build and test deterministic task generation in `Simulation/pgbm_sim/tasks.py`

### 6. Scenario validation and export · done

Validate and save complete environment and task scenarios so later planners can consume the same experiment input without regenerating it.

**Done when:** a scenario can be validated, saved, loaded, summarized, and reproduced from its configuration and seed, with clear errors for invalid geometry or task data.

- [x] Record the initial export contract: [0004](../specs/0004-scenario-validation-export.md)
- [x] Build and test JSON validation, save, load, and deterministic reproduction in `Simulation/pgbm_sim/scenario.py`

## Later research phases

### 7. PGBM planner integration · in-progress

Connect the generated environment and tasks to the PGBM assignment, tour, routing, payload, energy, and service value decisions.

**Done when:** the research planner can consume a saved scenario and produce feasible assignment decisions, collision-aware routes, and standard metrics. The current `pgbm_heuristic_v1` is the first resource-aware planner; the exact mathematical PGBM solver remains to be ratified and implemented.

- [x] Build the first deterministic assignment, parcel-count, energy, and route-aware planner in `Simulation/pgbm_sim/planner.py` and `routing.py` (initial contract: [0005](../specs/0005-pgbm-planner-execution.md))
- [ ] Ratify and implement the exact mathematical PGBM formulation: `/architect PGBM planner integration`

### 8. Simulation execution and event recourse · done

Simulate UAV movement, service completion, resource changes, newly arriving tasks, and accepted or rejected task replacements over time.

**Done when:** a scenario can run through event times and record service timing, resource use, safe return, and recourse outcomes.

- [x] Build event execution, route-aware travel metrics, safe return, and replacement-task recourse in `Simulation/pgbm_sim/execution.py`

### 9. Baselines and comparative experiments · done

Add a transparent reference planner and controlled experiments for comparing PGBM with simpler strategies.

**Done when:** repeated seeded experiments produce comparable metrics for PGBM and at least one baseline across multiple scenario settings.

- [x] Compare `pgbm_heuristic_v1` against `nearest_task_first` over repeated seeds in `Simulation/pgbm_sim/experiment.py`

### 11. PGBM V2 one-for-one task replacement recourse · done

Add the limited recourse rule from the selected formulation while preserving V1 as a stable reference. A newly detected task may replace one uncompleted task in one active mission only when the revised mission remains feasible and its remaining service value improves.

**Done when:** V1 remains unchanged, V2 records deterministic active mission replacement decisions, completed route prefixes and current onboard inventory are respected, paired V1 and V2 experiments run across the heavy matrix, and the comparative report is compiled and verified.

- [x] Design it (spec): `/architect PGBM V2 one-for-one task replacement recourse`
- [x] Build it: `/develop PGBM V2 one-for-one task replacement recourse`
  - [x] Add separate V2 runtime state and event execution beside V1
  - [x] Add one-for-one replacement, remaining route rebuild, inventory and energy checks
  - [x] Add deterministic decision traces and focused recourse tests
  - [x] Run the paired heavy matrix and preserve raw metrics
  - [x] Generate, compile, and verify the V2 comparative report
- [x] Verify it: `/check verify PGBM V2 one-for-one task replacement recourse`
- [x] Test it: `/test PGBM V2 one-for-one task replacement recourse`

Spec [0007](../specs/0007-pgbm-v2-task-replacement-recourse.md) · code in `Simulation/pgbm_sim/v2/`

### 12. V3 reserve inventory and active reassignment · needs a decision

Extend the validated V2 state model so UAVs can carry deliberately uncommitted reserve inventory and use it for later task reassignment without changing the V2 research question.

**Done when:** the V2 evidence is accepted, reserve inventory policy is specified, active inventory allocation remains feasible, and the V3 comparison isolates reserve inventory from one-for-one recourse.

- [ ] Design it (spec): `/architect V3 reserve inventory and active reassignment`

## Deferred

These items remain outside the first simulation slice.

- Real geographic or disaster datasets
- High fidelity physics and flight dynamics
- Hazard propagation and changing obstacles
- Full optimization benchmarking
- Final thesis figures and statistical analysis

## Legend

**Status:** `existing` means the work predates this scope. `planned` means it is ordered but not started through this workflow.

**Next step:** the first unticked box is the next recommended action. A feature with a real design decision starts with `/architect`.
