# Initial Solution V1 Heavy Experiment Findings Report

**Date**: 2026-09-27

## Executive summary

Initial Solution V1 was evaluated as a seeded, two hour, event driven bounded brute force reference planner. The replacement evidence contains **180 rows**, covering 2 environments, task loads 30, 60, 90, UAV counts 2, 3, 4, and seeds 101 through 110.

The workload is intentionally much heavier than the earlier six task report. New tasks are detected in a high, medium, and low phase, remain queued when all UAVs are busy, and are planned only at dispatch opportunities. Active missions are fixed, so recourse and rerouting remain outside V1.

The measured planner bottleneck is route evaluation. Across the complete matrix, route construction accounts for approximately **98.700%** of planner time. Synthetic is the faster environment on average, while DU outdoor is the slower environment. The current heavy run observed **75 dispatches that reached the candidate search limit**; those cases are reported as bounded search evidence, not hidden as optimal results.

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
| UAV counts | 2, 3, 4 |
| Seeds | 101 through 110 (10 seeds) |
| Total rows | 180 |
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
| DU outdoor | 9.300 ± 3.093 | 31.000% | 20.700 ± 3.093 | 20.700 | 34.614 | 2597.699 | 16.570 |
| Synthetic | 20.200 ± 0.632 | 67.333% | 9.800 ± 0.632 | 11.200 | 29.647 | 2208.421 | 2.869 |

## Complete task load and fleet matrix

The following table reports every environment, task load, and UAV count case. Each row aggregates the seed replicates for that case.

| Environment | Tasks | UAVs | Served | Rate | Deferred | Peak queue | Delay min | Parcel util | Runtime s | Route share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DU outdoor | 30 | 2 | 6.700 ± 2.163 | 22.333% | 23.300 ± 2.163 | 23.300 | 34.377 | 43.750% | 12.132 | 99.584% |
| DU outdoor | 30 | 3 | 9.300 ± 3.093 | 31.000% | 20.700 ± 3.093 | 20.700 | 34.614 | 29.167% | 16.570 | 99.059% |
| DU outdoor | 30 | 4 | 12.200 ± 3.882 | 40.667% | 17.800 ± 3.882 | 17.800 | 35.194 | 22.500% | 18.067 | 98.805% |
| DU outdoor | 60 | 2 | 6.700 ± 1.059 | 11.167% | 53.300 ± 1.059 | 53.300 | 36.348 | 48.750% | 11.690 | 99.890% |
| DU outdoor | 60 | 3 | 9.400 ± 1.506 | 15.667% | 50.600 ± 1.506 | 50.600 | 36.090 | 32.500% | 16.577 | 99.629% |
| DU outdoor | 60 | 4 | 12.500 ± 1.581 | 20.833% | 47.500 ± 1.581 | 47.500 | 35.306 | 25.000% | 19.721 | 98.612% |
| DU outdoor | 90 | 2 | 6.900 ± 0.994 | 7.667% | 83.100 ± 0.994 | 83.100 | 34.516 | 48.750% | 12.839 | 99.439% |
| DU outdoor | 90 | 3 | 9.800 ± 1.619 | 10.889% | 80.200 ± 1.619 | 80.200 | 34.046 | 33.333% | 18.128 | 99.262% |
| DU outdoor | 90 | 4 | 12.500 ± 2.224 | 13.889% | 77.500 ± 2.224 | 77.500 | 33.538 | 25.000% | 20.423 | 98.665% |
| Synthetic | 30 | 2 | 14.400 ± 0.966 | 48.000% | 15.600 ± 0.966 | 16.100 | 30.208 | 50.000% | 2.279 | 99.560% |
| Synthetic | 30 | 3 | 20.200 ± 0.632 | 67.333% | 9.800 ± 0.632 | 11.200 | 29.647 | 33.333% | 2.869 | 99.249% |
| Synthetic | 30 | 4 | 23.600 ± 1.174 | 78.667% | 6.400 ± 1.174 | 8.600 | 26.333 | 25.000% | 3.319 | 95.836% |
| Synthetic | 60 | 2 | 14.300 ± 1.947 | 23.833% | 45.700 ± 1.947 | 45.700 | 27.281 | 50.000% | 2.694 | 99.085% |
| Synthetic | 60 | 3 | 20.800 ± 2.781 | 34.667% | 39.200 ± 2.781 | 39.500 | 26.399 | 33.333% | 4.352 | 95.936% |
| Synthetic | 60 | 4 | 26.700 ± 2.669 | 44.500% | 33.300 ± 2.669 | 33.400 | 25.317 | 25.000% | 5.500 | 95.360% |
| Synthetic | 90 | 2 | 15.500 ± 0.850 | 17.222% | 74.500 ± 0.850 | 74.500 | 25.680 | 50.000% | 2.457 | 99.583% |
| Synthetic | 90 | 3 | 21.600 ± 1.174 | 24.000% | 68.400 ± 1.174 | 68.400 | 24.910 | 33.333% | 4.452 | 98.168% |
| Synthetic | 90 | 4 | 27.700 ± 1.636 | 30.778% | 62.300 ± 1.636 | 62.300 | 24.647 | 25.000% | 6.951 | 94.429% |

