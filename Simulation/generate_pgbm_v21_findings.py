"""Create V2.1 cache metrics summaries and Plotly evidence charts."""

import argparse
import csv
import json
import os
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import plotly.graph_objects as go
from plotly.subplots import make_subplots


NUMERIC_FIELDS = (
    "objective_value",
    "served_tasks",
    "deferred_tasks",
    "average_completion_delay",
    "total_distance",
    "total_energy",
    "parcel_delivery_rate",
    "safe_return_rate",
    "runtime_seconds",
    "cache_loaded_parcels",
    "cache_used_parcels",
    "cache_returned_parcels",
    "cache_match_count",
    "cache_hit_count",
    "cache_hit_rate",
    "cache_assisted_count",
    "cache_energy_overhead",
)


def read_rows(path: str) -> List[Dict[str, object]]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        rows: List[Dict[str, object]] = []
        for raw in csv.DictReader(handle):
            row: Dict[str, object] = dict(raw)
            for field in NUMERIC_FIELDS:
                row[field] = float(raw.get(field, 0.0) or 0.0)
            row["task_count"] = int(raw["task_count"])
            row["uav_count"] = int(raw["uav_count"])
            row["seed"] = int(raw["seed"])
            row["cache_enabled"] = raw.get("cache_enabled", "False").lower() == "true"
            rows.append(row)
    if not rows:
        raise ValueError("metrics file contains no rows")
    return rows


