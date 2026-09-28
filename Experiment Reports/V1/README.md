# PGBM Initial Solution V1 Simulation Report

This folder contains the organized Bangla LaTeX source and PDF version of the
PGBM V1 simulation report. The report follows the direct flow of the simulation
work: core features, algorithm, simulation flow, experiment, metrics, results,
bottlenecks, and next steps. It is based on 240 seeded runs.

- `pgbm_v1_simulation_findings_bn.tex`: editable Bengali LaTeX source.
- `pgbm_v1_simulation_findings_bn.pdf`: compiled report.
- `build_bn/`: XeLaTeX auxiliary files used during Bengali compilation.

The source requires XeLaTeX and the `Kohinoor Bangla` font. The built in
editor compiler may need network access to download its Tectonic bundle, so
the verified PDF was compiled with the local TeX Live XeLaTeX installation.

The numerical evidence is generated from
`Simulation/results/pgbm_v1_two_hour_experiments/raw_metrics/pgbm_v1_two_hour_matrix_metrics_tasks_30_60_90_uavs_3_5_8_10_seeds_101_110.csv`.
The matrix covers Synthetic and DU outdoor environments, 30, 60, and 90
tasks, 3, 5, 8, and 10 UAVs, and seeds 101 through 110. The Markdown summary
is `docs/reports/pgbm_v1_simulation_findings.md`, and the run manifest is
`Simulation/results/pgbm_v1_two_hour_experiments/manifests/pgbm_v1_two_hour_matrix_manifest.json`.
