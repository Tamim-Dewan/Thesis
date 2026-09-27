# 0006 · Exact georeferenced L’Aquila reconstruction

**Status**: Accepted
**Date**: 2026-09-26

## Summary

The single L’Aquila environment will use the stored OSM snapshot and its source coordinates instead of a synthetic grid. The 17 nonredundant building footprints from the frozen context will keep their real relative positions in a local metre coordinate frame. The local heiDATA assets and the stored scenario manifest will be used where they actually bind to a building, while missing three dimensional information will be labelled as derived rather than invented.

This is a source faithful reconstruction of the data that is present in the repository. It is not allowed to claim an unobserved height, mesh, or earthquake damage state as measured truth.

## Context

> ⚠️ Premise note: Exact reconstruction is the right direction for the L’Aquila environment, but the local package does not contain a measured three dimensional pre and post model for every OSM building. Calling every rendered volume exact would create false precision. The correct boundary is exact stored position and footprint, exact stored template bindings, and explicit derived geometry for information the dataset does not provide.

The previous implementation selected 16 OSM footprints and placed them in a four by four synthetic layout. That made the scene repeatable, but it discarded the real L’Aquila spatial relationship and excluded two valid source footprints. The local geospatial benchmark already contains the correct source composition in `Simulation/heidata_benchmark`: the OSM snapshot has 18 building polygons, `scenario.v1.json` excludes one overlapping polygon, and the remaining 17 buildings are placed in their original source relationship.

The PGBM simulator needs the same source geometry as the visual benchmark so that future UAV collision and task planning use the environment that the supervisor sees. Active road obstacles remain excluded because the user selected an airborne UAV environment, but road geometry remains available in the source provenance and the separate geospatial audit.

## Requirements

* **AC-1**: The existing `laquila_informed` mode becomes the one canonical L’Aquila mode. No second L’Aquila mode or synthetic grid mode is introduced.
* **AC-2**: The loader reads the local OSM GeoJSON, local `scenario.v1.json`, and local heiDATA manifest without network access.
* **AC-3**: The active scene contains exactly the 17 nonredundant buildings selected by `scenario.v1`. The overlapping `way/503172320` is excluded with its recorded reason. No other source building is silently removed.
* **AC-4**: Every active building keeps its original OSM polygon and original relative position after conversion from WGS 84 to the stored local ENU metre frame. No four by four placement, random translation, or synthetic lot scale is allowed.
* **AC-5**: The scenario damage state comes from `scenario.v1.json`. The generator must not redistribute states from the `light`, `moderate`, or `severe` preset for this mode.
* **AC-6**: The five explicit template bindings in `scenario.v1` use the exact accepted local heiDATA asset named by that binding. An inspection only post asset cannot enter the active scene.
* **AC-7**: The six derived damage bindings use the exact OSM footprint and the named derived profile rule. The six remaining buildings with no damage binding use an OSM footprint extrusion because the stored context has no building specific height or mesh for them. Hover and metadata must say which of these cases applies.
* **AC-8**: The visible source mesh placement uses the original local coordinates and the stored building footprint envelope. Any scale needed to fit an unpaired heiDATA template is recorded as a template placement transform and is not described as measured OSM geometry.
* **AC-9**: Ground rubble is attached to its parent building and remains within the parent footprint or its declared collapsed region. Destruction receives denser rubble than major damage. No unrelated rubble is placed elsewhere.
* **AC-10**: Active PGBM scene roads and road blocks remain empty for UAV experiments. The complete OSM road context remains in the geospatial source artifact and provenance.
* **AC-11**: World bounds are derived from the exact source building geometry with a documented boundary margin. The base is placed at a validated free source coordinate, at `z = 0`, outside all building and rubble geometry.
* **AC-12**: Collision geometry uses the exact placed OSM footprint and conservative height envelope. Visual mesh detail does not change collision validation.
* **AC-13**: Tasks, candidate sites, route collision checks, and `scenario.v2` export continue to work without changing their public contracts.
* **AC-14**: Hover text identifies the building name when available, OSM id, original WGS 84 source, local source position, damage state, asset binding, and whether the visible geometry is source, template placed, or derived.
* **AC-15**: The layout, source damage, collision, and task previews use clear titles that say `exact source position`, `template`, or `derived` where relevant. They must not call the scene a purely measured three dimensional reconstruction.
* **AC-16**: The same local source files and source scenario produce identical geometry and metadata for every seed. The seed may affect only simulator generated task sites and candidate sites, never the source building placement or source damage allocation.

## Decision

Update the existing loader in place and use the existing geospatial benchmark as the source of truth. The loader will consume `load_osm_context` and `build_geospatial_scenario` rather than duplicating a second OSM parser or maintaining a synthetic placement table. The current public mode name remains `laquila_informed` to avoid breaking callers, but all metadata and previews will identify it as an exact georeferenced source reconstruction.

The scene will contain the 17 buildings from `scenario.v1` after its one explicit overlap exclusion. Their local coordinates are produced by the existing deterministic WGS 84 to ENU projection. Their footprint vertices are not changed. The exact source scenario determines whether a building is intact, minor, major, extreme, or destroyed. The PGBM state vocabulary maps no damage and footprint only to `intact`, minor to `minor`, major and heavy or extreme damage to `major`, and destruction to `destroyed`.

The five stored template bindings use accepted heiDATA meshes. The six derived bindings use the OSM polygon and the existing nonflat damage profile. The remaining six buildings use an exact footprint extrusion only because the source contains no building specific height or mesh for them. This is the only honest way to preserve every nonredundant building without inventing measurements.

The simulator continues to use polygon collision geometry and shared task contracts. It will not add source roads to the active airborne scene. The base is derived from a validated free location near the source cluster, and that derivation is recorded separately from the source building data.

