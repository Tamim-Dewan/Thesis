# Simulation area context

This directory contains the reproducible Python simulation and the separate
heiDATA mesh benchmark reference.

## Commands

Run the complete test suite from the thesis root with:

```bash
python3 -m pytest -q Simulation
```

Run one complete DU episode with:

```bash
python3 run_simulation.py --mode du_outdoor --severity severe --seed 20260924 --output results/du_complete_run_20260924.json
```

Export only the validated input, without planning or execution, with:

```bash
python3 run_simulation.py --mode du_outdoor --severity severe --seed 20260924 --task-count 6 --uav-count 3 --export-only --output results/du_complete_run_20260924.scenario.json
```

Generate a scene preview with task and vertical drop off layers using
`render_disaster_preview.py --with-tasks`. Generate the real mesh
reference with `PYTHONPATH=. python3 -m heidata_benchmark.cli` and its manifest.

## Conventions

Scene generation is deterministic from explicit seeds and local templates.
DU building footprints and road centerlines remain source derived. Damage is
a separate research informed layer. Polygon obstacles are used for collision
checks and Plotly rendering. Runtime generation does not download raw data.
Source layout and map previews are clean top-down footprint views: they show
only mapped source geometry, with readable building hover labels, north/scale
references, and no base, road, damage, task, or UAV overlays. Operational and
collision views show the simulation-added layers separately.
Damage previews use the moderate preset for supervisor presentation by default;
severe previews are explicit stress test artifacts. A damage footprint marker is
classification geometry, while obstacle meshes are the physical scene geometry.
Elevation guides are helper overlays and can be toggled as a legend group.
DU and synthetic target geometry uses the seeded `synthetic_damage_mesh.v1`
template vocabulary. Major targets use `major_partial_collapse.v1`, and
destroyed targets use `destroyed_rubble_cluster.v1`. These are modelling rules,
not claims of surveyed post earthquake mesh data.
Major damage is split at one deterministic footprint centroid cut. Its standing
volume and collapsed section are disjoint, and all major rubble, broken floor,
and elevated debris geometry must stay inside the collapsed section. Rubble is
rendered as a dense seeded cluster of larger irregular three dimensional pieces
with varied earthy colors, following the readable style of the heiDATA preview.
For airborne UAV scenes, road data stays local template metadata and is never
rendered or activated as collision geometry.
The `laquila_informed` mode is the single canonical exact georeferenced
reconstruction. It preserves the 17 nonredundant L’Aquila OSM building
footprints selected by the local `scenario.v1` artifact in their original
projected source positions. It does not use a four by four layout, random
translation, or random damage allocation. Roads remain source provenance only
for the airborne UAV scene. Accepted heiDATA pre/post assets are used only
where `scenario.v1` binds them; missing building-specific height or mesh is
explicitly rendered as derived OSM damage or footprint extrusion. Source mesh
identity, placement, damage state, and review status are visible in metadata
and hover text. Collision and rubble placement use the exact transformed OSM
polygon and the shared simulator contracts. The CLI severity argument remains
for compatibility but does not create a second L’Aquila mode or change source
states.
Scenario inputs use `scenario.v2`. A generated task is one survivor delivery
parcel, with zero or one food, water, and medical item, derived payload mass,
and task specific service duration. Task positions are sampled inside minor,
major, or destroyed target footprints. Their drop off waypoints are directly
above the local surface with a configured 2 to 4 metre vertical separation.
The default UAV limits are four parcels and 2.0 kilograms. Scenario exports do
not contain planner assignments.
Initial solution step by step replay views use a compact status panel, no
interactive trace legend, and route based UAV interpolation with planned,
travelled, and active path styles. Each task arrival includes a five second
playback hold with a popup identifying the serving UAV and task.

The current planner is `pgbm_heuristic_v1`, with `nearest_task_first` as a
baseline. Both use the collision aware routing layer. Do not describe the
heuristic as the final mathematical PGBM optimizer until the thesis equations
are ratified and implemented.

_Drafted by /sync from the introducing change, worth a quick human pass._

## Context files

- [heidata_benchmark/AGENTS.md](heidata_benchmark/AGENTS.md): local conventions for the separate L’Aquila benchmark environment.
