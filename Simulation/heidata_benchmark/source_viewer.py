"""Faithful visualisation of heiDATA OBJ coordinates.

The source OBJ models use Y as their vertical axis. Plotly uses Z as the
vertical axis, so visualisation maps source (X, Y, Z) to plot (X, Z, Y).
This is an axis permutation only. It never shifts, rescales, grids, or joins
the source models.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import plotly.graph_objects as go

from .mesh import Mesh, parse_obj


SOURCE_AXIS_CONVENTION = {
    "source_horizontal_axes": ("X", "Z"),
    "source_vertical_axis": "Y",
    "plot_mapping": "plot_x=source_x, plot_y=source_z, plot_z=source_y",
    "operation": "axis permutation only, with no translation or scale change",
}


@dataclass(frozen=True)
class SourcePair:
    scene_id: str
    source_id: str
    damage_grade: str
    pre_mesh: Mesh
    post_mesh: Mesh
    pre_file: str
    post_file: str

    @property
    def source_anchor_delta(self) -> tuple[float, float, float]:
        return tuple((self.post_mesh.minimum - self.pre_mesh.minimum).tolist())

    def report(self) -> dict:
        return {
            "scene_id": self.scene_id,
            "source_id": self.source_id,
            "damage_grade": self.damage_grade,
            "axis_convention": SOURCE_AXIS_CONVENTION,
            "pre_file": self.pre_file,
            "post_file": self.post_file,
            "pre_bounds_source_xyz": {
                "minimum": self.pre_mesh.minimum.tolist(),
                "maximum": self.pre_mesh.maximum.tolist(),
            },
            "post_bounds_source_xyz": {
                "minimum": self.post_mesh.minimum.tolist(),
                "maximum": self.post_mesh.maximum.tolist(),
            },
            "post_minus_pre_minimum_source_xyz": list(self.source_anchor_delta),
            "artificial_translation_applied": False,
            "artificial_layout_applied": False,
        }


@dataclass(frozen=True)
class SourceLayout:
    meshes: tuple[tuple[str, Mesh], ...]
    source_files: tuple[str, ...]


def source_y_up_to_plot_z_up(mesh: Mesh) -> Mesh:
    """Map source X,Y,Z to Plotly X,Z,Y without changing source positions."""

    return Mesh(mesh.vertices[:, (0, 2, 1)], mesh.faces.copy())


def _manifest_and_raw_dir(manifest_path: str | Path) -> tuple[dict, Path]:
    path = Path(manifest_path)
    return json.loads(path.read_text(encoding="utf-8")), path.parent / "raw"


def load_source_pair(manifest_path: str | Path, scene_id: str) -> SourcePair:
    manifest, raw_dir = _manifest_and_raw_dir(manifest_path)
    entry = next((value for value in manifest["buildings"] if value["scene_id"] == scene_id), None)
    if entry is None:
        raise ValueError(f"unknown source pair: {scene_id}")
    if "post" not in entry:
        raise ValueError(f"{scene_id} has no post event source model")
    pre = parse_obj(raw_dir / entry["pre"])
    post = parse_obj(raw_dir / entry["post"])
    return SourcePair(
        entry["scene_id"], entry["source_id"], entry["damage_grade"],
        pre, post, entry["pre"], entry["post"],
    )


def load_source_layout(manifest_path: str | Path) -> SourceLayout:
    manifest, raw_dir = _manifest_and_raw_dir(manifest_path)
    seen: set[str] = set()
    meshes: list[tuple[str, Mesh]] = []
    for entry in manifest["buildings"]:
        source_file = entry["pre"]
        if source_file in seen:
            continue
        seen.add(source_file)
        meshes.append((entry["source_id"], parse_obj(raw_dir / source_file)))
    return SourceLayout(tuple(meshes), tuple(sorted(seen)))


def _trace(mesh: Mesh, color: str, label: str, opacity: float) -> go.Mesh3d:
    plot_mesh = source_y_up_to_plot_z_up(mesh)
    return go.Mesh3d(
        x=plot_mesh.vertices[:, 0],
        y=plot_mesh.vertices[:, 1],
        z=plot_mesh.vertices[:, 2],
        i=plot_mesh.faces[:, 0],
        j=plot_mesh.faces[:, 1],
        k=plot_mesh.faces[:, 2],
        name=label,
        color=color,
        opacity=opacity,
        hovertext=label,
        hoverinfo="text",
        flatshading=True,
    )


def _source_layout_axes() -> dict:
    return {
        "xaxis": {"title": "source X, metres"},
        "yaxis": {"title": "source Z, metres"},
        "zaxis": {"title": "source Y, vertical, metres"},
        "aspectmode": "data",
        # Look across the source X--Z ground plane; source Y is the vertical
        # direction after the X,Y,Z -> X,Z,Y display permutation.
        "camera": {"eye": {"x": 1.45, "y": -1.45, "z": 0.9}},
    }


def render_source_pair(pair: SourcePair) -> go.Figure:
    figure = go.Figure()
    figure.add_trace(_trace(pair.pre_mesh, "#7f8c8d", "pre event source mesh", 0.28))
    figure.add_trace(_trace(pair.post_mesh, "#c0392b", f"post event source mesh, {pair.damage_grade}", 0.78))
    figure.update_layout(
        title=f"heiDATA source pair: {pair.scene_id}",
        scene=_source_layout_axes(),
        annotations=[{
            "text": "Source coordinates retained. Display only maps source X,Y,Z to Plotly X,Z,Y.",
            "xref": "paper", "yref": "paper", "x": 0, "y": -0.08, "showarrow": False,
        }],
    )
    return figure


def render_source_layout(layout: SourceLayout) -> go.Figure:
    palette = ("#1f77b4", "#2ca02c", "#9467bd", "#17becf", "#bcbd22", "#ff7f0e", "#8c564b", "#e377c2")
    figure = go.Figure()
    for index, (source_id, mesh) in enumerate(layout.meshes):
        figure.add_trace(_trace(mesh, palette[index % len(palette)], f"pre event source mesh, {source_id}", 0.72))
    figure.update_layout(
        title="heiDATA source-faithful pre-event layout (Y is vertical)",
        scene=_source_layout_axes(),
        annotations=[{
            "text": "Source X,Y,Z is displayed as Plotly X,Z,Y. No grid, road, base, task, or artificial translation is present.",
            "xref": "paper", "yref": "paper", "x": 0, "y": -0.08, "showarrow": False,
        }],
    )
    return figure
