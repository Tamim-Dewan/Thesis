# Synthetic disaster environment generation

**Date**: 2026-09-23
**Status**: In Progress

## Summary

This feature generates two reproducible three dimensional post earthquake environments for the thesis. The outdoor environment uses a real University of Dhaka Science Complex layout. The Real Building environment uses one real building with both exterior and interior geometry. Earthquake damage is a research informed synthetic layer, while runtime geometry remains local and lightweight.

## Requirements

### User stories

* As a researcher, I want a complete seeded disaster scene so that planning experiments can be repeated fairly.
* As a researcher, I want severity presets grounded in published disaster data so that the synthetic scenes have a defensible methodology.
* As a researcher, I want a local real layout mode so that I can compare synthetic scenes with simplified real earthquake geometry.
* As a researcher, I want an interactive three dimensional preview so that I can visually inspect every building footprint, earthquake damage, irregular debris, collision space, and the base.
* As a researcher, I want one real building environment with exterior and interior geometry so that indoor and outdoor experiments can use the same building.

### Acceptance criteria

* **AC-1**: `generate_disaster_scene(config, seed)` returns a complete immutable `DisasterScene` containing environment geometry, structures, obstacles, one base, UAV initial positions, candidate sites, effective configuration, and provenance. Airborne experiment scenes contain no active road geometry or road block obstacle.
* **AC-2**: The generator supports `du_outdoor`, `real_building`, and compatibility `synthetic` modes. `du_outdoor` uses the complete selected Science Complex source extent with true scale and source sized horizontal bounds, plus a 60 metre vertical bound. `real_building` uses the selected source scene dimensions and keeps ground level at `z = 0`.
* **AC-3**: The same validated configuration, seed, preset version, and template version produce exactly the same scene. Different seeds produce observably different valid synthetic scenes.
* **AC-4**: Built in `light`, `moderate`, and `severe` presets use documented research informed ranges. Increasing severity produces nondecreasing target proportions for major damage, destroyed structures, rubble, broken floors, and elevated debris.
* **AC-5**: Synthetic scenes have a structured urban layout. Buildings occupy separated lots with open air corridors, and related rubble and debris are placed within damaged parent footprints.
* **AC-6**: Buildings use polygon footprints. Ground rubble and elevated debris use deterministic irregular polygon fragments with nonuniform top surfaces. Broken floors and elevated debris occupy their parent structure footprint at a valid positive height. Collision geometry is a conservative enclosing volume, and unrelated objects do not share three dimensional volume.
* **AC-7**: The generator reserves the base safety area before other placement. The base remains inside the world at `z = 0`, `uav_initial_positions` contains exactly `uav_count` copies of that base position, and no generated object intrudes into the configured base clearance area.
* **AC-8**: Built in presets use capacity aware constructive placement and complete without random placement failure. A mathematically impossible custom configuration raises `SceneConfigurationError` before scene construction and does not silently reduce requested counts or relax geometry rules.
* **AC-9**: Candidate sites are unique and valid. The default scene contains 12 ground sites and 6 elevated sites. Ground sites lie on open ground or near rubble. Elevated sites lie on a referenced accessible rooftop or broken floor surface. A candidate may touch its own supporting surface but does not lie inside any solid volume or touch an unrelated obstacle.
* **AC-10**: `du_outdoor` loads a bundled, preprocessed true scale OSM template containing the complete selected Science Complex cluster around Mukarram Hussain Khundker Bhaban and CSE, including exact mapped building polygons and open areas. Source road data may be retained in the template, but it is not activated in an airborne experiment scene. The horizontal bounds are derived from the selected source extent and are never stretched or arbitrarily clipped.
* **AC-11**: Every scene records source title, URL or DOI, licence, source role, preset version, preprocessing version, template version, seed, any imputed values, and any deterministic crop or translation adjustment.
* **AC-12**: Runtime generation uses only local lightweight configuration and template files. It performs no network download and does not require raw point clouds, satellite images, Open3D, a database, credentials, or a GPU.
* **AC-13**: The saved map and source layout use a clean top-down source-only view of exact mapped footprints; they do not mix in the simulation base, roads, damage, tasks, or UAV layers. Damage and collision previews separately show structure damage states, irregular obstacle categories, candidate site kinds, and the simulation base. Every mapped target remains identifiable in the damage view, including destroyed structures. Source-view hover labels lead with the actual building name or stable template identifier.
* **AC-14**: The existing `Environment`, `generate_environment`, `is_valid_point`, and `plot_environment` public contracts remain backward compatible.
* **AC-15**: A missing, corrupt, unsupported, out of bounds, or internally inconsistent template raises `SceneTemplateError` with a clear message. No network fallback, geometry distortion, or silent repair occurs.
* **AC-16**: `DisasterScene.as_dict()` returns a JSON compatible representation. Saving and loading complete scenario files remains deferred to feature 6.
* **AC-17**: `real_building` loads one preprocessed real building environment with exterior geometry and interior floors, rooms, doors, windows, corridors, stairs, lifts, and semantic labels where available. Matterport3D is attempted first, with ScanNet as the fallback if access or licensing prevents use. The selected source must provide an exterior shell, or a compatible exterior companion source must be selected by the preprocessing rule.
* **AC-18**: Real building geometry is preserved as source geometry. Earthquake damage is a separate synthetic layer that can affect exterior walls, interior rooms, floors, stairs, corridors, and debris. The scene does not claim that the source building itself experienced an earthquake.
* **AC-19**: Outdoor and indoor candidate sites and routes are validated against their respective geometry. The default real building scene contains 6 indoor candidate sites, distributed across reachable floors where possible. Indoor routes use only connected rooms and connections whose status is open.
* **AC-20**: Every real building template records its interior source, exterior source, access or licence terms, scene identifier, preprocessing version, coordinate transform, retained semantic classes, and synthetic damage transformation. A source scene is selected by requiring an exterior shell, at least one floor connection, and the largest valid set of rooms and semantic labels among accessible candidates.
* **AC-21**: Indoor damage rules use versioned severity probabilities for damaged rooms, blocked doors, blocked corridors, damaged stairs, and indoor debris. The probabilities are nondecreasing from `light` to `severe` and are recorded in scene metadata.

