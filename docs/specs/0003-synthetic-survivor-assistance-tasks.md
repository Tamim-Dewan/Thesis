# 0003 Synthetic survivor assistance tasks

**Status**: Assumed
**Date**: 2026-09-24
**Authorized by**: Researcher during the complete simulation build goal

## Owed decision

The task generation feature still needs formal architecture review for the
final probability distributions and planner utility calibration.

## Assumption built on

Each accepted scan detection becomes a supply delivery task. Task locations
come from unique valid candidate sites in a generated disaster scene. The first
version uses food, water, and medical item types, a synthetic severity score,
integer item demand, a detected survivor position, and a UAV drop off position.
Tasks are pending at creation and become actionable after their detection time.
The scenario also records item weights, payload mass, shared units, and the common exponential
service value model metadata.

## Code area

`Simulation/pgbm_sim/tasks.py`, `Simulation/tests/test_tasks.py`, and the
package exports.

## Requirements

Tasks must be deterministic for the same scene, configuration, and seed. Task
locations must be valid and unique. Values must be bounded and JSON compatible.
The generator must expose the fields required by the current report contract and
the later PGBM planner. Service value is deferred to the planner phase.

## Ratify

This decision was recorded during implementation, not deliberated separately.
Run `/architect synthetic survivor assistance task generation` to ratify or
revise it. The assumption does not block continued implementation.
