# PGBM Simulation

This package is being built in phases. The current environment slice creates
seeded three dimensional disaster scenes with typed ground and elevated
obstacles. The scene is a reusable Python object, not a notebook project.

Run the Phase 1 validation from this directory:

```bash
python3 run_phase1.py --config configs/phase1_default.json
python3 -m pytest -q
```

The generated manifest records the configuration and deterministic component
seeds that later simulation phases must use. The old standalone Phase 1
preview is not part of the current supervisor workflow; current environment
evidence comes from the disaster scene previews below.

## Disaster scenes

The next feature adds deterministic post earthquake scenes. It has a structured
synthetic mode and a real layout `du_outdoor` mode built from a bundled,
true-scale OpenStreetMap template covering the complete selected University of
Dhaka Science Complex cluster. Its horizontal bounds follow the mapped source
extent, rather than an arbitrary fixed square. The building damage is synthetic and versioned as
`earthquake.v1`. The complete exported simulation input uses the validated
`scenario.v2` schema.

```bash
python3 render_disaster_preview.py --mode du_outdoor --severity moderate \
  --with-tasks --output results/du_disaster_preview.html
python3 render_disaster_preview.py --mode synthetic --severity severe \
  --with-tasks --output results/synthetic_disaster_preview.html
python3 render_disaster_preview.py --mode laquila_informed --severity moderate \
  --with-tasks --output results/laquila_informed_disaster_preview.html
```

The default Plotly preview is an operational airborne-UAV environment view. It keeps the
mapped target building footprints, post-earthquake building and debris volumes,
selected tasks, vertical drop off waypoints, and the base visible. Static context
buildings and unused candidate sites are hidden so that the research objects are
readable. Roads are intentionally absent from the airborne scene because route
planning is a later research layer and is not part of this environment preview.

DU and fully synthetic scenes now use the shared `synthetic_damage_mesh.v1`
template layer. `major_partial_collapse.v1` renders a standing section with an
uneven top and a disjoint collapsed section; its rubble, broken floors, and
elevated debris are confined to that collapsed side. `destroyed_rubble_cluster.v1`
renders the mapped source footprint together with a dense cluster of larger,
irregular three-dimensional rubble pieces. Rubble uses deterministic earthy
material variation and uneven top profiles to keep DU and synthetic previews
visually consistent with the heiDATA storyboard. These are seeded modelling
templates, not measured post earthquake meshes for the DU buildings. Their
template ID is stored in the scene metadata and appears in the damage mesh hover
information.

The `laquila_informed` mode is the single canonical exact georeferenced source
reconstruction. It preserves the 17 nonredundant building footprints selected
by the local `scenario.v1` artifact in their original projected source
positions; it does not use a four by four grid, random translation, or random
damage allocation. Roads remain source provenance only because the active
scene is for airborne UAV experiments. The local heiDATA pre earthquake and
accepted post earthquake OBJ models are used only where `scenario.v1` binds
them. Buildings without a building-specific height or mesh are shown as
explicit `footprint extrusion` or `derived OSM damage` geometry rather than
being presented as measured 3D truth. Collision geometry uses the same source
footprint, and hover text preserves the OSM identity, source asset, damage
state, and provenance.

The `--severity` argument remains accepted for script compatibility, but it
does not create a second L’Aquila mode or change the source building states.
Generate the one canonical source reconstruction with:

```bash
python3 render_scene_view.py --mode laquila_informed --severity moderate \
  --view layout --output results/laquila_informed_layout_view.html
python3 render_scene_view.py --mode laquila_informed --severity moderate \
  --view damage --output results/laquila_informed_damage_view.html
```

For a separate post earthquake damage view, use the moderate preset for a
balanced supervisor presentation and keep a severe artifact for stress testing:

```bash
python3 render_scene_view.py --mode du_outdoor --severity moderate \
  --view damage --output results/du_outdoor_damage_view.html
python3 render_scene_view.py --mode du_outdoor --severity severe \
  --view damage --output results/du_outdoor_damage_severe_view.html
```

For a diagnostic view that also shows the quiet context layer and every unused
candidate site, add `--show-context --show-candidate-sites`. The
`real_building` mode is deliberately not enabled until a licence reviewed local
Matterport3D or ScanNet derived template with both exterior and interior
geometry has been added. It reports a clear local template error instead of
pretending that synthetic geometry is a real building.

Both the DU and fully synthetic environment previews use the same task layer.
Each contains survivor task markers, vertical drop off waypoints, and the
vertical separation guide. The planner does not assign UAVs in these previews.

To regenerate task points and their synthetic vertical drop off waypoints:

```bash
python3 render_disaster_preview.py --mode du_outdoor --severity severe \
  --seed 20260924 --with-tasks \
  --output results/du_simulation_preview.html
```

This environment preview deliberately does not calculate task assignments or
UAV routes. The planner and collision aware routing layer remain available for
the later solution experiment, but their output is not mixed into the world
definition.

Each task is sampled inside a target `minor`, `major`, or `destroyed` damage
footprint. Its task surface uses the local top of the damaged geometry. The
drop off waypoint keeps the same x and y coordinates and is placed directly
2 to 4 metres above that surface. The vertical segment is rendered and the
drop off point is checked against the scene geometry.


