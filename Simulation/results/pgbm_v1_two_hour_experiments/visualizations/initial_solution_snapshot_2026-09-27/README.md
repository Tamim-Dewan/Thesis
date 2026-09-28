# Initial solution snapshot, 2026 09 27

This folder contains the DU outdoor and Synthetic outputs used during the
initial solution visualization work.

## Contents

- `du_outdoor_initial_solution_report.json`: DU execution report.
- `du_outdoor_initial_solution_scenario.json`: DU scenario input.
- `du_outdoor_initial_solution_static_view.html`: DU static initial solution view.
- `du_outdoor_initial_solution_step_by_step_replay.html`: DU replay with movement, arrival
  holds, and serving popups.
- `synthetic_initial_solution_report.json`: Synthetic execution report.
- `synthetic_initial_solution_scenario.json`: Synthetic scenario input.
- `synthetic_initial_solution_static_view.html`: Synthetic static initial solution view.
- `synthetic_initial_solution_step_by_step_replay.html`: Synthetic replay with movement,
  arrival holds, and serving popups.

The run uses the approved `t = 30` snapshot, no recourse, and the initial
heuristic planner. Each task arrival holds the replay for five seconds and
identifies the serving UAV above the task.

Source files remain in their normal project locations:

- [Renderer](../../../../render_step_by_step.py)
- [Renderer tests](../../../../tests/test_render_step_by_step.py)
- [Run configuration](../../../../configs/initial_snapshot.json)
