# Environment configuration and geometry

**Status**: Accepted

## Summary

This spec defines the first reusable Python environment for the PGBM simulation. It creates a small bounded three dimensional world with typed rectangular obstacles and one ground based base. It also provides point validation and an interactive Plotly view so generated scenes can be inspected before later task and routing work.

## Requirements

### Environment construction

**AC-1** A caller can create a complete environment from a validated configuration object and an optional seed.

**AC-2** The environment contains one world, zero or more typed rectangular obstacles, and one base at ground level.

**AC-3** The same configuration and seed produce the same environment. The generated environment retains the seed and effective configuration.

### Geometry rules

**AC-4** World bounds define minimum and maximum values for x, y, and z, with a distance unit.

**AC-5** Every obstacle has an identifier, a kind, a minimum corner position, and positive width, depth, and height.

**AC-6** Every obstacle is fully inside the world. Obstacles may overlap each other.

**AC-7** Buildings, road blocks, and ground rubble start at ground level. Broken floors and elevated debris may start at a positive z coordinate while remaining inside the world.

**AC-8** The environment contains one base with an identifier and a three dimensional position at ground level. The base is outside the bounding box surrounding all obstacles. If there are no obstacles, the base is placed at a valid position in the world.

**AC-9** A point is valid only when it is inside the world and outside every obstacle. A point on an obstacle boundary is blocked.

### Configuration and errors

**AC-10** Configuration uses a nested `environment` section and supports creation from Python plus loading from JSON.

**AC-11** Invalid requested values raise clear validation errors. This includes invalid world bounds, a non zero ground level, unknown obstacle kinds, non positive obstacle dimensions, invalid obstacle count ranges, and impossible size ranges.

**AC-12** If generation cannot find a valid base position, it raises a clear generation error rather than returning an invalid environment.

**AC-13** Any bounded placement adjustment or resampling used during generation is deterministic and recorded in the effective configuration or generation metadata.

### Visualization

**AC-14** `plot_environment(environment)` returns an interactive Plotly three dimensional figure containing world context, typed obstacles with distinguishable colors, and the base.

## Decision

**Chosen approach**: use typed Python data classes for the environment model, JSON compatible obstacle profiles for experiments, deterministic seeded generation, and Plotly graph objects for the three dimensional figure.

**Implementation skills**: `plotly` (`tondevrel/scientific-agent-skills`, `/Users/_d-one_/Desktop/Thesis/.agents/skills/plotly/`)

**Runner up**: a grid or voxel model was considered, but it would make the first scene heavier and less transparent than the rectangular geometry needed by the current research question.

## Feature design

### Data model

| Entity | Fields | Relationship |
|---|---|---|
| `Environment` | `world`, `obstacles`, `base`, `seed`, `effective_config`, `generation_metadata` | One environment has one world, zero or more obstacles, and one base |
| `World` | minimum and maximum x, y, z values, distance unit | Belongs to one environment |
| `Obstacle` | identifier, kind, minimum corner position, width, depth, height | Belongs to one environment |
| `Base` | identifier, three dimensional position | Belongs to one environment |
| Free space | Derived from world bounds minus obstacle volumes | Not stored as an entity |

Positions and sizes use numeric coordinate tuples with three values. Data classes provide the public model. NumPy may be used for calculations, but it is not the source of the model contract.

### Configuration

The configuration extends the existing experiment configuration with a nested environment section covering world bounds, ground level, distance unit, total obstacle count, obstacle profiles, base placement settings, and generation attempts. The first default remains a small world similar to the current `100` by `100` by `60` configuration, with ground level `z = 0`.

The supported obstacle kinds are `building`, `road_block`, `ground_rubble`, `broken_floor`, and `elevated_debris`. Each profile controls its size ranges and vertical placement rule. The recommended initial profile rules are:

* `building`: minimum z equals ground level, with medium to tall height.
* `road_block`: minimum z equals ground level, with low height.
* `ground_rubble`: minimum z equals ground level, with low to medium height.
* `broken_floor`: minimum z is sampled from ground level to the highest valid position, with low to medium height.
* `elevated_debris`: minimum z is sampled from a positive range, with low to medium height.

Elevated objects do not yet require a support relationship with a building. They are bounded geometric abstractions for future route and hazard experiments.

### Generation behavior

`generate_environment(config, seed=None)` creates the world, samples obstacles from configured ranges, and places one base. It may use bounded deterministic resampling when a sampled placement does not satisfy the geometry rules. It must not silently change invalid requested configuration values. If the requested configuration cannot produce a valid scene, generation fails with an explicit error.

The disaster area is represented by the generated obstacle cluster. There is no explicit affected circle or separate affected zone. The base is placed at ground level outside the axis aligned bounding box surrounding all generated obstacles. With zero obstacles, normal world validity is sufficient.

