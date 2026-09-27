# heiDATA benchmark context

This package is a separate L’Aquila benchmark. It does not import or modify `pgbm_sim`.

## Commands

Run from `Simulation`:

```bash
PYTHONPATH=. python3 -m heidata_benchmark.geo_cli
PYTHONPATH=. python3 -m heidata_benchmark.source_cli heidata_benchmark/data/sample/manifest.json --pair extreme_b001
PYTHONPATH=. python3 -m heidata_benchmark.tools.render_geospatial_storyboard
PYTHONPATH=. python3 -m pytest -q heidata_benchmark/tests
```

## Conventions

The source faithful view preserves OBJ coordinates and only maps source `X,Y,Z` to display `X,Z,Y`, with source `Y` as height. The geospatial scenario uses one visual building instance per selected OSM building. OSM roads remain map evidence, but the main airborne preview does not render them as active flight obstacles. Operational 3D bounds are based on mapped buildings and derived overlays, not the full road extent.

Ground rubble is stored and rendered as deterministic eight vertex three dimensional pieces. Collision volumes remain conservative bounds around the visual geometry. UAV base pads are selected near the mapped building cluster and must be free at ground and minimum flight altitude.

heiDATA meshes are labelled damage templates, not observed damage measurements for the OSM buildings. Scenario derived damage is controlled geometry and must retain its non observed provenance.
The post earthquake damage and airborne previews also render source only and
`no_damage` scenario buildings as `standing building volume` meshes. These use
the stored OSM footprint extrusion already present in the scenario, while
template and derived damage meshes remain separate layers.

The main preview is `results/heidata_geospatial_benchmark.html`. The five view storyboard is in `results/heidata_storyboard_html/`. The source faithful audit is `results/heidata_benchmark_preview.html`.

_Drafted by /sync from the introducing change, worth a quick human pass._
