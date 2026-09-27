"""Create a standalone heiDATA benchmark preview and summary."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .render import render_scene
from .scene import load_benchmark_scene


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--seed", type=int, default=20260924)
    parser.add_argument("--include-raw-heavy", action="store_true")
    parser.add_argument("--html", type=Path, default=Path("results/heidata_synthetic_benchmark_preview.html"))
    parser.add_argument("--summary", type=Path, default=Path("results/heidata_synthetic_benchmark_summary.json"))
    args = parser.parse_args()
    scene = load_benchmark_scene(args.manifest, args.seed, args.include_raw_heavy)
    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    render_scene(scene).write_html(str(args.html), include_plotlyjs=True)
    args.summary.write_text(json.dumps(scene.as_dict(), indent=2), encoding="utf-8")
    print(f"Preview: {args.html}")
    print(f"Summary: {args.summary}")
    print(f"Buildings: {len(scene.buildings)}")
    print(f"Quality flags: {scene.metadata['quality_flag_count']}")


if __name__ == "__main__":
    main()
