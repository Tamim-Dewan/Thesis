"""Build the OSM anchored static heiDATA benchmark and its audit outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .environment import build_geospatial_scenario, write_scenario_json
from .environment_render import write_scenario_html
from .geospatial import load_osm_context
from .library import build_mesh_library


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-manifest", type=Path, default=Path("heidata_benchmark/data/sample/manifest.json"))
    parser.add_argument("--osm-context", type=Path, default=Path("heidata_benchmark/data/sample/osm_context.v1.geojson"))
    parser.add_argument("--scenario", type=Path, default=Path("heidata_benchmark/data/sample/scenario.v1.json"))
    parser.add_argument("--html", type=Path, default=Path("results/heidata_geospatial_benchmark.html"))
    parser.add_argument("--output", type=Path, default=Path("results/heidata_geospatial_scenario.json"))
    parser.add_argument("--library-output", type=Path, default=Path("results/heidata_mesh_library.json"))
    args = parser.parse_args()
    library = build_mesh_library(args.asset_manifest)
    context = load_osm_context(args.osm_context)
    scenario = build_geospatial_scenario(args.scenario, context, library)
    write_scenario_html(scenario, args.html)
    write_scenario_json(scenario, args.output)
    args.library_output.parent.mkdir(parents=True, exist_ok=True)
    args.library_output.write_text(json.dumps(library.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
    print(f"Preview: {args.html}")
    print(f"Scenario: {args.output}")
    print(f"Mesh library: {args.library_output}")
    print(f"Mapped buildings: {len(scenario.buildings)}")
    print(f"Template buildings: {sum(item.asset_id is not None for item in scenario.buildings)}")
    print(f"Collision volumes: {len(scenario.collision_volumes)}")
    print(f"Navigation free cells: {scenario.navigation.free_cell_count}")


if __name__ == "__main__":
    main()
