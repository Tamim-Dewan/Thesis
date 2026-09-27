import json
import zipfile
from pathlib import Path

from heidata_benchmark.tools.download_full_dataset import published_files
from heidata_benchmark.tools.inventory_full_dataset import inventory


def test_published_files_reads_all_dataset_categories_and_checksums():
    metadata = {
        "data": {
            "latestVersion": {
                "files": [
                    {
                        "categories": ["Data"],
                        "dataFile": {
                            "id": 10,
                            "filename": "models.zip",
                            "filesize": 12,
                            "md5": "abc",
                            "contentType": "application/zip",
                        },
                    },
                    {
                        "categories": ["Code"],
                        "dataFile": {
                            "id": 11,
                            "filename": "script.py",
                            "filesize": 4,
                            "md5": "def",
                            "contentType": "text/x-python",
                        },
                    },
                ]
            }
        }
    }

    records = published_files(metadata)

    assert [record["filename"] for record in records] == ["script.py", "models.zip"]
    assert records[0]["category"] == "code"
    assert records[1]["category"] == "data"
    assert records[1]["url"].endswith("/10")


def test_inventory_extracts_obj_and_records_provenance(tmp_path):
    root = tmp_path / "dataset"
    archives = root / "archives"
    archives.mkdir(parents=True)
    archive = archives / "building_models_pre_event_generic.zip"
    obj = "# source sample\nv 0 0 0\nv 1 0 0\nv 0 2 0\nf 1 2 3\n"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("pre_b_001_pre.obj", obj)

    result = inventory(root, extract=True)

    assert result["summary"]["asset_count"] == 1
    asset = result["assets"][0]
    assert asset["building_id"] == "b_001"
    assert asset["damage_grade"] == "no_damage"
    assert asset["quality_status"] == "accepted"
    assert asset["source_axis"]["y"] == "vertical"
    assert json.loads((root / "asset_inventory.json").read_text()) == result


def test_inventory_marks_large_coordinates_for_review(tmp_path):
    root = tmp_path / "dataset"
    archive_dir = root / "extracted" / "building_models_post_event_damage_grade3_generic"
    archive_dir.mkdir(parents=True)
    (archive_dir / "grade3_b_003_post.obj").write_text(
        "v 0 0 0\nv 3000 0 0\nv 0 1 0\nf 1 2 3\n",
        encoding="utf-8",
    )

    result = inventory(root)

    asset = result["assets"][0]
    assert asset["damage_grade"] == "heavy"
    assert asset["quality_status"] == "inspection_only"
    assert "large_coordinate_extent_requires_review" in asset["quality_flags"]
