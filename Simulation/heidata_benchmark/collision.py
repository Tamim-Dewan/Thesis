"""Lightweight collision geometry derived from detailed benchmark meshes."""

from __future__ import annotations

from dataclasses import dataclass

from .scene import BenchmarkScene


@dataclass(frozen=True)
class CollisionBox:
    identifier: str
    minimum: tuple[float, float, float]
    maximum: tuple[float, float, float]
    source_id: str
    damage_grade: str

    def contains(self, point: tuple[float, float, float]) -> bool:
        return all(low <= value <= high for value, low, high in zip(point, self.minimum, self.maximum))


def collision_boxes(scene: BenchmarkScene) -> tuple[CollisionBox, ...]:
    """Return one conservative axis aligned box per visual geometry part."""

    result: list[CollisionBox] = []
    for building in scene.buildings:
        for index, part in enumerate(building.parts):
            result.append(
                CollisionBox(
                    f"{building.scene_id}_collision_{index + 1}",
                    tuple(part.minimum.tolist()),
                    tuple(part.maximum.tolist()),
                    building.source_id,
                    building.damage_grade,
                )
            )
    return tuple(result)


def is_free(scene: BenchmarkScene, point: tuple[float, float, float]) -> bool:
    return not any(box.contains(point) for box in collision_boxes(scene))
