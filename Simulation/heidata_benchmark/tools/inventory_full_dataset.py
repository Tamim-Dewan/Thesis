"""Extract and inventory the complete heiDATA building model archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


DEFAULT_ROOT = Path.home() / "Datasets" / "heiDATA_D3WZID"
BUILDING_PATTERN = re.compile(r"(?:pre_|grade\d_)?(b_\d+)", re.IGNORECASE)
GRADE_BY_ARCHIVE = {
    "pre_event": "no_damage",
    "grade3": "heavy",
    "grade4": "extreme",
    "grade5": "destruction",
}


def damage_grade_for_archive(archive_name: str) -> str:
    for marker, grade in GRADE_BY_ARCHIVE.items():
        if marker in archive_name:
            return grade
    return "unknown"


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _safe_member_path(destination: Path, member: zipfile.ZipInfo) -> Path:
    target = (destination / member.filename).resolve()
    if target != destination.resolve() and destination.resolve() not in target.parents:
        raise RuntimeError("archive member escapes extraction directory: {}".format(member.filename))
    return target


def extract_archives(root: Path, archive_names: Optional[Iterable[str]] = None) -> List[Path]:
    archives_dir = root / "archives"
    extraction_root = root / "extracted"
    extraction_root.mkdir(parents=True, exist_ok=True)
    selected = set(archive_names or ())
    extracted_dirs = []
    for archive in sorted(archives_dir.glob("*.zip")):
        if selected and archive.name not in selected:
            continue
        destination = extraction_root / archive.stem
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                target = _safe_member_path(destination, member)
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() and target.stat().st_size == member.file_size:
                    continue
                with bundle.open(member) as source, target.open("wb") as sink:
                    while True:
                        block = source.read(8 * 1024 * 1024)
                        if not block:
                            break
                        sink.write(block)
        extracted_dirs.append(destination)
    return extracted_dirs


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(8 * 1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def inspect_obj(path: Path, archive_name: str) -> dict:
    vertex_count = 0
    face_count = 0
    parse_errors: List[str] = []
    minimum = [float("inf")] * 3
    maximum = [float("-inf")] * 3
    max_abs_coordinate = 0.0

    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, line in enumerate(handle, start=1):
                if line.startswith("v "):
                    values = line.split()
                    if len(values) < 4:
                        parse_errors.append("vertex_without_three_coordinates:{}".format(line_number))
                        continue
                    try:
                        coordinates = [float(value) for value in values[1:4]]
                    except ValueError:
                        parse_errors.append("invalid_vertex:{}".format(line_number))
                        continue
                    vertex_count += 1
                    for index, coordinate in enumerate(coordinates):
                        minimum[index] = min(minimum[index], coordinate)
                        maximum[index] = max(maximum[index], coordinate)
                        max_abs_coordinate = max(max_abs_coordinate, abs(coordinate))
                elif line.startswith("f "):
                    if len(line.split()) < 4:
                        parse_errors.append("face_without_three_vertices:{}".format(line_number))
                    else:
                        face_count += 1
    except OSError as error:
        parse_errors.append("read_error:{}".format(error))

    if vertex_count:
        extent = [maximum[index] - minimum[index] for index in range(3)]
        bounds = {"min": minimum, "max": maximum, "extent": extent}
    else:
        extent = [0.0, 0.0, 0.0]
        bounds = {"min": None, "max": None, "extent": extent}

    flags = list(parse_errors)
    if vertex_count == 0:
        flags.append("no_vertices")
    if face_count == 0:
        flags.append("no_faces")
    if max_abs_coordinate > 1000.0 or max(extent) > 2000.0:
        flags.append("large_coordinate_extent_requires_review")

    status = "rejected" if any(flag in flags for flag in ("no_vertices", "no_faces")) else "accepted"
    if "large_coordinate_extent_requires_review" in flags and status == "accepted":
        status = "inspection_only"

    match = BUILDING_PATTERN.search(path.stem)
    return {
        "asset_id": "{}:{}".format(archive_name, path.relative_to(path.parents[2]).as_posix()),
        "archive": archive_name,
        "relative_path": path.relative_to(path.parents[2]).as_posix(),
        "filename": path.name,
        "building_id": match.group(1) if match else None,
        "damage_grade": damage_grade_for_archive(archive_name),
        "source_axis": {"x": "x", "y": "vertical", "z": "z"},
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "vertex_count": vertex_count,
        "face_count": face_count,
        "bounds": bounds,
        "max_abs_coordinate": max_abs_coordinate,
        "quality_status": status,
        "quality_flags": flags,
    }


def inventory(root: Path, extract: bool = False, archive_names: Optional[Iterable[str]] = None) -> dict:
    if extract:
        extract_archives(root, archive_names=archive_names)
    extracted_root = root / "extracted"
    records = []
    for archive_dir in sorted(path for path in extracted_root.iterdir() if path.is_dir()) if extracted_root.exists() else []:
        archive_name = archive_dir.name
        for obj_path in sorted(archive_dir.rglob("*.obj")):
            records.append(inspect_obj(obj_path, archive_name))

    quality_counts = Counter(record["quality_status"] for record in records)
    grade_counts = Counter(record["damage_grade"] for record in records)
    inventory = {
        "schema_version": "heidata.full_inventory.v1",
        "dataset_doi": "doi:10.11588/DATA/D3WZID",
        "root": str(root),
        "source_axis": {"x": "x", "y": "vertical", "z": "z"},
        "quality_policy": {
            "accepted": "OBJ has vertices and faces and no automatic geometry warning.",
            "inspection_only": "OBJ is parseable but has a large coordinate extent and needs review.",
            "rejected": "OBJ has no usable vertices or faces, or could not be read.",
            "large_extent_threshold": "max absolute coordinate > 1000 m or axis extent > 2000 m",
        },
        "summary": {
            "asset_count": len(records),
            "quality_status": dict(sorted(quality_counts.items())),
            "damage_grade": dict(sorted(grade_counts.items())),
        },
        "assets": records,
    }
    _write_json(root / "asset_inventory.json", inventory)
    return inventory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--extract", action="store_true", help="extract ZIP archives before inventory")
    parser.add_argument("--archive", action="append", help="limit extraction to a ZIP filename")
    args = parser.parse_args()
    result = inventory(args.root.expanduser(), extract=args.extract, archive_names=args.archive)
    print(json.dumps(result["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
