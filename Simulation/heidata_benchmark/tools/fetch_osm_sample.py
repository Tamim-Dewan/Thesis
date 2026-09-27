"""Fetch and freeze a small OpenStreetMap context for the heiDATA benchmark.

The output is a local GeoJSON file. It is intentionally used as an offline
research input, never fetched by the runtime simulator.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_QUERY = """[out:json][timeout:30];
(
  way[\"building\"](42.3498,13.3950,42.3522,13.3990);
  way[\"highway\"](42.3498,13.3950,42.3522,13.3990);
);
out geom;"""


def _height_m(tags: dict[str, str]) -> tuple[float | None, str]:
    value = tags.get("height")
    if value:
        try:
            return float(value.lower().replace("m", "").strip()), "osm:height"
        except ValueError:
            pass
    levels = tags.get("building:levels")
    if levels:
        try:
            return float(levels) * 3.0, "osm:building:levels_times_3m"
        except ValueError:
            pass
    return None, "template_or_default"


def overpass_to_geojson(payload: dict, snapshot_at: str) -> dict:
    """Convert Overpass way geometry to a reproducible GeoJSON context."""

    features: list[dict] = []
    for element in payload.get("elements", []):
        tags = element.get("tags", {})
        geometry = element.get("geometry", [])
        if len(geometry) < 2:
            continue
        coordinates = [[point["lon"], point["lat"]] for point in geometry]
        identifier = f"way/{element['id']}"
        if "building" in tags and len(coordinates) >= 4:
            if coordinates[0] != coordinates[-1]:
                coordinates.append(coordinates[0])
            height_m, height_source = _height_m(tags)
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "kind": "building",
                        "osm_id": identifier,
                        "osm_tags": tags,
                        "height_m": height_m,
                        "height_source": height_source,
                        "provenance": "source",
                    },
                    "geometry": {"type": "Polygon", "coordinates": [coordinates]},
                }
            )
        elif "highway" in tags:
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "kind": "road",
                        "osm_id": identifier,
                        "osm_tags": tags,
                        "provenance": "source",
                    },
                    "geometry": {"type": "LineString", "coordinates": coordinates},
                }
            )
    return {
        "type": "FeatureCollection",
        "name": "laquila_osm_context_v1",
        "properties": {
            "schema_version": "osm_context.v1",
            "snapshot_at": snapshot_at,
            "source": "OpenStreetMap via Overpass API",
            "license": "ODbL 1.0, OpenStreetMap contributors",
            "crs": "EPSG:4326",
            "query": DEFAULT_QUERY,
            "projection": "local_tangent_equirectangular, origin recorded by loader",
        },
        "features": features,
    }


def fetch(query: str) -> dict:
    endpoint = "https://overpass-api.de/api/interpreter"
    request = Request(
        f"{endpoint}?{urlencode({'data': query})}",
        headers={"User-Agent": "ThesisHeiDATAEnvironment/1.0 (academic research)"},
    )
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("heidata_benchmark/data/sample/osm_context.v1.geojson"))
    parser.add_argument("--input", type=Path, help="existing Overpass JSON, useful for a repeatable conversion")
    parser.add_argument("--snapshot-at", help="ISO timestamp used in the frozen GeoJSON")
    args = parser.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8")) if args.input else fetch(DEFAULT_QUERY)
    snapshot_at = args.snapshot_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    context = overpass_to_geojson(payload, snapshot_at)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(context, indent=2, sort_keys=True), encoding="utf-8")
    building_count = sum(feature["properties"]["kind"] == "building" for feature in context["features"])
    road_count = sum(feature["properties"]["kind"] == "road" for feature in context["features"])
    print(f"Wrote {args.output}: {building_count} buildings, {road_count} roads")


if __name__ == "__main__":
    main()