## Decision

**Chosen option**: two environment modes using real layout geometry and synthetic damage.

The `du_outdoor` mode loads a preprocessed OSM crop around the University of Dhaka Science Complex. The `real_building` mode loads one real building with both exterior and interior geometry, using Matterport3D first and ScanNet as fallback. Both modes apply versioned research informed earthquake damage rules. Raw source datasets are preprocessing inputs, not runtime dependencies.

**Implementation skills**: `plotly` (`tondevrel/scientific-agent-skills`, `.agents/skills/plotly/`)

## Feature design

### Data model

All models are frozen Python data classes and expose JSON compatible `as_dict()` values.

| Entity | Required fields | Relationships and rules |
|---|---|---|
| `DisasterScene` | `environment`, `roads`, `structures`, `indoor_rooms`, `indoor_connections`, `uav_initial_positions`, `candidate_sites`, `preset`, `provenance`, `generation_metadata` | Owns one complete generated scene. Airborne outdoor scenes expose an empty active road collection because roads do not constrain the flight experiment. |
| `SceneConfig` | `mode`, `severity`, `world_bounds`, `base_clearance`, `uav_count`, `ground_candidate_count`, `elevated_candidate_count`, `indoor_candidate_count`, `preset_id`, `template_path`, `seed` | `du_outdoor` defaults to the bundled source sized Science Complex bounds with a 60 metre vertical extent. `indoor_candidate_count` defaults to 6. `template_path` selects a local preprocessed template |
| `ScenePreset` | `identifier`, `version`, `severity`, layout ranges, damage proportions, derived obstacle probabilities, source identifiers | Built in identifiers are `light`, `moderate`, and `severe` |
| `RoadSegment` | `identifier`, `minimum`, `width`, `depth`, `centerline`, `status` | Optional retained source metadata for a future ground vehicle experiment. It is not active scene geometry for this feature. |
| `Structure` | `identifier`, polygon footprint, `height`, `damage_state`, `height_source` | A semantic damaged structure. Its source polygon is preserved, while damage geometry is derived from it. Damage state is `intact`, `minor`, `major`, or `destroyed` |
| `Obstacle` | existing fields plus optional `parent_structure_id`, `source_ref`, polygon footprint, orientation, and visual top profile | Existing constructor use remains valid through optional defaults. An irregular display mesh has a conservative collision envelope. |
| `CandidateSite` | `identifier`, `kind`, `position`, `surface_ref`, `clearance_radius`, `allowed_use` | Kind is `ground` or `elevated`; allowed use is `task` in this feature |
| `IndoorRoom` | `identifier`, `floor_id`, polygon or box geometry, `room_type`, `source_label` | Geometry and labels come from the real building template |
| `IndoorConnection` | `identifier`, `kind`, `from_room`, `to_room`, geometry, `status` | Kind is `door`, `corridor`, `stair`, or `lift`; status is `open`, `blocked`, or `damaged` |
| `SceneTemplate` | `identifier`, `version`, `environment_kind`, metric bounds, exterior and interior geometry, provenance | Contains preprocessed local geometry only |
| `DataSource` | `identifier`, `title`, `url_or_doi`, `licence`, `role`, `preprocessing_version` | Referenced by presets, templates, and generated metadata |

