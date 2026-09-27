# Rationale for environment configuration and geometry

## Context

The existing simulation package validates experiment settings, derives stable seeds, and defines future metrics, but it cannot yet create a scene. The first scene must be simple enough for repeated research experiments and clear enough to inspect visually.

This feature is a new part of the existing Python package. It is not a flight physics simulator. It does not include survivor tasks, UAV movement, route planning, or task replacement.

## Options considered

### Continuous rectangular geometry

This uses a bounded world and typed axis aligned boxes. Ground anchored and elevated profiles provide useful vertical variation without requiring detailed meshes or flight physics.

### Voxel geometry

This represents the world as occupied and free cells. It supports grid routing naturally, but adds resolution choices, memory cost, and conversion work before the first task can be generated.

### Robotics simulator

Gazebo or a similar simulator would provide sensors, dynamics, and vehicle behavior. Those capabilities are valuable for flight control or perception research, but they are outside the first PGBM planning experiment.

## Rationale

The research model needs a repeatable geometric world, not a flight control stack. Typed rectangular geometry keeps the environment understandable, while deterministic seeds make experiments comparable. A package interface keeps the model reusable, and the Plotly figure gives direct visual evidence of what each scenario contains.
