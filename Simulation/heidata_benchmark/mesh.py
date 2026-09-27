"""Small OBJ reader and geometry helpers for the heiDATA benchmark.

The benchmark keeps the source geometry as triangle meshes. It does not need a
large mesh library at runtime, which keeps the environment portable for the
existing Python simulation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np


class MeshFormatError(ValueError):
    """Raised when a source OBJ cannot be interpreted as a triangle mesh."""


@dataclass(frozen=True)
class Mesh:
    """A triangle mesh with vertices in metres and zero based face indices."""

    vertices: np.ndarray
    faces: np.ndarray

    def __post_init__(self) -> None:
        vertices = np.asarray(self.vertices, dtype=float)
        faces = np.asarray(self.faces, dtype=int)
        if vertices.ndim != 2 or vertices.shape[1] != 3:
            raise MeshFormatError("vertices must have shape (n, 3)")
        if faces.ndim != 2 or faces.shape[1] != 3:
            raise MeshFormatError("faces must have shape (n, 3)")
        if not np.isfinite(vertices).all():
            raise MeshFormatError("vertices contain a non finite value")
        if len(faces) and (faces.min() < 0 or faces.max() >= len(vertices)):
            raise MeshFormatError("face index is outside the vertex array")
        object.__setattr__(self, "vertices", vertices)
        object.__setattr__(self, "faces", faces)

    @property
    def minimum(self) -> np.ndarray:
        return self.vertices.min(axis=0)

    @property
    def maximum(self) -> np.ndarray:
        return self.vertices.max(axis=0)

    @property
    def extent(self) -> np.ndarray:
        return self.maximum - self.minimum

    def translated(self, offset: Sequence[float]) -> "Mesh":
        return Mesh(self.vertices + np.asarray(offset, dtype=float), self.faces.copy())

    def face_centroids(self) -> np.ndarray:
        return self.vertices[self.faces].mean(axis=1)

    def keep_faces(self, keep: Iterable[bool]) -> "Mesh":
        selected = self.faces[np.asarray(list(keep), dtype=bool)]
        if len(selected) == 0:
            raise MeshFormatError("face selection removed the whole mesh")
        used, inverse = np.unique(selected.reshape(-1), return_inverse=True)
        return Mesh(self.vertices[used], inverse.reshape((-1, 3)))

    def summary(self) -> dict:
        return {
            "vertex_count": int(len(self.vertices)),
            "face_count": int(len(self.faces)),
            "minimum": self.minimum.tolist(),
            "maximum": self.maximum.tolist(),
            "extent": self.extent.tolist(),
        }


def _obj_index(token: str, vertex_count: int) -> int:
    value = int(token.split("/", 1)[0])
    if value == 0:
        raise MeshFormatError("OBJ vertex indices are one based")
    return value - 1 if value > 0 else vertex_count + value


def parse_obj(path: str | Path) -> Mesh:
    """Read vertices and triangulated faces from a Wavefront OBJ file."""

    vertices: list[list[float]] = []
    faces: list[tuple[int, int, int]] = []
    source = Path(path)
    try:
        handle = source.open("r", encoding="utf-8", errors="replace")
    except OSError as error:
        raise MeshFormatError(f"OBJ file is unavailable: {source}") from error

    with handle:
        for line_number, line in enumerate(handle, start=1):
            parts = line.strip().split()
            if not parts or parts[0].startswith("#"):
                continue
            if parts[0] == "v":
                if len(parts) < 4:
                    raise MeshFormatError(f"vertex is incomplete at line {line_number}")
                vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif parts[0] == "f":
                if len(parts) < 4:
                    continue
                indices = [_obj_index(token, len(vertices)) for token in parts[1:]]
                for index in range(1, len(indices) - 1):
                    faces.append((indices[0], indices[index], indices[index + 1]))

    if not vertices or not faces:
        raise MeshFormatError(f"OBJ file has no usable mesh: {source}")
    return Mesh(np.asarray(vertices, dtype=float), np.asarray(faces, dtype=int))


def convex_hull(points: np.ndarray) -> np.ndarray:
    """Return the two dimensional monotonic chain hull."""

    values = sorted({(float(x), float(y)) for x, y in np.asarray(points)[:, :2]})
    if len(values) <= 1:
        return np.asarray(values, dtype=float)

    def cross(origin, first, second):
        return (first[0] - origin[0]) * (second[1] - origin[1]) - (first[1] - origin[1]) * (second[0] - origin[0])

    lower: list[tuple[float, float]] = []
    for point in values:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[tuple[float, float]] = []
    for point in reversed(values):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    return np.asarray(lower[:-1] + upper[:-1], dtype=float)


def polygon_area(points: np.ndarray) -> float:
    if len(points) < 3:
        return 0.0
    return float(abs(np.dot(points[:, 0], np.roll(points[:, 1], -1)) - np.dot(points[:, 1], np.roll(points[:, 0], -1))) / 2.0)


def mesh_footprint_area(mesh: Mesh) -> float:
    return polygon_area(convex_hull(mesh.vertices[:, :2]))


def mesh_volume(mesh: Mesh) -> float:
    """Estimate closed mesh volume from oriented triangles."""

    triangles = mesh.vertices[mesh.faces]
    signed = np.einsum("ij,ij->i", triangles[:, 0], np.cross(triangles[:, 1], triangles[:, 2]))
    return float(abs(signed.sum()) / 6.0)


def box_mesh(width: float, depth: float, height: float) -> Mesh:
    vertices = np.asarray(
        [
            (0, 0, 0), (width, 0, 0), (width, depth, 0), (0, depth, 0),
            (0, 0, height), (width, 0, height), (width, depth, height), (0, depth, height),
        ],
        dtype=float,
    )
    faces = np.asarray(
        [
            (0, 2, 1), (0, 3, 2),
            (4, 5, 6), (4, 6, 7),
            (0, 1, 5), (0, 5, 4),
            (1, 2, 6), (1, 6, 5),
            (2, 3, 7), (2, 7, 6),
            (3, 0, 4), (3, 4, 7),
        ],
        dtype=int,
    )
    return Mesh(vertices, faces)