One scene has one existing `Environment`, exactly `uav_count` initial positions, and many candidate sites. Outdoor airborne scenes contain structures and disaster obstacles, with no road geometry or road block. Real building scenes contain exterior structures plus indoor rooms and connections. An obstacle may belong to one structure, room, or connection. No database or schema migration is needed.

### Real building template contract

The outdoor template is a local OSM map of the complete connected Science Complex cluster around Mukarram Hussain Khundker Bhaban and the CSE building. Its horizontal bounds are source sized, it retains true metre scale, and it records the OSM snapshot, source attribution, coordinate reference system, transform, selection rule, and retained feature identifiers.

The real building template must contain one building environment with an exterior shell and an interior layout in the same local coordinate system. Matterport3D is attempted first because it provides accurately scaled real meshes and includes residential, commercial, and civic spaces. If access or licence terms prevent use, ScanNet is the fallback because it provides real indoor reconstructions and semantic labels. If the selected source does not include an exterior shell, the preprocessor selects a compatible exterior companion source for the same building, otherwise it rejects the source rather than joining unrelated buildings. The selected source and companion source are recorded in provenance.

The preprocessor keeps the smallest scene needed for a bounded experiment, retaining exact exterior building polygons, road centerlines, room boundaries, doors, windows, corridors, stairs, lifts, floor levels, and semantic object labels where available. It may simplify collision geometry into primitives, but the display geometry must preserve the source polygons and it must not invent room connectivity without recording that transformation.

For earthquake damage, an intact building is an extrusion of its source polygon. A major building uses a deterministic, disjoint polygon partition that leaves a standing section and a collapsed section. Rubble, broken floors, and elevated debris are generated only inside the collapsed section, so they cannot visually occupy the standing side. A destroyed building keeps a filled and labelled source footprint layer and receives a dense cluster of larger irregular rubble pieces inside that footprint, with navigable gaps. Broken floors are polygon slabs at positive heights. Elevated debris uses multiple irregular fragments with an uneven top profile. The source footprint and the generated damage geometry are stored separately.

### Indoor damage contract

The first preset version adds these indoor probabilities:

| Parameter | Light | Moderate | Severe |
|---|---:|---:|---:|
| Damaged room probability | 0.10 | 0.30 | 0.55 |
| Blocked door probability | 0.05 | 0.20 | 0.45 |
| Blocked corridor probability | 0.05 | 0.25 | 0.55 |
| Damaged stair probability | 0.05 | 0.20 | 0.45 |
| Indoor debris probability per damaged room | 0.25 | 0.65 | 0.95 |

These values are modelling assumptions calibrated from the same named post disaster damage sources as the outdoor preset. They are versioned with `earthquake.v1`. A reachable floor receives an indoor candidate where geometry permits, until the configured count is reached. If fewer sites are geometrically possible, generation raises a clear capacity error rather than silently reducing the count.

### Built in preset contract

