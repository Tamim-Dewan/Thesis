import copy
import json
import math
from pathlib import Path

import pytest

from heidata_benchmark import (
    ScenarioError,
    build_geospatial_scenario,
    build_mesh_library,
    load_osm_context,
    path_is_free,
    render_geospatial_scenario,
    render_geospatial_storyboard,
    write_geospatial_storyboard_html,
    write_scenario_html,
    write_scenario_json,
)
from heidata_benchmark.environment_render import _operational_bounds


ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "data" / "sample" / "manifest.json"
OSM_CONTEXT = ROOT / "data" / "sample" / "osm_context.v1.geojson"
SCENARIO = ROOT / "data" / "sample" / "scenario.v1.json"


def _inputs():
    return build_mesh_library(MANIFEST), load_osm_context(OSM_CONTEXT), json.loads(SCENARIO.read_text(encoding="utf-8"))


def test_mesh_library_records_checksums_axis_and_post_review():
    library, _, _ = _inputs()
    assert len({asset.asset_id for asset in library.assets}) == len(library.assets)
    assert all(len(asset.checksum_sha256) == 64 for asset in library.assets)
    assert library.asset("post:grade3_b_003_post.obj").review.status == "inspection_only"
    assert library.asset("post:grade4_b_001_post.obj").review.status == "accepted"
    assert library.asset("pre:pre_b_001_pre.obj").as_dict()["source_axis_convention"]["vertical"] == "Y"


def test_osm_context_preserves_wgs84_and_projects_a_local_map():
    _, context, _ = _inputs()
    assert context.crs == "EPSG:4326"
    assert len(context.buildings) == 18
    assert len(context.roads) == 89
    building = context.buildings[0]
    assert building.footprint_wgs84 != building.footprint_local
    assert max(abs(value) for point in building.footprint_local for value in point) < 1_000.0


def test_geospatial_scenario_is_deterministic_nonredundant_and_provenanced():
    library, context, config = _inputs()
    first = build_geospatial_scenario(config, context, library)
    second = build_geospatial_scenario(copy.deepcopy(config), context, library)
    assert first.as_dict() == second.as_dict()
    assert len(first.buildings) == 17
    assert len({building.osm_id for building in first.buildings}) == len(first.buildings)
    templates = [building for building in first.buildings if building.asset_id]
    derived_damage = [building for building in first.buildings if building.damage_geometry]
    assert len({building.source_id for building in templates}) == len(templates)
    assert all(building.placement is not None for building in templates)
    assert len(derived_damage) == 6
    assert {building.damage_grade for building in derived_damage} == {"minor", "major"}
    assert all(building.provenance == "scenario_derived" for building in derived_damage)
    assert all(item.damage_geometry.rule_version == "derived_osm_damage_geometry.v1" for item in derived_damage)
    map_buildings = {building.osm_id: building for building in context.buildings}
    assert all(
        tuple((float(x), float(y)) for x, y in item.visual_mesh.vertices[:len(map_buildings[item.osm_id].footprint_local), :2])
        == map_buildings[item.osm_id].footprint_local
        for item in derived_damage
    )
    assert first.excluded_osm_buildings[0]["osm_id"] == "way/503172320"
    assert all(overlay.provenance in {"source", "derived", "annotated"} for overlay in first.overlays)


