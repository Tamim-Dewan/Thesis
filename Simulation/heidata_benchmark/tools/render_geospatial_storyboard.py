"""Render five interactive shared-map HTML views of the OSM anchored scenario."""

from __future__ import annotations

import argparse
from pathlib import Path

from heidata_benchmark.environment import build_geospatial_scenario
from heidata_benchmark.environment_render import write_geospatial_storyboard_html
from heidata_benchmark.geospatial import load_osm_context
from heidata_benchmark.library import build_mesh_library
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-manifest", type=Path, default=Path("heidata_benchmark/data/sample/manifest.json"))
    parser.add_argument("--osm-context", type=Path, default=Path("heidata_benchmark/data/sample/osm_context.v1.geojson"))
    parser.add_argument("--scenario", type=Path, default=Path("heidata_benchmark/data/sample/scenario.v1.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/heidata_storyboard_html"))
    args = parser.parse_args()
    scenario = build_geospatial_scenario(
        args.scenario, load_osm_context(args.osm_context), build_mesh_library(args.asset_manifest)
    )
    for view, target in write_geospatial_storyboard_html(scenario, args.output_dir).items():
        print(f"Wrote {view}: {target}")


if __name__ == "__main__":
    main()
