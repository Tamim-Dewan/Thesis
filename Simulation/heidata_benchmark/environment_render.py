"""Plotly output for a geospatial heiDATA controlled benchmark."""

from __future__ import annotations

import html
from pathlib import Path

import plotly.graph_objects as go

from .environment import GeospatialScenario, OperationalOverlay
from .mesh import Mesh


COLORS = {
    "osm_footprint_only": "#9aa5b1",
    "no_damage": "#2ca02c",
    "minor": "#f4d03f",
    "major": "#d35400",
    "heavy": "#f1c40f",
    "extreme": "#e67e22",
    "destruction": "#c0392b",
}
STANDING_BUILDING_COLOR = "#607d8b"

STORYBOARD_VIEWS = (
    "01_map_evidence",
    "02_building_states",
    "03_damage_composition",
    "04_collision_navigation",
    "05_operational_overlays",
)


def _mesh_trace(
    mesh: Mesh, color: str, name: str, hover: str, opacity: float, legend_group: str, show_legend: bool,
) -> go.Mesh3d:
    return go.Mesh3d(
        x=mesh.vertices[:, 0], y=mesh.vertices[:, 1], z=mesh.vertices[:, 2],
        i=mesh.faces[:, 0], j=mesh.faces[:, 1], k=mesh.faces[:, 2],
        name=name, color=color, opacity=opacity, flatshading=True, hovertext=hover, hoverinfo="text",
        legendgroup=legend_group, showlegend=show_legend,
    )


def _building_name(building) -> str:
    """Return a readable OSM name, with a stable fallback for unnamed buildings."""

    name = building.tags.get("name") or building.tags.get("official_name")
    return str(name) if name else f"OSM building {building.osm_id}"


def _building_hover(scenario_building, map_building) -> str:
    """Describe one physical building without hiding its provenance."""

    name = html.escape(_building_name(map_building))
    osm_id = html.escape(map_building.osm_id)
    grade = html.escape(scenario_building.damage_grade)
    provenance = html.escape(scenario_building.provenance)
    lines = [f"<b>{name}</b>", f"OSM ID: {osm_id}", f"Damage state: {grade}", f"Provenance: {provenance}"]
    if scenario_building.asset_id:
        lines.append(f"heiDATA template: {html.escape(scenario_building.asset_id)}")
        lines.append("Template geometry, not observed OSM damage")
    elif scenario_building.damage_geometry:
        lines.append("Controlled OSM footprint damage, not observed earthquake damage")
    else:
        lines.append("OSM footprint extrusion")
    if scenario_building.damage_grade in {"osm_footprint_only", "no_damage"}:
        lines.append("Rendered geometry: standing building volume")
    return "<br>".join(lines)


def _footprint_trace(building) -> go.Scatter3d:
    points = building.footprint_local + building.footprint_local[:1]
    return go.Scatter3d(
        x=[point[0] for point in points], y=[point[1] for point in points], z=[0.04] * len(points),
        mode="lines", name="OSM footprint", legendgroup="osm_footprints", showlegend=False,
        line={"color": "#34495e", "width": 3},
        hovertext=f"<b>{html.escape(_building_name(building))}</b><br>OSM ID: {html.escape(building.osm_id)}<br>Source footprint",
        hoverinfo="text",
    )