## Task load effect

These values average across all three fleet sizes and all seeds. They show how the workload itself changes service and runtime.

| Environment | Tasks | Served | Rate | Peak queue | Candidates | Planner s | Route share | Truncated dispatches |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DU outdoor | 30 | 9.400 ± 3.784 | 31.333% | 20.600 | 41212.567 | 15.589 | 99.097% | 15 |
| DU outdoor | 60 | 9.533 ± 2.763 | 15.889% | 50.467 | 34163.733 | 15.994 | 99.275% | 15 |
| DU outdoor | 90 | 9.733 ± 2.840 | 10.815% | 80.267 | 46910.800 | 17.128 | 99.069% | 15 |
| Synthetic | 30 | 19.400 ± 3.971 | 64.667% | 11.967 | 14694.100 | 2.821 | 97.995% | 4 |
| Synthetic | 60 | 20.600 ± 5.685 | 34.333% | 39.533 | 39772.167 | 4.180 | 96.360% | 11 |
| Synthetic | 90 | 21.600 ± 5.210 | 24.000% | 68.400 | 46214.600 | 4.618 | 96.544% | 15 |

## Fleet size effect

These values average across all three task loads and all seeds. They isolate the effect of adding or removing UAVs under the same workload family.

| Environment | UAVs | Served | Rate | Deferred | Peak queue | Runtime s | Parcel util |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DU outdoor | 2 | 6.767 ± 1.455 | 11.278% | 53.233 | 53.233 | 12.220 | 47.083% |
| DU outdoor | 3 | 9.500 ± 2.129 | 15.833% | 50.500 | 50.500 | 17.092 | 31.667% |
| DU outdoor | 4 | 12.400 ± 2.647 | 20.667% | 47.600 | 47.600 | 19.404 | 24.167% |
| Synthetic | 2 | 14.733 ± 1.413 | 24.556% | 45.267 | 45.433 | 2.477 | 50.000% |
| Synthetic | 3 | 20.867 ± 1.814 | 34.778% | 39.133 | 39.700 | 3.891 | 33.333% |
| Synthetic | 4 | 26.000 ± 2.573 | 43.333% | 34.000 | 34.767 | 5.257 | 25.000% |

## Arrival phase verification

Every row should contain the exact configured phase counts. This is a generation and experiment contract check, not a performance metric.

| Tasks | High | Medium | Low | Rows with this split |
| --- | ---: | ---: | ---: | ---: |
| 30 | 15 | 10 | 5 | 60 |
| 60 | 30 | 20 | 10 | 60 |
| 90 | 45 | 30 | 15 | 60 |

## Runtime and search bottleneck evidence

Route share is computed as total route evaluation time divided by total planner time for the grouped rows. Candidate counts are the number of bounded joint candidates actually evaluated across dispatches.