Each generated task represents one survivor and one small delivery parcel. It
is not a daily ration. The demand always contains `food`, `water`, and
`medical`, each with a quantity of `0` or `1`, and at least one item is present.
The default item weights are `0.25 kg` for food and `0.50 kg` for both water
and medical supplies. `required_payload_mass` is calculated from those values.

The default UAV limits are `4` parcels and `2.0 kg`. Each task also stores its
own `service_duration`, calculated from the base duration, parcel count, and
severity. The scenario file stores the scene, tasks, UAV configuration, route
configuration, execution configuration, and initial UAV states. It does not
store planner assignments or planner output.

To create only a new validated scenario input, without planning or execution,
run:

```bash
python3 run_simulation.py --mode du_outdoor --severity severe \
  --seed 20260924 --task-count 6 --uav-count 3 --export-only \
  --output results/du_complete_run_20260924.scenario.json
```

## Real post-earthquake 3D reference

The repository also contains a licence-labelled sample from the heiDATA
dataset (`doi:10.11588/DATA/D3WZID`). It preserves real OBJ building meshes and
pre/post damage grades as a separate benchmark environment, so the research
can compare the lightweight DU/synthetic simulator with measured post-event
geometry:

```bash
PYTHONPATH=. python3 -m heidata_benchmark.cli \
  heidata_benchmark/data/sample/manifest.json
```

The command writes `results/heidata_benchmark_preview.html` and a provenance
summary. The benchmark is not silently converted into rectangular buildings;
its mesh geometry and quality flags remain visible in the reference preview.

## Initial no recourse run

The approved first solution is a single snapshot at t = 30. The
initial_snapshot_greedy_v1 planner ranks eligible tasks by current exponential
service value, then appends each task to the feasible UAV tour with the
smallest marginal route distance. The no recourse flag keeps this run limited
to the initial allocation and route execution. The fixed inputs are recorded
in configs/initial_snapshot.json.

```bash
python3 run_simulation.py --mode du_outdoor --severity moderate \
  --seed 20260924 --task-count 6 --uav-count 3 \
  --start-time 30 --planner initial_snapshot_greedy_v1 --no-recourse \
  --output results/initial_runs/session_2026-09-27/du_outdoor_initial.json

python3 run_simulation.py --mode synthetic --severity moderate \
  --seed 20260924 --task-count 6 --uav-count 3 \
  --start-time 30 --planner initial_snapshot_greedy_v1 --no-recourse \
  --output results/initial_runs/session_2026-09-27/synthetic_initial.json
```

The initial run writes a `simulation_run.v2` report with the initial plan and
execution events. Its `recourse` field is `null` by design.

Run both approved cases from the manifest with:

~~~bash
python3 run_initial_snapshot.py
~~~

After a report is created, render its assignment and routes with:

~~~bash
python3 render_initial_solution.py \
  --report results/initial_runs/session_2026-09-27/du_outdoor_initial.json
python3 render_initial_solution.py \
  --report results/initial_runs/session_2026-09-27/synthetic_initial.json
~~~

For a step by step replay of assignment, route, arrival, service, and return.
The replay uses a slower playback speed, a structured status panel, hidden
trace toggles, and interpolated UAV movement along the planned route. Dashed
lines show the planned route, solid lines show the travelled route, and the
orange segment shows the active leg. When a UAV reaches a task, playback holds
for five seconds and shows a popup above the task identifying the UAV and the
task being served:

~~~bash
python3 render_step_by_step.py \
  --report results/initial_runs/session_2026-09-27/du_outdoor_initial.json
python3 render_step_by_step.py \
  --report results/initial_runs/session_2026-09-27/synthetic_initial.json
~~~

## End to end research run

The complete episode can also be run and exported with one command. This
creates a `scenario.v2` input beside the `simulation_run.v2` report:

```bash
python3 run_simulation.py --mode du_outdoor --severity severe \
  --seed 20260924 --output results/du_complete_run_20260924.json
```

This writes both a validated `.scenario.json` input and a JSON report
containing the initial plan, replacement-task recourse, execution events, and
metrics. Planner assignments remain in the run report, not in the exported
scenario input.

Generate tasks, export a complete scenario, build a resource aware plan, and
execute it with:

```bash
python3 - <<'PY'
from pgbm_sim import (
    SceneConfig, TaskConfig, UAVConfig, build_scenario, save_scenario,
    load_scenario, plan_tasks, execute_plan,
)

scenario = build_scenario(
    SceneConfig(mode="du_outdoor", severity="severe", seed=20260924),
    TaskConfig(task_count=6, seed=20260925),
    scenario_id="du_severe_20260924",
)
save_scenario(scenario, "results/du_severe_20260924.json")
scenario = load_scenario("results/du_severe_20260924.json")
uavs = UAVConfig(count=3)
plan = plan_tasks(scenario, uavs)
result = execute_plan(scenario, plan, uavs)
print(result.as_dict())
PY
```

Run the PGBM heuristic and nearest task baseline over repeated seeds with:

```bash
python3 run_experiments.py --mode du_outdoor --severity moderate \
  --seeds 101 102 103 104 105 \
  --start-time 30 --output results/research_metrics.csv
```

The current planner is explicitly named `pgbm_heuristic_v1`. It is a working
assignment and execution baseline with synthetic severity, parcel count,
distance based energy, return to base, and replacement task handling. The
formal service value objective and full mathematical optimization formulation
remain later planner refinements.
