"""Stable component-level random seeds for reproducible experiments."""

import hashlib
import random
from typing import Dict


class SeedManager:
    """Derive stable integer seeds without relying on Python's randomized hash."""

    def __init__(self, base_seed: int):
        if base_seed < 0:
            raise ValueError("base_seed must be non-negative")
        self.base_seed = int(base_seed)

    def seed_for(self, component: str, repetition: int = 0) -> int:
        key = "{}:{}:{}".format(self.base_seed, component, repetition).encode("utf-8")
        digest = hashlib.sha256(key).digest()
        return int.from_bytes(digest[:8], byteorder="big") % (2 ** 32)

    def manifest(self, components) -> Dict[str, int]:
        return {component: self.seed_for(component) for component in components}

    def python_rng(self, component: str, repetition: int = 0) -> random.Random:
        return random.Random(self.seed_for(component, repetition))
