"""Verified local heiDATA mesh assets and post event mesh reviews."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .mesh import Mesh, parse_obj


class MeshLibraryError(ValueError):
    """Raised when manifest evidence is inconsistent or unsafe to use."""


@dataclass(frozen=True)
class MeshReview:
    asset_id: str
    status: str
    checks: tuple[str, ...]
    reason: str
    review_version: str = "mesh_review.v1"

    def as_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "status": self.status,
            "checks": list(self.checks),
            "reason": self.reason,
            "review_version": self.review_version,
        }


@dataclass(frozen=True)
class MeshAsset:
    asset_id: str
    source_id: str
    path: str
    event_phase: str
    damage_grade: str
    checksum_sha256: str
    mesh: Mesh
    review: MeshReview

    @property
    def raw_bounds_source_xyz(self) -> dict:
        return {"minimum": self.mesh.minimum.tolist(), "maximum": self.mesh.maximum.tolist()}

    def as_dict(self) -> dict:
        return {
            "asset_id": self.asset_id,
            "source_id": self.source_id,
            "path": self.path,
            "event_phase": self.event_phase,
            "damage_grade": self.damage_grade,
            "checksum_sha256": self.checksum_sha256,
            "raw_bounds_source_xyz": self.raw_bounds_source_xyz,
            "source_axis_convention": {"horizontal": ["X", "Z"], "vertical": "Y"},
            "review": self.review.as_dict(),
        }


@dataclass(frozen=True)
class MeshLibrary:
    manifest_path: str
    dataset_identifier: str
    assets: tuple[MeshAsset, ...]

    def asset(self, asset_id: str) -> MeshAsset:
        match = next((item for item in self.assets if item.asset_id == asset_id), None)
        if match is None:
            raise MeshLibraryError(f"unknown mesh asset: {asset_id}")
        return match

    def as_dict(self) -> dict:
        return {
            "manifest_path": self.manifest_path,
            "dataset_identifier": self.dataset_identifier,
            "asset_count": len(self.assets),
            "assets": [asset.as_dict() for asset in self.assets],
        }


def asset_id_for(path: str) -> str:
    phase = "post" if "_post" in path else "pre"
    return f"{phase}:{Path(path).name}"


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _accepted_review(asset_id: str) -> MeshReview:
    return MeshReview(asset_id, "accepted", ("source mesh parsed",), "pre event source asset")


def _review_post_mesh(asset_id: str, post: Mesh, pre: Mesh) -> MeshReview:
    """Mark geometric outliers inspection only, never silently repair them."""

    checks: list[str] = ["source mesh parsed"]
    horizontal_ratio = max(
        float(post.extent[0] / max(pre.extent[0], 1e-9)),
        float(post.extent[2] / max(pre.extent[2], 1e-9)),
    )
    vertical_ratio = float(post.extent[1] / max(pre.extent[1], 1e-9))
    if horizontal_ratio > 4.0:
        checks.append(f"horizontal extent ratio {horizontal_ratio:.2f} exceeds 4.00")
    if vertical_ratio > 4.0:
        checks.append(f"vertical extent ratio {vertical_ratio:.2f} exceeds 4.00")
    if post.minimum[1] < -2.0:
        checks.append("source vertical coordinate is more than 2 metres below local ground")
    if len(checks) > 1:
        return MeshReview(asset_id, "inspection_only", tuple(checks), "geometry needs explicit thesis review before scenario use")
    return MeshReview(asset_id, "accepted", tuple(checks), "geometry is within deterministic source review thresholds")


def build_mesh_library(manifest_path: str | Path) -> MeshLibrary:
    """Build a deduplicated local mesh library from the checked manifest."""

    manifest_file = Path(manifest_path)
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except OSError as error:
        raise MeshLibraryError(f"manifest is unavailable: {manifest_file}") from error
    except json.JSONDecodeError as error:
        raise MeshLibraryError(f"manifest is not valid JSON: {manifest_file}") from error
    try:
        entries = manifest["buildings"]
        raw_directory = manifest["raw_directory"]
        dataset_identifier = manifest["dataset"]["persistent_identifier"]
    except KeyError as error:
        raise MeshLibraryError(f"manifest field is missing: {error.args[0]}") from error
    if not isinstance(entries, list) or not entries:
        raise MeshLibraryError("manifest must contain buildings")
    raw_dir = manifest_file.parent / raw_directory

    source_pre: dict[str, tuple[str, Mesh]] = {}
    occurrences: list[tuple[str, str, str, str]] = []
    for entry in entries:
        try:
            source_id = str(entry["source_id"])
            pre_name = str(entry["pre"])
            grade = str(entry["damage_grade"])
        except KeyError as error:
            raise MeshLibraryError(f"manifest building is missing: {error.args[0]}") from error
        if source_id in source_pre and source_pre[source_id][0] != pre_name:
            raise MeshLibraryError(f"source id {source_id} has conflicting pre assets")
        pre_mesh = parse_obj(raw_dir / pre_name)
        source_pre[source_id] = (pre_name, pre_mesh)
        occurrences.append((source_id, pre_name, "pre", "no_damage"))
        if "post" in entry:
            occurrences.append((source_id, str(entry["post"]), "post", grade))

    assets: list[MeshAsset] = []
    seen_paths: set[str] = set()
    for source_id, name, phase, grade in occurrences:
        if name in seen_paths:
            continue
        seen_paths.add(name)
        path = raw_dir / name
        mesh = parse_obj(path)
        asset_id = asset_id_for(name)
        review = _accepted_review(asset_id) if phase == "pre" else _review_post_mesh(asset_id, mesh, source_pre[source_id][1])
        assets.append(MeshAsset(asset_id, source_id, str(path), phase, grade, _checksum(path), mesh, review))
    return MeshLibrary(str(manifest_file), str(dataset_identifier), tuple(sorted(assets, key=lambda item: item.asset_id)))