The first preset version is `earthquake.v1`. The values below are explicit modelling assumptions informed by the named datasets. They are not presented as direct population estimates. Each generated scene samples within these rules using its seed.

| Parameter | Light | Moderate | Severe |
|---|---:|---:|---:|
| Structures | 8 | 8 | 8 |
| Intact proportion | 0.55 | 0.25 | 0.05 |
| Minor proportion | 0.30 | 0.30 | 0.15 |
| Major proportion | 0.10 | 0.30 | 0.40 |
| Destroyed proportion | 0.05 | 0.15 | 0.40 |
| Rubble density factor for major or destroyed structure | 0.25 | 0.65 | 0.95 |
| Broken floor probability per major structure | 0.10 | 0.40 | 0.70 |
| Elevated debris probability per major structure | 0.10 | 0.35 | 0.60 |

All presets use open air corridors to separate synthetic building lots, building footprint dimensions from 10 to 18 metres, and building heights from 12 to 35 metres. Integer damage counts use deterministic largest remainder allocation so the four counts always total eight. Equal remainders are resolved in `destroyed`, `major`, `minor`, then `intact` order. Custom presets may change these fields but must pass the same capacity and proportion validation.

### Damage to geometry mapping

* An `intact` or `minor` structure creates one full rectangular `building` obstacle. Its roof is a valid elevated support surface.
* A `major` structure partitions its footprint deterministically into disjoint standing and collapsed sections. Ground rubble, `broken_floor`, and elevated debris fragments use only the collapsed section and cannot overlap the standing solid. Every major structure receives a visible rubble cluster.
* A `destroyed` structure creates no full height building box. It creates a dense cluster of larger irregular ground rubble piles inside a visible source footprint while retaining navigable gaps.
* Every ground rubble pile uses a deterministic five to eight sided footprint, an uneven top profile, and a seeded earthy material variant. Every elevated debris group uses two or more irregular fragments at a valid positive height, each with an uneven top profile. The collision volume fully contains the visual fragment.
* Candidate validation uses `is_valid_candidate_site`. Contact with the candidate's declared support surface is allowed. Intersection with the interior of that support or any unrelated solid is not allowed.

### Generation flow

1. Validate the configuration, preset, world capacity, and optional template before placement.
2. Reserve the base and its safety area.
3. In `synthetic` mode, partition the world into separated lots with open air corridors, then place nonoverlapping structures.
4. Apply the severity preset, then create structure related irregular rubble, broken floors, and elevated debris fragments under the category rules.
5. In `du_outdoor` mode, load the bundled complete Science Complex template, translate its lower left corner to the local origin, and instantiate exact source polygons without scaling or clipping source features. Source roads remain inactive metadata.
6. In `real_building` mode, load the bundled real building template, preserve its exterior and interior source dimensions, and instantiate both geometry layers without scaling.
7. Apply the synthetic damage layer to the selected environment mode. Outdoor damage affects structures, rubble, broken floors, and debris. Real building damage affects the exterior shell, rooms, connections, floors, stairs, and debris.
8. Derive ground, elevated, and indoor candidate sites from valid surfaces and connectivity.
9. Validate all invariants, assemble provenance and generation metadata, and return the immutable scene.

If a real source omits height, the loader deterministically imputes height from the active preset. The structure records `height_source = imputed`, and metadata records the source range and sampled value. A template that cannot fit its declared local bounds without distortion is rejected.

### Public interface

| Function | Key inputs | Key output | Key errors |
|---|---|---|---|
| `generate_disaster_scene` | validated `SceneConfig`, optional seed | `DisasterScene` | `SceneConfigurationError`, `SceneTemplateError` |
| `load_scene_preset` | built in name or local JSON path | `ScenePreset` | validation or file error |
| `load_scene_template` | local JSON path | `SceneTemplate` | `SceneTemplateError` |
| `is_valid_candidate_site` | scene and `CandidateSite` | boolean | invalid relationship or point error |
| `is_valid_indoor_route` | scene and route connection identifiers | boolean | blocked connection or invalid room relationship |
| `plot_disaster_scene` | `DisasterScene` | Plotly `Figure` | invalid scene error |