def test_redundancy_and_unreviewed_meshes_are_rejected():
    library, context, config = _inputs()
    duplicate = copy.deepcopy(config)
    duplicate["template_bindings"].append(copy.deepcopy(duplicate["template_bindings"][0]))
    with pytest.raises(ScenarioError, match="duplicate OSM building binding"):
        build_geospatial_scenario(duplicate, context, library)

    overlapping = copy.deepcopy(config)
    overlapping["excluded_osm_buildings"] = []
    with pytest.raises(ScenarioError, match="overlapping OSM footprints"):
        build_geospatial_scenario(overlapping, context, library)

    unreviewed = copy.deepcopy(config)
    unreviewed["template_bindings"][0]["asset_id"] = "post:grade3_b_003_post.obj"
    with pytest.raises(ScenarioError, match="inspection only mesh"):
        build_geospatial_scenario(unreviewed, context, library)

    conflicting_derived = copy.deepcopy(config)
    conflicting_derived["derived_damage_bindings"].append({
        "osm_id": conflicting_derived["template_bindings"][0]["osm_id"], "damage_state": "major",
    })
    with pytest.raises(ScenarioError, match="duplicate selected state"):
        build_geospatial_scenario(conflicting_derived, context, library)

    invalid_derived = copy.deepcopy(config)
    invalid_derived["derived_damage_bindings"][0]["damage_state"] = "destruction"
    with pytest.raises(ScenarioError, match="unknown derived damage state"):
        build_geospatial_scenario(invalid_derived, context, library)


def test_navigation_blocks_collisions_and_keeps_high_airspace_route_free():
    library, context, config = _inputs()
    scenario = build_geospatial_scenario(config, context, library)
    pads = [overlay for overlay in scenario.overlays if overlay.kind == "launch_landing_pad"]
    altitude = scenario.navigation.altitude_levels_m[-1]
    high_path = tuple((pad.geometry_enu_m[0][0], pad.geometry_enu_m[0][1], altitude) for pad in pads)
    assert path_is_free(scenario.navigation, scenario.collision_volumes, high_path)
    building = next(volume for volume in scenario.collision_volumes if volume.kind == "building")
    center = tuple((low + high) / 2.0 for low, high in zip(building.minimum_enu_m, building.maximum_enu_m))
    assert not path_is_free(scenario.navigation, scenario.collision_volumes, (center, center))


def test_rubble_is_visible_3d_and_uav_pads_are_near_the_building_cluster():
    library, context, config = _inputs()
    scenario = build_geospatial_scenario(config, context, library)
    rubble = [overlay for overlay in scenario.overlays if overlay.kind == "rubble"]
    assert len(rubble) == 24
    assert all(len(overlay.geometry_enu_m) == 8 for overlay in rubble)
    assert all(any(point[2] > 0.0 for point in overlay.geometry_enu_m) for overlay in rubble)

    anchor = (
        sum(building.centroid_local[0] for building in context.buildings) / len(context.buildings),
        sum(building.centroid_local[1] for building in context.buildings) / len(context.buildings),
    )
    pads = [overlay.geometry_enu_m[0] for overlay in scenario.overlays if overlay.kind == "launch_landing_pad"]
    assert len(pads) == 2
    assert max(math.dist(point[:2], anchor) for point in pads) < 100.0


def test_main_preview_is_airborne_and_does_not_duplicate_context_buildings():
    library, context, config = _inputs()
    scenario = build_geospatial_scenario(config, context, library)
    figure = render_geospatial_scenario(scenario)
    assert "OSM anchored" in figure.layout.title.text
    assert not any("road" in str(trace.name).lower() for trace in figure.data)
    assert sum(trace.name == "post earthquake building geometry" for trace in figure.data) == 10
    standing = [trace for trace in figure.data if trace.name == "standing building volume" and trace.type == "mesh3d"]
    assert len(standing) == 7
    assert "Standing building volumes: 7" in figure.layout.title.text
    assert any(trace.name == "ground rubble" and len(trace.x) == 8 for trace in figure.data)


def test_export_and_renderer_make_the_map_template_boundary_explicit(tmp_path):
    library, context, config = _inputs()
    scenario = build_geospatial_scenario(config, context, library)
    figure = render_geospatial_scenario(scenario)
    assert figure.layout.scene.xaxis.title.text == "local east, metres"
    assert "heiDATA geometry is a labelled template" in figure.layout.annotations[0].text
    json_path = tmp_path / "scenario.json"
    html_path = tmp_path / "scenario.html"
    write_scenario_json(scenario, json_path)
    write_scenario_html(scenario, html_path)
    exported = json.loads(json_path.read_text(encoding="utf-8"))
    assert exported["kind"] == "controlled_geospatial_benchmark_composite"
    assert exported["geo_context"]["crs"] == "EPSG:4326"
    exported_damage = [building for building in exported["buildings"] if building["damage_geometry"]]
    assert len(exported_damage) == 6
    assert all(item["damage_geometry"]["provenance"] == "scenario_derived_not_observed" for item in exported_damage)
    assert "OSM anchored" in html_path.read_text(encoding="utf-8")


