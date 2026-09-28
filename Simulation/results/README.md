# Simulation results

This directory contains generated outputs. The canonical PGBM V1 experiment
artifacts are grouped under `pgbm_v1_two_hour_experiments/` so that each file
name identifies its experiment content.

## Artifact groups

- `du_*`: University of Dhaka outdoor source, damage, collision, preview, and
  run artifacts.
- `synthetic_*`: fully generated environment, damage, collision, preview, and
  scenario artifacts.
- `laquila_*`: the separate L’Aquila informed source reconstruction outputs.
- `heidata_*`: source mesh and OSM benchmark outputs.
- `phase1_*`: the original experiment contract manifest and empty metrics file.
- `research_metrics*`: repeated planner comparison metrics. New initial
  comparisons use `research_metrics_initial.csv`; the current one replacement
  fixture is explicitly labelled `research_metrics_recourse.csv`.
- `pgbm_v1_two_hour_experiments/raw_metrics/`: the complete 240 row matrix,
  baseline, pilot, and historical sensitivity CSV files.
- `pgbm_v1_two_hour_experiments/metrics_by_configuration/`: six environment
  and task load CSV blocks used to inspect the matrix by configuration.
- `pgbm_v1_two_hour_experiments/manifests/`: the verified experiment coverage
  manifest.
- `pgbm_v1_two_hour_experiments/visualizations/`: named JSON reports, scenario
  inputs, static views, and step by step replays.
- `Simulation/configs/initial_snapshot.json`: the approved single snapshot
  configuration used by the visualization artifacts.

## Visual meanings

- `*_layout*` and `*_map*` show source or generated building layout.
- `*_damage*` shows the synthetic post earthquake damage layer.
- `*_collision*` shows simplified blocked volumes for future route checking.
- `*_disaster_preview*` and `*_simulation_preview*` show combined environment
  and task layers. They do not contain planner assignments unless explicitly
  stated in the filename or report.
- `*_static_view.html` shows the approved `t = 30` initial plan, including
  task assignment, drop off points, collision aware UAV routes, and execution
  summary.
- `*_step_by_step_replay.html` replays the assignment decisions first, then
  animates UAV movement between arrival, service, and return events. The
  compact view uses a structured status panel, hides trace toggles, and
  distinguishes planned, travelled, and active route segments. Each arrival
  pauses playback for five seconds and shows which UAV is serving the task.

The collision views are environment diagnostics. They are not proof that the
new initial task allocation and routing algorithm has been implemented.