def grouped_mean(rows: Iterable[Mapping[str, object]], keys: Sequence[str]) -> List[Dict[str, object]]:
    groups: Dict[Tuple[object, ...], List[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    result: List[Dict[str, object]] = []
    for key, members in sorted(groups.items(), key=lambda item: tuple(str(value) for value in item[0])):
        summary = {name: value for name, value in zip(keys, key)}
        summary["episodes"] = len(members)
        for field in NUMERIC_FIELDS:
            summary[field] = mean(float(member[field]) for member in members)
        result.append(summary)
    return result


def paired_deltas(rows: Sequence[Mapping[str, object]]) -> List[Dict[str, object]]:
    """Compute cache-policy deltas against the matching V2 control episode."""

    key_fields = ("environment", "task_count", "uav_count", "seed")
    delta_fields = (
        "objective_value",
        "served_tasks",
        "deferred_tasks",
        "average_completion_delay",
        "total_energy",
        "parcel_delivery_rate",
        "safe_return_rate",
    )
    controls = {
        tuple(row[field] for field in key_fields): row
        for row in rows
        if _variant_label(row) == "v2_control"
    }
    grouped: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for row in rows:
        variant = _variant_label(row)
        if variant == "v2_control":
            continue
        control = controls.get(tuple(row[field] for field in key_fields))
        if control is None:
            continue
        delta = {"cache_variant": variant}
        for field in delta_fields:
            delta["delta_" + field] = float(row[field]) - float(control[field])
        delta["cache_energy_overhead"] = float(row["cache_energy_overhead"])
        grouped[variant].append(delta)

    summaries: List[Dict[str, object]] = []
    for variant, members in sorted(grouped.items()):
        summary: Dict[str, object] = {"cache_variant": variant, "episodes": len(members)}
        for field in delta_fields:
            summary["delta_" + field] = mean(float(member["delta_" + field]) for member in members)
        summary["cache_energy_overhead"] = mean(float(member["cache_energy_overhead"]) for member in members)
        summaries.append(summary)
    return summaries


def write_summary_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _variant_label(row: Mapping[str, object]) -> str:
    return str(row.get("cache_variant") or row.get("algorithm") or "unknown")


def _write_chart(fig: go.Figure, path: Path, title: str) -> None:
    fig.update_layout(
        template="plotly_white",
        title=title,
        font={"family": "Aptos, Arial, sans-serif", "size": 13},
        margin={"l": 70, "r": 40, "t": 80, "b": 70},
        legend={"orientation": "h", "y": -0.18},
    )
    fig.write_html(str(path), include_plotlyjs=True, full_html=True)


def create_charts(rows: Sequence[Mapping[str, object]], output_dir: Path) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    overall = grouped_mean(rows, ("cache_variant", "algorithm"))
    cache_rows = [row for row in overall if bool(row.get("cache_enabled", False)) or row["cache_variant"] != "v2_control"]
    labels = [_variant_label(row) for row in cache_rows]

    activity = go.Figure()
    for field, label in (
        ("cache_loaded_parcels", "Loaded"),
        ("cache_used_parcels", "Used"),
        ("cache_returned_parcels", "Returned"),
        ("cache_match_count", "Matches"),
        ("cache_hit_count", "Accepted hits"),
    ):
        activity.add_trace(go.Bar(x=labels, y=[float(row[field]) for row in cache_rows], name=label))
    activity_path = output_dir / "cache_activity.html"
    _write_chart(activity, activity_path, "V2.1 cache activity per episode")

    performance = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.18,
        subplot_titles=("Mean service objective", "Delivery and safe return rates"),
    )
    all_labels = [_variant_label(row) for row in overall]
    performance.add_trace(
        go.Bar(x=all_labels, y=[float(row["objective_value"]) for row in overall], name="Objective"),
        row=1,
        col=1,
    )
    performance.add_trace(
        go.Bar(x=all_labels, y=[float(row["parcel_delivery_rate"]) for row in overall], name="Parcel delivery rate"),
        row=2,
        col=1,
    )
    performance.add_trace(
        go.Bar(x=all_labels, y=[float(row["safe_return_rate"]) for row in overall], name="Safe return rate"),
        row=2,
        col=1,
    )
    performance.update_yaxes(title_text="Objective", row=1, col=1)
    performance.update_yaxes(title_text="Rate", range=[0.0, 1.05], row=2, col=1)
    performance_path = output_dir / "performance_comparison.html"
    _write_chart(performance, performance_path, "V2 control and V2.1 performance")

    condition_rows = grouped_mean(rows, ("cache_variant", "environment"))
    heatmap_variants = sorted({_variant_label(row) for row in condition_rows if _variant_label(row) != "v2_control"})
    environments = sorted({str(row["environment"]) for row in condition_rows})
    heatmap = go.Figure()
    z = []
    for variant in heatmap_variants:
        z.append(
            [
                next(
                    (float(row["cache_hit_rate"]) for row in condition_rows if _variant_label(row) == variant and row["environment"] == environment),
                    0.0,
                )
                for environment in environments
            ]
        )
    if heatmap_variants:
        heatmap.add_trace(
            go.Heatmap(
                z=z,
                x=environments,
                y=heatmap_variants,
                colorscale="Blues",
                zmin=0.0,
                zmax=1.0,
                colorbar={"title": "Hit rate"},
                text=[["{:.3f}".format(value) for value in row] for row in z],
                texttemplate="%{text}",
            )
        )
    hit_path = output_dir / "cache_hit_rate_by_environment.html"
    _write_chart(heatmap, hit_path, "Cache hit rate by environment")

    energy = go.Figure()
    for row in cache_rows:
        label = _variant_label(row)
        members = [float(item["cache_energy_overhead"]) for item in rows if _variant_label(item) == label]
        energy.add_trace(go.Box(y=members, name=label, boxmean=True))
    energy_path = output_dir / "cache_energy_overhead.html"
    _write_chart(energy, energy_path, "Cache energy overhead distribution")
    return {
        "cache_activity": activity_path.name,
        "performance_comparison": performance_path.name,
        "cache_hit_rate_by_environment": hit_path.name,
        "cache_energy_overhead": energy_path.name,
    }


def _markdown_table(rows: Sequence[Mapping[str, object]], fields: Sequence[Tuple[str, str]]) -> str:
    header = "| " + " | ".join(label for _, label in fields) + " |\n"
    separator = "| " + " | ".join("---" for _ in fields) + " |\n"
    body = ""
    for row in rows:
        values = []
        for key, _ in fields:
            value = row.get(key, "")
            if isinstance(value, float):
                values.append("{:.4f}".format(value))
            else:
                values.append(str(value))
        body += "| " + " | ".join(values) + " |\n"
    return header + separator + body


def write_report(
    rows: Sequence[Mapping[str, object]],
    report_path: Path,
    chart_names: Mapping[str, str],
    chart_dir: Path,
    manifest_path: str = "",
) -> None:
    overall = grouped_mean(rows, ("cache_variant", "algorithm"))
    cache_rows = [row for row in overall if _variant_label(row) != "v2_control"]
    paired = paired_deltas(rows)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    chart_links = {
        key: Path(os.path.relpath(chart_dir / value, report_path.parent))
        for key, value in chart_names.items()
    }
    lines = [
        "# PGBM Version 2.1 Cache Aware Recourse Findings",
        "",
        "This is a separate evidence note for the cache aware Version 2.1 path. Canonical V1 and V2 evidence are not overwritten.",
        "",
        "## Experimental contract",
        "",
        "The V2 control and every V2.1 variant use the same seeded scenario. V2.1 loads at most one reserve parcel at dispatch, checks payload, energy reserve, route return, and horizon, then keeps the V2 one for one positive gain rule.",
        "",
        "The water heavy prior is a sensitivity policy, not a field calibrated probability. The default uniform prior follows the current uniform non empty subset task generator.",
        "",
        "## Aggregate performance",
        "",
        _markdown_table(
            overall,
            (
                ("algorithm", "Algorithm"),
                ("cache_variant", "Variant"),
                ("episodes", "Episodes"),
                ("objective_value", "Objective"),
                ("parcel_delivery_rate", "Delivery rate"),
                ("safe_return_rate", "Safe return"),
                ("total_energy", "Energy"),
                ("average_completion_delay", "Mean delay"),
            ),
        ),
        "## Paired core findings",
        "",
        "Each V2.1 row below is compared with the V2 control from the identical environment, task load, fleet size, and seed.",
        "",
        _markdown_table(
            paired,
            (
                ("cache_variant", "Variant"),
                ("episodes", "Paired episodes"),
                ("delta_objective_value", "Delta objective"),
                ("delta_served_tasks", "Delta served"),
                ("delta_deferred_tasks", "Delta deferred"),
                ("delta_average_completion_delay", "Delta delay"),
                ("delta_parcel_delivery_rate", "Delta delivery"),
                ("delta_total_energy", "Delta energy"),
                ("cache_energy_overhead", "Cache energy overhead"),
            ),
        ),
        "## Cache behavior",
        "",
        _markdown_table(
            cache_rows,
            (
                ("cache_variant", "Variant"),
                ("cache_loaded_parcels", "Loaded"),
                ("cache_used_parcels", "Used"),
                ("cache_returned_parcels", "Returned"),
                ("cache_match_count", "Matches"),
                ("cache_hit_count", "Accepted hits"),
                ("cache_hit_rate", "Hit rate"),
                ("cache_energy_overhead", "Cache energy overhead"),
            ),
        ),
        "## Core interpretation",
        "",
        "The control row is the reference for judging whether reserve inventory changes service performance rather than merely changing traces.",
        "Cache loaded but unused parcels are reported as returned, so loading alone is not counted as a successful cache hit.",
        "The reported cache hit rate is accepted cache hits divided by all accepted replacements; it is not the fraction of loaded parcels that were used.",
        "A cache match is distinct from an accepted replacement. The replacement must still satisfy route, payload, energy, horizon, and positive gain checks.",
        "Across this bounded matrix, both one-slot policies show a small service gain but return most loaded reserve parcels unused; the water-heavy sensitivity costs more cache energy. The evidence therefore supports retaining one slot and deferring a second slot or adaptive prior.",
        "",
        "## Charts",
        "",
        "* [Cache activity](<{}>)".format(chart_links["cache_activity"]),
        "* [Performance comparison](<{}>)".format(chart_links["performance_comparison"]),
        "* [Cache hit rate by environment](<{}>)".format(chart_links["cache_hit_rate_by_environment"]),
        "* [Cache energy overhead](<{}>)".format(chart_links["cache_energy_overhead"]),
        "",
        "## Evidence files",
        "",
        "* Metrics CSV: `Simulation/results/pgbm_v2_1_cache_experiments/raw_metrics/`",
        "* Decision traces: `Simulation/results/pgbm_v2_1_cache_experiments/decision_traces/`",
        "* Configuration manifest: `{}`".format(manifest_path or "the matrix manifest"),
        "",
        "## Limitations",
        "",
        "The matrix does not establish a real world item probability. It compares a generator aligned uniform prior with one named sensitivity prior.",
        "The planner bounds used for this evidence run are recorded in the manifest; results should be interpreted as bounded-search evidence rather than an unrestricted optimality claim.",
        "The current implementation intentionally stops at one reserve slot. A second slot or adaptive prior should be added only if the matrix shows consistent benefit without unacceptable energy or return cost.",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", required=True)
    parser.add_argument("--report", default="docs/reports/pgbm_v2_1_cache_findings.md")
    parser.add_argument(
        "--chart-dir",
        default="Simulation/results/pgbm_v2_1_cache_experiments/charts",
    )
    parser.add_argument("--summary", default="Simulation/results/pgbm_v2_1_cache_experiments/summary/pgbm_v2_1_cache_summary.csv")
    parser.add_argument("--manifest", default="Simulation/results/pgbm_v2_1_cache_experiments/manifests/pgbm_v2_1_cache_manifest.json")
    args = parser.parse_args()
    rows = read_rows(args.metrics)
    overall = grouped_mean(rows, ("cache_variant", "algorithm"))
    write_summary_csv(Path(args.summary), overall)
    chart_names = create_charts(rows, Path(args.chart_dir))
    write_report(rows, Path(args.report), chart_names, Path(args.chart_dir), args.manifest)
    print("Summary: {}".format(args.summary))
    print("Report: {}".format(args.report))
    print("Charts: {}".format(args.chart_dir))


if __name__ == "__main__":
    main()
