# Verify: environment configuration and geometry, spec 0001

Steps derived from spec 0001 acceptance criteria.

## Commands

* [x] `python3 -m pytest -q` produces passing tests for the typed obstacle model, verifies AC 1 through AC 14.
* [x] Load the default configuration and generate a typed environment, verifies AC 1, AC 2, AC 4, and AC 10.
* [x] Generate the same seed twice and compare world, obstacles, base, seed, and metadata, verifies AC 3.
* [x] Confirm every obstacle has a supported kind, positive dimensions, and stays inside the world, verifies AC 5, AC 6, and AC 11.
* [x] Confirm overlapping obstacles are accepted, verifies AC 6.
* [x] Confirm ground anchored and elevated obstacle placement rules, verifies AC 7.
* [x] Confirm the base is at ground level and outside the obstacle cluster, verifies AC 8.
* [x] Check points inside the world, outside the world, inside an obstacle, and on an obstacle boundary, verifies AC 9.
* [x] Confirm invalid configuration values raise clear errors, verifies AC 11.
* [x] Confirm impossible base placement raises a generation error, verifies AC 12.
* [x] Confirm placement metadata is deterministic, verifies AC 13.
* [x] Confirm `plot_environment` returns a Plotly figure with typed obstacle colors and a base trace, verifies AC 14.

## Acceptance criteria coverage

AC 1 through AC 13 are covered by the commands above and the focused environment tests in `Simulation/tests/test_environment.py`.
