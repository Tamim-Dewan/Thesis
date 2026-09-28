"""Lazy access to the complete downloaded heiDATA archives.

The archives stay outside the repository.  The manifest indexes every OBJ
member, while the mesh library reads only assets required by a scenario.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Iterable

from .library import MeshAsset, MeshLibrary, MeshLibraryError, MeshReview
from .mesh import parse_obj_stream


FULL_MANIFEST_SCHEMA = "heidata.full_manifest.v1"
_BUILDING_ID = re.compile(r"(?:pre_)?(b_\d+)", re.IGNORECASE)

ARCHIVE_INFO = {
    "building_models_pre_event_generic.zip": ("pre", "no_damage", "pre"),
    "building_models_post_event_damage_grade3_generic.zip": ("post", "heavy", "grade3"),
    "building_models_post_event_damage_grade4_generic.zip": ("post", "extreme", "grade4"),
    "building_models_post_event_damage_grade5_generic.zip": ("post", "destruction", "grade5"),
}


def _asset_id(archive_name: str, member_name: str) -> str:
    phase, _, marker = ARCHIVE_INFO[archive_name]
    return f"{phase}:{marker}_{Path(member_name).name}"


def _source_id(member_name: str) -> str:
    match = _BUILDING_ID.search(Path(member_name).stem)
    if not match:
        raise MeshLibraryError(f"cannot determine building id from {member_name}")
    return match.group(1).lower()


def build_full_manifest(root: str | Path) -> dict:
    """Index every OBJ member without extracting the multi gigabyte archives."""

    dataset_root = Path(root).expanduser().resolve()
    assets: list[dict] = []
    for archive_path in sorted((dataset_root / "archives").glob("*.zip")):
        if archive_path.name not in ARCHIVE_INFO:
            continue
        phase, damage_grade, marker = ARCHIVE_INFO[archive_path.name]
        with zipfile.ZipFile(archive_path) as archive:
            for member in sorted(
                (info for info in archive.infolist() if info.filename.lower().endswith(".obj")),
                key=lambda info: info.filename,
            ):
                assets.append({
                    "asset_id": _asset_id(archive_path.name, member.filename),
                    "source_id": _source_id(member.filename),
                    "event_phase": phase,
                    "damage_grade": damage_grade,
                    "archive": archive_path.name,
                    "member": member.filename,
                    "size_bytes": member.file_size,
                    "compressed_size_bytes": member.compress_size,
                })
    if not assets:
        raise MeshLibraryError(f"no complete heiDATA OBJ archives found in {dataset_root / 'archives'}")
    return {
        "schema_version": FULL_MANIFEST_SCHEMA,
        "dataset": {"persistent_identifier": "doi:10.11588/DATA/D3WZID"},
        "root": str(dataset_root),
        "archive_count": len({item["archive"] for item in assets}),
        "asset_count": len(assets),
        "source_axis_convention": {"horizontal": ["X", "Z"], "vertical": "Y"},
        "assets": assets,
    }


def write_full_manifest(root: str | Path, output: str | Path | None = None) -> Path:
    dataset_root = Path(root).expanduser().resolve()
    destination = Path(output).expanduser() if output else dataset_root / "full_manifest.v1.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(build_full_manifest(dataset_root), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return destination


def _checksum_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _post_review(asset_id: str, post, pre) -> MeshReview:
    checks = ["source mesh parsed from official archive"]
    horizontal_ratio = max(
        float(post.extent[0] / max(pre.extent[0], 1e-9)),
        float(post.extent[2] / max(pre.extent[2], 1e-9)),
    )
    vertical_ratio = float(post.extent[1] / max(pre.extent[1], 1e-9))
    if horizontal_ratio > 4.0:
        checks.append(f"horizontal extent ratio {horizontal_ratio:.2f} exceeds 4.00")
    if vertical_ratio > 4.0:
        checks.append(f"vertical extent ratio {vertical_ratio:.2f} exceeds 4.00")
    status = "inspection_only" if len(checks) > 1 else "accepted"
    reason = "geometry needs explicit thesis review before scenario use" if status != "accepted" else "geometry is within deterministic source review thresholds"
    return MeshReview(asset_id, status, tuple(checks), reason)


def build_full_mesh_library(manifest_path: str | Path, required_asset_ids: Iterable[str]) -> MeshLibrary:
    """Load only the selected full archive assets required by one scenario."""

    manifest_file = Path(manifest_path).expanduser().resolve()
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise MeshLibraryError(f"full manifest is unavailable or invalid: {manifest_file}") from error
    if manifest.get("schema_version") != FULL_MANIFEST_SCHEMA:
        raise MeshLibraryError(f"supported full manifest schema is {FULL_MANIFEST_SCHEMA}")
    root = Path(manifest["root"]).expanduser().resolve()
    entries = {item["asset_id"]: item for item in manifest.get("assets", [])}
    wanted = set(required_asset_ids)
    missing = sorted(wanted.difference(entries))
    if missing:
        raise MeshLibraryError(f"full manifest is missing required assets: {missing}")
    pre_entries = {item["source_id"]: item for item in manifest["assets"] if item["event_phase"] == "pre"}
    loaded: dict[str, MeshAsset] = {}
    for asset_id in sorted(wanted):
        entry = entries[asset_id]
        archive_path = root / "archives" / entry["archive"]
        try:
            with zipfile.ZipFile(archive_path) as archive:
                raw = archive.read(entry["member"])
        except (OSError, KeyError, zipfile.BadZipFile) as error:
            raise MeshLibraryError(f"cannot read full dataset asset {asset_id}") from error
        import io
        with io.TextIOWrapper(io.BytesIO(raw), encoding="utf-8", errors="replace") as handle:
            mesh = parse_obj_stream(handle, f"{archive_path}!{entry['member']}")
        if entry["event_phase"] == "post":
            pre_entry = pre_entries.get(entry["source_id"])
            if pre_entry is None:
                raise MeshLibraryError(f"post asset has no matching pre asset: {asset_id}")
            with zipfile.ZipFile(root / "archives" / pre_entry["archive"]) as archive:
                pre_raw = archive.read(pre_entry["member"])
            with io.TextIOWrapper(io.BytesIO(pre_raw), encoding="utf-8", errors="replace") as handle:
                pre_mesh = parse_obj_stream(handle, f"{pre_entry['archive']}!{pre_entry['member']}")
            review = _post_review(asset_id, mesh, pre_mesh)
        else:
            review = MeshReview(asset_id, "accepted", ("source mesh parsed from official archive",), "pre event source asset")
        loaded[asset_id] = MeshAsset(
            asset_id=asset_id,
            source_id=entry["source_id"],
            path=f"{archive_path}!{entry['member']}",
            event_phase=entry["event_phase"],
            damage_grade=entry["damage_grade"],
            checksum_sha256=_checksum_bytes(raw),
            mesh=mesh,
            review=review,
        )
    return MeshLibrary(str(manifest_file), str(manifest["dataset"]["persistent_identifier"]), tuple(loaded.values()))
