import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from pgbm_sim import (  # noqa: E402
    SceneConfig, SceneTemplateError, TaskConfig, build_scenario, generate_disaster_scene, is_valid_candidate_site,
    load_scene_preset, plot_building_layout, plot_collision_view, plot_damage_view, plot_disaster_scene, plot_map_view,
)
from pgbm_sim.disaster_scene import _partition_polygon, _point_in_polygon  # noqa: E402


def test_synthetic_scene_is_complete_reproducible_and_seed_sensitive():
    config = SceneConfig(mode="synthetic", severity="moderate", seed=7)
    first = generate_disaster_scene(config)
    second = generate_disaster_scene(config)
    different = generate_disaster_scene(SceneConfig(mode="synthetic", severity="moderate", seed=8))
    assert first.as_dict() == second.as_dict()
    assert first.as_dict() != different.as_dict()
    assert len(first.uav_initial_positions) == 3
    assert all(position == first.environment.base.position for position in first.uav_initial_positions)
    assert len(first.candidate_sites) == 18
    assert all(is_valid_candidate_site(first, site) for site in first.candidate_sites)


@pytest.mark.parametrize("seed", range(101, 111))
def test_synthetic_heavy_experiment_seed_range_has_valid_layout(seed):
    scene = generate_disaster_scene(SceneConfig(mode="synthetic", severity="moderate", seed=seed))
    assert len(scene.structures) == 8
    assert len(scene.candidate_sites) == 18
    assert all(is_valid_candidate_site(scene, site) for site in scene.candidate_sites)


def test_du_scene_uses_bundled_true_scale_osm_template_with_provenance():
    scene = generate_disaster_scene(SceneConfig(mode="du_outdoor", severity="moderate", seed=11))
    assert scene.environment.world.minimum == (-44, -65, 0)
    assert scene.environment.world.maximum == (281, 259, 60)
    assert any("Mokarram" in structure.identifier or "mokarram" in structure.identifier for structure in scene.structures)
    assert any("CSE" in structure.identifier or "cse" in structure.identifier for structure in scene.structures)
    assert scene.provenance[0].licence == "ODbL 1.0"
    assert scene.generation_metadata["template_version"] == "osm-2026-09-24.v4"
    assert len(scene.structures) == 24
    assert sum(item.scene_role == "target" for item in scene.structures) == 8
    assert sum(item.scene_role == "context" for item in scene.structures) == 16
    for structure in scene.structures:
        assert structure.minimum[0] >= -44 and structure.minimum[1] >= -65
        assert structure.minimum[0] + structure.width <= 281
        assert structure.minimum[1] + structure.depth <= 259


# Covers AC-2, AC-3, AC-4, AC-6, AC-11, and AC-12.
def test_laquila_informed_scene_uses_the_exact_source_footprints():
    config = SceneConfig(mode="laquila_informed", severity="moderate", seed=20260925)
    first = generate_disaster_scene(config)
    second = generate_disaster_scene(config)
    different = generate_disaster_scene(SceneConfig(mode="laquila_informed", severity="moderate", seed=20260926))

    assert first.as_dict() == second.as_dict()
    assert [structure.as_dict() for structure in first.structures] == [structure.as_dict() for structure in different.structures]
    assert len(first.structures) == 17
    assert len({structure.source_ref for structure in first.structures}) == 17
    assert all(structure.source_name for structure in first.structures)
    assert all(structure.visual_provenance for structure in first.structures)
    assert not first.roads
    assert first.generation_metadata["layout_version"] == "laquila_georeferenced_layout.v1"
    assert first.generation_metadata["source_building_count"] == 18
    assert first.generation_metadata["active_building_count"] == 17
    assert "way/500792516" in first.generation_metadata["active_osm_ids"]
    assert "way/501746087" in first.generation_metadata["active_osm_ids"]
    assert "way/496729871" in first.generation_metadata["active_osm_ids"]
    assert any(item["osm_id"] == "way/503172320" for item in first.generation_metadata["excluded_osm_buildings"])


# Covers AC-7, AC-9, and AC-10.
def test_laquila_informed_scene_is_task_compatible_and_source_named_in_preview():
    scenario = build_scenario(
        SceneConfig(mode="laquila_informed", severity="moderate", seed=20260925),
        TaskConfig(task_count=6, seed=20260926),
    )
    figure = plot_damage_view(scenario.scene)

    assert len(scenario.tasks) == 6
    assert all(is_valid_candidate_site(scenario.scene, site) for site in scenario.scene.candidate_sites)
    assert "L’AQUILA EXACT GEOREFERENCED SOURCE" in figure.layout.title.text
    assert any("Source building:" in str(trace.hovertext) for trace in figure.data if trace.type == "mesh3d")
    assert any(trace.name == "major collapse rubble mesh" for trace in figure.data)
    assert any(trace.name == "destroyed building rubble mesh" for trace in figure.data)


