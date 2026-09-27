# 0004. heiDATA post earthquake environment

**Date**: 2026-09-24
**Status**: In Progress

## Summary

This plan completes the first four layers of a separate heiDATA benchmark environment for the thesis. It uses a versioned OpenStreetMap snapshot for real world building positions and roads, then applies verified heiDATA damage meshes as labelled damage templates. It creates a controlled mixed damage scene with safe lightweight navigation geometry. It does not change the DU environment and it does not yet add survivor tasks, UAV missions, or planning experiments.

## Context

> ⚠️ Premise note: The heiDATA generic building models are virtual damage models, not georeferenced copies of real buildings. Their local OBJ coordinates cannot identify a latitude, longitude, or matching real building. This plan uses a dated OpenStreetMap snapshot for exact map position and road geometry, while it labels heiDATA meshes as damage templates rather than as exact real building reconstructions.

The current package can load selected OBJ assets and render a source faithful view. The first synthetic preview used the wrong display axis and an invented grid, roads, and candidate points. The corrected view proves that source Y is vertical and maps source X, Y, Z to Plotly X, Z, Y. The next implementation must preserve this correction throughout visualisation, collision, and navigation.

The first deliverable is a fixed static environment. It must support repeatable experiments and defensible thesis figures without presenting unobserved conditions as measured fact. A scenario selects one actual study area, stores the OSM query boundary, snapshot date, OSM element identifiers, coordinate reference system, and transformation to local metres. It remains isolated in `Simulation/heidata_benchmark/` and must not import, edit, or depend on `Simulation/pgbm_sim/`.

## Requirements

**User stories**:

* As a thesis researcher, I want every rendered building and damage state linked to its exact heiDATA file so that the scene remains auditable.
* As a thesis researcher, I want the layout, roads, and building footprint identifiers linked to a fixed OSM snapshot so that real world positions can be checked.
* As a simulation developer, I want a collision and navigation representation that is smaller than the visual mesh so that path checking is practical.
* As a UAV operator model, I want only validated safe zones and declared access constraints so that later mission work starts from feasible locations.

**Acceptance criteria**:

* **AC 1**: The mesh library loads only manifest declared OBJ files, preserves their raw coordinates, records a content checksum and source bounds, and declares source Y as vertical.
* **AC 2**: The renderer always maps source X, Y, Z to visual X, Z, Y, labels the axes, and never grids, aligns, rotates, scales, or translates a source mesh unless a named derived transform is recorded.
* **AC 3**: Every source post mesh has a machine readable quality review that records geometry checks, status as accepted or inspection only, and the reason for exclusion when it cannot be used in a benchmark scenario.
* **AC 4**: A mixed damage scenario selects at most one state for each source building identifier, retains its original local position, and records the selected pre or post asset, grade, and provenance for every building.
* **AC 5**: A mixed damage scenario is labelled as a controlled benchmark composite, not a measured earthquake site, and a user can reproduce it from a scenario manifest without a network connection.
* **AC 6**: Visual meshes and collision meshes are stored as separate representations. Collision geometry is conservative, records its derivation from visual geometry, and uses the same X, Z ground plane and Y height convention.
* **AC 7**: The package generates a static navigation volume with configured cell size, vertical clearance, no fly obstacles, and free or blocked cells. It rejects a path that intersects a collision volume or leaves the world boundary.
* **AC 8**: Roads, rubble, blocked zones, launch pads, and landing pads are explicit overlay records with a provenance field of source, annotated, or derived. The source only mode contains none of these overlays.
* **AC 9**: A road or zone is usable only when it is inside the world boundary and satisfies configured clearance and collision rules. A blocked road has a recorded cause and blocking geometry.
* **AC 10**: The package exports an interactive HTML view and a JSON scenario package containing mesh evidence, transforms, collision and navigation data, operational overlays, validation results, seed, and version identifiers.
* **AC 11**: Tests cover raw coordinate preservation, axis mapping, duplicate building prevention, rejected source meshes, deterministic scenario generation, collision conservatism, navigation safety, overlay provenance, and offline export.
* **AC 12**: The heiDATA package remains separate from DU and does not create survivor tasks, route assignment, flight dynamics, dynamic events, or performance claims.
* **AC 13**: A geospatial scenario stores a fixed OSM extract, the study area boundary, OSM building and highway identifiers, original WGS 84 geometry, projected metre geometry, projection definition, and snapshot timestamp.
* **AC 14**: Each mapped building is labelled as exactly one of OSM intact footprint extrusion, OSM footprint with a heiDATA damage template, or OSM footprint with a scenario derived damage geometry. The system never claims that a generic heiDATA mesh or scenario derived damage geometry is the exact surveyed geometry or observed damage of an OSM building.
* **AC 15**: A final scenario has exactly one building record, one visual instance, and one selected state for each OSM building identifier. It rejects duplicate identifiers, duplicate footprint bindings, and building footprints that overlap beyond the configured geometry tolerance.
* **AC 16**: A scenario derived damage binding names its OSM building identifier, one declared state of minor or major, a deterministic rule version, and the derived height profile. It cannot share an OSM identifier with a heiDATA template binding or another derived damage binding.

