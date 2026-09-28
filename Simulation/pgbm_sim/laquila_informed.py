"""Load the exact georeferenced L'Aquila source scenario.

The public PGBM mode name remains ``laquila_informed`` for compatibility, but
the scene is no longer arranged into a synthetic grid.  This module reuses the
local heiDATA geospatial benchmark so OSM positions, exclusions, template
bindings, and derived damage states have one source of truth.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from heidata_benchmark.environment import GeospatialScenario, ScenarioError, build_geospatial_scenario
from heidata_benchmark.geospatial import GeoContext, GeoContextError, load_osm_context
from heidata_benchmark.full_dataset import build_full_mesh_library
from heidata_benchmark.library import MeshAsset, MeshLibraryError, build_mesh_library


DEFAULT_LAYOUT_PATH = Path(__file__).parents[1] / "data" / "templates" / "laquila_informed_layout.json"
ACTIVE_LAYOUT_SCHEMAS = {
    "laquila_georeferenced_layout.v1",
    "heidata_neighborhood_layout.v1",
}
SOURCE_SCENARIO_SCHEMA = "scenario.v1"


class LaquilaPrototypeError(ValueError):
    """Raised when the local L'Aquila source cannot be used safely."""


def _read_config(path: str | Path | None) -> tuple[Path, Path, Path, dict[str, Any]]:
    config_path = Path(path) if path else DEFAULT_LAYOUT_PATH
    try:
        values = json.loads(config_path.read_text(encoding="utf-8"))
    except OSError as error:
        raise LaquilaPrototypeError(f"L'Aquila layout configuration is unavailable: {config_path}") from error
    except json.JSONDecodeError as error:
        raise LaquilaPrototypeError(f"L'Aquila layout configuration is invalid: {config_path}") from error
    if values.get("schema_version") not in ACTIVE_LAYOUT_SCHEMAS:
        raise LaquilaPrototypeError(
            "supported geospatial layout schemas are {}".format(
                ", ".join(sorted(ACTIVE_LAYOUT_SCHEMAS))
            )
        )
    required = ("source_context", "source_manifest", "source_scenario")
    if any(not isinstance(values.get(key), str) or not values[key] for key in required):
        raise LaquilaPrototypeError("exact L'Aquila layout needs source_context, source_manifest, and source_scenario")
    margin = float(values.get("boundary_margin_m", 18.0))
    if margin <= 0:
        raise LaquilaPrototypeError("boundary_margin_m must be positive")
    return (
        (config_path.parent / values["source_context"]).resolve(),
        (config_path.parent / values["source_manifest"]).resolve(),
        (config_path.parent / values["source_scenario"]).resolve(),
        values,
    )


def _load_source_scenario(path: str | Path | None) -> tuple[Path, Path, Path, dict[str, Any], GeoContext, GeospatialScenario, tuple[MeshAsset, ...]]:
    source_context_path, source_manifest_path, source_scenario_path, config = _read_config(path)
    try:
        context = load_osm_context(source_context_path)
        manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema_version") == "heidata.full_manifest.v1":
            scenario_values = json.loads(source_scenario_path.read_text(encoding="utf-8"))
            required_assets = {
                str(binding["asset_id"])
                for binding in scenario_values.get("template_bindings", [])
                if binding.get("asset_id")
            }
            library = build_full_mesh_library(source_manifest_path, required_assets)
        else:
            library = build_mesh_library(source_manifest_path)
        scenario = build_geospatial_scenario(source_scenario_path, context, library)
    except (GeoContextError, MeshLibraryError, ScenarioError) as error:
        raise LaquilaPrototypeError(str(error)) from error
    if scenario.version != SOURCE_SCENARIO_SCHEMA:
        raise LaquilaPrototypeError(f"L'Aquila source scenario must use {SOURCE_SCENARIO_SCHEMA}")
    return source_context_path, source_manifest_path, source_scenario_path, config, context, scenario, library.assets


