# Simulation results

This directory contains generated outputs. Existing files remain in place so
that documented paths and earlier evidence are not broken.

## Artifact groups

- `du_*`: University of Dhaka outdoor source, damage, collision, preview, and
  run artifacts.
- `synthetic_*`: fully generated environment, damage, collision, preview, and
  scenario artifacts.
- `laquila_*`: the separate L’Aquila informed source reconstruction outputs.
- `heidata_*`: source mesh and OSM benchmark outputs.
- `phase1_*`: the original experiment contract manifest and empty metrics file.
- `research_metrics*`: repeated planner comparison metrics.
- `initial_runs/session_2026-09-27/`: the organized folder for this session's
  no recourse initial solution reports, scenarios, and assignment route views.
  The approved configuration is `Simulation/configs/initial_snapshot.json`.

## Visual meanings

- `*_layout*` and `*_map*` show source or generated building layout.
- `*_damage*` shows the synthetic post earthquake damage layer.
- `*_collision*` shows simplified blocked volumes for future route checking.
- `*_disaster_preview*` and `*_simulation_preview*` show combined environment
  and task layers. They do not contain planner assignments unless explicitly
  stated in the filename or report.
- `*_initial_visual.html` shows the approved `t = 30` initial plan, including
  task assignment, drop off points, collision aware UAV routes, and execution
  summary.
- `*_initial_step_by_step.html` replays the assignment decisions first, then
  animates UAV movement between arrival, service, and return events. The
  compact view uses a structured status panel, hides trace toggles, and
  distinguishes planned, travelled, and active route segments. Each arrival
  pauses playback for five seconds and shows which UAV is serving the task.

The collision views are environment diagnostics. They are not proof that the
new initial task allocation and routing algorithm has been implemented.
