"""Write source faithful heiDATA layout and damage pair previews."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .source_viewer import load_source_layout, load_source_pair, render_source_layout, render_source_pair


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--pair", default="extreme_b001")
    # This is the canonical preview path used by the thesis workspace.  It
    # deliberately writes the source-faithful layout, never the older
    # synthetic grid composition.
    parser.add_argument("--layout-html", type=Path, default=Path("results/heidata_benchmark_preview.html"))
    parser.add_argument("--pair-html", type=Path, default=Path("results/heidata_source_pair.html"))
    parser.add_argument("--report", type=Path, default=Path("results/heidata_source_pair_report.json"))
    args = parser.parse_args()
    layout = load_source_layout(args.manifest)
    pair = load_source_pair(args.manifest, args.pair)
    for target in (args.layout_html, args.pair_html, args.report):
        target.parent.mkdir(parents=True, exist_ok=True)
    render_source_layout(layout).write_html(str(args.layout_html), include_plotlyjs=True)
    render_source_pair(pair).write_html(str(args.pair_html), include_plotlyjs=True)
    args.report.write_text(json.dumps(pair.report(), indent=2), encoding="utf-8")
    print(f"Layout: {args.layout_html}")
    print(f"Pair: {args.pair_html}")
    print(f"Report: {args.report}")


if __name__ == "__main__":
    main()