def _source_bounds(scenario: GeospatialScenario, config: dict[str, Any]) -> tuple[float, float, float, float, float, float]:
    selected_ids = {building.osm_id for building in scenario.buildings}
    points = [
        point
        for building in scenario.context.buildings
        if building.osm_id in selected_ids
        for point in building.footprint_local
    ]
    if not points:
        raise LaquilaPrototypeError("the exact L'Aquila scenario has no active building footprint")
    margin = float(config.get("boundary_margin_m", 18.0))
    min_x = min(point[0] for point in points) - margin
    min_y = min(point[1] for point in points) - margin
    max_x = max(point[0] for point in points) + margin
    max_y = max(point[1] for point in points) + margin
    maximum_height = max(float(building.visual_mesh.maximum[2]) for building in scenario.buildings)
    maximum_airspace = max(float(config.get("maximum_airspace_m", 50.0)), maximum_height + margin)
    return min_x, min_y, 0.0, max_x, max_y, maximum_airspace


def _base_position(scenario: GeospatialScenario) -> tuple[float, float, float] | None:
    pads = [
        overlay.geometry_enu_m[0]
        for overlay in scenario.overlays
        if overlay.kind == "launch_landing_pad" and overlay.geometry_enu_m
    ]
    if not pads:
        return None
    point = pads[0]
    return float(point[0]), float(point[1]), 0.0


def _materialize_config(config: dict[str, Any], scenario: GeospatialScenario) -> dict[str, Any]:
    values = dict(config)
    values["bounds"] = list(_source_bounds(scenario, values))
    base = _base_position(scenario)
    if base is not None:
        values["base_position"] = list(base)
    values["building_count"] = len(scenario.buildings)
    values["excluded_osm_buildings"] = [dict(item) for item in scenario.excluded_osm_buildings]
    values["source_origin_wgs84"] = list(scenario.context.origin_wgs84)
    values["source_scenario_id"] = scenario.identifier
    values["source_road_count"] = len(scenario.context.roads)
    return values


def load_laquila_layout(path: str | Path | None = None) -> tuple[Path, dict[str, Any], tuple[dict[str, Any], ...]]:
    """Load a local geospatial layout and its building records."""

    source_context_path, _, _, config, _, scenario, _ = _load_source_scenario(path)
    materialized = _materialize_config(config, scenario)
    buildings = tuple(
        {
            "osm_id": building.osm_id,
            "source_name": str(building.tags.get("name") or f"OSM building {building.osm_id}"),
            "footprint": building.footprint_local,
            "footprint_wgs84": building.footprint_wgs84,
            "tags": dict(building.tags),
        }
        for building in scenario.context.buildings
        if building.osm_id in {item.osm_id for item in scenario.buildings}
    )
    if len(buildings) != int(materialized["building_count"]):
        raise LaquilaPrototypeError("source building count does not match the exact scenario")
    return source_context_path, materialized, buildings


def _state_for_grade(grade: str) -> str:
    if grade in {"no_damage", "osm_footprint_only"}:
        return "intact"
    if grade == "minor":
        return "minor"
    if grade in {"major", "heavy", "extreme"}:
        return "major"
    if grade in {"destruction", "destroyed"}:
        return "destroyed"
    raise LaquilaPrototypeError(f"unsupported source damage grade: {grade}")


def _asset_maps(assets: tuple[MeshAsset, ...]) -> tuple[dict[str, MeshAsset], dict[str, MeshAsset]]:
    by_id = {asset.asset_id: asset for asset in assets}
    pre_by_source = {
        asset.source_id: asset
        for asset in assets
        if asset.event_phase == "pre"
    }
    return by_id, pre_by_source


def _source_ref(
    context: GeoContext,
    scenario: GeospatialScenario,
    building_id: str,
    footprint_wgs84: tuple[tuple[float, float], ...],
    layout_schema: str,
) -> str:
    lon = sum(point[0] for point in footprint_wgs84) / len(footprint_wgs84)
    lat = sum(point[1] for point in footprint_wgs84) / len(footprint_wgs84)
    if layout_schema == "heidata_neighborhood_layout.v1":
        return (
            f"Controlled neighbourhood slot {building_id} | derived local layout position | "
            f"synthetic WGS84 anchor {lon:.7f}, {lat:.7f} | source scenario {scenario.identifier}"
        )
    return (
        f"OSM {building_id} | WGS84 centroid {lon:.7f}, {lat:.7f} | "
        f"source scenario {scenario.identifier} | local origin {context.origin_wgs84[0]:.7f}, {context.origin_wgs84[1]:.7f}"
    )