### Public interface

| Function | Input | Output | Errors |
|---|---|---|---|
| `generate_environment` | validated environment configuration, optional seed | `Environment` | configuration validation error or generation error |
| `is_valid_point` | environment, three dimensional point | boolean | invalid point shape may raise a validation error |
| `plot_environment` | environment | Plotly `Figure` | invalid environment may raise a validation error |

The visualization function returns a figure rather than displaying it. The first figure shows the world context, typed obstacle boxes with labels and colors, and the ground based base. Task and route layers belong to later features.

### Validation and invariants

The following rules must hold before an `Environment` is returned:

* Each world minimum is less than its corresponding maximum.
* The world ground level is `z = 0`.
* Each obstacle dimension is strictly positive.
* Each obstacle is fully contained by the world.
* Obstacle overlap is allowed.
* Every obstacle kind is supported by a configured profile.
* Ground anchored kinds start at `z = 0`.
* Elevated kinds start at a valid positive z position when configured as elevated.
* A base is inside the world, at `z = 0`, and outside the obstacle cluster bounding box.
* A point on an obstacle boundary is invalid.
* The environment is fixed after generation.

### Security model

This is local research code with no users, accounts, external services, secrets, or regulated data. No authentication or authorization is applicable.

### Configuration required

No environment variables or credentials are required. Plotly is a required Python dependency for this feature.

### Critical test scenarios

* Happy path: generate a small seeded world with typed obstacles and one ground based base, then return a Plotly figure, verifies **AC-1**, **AC-2**, **AC-3**, **AC-8**, and **AC-14**.
* Reproducibility: generate twice with the same configuration and seed and compare every model field, verifies **AC-3**.
* Geometry validity: confirm every obstacle is inside the world, has positive dimensions, and has a supported kind, verifies **AC-5**, **AC-6**, and **AC-11**.
* Overlap: generate or construct overlapping obstacles and confirm the environment remains valid, verifies **AC-6**.
* Vertical placement: confirm buildings, road blocks, and ground rubble start at zero, while elevated kinds may start above zero, verifies **AC-7**.
* Point checks: test an interior point, a world boundary point, an outside point, an obstacle interior point, and an obstacle boundary point, verifies **AC-9**.
* Invalid configuration: provide reversed world bounds, non zero ground level, unknown kinds, non positive dimensions, and invalid count ranges, verifies **AC-11**.
* Base failure: use a configuration that leaves no valid base location and confirm a generation error is raised, verifies **AC-12**.
* Visualization: confirm the returned figure contains typed obstacle traces with distinguishable colors and a base trace, verifies **AC-14**.

## Build plan

1. [x] Update the typed geometry and configuration models with obstacle kinds, profiles, ground level, and JSON round trip support, satisfies **AC-2**, **AC-4**, **AC-5**, **AC-7**, **AC-10**, and **AC-11**.
2. [x] Implement deterministic category based obstacle generation and ground based base placement, satisfies **AC-1**, **AC-3**, **AC-6**, **AC-7**, **AC-8**, **AC-12**, and **AC-13**.
3. [x] Preserve point validation and immutable generated environment results under the typed obstacle model, satisfies **AC-9**.
4. [x] Update the Plotly view with category colors, labels, and ground based base display, satisfies **AC-14**.
5. [x] Add focused tests for category placement, reproducibility, geometry invariants, invalid inputs, base placement, point validity, overlap, and visualization traces, satisfies **AC-3**, **AC-5**, **AC-6**, **AC-7**, **AC-9**, **AC-11**, **AC-12**, and **AC-14**.

## Consequences

**Positive**:

* The environment is easy to inspect and reproduce.
* The model is small enough to build before task generation while representing both ground and elevated disaster structures.
* Later task and routing features can consume a stable scene object.
* Plotly provides interactive three dimensional inspection without introducing a flight simulator.

**Negative and tradeoffs**:

* Rectangular obstacles do not represent detailed buildings or rubble geometry.
* Overlapping obstacles can make the visual scene look like merged blocks, even though they remain separate objects.
* Plotly becomes a required dependency for the first feature.
* The base placement rule is intentionally simple and does not yet model launch pads, landing clearance, or multiple bases.

**Neutral**:

* Route collision checking is deferred to the routing feature.
* The affected zone is not stored. The obstacle cluster is the current visual proxy for the disaster area.

## Follow-up

* [ ] Add the Plotly convention to the project root `AGENTS.md` when project context is bootstrapped.
* [ ] Define the task generation contract after this environment feature is built and verified.
* [ ] Decide whether later routing needs a grid, visibility graph, or continuous path representation.

## Rationale

Reasoning and options: see [rationale.md](rationale.md).
