"""Static, geospatial heiDATA benchmark composition.

This module combines a frozen OSM map context with reviewed heiDATA meshes.
OSM supplies real world position and footprint evidence.  heiDATA meshes are
labelled damage templates and are never represented as surveyed OSM buildings.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from .geospatial import GeoContext, GeoContextError, MapBuilding, MapRoad, Point2, bounds_2d, footprints_overlap
from .library import MeshAsset, MeshLibrary, MeshLibraryError
from .mesh import Mesh, box_mesh


class ScenarioError(ValueError):
    """Raised when a controlled geospatial scenario is not valid."""


def _mesh_to_enu(mesh: Mesh) -> Mesh:
    """Convert source X,Y,Z to local East,North,Up as X,Z,Y."""

    return Mesh(mesh.vertices[:, (0, 2, 1)], mesh.faces.copy(), mesh.face_materials)


def _extrude_footprint_with_profile(
    points: tuple[Point2, ...], height_profile_m: tuple[float, ...],
) -> Mesh:
    """Extrude an exact OSM footprint with a possibly damaged top profile."""

    if len(points) < 3 or len(points) != len(height_profile_m) or min(height_profile_m) <= 0:
        raise ScenarioError("OSM footprint extrusion needs a positive height profile and polygon")
    bottom = np.asarray([(x, y, 0.0) for x, y in points], dtype=float)
    top = np.asarray([(x, y, height) for (x, y), height in zip(points, height_profile_m)], dtype=float)
    vertices = np.concatenate((bottom, top))
    count = len(points)
    faces: list[tuple[int, int, int]] = []
    for index in range(1, count - 1):
        faces.append((0, index + 1, index))
        faces.append((count, count + index, count + index + 1))
    for index in range(count):
        next_index = (index + 1) % count
        faces.extend(((index, next_index, count + next_index), (index, count + next_index, count + index)))
    return Mesh(vertices, np.asarray(faces, dtype=int))


def _extrude_footprint(points: tuple[Point2, ...], height_m: float) -> Mesh:
    if len(points) < 3 or height_m <= 0:
        raise ScenarioError("OSM footprint extrusion needs a positive height and polygon")
    return _extrude_footprint_with_profile(points, tuple(height_m for _ in points))


@dataclass(frozen=True)
class PlacementTransform:
    osm_id: str
    asset_id: str
    translation_enu_m: tuple[float, float, float]
    horizontal_scale: float
    vertical_scale: float
    target_height_m: float
    target_height_source: str

    def as_dict(self) -> dict:
        return {
            "osm_id": self.osm_id,
            "asset_id": self.asset_id,
            "translation_enu_m": list(self.translation_enu_m),
            "horizontal_scale": self.horizontal_scale,
            "vertical_scale": self.vertical_scale,
            "target_height_m": self.target_height_m,
            "target_height_source": self.target_height_source,
        }


@dataclass(frozen=True)
class DerivedDamageGeometry:
    """Declared controlled damage, generated from an exact OSM footprint."""

    osm_id: str
    damage_state: str
    height_profile_m: tuple[float, ...]
    target_height_m: float
    target_height_source: str
    seed: int
    rule_version: str = "derived_osm_damage_geometry.v1"

    def as_dict(self) -> dict:
        return {
            "osm_id": self.osm_id,
            "damage_state": self.damage_state,
            "height_profile_m": list(self.height_profile_m),
            "target_height_m": self.target_height_m,
            "target_height_source": self.target_height_source,
            "seed": self.seed,
            "rule_version": self.rule_version,
            "provenance": "scenario_derived_not_observed",
        }


def _derived_damage_mesh(
    building: MapBuilding, default_height_m: float, damage_state: str, seed: int,
) -> tuple[Mesh, DerivedDamageGeometry]:
    """Create a deterministic non cuboid damage mesh while retaining the OSM footprint."""

    if damage_state not in {"minor", "major"}:
        raise ScenarioError(f"unknown derived damage state: {damage_state}")
    target_height = building.height_m if building.height_m is not None else default_height_m
    height_source = building.height_source if building.height_m is not None else "scenario:default_building_height_m"
    rng = random.Random(f"derived_osm_damage_geometry.v1:{seed}:{building.osm_id}:{damage_state}")
    lower, upper = (0.72, 0.94) if damage_state == "minor" else (0.18, 0.66)
    profile = tuple(round(target_height * rng.uniform(lower, upper), 6) for _ in building.footprint_local)
    mesh = _extrude_footprint_with_profile(building.footprint_local, profile)
    return mesh, DerivedDamageGeometry(
        building.osm_id, damage_state, profile, target_height, height_source, seed,
    )


def _place_template(asset: MeshAsset, building: MapBuilding, default_height_m: float) -> tuple[Mesh, PlacementTransform]:
    source = _mesh_to_enu(asset.mesh)
    source_min = source.minimum
    source_extent = source.extent
    target_min_x, target_min_y, target_max_x, target_max_y = building.bounds_local
    target_width = target_max_x - target_min_x
    target_depth = target_max_y - target_min_y
    if target_width <= 0.1 or target_depth <= 0.1 or source_extent[0] <= 0 or source_extent[1] <= 0 or source_extent[2] <= 0:
        raise ScenarioError(f"cannot place {asset.asset_id} on OSM building {building.osm_id}")
    horizontal_scale = min(target_width / source_extent[0], target_depth / source_extent[1]) * 0.88
    if horizontal_scale <= 0:
        raise ScenarioError(f"placement scale is invalid for {building.osm_id}")
    natural_height = source_extent[2] * horizontal_scale
    target_height = building.height_m if building.height_m is not None else max(default_height_m, natural_height)
    height_source = building.height_source if building.height_m is not None else "scenario:default_or_template_height"
    vertical_scale = target_height / source_extent[2]
    scaled = source.vertices.copy()
    scaled[:, 0] *= horizontal_scale
    scaled[:, 1] *= horizontal_scale
    scaled[:, 2] *= vertical_scale
    source_center = np.asarray(((source.minimum[0] + source.maximum[0]) / 2.0, (source.minimum[1] + source.maximum[1]) / 2.0))
    target_center = np.asarray(building.centroid_local)
    translation_xy = target_center - source_center * horizontal_scale
    translation_z = -source.minimum[2] * vertical_scale
    transform = PlacementTransform(
        building.osm_id, asset.asset_id, (float(translation_xy[0]), float(translation_xy[1]), float(translation_z)),
        float(horizontal_scale), float(vertical_scale), float(target_height), height_source,
    )
    return Mesh(scaled + np.asarray(transform.translation_enu_m), source.faces.copy(), source.face_materials), transform


@dataclass(frozen=True)
class CollisionVolume:
    identifier: str
    owner_id: str
    kind: str
    minimum_enu_m: tuple[float, float, float]
    maximum_enu_m: tuple[float, float, float]
    clearance_margin_m: float
    derivation_version: str = "collision_volume.v1"

    def contains(self, point: tuple[float, float, float]) -> bool:
        return all(low <= value <= high for value, low, high in zip(point, self.minimum_enu_m, self.maximum_enu_m))

    def as_dict(self) -> dict:
        return {
            "id": self.identifier,
            "owner_id": self.owner_id,
            "kind": self.kind,
            "minimum_enu_m": list(self.minimum_enu_m),
            "maximum_enu_m": list(self.maximum_enu_m),
            "clearance_margin_m": self.clearance_margin_m,
            "derivation_version": self.derivation_version,
        }


def _collision_for_mesh(identifier: str, owner_id: str, kind: str, mesh: Mesh, margin_m: float) -> CollisionVolume:
    if margin_m < 0:
        raise ScenarioError("collision margin must not be negative")
    margin = np.asarray((margin_m, margin_m, margin_m), dtype=float)
    return CollisionVolume(
        identifier, owner_id, kind, tuple((mesh.minimum - margin).tolist()), tuple((mesh.maximum + margin).tolist()), margin_m,
    )


@dataclass(frozen=True)
class ScenarioBuilding:
    osm_id: str
    source_id: str | None
    asset_id: str | None
    damage_grade: str
    visual_kind: str
    visual_mesh: Mesh
    placement: PlacementTransform | None
    damage_geometry: DerivedDamageGeometry | None
    provenance: str

    def as_dict(self) -> dict:
        return {
            "osm_id": self.osm_id,
            "source_id": self.source_id,
            "asset_id": self.asset_id,
            "damage_grade": self.damage_grade,
            "visual_kind": self.visual_kind,
            "visual_mesh_summary": self.visual_mesh.summary(),
            "placement": self.placement.as_dict() if self.placement else None,
            "damage_geometry": self.damage_geometry.as_dict() if self.damage_geometry else None,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class OperationalOverlay:
    identifier: str
    kind: str
    status: str
    provenance: str
    geometry_enu_m: tuple[tuple[float, float, float], ...]
    source_ids: tuple[str, ...]
    rule_version: str
    notes: str

    def as_dict(self) -> dict:
        return {
            "id": self.identifier,
            "kind": self.kind,
            "status": self.status,
            "provenance": self.provenance,
            "geometry_enu_m": [list(point) for point in self.geometry_enu_m],
            "source_ids": list(self.source_ids),
            "rule_version": self.rule_version,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class NavigationVolume:
    world_minimum_enu_m: tuple[float, float, float]
    world_maximum_enu_m: tuple[float, float, float]
    cell_size_m: float
    altitude_levels_m: tuple[float, ...]
    occupied_cells: tuple[tuple[int, int, int], ...]
    free_cell_count: int
    collision_ids: tuple[str, ...]

    def contains(self, point: tuple[float, float, float]) -> bool:
        return all(low <= value <= high for value, low, high in zip(point, self.world_minimum_enu_m, self.world_maximum_enu_m))

    def cell_center(self, cell: tuple[int, int, int]) -> tuple[float, float, float]:
        return (
            self.world_minimum_enu_m[0] + (cell[0] + 0.5) * self.cell_size_m,
            self.world_minimum_enu_m[1] + (cell[1] + 0.5) * self.cell_size_m,
            self.altitude_levels_m[cell[2]],
        )

    def as_dict(self) -> dict:
        return {
            "world_minimum_enu_m": list(self.world_minimum_enu_m),
            "world_maximum_enu_m": list(self.world_maximum_enu_m),
            "cell_size_m": self.cell_size_m,
            "altitude_levels_m": list(self.altitude_levels_m),
            "occupied_cells": [list(cell) for cell in self.occupied_cells],
            "free_cell_count": self.free_cell_count,
            "collision_ids": list(self.collision_ids),
        }


def _in_collision(point: tuple[float, float, float], volumes: Iterable[CollisionVolume]) -> bool:
    return any(volume.contains(point) for volume in volumes)


def _altitude_levels(minimum_m: float, maximum_m: float, step_m: float) -> tuple[float, ...]:
    if minimum_m <= 0 or maximum_m <= minimum_m or step_m <= 0:
        raise ScenarioError("navigation altitude configuration is invalid")
    values: list[float] = []
    current = minimum_m
    while current <= maximum_m + 1e-9:
        values.append(round(current, 6))
        current += step_m
    return tuple(values)


def build_navigation_volume(
    world_minimum: tuple[float, float, float],
    world_maximum: tuple[float, float, float],
    collision_volumes: tuple[CollisionVolume, ...],
    cell_size_m: float,
    minimum_flight_altitude_m: float,
    maximum_flight_altitude_m: float,
    altitude_step_m: float,
) -> NavigationVolume:
    """Rasterise a static conservative airspace volume deterministically."""

    if cell_size_m <= 0:
        raise ScenarioError("navigation cell size must be positive")
    if any(low >= high for low, high in zip(world_minimum, world_maximum)):
        raise ScenarioError("navigation world bounds are invalid")
    levels = _altitude_levels(minimum_flight_altitude_m, maximum_flight_altitude_m, altitude_step_m)
    count_x = math.ceil((world_maximum[0] - world_minimum[0]) / cell_size_m)
    count_y = math.ceil((world_maximum[1] - world_minimum[1]) / cell_size_m)
    occupied: list[tuple[int, int, int]] = []
    free_count = 0
    for x_index in range(count_x):
        for y_index in range(count_y):
            for z_index, altitude in enumerate(levels):
                point = (
                    world_minimum[0] + (x_index + 0.5) * cell_size_m,
                    world_minimum[1] + (y_index + 0.5) * cell_size_m,
                    altitude,
                )
                if _in_collision(point, collision_volumes):
                    occupied.append((x_index, y_index, z_index))
                else:
                    free_count += 1
    if free_count == 0:
        raise ScenarioError("navigation volume has no free cells")
    return NavigationVolume(world_minimum, world_maximum, cell_size_m, levels, tuple(occupied), free_count, tuple(item.identifier for item in collision_volumes))


def path_is_free(
    navigation: NavigationVolume,
    collision_volumes: tuple[CollisionVolume, ...],
    waypoints: tuple[tuple[float, float, float], ...],
) -> bool:
    """Check a polyline against the static boundary and collision volumes."""

    if len(waypoints) < 2:
        raise ScenarioError("a path needs at least two waypoints")
    for start, end in zip(waypoints, waypoints[1:]):
        distance = math.dist(start, end)
        steps = max(1, math.ceil(distance / max(navigation.cell_size_m / 2.0, 0.1)))
        for index in range(steps + 1):
            ratio = index / steps
            point = tuple(first + (second - first) * ratio for first, second in zip(start, end))
            if not navigation.contains(point) or _in_collision(point, collision_volumes):
                return False
    return True


@dataclass(frozen=True)
class GeospatialScenario:
    identifier: str
    version: str
    seed: int
    dataset_identifier: str
    context: GeoContext
    buildings: tuple[ScenarioBuilding, ...]
    collision_volumes: tuple[CollisionVolume, ...]
    navigation: NavigationVolume
    overlays: tuple[OperationalOverlay, ...]
    excluded_osm_buildings: tuple[dict[str, str], ...]
    validation: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "scenario_id": self.identifier,
            "scenario_version": self.version,
            "kind": "controlled_geospatial_benchmark_composite",
            "dataset_identifier": self.dataset_identifier,
            "seed": self.seed,
            "coordinate_convention": {
                "source_mesh": "source X,Y,Z, with source Y vertical",
                "simulation": "local ENU X,Y,Z, with Z vertical",
                "display": "Plotly local ENU X,Y,Z",
            },
            "exactness_policy": "OSM geometry is tied to the stored snapshot. heiDATA assets are labelled damage templates, and scenario derived damage geometry is a controlled annotation. Neither is measured OSM building damage.",
            "geo_context": self.context.as_dict(),
            "buildings": [building.as_dict() for building in self.buildings],
            "collision_volumes": [volume.as_dict() for volume in self.collision_volumes],
            "navigation": self.navigation.as_dict(),
            "overlays": [overlay.as_dict() for overlay in self.overlays],
            "excluded_osm_buildings": [dict(item) for item in self.excluded_osm_buildings],
            "validation": list(self.validation),
        }


def _load_config(config: str | Path | dict) -> dict:
    if isinstance(config, dict):
        return config
    path = Path(config)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ScenarioError(f"scenario manifest is unavailable: {path}") from error
    except json.JSONDecodeError as error:
        raise ScenarioError(f"scenario manifest is not valid JSON: {path}") from error


def _irregular_rubble_mesh(width: float, depth: float, height: float, rng: random.Random) -> Mesh:
    """Create one low poly rubble piece with an uneven three dimensional top."""

    top = [
        (width * rng.uniform(0.05, 0.22), depth * rng.uniform(0.05, 0.22), height * rng.uniform(0.55, 1.0)),
        (width * rng.uniform(0.78, 1.0), depth * rng.uniform(0.05, 0.22), height * rng.uniform(0.55, 1.0)),
        (width * rng.uniform(0.78, 1.0), depth * rng.uniform(0.78, 1.0), height * rng.uniform(0.55, 1.0)),
        (width * rng.uniform(0.05, 0.22), depth * rng.uniform(0.78, 1.0), height * rng.uniform(0.55, 1.0)),
    ]
    vertices = np.asarray(
        [
            (0.0, 0.0, 0.0), (width, 0.0, 0.0), (width, depth, 0.0), (0.0, depth, 0.0),
            *top,
        ],
        dtype=float,
    )
    faces = np.asarray(
        [
            (0, 2, 1), (0, 3, 2),
            (4, 5, 6), (4, 6, 7),
            (0, 1, 5), (0, 5, 4),
            (1, 2, 6), (1, 6, 5),
            (2, 3, 7), (2, 7, 6),
            (3, 0, 4), (3, 4, 7),
        ],
        dtype=int,
    )
    return Mesh(vertices, faces)


def _rubble_meshes(building: ScenarioBuilding, seed: int) -> tuple[Mesh, ...]:
    """Generate deterministic, visible three dimensional rubble pieces."""

    rng = random.Random(f"{seed}:{building.osm_id}:rubble.v2")
    minimum = building.visual_mesh.minimum
    extent = building.visual_mesh.extent
    destruction = building.damage_grade == "destruction"
    piece_count = 6 if destruction else 4
    width_range = (0.12, 0.24) if destruction else (0.10, 0.20)
    depth_range = (0.12, 0.24) if destruction else (0.10, 0.20)
    height_range = (0.06, 0.18) if destruction else (0.05, 0.14)
    pieces: list[Mesh] = []
    for _ in range(piece_count):
        width = max(0.8, extent[0] * rng.uniform(*width_range))
        depth = max(0.8, extent[1] * rng.uniform(*depth_range))
        height = max(0.35, min(3.0, extent[2] * rng.uniform(*height_range)))
        available_x = max(0.0, extent[0] - width)
        available_y = max(0.0, extent[1] - depth)
        x = minimum[0] + available_x * rng.uniform(0.08, 0.92)
        y = minimum[1] + available_y * rng.uniform(0.08, 0.92)
        pieces.append(_irregular_rubble_mesh(width, depth, height, rng).translated((x, y, 0.0)))
    return tuple(pieces)


def _road_overlay(road: MapRoad, blocked: bool) -> OperationalOverlay:
    status = "blocked" if blocked else "clear"
    return OperationalOverlay(
        f"road:{road.osm_id}", "road", status, "source",
        tuple((x, y, 0.0) for x, y in road.centerline_local), (road.osm_id,), "osm_context.v1",
        "OpenStreetMap highway geometry from frozen context",
    )


def _blocked_zone(road: MapRoad) -> OperationalOverlay:
    midpoint_index = len(road.centerline_local) // 2
    x, y = road.centerline_local[midpoint_index]
    half_size = 2.0
    geometry = ((x - half_size, y - half_size, 0.0), (x + half_size, y - half_size, 0.0), (x + half_size, y + half_size, 0.0), (x - half_size, y + half_size, 0.0))
    return OperationalOverlay(
        f"blocked_zone:{road.osm_id}", "blocked_zone", "blocked", "derived", geometry, (road.osm_id,), "road_blockage.v1",
        "Deterministic obstruction marker attached to a blocked OSM road",
    )


def _safe_pads(
    navigation: NavigationVolume,
    collision_volumes: tuple[CollisionVolume, ...],
    count: int,
    anchor_xy: tuple[float, float],
) -> tuple[OperationalOverlay, ...]:
    """Find deterministic UAV pads near the mapped building cluster."""

    if count < 0:
        raise ScenarioError("safe pad count must not be negative")
    if count == 0:
        return ()
    pads: list[OperationalOverlay] = []
    step = max(navigation.cell_size_m * 2.0, 4.0)
    candidates: list[tuple[float, float, float]] = []
    x = navigation.world_minimum_enu_m[0] + step
    while x < navigation.world_maximum_enu_m[0] - step:
        y = navigation.world_minimum_enu_m[1] + step
        while y < navigation.world_maximum_enu_m[1] - step:
            candidates.append((x, y, 0.0))
            y += step
        x += step
    candidates.sort(key=lambda point: ((point[0] - anchor_xy[0]) ** 2 + (point[1] - anchor_xy[1]) ** 2, point[0], point[1]))
    minimum_separation = max(step * 0.9, 8.0)
    for point in candidates:
        clearance_point = (point[0], point[1], navigation.altitude_levels_m[0])
        if _in_collision(point, collision_volumes) or _in_collision(clearance_point, collision_volumes):
            continue
        if any(math.dist(point[:2], pad.geometry_enu_m[0][:2]) < minimum_separation for pad in pads):
            continue
        pads.append(
            OperationalOverlay(
                f"safe_pad:{len(pads) + 1}", "launch_landing_pad", "available", "derived", (point,), (), "safe_pad.v2",
                "Open ground cell near the mapped building cluster, selected with configured collision clearance",
            )
        )
        if len(pads) == count:
            break
    if len(pads) < count:
        raise ScenarioError("cannot find the configured number of safe pads")
    return tuple(pads)


def _validate_overlays(
    context: GeoContext,
    overlays: tuple[OperationalOverlay, ...],
    navigation: NavigationVolume,
    collision_volumes: tuple[CollisionVolume, ...],
) -> tuple[str, ...]:
    known_roads = {road.osm_id for road in context.roads}
    known_buildings = {building.osm_id for building in context.buildings}
    messages: list[str] = []
    for overlay in overlays:
        if overlay.provenance not in {"source", "annotated", "derived"}:
            raise ScenarioError(f"overlay {overlay.identifier} has invalid provenance")
        if overlay.kind == "road":
            if len(overlay.source_ids) != 1 or overlay.source_ids[0] not in known_roads:
                raise ScenarioError(f"road overlay {overlay.identifier} lacks an OSM road source")
        elif overlay.kind == "rubble":
            if len(overlay.source_ids) != 1 or overlay.source_ids[0] not in known_buildings:
                raise ScenarioError(f"rubble overlay {overlay.identifier} lacks a building source")
            if len(overlay.geometry_enu_m) != 8 or any(point[2] <= 0.0 for point in overlay.geometry_enu_m[4:]):
                raise ScenarioError(f"rubble overlay {overlay.identifier} must contain a positive height 3D mesh")
        elif overlay.kind == "blocked_zone":
            if len(overlay.source_ids) != 1 or overlay.source_ids[0] not in known_roads or overlay.status != "blocked":
                raise ScenarioError(f"blocked zone {overlay.identifier} is invalid")
        elif overlay.kind == "launch_landing_pad":
            if len(overlay.geometry_enu_m) != 1 or overlay.status != "available":
                raise ScenarioError(f"safe pad {overlay.identifier} is invalid")
            point = overlay.geometry_enu_m[0]
            if not navigation.contains(point) or _in_collision(point, collision_volumes):
                raise ScenarioError(f"safe pad {overlay.identifier} is not free")
        else:
            raise ScenarioError(f"unknown overlay kind: {overlay.kind}")
        messages.append(f"validated {overlay.identifier}")
    return tuple(messages)


def build_geospatial_scenario(
    config: str | Path | dict,
    context: GeoContext,
    library: MeshLibrary,
) -> GeospatialScenario:
    """Create one nonredundant controlled scenario from local research files."""

    data = _load_config(config)
    if data.get("schema_version") != "scenario.v1":
        raise ScenarioError("scenario schema_version must be scenario.v1")
    identifier = data.get("scenario_id")
    if not isinstance(identifier, str) or not identifier:
        raise ScenarioError("scenario_id is required")
    seed = int(data.get("seed", 0))
    default_height = float(data.get("default_building_height_m", 9.0))
    margin = float(data.get("collision_margin_m", 1.0))
    bindings = data.get("template_bindings", [])
    if not isinstance(bindings, list):
        raise ScenarioError("template_bindings must be a list")
    derived_bindings = data.get("derived_damage_bindings", [])
    if not isinstance(derived_bindings, list):
        raise ScenarioError("derived_damage_bindings must be a list")
    all_map_buildings = {building.osm_id: building for building in context.buildings}
    exclusions_raw = data.get("excluded_osm_buildings", [])
    if not isinstance(exclusions_raw, list):
        raise ScenarioError("excluded_osm_buildings must be a list")
    exclusions: list[dict[str, str]] = []
    excluded_ids: set[str] = set()
    for exclusion in exclusions_raw:
        if not isinstance(exclusion, dict) or not isinstance(exclusion.get("osm_id"), str) or not isinstance(exclusion.get("reason"), str):
            raise ScenarioError("each excluded OSM building needs osm_id and reason")
        osm_id = exclusion["osm_id"]
        if osm_id not in all_map_buildings:
            raise ScenarioError(f"excluded OSM building is unknown: {osm_id}")
        if osm_id in excluded_ids:
            raise ScenarioError(f"duplicate excluded OSM building: {osm_id}")
        excluded_ids.add(osm_id)
        exclusions.append({"osm_id": osm_id, "reason": exclusion["reason"]})
    map_buildings = {osm_id: building for osm_id, building in all_map_buildings.items() if osm_id not in excluded_ids}
    bound_osm_ids: set[str] = set()
    bound_source_ids: set[str] = set()
    binding_by_osm: dict[str, MeshAsset] = {}
    damage_override_by_osm: dict[str, str] = {}
    for binding in bindings:
        if not isinstance(binding, dict):
            raise ScenarioError("template binding must be an object")
        osm_id = binding.get("osm_id")
        asset_id = binding.get("asset_id")
        if not isinstance(osm_id, str) or not isinstance(asset_id, str):
            raise ScenarioError("template binding needs osm_id and asset_id")
        if osm_id not in map_buildings:
            raise ScenarioError(f"template binding references unknown OSM building: {osm_id}")
        if osm_id in bound_osm_ids:
            raise ScenarioError(f"duplicate OSM building binding: {osm_id}")
        asset = library.asset(asset_id)
        if asset.event_phase == "post" and asset.review.status != "accepted":
            raise ScenarioError(f"inspection only mesh cannot enter benchmark: {asset.asset_id}")
        if asset.source_id in bound_source_ids:
            raise ScenarioError(f"duplicate heiDATA source building binding: {asset.source_id}")
        damage_override = binding.get("damage_state_override")
        if damage_override is not None:
            if damage_override not in {"intact", "minor"}:
                raise ScenarioError(
                    "damage_state_override is only supported for intact or minor pre-event geometry"
                )
            if asset.event_phase != "pre":
                raise ScenarioError("damage_state_override requires a pre-event heiDATA mesh")
            damage_override_by_osm[osm_id] = str(damage_override)
        bound_osm_ids.add(osm_id)
        bound_source_ids.add(asset.source_id)
        binding_by_osm[osm_id] = asset

    derived_by_osm: dict[str, str] = {}
    for binding in derived_bindings:
        if not isinstance(binding, dict):
            raise ScenarioError("derived damage binding must be an object")
        osm_id = binding.get("osm_id")
        damage_state = binding.get("damage_state")
        if not isinstance(osm_id, str) or not isinstance(damage_state, str):
            raise ScenarioError("derived damage binding needs osm_id and damage_state")
        if osm_id not in map_buildings:
            raise ScenarioError(f"derived damage binding references unknown OSM building: {osm_id}")
        if osm_id in bound_osm_ids or osm_id in derived_by_osm:
            raise ScenarioError(f"duplicate selected state for OSM building: {osm_id}")
        if damage_state not in {"minor", "major"}:
            raise ScenarioError(f"unknown derived damage state: {damage_state}")
        derived_by_osm[osm_id] = damage_state

    buildings: list[ScenarioBuilding] = []
    volumes: list[CollisionVolume] = []
    footprints: list[tuple[str, tuple[Point2, ...]]] = []
    for map_building in map_buildings.values():
        for existing_id, existing_footprint in footprints:
            if footprints_overlap(existing_footprint, map_building.footprint_local, float(data.get("overlap_tolerance_m", 0.05))):
                raise ScenarioError(f"overlapping OSM footprints: {existing_id}, {map_building.osm_id}")
        footprints.append((map_building.osm_id, map_building.footprint_local))
        asset = binding_by_osm.get(map_building.osm_id)
        if asset is None:
            damage_state = derived_by_osm.get(map_building.osm_id)
            if damage_state is None:
                height = map_building.height_m if map_building.height_m is not None else default_height
                visual_mesh = _extrude_footprint(map_building.footprint_local, height)
                building = ScenarioBuilding(map_building.osm_id, None, None, "osm_footprint_only", "osm_footprint_extrusion", visual_mesh, None, None, "source")
            else:
                visual_mesh, damage_geometry = _derived_damage_mesh(map_building, default_height, damage_state, seed)
                building = ScenarioBuilding(
                    map_building.osm_id, None, None, damage_state, "osm_footprint_derived_damage",
                    visual_mesh, None, damage_geometry, "scenario_derived",
                )
        else:
            visual_mesh, placement = _place_template(asset, map_building, default_height)
            damage_grade = damage_override_by_osm.get(map_building.osm_id, asset.damage_grade)
            building = ScenarioBuilding(
                map_building.osm_id, asset.source_id, asset.asset_id, damage_grade,
                "heidata_damage_template", visual_mesh, placement, None, "template",
            )
        buildings.append(building)
        volumes.append(_collision_for_mesh(f"collision:{building.osm_id}", building.osm_id, "building", building.visual_mesh, margin))

    overlays: list[OperationalOverlay] = []
    blocked_ids = {str(item) for item in data.get("blocked_road_ids", [])}
    available_roads = {road.osm_id: road for road in context.roads}
    unknown_roads = blocked_ids - set(available_roads)
    if unknown_roads:
        raise ScenarioError(f"blocked road is unknown: {sorted(unknown_roads)[0]}")
    for road in context.roads:
        overlays.append(_road_overlay(road, road.osm_id in blocked_ids))
        if road.osm_id in blocked_ids:
            zone = _blocked_zone(road)
            overlays.append(zone)
            xs = [point[0] for point in zone.geometry_enu_m]
            ys = [point[1] for point in zone.geometry_enu_m]
            obstruction = box_mesh(max(xs) - min(xs), max(ys) - min(ys), 2.0).translated((min(xs), min(ys), 0.0))
            volumes.append(_collision_for_mesh(f"collision:{zone.identifier}", zone.identifier, "blocked_zone", obstruction, margin))
    if bool(data.get("derive_rubble_for_destruction", True)):
        for building in buildings:
            is_template_destruction = building.damage_grade == "destruction"
            is_derived_major = building.damage_geometry is not None and building.damage_grade == "major"
            if not is_template_destruction and not (is_derived_major and bool(data.get("derive_rubble_for_major_damage", False))):
                continue
            for index, mesh in enumerate(_rubble_meshes(building, seed), start=1):
                note = (
                    "Deterministic rubble derived from an accepted destruction template"
                    if is_template_destruction
                    else "Deterministic rubble derived from an OSM footprint and scenario damage rule, not observed data"
                )
                overlay = OperationalOverlay(
                    f"rubble:{building.osm_id}:{index}", "rubble", "present", "derived",
                    tuple(tuple(float(value) for value in vertex) for vertex in mesh.vertices), (building.osm_id,), "rubble.v2",
                    note,
                )
                overlays.append(overlay)
                volumes.append(_collision_for_mesh(f"collision:{overlay.identifier}", overlay.identifier, "rubble", mesh, margin))

    min_x, min_y, max_x, max_y = context.world_bounds_2d
    boundary_margin = float(data.get("boundary_margin_m", 8.0))
    maximum_object_height = max(volume.maximum_enu_m[2] for volume in volumes)
    maximum_airspace = max(float(data.get("maximum_flight_altitude_m", 36.0)), maximum_object_height + margin)
    navigation_config = data.get("navigation", {})
    if not isinstance(navigation_config, dict):
        raise ScenarioError("navigation must be an object")
    navigation = build_navigation_volume(
        (min_x - boundary_margin, min_y - boundary_margin, 0.0), (max_x + boundary_margin, max_y + boundary_margin, maximum_airspace),
        tuple(volumes), float(navigation_config.get("cell_size_m", 6.0)),
        float(navigation_config.get("minimum_flight_altitude_m", 3.0)), maximum_airspace,
        float(navigation_config.get("altitude_step_m", 4.0)),
    )
    anchor_x = sum(building.centroid_local[0] for building in map_buildings.values()) / len(map_buildings)
    anchor_y = sum(building.centroid_local[1] for building in map_buildings.values()) / len(map_buildings)
    overlays.extend(_safe_pads(navigation, tuple(volumes), int(data.get("safe_pad_count", 2)), (anchor_x, anchor_y)))
    validation = _validate_overlays(context, tuple(overlays), navigation, tuple(volumes))
    return GeospatialScenario(
        identifier, "scenario.v1", seed, library.dataset_identifier, context, tuple(buildings), tuple(volumes),
        navigation, tuple(overlays), tuple(exclusions), validation,
    )


def write_scenario_json(scenario: GeospatialScenario, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(scenario.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
