"""Scene construction for the heiDATA post earthquake benchmark."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

from .mesh import Mesh, box_mesh, mesh_footprint_area, mesh_volume, parse_obj


DAMAGE_GRADES = ("no_damage", "heavy", "extreme", "destruction")
DAMAGE_COLORS = {
    "no_damage": "#2ca02c",
    "heavy": "#f1c40f",
    "extreme": "#e67e22",
    "destruction": "#c0392b",
}


@dataclass(frozen=True)
class DamageMetrics:
    pre_height: float
    post_height: float
    pre_volume: float
    post_volume: float
    pre_footprint_area: float
    post_footprint_area: float
    height_ratio: float
    volume_ratio: float
    footprint_ratio: float

    def as_dict(self) -> dict:
        return {
            "pre_height": self.pre_height,
            "post_height": self.post_height,
            "pre_volume": self.pre_volume,
            "post_volume": self.post_volume,
            "pre_footprint_area": self.pre_footprint_area,
            "post_footprint_area": self.post_footprint_area,
            "height_ratio": self.height_ratio,
            "volume_ratio": self.volume_ratio,
            "footprint_ratio": self.footprint_ratio,
        }


@dataclass(frozen=True)
class BenchmarkBuilding:
    scene_id: str
    source_id: str
    damage_grade: str
    parts: tuple[Mesh, ...]
    pre_mesh: Mesh
    post_mesh: Mesh
    metrics: DamageMetrics
    source_files: tuple[str, ...]
    quality_flags: tuple[str, ...]
    derived: bool = False

    @property
    def mesh(self) -> Mesh:
        return self.parts[0]

    def as_dict(self) -> dict:
        return {
            "scene_id": self.scene_id,
            "source_id": self.source_id,
            "damage_grade": self.damage_grade,
            "parts": [part.summary() for part in self.parts],
            "metrics": self.metrics.as_dict(),
            "source_files": list(self.source_files),
            "quality_flags": list(self.quality_flags),
            "derived": self.derived,
        }


@dataclass(frozen=True)
class Road:
    identifier: str
    start: tuple[float, float]
    end: tuple[float, float]
    width: float
    status: str


@dataclass(frozen=True)
class BenchmarkScene:
    buildings: tuple[BenchmarkBuilding, ...]
    roads: tuple[Road, ...]
    base: tuple[float, float, float]
    candidate_sites: tuple[tuple[float, float, float], ...]
    world_minimum: tuple[float, float, float]
    world_maximum: tuple[float, float, float]
    seed: int
    source: str
    metadata: dict

    def as_dict(self) -> dict:
        return {
            "buildings": [building.as_dict() for building in self.buildings],
            "roads": [road.__dict__ for road in self.roads],
            "base": list(self.base),
            "candidate_sites": [list(site) for site in self.candidate_sites],
            "world_minimum": list(self.world_minimum),
            "world_maximum": list(self.world_maximum),
            "seed": self.seed,
            "source": self.source,
            "metadata": self.metadata,
        }


def _safe_ratio(post: float, pre: float) -> float:
    return float(post / pre) if pre > 1e-9 else 0.0


def _metrics(pre: Mesh, post: Mesh) -> DamageMetrics:
    return DamageMetrics(
        pre_height=float(pre.extent[2]),
        post_height=float(post.extent[2]),
        pre_volume=mesh_volume(pre),
        post_volume=mesh_volume(post),
        pre_footprint_area=mesh_footprint_area(pre),
        post_footprint_area=mesh_footprint_area(post),
        height_ratio=_safe_ratio(float(post.extent[2]), float(pre.extent[2])),
        volume_ratio=_safe_ratio(mesh_volume(post), mesh_volume(pre)),
        footprint_ratio=_safe_ratio(mesh_footprint_area(post), mesh_footprint_area(pre)),
    )


def _quality_flags(metrics: DamageMetrics, post: Mesh) -> tuple[str, ...]:
    flags: list[str] = []
    if metrics.height_ratio > 3.0:
        flags.append("post height is more than three times the pre event height")
    if metrics.footprint_ratio > 5.0:
        flags.append("post footprint is more than five times the pre event footprint")
    if post.minimum[2] < -0.1:
        flags.append("post geometry contains coordinates below the local ground reference")
    if post.extent[0] > 100.0 or post.extent[1] > 100.0:
        flags.append("post geometry has an unusually large horizontal extent")
    return tuple(flags)


def _align_pair(pre: Mesh, post: Mesh) -> tuple[Mesh, Mesh]:
    origin = pre.minimum
    return pre.translated(-origin), post.translated(-origin)


def _derived_heavy_mesh(pre: Mesh, seed: int) -> Mesh:
    """Create a transparent partial collapse when raw grade 3 is rejected.

    The source building remains heiDATA geometry. Only the damage operation is
    derived and recorded in the building metadata.
    """

    rng = random.Random(seed)
    centroids = pre.face_centroids()
    threshold = pre.minimum[0] + pre.extent[0] * rng.uniform(0.52, 0.66)
    keep = centroids[:, 0] <= threshold
    if keep.sum() < max(8, len(keep) // 8):
        keep = centroids[:, 0] <= pre.minimum[0] + pre.extent[0] * 0.72
    return pre.keep_faces(keep)


def _derived_heavy_parts(pre: Mesh, seed: int) -> tuple[Mesh, ...]:
    standing = _derived_heavy_mesh(pre, seed)
    rng = random.Random(seed + 101)
    x0, y0, _ = pre.minimum
    width, depth, height = pre.extent
    rubble: list[Mesh] = []
    for _ in range(4):
        rubble_width = max(0.4, width * rng.uniform(0.06, 0.14))
        rubble_depth = max(0.4, depth * rng.uniform(0.06, 0.16))
        rubble_height = max(0.25, height * rng.uniform(0.03, 0.12))
        rubble_x = x0 + width * rng.uniform(0.58, 0.88)
        rubble_y = y0 + depth * rng.uniform(0.12, 0.88)
        rubble.append(box_mesh(rubble_width, rubble_depth, rubble_height).translated((rubble_x, rubble_y, 0.0)))
    return (standing, *rubble)


def _translate_building(building: BenchmarkBuilding, offset: tuple[float, float, float]) -> BenchmarkBuilding:
    parts = tuple(part.translated(offset) for part in building.parts)
    return BenchmarkBuilding(
        building.scene_id,
        building.source_id,
        building.damage_grade,
        parts,
        building.pre_mesh.translated(offset),
        building.post_mesh.translated(offset),
        building.metrics,
        building.source_files,
        building.quality_flags,
        building.derived,
    )


def _load_building(raw_dir: Path, entry: dict, seed: int, include_raw_heavy: bool) -> BenchmarkBuilding:
    pre_path = raw_dir / entry["pre"]
    pre = parse_obj(pre_path)
    grade = entry["damage_grade"]
    source_files = [entry["pre"]]
    derived = False
    if grade == "no_damage":
        post = pre
        parts = (pre,)
    elif grade == "heavy" and not include_raw_heavy:
        post = _derived_heavy_mesh(pre, seed)
        parts = (post,)
        derived = True
    else:
        post_name = entry.get("post")
        if not post_name:
            raise ValueError(f"missing post event file for {entry['scene_id']}")
        post_path = raw_dir / post_name
        post = parse_obj(post_path)
        source_files.append(post_name)
        parts = (post,)
    aligned_pre, aligned_post = _align_pair(pre, post)
    metrics = _metrics(aligned_pre, aligned_post)
    flags = _quality_flags(metrics, aligned_post)
    if grade != "no_damage" and metrics.volume_ratio > 1.05:
        flags = flags + ("post mesh volume exceeds pre event volume, review debris interpretation",)
    if derived:
        parts = _derived_heavy_parts(aligned_pre, seed)
    else:
        parts = (aligned_post,)
    return BenchmarkBuilding(
        entry["scene_id"],
        entry["source_id"],
        grade,
        parts,
        aligned_pre,
        aligned_post,
        metrics,
        tuple(source_files),
        flags,
        derived,
    )


def load_benchmark_scene(
    manifest_path: str | Path,
    seed: int = 20260924,
    include_raw_heavy: bool = False,
) -> BenchmarkScene:
    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    raw_dir = manifest_file.parent / manifest["raw_directory"]
    entries = manifest["buildings"]
    buildings = [
        _load_building(raw_dir, entry, seed + index, include_raw_heavy)
        for index, entry in enumerate(entries)
    ]

    placed: list[BenchmarkBuilding] = []
    for index, building in enumerate(buildings):
        cell_x, cell_y = (index % 3) * 40.0, (index // 3) * 40.0
        minimum = np.min(np.asarray([part.minimum for part in building.parts]), axis=0)
        offset = (cell_x - minimum[0], cell_y - minimum[1], -minimum[2])
        placed.append(_translate_building(building, offset))

    rng = random.Random(seed)
    roads = (
        Road("east_west", (0.0, 35.0), (120.0, 35.0), 6.0, "blocked" if rng.random() < 0.5 else "clear"),
        Road("north_south", (35.0, 0.0), (35.0, 160.0), 6.0, "blocked" if rng.random() < 0.35 else "clear"),
    )
    all_vertices = np.concatenate([part.vertices for building in placed for part in building.parts])
    minimum = all_vertices.min(axis=0) - np.asarray((5.0, 5.0, 0.0))
    maximum = all_vertices.max(axis=0) + np.asarray((5.0, 5.0, 5.0))
    base = (minimum[0] + 3.0, minimum[1] + 3.0, 0.0)
    candidates = (
        (30.0, 30.0, 0.0), (70.0, 30.0, 0.0), (110.0, 30.0, 0.0),
        (30.0, 70.0, 0.0), (70.0, 70.0, 0.0), (110.0, 70.0, 0.0),
        (30.0, 110.0, 0.0), (70.0, 110.0, 0.0), (110.0, 110.0, 0.0),
    )
    return BenchmarkScene(
        tuple(placed), roads, base, candidates,
        tuple(minimum.tolist()), tuple(maximum.tolist()), seed,
        manifest["dataset"]["persistent_identifier"],
        {
            "manifest_version": manifest["manifest_version"],
            "damage_grade_mapping": manifest["damage_grade_mapping"],
            "include_raw_heavy": include_raw_heavy,
            "quality_flag_count": sum(len(item.quality_flags) for item in placed),
        },
    )


def build_sample_scene(raw_dir: str | Path, seed: int = 20260924, include_raw_heavy: bool = False) -> BenchmarkScene:
    """Build the checked in sample scene without changing the DU simulator."""

    manifest = Path(raw_dir).parent / "manifest.json"
    return load_benchmark_scene(manifest, seed=seed, include_raw_heavy=include_raw_heavy)