def test_storyboard_html_views_follow_the_du_five_composition_contract(tmp_path):
    library, context, config = _inputs()
    scenario = build_geospatial_scenario(config, context, library)
    figures = render_geospatial_storyboard(scenario)
    assert set(figures) == {
        "01_map_evidence", "02_building_states", "03_damage_composition",
        "04_collision_navigation", "05_operational_overlays",
    }
    expected_map_range_x = [context.world_bounds_2d[0] - 12.0, context.world_bounds_2d[2] + 12.0]
    expected_map_range_y = [context.world_bounds_2d[1] - 12.0, context.world_bounds_2d[3] + 12.0]
    operational_bounds = _operational_bounds(scenario)
    expected_range_x = [operational_bounds[0], operational_bounds[2]]
    expected_range_y = [operational_bounds[1], operational_bounds[3]]
    map_figure = figures["01_map_evidence"]
    assert {trace.type for trace in map_figure.data} == {"scatter"}
    assert sum("building" in trace.name or "footprint" in trace.name for trace in map_figure.data) == len(context.buildings)
    assert list(map_figure.layout.xaxis.range) == expected_map_range_x
    assert list(map_figure.layout.yaxis.range) == expected_map_range_y
    assert map_figure.layout.xaxis.scaleanchor == "y"
    assert {trace.name for trace in map_figure.data} >= {
        "earthquake target building", "static context building",
        "excluded overlapping OSM source footprint", "safe UAV pad",
    }

    three_dimensional = {key: figures[key] for key in tuple(figures)[1:]}
    for figure in three_dimensional.values():
        assert {trace.type for trace in figure.data} >= {"mesh3d", "scatter3d"}
        assert list(figure.layout.scene.xaxis.range) == expected_range_x
        assert list(figure.layout.scene.yaxis.range) == expected_range_y
        assert figure.layout.scene.aspectmode == "data"
        assert not any("road" in str(trace.name).lower() for trace in figure.data)

    layout = figures["02_building_states"]
    target_count = sum(trace.name.startswith("earthquake target building (") for trace in layout.data)
    context_count = sum(trace.name.startswith("static context building (") for trace in layout.data)
    assert target_count == 10
    assert context_count == 7
    assert "every nonredundant scenario footprint" in layout.layout.title.text

    damage = figures["03_damage_composition"]
    assert "standing volumes and damage targets" in damage.layout.title.text
    standing = [trace for trace in damage.data if trace.name == "standing building volume" and trace.type == "mesh3d"]
    assert len(standing) == 7
    assert any(trace.name == "heiDATA damage template" for trace in damage.data)
    assert any(trace.name == "scenario derived damage geometry" for trace in damage.data)
    assert any(trace.name == "ground rubble" for trace in damage.data)

    collision = figures["04_collision_navigation"]
    assert {trace.name for trace in collision.data} >= {"ground blocked volume", "safe UAV pad"}
    assert len([trace for trace in collision.data if trace.name == "ground blocked volume"]) == len(scenario.collision_volumes)

    full_scene = figures["05_operational_overlays"]
    assert full_scene.layout.title.text.startswith("L’Aquila OSM anchored post earthquake environment")
    assert any(trace.name == "derived blocked zone" for trace in full_scene.data)
    assert any(trace.name == "safe UAV pad" for trace in full_scene.data)
    paths = write_geospatial_storyboard_html(scenario, tmp_path)
    assert set(paths) == set(figures)
    assert all(path.exists() and "Plotly.newPlot" in path.read_text(encoding="utf-8") for path in paths.values())
