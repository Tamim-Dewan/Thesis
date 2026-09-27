"""Create a thesis friendly static overview of the OSM anchored benchmark."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Polygon

from heidata_benchmark.environment import build_geospatial_scenario
from heidata_benchmark.geospatial import load_osm_context
from heidata_benchmark.library import build_mesh_library
from heidata_benchmark.mesh import convex_hull


COLORS = {
    "osm_footprint_only": "#c7d0d9",
    "no_damage": "#2ca02c",
    "minor": "#f4d03f",
    "major": "#d35400",
    "heavy": "#f1c40f",
    "extreme": "#e67e22",
    "destruction": "#c0392b",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--asset-manifest", type=Path, default=Path("heidata_benchmark/data/sample/manifest.json"))
    parser.add_argument("--osm-context", type=Path, default=Path("heidata_benchmark/data/sample/osm_context.v1.geojson"))
    parser.add_argument("--scenario", type=Path, default=Path("heidata_benchmark/data/sample/scenario.v1.json"))
    parser.add_argument("--output", type=Path, default=Path("results/heidata_geospatial_overview.png"))
    args = parser.parse_args()

    scenario = build_geospatial_scenario(
        args.scenario, load_osm_context(args.osm_context), build_mesh_library(args.asset_manifest)
    )
    figure, axis = plt.subplots(figsize=(12, 9), constrained_layout=True)
    map_buildings = {item.osm_id: item for item in scenario.context.buildings}
    for building in scenario.buildings:
        footprint = map_buildings[building.osm_id].footprint_local
        axis.add_patch(Polygon(footprint, closed=True, facecolor="#e8edf2", edgecolor="#4b5d6b", linewidth=0.65, zorder=2))
    for overlay in scenario.overlays:
        if overlay.kind == "road":
            color = "#c0392b" if overlay.status == "blocked" else "#768390"
            axis.plot(*zip(*[(point[0], point[1]) for point in overlay.geometry_enu_m]), color=color, linewidth=1.2, zorder=1)
        elif overlay.kind == "rubble":
            axis.add_patch(Polygon([(point[0], point[1]) for point in overlay.geometry_enu_m[:4]], closed=True, facecolor="#ca8a04", edgecolor="none", zorder=5))
        elif overlay.kind == "launch_landing_pad":
            x, y, _ = overlay.geometry_enu_m[0]
            axis.scatter(x, y, s=62, color="#2980b9", marker="D", edgecolors="white", linewidths=0.8, zorder=6)
    for building in scenario.buildings:
        if building.asset_id is None and building.damage_geometry is None:
            continue
        template_hull = convex_hull(building.visual_mesh.vertices[:, :2])
        axis.add_patch(
            Polygon(
                template_hull,
                closed=True, facecolor=COLORS[building.damage_grade], edgecolor="#2c3e50", linewidth=0.8, alpha=0.9, zorder=4,
            )
        )
    axis.set_title("L’Aquila OSM anchored post earthquake environment", pad=12)
    axis.set_xlabel("Local east, metres")
    axis.set_ylabel("Local north, metres")
    axis.set_aspect("equal", adjustable="box")
    axis.grid(True, color="#d9e1e8", linewidth=0.6)
    axis.legend(
        handles=[
            Patch(facecolor="#e8edf2", edgecolor="#4b5d6b", label="OSM footprint only"),
            Patch(facecolor=COLORS["no_damage"], edgecolor="#2c3e50", label="Intact heiDATA template"),
            Patch(facecolor=COLORS["minor"], edgecolor="#2c3e50", label="Scenario derived minor damage"),
            Patch(facecolor=COLORS["major"], edgecolor="#2c3e50", label="Scenario derived major damage"),
            Patch(facecolor=COLORS["extreme"], edgecolor="#2c3e50", label="Extreme heiDATA template"),
            Patch(facecolor=COLORS["destruction"], edgecolor="#2c3e50", label="Destruction heiDATA template"),
            Patch(facecolor="#ca8a04", edgecolor="none", label="Ground rubble"),
            Line2D([0], [0], color="#c0392b", lw=2, label="Blocked OSM road"),
            Line2D([0], [0], marker="D", color="w", markerfacecolor="#2980b9", markeredgecolor="white", markersize=8, label="Safe UAV base pad"),
        ],
        loc="upper right", frameon=True,
    )
    axis.text(
        0.01, -0.12,
        "OSM outlines and roads are frozen map evidence. heiDATA meshes are templates. Minor and major coloured OSM footprints are scenario derived damage, not observed earthquake damage.",
        transform=axis.transAxes, fontsize=9, va="top",
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(args.output, dpi=180, bbox_inches="tight")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