## Options considered

### Extend the old synthetic grid scene

This is fast because roads, points, and damage examples already exist. It fails the thesis evidence standard because it changes coordinates and does not separate measured data from made up elements.

### Render only raw source meshes

This is the strongest source display but cannot provide a usable static benchmark with collision, routes, or UAV safe zones.

### Keep source evidence and add declared benchmark overlays

This retains raw mesh evidence while adding only the operational layers needed for a controlled static environment. It is the chosen option.

### Use a real map base with declared damage templates

This uses a fixed OSM snapshot for actual building positions and road geometry, then attaches compatible heiDATA damage templates through an explicit mapping. It is the chosen geospatial extension because it gives exact map position without falsely claiming that virtual damage meshes are measured buildings.

## Decision

**Chosen option**: Keep source evidence and add declared benchmark overlays.

Use a source faithful mesh library, a fixed OSM map base, and a scenario manifest. OSM supplies exact geographic footprint and road location. A compatible heiDATA mesh supplies labelled damage appearance only. Compose one chosen damage template per mapped building, then derive conservative collision and navigation geometry. Add rubble, blocked areas, launch pads, and landing pads through explicit versioned overlay records. A source only scene remains available as the audit view.

**Implementation skills**: `plotly` (`_d-one_/Thesis`, `.agents/skills/plotly/`) for interactive scientific visualisation.

## Rationale

The selected data gives building shapes and damage examples, but it does not provide a complete operational disaster map. The design keeps the value of the data by preserving it exactly, while making the assumptions required for simulation visible and testable. A separate collision layer avoids using complex triangle meshes for every safety query, yet its derivation can be inspected against the original mesh.

The Skateboard approach starts with a usable and auditable static scenario. It deliberately stops before survivor, mission, and planner features, because those require further research decisions after environment validity is proven.

## Feature design

**Data model sketch**:

| Entity | Required fields | Relationship and rule |
|---|---|---|
| `MeshAsset` | asset id, path, SHA 256, source id, event phase, damage grade, raw bounds, source axis convention, review status | one manifest owns many assets, source coordinates are immutable |
| `MeshReview` | asset id, accepted or inspection only, checks, reviewer note, review version | one review for each post asset |
| `GeoContext` | study area boundary, OSM snapshot path and timestamp, WGS 84 geometry, projected coordinate reference system, OSM ids | one context owns all real map records |
| `MapBuilding` | OSM id, footprint, height source, projected footprint, template binding status | one OSM building belongs to one geo context |
| `ScenarioBuilding` | building id, OSM id, heiDATA source id, selected asset id, grade, placement transform, collision ids, provenance | one selected state per OSM building |
| `DerivedDamageGeometry` | OSM id, damage state, height profile, rule version, seed, provenance | one declared scenario rule derives an irregular top profile from one OSM footprint |
| `ScenarioManifest` | scenario id, version, seed, geo context id, world bounds, selected buildings, overlays | owns buildings, collision geometry, navigation volume, and overlays |
| `CollisionVolume` | id, building id, minimum, maximum, clearance margin, derivation version | one or more conservative volumes per scenario building |
| `NavigationVolume` | cell size, altitude bands, boundary, occupied cells, clearance policy | derived from collision volumes and world boundary |
| `OperationalOverlay` | id, kind, geometry, status, provenance, source asset ids, rule version, notes | kinds are road, rubble, blocked zone, launch pad, or landing pad |
| `ValidationReport` | scenario id, pass or fail, checks, warnings, generated at | one report per exported scenario |