Existing environment functions remain unchanged. Complete scenario save and load functions are not added in this feature.

### Value sourcing

| Action | Value produced or displayed | Source |
|---|---|---|
| Select severity mix | Damage, rubble, broken floor, and debris targets | Versioned `ScenePreset`; built in values come from the `earthquake.v1` table in this spec |
| Construct synthetic layout | Open air corridors, lots, and building geometry | `SceneConfig`, world capacity rules, preset ranges, and seeded random generator |
| Place base and UAV starts | Base position, clearance, and repeated UAV positions | Existing base configuration plus `SceneConfig.base_clearance` and `SceneConfig.uav_count` |
| Load DU outdoor layout | Structure geometry | Local OSM `SceneTemplate` for the complete selected Science Complex cluster, exact source polygons, and its preprocessing manifest |
| Load real building layout | Exterior shell, rooms, floors, doors, stairs, lifts, and semantic labels | Local Matterport3D template, or ScanNet fallback, and its preprocessing manifest |
| Select real building scene | Source scene and exterior companion | First accessible source satisfying the exterior shell, floor connection, room, and semantic label requirements |
| Fill missing height | Structure height | Seeded sample from active preset, recorded as imputed |
| Create obstacle | Geometry, kind, parent link, and visual top profile | Structure damage state, preset rules, deterministic fragment rule, and supporting geometry |
| Create candidate | Count, position, kind, and surface reference | Explicit ground and elevated counts from `SceneConfig`, then valid free ground or a validated structure surface |
| Validate indoor route | Room sequence and connection status | `IndoorRoom` relationships and `IndoorConnection.status` |
| Create indoor damage | Damaged rooms, blocked connections, damaged stairs, and indoor debris | Versioned indoor severity probabilities in the active `ScenePreset` and the seeded random generator |
| Render preview | Colors, labels, layers, and hover data | Generated scene fields and stable Plotly style mapping |
| Report provenance | Source, licence, versions, adjustments, and seed | Preset metadata, template manifest, and effective generation configuration |

### Key invariants

* Ground level is always `z = 0`, and all geometry is inside the world.
* Metric scale is preserved. Translation and cropping are allowed, geometric scaling is not.
* The base safety area is empty and the UAV position tuple length equals `uav_count`, with every entry equal to the base position.
* Structure, obstacle, and candidate identifiers are unique within a scene.
* Airborne scenes contain no active road segment and no `road_block` obstacle.
* Every rubble and elevated debris footprint has at least five vertices and every visual top profile remains within its collision envelope.
* Every relationship identifier resolves to an object in the same scene.
* Indoor routes use only connected rooms and connections whose status is `open`.
* Real source geometry is never described as measured earthquake damage.
* Indoor candidate sites never lie in a blocked room or connection and every indoor site references a reachable floor or room.
* Every built in preset is feasible for the default world and completes constructively.
* Determinism includes the effective config, source versions, ordering, and imputed values.
* Validation never silently changes requested counts, severity, scale, or collision rules.

### Security model

This is local research software. It has no accounts, personal data, credentials, remote services, or runtime dataset downloads. Local JSON input is treated as untrusted and validated before use. Dataset licence and attribution metadata are retained in every derived template.

### Critical test scenarios

