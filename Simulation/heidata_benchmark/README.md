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

## Dataset provenance

The data is from heiDATA, version 1.1, under CC BY 4.0. The source code published with the dataset is under GPL v3. The dataset page and its related publication must be cited in the thesis.