`OSM id` is unique within `ScenarioBuilding`. A scenario cannot include two damage states, two visual instances, or two selected bindings for the same OSM building. Raw heiDATA coordinates are immutable in source evidence. A source only scene uses identity geometry except for the display axis permutation. A map bound damage template may be translated, rotated, and scaled only through a recorded placement transform that references the target OSM footprint.

**Exactness policy**:

OSM positions, building footprints, and road paths are exact only with respect to the stored OSM snapshot. OSM height tags are used when present. Missing height is an explicit scenario assumption. heiDATA mesh shape and damage grade remain template evidence, not a claim about the exact real OSM building or its observed earthquake damage. Scenario derived minor and major damage geometry preserves the OSM footprint but uses a declared deterministic height profile. It is a controlled modelling annotation, not damage observed by OSM or heiDATA.

**State transitions**:

```text
raw OBJ asset
  -> parsed source mesh
  -> reviewed asset
  -> fixed OSM map context and projected building footprint
  -> selected damage template and recorded placement transform
  -> visual mesh and collision volumes
  -> navigation volume and declared overlays
  -> validated static scenario package
```

**Local interface surface**:

| Action | Key inputs | Key outputs | Key errors |
|---|---|---|---|
| `build_mesh_library` | asset manifest, local OBJ files | `MeshAsset` and `MeshReview` records | missing asset, checksum mismatch, malformed mesh |
| `load_osm_context` | fixed OSM extract, study boundary, projection | `GeoContext`, map buildings, roads | missing id, invalid polygon, unsupported projection |
| `build_source_scene` | mesh library, selected asset ids | source faithful view | duplicate source id, unreviewed post asset |
| `build_composite_scenario` | scenario manifest, OSM context, seed | mixed damage `ScenarioManifest` | duplicate OSM id, unknown asset, missing placement transform |
| `derive_collision` | scenario buildings, clearance policy | conservative `CollisionVolume` values | empty mesh, invalid bounds |
| `build_navigation_volume` | collision volumes, world boundary, cell size, altitude bands | occupied and free cells | invalid cell size, no usable free volume |
| `validate_overlays` | overlays, collision volumes, navigation volume | checked overlays and report | unknown provenance, unsafe pad, road outside boundary |
| `export_scenario` | validated scenario, output paths | HTML, JSON, report | validation failure, output failure |

**Value sourcing**:

| Action | Value produced | Source |
|---|---|---|
| Parse OBJ | vertices, faces, raw bounds | local mesh asset file |
| Build asset record | checksum, event phase, damage grade | bytes of asset file and asset manifest |
| Load map context | real footprint, road geometry, OSM identifier | fixed OSM extract and declared coordinate reference system |
| Review post asset | accepted or inspection only, quality reasons | deterministic geometry checks and versioned review record |
| Build scenario | selected damage state and real map position | scenario manifest, OSM footprint, and recorded template placement transform |
| Derive OSM damage geometry | minor or major profile and visible mesh | scenario derived damage binding, OSM footprint, default or tagged height, seed, and named rule version |
| Render scene | visual vertices and axis labels | source mesh and fixed X, Y, Z to X, Z, Y mapping |
| Derive collision | occupied volume and margin | visual mesh bounds, configured clearance policy |
| Build navigation | free cells and no fly cells | world boundary, collision volumes, cell size, altitude bands |
| Add operational overlay | geometry, status, provenance | scenario overlay record, source link or declared derivation rule |
| Export report | validation result and warnings | all validation checks and scenario manifest |

