import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from heidata_benchmark.full_dataset import build_full_manifest, build_full_mesh_library


OBJ = "v 0 0 0\nv 1 0 0\nv 0 0 1\nv 0 1 0\nf 1 2 3\nf 1 4 2\nf 2 4 3\nf 3 4 1\n"


def _full_root(tmp_path: Path) -> Path:
    root = tmp_path / "dataset"
    (root / "archives").mkdir(parents=True)
    names = {
        "building_models_pre_event_generic.zip": "pre_b_001_pre.obj",
        "building_models_post_event_damage_grade4_generic.zip": "b_001_post.obj",
    }
    for archive_name, member in names.items():
        with ZipFile(root / "archives" / archive_name, "w", ZIP_DEFLATED) as archive:
            archive.writestr(member, OBJ)
    return root


def test_full_manifest_indexes_archive_members(tmp_path):
    manifest = build_full_manifest(_full_root(tmp_path))
    assert manifest["schema_version"] == "heidata.full_manifest.v1"
    assert manifest["asset_count"] == 2
    assert {item["source_id"] for item in manifest["assets"]} == {"b_001"}


def test_full_mesh_library_reads_only_required_zip_members(tmp_path):
    root = _full_root(tmp_path)
    manifest_path = root / "full_manifest.v1.json"
    manifest_path.write_text(json.dumps(build_full_manifest(root)), encoding="utf-8")
    library = build_full_mesh_library(manifest_path, {"post:grade4_b_001_post.obj"})
    assert len(library.assets) == 1
    assert library.assets[0].source_id == "b_001"
    assert library.assets[0].path.endswith("!b_001_post.obj")


def test_obj_parser_preserves_face_material_names(tmp_path):
    source = tmp_path / "material.obj"
    source.write_text(
        "v 0 0 0\nv 1 0 0\nv 0 0 1\nv 0 1 0\n"
        "usemtl plaster\nf 1 2 3\nusemtl glass\nf 1 4 2\n"
        "f 2 4 3\nf 3 4 1\n",
        encoding="utf-8",
    )
    from heidata_benchmark.mesh import parse_obj

    mesh = parse_obj(source)
    assert mesh.face_materials == ("plaster", "glass", "glass", "glass")