| Environment | Mean planner s | Min s | Max s | Mean candidates | Max dispatch candidates | Route share | Truncated dispatches |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DU outdoor | 16.237 | 1.943 | 44.615 | 40762.367 | 50000.000 | 99.146% | 45 |
| Synthetic | 3.873 | 0.574 | 12.782 | 33560.289 | 50000.000 | 96.830% | 30 |

### Ten slowest individual runs

| Environment | Seed | Tasks | UAVs | Served | Runtime s | Planner s | Candidates | Truncated |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| DU outdoor | 108 | 30 | 4 | 6.000 | 44.617 | 44.615 | 212147.000 | 3 |
| DU outdoor | 108 | 90 | 4 | 13.000 | 43.291 | 43.287 | 39034.000 | 0 |
| DU outdoor | 108 | 30 | 3 | 5.000 | 41.922 | 41.921 | 111556.000 | 2 |
| DU outdoor | 108 | 30 | 2 | 4.000 | 33.666 | 33.665 | 15661.000 | 0 |
| DU outdoor | 108 | 60 | 3 | 10.000 | 33.041 | 33.039 | 861.000 | 0 |
| DU outdoor | 108 | 60 | 4 | 14.000 | 31.730 | 31.729 | 15618.000 | 0 |
| DU outdoor | 108 | 90 | 3 | 9.000 | 31.644 | 31.642 | 1936.000 | 0 |
| DU outdoor | 108 | 90 | 2 | 6.000 | 30.801 | 30.799 | 1375.000 | 0 |
| DU outdoor | 102 | 60 | 4 | 13.000 | 30.715 | 30.710 | 70314.000 | 1 |
| DU outdoor | 104 | 30 | 4 | 13.000 | 29.156 | 29.155 | 49163.000 | 0 |

## Findings

1. The previous six task experiment was too small to characterize queue pressure. The replacement matrix raises the task load to 30, 60, and 90 and produces a much wider range of deferred work and runtime.
2. The 3:2:1 high, medium, and low arrival structure is reproduced exactly for every task load. The high phase therefore creates the initial queue pressure that the event runner must absorb.
3. More UAVs generally improve service rate and reduce queue pressure, but the improvement is environment and workload dependent. Additional UAVs also create more candidate assignment combinations, so fleet growth is not computationally free.
4. DU outdoor runs are expected to be slower and less serviceable than Synthetic runs in this implementation because the mapped polygon geometry creates more difficult route searches and longer travel paths. The matrix reports the magnitude rather than treating that difference as a universal real world law.
5. Route evaluation is the dominant measured cost. This makes route caching, reuse of fixed leg paths, early feasibility pruning, and a scalable candidate search the immediate targets for the next solution.
6. Search truncation is reported explicitly. If a case reaches the 50,000 candidate limit, its result demonstrates bounded V1 behavior under load and must not be interpreted as a global optimum.
7. Safe return rate is a model feasibility result. It is not a field reliability estimate because the current energy coefficients, speed, turnaround time, and base supply policy are research assumptions.

## Limitations and next step

V1 is a transparent bounded reference planner, not the final mathematical PGBM optimizer. It keeps the individual task model, current Synthetic and DU scene generators, one sufficient base supply, fixed active routes, and the existing collision aware routing layer. Recourse and rerouting are deliberately deferred. The next step is to design an efficient planner using the route and search bottleneck evidence, then compare that planner against this heavy V1 reference before introducing recourse.

## Reproducibility artifacts

- `Simulation/results/pgbm_v1_two_hour_experiments/raw_metrics/pgbm_v1_two_hour_matrix_metrics_tasks_30_60_90_uavs_3_5_8_10_seeds_101_110.csv` contains all raw rows.
- `Simulation/run_pgbm_v1_experiment_matrix.py` runs the default heavy matrix.
- `Simulation/pgbm_sim/experiment.py` contains the matrix runner and metric assembly.
- `Simulation/pgbm_sim/event_simulation.py` contains the 120 minute event clock and queue execution.
- `Experiment Reports/V1/pgbm_v1_simulation_findings_bn.tex` is the PDF source for the formatted report.
