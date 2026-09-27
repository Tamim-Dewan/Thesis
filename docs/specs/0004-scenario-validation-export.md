# 0004 Scenario validation and export

**Status**: Assumed
**Date**: 2026-09-24
**Authorized by**: Researcher during the complete simulation build goal

## Owed decision

The final long term scenario schema and version migration policy still need
architecture review.

## Assumption built on

A scenario stores the scene configuration, scene seed, task configuration, task
seed, complete generated scene dictionary, complete task dictionaries, and a
schema version. Loading regenerates the scene and tasks from the stored local
inputs, validates canonical equality, and rejects tampered or stale artifacts.

The implementation update authorized on 2026-09-25 uses `scenario.v2` for
active exports. It additionally stores UAV, route, and execution configuration,
initial UAV states, and the small survivor task payload contract. Planner
assignments are intentionally excluded from scenario artifacts. Existing
`scenario.v1` artifacts are not migrated and are rejected by the active loader;
new artifacts must be regenerated.

## Code area

`Simulation/pgbm_sim/scenario.py`, `Simulation/tests/test_scenario.py`.

## Requirements

Scenario export must be deterministic JSON, local, reproducible, and explicit
when the stored source template or schema is incompatible.

## Ratify

Run `/architect scenario validation and export` to ratify or revise this
assumption.
