import json
from pathlib import Path

import numpy as np

from heidata_benchmark import build_sample_scene, collision_boxes, is_free, parse_obj


ROOT = Path(__file__).parents[1]
RAW = ROOT / "data" / "sample" / "raw"


def test_obj_parser_reads_real_heidata_geometry():
    mesh = parse_obj(RAW / "b_001_pre.obj")
    assert len(mesh.vertices) > 100
    assert len(mesh.faces) > 100
    assert np.all(mesh.extent > 0)


def test_sample_scene_has_all_damage_grades_and_provenance():
    scene = build_sample_scene(RAW, seed=17)
    assert {building.damage_grade for building in scene.buildings} == {
        "no_damage", "heavy", "extreme", "destruction"
    }
    assert scene.source == "doi:10.11588/DATA/D3WZID"
    assert scene.metadata["manifest_version"] == "heidata.sample.v1"
    assert scene.world_maximum[2] > scene.world_minimum[2]


def test_sample_scene_is_reproducible_and_seed_changes_road_state():
    first = build_sample_scene(RAW, seed=17)
    second = build_sample_scene(RAW, seed=17)
    different = build_sample_scene(RAW, seed=18)
    assert first.as_dict() == second.as_dict()
    assert [road.status for road in first.roads] != [road.status for road in different.roads]


def test_heavy_default_is_explicitly_derived_from_source_geometry():
    scene = build_sample_scene(RAW, seed=17)
    heavy = next(item for item in scene.buildings if item.damage_grade == "heavy")
    assert heavy.derived is True
    assert "pre_b_003_pre.obj" in heavy.source_files
    assert len(heavy.parts) == 5


def test_collision_geometry_is_conservative_and_candidate_points_are_free():
    scene = build_sample_scene(RAW, seed=17)
    boxes = collision_boxes(scene)
    assert len(boxes) >= len(scene.buildings)
    assert all(box.minimum[0] <= box.maximum[0] for box in boxes)
    assert all(is_free(scene, point) for point in scene.candidate_sites)


def test_raw_grade3_geometry_exposes_source_quality_warning():
    scene = build_sample_scene(RAW, seed=17, include_raw_heavy=True)
    heavy = next(item for item in scene.buildings if item.damage_grade == "heavy")
    assert heavy.derived is False
    assert heavy.quality_flags
    assert any("large" in flag or "three times" in flag for flag in heavy.quality_flags)


def test_manifest_is_valid_json():
    manifest = ROOT / "data" / "sample" / "manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(data["buildings"]) == 10
