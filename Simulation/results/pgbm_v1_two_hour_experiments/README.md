# PGBM V1 two hour experiment artifacts

This folder contains the generated evidence for the seeded 120 minute PGBM V1
experiment. The matrix covers two environments, three task loads, four UAV
fleet sizes, and ten seeds, for 240 runs in total.

## Folder guide

- `raw_metrics/`: complete matrix, baseline, pilot, and sensitivity CSV files.
- `metrics_by_configuration/`: six CSV blocks grouped by environment and task
  load.
- `manifests/`: experiment coverage and configuration manifest.
- `visualizations/`: initial solution reports, scenario inputs, static route
  views, and step by step replays.

## Canonical matrix

The primary result file is
`raw_metrics/pgbm_v1_two_hour_matrix_metrics_tasks_30_60_90_uavs_3_5_8_10_seeds_101_110.csv`.
Its rows use the experiment label
`pgbm_v1_two_hour_experiment_matrix`.
