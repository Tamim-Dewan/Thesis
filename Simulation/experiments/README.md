# Experiment runners

These scripts are the executable experiment entry points. Run them from the
`Simulation/` directory so the existing relative result paths remain stable.

- `run_initial_snapshot.py` — approved DU and synthetic `t = 30` snapshot.
- `run_pgbm_v1_single_simulation.py` — one V1 two-hour episode.
- `run_pgbm_v1_experiment_matrix.py` — canonical V1 240-run matrix.
- `run_pgbm_v2_experiment_matrix.py` — paired V1/V2 recourse matrix.
- `run_pgbm_v21_experiment_matrix.py` — paired V2/V2.1 cache matrix.
- `merge_pgbm_v2_matrix_parts.py` — merge and validate distributed V2 parts.
- `run_experiments.py` — small historical baseline comparison.
- `run_phase1.py` — legacy Phase 1 validation.

The general single-episode entry point, `run_simulation.py`, remains directly
under `Simulation/` because it is the primary CLI used by the project.