**Implementation skills**: `plotly` (`/Users/_d-one_/.agents/skills/plotly/`) for browser based scientific visualisation.

## Feature design

### Source records

| Field | Meaning | Source |
|---|---|---|
| `osm_id` | Stable source building identity | Frozen OSM GeoJSON |
| `footprint_wgs84` | Original geographic polygon | Frozen OSM GeoJSON |
| `footprint_local_m` | Deterministic local ENU polygon | Existing `geospatial.py` projection |
| `damage_grade` | Stored source or declared scenario state | `scenario.v1.json` and its bindings |
| `asset_id` | Accepted heiDATA template when explicitly bound | `scenario.v1.json` and mesh library |
| `visual_kind` | Source template, derived damage, or footprint extrusion | Geospatial scenario builder |
| `placement_transform` | Only the transparent fit of an unpaired source template | Geospatial scenario builder |
| `provenance` | Source, template, or scenario derived | Loader metadata and hover text |

### Exactness boundary

The exact part is the stored geographic footprint, relative building position, exclusion rule, explicit template binding, accepted asset checksum, and stored damage annotation. The derived part is the local display projection, template fitting for a mesh that is not building specific, footprint extrusion for buildings with no height, damage profile for derived bindings, rubble, base, candidate sites, and tasks. Every derived value is named in metadata.

### Damage mapping

| Source state | PGBM state | Visible geometry |
|---|---|---|
| `no_damage` or `osm_footprint_only` | `intact` | Accepted pre template or exact polygon extrusion |
| `minor` | `minor` | OSM footprint with stored derived profile |
| `major` or `heavy` or `extreme` | `major` | Accepted template or stored derived profile |
| `destruction` | `destroyed` | Accepted post template and parent aligned rubble |

The `severity` command argument remains accepted for compatibility with existing scripts, but it does not change L’Aquila source building states. The preview title reports the source scenario instead of presenting a random moderate or severe allocation as observed L’Aquila data.

### Simulation boundary

The visible geometry and collision geometry share the same exact local footprint. Collision uses a conservative height envelope so route validation remains stable even when the visual mesh has irregular faces. Roads are retained in the source benchmark but are not copied into `DisasterScene.roads` or obstacle collision objects.

## Build plan

1. [x] Audit the local OSM context, source scenario, manifest, raw OBJ files, and review statuses.
2. [x] Replace the four by four configuration with the source scenario configuration and one overlap exclusion.
3. [x] Reuse the geospatial loader so source coordinates, explicit template bindings, and derived damage states are not duplicated.
4. [x] Convert the exact geospatial building records into PGBM structures with source and derived provenance.
5. [x] Derive source bounds and a validated free base position. Keep roads out of the airborne scene.
6. [x] Regenerate source layout, damage, collision, task, and `scenario.v2` previews.
7. [x] Inspect every regenerated preview in a browser and check that source positions, names, damage states, and missing three dimensional data are understandable.
8. [x] Run focused exactness, geometry, deterministic source state, export, and relevant regression checks.

## Migration plan

**Strategy**: replace in place

**Phases**:
1. Switch the existing `laquila_informed` loader and template to the source scenario while preserving the public mode and simulator contracts.
2. Regenerate all L’Aquila artifacts and replace old synthetic grid previews.
3. Inspect the new artifacts and retain the old generated files only as historical untracked output if they are not referenced by the workflow.

**Rollback**: restore the previous loader and layout configuration from the working tree. No persistent database or external service is changed.

**Risks**: Some buildings have no building specific 3D mesh or height. The renderer must show footprint extrusion or derived geometry with an explicit label instead of hiding the gap or inventing a measurement. The exact source scene is larger and irregular, so camera fitting and candidate site generation must be checked again.

## Consequences

The L’Aquila map will now be geographically meaningful and directly comparable to the stored source benchmark. Buildings will no longer be rearranged into a presentation grid. The supervisor can trace each visible building back to its OSM id and source scenario record.

The scene will not claim more than the dataset provides. Six buildings will use footprint extrusion because no height or mesh is present. Six damage cases are derived from exact footprints. This is a visible limitation, but it is more defensible than calling repeated generic geometry an exact reconstruction.

## Follow-up

* [ ] If building specific height or mesh data becomes available, replace only the affected footprint extrusion records and preserve the source ids.
* [ ] Review the inspection only post meshes separately before changing their status.
* [ ] Run the full `/test` suite after the visual exactness review is accepted.

## Rationale

The requested change is an enhancement of the current L’Aquila mode, not a second environment. Reusing the already audited geospatial benchmark prevents two loaders from disagreeing about positions, exclusions, and template bindings. Keeping a named boundary between source and derived geometry makes the reconstruction useful for simulation and defensible in a thesis.

## References

### Project sources

1. `Simulation/heidata_benchmark/data/sample/osm_context.v1.geojson`, stored OSM polygons and roads.
2. `Simulation/heidata_benchmark/data/sample/scenario.v1.json`, exclusions, explicit template bindings, and derived damage bindings.
3. `Simulation/heidata_benchmark/geospatial.py`, local ENU projection and source context loader.
4. `Simulation/heidata_benchmark/environment.py`, exact source scenario composition and validation.
5. `Simulation/heidata_benchmark/library.py`, local OBJ checksums and inspection only review.
6. `Simulation/pgbm_sim/disaster_scene.py`, shared PGBM collision, damage, task, and preview contracts.

### Dataset

The local manifest identifies the heiDATA dataset `doi:10.11588/DATA/D3WZID`, under CC BY 4.0. The stored OSM snapshot remains the source for building position and footprint, while the heiDATA files remain source mesh templates unless the scenario explicitly binds them.

Spec [0002](../specs/0002-synthetic-disaster-environment-generation/index.md)