def build_laquila_structure_specs(
    path: str | Path | None,
    bounds: tuple[float, float, float, float, float, float] | None = None,
    damage_states: tuple[str, ...] = (),
    seed: int = 0,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, str], ...], dict[str, Any]]:
    """Convert a local geospatial source scenario into PGBM structures."""

    source_context_path, source_manifest_path, source_scenario_path, config, context, scenario, assets = _load_source_scenario(path)
    asset_by_id, pre_by_source = _asset_maps(assets)
    map_buildings = {building.osm_id: building for building in context.buildings}
    visual_usage = {
        "source_pre_mesh": 0,
        "source_post_mesh": 0,
        "derived_partial_mesh": 0,
        "footprint_extrusion": 0,
        "rubble_only": 0,
    }
    post_assets_used: list[str] = []
    derived_bindings: list[dict[str, str]] = []
    template_bindings: list[dict[str, str]] = []
    specs: list[dict[str, Any]] = []
    context_only_ids = {str(value) for value in config.get("visual_context_only_osm_ids", [])}
    controlled_layout = config.get("schema_version") == "heidata_neighborhood_layout.v1"
    known_osm_ids = {building.osm_id for building in context.buildings}
    unknown_context_ids = context_only_ids.difference(known_osm_ids)
    if unknown_context_ids:
        raise LaquilaPrototypeError(
            "visual context building is unknown: {}".format(sorted(unknown_context_ids)[0])
        )

    for index, source_building in enumerate(scenario.buildings, start=1):
        map_building = map_buildings[source_building.osm_id]
        polygon = tuple(tuple(float(value) for value in point) for point in map_building.footprint_local)
        minimum_x = min(point[0] for point in polygon)
        minimum_y = min(point[1] for point in polygon)
        maximum_x = max(point[0] for point in polygon)
        maximum_y = max(point[1] for point in polygon)
        is_context_only = source_building.osm_id in context_only_ids
        state = "intact" if is_context_only else _state_for_grade(source_building.damage_grade)
        source_visual_mesh = source_building.visual_mesh
        visual_mesh = None if is_context_only else source_visual_mesh
        asset = asset_by_id.get(source_building.asset_id) if source_building.asset_id else None
        pre_asset = pre_by_source.get(asset.source_id) if asset else None
        if source_building.asset_id and asset is None:
            raise LaquilaPrototypeError(f"source scenario references missing mesh asset: {source_building.asset_id}")
        if asset and asset.event_phase == "post" and asset.review.status != "accepted":
            raise LaquilaPrototypeError(f"inspection only mesh entered exact scenario: {asset.asset_id}")

        if is_context_only:
            if asset is not None or source_building.damage_geometry is not None:
                raise LaquilaPrototypeError(
                    "visual context building cannot also have a selected damage asset: {}".format(
                        source_building.osm_id
                    )
                )
            visual_phase = "context_footprint"
            visual_provenance = (
                "exact OSM footprint retained as visual context; no generic mesh attached"
                if not controlled_layout
                else "derived neighbourhood footprint retained as context; no generic mesh attached"
            )
            visual_usage["footprint_extrusion"] += 1
        elif asset and asset.event_phase == "post":
            visual_phase = "source_post"
            visual_provenance = (
                "derived controlled neighbourhood slot with accepted heiDATA post damage template; "
                "not a measured building specific reconstruction"
                if controlled_layout
                else "exact source position with accepted heiDATA post template bound by scenario.v1"
            )
            visual_usage["source_post_mesh"] += 1
            post_assets_used.append(asset.asset_id)
            template_bindings.append({"osm_id": source_building.osm_id, "asset_id": asset.asset_id})
        elif asset and asset.event_phase == "pre":
            visual_phase = "source_pre"
            if source_building.damage_grade == "minor":
                visual_provenance = (
                    (
                        "derived controlled neighbourhood slot with accepted heiDATA pre template and "
                        "explicit minor-state visualization; minor damage is not observed in the pre mesh"
                    )
                    if controlled_layout
                    else (
                        "exact source position with accepted heiDATA pre template and explicit "
                        "scenario minor-state override; minor damage is not observed in the pre mesh"
                    )
                )
            else:
                visual_provenance = (
                    "derived controlled neighbourhood slot with accepted heiDATA pre template; "
                    "not a measured building specific reconstruction"
                    if controlled_layout
                    else "exact source position with accepted heiDATA pre template bound by scenario.v1"
                )
            visual_usage["source_pre_mesh"] += 1
            binding_record = {"osm_id": source_building.osm_id, "asset_id": asset.asset_id}
            if source_building.damage_grade == "minor":
                binding_record["damage_state_override"] = "minor"
            template_bindings.append(binding_record)
        elif source_building.damage_geometry is not None:
            visual_phase = "derived_damage"
            visual_provenance = (
                "derived controlled neighbourhood footprint with scenario.v1 derived damage profile"
                if controlled_layout
                else "exact OSM footprint with scenario.v1 derived damage profile"
            )
            visual_usage["derived_partial_mesh"] += 1
            derived_bindings.append({"osm_id": source_building.osm_id, "damage_state": state})
        else:
            visual_phase = "footprint_extrusion"
            visual_provenance = (
                "derived controlled neighbourhood footprint extrusion; source height and mesh unavailable"
                if controlled_layout
                else "exact OSM footprint extrusion; source height and mesh unavailable"
            )
            visual_usage["footprint_extrusion"] += 1

        if source_building.damage_grade == "destruction" and asset is None:
            visual_usage["rubble_only"] += 1

        height_source = "derived neighbourhood height unavailable" if controlled_layout else "osm height unavailable"
        if source_building.placement is not None:
            height_source = source_building.placement.target_height_source
        elif source_building.damage_geometry is not None:
            height_source = source_building.damage_geometry.target_height_source
        height = max(float(source_visual_mesh.extent[2]), 0.1)
        source_name = (
            str(map_building.tags.get("name") or f"Controlled neighbourhood building {index:02d}")
            if controlled_layout
            else str(map_building.tags.get("name") or f"OSM building {source_building.osm_id}")
        )
        specs.append({
            "identifier": f"heidata_neighborhood_{index:02d}" if controlled_layout else f"laquila_source_{index:02d}",
            "minimum": (minimum_x, minimum_y, 0.0),
            "width": max(maximum_x - minimum_x, 0.1),
            "depth": max(maximum_y - minimum_y, 0.1),
            "height": height,
            "damage_state": state,
            "height_source": height_source,
            "source_ref": _source_ref(
                context,
                scenario,
                source_building.osm_id,
                map_building.footprint_wgs84,
                str(config["schema_version"]),
            ),
            "footprint": polygon,
            "scene_role": "context" if is_context_only else "target",
            "source_name": source_name,
            "source_id": asset.source_id if asset else None,
            "pre_asset_id": pre_asset.asset_id if pre_asset else None,
            "post_asset_id": asset.asset_id if asset and asset.event_phase == "post" else None,
            "visual_mesh_asset": asset.asset_id if asset else None,
            "visual_mesh_phase": visual_phase,
            "visual_provenance": visual_provenance,
            "visual_mesh": visual_mesh,
            "visual_face_materials": tuple(visual_mesh.face_materials) if visual_mesh is not None else (),
        })

    metadata = _materialize_config(config, scenario)
    metadata.update({
        "layout_version": str(config["schema_version"]),
        "layout_rule": str(config.get("layout_rule", "osm_georeferenced_local_enu.v1")),
        "source_context_path": str(source_context_path),
        "source_manifest_path": str(source_manifest_path),
        "source_scenario_path": str(source_scenario_path),
        "source_scenario_schema": SOURCE_SCENARIO_SCHEMA,
        "source_origin_wgs84": list(context.origin_wgs84),
        "source_building_count": len(context.buildings),
        "active_building_count": len(specs),
        "active_osm_ids": [item.osm_id for item in scenario.buildings],
        "visual_context_only_osm_ids": sorted(context_only_ids),
        "excluded_osm_buildings": [dict(item) for item in scenario.excluded_osm_buildings],
        "source_damage_grade_counts": {
            grade: sum(item.damage_grade == grade for item in scenario.buildings)
            for grade in sorted({item.damage_grade for item in scenario.buildings})
        },
        "template_bindings": template_bindings,
        "derived_damage_bindings": derived_bindings,
        "accepted_post_assets": [asset.asset_id for asset in assets if asset.event_phase == "post" and asset.review.status == "accepted"],
        "inspection_only_post_assets": [asset.asset_id for asset in assets if asset.event_phase == "post" and asset.review.status != "accepted"],
        "post_assets_used": sorted(set(post_assets_used)),
        "visual_mesh_usage": visual_usage,
        "placement_provenance": (
            "derived ordered controlled neighbourhood positions from a deterministic grid layout; "
            "each slot and mesh binding is recorded, and no claim of measured L'Aquila position is made"
            if controlled_layout
            else "original OSM source positions in deterministic local ENU coordinates; no synthetic translation, rotation, grid, or lot scaling"
        ),
        "damage_provenance": (
            "fixed controlled scenario.v1 damage allocation using accepted heiDATA pre and post templates; "
            "damage labels are simulation assignments, not measured building damage"
            if controlled_layout
            else "fixed scenario.v1 state, accepted explicit template bindings, and named OSM derived damage bindings"
        ),
        "exactness_policy": (
            "building count, ordered slots, and mesh identities are reproducible derived simulation inputs; "
            "the additional neighbourhood is not an OSM measured reconstruction"
            if controlled_layout
            else "source footprint and relative position are exact for the stored snapshot; missing height or building specific mesh is explicitly derived"
        ),
        "source_road_count": len(context.roads),
        "active_road_count": 0,
        "seed_effect": "source buildings and damage states are seed independent; seed affects only simulator candidate sites and generated tasks",
        "scenario_seed": scenario.seed,
    })
    if controlled_layout:
        provenance = (
            {
                "identifier": "heidata_controlled_neighborhood_layout",
                "title": "Derived controlled neighbourhood layout",
                "url_or_doi": str(source_context_path),
                "licence": "project source artifact",
                "role": "ordered building slots, local footprints, and derived street context",
                "preprocessing_version": "heidata_neighborhood_layout.v1",
            },
            {
                "identifier": "heidata_controlled_neighborhood_scenario",
                "title": "Controlled neighbourhood scenario manifest",
                "url_or_doi": str(source_scenario_path),
                "licence": "project source artifact",
                "role": "explicit damage allocation and one to one mesh bindings",
                "preprocessing_version": SOURCE_SCENARIO_SCHEMA,
            },
            {
                "identifier": "heidata_source_mesh_library",
                "title": "heiDATA accepted local source meshes",
                "url_or_doi": "doi:10.11588/DATA/D3WZID",
                "licence": "CC BY 4.0",
                "role": "unique source mesh templates placed into controlled building slots",
                "preprocessing_version": "mesh_review.v1",
            },
        )
    else:
        provenance = (
            {
                "identifier": "laquila_osm_source_context",
                "title": "Frozen L'Aquila OpenStreetMap source context",
                "url_or_doi": "https://www.openstreetmap.org/copyright",
                "licence": "ODbL 1.0",
                "role": "exact source building identity, WGS 84 footprint, and relative position",
                "preprocessing_version": "osm_context.v1",
            },
            {
                "identifier": "laquila_source_scenario",
                "title": "L'Aquila source scenario manifest",
                "url_or_doi": str(source_scenario_path),
                "licence": "project source artifact",
                "role": "explicit exclusion, damage states, and template bindings",
                "preprocessing_version": SOURCE_SCENARIO_SCHEMA,
            },
            {
                "identifier": "heidata_source_mesh_library",
                "title": "heiDATA accepted local source meshes",
                "url_or_doi": "doi:10.11588/DATA/D3WZID",
                "licence": "CC BY 4.0",
                "role": "building specific source mesh templates where explicitly bound",
                "preprocessing_version": "mesh_review.v1",
            },
        )
    return tuple(specs), provenance, metadata
