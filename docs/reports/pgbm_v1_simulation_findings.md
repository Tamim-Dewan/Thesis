# Initial Solution V1 Heavy Experiment Findings Report

**Date**: 2026-09-27

## Executive summary

Initial Solution V1 was evaluated as a seeded, two hour, event driven bounded brute force reference planner. The replacement evidence contains **240 rows**, covering 2 environments, task loads 30, 60, 90, UAV counts 3, 5, 8, 10, and seeds 101 through 110.

The workload is intentionally much heavier than the earlier six task report. New tasks are detected in a high, medium, and low phase, remain queued when all UAVs are busy, and are planned only at dispatch opportunities. Active missions are fixed, so recourse and rerouting remain outside V1.

The measured planner bottleneck is route evaluation. Across the complete matrix, route construction accounts for approximately **96.550%** of planner time. Synthetic is the faster environment on average, while DU outdoor is the slower environment. The current heavy run observed **612 dispatches that reached the candidate search limit**; those cases are reported as bounded search evidence, not hidden as optimal results.

## Scope and formulation

The implementation follows the full report and `Research Source/Problem Formulation/problem_formulation_v5.tex`. It uses severity based exponential service value at completion:

`v_i(C_i) = s_i * exp(-lambda * (C_i - t_i))`

At each dispatch opportunity, V1 enumerates bounded joint assignments and within UAV task orders. A candidate is accepted only when its route is collision free, its parcel count and mass fit the UAV, its energy stays above the reserve, all service completes within the horizon, and the UAV returns to base. The chosen candidate maximizes the sum of completion time service values, with deterministic tie breaks.

## Experiment protocol

| Item | Setting |
| --- | ---: |
| Horizon | 120 minutes |
| Arrival phases | High 0 to 40, medium 40 to 80, low 80 to 120 minutes |
| Relative phase weights | 3:2:1 |
| Task loads | 30, 60, 90 |
| UAV counts | 3, 5, 8, 10 |
| Seeds | 101 through 110 (10 seeds) |
| Total rows | 240 |
| Payload capacity | 2.0 kg and 4 parcels per UAV |
| Base turnaround | 5 minutes |
| Search bound | At most 8 pending tasks and 50,000 candidates per dispatch |
| Recourse | Disabled |

The three phase quotas are deterministic for the selected loads. The expected counts are 15/10/5 for 30 tasks, 30/20/10 for 60 tasks, and 45/30/15 for 90 tasks. The metrics rows confirm these counts for every completed run.

A seed reproduces the same scene and task set when the full configuration is unchanged. Changing task load changes the generated task set, so the load and fleet sweeps are controlled seeded replicates rather than claims of a nested prefix schedule.

## Main 30 task, 3 UAV baseline

This section gives a readable reference point. Values are means over the available seeds, with standard deviation after `±`.

| Environment | Served | Service rate | Deferred | Peak queue | Delay min | Distance m | Runtime s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DU outdoor | 10.500 ± 3.100 | 35.000% | 19.500 ± 3.100 | 19.500 | 34.333 | 2832.367 | 11.485 |
| Synthetic | 22.600 ± 1.776 | 75.333% | 7.400 ± 1.776 | 9.700 | 23.656 | 2521.943 | 2.069 |

[Open the V1 baseline comparison chart](../../Experiment%20Reports/assets/v1/v1_baseline_comparison.pdf)

## Complete task load and fleet matrix

The following table reports every environment, task load, and UAV count case. Each row aggregates the seed replicates for that case.

