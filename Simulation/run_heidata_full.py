"""Build the full heiDATA earthquake environment and its initial solution views."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from heidata_benchmark.full_dataset import write_full_manifest
from heidata_benchmark.geospatial import load_osm_context
from pgbm_sim import (
    ExecutionConfig,
    SceneConfig,
    TaskConfig,
    UAVConfig,
    build_scenario,
    execute_plan,
    plan_tasks,
    save_scenario,
    plot_collision_view,
    plot_damage_view,
    plot_disaster_scene,
)


REPO_ROOT = Path(__file__).resolve().parent
SOURCE_CONTEXT = REPO_ROOT / "heidata_benchmark" / "data" / "sample" / "osm_context.v1.geojson"
SOURCE_SCENARIO = REPO_ROOT / "heidata_benchmark" / "data" / "sample" / "scenario.v1.json"

CURATED_MAJOR_ASSETS = (
    "post:grade4_b_010_post.obj",
    "post:grade4_b_025_post.obj",
    "post:grade4_b_048_post.obj",
)
CURATED_MINOR_ASSETS = (
    "pre:pre_b_011_pre.obj",
    "pre:pre_b_067_pre.obj",
    "pre:pre_b_078_pre.obj",
)
CURATED_INTACT_ASSETS = (
    "pre:pre_b_009_pre.obj",
    "pre:pre_b_012_pre.obj",
    "pre:pre_b_054_pre.obj",
    "pre:pre_b_077_pre.obj",
    "pre:pre_b_085_pre.obj",
    "pre:pre_b_096_pre.obj",
)


def _write_visual_scenario(output_dir: Path) -> Path:
    """Build a curated visual composition without arbitrary mesh repetition."""

    values = json.loads(SOURCE_SCENARIO.read_text(encoding="utf-8"))
    context = load_osm_context(SOURCE_CONTEXT)
    excluded = {item["osm_id"] for item in values.get("excluded_osm_buildings", [])}
    active_ids = sorted(building.osm_id for building in context.buildings if building.osm_id not in excluded)
    bindings = list(values.get("template_bindings", []))
    derived = list(values.get("derived_damage_bindings", []))
    bound_ids = {item["osm_id"] for item in bindings}
    derived_by_id = {item["osm_id"]: item for item in derived}
    source_id_pattern = re.compile(r"(b_\d+)")
    used_sources = {
        match.group(1)
        for item in bindings
        for match in [source_id_pattern.search(str(item["asset_id"]))]
        if match is not None
    }
    def take_asset(pool: tuple[str, ...], purpose: str) -> str:
        for asset_id in pool:
            match = source_id_pattern.search(asset_id)
            source_id = match.group(1) if match else None
            if source_id not in used_sources:
                used_sources.add(source_id)
                return asset_id
        raise RuntimeError("curated heiDATA asset pool is exhausted for {}".format(purpose))

    unbound_intact_ids = [
        osm_id
        for osm_id in active_ids
        if osm_id not in bound_ids and osm_id not in derived_by_id
    ]
    # Keep two intact source meshes as focal buildings. The remaining intact
    # footprints stay as map context, which avoids making the entire scene a
    # wall of unrelated generic templates.
    context_only_ids = set(unbound_intact_ids[2:])

    for osm_id in active_ids:
        if osm_id in bound_ids:
            continue
        damage = derived_by_id.get(osm_id, {}).get("damage_state")
        if damage == "major":
            bindings.append({
                "osm_id": osm_id,
                "asset_id": take_asset(CURATED_MAJOR_ASSETS, "major damage"),
            })
        elif damage == "minor":
            asset_id = take_asset(CURATED_MINOR_ASSETS, "minor damage")
            bindings.append({
                "osm_id": osm_id,
                "asset_id": asset_id,
                "damage_state_override": "minor",
            })
        else:
            if osm_id in context_only_ids:
                continue
            bindings.append({
                "osm_id": osm_id,
                "asset_id": take_asset(CURATED_INTACT_ASSETS, "intact buildings"),
            })

    values["scenario_id"] = "laquila_osm_heidata_full_visual_v1"
    values["template_bindings"] = bindings
    values["derived_damage_bindings"] = []
    values["visual_context_only_osm_ids"] = sorted(context_only_ids)
    values["notes"] = (
        "Curated full archive visual benchmark: focal damaged and intact buildings use unique selected "
        "heiDATA assets, while four intact OSM footprints remain map context. Generic assets remain "
        "labelled templates, not surveyed earthquake buildings."
    )
    scenario_path = output_dir / "heidata_full_visual_scenario.v1.json"
    scenario_path.write_text(json.dumps(values, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return scenario_path


def _write_layout(output_dir: Path, manifest_path: Path, scenario_path: Path) -> Path:
    visual_scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
    layout_path = output_dir / "heidata_full_layout.v1.json"
    layout_path.write_text(
        json.dumps(
            {
                "schema_version": "laquila_georeferenced_layout.v1",
                "source_context": str(SOURCE_CONTEXT),
                "source_manifest": str(manifest_path),
                "source_scenario": str(scenario_path),
                "layout_rule": "osm_georeferenced_local_enu.v1",
                "boundary_margin_m": 18.0,
                "maximum_airspace_m": 50.0,
                "active_road_geometry": False,
                "visual_context_only_osm_ids": visual_scenario.get("visual_context_only_osm_ids", []),
                "notes": "Curated L'Aquila environment. Focal heiDATA meshes remain generic damage templates, not measured building damage.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return layout_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=Path.home() / "Datasets" / "heiDATA_D3WZID")
    parser.add_argument("--output-dir", type=Path, default=Path("results/heidata_full_initial"))
    parser.add_argument("--seed", type=int, default=20260927)
    parser.add_argument("--task-count", type=int, default=6)
    parser.add_argument("--uav-count", type=int, default=3)
    parser.add_argument("--planner", choices=("initial_snapshot_greedy_v1", "pgbm_heuristic_v1", "nearest_task_first"), default="pgbm_heuristic_v1")
    args = parser.parse_args()

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = write_full_manifest(args.dataset_root)
    scenario_manifest_path = _write_visual_scenario(output_dir)
    layout_path = _write_layout(output_dir, manifest_path, scenario_manifest_path)
    uavs = UAVConfig(count=args.uav_count)
    scenario = build_scenario(
        SceneConfig(mode="heidata_full", severity="severe", seed=args.seed, uav_count=args.uav_count, template_path=str(layout_path)),
        TaskConfig(task_count=args.task_count, seed=args.seed + 1),
        scenario_id="heidata_full_severe_{}".format(args.seed),
        uav_config=uavs,
        execution_config=ExecutionConfig(start_time=30.0),
    )
    initial_plan = plan_tasks(scenario, uavs, method=args.planner)
    execution = execute_plan(scenario, initial_plan, uavs)
    scenario_path = output_dir / "heidata_full_initial.scenario.json"
    report_path = output_dir / "heidata_full_initial.json"
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
        "environment_provenance": "L'Aquila OSM snapshot plus full heiDATA archive backed damage templates",
    }
    report_path.write_text(json.dumps(report, sort_keys=True, indent=2), encoding="utf-8")

    environment_path = output_dir / "heidata_full_environment.html"
    plot_disaster_scene(scenario.scene, tasks=scenario.tasks, show_context=False).write_html(str(environment_path), include_plotlyjs=True, full_html=True)
    plot_damage_view(scenario.scene).write_html(str(output_dir / "heidata_full_damage_view.html"), include_plotlyjs=True, full_html=True)
    plot_collision_view(scenario.scene).write_html(str(output_dir / "heidata_full_collision_view.html"), include_plotlyjs=True, full_html=True)

    from render_step_by_step import render_step_by_step

    replay_path = output_dir / "heidata_full_initial_step_by_step.html"
    render_step_by_step(report_path, replay_path)
    print("Full manifest: {}".format(manifest_path))
    print("Run report: {}".format(report_path))
    print("Environment view: {}".format(environment_path))
    print("Step by step view: {}".format(replay_path))
    print("Verified selected assets: {}".format(len(scenario.scene.generation_metadata.get("post_assets_used", []))))
    print("Tasks: {} | Served: {} | Missed: {}".format(len(scenario.tasks), len(execution.served_task_ids), len(execution.missed_task_ids)))


if __name__ == "__main__":
    main()