**Key invariants**:

1. Source meshes use X and Z as the ground plane and Y as height.
2. A source faithful visual transform is identity except for display axis permutation.
3. A scenario contains no repeated source building identifier.
4. An inspection only post mesh cannot enter a thesis benchmark scenario without an explicit reviewed override.
5. Collision geometry fully contains the visual geometry after the configured margin is applied.
6. Every overlay has provenance and a stable identifier.
7. Launch and landing pads must be free, level, within bounds, and outside configured building clearance.
8. Output generation is deterministic for the same local assets, manifest, configuration, and seed.
9. No DU package is imported or changed.
10. An OSM snapshot is stored locally and no live OSM query is needed to reproduce an exported scenario.
11. A selected building state names its OSM building id and either its heiDATA asset id or its scenario derived damage rule.
12. Final scenario building footprints are unique and do not exceed the configured overlap tolerance.
13. A scenario derived damage building retains the exact OSM ground footprint and records its non observed provenance and deterministic rule inputs.

**Security model**:

The package reads local public research files and writes local research artefacts. It has no accounts, credentials, network dependency at runtime, or personal data.

**Configuration required**:

* `mesh_library.v1.json`: asset evidence, checksums, review state, and source axis convention.
* `osm_context.v1.geojson`: fixed OSM snapshot, study boundary, element ids, original coordinates, and projected geometries.
* `scenario.v1.json`: selected building states, bounds, seed, collision margin, cell size, altitude bands, and overlays.
* `operational_overlay.v1.json`: declared roads, rubble, blocked zones, and pads with provenance.

**Critical test scenarios**:

* Source audit: parse every selected OBJ, recompute its checksum, preserve raw values, and render Y as vertical, verifies **AC 1**, **AC 2**.
* Geospatial audit: load a fixed OSM extract, verify every map building and road identifier, project it to metres, and reproduce the same local geometry without network access, verifies **AC 13**.
* Mixed state scenario: choose distinct source ids across intact and post damage assets, reject a second state for the same id, and reproduce the same JSON, verifies **AC 4**, **AC 5**.
* Template honesty: bind a heiDATA mesh to one OSM footprint and verify that the export names both sources and says template rather than observed building damage, verifies **AC 14**.
* Derived damage honesty: bind a minor or major scenario rule to an unbound OSM footprint, verify its deterministic profile, exact footprint, provenance label, and conflict rejection against a template binding, verifies **AC 14**, **AC 16**.
* Redundancy failure: attempt to add a second state, visual mesh, or overlapping footprint for the same OSM building, then reject the scenario with the conflicting identifiers, verifies **AC 15**.
* Quality failure: mark an abnormal post mesh inspection only and reject it from a benchmark without an explicit approved override, verifies **AC 3**.
* Navigation safety: expand collision volumes, rasterise the navigation volume, and reject routes that enter an occupied cell or leave the bounds, verifies **AC 6**, **AC 7**.
* Operational overlay: accept a declared clear road and pad, then reject an unproven road, blocked pad, or overlay outside the boundary, verifies **AC 8**, **AC 9**.
* Offline export: build and export the same scenario with network access unavailable, verifies **AC 10**, **AC 11**, **AC 12**.

## Build plan