| Environment | Tasks | UAVs | Served | Rate | Deferred | Peak queue | Delay min | Parcel util | Runtime s | Route share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DU outdoor | 30 | 3 | 10.500 ± 3.100 | 35.000% | 19.500 ± 3.100 | 19.500 | 34.333 | 31.667% | 11.485 | 99.266% |
| DU outdoor | 30 | 5 | 15.900 ± 3.315 | 53.000% | 14.100 ± 3.315 | 14.300 | 33.314 | 19.000% | 13.509 | 97.982% |
| DU outdoor | 30 | 8 | 20.200 ± 3.120 | 67.333% | 9.800 ± 3.120 | 10.200 | 28.357 | 12.188% | 15.143 | 95.013% |
| DU outdoor | 30 | 10 | 21.200 ± 2.741 | 70.667% | 8.800 ± 2.741 | 9.200 | 25.973 | 9.500% | 14.422 | 93.954% |
| DU outdoor | 60 | 3 | 10.800 ± 1.619 | 18.000% | 49.200 ± 1.619 | 49.200 | 33.638 | 33.333% | 12.684 | 99.316% |
| DU outdoor | 60 | 5 | 17.800 ± 1.989 | 29.667% | 42.200 ± 1.989 | 42.200 | 33.207 | 20.000% | 18.059 | 97.141% |
| DU outdoor | 60 | 8 | 26.900 ± 3.035 | 44.833% | 33.100 ± 3.035 | 33.100 | 32.947 | 12.500% | 23.971 | 96.671% |
| DU outdoor | 60 | 10 | 32.600 ± 4.993 | 54.333% | 27.400 ± 4.993 | 27.400 | 32.623 | 10.000% | 30.386 | 96.158% |
| DU outdoor | 90 | 3 | 11.200 ± 1.687 | 12.444% | 78.800 ± 1.687 | 78.800 | 32.996 | 33.333% | 15.823 | 99.210% |
| DU outdoor | 90 | 5 | 17.600 ± 2.875 | 19.556% | 72.400 ± 2.875 | 72.400 | 31.723 | 20.000% | 20.151 | 97.796% |
| DU outdoor | 90 | 8 | 25.600 ± 3.502 | 28.444% | 64.400 ± 3.502 | 64.400 | 30.099 | 12.500% | 30.704 | 96.515% |
| DU outdoor | 90 | 10 | 31.200 ± 4.237 | 34.667% | 58.800 ± 4.237 | 58.800 | 30.517 | 10.000% | 36.365 | 95.366% |
| Synthetic | 30 | 3 | 22.600 ± 1.776 | 75.333% | 7.400 ± 1.776 | 9.700 | 23.656 | 33.333% | 2.069 | 96.483% |
| Synthetic | 30 | 5 | 27.200 ± 1.398 | 90.667% | 2.800 ± 1.398 | 5.500 | 16.152 | 20.000% | 1.118 | 99.377% |
| Synthetic | 30 | 8 | 27.500 ± 1.434 | 91.667% | 2.500 ± 1.434 | 3.400 | 11.406 | 11.562% | 1.102 | 98.288% |
| Synthetic | 30 | 10 | 27.500 ± 1.434 | 91.667% | 2.500 ± 1.434 | 2.700 | 10.370 | 7.750% | 1.078 | 97.587% |
| Synthetic | 60 | 3 | 25.400 ± 2.459 | 42.333% | 34.600 ± 2.459 | 35.000 | 21.600 | 33.333% | 2.862 | 99.258% |
| Synthetic | 60 | 5 | 39.900 ± 3.843 | 66.500% | 20.100 ± 3.843 | 22.000 | 21.642 | 20.000% | 4.039 | 96.426% |
| Synthetic | 60 | 8 | 53.300 ± 3.199 | 88.833% | 6.700 ± 3.199 | 11.000 | 18.928 | 12.500% | 4.663 | 94.019% |
| Synthetic | 60 | 10 | 55.300 ± 1.767 | 92.167% | 4.700 ± 1.767 | 8.700 | 15.013 | 10.000% | 3.644 | 94.788% |
| Synthetic | 90 | 3 | 27.700 ± 2.406 | 30.778% | 62.300 ± 2.406 | 62.300 | 20.887 | 33.333% | 3.246 | 99.802% |
| Synthetic | 90 | 5 | 41.800 ± 3.824 | 46.444% | 48.200 ± 3.824 | 48.500 | 20.039 | 20.000% | 5.201 | 96.675% |
| Synthetic | 90 | 8 | 62.300 ± 5.498 | 69.222% | 27.700 ± 5.498 | 29.300 | 19.906 | 12.500% | 7.286 | 93.854% |
| Synthetic | 90 | 10 | 74.300 ± 4.218 | 82.556% | 15.700 ± 4.218 | 19.600 | 19.960 | 10.000% | 8.488 | 92.269% |

