"""Render a clean top down audit of DU OSM buildings versus the scene template.

This is an inspection artifact, not a simulator runtime dependency.  The
generated HTML embeds the source footprints so it remains viewable offline.
"""

import argparse
import json
import math
import urllib.request
import xml.etree.ElementTree as ElementTree
from pathlib import Path

import plotly.graph_objects as go


TEMPLATE = Path(__file__).parent / "data" / "templates" / "du_science_complex.json"


def _local_point(latitude, longitude, crop):
    mid_latitude = (crop["south"] + crop["north"]) / 2.0
    return (
        (longitude - crop["west"]) * 111_320 * math.cos(math.radians(mid_latitude)),
        (latitude - crop["south"]) * 111_320,
    )


def _osm_buildings(crop):
    url = "https://api.openstreetmap.org/api/0.6/map?bbox={},{},{},{}".format(
        crop["west"], crop["south"], crop["east"], crop["north"]
    )
    with urllib.request.urlopen(url, timeout=30) as response:
        root = ElementTree.fromstring(response.read())
    nodes = {
        item.attrib["id"]: (float(item.attrib["lat"]), float(item.attrib["lon"]))
        for item in root.findall("node")
    }
    buildings = []
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
        buildings.append(
            {
                "way_id": way.attrib["id"],
                "name": tags.get("name", "Unnamed mapped building"),
                "building_type": tags.get("building", "yes"),
                "footprint": footprint,
            }
        )
    return buildings, url


def _trace(building, color, label, opacity):
    points = building["footprint"]
    fill_color = color.replace("rgb(", "rgba(").replace(")", ", {})".format(opacity))
    return go.Scatter(
        x=[point[0] for point in points],
        y=[point[1] for point in points],
        mode="lines",
        fill="toself",
        fillcolor=fill_color,
        line={"color": color, "width": 2},
        name=label,
        legendgroup=label,
        hovertemplate=(
            "<b>{}</b><br>Simulation ID: {}<br>OSM way: {}<br>Type: {}<extra></extra>".format(
                building["display_name"], building["simulation_identifier"], building["way_id"], building["building_type"]
            )
        ),
        showlegend=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="results/du_map_completeness_audit.html")
    args = parser.parse_args()

    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    existing_by_osm_id = {
        item["source_ref"].removeprefix("osm-way-"): item["identifier"]
        for item in template["structures"]
        if item.get("source_ref", "").startswith("osm-way-")
    }
    buildings, source_url = _osm_buildings(template["crop"])
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=[None], y=[None], mode="lines", line={"color": "#2563eb", "width": 3}, name="Present in simulation template"))
    figure.add_trace(go.Scatter(x=[None], y=[None], mode="lines", line={"color": "#dc2626", "width": 3}, name="Mapped by OSM but missing from template"))
    for building in buildings:
        identifier = existing_by_osm_id.get(building["way_id"], "not yet included")
        building["simulation_identifier"] = identifier
        building["display_name"] = building["name"] if building["name"] != "Unnamed mapped building" else identifier.replace("_", " ").title()
        present = building["way_id"] in existing_by_osm_id
        figure.add_trace(_trace(
            building,
            "rgb(37, 99, 235)" if present else "rgb(220, 38, 38)",
            "Present in simulation template" if present else "Mapped by OSM but missing from template",
            0.20 if present else 0.10,
        ))
    figure.update_layout(
        title="DU map completeness audit: source footprints versus current simulation template",
        template="plotly_white",
        width=1050,
        height=850,
        xaxis={"title": "local x, metres", "scaleanchor": "y", "scaleratio": 1},
        yaxis={"title": "local y, metres"},
        annotations=[{
            "text": "OSM mapped buildings: {} | Current template buildings: {} | Missing from current template: {}".format(
                len(buildings), len(existing_by_osm_id), len(buildings) - len(existing_by_osm_id)
            ),
            "xref": "paper", "yref": "paper", "x": 0.5, "y": 1.08,
            "showarrow": False,
        }],
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(str(output), include_plotlyjs=True)
    print("Audit preview: {}".format(output))
    print("OSM mapped buildings: {}".format(len(buildings)))
    print("Present in template: {}".format(len(existing_by_osm_id)))
    print("Missing from template: {}".format(len(buildings) - len(existing_by_osm_id)))
    print("Source: {}".format(source_url))


if __name__ == "__main__":
    main()
