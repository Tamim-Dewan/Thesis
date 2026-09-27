"""Plotly rendering for the heiDATA benchmark scene."""

from __future__ import annotations

import plotly.graph_objects as go

from .mesh import Mesh
from .scene import DAMAGE_COLORS, BenchmarkScene


def _mesh_trace(mesh: Mesh, color: str, label: str, opacity: float = 0.72) -> go.Mesh3d:
    return go.Mesh3d(
        x=mesh.vertices[:, 0],
        y=mesh.vertices[:, 1],
        z=mesh.vertices[:, 2],
        i=mesh.faces[:, 0],
        j=mesh.faces[:, 1],
        k=mesh.faces[:, 2],
        name=label,
        color=color,
        opacity=opacity,
        hovertext=label,
        hoverinfo="text",
        flatshading=True,
    )


def _road_trace(road, color: str) -> go.Mesh3d:
    x0, y0 = road.start
    x1, y1 = road.end
    dx, dy = x1 - x0, y1 - y0
    length = max((dx * dx + dy * dy) ** 0.5, 1e-9)
    nx, ny = -dy / length * road.width / 2.0, dx / length * road.width / 2.0
    points = [(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)]
    return go.Mesh3d(
        x=[point[0] for point in points],
        y=[point[1] for point in points],
        z=[0.02] * 4,
        i=[0, 0], j=[1, 2], k=[2, 3],
        name=f"{road.identifier} ({road.status})",
        color=color,
        opacity=0.35,
        hovertext=f"{road.identifier}, {road.status}",
        hoverinfo="text",
    )


def render_scene(scene: BenchmarkScene) -> go.Figure:
    figure = go.Figure()
    for road in scene.roads:
        _color = "#c0392b" if road.status == "blocked" else "#7f8c8d"
        figure.add_trace(_road_trace(road, _color))
    for building in scene.buildings:
        color = DAMAGE_COLORS[building.damage_grade]
        for index, part in enumerate(building.parts):
            label = f"{building.scene_id}, {building.damage_grade}"
            if index:
                label += f", part {index + 1}"
            figure.add_trace(_mesh_trace(part, color, label))
    figure.add_trace(
        go.Scatter3d(
            x=[scene.base[0]], y=[scene.base[1]], z=[scene.base[2]],
            mode="markers+text", text=["base"], name="base",
            marker={"size": 8, "color": "#2980b9", "symbol": "diamond"},
        )
    )
    if scene.candidate_sites:
        figure.add_trace(
            go.Scatter3d(
                x=[point[0] for point in scene.candidate_sites],
                y=[point[1] for point in scene.candidate_sites],
                z=[point[2] for point in scene.candidate_sites],
                mode="markers", name="candidate sites",
                marker={"size": 5, "color": "#16a085"},
            )
        )
    figure.update_layout(
        title="heiDATA post earthquake benchmark environment",
        scene={
            "xaxis": {"title": "x, metres"},
            "yaxis": {"title": "y, metres"},
            "zaxis": {"title": "z, metres"},
            "aspectmode": "data",
        },
        legend={"orientation": "h"},
    )
    return figure