## Task load effect

These values average across all three fleet sizes and all seeds. They show how the workload itself changes service and runtime.

| Environment | Tasks | Served | Rate | Peak queue | Candidates | Planner s | Route share | Truncated dispatches |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DU outdoor | 30 | 16.950 ± 5.198 | 56.500% | 13.300 | 204896.575 | 13.639 | 96.364% | 137 |
| DU outdoor | 60 | 22.025 ± 9.003 | 36.708% | 37.975 | 240482.700 | 21.273 | 96.981% | 155 |
| DU outdoor | 90 | 21.400 ± 8.311 | 23.778% | 68.600 | 303050.825 | 25.757 | 96.774% | 205 |
| Synthetic | 30 | 26.200 ± 2.564 | 87.333% | 5.325 | 11244.350 | 1.340 | 97.678% | 6 |
| Synthetic | 60 | 43.475 ± 12.471 | 72.458% | 19.175 | 60237.950 | 3.800 | 95.829% | 34 |
| Synthetic | 90 | 51.525 ± 18.664 | 57.250% | 39.925 | 124149.525 | 6.053 | 94.701% | 75 |

[Open the V1 workload pressure chart](../../Experiment%20Reports/assets/v1/v1_workload_pressure.pdf)

**Core findings:** Higher task load lowers service rate and raises queue pressure in both environments. DU outdoor remains more constrained than Synthetic across the tested loads.

## Fleet size effect

These values average across all three task loads and all seeds. They isolate the effect of adding or removing UAVs under the same workload family.

| Environment | UAVs | Served | Rate | Deferred | Peak queue | Runtime s | Parcel util |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DU outdoor | 3 | 10.833 ± 2.183 | 18.056% | 49.167 | 49.167 | 13.331 | 32.778% |
| DU outdoor | 5 | 17.100 ± 2.820 | 28.500% | 42.900 | 42.967 | 17.240 | 19.667% |
| DU outdoor | 8 | 24.233 ± 4.289 | 40.389% | 35.767 | 35.900 | 23.273 | 12.396% |
| DU outdoor | 10 | 28.333 ± 6.504 | 47.222% | 31.667 | 31.800 | 27.058 | 9.833% |
| Synthetic | 3 | 25.233 ± 3.025 | 42.056% | 34.767 | 35.667 | 2.726 | 33.333% |
| Synthetic | 5 | 36.300 ± 7.293 | 60.500% | 23.700 | 25.333 | 3.453 | 20.000% |
| Synthetic | 8 | 47.700 ± 15.434 | 79.500% | 12.300 | 14.567 | 4.351 | 12.188% |
| Synthetic | 10 | 52.367 ± 19.728 | 87.278% | 7.633 | 10.333 | 4.403 | 9.250% |

[Open the V1 fleet sensitivity chart](../../Experiment%20Reports/assets/v1/v1_fleet_sensitivity.pdf)

**Core finding:** More UAVs improve service rate, but runtime also increases because the bounded assignment search has more combinations to evaluate.

## Arrival phase verification

Every row should contain the exact configured phase counts. This is a generation and experiment contract check, not a performance metric.

