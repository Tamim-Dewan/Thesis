from pathlib import Path

import numpy as np

from heidata_benchmark import (
    load_source_layout,
    load_source_pair,
    parse_obj,
    render_source_layout,
    source_y_up_to_plot_z_up,
)


ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "data" / "sample" / "manifest.json"
RAW = ROOT / "data" / "sample" / "raw"


def test_source_axis_mapping_uses_y_as_vertical_without_translation():
    mesh = parse_obj(RAW / "pre_b_001_pre.obj")
    visual = source_y_up_to_plot_z_up(mesh)
    assert np.array_equal(visual.vertices[:, 0], mesh.vertices[:, 0])
    assert np.array_equal(visual.vertices[:, 1], mesh.vertices[:, 2])
    assert np.array_equal(visual.vertices[:, 2], mesh.vertices[:, 1])


def test_source_pair_preserves_raw_pre_and_post_coordinates():
    pair = load_source_pair(MANIFEST, "extreme_b001")
    raw_pre = parse_obj(RAW / "pre_b_001_pre.obj")
    raw_post = parse_obj(RAW / "grade4_b_001_post.obj")
    assert np.array_equal(pair.pre_mesh.vertices, raw_pre.vertices)
    assert np.array_equal(pair.post_mesh.vertices, raw_post.vertices)
    assert pair.report()["artificial_translation_applied"] is False
    assert pair.report()["artificial_layout_applied"] is False


def test_source_layout_retains_non_grid_source_positions():
    layout = load_source_layout(MANIFEST)
    minimum_z = [mesh.minimum[2] for _, mesh in layout.meshes]
    assert len(layout.meshes) == 8
    assert len(set(minimum_z)) > 4


def test_source_layout_uses_the_explicit_y_up_display_axis():
    layout = load_source_layout(MANIFEST)
    figure = render_source_layout(layout)
    scene = figure.layout.scene
    assert scene.xaxis.title.text == "source X, metres"
    assert scene.yaxis.title.text == "source Z, metres"
    assert scene.zaxis.title.text == "source Y, vertical, metres"
    first_trace = figure.data[0]
    raw_first_mesh = layout.meshes[0][1]
    assert np.array_equal(np.asarray(first_trace.x), raw_first_mesh.vertices[:, 0])
    assert np.array_equal(np.asarray(first_trace.y), raw_first_mesh.vertices[:, 2])
    assert np.array_equal(np.asarray(first_trace.z), raw_first_mesh.vertices[:, 1])