def test_damage_preset_rules_are_monotonic():
    light, moderate, severe = (load_scene_preset(value) for value in ("light", "moderate", "severe"))
    for key in ("major", "destroyed"):
        assert light.damage_proportions[key] <= moderate.damage_proportions[key] <= severe.damage_proportions[key]
    for key in ("road_block_probability", "rubble_probability", "broken_floor_probability", "elevated_debris_probability"):
        assert getattr(light, key) <= getattr(moderate, key) <= getattr(severe, key)


def test_missing_real_building_asset_is_an_explicit_honest_error():
    with pytest.raises(SceneTemplateError, match="unavailable"):
        generate_disaster_scene(SceneConfig(mode="real_building"))


def test_disaster_plot_is_interactive_figure():
    scene = generate_disaster_scene(SceneConfig(mode="synthetic", seed=9))
    figure = plot_disaster_scene(scene)
    assert figure.__class__.__name__ == "Figure"
    assert any(trace.name == "base" for trace in figure.data)
    assert any("footprint" in str(trace.name) for trace in figure.data)
    assert not any("site" in str(trace.name) for trace in figure.data)


def test_task_hover_displays_survivor_metadata_and_assignment():
    scenario = build_scenario(SceneConfig(mode="synthetic", severity="moderate", seed=9), TaskConfig(task_count=2, seed=10))
    figure = plot_disaster_scene(
        scenario.scene,
        tasks=scenario.tasks,
        task_assignees={"task_1": "uav_1"},
    )
    task_trace = next(trace for trace in figure.data if trace.name == "survivor tasks")
    assert "Severity:" in task_trace.hovertext[0]
    assert "Drop off waypoint:" in task_trace.hovertext[0]
    assert "Site:" not in task_trace.hovertext[0]
    assert "Demand:" in task_trace.hovertext[0]
    assert "Confidence:" not in task_trace.hovertext[0]
    assert "Deadline:" not in task_trace.hovertext[0]
    assert "Assigned UAV: uav_1" in task_trace.hovertext[0]
    assert not any("candidate site" in str(trace.name) for trace in figure.data)


def test_operational_plot_groups_damage_objects_and_can_show_diagnostics():
    scene = generate_disaster_scene(SceneConfig(mode="du_outdoor", severity="severe", seed=20260924))
    clean = plot_disaster_scene(scene)
    diagnostic = plot_disaster_scene(scene, show_context=True, show_candidate_sites=True)

    assert not any("context" in str(trace.name) for trace in clean.data)
    assert not any("candidate site" in str(trace.name) for trace in clean.data)
    assert any(trace.name == "major damage footprint" for trace in clean.data)
    assert any(
        trace.name in {"ground rubble", "major collapse rubble mesh", "destroyed building rubble mesh"}
        for trace in clean.data
    )
    assert any(trace.name == "elevation guide" for trace in clean.data)
    assert any("static context" in str(trace.name) for trace in diagnostic.data)
    assert any("candidate sites" in str(trace.name) for trace in diagnostic.data)


def test_damage_view_explains_layers_and_supports_elevation_guide_toggle():
    scene = generate_disaster_scene(SceneConfig(mode="du_outdoor", severity="moderate", seed=20260924))
    visible = plot_damage_view(scene)
    hidden = plot_damage_view(scene, show_elevation_guides=False)

    assert "Target buildings:" in visible.layout.title.text
    assert "Static context:" in visible.layout.title.text
    assert "Preset: moderate" in visible.layout.title.text
    assert any("damage footprint marker" in str(trace.name) for trace in visible.data)
    assert any(trace.name == "elevation guide (helper)" for trace in visible.data)
    assert not any(trace.name == "elevation guide (helper)" for trace in hidden.data)
    assert not any(trace.name == "elevation guide" for trace in hidden.data)
    assert not any(str(trace.name).startswith("post-earthquake ") for trace in visible.data)
    obstacle_traces = [
        trace for trace in visible.data
        if trace.type == "mesh3d"
        and str(trace.name) in {"standing building volume", "ground rubble", "broken floor", "elevated debris"}
    ]
    assert obstacle_traces
    assert any("Parent building:" in str(trace.hovertext) for trace in obstacle_traces)


