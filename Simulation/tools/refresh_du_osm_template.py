"""Preprocess the selected DU OSM crop into a complete local template.

This is a one time preprocessing tool.  The simulator itself continues to
read only the checked in JSON template and never downloads OSM data at run
time.
"""

import json
import math
import re
import urllib.request
import xml.etree.ElementTree as ElementTree
from pathlib import Path


ROOT = Path(__file__).parents[1]
TEMPLATE_PATH = ROOT / "data" / "templates" / "du_science_complex.json"


def _slug(value):
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _local_point(latitude, longitude, crop):
    latitude_midpoint = (crop["south"] + crop["north"]) / 2.0
    return (
        round((longitude - crop["west"]) * 111_320 * math.cos(math.radians(latitude_midpoint)), 2),
        round((latitude - crop["south"]) * 111_320, 2),
    )


def _height(tags):
    levels = tags.get("building:levels") or tags.get("levels")
    if levels:
        try:
            return max(3.5, float(levels) * 3.5), "osm_building_levels"
        except ValueError:
            pass
    return 10.0, "imputed_context_height"


def main():
    template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    crop = template["crop"]
    existing = {item["source_ref"]: item for item in template["structures"]}
    url = "https://api.openstreetmap.org/api/0.6/map?bbox={},{},{},{}".format(
        crop["west"], crop["south"], crop["east"], crop["north"]
    )
    with urllib.request.urlopen(url, timeout=30) as response:
        root = ElementTree.fromstring(response.read())
    nodes = {
        item.attrib["id"]: (float(item.attrib["lat"]), float(item.attrib["lon"]))
        for item in root.findall("node")
    }
    structures = []
    for way in root.findall("way"):
        tags = {item.attrib["k"]: item.attrib["v"] for item in way.findall("tag")}
        if "building" not in tags:
            continue
        footprint = [
            _local_point(*nodes[item.attrib["ref"]], crop)
            for item in way.findall("nd")
            if item.attrib["ref"] in nodes
        ]
        if len(footprint) < 3:
            continue
        if footprint[0] != footprint[-1]:
            footprint.append(footprint[0])
        source_ref = "osm-way-{}".format(way.attrib["id"])
        previous = existing.get(source_ref)
        if previous:
            record = dict(previous)
            record["footprint"] = [list(point) for point in footprint]
            record["scene_role"] = "target"
        else:
            width = max(point[0] for point in footprint) - min(point[0] for point in footprint)
            depth = max(point[1] for point in footprint) - min(point[1] for point in footprint)
            height, height_source = _height(tags)
            record = {
                "identifier": "context_{}_{}".format(_slug(tags.get("name", "building")) or "building", way.attrib["id"]),
                "minimum": [min(point[0] for point in footprint), min(point[1] for point in footprint), 0],
                "width": round(width, 2),
                "depth": round(depth, 2),
                "height": height,
                "height_source": height_source,
                "source_ref": source_ref,
                "footprint": [list(point) for point in footprint],
                "scene_role": "context",
            }
        structures.append(record)
    structures.sort(key=lambda item: (item["scene_role"] != "target", item["identifier"]))
    all_points = [point for item in structures for point in item["footprint"]]
    template["structures"] = structures
    template["bounds"] = [
        math.floor(min(point[0] for point in all_points) - 5),
        math.floor(min(point[1] for point in all_points) - 5),
        0,
        math.ceil(max(point[0] for point in all_points) + 5),
        math.ceil(max(point[1] for point in all_points) + 5),
        60,
    ]
    template["base_position"] = [6, 6, 0]
    template["version"] = "osm-2026-09-24.v4"
    template["crop"]["selection_rule"] = "all mapped building footprints returned by the DU Science Complex source crop; eight named research buildings are earthquake targets and the rest are static context"
    template["provenance"][0]["role"] = "complete mapped DU crop with target buildings and static surrounding context"
    template["provenance"][0]["preprocessing_version"] = "local-metric-crop.v4"
    TEMPLATE_PATH.write_text(json.dumps(template, indent=2), encoding="utf-8")
    print("Updated {} with {} OSM building footprints".format(TEMPLATE_PATH, len(structures)))
    print("World bounds: {}".format(template["bounds"]))


if __name__ == "__main__":
    main()
