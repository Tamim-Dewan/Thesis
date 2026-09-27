"""Frozen OpenStreetMap context loading and local metre projection.

The input keeps its original WGS 84 coordinates.  This module derives a small
local east north coordinate frame only for simulation geometry.  The local
frame is deterministic and its origin is exported with each scenario.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


EARTH_RADIUS_M = 6_378_137.0
Point2 = tuple[float, float]


class GeoContextError(ValueError):
    """Raised when a frozen OSM context cannot be used safely."""


@dataclass(frozen=True)
class MapBuilding:
    osm_id: str
    footprint_wgs84: tuple[Point2, ...]
    footprint_local: tuple[Point2, ...]
    height_m: float | None
    height_source: str
    tags: dict[str, str]

    @property
    def centroid_local(self) -> Point2:
        return polygon_centroid(self.footprint_local)

    @property
    def bounds_local(self) -> tuple[float, float, float, float]:
        return bounds_2d(self.footprint_local)


@dataclass(frozen=True)
class MapRoad:
    osm_id: str
    centerline_wgs84: tuple[Point2, ...]
    centerline_local: tuple[Point2, ...]
    tags: dict[str, str]


@dataclass(frozen=True)
class GeoContext:
    identifier: str
    path: str
    snapshot_at: str
    source: str
    license: str
    crs: str
    projection: str
    origin_wgs84: Point2
    buildings: tuple[MapBuilding, ...]
    roads: tuple[MapRoad, ...]

    @property
    def world_bounds_2d(self) -> tuple[float, float, float, float]:
        points = [point for building in self.buildings for point in building.footprint_local]
        points.extend(point for road in self.roads for point in road.centerline_local)
        if not points:
            raise GeoContextError("OSM context has no usable geometry")
        return bounds_2d(points)

    def as_dict(self) -> dict:
        return {
            "id": self.identifier,
            "path": self.path,
            "snapshot_at": self.snapshot_at,
            "source": self.source,
            "license": self.license,
            "crs": self.crs,
            "projection": self.projection,
            "origin_wgs84": list(self.origin_wgs84),
            "buildings": [
                {
                    "osm_id": building.osm_id,
                    "footprint_wgs84": [list(point) for point in building.footprint_wgs84],
                    "footprint_local_m": [list(point) for point in building.footprint_local],
                    "height_m": building.height_m,
                    "height_source": building.height_source,
                }
                for building in self.buildings
            ],
            "roads": [
                {
                    "osm_id": road.osm_id,
                    "centerline_wgs84": [list(point) for point in road.centerline_wgs84],
                    "centerline_local_m": [list(point) for point in road.centerline_local],
                }
                for road in self.roads
            ],
        }


def bounds_2d(points: Iterable[Point2]) -> tuple[float, float, float, float]:
    values = tuple(points)
    if not values:
        raise GeoContextError("geometry has no points")
    xs, ys = zip(*values)
    return min(xs), min(ys), max(xs), max(ys)


def polygon_area(points: tuple[Point2, ...]) -> float:
    if len(points) < 3:
        return 0.0
    total = 0.0
    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]):
        total += x0 * y1 - x1 * y0
    return abs(total) / 2.0


def polygon_centroid(points: tuple[Point2, ...]) -> Point2:
    signed_twice_area = 0.0
    x_total = 0.0
    y_total = 0.0
    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]):
        cross = x0 * y1 - x1 * y0
        signed_twice_area += cross
        x_total += (x0 + x1) * cross
        y_total += (y0 + y1) * cross
    if abs(signed_twice_area) < 1e-9:
        xs, ys = zip(*points)
        return sum(xs) / len(xs), sum(ys) / len(ys)
    return x_total / (3.0 * signed_twice_area), y_total / (3.0 * signed_twice_area)


def _project(point: Point2, origin: Point2) -> Point2:
    lon, lat = point
    origin_lon, origin_lat = origin
    east = math.radians(lon - origin_lon) * EARTH_RADIUS_M * math.cos(math.radians(origin_lat))
    north = math.radians(lat - origin_lat) * EARTH_RADIUS_M
    return east, north


def _read_points(coordinates: object, minimum_count: int, label: str) -> tuple[Point2, ...]:
    if not isinstance(coordinates, list) or len(coordinates) < minimum_count:
        raise GeoContextError(f"{label} has too few coordinates")
    result: list[Point2] = []
    for value in coordinates:
        if not isinstance(value, list) or len(value) < 2:
            raise GeoContextError(f"{label} has an invalid coordinate")
        lon, lat = float(value[0]), float(value[1])
        if not math.isfinite(lon) or not math.isfinite(lat) or not -180.0 <= lon <= 180.0 or not -90.0 <= lat <= 90.0:
            raise GeoContextError(f"{label} has an invalid WGS 84 coordinate")
        result.append((lon, lat))
    return tuple(result)


def _feature_parts(feature: dict) -> tuple[str, str, tuple[Point2, ...], dict]:
    properties = feature.get("properties")
    geometry = feature.get("geometry")
    if not isinstance(properties, dict) or not isinstance(geometry, dict):
        raise GeoContextError("GeoJSON feature is missing properties or geometry")
    kind = properties.get("kind")
    osm_id = properties.get("osm_id")
    if kind not in {"building", "road"} or not isinstance(osm_id, str) or not osm_id:
        raise GeoContextError("feature needs kind and osm_id")
    geometry_type = geometry.get("type")
    if kind == "building":
        if geometry_type != "Polygon":
            raise GeoContextError(f"building {osm_id} must be a Polygon")
        rings = geometry.get("coordinates")
        if not isinstance(rings, list) or not rings:
            raise GeoContextError(f"building {osm_id} has no exterior ring")
        points = _read_points(rings[0], 4, f"building {osm_id}")
        if points[0] == points[-1]:
            points = points[:-1]
        # WGS 84 polygon area is in square degrees at this parsing stage.  A
        # small positive threshold avoids rejecting normal building footprints.
        if len(points) < 3 or polygon_area(points) <= 1e-14:
            raise GeoContextError(f"building {osm_id} has an invalid footprint")
    else:
        if geometry_type != "LineString":
            raise GeoContextError(f"road {osm_id} must be a LineString")
        points = _read_points(geometry.get("coordinates"), 2, f"road {osm_id}")
    return kind, osm_id, points, properties


def load_osm_context(path: str | Path) -> GeoContext:
    """Load a frozen OSM GeoJSON extract without any network dependency."""

    source = Path(path)
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise GeoContextError(f"OSM context is unavailable: {source}") from error
    except json.JSONDecodeError as error:
        raise GeoContextError(f"OSM context is not valid JSON: {source}") from error
    if data.get("type") != "FeatureCollection" or not isinstance(data.get("features"), list):
        raise GeoContextError("OSM context must be a GeoJSON FeatureCollection")
    metadata = data.get("properties")
    if not isinstance(metadata, dict) or metadata.get("schema_version") != "osm_context.v1":
        raise GeoContextError("OSM context schema_version must be osm_context.v1")
    required_metadata = ("snapshot_at", "source", "license", "crs", "projection")
    if any(not metadata.get(key) for key in required_metadata):
        raise GeoContextError("OSM context metadata is incomplete")

    parsed = [_feature_parts(feature) for feature in data["features"]]
    source_points = [point for _, _, points, _ in parsed for point in points]
    if not source_points:
        raise GeoContextError("OSM context has no features")
    origin = (
        sum(point[0] for point in source_points) / len(source_points),
        sum(point[1] for point in source_points) / len(source_points),
    )
    building_ids: set[str] = set()
    road_ids: set[str] = set()
    buildings: list[MapBuilding] = []
    roads: list[MapRoad] = []
    for kind, osm_id, points, properties in parsed:
        if kind == "building":
            if osm_id in building_ids:
                raise GeoContextError(f"duplicate OSM building id: {osm_id}")
            building_ids.add(osm_id)
            height = properties.get("height_m")
            height_m = float(height) if height is not None else None
            if height_m is not None and (not math.isfinite(height_m) or height_m <= 0.0):
                raise GeoContextError(f"building {osm_id} has invalid height")
            buildings.append(
                MapBuilding(
                    osm_id, points, tuple(_project(point, origin) for point in points),
                    height_m, str(properties.get("height_source", "template_or_default")),
                    dict(properties.get("osm_tags", {})),
                )
            )
        else:
            if osm_id in road_ids:
                raise GeoContextError(f"duplicate OSM road id: {osm_id}")
            road_ids.add(osm_id)
            roads.append(MapRoad(osm_id, points, tuple(_project(point, origin) for point in points), dict(properties.get("osm_tags", {}))))
    if not buildings:
        raise GeoContextError("OSM context has no buildings")
    return GeoContext(
        str(data.get("name", source.stem)), str(source), str(metadata["snapshot_at"]),
        str(metadata["source"]), str(metadata["license"]), str(metadata["crs"]),
        str(metadata["projection"]), origin, tuple(sorted(buildings, key=lambda item: item.osm_id)),
        tuple(sorted(roads, key=lambda item: item.osm_id)),
    )


def _orientation(first: Point2, second: Point2, third: Point2) -> float:
    return (second[0] - first[0]) * (third[1] - first[1]) - (second[1] - first[1]) * (third[0] - first[0])


def _proper_segment_intersection(first: Point2, second: Point2, third: Point2, fourth: Point2, tolerance_m: float) -> bool:
    one = _orientation(first, second, third)
    two = _orientation(first, second, fourth)
    three = _orientation(third, fourth, first)
    four = _orientation(third, fourth, second)
    return (one > tolerance_m and two < -tolerance_m or one < -tolerance_m and two > tolerance_m) and (
        three > tolerance_m and four < -tolerance_m or three < -tolerance_m and four > tolerance_m
    )


def _strictly_contains(polygon: tuple[Point2, ...], point: Point2, tolerance_m: float) -> bool:
    x, y = point
    inside = False
    for (x0, y0), (x1, y1) in zip(polygon, polygon[1:] + polygon[:1]):
        if abs(_orientation((x0, y0), (x1, y1), point)) <= tolerance_m:
            continue
        if (y0 > y) != (y1 > y):
            crossing = (x1 - x0) * (y - y0) / (y1 - y0) + x0
            if crossing > x:
                inside = not inside
    return inside


def footprints_overlap(first: tuple[Point2, ...], second: tuple[Point2, ...], tolerance_m: float = 0.05) -> bool:
    """Return true only for area overlap, not a shared boundary edge."""

    if tolerance_m < 0:
        raise GeoContextError("overlap tolerance must not be negative")
    first_bounds = bounds_2d(first)
    second_bounds = bounds_2d(second)
    if first_bounds[2] <= second_bounds[0] + tolerance_m or second_bounds[2] <= first_bounds[0] + tolerance_m:
        return False
    if first_bounds[3] <= second_bounds[1] + tolerance_m or second_bounds[3] <= first_bounds[1] + tolerance_m:
        return False
    if len(first) == len(second) and all(math.dist(a, b) <= tolerance_m for a, b in zip(first, second)):
        return True
    for start_a, end_a in zip(first, first[1:] + first[:1]):
        for start_b, end_b in zip(second, second[1:] + second[:1]):
            if _proper_segment_intersection(start_a, end_a, start_b, end_b, tolerance_m):
                return True
    return _strictly_contains(first, second[0], tolerance_m) or _strictly_contains(second, first[0], tolerance_m)