@pytest.mark.parametrize("mode", ["synthetic", "du_outdoor"])
def test_environment_preview_shows_tasks_and_vertical_dropoffs_without_planner_output(mode):
    scenario = build_scenario(SceneConfig(mode=mode, severity="severe", seed=20260924), TaskConfig(task_count=6, seed=20260925))
    figure = plot_disaster_scene(scenario.scene, tasks=scenario.tasks)
    names = [str(trace.name) for trace in figure.data]

    assert "UAV drop off waypoints" in names
    assert "vertical drop off path" in names
    assert not any("route" in name for name in names)
    assert "UAV assignment: not included" in figure.layout.title.text
    dropoff_trace = next(trace for trace in figure.data if trace.name == "UAV drop off waypoints")
    assert all("UAV assignment: not planned" in hover for hover in dropoff_trace.hovertext)
    task_trace = next(trace for trace in figure.data if trace.name == "survivor tasks")
    assert all("Vertical drop off separation:" in hover for hover in task_trace.hovertext)


def test_clean_visual_views_keep_layout_damage_and_collision_separate():
    scene = generate_disaster_scene(SceneConfig(mode="du_outdoor", severity="severe", seed=20260924))
    layout, damage, collision = plot_building_layout(scene), plot_damage_view(scene), plot_collision_view(scene)
    assert any("static context footprint" in str(trace.name) for trace in layout.data)
    assert all(trace.type == "scatter" for trace in layout.data)
    assert not any(str(trace.name) == "base" for trace in layout.data)
    assert not any("survivor" in str(trace.name) for trace in layout.data)
    assert any(
        str(trace.name) in {"standing building volume", "ground rubble", "broken floor", "elevated debris"}
        for trace in damage.data
    )
    assert any("destroyed damage footprint marker" in str(trace.name) for trace in damage.data)
    blocked_volumes = [trace for trace in collision.data if trace.type == "mesh3d" and "blocked volume" in str(trace.name)]
    assert len(blocked_volumes) == len(scene.environment.obstacles)
    assert {trace.color for trace in blocked_volumes} <= {"#dc2626", "#7c3aed"}


def test_map_view_includes_every_structure_without_webgl_geometry():
    scene = generate_disaster_scene(SceneConfig(mode="du_outdoor", severity="severe", seed=20260924))

    figure = plot_map_view(scene)

    footprints = [trace for trace in figure.data if str(trace.name) in {"mapped building footprint", "static context footprint"}]
    assert len(footprints) == len(scene.structures)
    assert all(trace.type == "scatter" for trace in footprints)
    assert not any(str(trace.name) == "base" for trace in figure.data)
    assert all("Building:" in trace.hovertext[0] for trace in footprints)
    assert any(annotation.text == "<b>N</b>" for annotation in figure.layout.annotations)


@pytest.mark.parametrize("mode", ["synthetic", "du_outdoor"])
def test_scene_preserves_polygon_geometry_and_unique_candidate_positions(mode):
    scene = generate_disaster_scene(SceneConfig(mode=mode, severity="severe", seed=20260924))
    assert all(structure.footprint for structure in scene.structures)
    assert len({site.position for site in scene.candidate_sites}) == len(scene.candidate_sites)
    assert all(is_valid_candidate_site(scene, site) for site in scene.candidate_sites)
    polygon_obstacles = [obstacle for obstacle in scene.environment.obstacles if obstacle.footprint]
    assert polygon_obstacles
    assert any(obstacle.kind == "ground_rubble" for obstacle in polygon_obstacles)


@pytest.mark.parametrize("mode", ["synthetic", "du_outdoor"])
def test_airborne_uav_scenes_exclude_road_geometry_and_road_blocks(mode):
    scene = generate_disaster_scene(SceneConfig(mode=mode, severity="severe", seed=20260924))

    assert not scene.roads
    assert all(obstacle.kind != "road_block" and obstacle.road_segment_id is None for obstacle in scene.environment.obstacles)


@pytest.mark.parametrize("mode", ["synthetic", "du_outdoor"])
def test_rubble_and_elevated_debris_are_irregular_uneven_visual_geometry(mode):
    scene = generate_disaster_scene(SceneConfig(mode=mode, severity="severe", seed=20260924))
    fragments = [
        obstacle for obstacle in scene.environment.obstacles
        if obstacle.kind in {"ground_rubble", "elevated_debris"}
    ]

    assert fragments
    assert any(obstacle.kind == "elevated_debris" for obstacle in fragments)
    for obstacle in fragments:
        assert obstacle.footprint is not None and 5 <= len(obstacle.footprint) <= 8
        assert len(obstacle.visual_top_profile) == len(obstacle.footprint)
        assert min(obstacle.visual_top_profile) < max(obstacle.visual_top_profile) == 1.0


