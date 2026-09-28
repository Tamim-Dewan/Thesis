"""Build an ordered 32 building neighbourhood from the full heiDATA archive."""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable

from heidata_benchmark.full_dataset import build_full_mesh_library, write_full_manifest
from pgbm_sim import (
    ExecutionConfig,
    SceneConfig,
    TaskConfig,
    UAVConfig,
    build_scenario,
    execute_plan,
    plan_tasks,
    plot_building_layout,
    plot_collision_view,
    plot_damage_view,
    plot_disaster_scene,
    save_scenario,
)


EARTH_RADIUS_M = 6_378_137.0
ORIGIN_WGS84 = (13.3985, 42.3505)
GRID_ROWS = 4
GRID_COLUMNS = 8
BUILDING_COUNT = GRID_ROWS * GRID_COLUMNS


def _source_number(source_id: str) -> int:
    match = re.search(r"(\d+)$", source_id)
    return int(match.group(1)) if match else 10_000


def _spread(entries: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    """Take deterministic, well spaced entries from a sorted source pool."""

    if len(entries) < count:
        raise RuntimeError("full heiDATA archive does not contain enough eligible assets")
    if count == 1:
        return [entries[len(entries) // 2]]
    positions = [round(index * (len(entries) - 1) / (count - 1)) for index in range(count)]
    return [entries[position] for position in positions]


def _eligible_entries(
    manifest: dict[str, Any],
    event_phase: str,
    damage_grade: str,
    maximum_size_bytes: int,
    used_sources: set[str],
) -> list[dict[str, Any]]:
    return sorted(
        (
            item
            for item in manifest.get("assets", [])
            if item.get("event_phase") == event_phase
            and item.get("damage_grade") == damage_grade
            and int(item.get("size_bytes", 0)) <= maximum_size_bytes
            and str(item.get("source_id")) not in used_sources
        ),
        key=lambda item: (_source_number(str(item["source_id"])), str(item["asset_id"])),
    )


def _select_assets(manifest_path: Path) -> tuple[dict[str, list[str]], Any]:
    """Select 32 distinct source buildings, then keep only reviewed post meshes."""

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    used_sources: set[str] = set()
    selected: dict[str, list[str]] = {"intact": [], "minor": [], "major": [], "destroyed": []}
    candidate_pools: dict[str, list[dict[str, Any]]] = {}

    # The size ceilings keep the browser artifact responsive while still
    # selecting from the complete downloaded archive rather than one repeated
    # template. Every selected source id remains unique in this scene.
    pre_groups = (("intact", 10, 8_000_000), ("minor", 8, 8_000_000))
    for label, count, maximum_size in pre_groups:
        candidates = _eligible_entries(manifest, "pre", "no_damage", maximum_size, used_sources)
        chosen = _spread(candidates, count)
        selected[label] = [str(item["asset_id"]) for item in chosen]
        used_sources.update(str(item["source_id"]) for item in chosen)

    post_groups = (("major", "extreme", 10, 15_000_000, 24), ("destroyed", "destruction", 4, 30_000_000, 12))
    for label, damage_grade, count, maximum_size, pool_size in post_groups:
        candidates = _eligible_entries(manifest, "post", damage_grade, maximum_size, used_sources)
        pool = _spread(candidates, pool_size)
        candidate_pools[label] = pool
        used_sources.update(str(item["source_id"]) for item in pool)

    required_asset_ids = selected["intact"] + selected["minor"]
    required_asset_ids += [str(item["asset_id"]) for pool in candidate_pools.values() for item in pool]
    library = build_full_mesh_library(manifest_path, required_asset_ids)
    library_by_id = {asset.asset_id: asset for asset in library.assets}

    for label, pool in candidate_pools.items():
        accepted = [
            str(item["asset_id"])
            for item in pool
            if library_by_id[str(item["asset_id"])].review.status == "accepted"
        ]
        required_count = 10 if label == "major" else 4
        if len(accepted) < required_count:
            raise RuntimeError(
                "only {} accepted {} meshes were found, but {} are required".format(
                    len(accepted), label, required_count
                )
            )
        selected[label] = accepted[:required_count]

    if sum(len(items) for items in selected.values()) != BUILDING_COUNT:
        raise RuntimeError("selected heiDATA asset count does not match the 4 by 8 neighbourhood")
    return selected, library


def _local_to_wgs84(x: float, y: float) -> list[float]:
    lon, lat = ORIGIN_WGS84
    return [
        lon + math.degrees(x / (EARTH_RADIUS_M * math.cos(math.radians(lat)))),
        lat + math.degrees(y / EARTH_RADIUS_M),
    ]


def _ring_wgs84(x0: float, y0: float, width: float, depth: float) -> list[list[float]]:
    points = ((x0, y0), (x0 + width, y0), (x0 + width, y0 + depth), (x0, y0 + depth), (x0, y0))
    return [_local_to_wgs84(x, y) for x, y in points]


def _line_wgs84(points: Iterable[tuple[float, float]]) -> list[list[float]]:
    return [_local_to_wgs84(x, y) for x, y in points]


def _slot(index: int) -> tuple[int, int, float, float, float, float]:
    row, column = divmod(index, GRID_COLUMNS)
    center_x = 24.0 + column * 32.0
    center_y = 24.0 + row * 32.0
    width = 16.0 + 2.0 * ((row + column) % 3)
    depth = 12.0 + 2.0 * ((2 * row + column) % 3)
    return row, column, center_x - width / 2.0, center_y - depth / 2.0, width, depth


def _write_context(output_dir: Path) -> Path:
    features: list[dict[str, Any]] = []
    for index in range(BUILDING_COUNT):
        row, column, x0, y0, width, depth = _slot(index)
        building_id = "nh_b_{:02d}".format(index + 1)
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [_ring_wgs84(x0, y0, width, depth)]},
                "properties": {
                    "kind": "building",
                    "osm_id": building_id,
                    "osm_tags": {
                        "name": "Controlled neighbourhood building {:02d}".format(index + 1),
                        "source_type": "derived_controlled_layout",
                        "layout_row": str(row + 1),
                        "layout_column": str(column + 1),
                    },
                    "provenance": "derived_controlled_neighbourhood",
                },
            }
        )

    # These lines are source context only. The airborne scene keeps roads out
    # of active collision geometry, but retaining them makes the ordered block
    # rule explicit and auditable in the local context artifact.
    left = 4.0
    right = 268.0
    bottom = 4.0
    top = 140.0
    for road_index in range(GRID_ROWS - 1):
        y = 40.0 + road_index * 32.0
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": _line_wgs84(((left, y), (right, y)))},
                "properties": {
                    "kind": "road",
                    "osm_id": "nh_road_h_{:02d}".format(road_index + 1),
                    "osm_tags": {"highway": "residential", "name": "Controlled east west street {:02d}".format(road_index + 1)},
                    "provenance": "derived_controlled_neighbourhood",
                },
            }
        )
    for road_index in range(GRID_COLUMNS - 1):
        x = 40.0 + road_index * 32.0
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": _line_wgs84(((x, bottom), (x, top)))},
                "properties": {
                    "kind": "road",
                    "osm_id": "nh_road_v_{:02d}".format(road_index + 1),
                    "osm_tags": {"highway": "residential", "name": "Controlled north south street {:02d}".format(road_index + 1)},
                    "provenance": "derived_controlled_neighbourhood",
                },
            }
        )

    context = {
        "type": "FeatureCollection",
        "name": "heidata_controlled_neighborhood_context",
        "properties": {
            "schema_version": "osm_context.v1",
            "snapshot_at": "2026-09-27",
            "source": "derived controlled neighbourhood layout generated from the full heiDATA benchmark",
            "license": "project source artifact",
            "crs": "EPSG:4326",
            "projection": "local east north tangent plane used only for deterministic derived placement",
            "provenance": "not an OSM extract and not a measured L'Aquila neighbourhood",
        },
        "features": features,
    }
    path = output_dir / "heidata_controlled_neighborhood_context.v1.geojson"
    path.write_text(json.dumps(context, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_scenario(output_dir: Path, context_path: Path, manifest_path: Path, selected: dict[str, list[str]]) -> Path:
    category_pattern = ["intact", "minor", "major", "intact", "major", "minor", "major", "destroyed"] * 4
    category_pattern[2] = "intact"
    category_pattern[10] = "intact"
    cursors = {label: 0 for label in selected}
    bindings: list[dict[str, str]] = []
    for index, label in enumerate(category_pattern):
        asset_id = selected[label][cursors[label]]
        cursors[label] += 1
        binding: dict[str, str] = {"osm_id": "nh_b_{:02d}".format(index + 1), "asset_id": asset_id}
        if label == "minor":
            binding["damage_state_override"] = "minor"
        bindings.append(binding)

    values = {
        "schema_version": "scenario.v1",
        "scenario_id": "heidata_controlled_neighborhood_v1",
        "seed": 20260927,
        "default_building_height_m": 9.0,
        "collision_margin_m": 1.0,
        "overlap_tolerance_m": 0.05,
        "boundary_margin_m": 16.0,
        "maximum_flight_altitude_m": 50.0,
        "safe_pad_count": 2,
        "derive_rubble_for_destruction": True,
        "derive_rubble_for_major_damage": False,
        "excluded_osm_buildings": [],
        "blocked_road_ids": [],
        "navigation": {"cell_size_m": 6.0, "minimum_flight_altitude_m": 3.0, "altitude_step_m": 4.0},
        "template_bindings": bindings,
        "derived_damage_bindings": [],
        "notes": (
            "Thirty two distinct full heiDATA source buildings are placed in an ordered 4 by 8 derived neighbourhood. "
            "The layout is a controlled simulation input, not a measured OSM or L'Aquila reconstruction."
        ),
    }
    path = output_dir / "heidata_controlled_neighborhood_scenario.v1.json"
    path.write_text(json.dumps(values, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _write_layout(output_dir: Path, context_path: Path, manifest_path: Path, scenario_path: Path) -> Path:
    values = {
        "schema_version": "heidata_neighborhood_layout.v1",
        "source_context": str(context_path),
        "source_manifest": str(manifest_path),
        "source_scenario": str(scenario_path),
        "layout_rule": "ordered_controlled_grid_4x8.v1",
        "boundary_margin_m": 16.0,
        "maximum_airspace_m": 50.0,
        "active_road_geometry": False,
        "visual_context_only_osm_ids": [],
        "building_count": BUILDING_COUNT,
        "grid_rows": GRID_ROWS,
        "grid_columns": GRID_COLUMNS,
        "notes": (
            "Derived controlled neighbourhood for scale testing. Building footprints are orderly simulation slots; "
            "each visible mesh is a distinct accepted heiDATA asset and no slot is presented as a measured real building."
        ),
    }
    path = output_dir / "heidata_controlled_neighborhood_layout.v1.json"
    path.write_text(json.dumps(values, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=Path.home() / "Datasets" / "heiDATA_D3WZID")
    parser.add_argument("--output-dir", type=Path, default=Path("results/heidata_controlled_neighborhood_initial"))
    parser.add_argument("--seed", type=int, default=20260927)
    parser.add_argument("--task-count", type=int, default=8)
    parser.add_argument("--uav-count", type=int, default=4)
    parser.add_argument("--planner", choices=("initial_snapshot_greedy_v1", "pgbm_heuristic_v1", "nearest_task_first"), default="pgbm_heuristic_v1")
    args = parser.parse_args()

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = write_full_manifest(args.dataset_root)
    selected_assets, _library = _select_assets(manifest_path)
    context_path = _write_context(output_dir)
    source_scenario_path = _write_scenario(output_dir, context_path, manifest_path, selected_assets)
    layout_path = _write_layout(output_dir, context_path, manifest_path, source_scenario_path)

    uavs = UAVConfig(count=args.uav_count)
    scenario = build_scenario(
        SceneConfig(
            mode="heidata_neighborhood",
            severity="severe",
            seed=args.seed,
            uav_count=args.uav_count,
            template_path=str(layout_path),
        ),
        TaskConfig(task_count=args.task_count, seed=args.seed + 1),
        scenario_id="heidata_controlled_neighborhood_{}".format(args.seed),
        uav_config=uavs,
        execution_config=ExecutionConfig(start_time=30.0),
    )
    initial_plan = plan_tasks(scenario, uavs, method=args.planner)
    execution = execute_plan(scenario, initial_plan, uavs)
    scenario_path = output_dir / "heidata_controlled_neighborhood_initial.scenario.json"
    report_path = output_dir / "heidata_controlled_neighborhood_initial.json"
    save_scenario(scenario, str(scenario_path))
    report = {
        "schema_version": "simulation_run.v2",
        "scenario_file": str(scenario_path),
        "scenario": scenario.as_dict(),
        "uav_config": uavs.as_dict(),
        "initial_plan": initial_plan.as_dict(),
        "recourse": None,
        "execution": execution.as_dict(),
        "full_dataset_manifest": str(manifest_path),
        "selected_assets_by_state": selected_assets,
        "environment_provenance": (
            "Derived ordered 4 by 8 controlled neighbourhood using 32 distinct accepted heiDATA source meshes. "
            "This is a simulation scale benchmark, not a measured real world building map."
        ),
    }
    report_path.write_text(json.dumps(report, sort_keys=True, indent=2), encoding="utf-8")

    plot_disaster_scene(scenario.scene, tasks=scenario.tasks, show_context=False).write_html(
        str(output_dir / "heidata_controlled_neighborhood_environment.html"), include_plotlyjs=True, full_html=True
    )
    plot_building_layout(scenario.scene).write_html(
        str(output_dir / "heidata_controlled_neighborhood_layout.html"), include_plotlyjs=True, full_html=True
    )
    plot_damage_view(scenario.scene).write_html(
        str(output_dir / "heidata_controlled_neighborhood_damage_view.html"), include_plotlyjs=True, full_html=True
    )
    plot_collision_view(scenario.scene).write_html(
        str(output_dir / "heidata_controlled_neighborhood_collision_view.html"), include_plotlyjs=True, full_html=True
    )

    from render_step_by_step import render_step_by_step

    replay_path = output_dir / "heidata_controlled_neighborhood_initial_step_by_step.html"
    render_step_by_step(report_path, replay_path)
    print("Full manifest: {}".format(manifest_path))
    print("Run report: {}".format(report_path))
    print("Building count: {}".format(len(scenario.scene.structures)))
    print("Tasks: {} | Served: {} | Missed: {}".format(len(scenario.tasks), len(execution.served_task_ids), len(execution.missed_task_ids)))
    print("Environment view: {}".format(output_dir / "heidata_controlled_neighborhood_environment.html"))
    print("Layout view: {}".format(output_dir / "heidata_controlled_neighborhood_layout.html"))
    print("Step by step view: {}".format(replay_path))


if __name__ == "__main__":
    main()
