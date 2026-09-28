# heiDATA benchmark environment

This package contains two different outputs for the thesis. It does not change the DU simulation package in `pgbm_sim`.

The `cli` preview is a synthetic benchmark composition. It arranges source meshes into a test scene and adds synthetic roads, a base, candidate sites, and derived heavy damage. It must not be described as a real geographic earthquake site.

The `source_cli` preview is source faithful. It retains the original local positions of the OBJ meshes and uses no grid, road, base, task, or artificial translation. The OBJ source uses Y as vertical. The viewer shows that vertical dimension as Plotly Z through the explicit mapping `(source X, source Y, source Z) -> (plot X, plot Z, plot Y)`.

The `geo_cli` preview is the thesis static environment. It uses a checked local OpenStreetMap snapshot for real building footprint and road positions in L'Aquila. It uses heiDATA OBJ files as explicitly labelled damage templates, not as surveyed OSM building geometry. Every final map building has one visual instance and one damage state only. The default HTML is an airborne operational view, so roads remain source evidence but are not rendered as active flight obstacles. The command creates source and map provenance, collision volumes, a static navigation grid, blocked zones, three dimensional derived rubble, and UAV base pads without changing `pgbm_sim`.

The sample scene uses real OBJ building geometry extracted from the public heiDATA dataset identified by `doi:10.11588/DATA/D3WZID`. It contains four benchmark states, no damage, heavy damage, extreme damage, and destruction.

The raw grade 3 archive contains a selected post event model with a very large coordinate spread. The default sample therefore derives a transparent partial collapse from the corresponding heiDATA pre event mesh and records that choice in the summary. Passing `--include-raw-heavy` enables the raw grade 3 model for inspection and exposes its quality flags.

## Run the preview

From the `Simulation` directory, run:

```bash
PYTHONPATH=. python3 -m heidata_benchmark.cli heidata_benchmark/data/sample/manifest.json
```

The command writes an interactive HTML preview and a JSON summary. The summary records the source files, damage grade, geometry metrics, quality flags, seed, and dataset identifier.

## Run the source faithful views

From the `Simulation` directory, run:

```bash
PYTHONPATH=. python3 -m heidata_benchmark.source_cli heidata_benchmark/data/sample/manifest.json --pair extreme_b001
```

This writes the canonical preview at `results/heidata_benchmark_preview.html`, a matching pre and post event pair overlay, and an alignment report. These are the correct files to use when discussing the original heiDATA geometry. The canonical preview maps OBJ `(X, Y, Z)` to Plotly `(X, Z, Y)`, because source `Y` is height; it contains no synthetic roads, candidate sites, base, or grid.

## Run the OSM anchored benchmark

From the `Simulation` directory, run:

```bash
PYTHONPATH=. python3 -m heidata_benchmark.geo_cli
```

This writes `results/heidata_geospatial_benchmark.html`, `results/heidata_geospatial_scenario.json`, and `results/heidata_mesh_library.json`. The stored OSM context is an offline snapshot. Do not call its heiDATA template bindings actual measured earthquake damage to the OSM buildings.

## Recreate the sample assets

The sample OBJ files can be extracted again from the public archive files with range requests:

```bash
PYTHONPATH=. python3 heidata_benchmark/tools/fetch_sample.py
```

This downloads only the selected sample entries, not the complete archives.

The OSM sample can be refreshed deliberately, then committed as a new dated snapshot. Runtime code never downloads it:

```bash
PYTHONPATH=. python3 heidata_benchmark/tools/fetch_osm_sample.py
```

## Run the full downloaded heiDATA environment

The complete archives are kept outside the repository at
`/Users/_d-one_/Datasets/heiDATA_D3WZID`. The full manifest indexes all 448 OBJ
members without extracting the 67 GB uncompressed archive contents. The
environment loads only the selected assets needed by the frozen L'Aquila
scenario.

From the thesis root, run:

```bash
PYTHONPATH=Simulation python3 Simulation/run_heidata_full.py \
  --dataset-root /Users/_d-one_/Datasets/heiDATA_D3WZID \
  --output-dir Simulation/results/heidata_full_initial_20260927
```

The command creates an earthquake environment view, a damage view, a collision
view, an initial solution report, and a step by step UAV replay. The replay uses
the existing initial planner and execution model at planning time `t = 30`.
The visual scenario uses a curated set of 13 unique full-archive focal meshes
(6 pre-event meshes and 7 post-event meshes). Three minor states use explicit
pre-event meshes with a declared minor-state override. Four additional intact
OSM footprints remain map context instead of being filled with unrelated
generic models. The full archive meshes remain generic damage templates, while
the frozen L'Aquila OSM snapshot supplies building positions and footprints.

## Run the ordered 32 building neighbourhood

The L'Aquila source mode remains the exact 17 building OSM reconstruction.
For scale testing, the separate `heidata_neighborhood` mode creates a
deterministic four by eight neighbourhood with 32 distinct accepted heiDATA
source meshes. Its footprints and street context are derived simulation
inputs, not measured L'Aquila or OSM geometry. Damage states are assigned as
10 intact, 8 minor, 10 major, and 4 destroyed buildings.

From the thesis root, run:

```bash
PYTHONPATH=Simulation python3 Simulation/run_heidata_neighborhood.py \
  --dataset-root /Users/_d-one_/Datasets/heiDATA_D3WZID \
  --output-dir Simulation/results/heidata_controlled_neighborhood_initial_20260927
```

The command writes the ordered footprint view, full 3D environment, damage and
collision views, and the initial solution replay. The full dataset remains
outside Git, and every building slot records its selected source asset.

## Dataset provenance

The data is from heiDATA, version 1.1, under CC BY 4.0. The source code published with the dataset is under GPL v3. The dataset page and its related publication must be cited in the thesis.