def test_destroyed_structures_receive_denser_and_taller_rubble_clusters():
    scene = generate_disaster_scene(SceneConfig(mode="du_outdoor", severity="severe", seed=20260924))
    structures = {structure.identifier: structure for structure in scene.structures}
    rubble_by_parent = {}
    for obstacle in scene.environment.obstacles:
        if obstacle.kind == "ground_rubble":
            rubble_by_parent.setdefault(obstacle.parent_structure_id, []).append(obstacle)

    destroyed = [
        rubble_by_parent.get(identifier, [])
        for identifier, structure in structures.items()
        if structure.damage_state == "destroyed"
    ]
    major = [
        rubble_by_parent.get(identifier, [])
        for identifier, structure in structures.items()
        if structure.damage_state == "major"
    ]
    assert destroyed and major
    assert all(group for group in destroyed)
    assert all(group for group in major)
    assert sum(map(len, destroyed)) >= sum(map(len, major))
    assert max(obstacle.height for group in destroyed for obstacle in group) > 2.0


@pytest.mark.parametrize("mode", ["synthetic", "du_outdoor"])
def test_major_rubble_stays_inside_the_collapsed_section(mode):
    scene = generate_disaster_scene(SceneConfig(mode=mode, severity="severe", seed=20260924))
    for structure in (item for item in scene.structures if item.damage_state == "major"):
        _, collapsed = _partition_polygon(structure.footprint)
        rubble = [
            obstacle for obstacle in scene.environment.obstacles
            if obstacle.parent_structure_id == structure.identifier and obstacle.kind == "ground_rubble"
        ]
        assert rubble
        assert all(
            _point_in_polygon(point[0], point[1], collapsed)
            for obstacle in rubble
            for point in obstacle.footprint
        )


def test_rubble_preview_uses_varied_earthy_mesh_materials():
    scene = generate_disaster_scene(SceneConfig(mode="synthetic", severity="severe", seed=20260924))
    figure = plot_damage_view(scene)
    rubble_traces = [
        trace for trace in figure.data
        if trace.type == "mesh3d" and "rubble" in str(trace.name)
    ]
    assert len(rubble_traces) >= 2
    assert len({trace.color for trace in rubble_traces}) >= 2
    assert all(float(trace.opacity) >= 0.84 for trace in rubble_traces)


@pytest.mark.parametrize("mode", ["synthetic", "du_outdoor"])
def test_major_and_destroyed_structures_use_named_damage_mesh_templates(mode):
    scene = generate_disaster_scene(SceneConfig(mode=mode, severity="severe", seed=20260924))
    metadata = scene.generation_metadata

    assert metadata["damage_mesh_template_version"] == "synthetic_damage_mesh.v1"
    assert metadata["damage_mesh_templates"]["major"]["id"] == "major_partial_collapse.v1"
    assert metadata["damage_mesh_templates"]["destroyed"]["id"] == "destroyed_rubble_cluster.v1"

    target_states = {structure.identifier: structure.damage_state for structure in scene.structures}
    major_meshes = [
        obstacle for obstacle in scene.environment.obstacles
        if target_states.get(obstacle.parent_structure_id) == "major"
    ]
    destroyed_meshes = [
        obstacle for obstacle in scene.environment.obstacles
        if target_states.get(obstacle.parent_structure_id) == "destroyed"
    ]
    assert major_meshes and destroyed_meshes
    assert all(obstacle.damage_template_id == "major_partial_collapse.v1" for obstacle in major_meshes)
    assert all(obstacle.damage_template_id == "destroyed_rubble_cluster.v1" for obstacle in destroyed_meshes)
    assert any(
        obstacle.kind == "building"
        and obstacle.visual_top_profile
        and min(obstacle.visual_top_profile) < max(obstacle.visual_top_profile)
        for obstacle in major_meshes
    )

    figure = plot_damage_view(scene)
    names = {str(trace.name) for trace in figure.data}
    assert "major damaged building mesh" in names
    assert "destroyed building rubble mesh" in names
    assert any(
        trace.type == "mesh3d" and "Damage mesh template:" in str(trace.hovertext)
        for trace in figure.data
    )


def test_major_damage_has_a_standing_polygon_and_a_collapsed_section():
    scene = generate_disaster_scene(SceneConfig(mode="du_outdoor", severity="severe", seed=20260924))
    major = [structure for structure in scene.structures if structure.damage_state == "major"]
    assert major
    for structure in major:
        related = [obstacle for obstacle in scene.environment.obstacles if obstacle.parent_structure_id == structure.identifier]
        assert any(obstacle.kind == "building" for obstacle in related)