1. Replace the remaining synthetic preview entry point with a mesh library reader that validates checksums, raw bounds, source axis convention, and post asset review records. Keep the source only renderer as the first inspection surface, satisfies **AC 1**, **AC 2**, **AC 3**, **AC 12**.
2. Add a fixed OSM context loader and local coordinate projection. Store the exact study boundary, OSM building and road ids, source geometry, projection, and snapshot metadata, satisfies **AC 13**.
3. Add a versioned scenario manifest and a mixed damage composer. Enforce one selected state and one visual building instance per mapped building, unique template or derived damage binding, explicit footprint based placement transforms, deterministic OSM damage profiles, offline reproduction, controlled composite labels, and template honesty, satisfies **AC 4**, **AC 5**, **AC 10**, **AC 12**, **AC 14**, **AC 15**, **AC 16**.
4. Add derived collision volumes and a static three dimensional navigation volume. Use conservative clearance, projected OSM ground geometry, template height, and deterministic configuration values, satisfies **AC 6**, **AC 7**.
5. Add declared operational overlays for roads, rubble, blocked zones, launch pads, and landing pads. Start from OSM road geometry and validate provenance, bounds, clearance, and blockage state, satisfies **AC 8**, **AC 9**.
6. Render the validated composite scene with a clear legend for OSM map data, heiDATA templates, and derived geometry. Export the visual HTML, scenario JSON, and validation report together, satisfies **AC 2**, **AC 5**, **AC 8**, **AC 10**, **AC 13**, **AC 14**.
7. Add focused unit and end to end tests for every invariant and failure path, including duplicate and overlap rejection. Run the full heiDATA package test suite offline, satisfies **AC 11**, **AC 12**, **AC 15**.

## Consequences

**Positive**:

* Thesis scenes will use actual OSM map positions and distinguish map evidence, damage template evidence, and modelling assumptions.
* Source faithful visualisation and fast safety geometry will share one explicit coordinate convention.
* The exported static scenario will be stable enough for later survivor and UAV work.

**Negative and tradeoffs**:

* A conservative collision volume can block more space than the visible mesh.
* OSM footprint data is exact to its stored snapshot, but it does not prove building height, condition, or earthquake damage.
* Manual overlays require careful annotation and can never be presented as supplied by heiDATA or OSM.
* Some post meshes may be excluded until their review is defensible.

**Neutral**:

* Full mission logic, route optimisation, sensors, flight physics, survivors, and dynamic hazards remain outside this deliverable.

## Follow-up

* [ ] Review all candidate grade 3 post meshes and document accepted or inspection only status before thesis experiment selection.
* [ ] Design survivor and UAV mission layers only after the static environment validation is accepted.
* [ ] Add a planner adapter only after navigation volume checks have a stable contract.

## Migration plan

**Strategy**: Strangler pattern.

**Phases**:

1. Keep existing source faithful viewer outputs while adding the mesh library, local OSM context, and scenario manifest beside the old synthetic benchmark code.
2. Make the validated OSM based composite scenario the default public preview and retain the source only viewer as the evidence inspection mode.
3. Remove the compatibility preview only after output comparison and regression tests prove that no thesis output depends on it.

**Rollback**: Retain versioned manifests and existing source viewer files. Revert the default command to the source only preview if a composite validation fails.

**Risks**: An unreviewed damaged mesh, a mismatched coordinate convention, or an overlay without provenance can invalidate a figure. The required validation report prevents silent publication of such a scene.

## References

**Project sources**:

1. `Simulation/heidata_benchmark/`, the current separate heiDATA implementation.
2. `Simulation/heidata_benchmark/data/sample/manifest.json`, current selected asset evidence.
3. `docs/specs/0002-synthetic-disaster-environment-generation/index.md`, current separate DU and synthetic environment scope.
4. `Simulation/pgbm_sim/`, existing planner package that must remain unchanged.

**Practices and standards**:

1. Preserve research data provenance and record every derived transformation.
2. Use seeded deterministic scenario generation.
3. Keep high detail visual geometry separate from conservative collision geometry.

**Links**:

1. [heiDATA dataset](https://heidata.uni-heidelberg.de/dataset.xhtml?persistentId=doi:10.11588/DATA/D3WZID)
2. [Related publication](https://doi.org/10.1016/j.jag.2023.103406)
