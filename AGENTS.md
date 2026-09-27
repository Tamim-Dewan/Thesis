# PGBM Thesis and Simulation

## Stack

- **Language / Runtime**: Python 3.9 or later, with LaTeX for the thesis
- **Framework**: Plain Python modules with Plotly visualisation
- **Key dependencies**: NumPy, pytest, Plotly, TeX Live
- **Package manager**: pip for Python, TeX Live for LaTeX

## Build approach

Skateboard, build the smallest usable simulation slice, then expand it.

## Commands

```bash
# Install
python3 -m pip install -r Simulation/requirements.txt

# Run a simulation
cd Simulation && python3 run_simulation.py --mode du_outdoor --severity moderate --seed 20260924

# Build check
python3 -m compileall -q Simulation

# Test
python3 -m pytest -q Simulation
```

## Specs

Specifications are stored in `docs/specs/`. The project scope is in `docs/scope/`.

## Rules

- Keep seeded generation deterministic and keep source data separate from derived simulation assumptions.
- Treat `Simulation/pgbm_sim` as the main simulator and `Simulation/heidata_benchmark` as a separate benchmark area.
- Runtime generation must work from local data and must not download raw data.
- Treat `Simulation/results/` as generated evidence, not as source code.
- Do not describe `pgbm_heuristic_v1` as the final mathematical PGBM optimizer.
- Preserve the explicit provenance of OSM geometry, heiDATA meshes, synthetic damage, and derived geometry.
- Keep thesis drafts and generated PDFs separate until one canonical formulation is selected.

## Agent skills

- [plotly](.agents/skills/plotly/): `davila7/claude-code-templates`, Plotly based scientific visualisation

## Context files

- [Simulation/AGENTS.md](Simulation/AGENTS.md): simulator commands, geometry contracts, and provenance rules.
- [Simulation/heidata_benchmark/AGENTS.md](Simulation/heidata_benchmark/AGENTS.md): local mesh benchmark conventions.
- [Research Source/AGENTS.md](Research%20Source/AGENTS.md): thesis source layout and LaTeX gotchas.

_Drafted by /audit from the repo, worth a quick human pass. Edit freely: once a line stops matching this draft, later runs treat it as curated and will flag rather than overwrite it._