* Generate each built in preset repeatedly across representative seeds and confirm completion, no active roads, no road blocks, and all scene invariants, verifies **AC-1**, **AC-3**, **AC-4**, **AC-5**, **AC-6**, **AC-7**, and **AC-8**.
* Generate twice with identical inputs and compare complete `as_dict()` output, then change only the seed and confirm a different valid synthetic scene, verifies **AC-3** and **AC-16**.
* Request an impossible custom density or base clearance and confirm validation fails before construction with no silent adjustment, verifies **AC-8**.
* Generate the default 12 ground and 6 elevated candidates, then validate free space, support contact, and unrelated obstacle clearance, verifies **AC-9**.
* Load the bundled DU template offline and confirm source sized bounds, complete cluster coverage, exact polygon footprints, translation, provenance, and deterministic imputation, verifies **AC-2**, **AC-10**, **AC-11**, and **AC-12**.
* Generate major and destroyed structures and confirm polygon partitions, irregular rubble clusters, multi fragment elevated debris, uneven visual top profiles, conservative collision envelopes, open gaps, positive height slabs, and separate source footprint layers, verifies **AC-5**, **AC-6**, and **AC-13**.
* Load the bundled real building template and confirm exterior shell, rooms, connections, semantic labels, source metadata, and preserved scale, verifies **AC-17**, **AC-18**, and **AC-20**.
* Mark an indoor door, stair, and corridor blocked and confirm indoor route validation rejects paths using them, verifies **AC-19**.
* Generate indoor scenes across all severities and verify monotonic indoor damage probabilities, blocked connections, debris, and six candidate sites when capacity allows, verifies **AC-19** and **AC-21**.
* Load malformed, unsupported, and out of bounds templates and confirm explicit errors, verifies **AC-15**.
* Inspect the Plotly figure trace names, colors, hover labels, and legend groups, verifies **AC-13**.
* Run the existing environment tests without changing their caller code, verifies **AC-14**.

## Build plan

1. Add the additive scene models, validation errors, versioned preset format, and backward compatible optional obstacle links, satisfies **AC-1**, **AC-2**, **AC-4**, **AC-11**, **AC-14**, and **AC-16**.
2. Build one thin end to end synthetic airborne scene with reserved base, separated lots, structures, irregular obstacles, candidate sites, and Plotly inspection, satisfies **AC-1**, **AC-5**, **AC-6**, **AC-7**, **AC-9**, and **AC-13**.
3. Complete all severity presets, capacity validation, constructive placement guarantees, category rules, deterministic metadata, and failure handling, satisfies **AC-3**, **AC-4**, **AC-6**, **AC-8**, **AC-11**, and **AC-15**.
4. Add the lightweight preprocessed DU OSM template, its source manifest, deterministic height imputation, and `du_outdoor` generation, satisfies **AC-2**, **AC-3**, **AC-10**, **AC-11**, **AC-12**, and **AC-15**.
5. Add one lightweight real Matterport3D building template with ScanNet fallback, exterior and interior geometry, source manifest, and `real_building` generation, satisfies **AC-2**, **AC-17**, **AC-18**, **AC-19**, and **AC-20**.
6. Add indoor damage probabilities, route validation, indoor candidate generation, and capacity errors, satisfies **AC-19**, **AC-20**, and **AC-21**.
7. Remove active road geometry and road blocks from airborne scenes. Add deterministic irregular rubble and elevated debris fragments, uneven visual top profiles, clear destroyed footprint layers, named audit hover data, automated checks, and generated interactive previews without changing the existing environment API, satisfies **AC-1**, **AC-4**, **AC-5**, **AC-6**, and **AC-13**.

## Consequences

**Positive**:

* Scenes are reproducible, visually inspectable, and methodologically traceable.
* Structured placement removes arbitrary floating geometry and most random generation failure.
* The rendered damage layer makes destroyed buildings, irregular rubble, and elevated debris easier to distinguish from full standing buildings.
* DU outdoor and real building environments support controlled experiments without a heavyweight simulator.

**Negative and tradeoffs**:

* Irregular fragments improve visual realism but still do not reproduce structural physics or measured collapse mechanics.
* Research informed presets remain calibrated approximations rather than direct replicas of every source location.
* Preparing and documenting two real layout templates requires offline preprocessing and licence review.

**Neutral**:

* Actual survivor tasks remain in feature 5.
* Complete scenario persistence remains in feature 6.
* High-fidelity flight dynamics and dynamic hazard propagation remain outside
  this environment feature. Lightweight collision-aware route planning is now
  implemented in the later planner/execution slice.

## Follow-up

* [ ] Add the Plotly convention to a root `AGENTS.md` when project context is bootstrapped.
* [ ] Record the exact DU crop and transformation in the preprocessing manifest during implementation.
* [ ] Request Matterport3D access and confirm whether the selected real building may be redistributed as a derived lightweight geometry template. Use ScanNet if access is unavailable.
* [ ] Design survivor task generation after this scene contract is built and verified.

## Rationale

Reasoning, alternatives, and research sources: see [rationale.md](rationale.md).