def _rubble_trace(overlay: OperationalOverlay) -> go.Mesh3d:
    points = overlay.geometry_enu_m
    if len(points) == 8:
        faces = (
            (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
            (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
            (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
        )
    else:
        faces = ((0, 2, 1), (0, 3, 2))
    return go.Mesh3d(
        x=[point[0] for point in points], y=[point[1] for point in points], z=[point[2] for point in points],
        i=[face[0] for face in faces], j=[face[1] for face in faces], k=[face[2] for face in faces],
        name="ground rubble", legendgroup="rubble", color="#ca8a04", opacity=0.88,
        flatshading=True, hovertext=f"<b>{overlay.identifier}</b><br>Ground rubble, 3D derived piece<br>{html.escape(overlay.notes)}",
        hoverinfo="text",
    )


def render_geospatial_scenario(scenario: GeospatialScenario) -> go.Figure:
    """Render the clean airborne operational view used by the other environments."""

    return _full_scene_figure(scenario, show_context=False)


def write_scenario_html(scenario: GeospatialScenario, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    render_geospatial_scenario(scenario).write_html(str(target), include_plotlyjs=True)


def _footprint_polygon(scenario: GeospatialScenario, osm_id: str) -> tuple[tuple[float, float], ...]:
    for building in scenario.context.buildings:
        if building.osm_id == osm_id:
            return building.footprint_local
    raise ValueError(f"scenario building has no OSM footprint: {osm_id}")


def _is_damage_target(building) -> bool:
    return building.damage_grade not in {"osm_footprint_only", "no_damage"}


def _story_bounds(scenario: GeospatialScenario) -> tuple[float, float, float, float]:
    min_x, min_y, max_x, max_y = scenario.context.world_bounds_2d
    return min_x - 12.0, min_y - 12.0, max_x + 12.0, max_y + 12.0


def _operational_bounds(scenario: GeospatialScenario) -> tuple[float, float, float, float]:
    """Return airborne scene bounds without stretching to the road context."""

    selected_ids = {building.osm_id for building in scenario.buildings}
    points = [
        point
        for building in scenario.context.buildings
        if building.osm_id in selected_ids
        for point in building.footprint_local
    ]
    for overlay in scenario.overlays:
        if overlay.kind != "road":
            points.extend((point[0], point[1]) for point in overlay.geometry_enu_m)
    if not points:
        return _story_bounds(scenario)
    min_x = min(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_x = max(point[0] for point in points)
    max_y = max(point[1] for point in points)
    return min_x - 12.0, min_y - 12.0, max_x + 12.0, max_y + 12.0


def _source_map_figure(scenario: GeospatialScenario) -> go.Figure:
    scenario_by_osm = {building.osm_id: building for building in scenario.buildings}
    excluded = {item["osm_id"] for item in scenario.excluded_osm_buildings}
    figure = go.Figure()
    shown: set[str] = set()
    for map_building in scenario.context.buildings:
        selected = scenario_by_osm.get(map_building.osm_id)
        if map_building.osm_id in excluded:
            role, color, fill = "excluded overlapping OSM source footprint", "#64748b", None
        elif selected is not None and _is_damage_target(selected):
            role, color, fill = "earthquake target building", "#1d4ed8", "rgba(37, 99, 235, .32)"
        else:
            role, color, fill = "static context building", "#64748b", "rgba(148, 163, 184, .24)"
        points = map_building.footprint_local + map_building.footprint_local[:1]
        figure.add_trace(go.Scatter(
            x=[point[0] for point in points], y=[point[1] for point in points], mode="lines",
            fill="toself" if fill else None, fillcolor=fill,
            line={"color": color, "width": 2, "dash": "dot" if map_building.osm_id in excluded else "solid"},
            name=role, legendgroup=role, showlegend=role not in shown,
            hovertemplate=(
                f"<b>{html.escape(_building_name(map_building))}</b><br>OSM ID: {html.escape(map_building.osm_id)}"
                f"<br>Role: {role}<br>Source: stored OSM snapshot<extra></extra>"
            ),
        ))
        shown.add(role)
    first_pad = True
    for overlay in scenario.overlays:
        if overlay.kind != "launch_landing_pad":
            continue
        point = overlay.geometry_enu_m[0]
        label = "primary UAV base" if overlay.identifier == "safe_pad:1" else "alternate UAV base"
        show_label = overlay.identifier == "safe_pad:1"
        figure.add_trace(go.Scatter(
            x=[point[0]], y=[point[1]], mode="markers+text" if show_label else "markers", text=[label] if show_label else None,
            textposition="top center", name="safe UAV pad", legendgroup="safe_pads", showlegend=first_pad,
            marker={"size": 11, "color": "#1d4ed8", "symbol": "diamond"},
            hovertemplate=f"<b>{label}</b><br>ID: {overlay.identifier}<br>{overlay.notes}<extra></extra>",
        ))
        first_pad = False
    min_x, min_y, max_x, max_y = _story_bounds(scenario)
    target_count = sum(_is_damage_target(building) for building in scenario.buildings)
    figure.update_layout(
        title={"text": (
            "heiDATA OSM source map: every stored footprint"
            f"<br><sup>OSM features: {len(scenario.context.buildings)} | Scenario buildings: {len(scenario.buildings)} | "
            f"Earthquake targets: {target_count} | Static context: {len(scenario.buildings) - target_count}</sup>"
        )},
        template="plotly_white", width=1150, height=820,
        xaxis={"title": "local east, metres", "range": [min_x, max_x], "scaleanchor": "y", "scaleratio": 1},
        yaxis={"title": "local north, metres", "range": [min_y, max_y]},
        legend={"orientation": "h"}, margin={"t": 100},
    )
    return figure


def _ground_trace(scenario: GeospatialScenario) -> go.Mesh3d:
    min_x, min_y, max_x, max_y = _operational_bounds(scenario)
    return go.Mesh3d(
        x=[min_x, max_x, max_x, min_x], y=[min_y, min_y, max_y, max_y], z=[0, 0, 0, 0],
        i=[0, 0], j=[1, 2], k=[2, 3], color="#e2e8f0", opacity=0.28,
        name="ground reference", hoverinfo="skip", showlegend=False,
    )


def _legend_proxy_3d(name: str, color: str, group: str) -> go.Scatter3d:
    return go.Scatter3d(
        x=[None], y=[None], z=[None], mode="markers", name=name, legendgroup=group,
        marker={"size": 8, "color": color}, hoverinfo="skip", showlegend=True,
    )


def _polygon_prism_trace(points, z0: float, heights, color: str, name: str, opacity: float, group: str) -> go.Mesh3d:
    values = tuple(points)
    top = tuple(float(value) for value in heights) if not isinstance(heights, (int, float)) else tuple(float(heights) for _ in values)
    count = len(values)
    vertices = [(x, y, z0) for x, y in values] + [(x, y, top[index]) for index, (x, y) in enumerate(values)]
    faces: list[tuple[int, int, int]] = []
    for index in range(1, count - 1):
        faces.extend(((0, index + 1, index), (count, count + index, count + index + 1)))
    for index in range(count):
        following = (index + 1) % count
        faces.extend(((index, following, count + following), (index, count + following, count + index)))
    return go.Mesh3d(
        x=[value[0] for value in vertices], y=[value[1] for value in vertices], z=[value[2] for value in vertices],
        i=[face[0] for face in faces], j=[face[1] for face in faces], k=[face[2] for face in faces],
        name=name, legendgroup=group, showlegend=False, color=color, opacity=opacity,
        hovertext=name, hoverinfo="text", flatshading=True,
    )


def _source_height(building) -> float:
    if building.damage_geometry is not None:
        return building.damage_geometry.target_height_m
    if building.placement is not None:
        return building.placement.target_height_m
    return float(building.visual_mesh.maximum[2])


def _add_safe_pads_3d(figure: go.Figure, scenario: GeospatialScenario) -> None:
    first = True
    for overlay in scenario.overlays:
        if overlay.kind != "launch_landing_pad":
            continue
        point = overlay.geometry_enu_m[0]
        label = "primary UAV base" if overlay.identifier == "safe_pad:1" else "alternate UAV base"
        show_label = overlay.identifier == "safe_pad:1"
        figure.add_trace(go.Scatter3d(
            x=[point[0]], y=[point[1]], z=[point[2]], mode="markers+text" if show_label else "markers", text=[label] if show_label else None,
            textposition="top center", name="safe UAV pad", legendgroup="safe_pads", showlegend=first,
            marker={"size": 7, "color": "#1d4ed8", "symbol": "diamond"},
            hovertext=[f"<b>{label}</b><br>ID: {overlay.identifier}<br>{overlay.notes}"], hoverinfo="text",
        ))
        first = False


def _scene_layout(figure: go.Figure, scenario: GeospatialScenario, title: str, note: str = "") -> go.Figure:
    min_x, min_y, max_x, max_y = _operational_bounds(scenario)
    maximum_height = max(
        max(float(building.visual_mesh.maximum[2]) for building in scenario.buildings),
        max(volume.maximum_enu_m[2] for volume in scenario.collision_volumes),
    )
    figure.update_layout(
        title=title, template="plotly_white", width=1150, height=820,
        scene={
            "xaxis": {"title": "local east, metres", "range": [min_x, max_x]},
            "yaxis": {"title": "local north, metres", "range": [min_y, max_y]},
            "zaxis": {"title": "height, metres", "range": [0, maximum_height + 2]},
            "aspectmode": "data", "camera": {"eye": {"x": 1.45, "y": -1.65, "z": 1.2}},
        },
        legend={"orientation": "h"},
        annotations=[] if not note else [{
            "text": note, "xref": "paper", "yref": "paper", "x": 0, "y": -0.09, "showarrow": False,
            "font": {"size": 12, "color": "#34495e"},
        }],
    )
    return figure


def _building_layout_figure(scenario: GeospatialScenario) -> go.Figure:
    figure = go.Figure([_ground_trace(scenario)])
    figure.add_trace(_legend_proxy_3d("earthquake target building", "#2563eb", "targets"))
    figure.add_trace(_legend_proxy_3d("static context building", "#94a3b8", "context"))
    for building in scenario.buildings:
        target = _is_damage_target(building)
        role = "earthquake target building" if target else "static context building"
        figure.add_trace(_polygon_prism_trace(
            _footprint_polygon(scenario, building.osm_id), 0.0, _source_height(building),
            "#2563eb" if target else "#94a3b8", f"{role} ({building.osm_id})",
            0.54 if target else 0.32, "targets" if target else "context",
        ))
    _add_safe_pads_3d(figure, scenario)
    return _scene_layout(
        figure, scenario, "heiDATA OSM source building layout: every nonredundant scenario footprint",
        "Exact OSM footprints and positions. One overlapping source feature is excluded by the scenario manifest.",
    )


def _damage_figure(scenario: GeospatialScenario) -> go.Figure:
    figure = go.Figure([_ground_trace(scenario)])
    states = sorted({building.damage_grade for building in scenario.buildings if _is_damage_target(building)})
    for state in states:
        figure.add_trace(_legend_proxy_3d(f"{state} damage footprint marker", COLORS[state], f"damage:{state}"))
    figure.add_trace(_legend_proxy_3d("static context footprint", "#94a3b8", "context"))
    if any(not _is_damage_target(building) for building in scenario.buildings):
        figure.add_trace(_legend_proxy_3d("standing building volume", STANDING_BUILDING_COLOR, "standing-buildings"))
    map_buildings = {building.osm_id: building for building in scenario.context.buildings}
    shown_geometry: set[str] = set()
    for building in scenario.buildings:
        map_building = map_buildings[building.osm_id]
        hover = _building_hover(building, map_building)
        points = _footprint_polygon(scenario, building.osm_id)
        closed = points + points[:1]
        if not _is_damage_target(building):
            figure.add_trace(go.Scatter3d(
                x=[point[0] for point in closed], y=[point[1] for point in closed], z=[0.08] * len(closed),
                mode="lines", name="static context footprint", legendgroup="context", showlegend=False,
                line={"color": "#94a3b8", "width": 1, "dash": "dot"}, hovertext=[hover] * len(closed), hoverinfo="text",
            ))
            figure.add_trace(_mesh_trace(
                building.visual_mesh,
                STANDING_BUILDING_COLOR,
                "standing building volume",
                hover,
                0.42,
                "standing-buildings",
                "standing-buildings" not in shown_geometry,
            ))
            shown_geometry.add("standing-buildings")
            continue
        state = building.damage_grade
        marker = _polygon_prism_trace(points, 0.0, 0.18, COLORS[state], f"{state} damage footprint marker", 0.26, f"damage:{state}")
        marker.update(hovertext=hover, hoverinfo="text")
        figure.add_trace(marker)
        geometry_label = "heiDATA damage template" if building.asset_id else "scenario derived damage geometry"
        group = f"geometry:{geometry_label}"
        figure.add_trace(_mesh_trace(
            building.visual_mesh, COLORS[state], geometry_label,
            hover,
            0.68, group, group not in shown_geometry,
        ))
        shown_geometry.add(group)
    rubble_shown = False
    for overlay in scenario.overlays:
        if overlay.kind != "rubble":
            continue
        trace = _rubble_trace(overlay)
        trace.showlegend = not rubble_shown
        figure.add_trace(trace)
        rubble_shown = True
    _add_safe_pads_3d(figure, scenario)
    return _scene_layout(
        figure, scenario, "heiDATA post earthquake damage layer: standing volumes and damage targets",
        "Standing building volumes use the mapped OSM footprint extrusion. Damage meshes are heiDATA templates or controlled derived geometry.",
    )


def _collision_volume_trace(volume, color: str, label: str, group: str, show_legend: bool) -> go.Mesh3d:
    low = volume.minimum_enu_m
    high = volume.maximum_enu_m
    points = ((low[0], low[1]), (high[0], low[1]), (high[0], high[1]), (low[0], high[1]))
    trace = _polygon_prism_trace(points, max(0.0, low[2]), high[2], color, f"{label} ({volume.identifier})", 0.42, group)
    trace.showlegend = show_legend
    trace.name = label
    return trace


def _collision_figure(scenario: GeospatialScenario) -> go.Figure:
    figure = go.Figure([_ground_trace(scenario)])
    shown: set[str] = set()
    for volume in scenario.collision_volumes:
        elevated = volume.minimum_enu_m[2] > 0.01
        label = "elevated blocked volume" if elevated else "ground blocked volume"
        group = "elevated-blocked" if elevated else "ground-blocked"
        color = "#7c3aed" if elevated else "#dc2626"
        figure.add_trace(_collision_volume_trace(volume, color, label, group, group not in shown))
        shown.add(group)
    _add_safe_pads_3d(figure, scenario)
    return _scene_layout(
        figure, scenario, "heiDATA collision view: red ground volumes, purple elevated volumes",
        "Collision geometry is conservative and contains the visual geometry plus configured clearance.",
    )


def _blocked_zone_trace(overlay: OperationalOverlay) -> go.Mesh3d:
    points = tuple((point[0], point[1]) for point in overlay.geometry_enu_m)
    return _polygon_prism_trace(points, 0.0, 2.0, "#922b21", "derived blocked zone", 0.58, "blocked-zone")


def _full_scene_figure(scenario: GeospatialScenario, show_context: bool = False) -> go.Figure:
    figure = go.Figure([_ground_trace(scenario)])
    target_states = sorted({building.damage_grade for building in scenario.buildings if _is_damage_target(building)})
    for state in target_states:
        figure.add_trace(_legend_proxy_3d(f"{state} damage footprint marker", COLORS[state], f"damage:{state}"))
    map_buildings = {building.osm_id: building for building in scenario.context.buildings}
    footprint_groups: set[str] = set()
    geometry_groups: set[str] = set()
    for building in scenario.buildings:
        target = _is_damage_target(building)
        map_building = map_buildings[building.osm_id]
        hover = _building_hover(building, map_building)
        points = _footprint_polygon(scenario, building.osm_id)
        closed = points + points[:1]
        footprint_label = "earthquake target footprint" if target else "static context footprint"
        footprint_group = "target-footprints" if target else "context-footprints"
        if not target and not show_context:
            figure.add_trace(go.Scatter3d(
                x=[point[0] for point in closed], y=[point[1] for point in closed], z=[0.08] * len(closed),
                mode="lines", name=footprint_label, legendgroup=footprint_group, showlegend=False,
                line={"color": "#94a3b8", "width": 1, "dash": "dot"},
                hovertext=[hover] * len(closed), hoverinfo="text",
            ))
            figure.add_trace(_mesh_trace(
                building.visual_mesh,
                STANDING_BUILDING_COLOR,
                "standing building volume",
                hover,
                0.36,
                "standing-buildings",
                "standing-buildings" not in geometry_groups,
            ))
            geometry_groups.add("standing-buildings")
            continue
        if target:
            marker = _polygon_prism_trace(
                points, 0.0, 0.18, COLORS[building.damage_grade],
                f"{building.damage_grade} damage footprint marker", 0.24, f"damage:{building.damage_grade}",
            )
            marker.update(hovertext=hover, hoverinfo="text")
            figure.add_trace(marker)
        figure.add_trace(go.Scatter3d(
            x=[point[0] for point in closed], y=[point[1] for point in closed], z=[0.08] * len(closed),
            mode="lines", name=footprint_label, legendgroup=footprint_group,
            showlegend=footprint_group not in footprint_groups,
            line={"color": COLORS.get(building.damage_grade, "#64748b") if target else "#64748b", "width": 4 if target else 2, "dash": "solid" if target else "dot"},
            hovertext=[hover] * len(closed), hoverinfo="text",
        ))
        footprint_groups.add(footprint_group)
        geometry_label = "post earthquake building geometry" if target else "standing building volume"
        geometry_group = "target-geometry" if target else "standing-buildings"
        figure.add_trace(_mesh_trace(
            building.visual_mesh, COLORS.get(building.damage_grade, "#94a3b8") if target else "#94a3b8",
            geometry_label, hover,
            0.68 if target else 0.32, geometry_group, geometry_group not in geometry_groups,
        ))
        geometry_groups.add(geometry_group)
    rubble_shown = False
    blocked_shown = False
    for overlay in scenario.overlays:
        if overlay.kind == "rubble":
            trace = _rubble_trace(overlay)
            trace.showlegend = not rubble_shown
            figure.add_trace(trace)
            rubble_shown = True
        elif overlay.kind == "blocked_zone":
            trace = _blocked_zone_trace(overlay)
            trace.showlegend = not blocked_shown
            figure.add_trace(trace)
            blocked_shown = True
    _add_safe_pads_3d(figure, scenario)
    return _scene_layout(
        figure, scenario,
        "L’Aquila OSM anchored post earthquake environment<br><sup>Unique OSM buildings: {} | Target buildings: {} | Standing building volumes: {} | Ground rubble pieces: {} | UAV base pads: {} | Roads hidden in airborne view</sup>".format(
            len(scenario.buildings),
            sum(_is_damage_target(building) for building in scenario.buildings),
            sum(not _is_damage_target(building) for building in scenario.buildings),
            sum(overlay.kind == "rubble" for overlay in scenario.overlays),
            sum(overlay.kind == "launch_landing_pad" for overlay in scenario.overlays),
        ),
        "Each mapped building has one physical visual instance. OSM positions are source evidence; heiDATA geometry is a labelled template, not observed building damage.",
    )


def render_geospatial_storyboard(scenario: GeospatialScenario) -> dict[str, go.Figure]:
    """Create the same five view composition used by the DU environment."""

    return {
        "01_map_evidence": _source_map_figure(scenario),
        "02_building_states": _building_layout_figure(scenario),
        "03_damage_composition": _damage_figure(scenario),
        "04_collision_navigation": _collision_figure(scenario),
        "05_operational_overlays": _full_scene_figure(scenario),
    }


def write_geospatial_storyboard_html(scenario: GeospatialScenario, directory: str | Path) -> dict[str, Path]:
    """Write the five DU composition compatible interactive views."""

    output_directory = Path(directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for view, figure in render_geospatial_storyboard(scenario).items():
        path = output_directory / f"{view}.html"
        figure.write_html(str(path), include_plotlyjs=True)
        paths[view] = path
    return paths
