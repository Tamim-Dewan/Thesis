# Initial solution session, 2026 09 27

This folder contains the DU outdoor and Synthetic outputs used during the
initial solution visualization work.

## Contents

- `du_outdoor_initial.json`: DU execution report.
- `du_outdoor_initial.scenario.json`: DU scenario input.
- `du_outdoor_initial_visual.html`: DU static initial solution view.
- `du_outdoor_initial_step_by_step.html`: DU replay with movement, arrival
  holds, and serving popups.
- `synthetic_initial.json`: Synthetic execution report.
- `synthetic_initial.scenario.json`: Synthetic scenario input.
- `synthetic_initial_visual.html`: Synthetic static initial solution view.
- `synthetic_initial_step_by_step.html`: Synthetic replay with movement,
  arrival holds, and serving popups.

The run uses the approved `t = 30` snapshot, no recourse, and the initial
heuristic planner. Each task arrival holds the replay for five seconds and
identifies the serving UAV above the task.

Source files remain in their normal project locations:

- [Renderer](../../../render_step_by_step.py)
- [Renderer tests](../../../tests/test_render_step_by_step.py)
- [Run configuration](../../../configs/initial_snapshot.json)