| Tasks | High | Medium | Low | Rows with this split |
| --- | ---: | ---: | ---: | ---: |
| 30 | 15 | 10 | 5 | 80 |
| 60 | 30 | 20 | 10 | 80 |
| 90 | 45 | 30 | 15 | 80 |

## Runtime and search bottleneck evidence

Route share is computed as total route evaluation time divided by total planner time for the grouped rows. Candidate counts are the number of bounded joint candidates actually evaluated across dispatches.

| Environment | Mean planner s | Min s | Max s | Mean candidates | Max dispatch candidates | Route share | Truncated dispatches |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DU outdoor | 20.223 | 3.325 | 62.198 | 249476.700 | 50000.000 | 96.754% | 497 |
| Synthetic | 3.731 | 0.157 | 14.430 | 65210.608 | 50000.000 | 95.440% | 115 |

[Open the V1 runtime bottleneck chart](../../Experiment%20Reports/assets/v1/v1_runtime_bottleneck.pdf)

### Ten slowest individual runs

| Environment | Seed | Tasks | UAVs | Served | Runtime s | Planner s | Candidates | Truncated |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DU outdoor | 108 | 60 | 10 | 34.000 | 62.203 | 62.198 | 229572.000 | 4 |
| DU outdoor | 108 | 90 | 8 | 25.000 | 59.444 | 59.439 | 345304.000 | 6 |
| DU outdoor | 108 | 90 | 10 | 31.000 | 50.290 | 50.287 | 268368.000 | 5 |
| DU outdoor | 108 | 60 | 8 | 27.000 | 47.610 | 47.607 | 278638.000 | 5 |
| DU outdoor | 104 | 90 | 10 | 30.000 | 44.352 | 44.346 | 625025.000 | 12 |
| DU outdoor | 102 | 90 | 10 | 31.000 | 42.033 | 42.028 | 500035.000 | 9 |
| DU outdoor | 103 | 90 | 10 | 31.000 | 41.340 | 41.334 | 568571.000 | 11 |
| DU outdoor | 108 | 90 | 5 | 20.000 | 41.187 | 41.185 | 174027.000 | 3 |
| DU outdoor | 110 | 60 | 10 | 23.000 | 41.068 | 41.058 | 705859.000 | 6 |
| DU outdoor | 108 | 90 | 3 | 12.000 | 39.521 | 39.519 | 6228.000 | 0 |

## Core findings

1. Higher task load lowers service rate and increases queue pressure in both environments.
2. More UAVs improve service rate, but the larger fleet also increases bounded search cost and runtime.
3. DU outdoor is the harder tested environment, with lower service and higher runtime than Synthetic.
4. Route evaluation is the dominant measured planner cost, so route reuse and early feasibility pruning are the clearest optimization targets.
5. Search truncation is reported explicitly. A run that reaches the candidate limit demonstrates bounded V1 behavior, not a global optimum.

## Limitations and next step

V1 is a transparent bounded reference planner, not the final mathematical PGBM optimizer. It keeps the individual task model, current Synthetic and DU scene generators, one sufficient base supply, fixed active routes, and the existing collision aware routing layer. Recourse and rerouting are deliberately deferred. The next step is to design an efficient planner using the route and search bottleneck evidence, then compare that planner against this heavy V1 reference before introducing recourse.

## Reproducibility artifacts

- `Simulation/results/pgbm_v1_two_hour_experiments/raw_metrics/pgbm_v1_two_hour_matrix_metrics_tasks_30_60_90_uavs_3_5_8_10_seeds_101_110.csv` contains all raw rows.
- `Simulation/experiments/run_pgbm_v1_experiment_matrix.py` runs the default heavy matrix.
- `Simulation/pgbm_sim/experiment.py` contains the matrix runner and metric assembly.
- `Simulation/pgbm_sim/event_simulation.py` contains the 120 minute event clock and queue execution.
- `Experiment Reports/V1/pgbm_v1_simulation_findings_bn.tex` is the PDF source for the formatted report.
