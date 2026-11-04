"""Build the eight static figures used by the V1 and V2 reports.

The figures are derived only from the canonical experiment CSV files.  The
module deliberately keeps aggregation here instead of duplicating numbers in
the LaTeX sources, so tables and charts can be regenerated from the same
evidence.
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import plotly.graph_objects as go
from plotly.subplots import make_subplots


ROOT = Path(__file__).resolve().parents[1]
V1_METRICS = ROOT / (
    "Simulation/results/pgbm_v1_two_hour_experiments/raw_metrics/"
    "pgbm_v1_two_hour_matrix_metrics_tasks_30_60_90_uavs_3_5_8_10_seeds_101_110.csv"
)
V2_METRICS = ROOT / (
    "Simulation/results/pgbm_v2_recourse_experiments/raw_metrics/"
    "pgbm_v2_paired_matrix_metrics_tasks_30_60_90_uavs_3_5_8_10_seeds_101_110.csv"
)
CHART_ROOT = ROOT / "Experiment Reports/assets"

NAVY = "#17365D"
SLATE = "#64748B"
BLUE = "#0072B2"
ORANGE = "#E69F00"
TEAL = "#009E73"
VERMILLION = "#D55E00"
PURPLE = "#7B61A8"
GRID = "#D9E1E8"
TEXT = "#1F2937"

ENVIRONMENT_COLORS = {"synthetic": BLUE, "du_outdoor": ORANGE}
ALGORITHM_COLORS = {"V1": SLATE, "V2": TEAL}

V1_CHART_NAMES = (
    "v1_workload_pressure",
    "v1_fleet_sensitivity",
    "v1_runtime_bottleneck",
    "v1_baseline_comparison",
)
V2_CHART_NAMES = (
    "v2_environment_comparison",
    "v2_objective_gain_heatmap",
    "v2_recourse_decisions",
    "v2_tradeoff",
)


def _load_csv(path: Path) -> List[Dict[str, object]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        rows: List[Dict[str, object]] = []
        for raw in csv.DictReader(handle):
            row: Dict[str, object] = dict(raw)
            for key, value in raw.items():
                if key in {
                    "seed", "task_count", "uav_count", "served_tasks", "deferred_tasks",
                    "peak_queue_size", "requested_parcels", "dropped_parcels",
                    "accepted_replacements", "rejected_replacements", "recourse_trigger_count",
                    "search_truncated_dispatches", "candidate_count", "dispatch_count",
                }:
                    row[key] = int(value)
                elif key in {
                    "objective_value", "average_completion_delay", "runtime_seconds",
                    "planner_runtime_seconds", "route_runtime_seconds", "recourse_runtime_seconds",
                    "total_energy", "total_distance", "parcel_delivery_rate", "safe_return_rate",
                    "replacement_gain",
                }:
                    row[key] = float(value)
            if "rejection_reasons" in raw:
                row["rejection_reasons_dict"] = json.loads(raw["rejection_reasons"] or "{}")
            rows.append(row)
        return rows


def _mean(rows: Sequence[Mapping[str, object]], field: str) -> float:
    values = [float(row[field]) for row in rows]
    return statistics.mean(values) if values else 0.0


def _sd(rows: Sequence[Mapping[str, object]], field: str) -> float:
    values = [float(row[field]) for row in rows]
    return statistics.stdev(values) if len(values) > 1 else 0.0


def _task_rate(row: Mapping[str, object]) -> float:
    count = float(row["task_count"])
    return float(row["served_tasks"]) / count if count else 0.0


def _group(rows: Iterable[Mapping[str, object]], keys: Sequence[str]):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    return groups


def _layout(fig: go.Figure, width: int = 1200, height: int = 660) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        width=width,
        height=height,
        font={"family": "Avenir Next, Arial, sans-serif", "size": 13, "color": TEXT},
        title={"font": {"family": "Avenir Next, Arial, sans-serif", "size": 19, "color": NAVY}},
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin={"l": 75, "r": 35, "t": 85, "b": 70},
        legend={"orientation": "h", "y": -0.16, "x": 0.5, "xanchor": "center"},
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID, mirror=True)
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID, mirror=True)
    return fig


def _add_environment_title(fig: go.Figure, row: int, col: int, environment: str) -> None:
    label = "Synthetic" if environment == "synthetic" else "DU outdoor"
    fig.add_annotation(
        text=label,
        x=0.5,
        y=1.08,
        xref=f"x{(row - 1) * 2 + col if row > 1 or col > 1 else ''} domain",
        yref=f"y{(row - 1) * 2 + col if row > 1 or col > 1 else ''} domain",
        showarrow=False,
        font={"family": "Avenir Next, Arial, sans-serif", "size": 15, "color": NAVY},
    )


def v1_workload_pressure(rows: Sequence[Mapping[str, object]]) -> go.Figure:
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Task service rate", "Peak queue size"),
        horizontal_spacing=0.12,
    )
    for environment, col in (("synthetic", 1), ("du_outdoor", 2)):
        env_groups = _group(
            [row for row in rows if row["scenario_id"].startswith(environment)],
            ("task_count",),
        )
        task_keys = sorted(env_groups)
        tasks = [key[0] for key in task_keys]
        fig.add_trace(
            go.Scatter(
                x=tasks,
                y=[100.0 * statistics.mean(_task_rate(row) for row in env_groups[key]) for key in task_keys],
                error_y={"type": "data", "array": [100.0 * statistics.stdev([_task_rate(row) for row in env_groups[key]]) if len(env_groups[key]) > 1 else 0.0 for key in task_keys], "visible": True},
                mode="lines+markers",
                name="Synthetic" if environment == "synthetic" else "DU outdoor",
                line={"color": ENVIRONMENT_COLORS[environment], "width": 3},
                marker={"size": 9},
                showlegend=True,
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=tasks,
                y=[_mean(env_groups[key], "peak_queue_size") for key in task_keys],
                error_y={"type": "data", "array": [_sd(env_groups[key], "peak_queue_size") for key in task_keys], "visible": True},
                mode="lines+markers",
                name="Synthetic" if environment == "synthetic" else "DU outdoor",
                line={"color": ENVIRONMENT_COLORS[environment], "width": 3},
                marker={"size": 9},
                showlegend=False,
            ),
            row=1,
            col=2,
        )
    fig.update_xaxes(title_text="Task load", tickvals=[30, 60, 90])
    fig.update_yaxes(title_text="Service rate (%)", range=[0, 100], row=1, col=1)
    fig.update_yaxes(title_text="Tasks", row=1, col=2)
    _layout(fig, height=600)
    fig.update_layout(title="V1 workload pressure")
    return fig


def v1_fleet_sensitivity(rows: Sequence[Mapping[str, object]]) -> go.Figure:
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Task service rate", "Runtime"),
        horizontal_spacing=0.12,
    )
    for environment, col in (("synthetic", 1), ("du_outdoor", 2)):
        env_rows = [row for row in rows if row["scenario_id"].startswith(environment)]
        groups = _group(env_rows, ("uav_count",))
        uav_keys = sorted(groups)
        uavs = [key[0] for key in uav_keys]
        fig.add_trace(
            go.Scatter(
                x=uavs,
                y=[100.0 * statistics.mean(_task_rate(row) for row in groups[key]) for key in uav_keys],
                error_y={"type": "data", "array": [100.0 * statistics.stdev([_task_rate(row) for row in groups[key]]) if len(groups[key]) > 1 else 0.0 for key in uav_keys], "visible": True},
                mode="lines+markers",
                name="Synthetic" if environment == "synthetic" else "DU outdoor",
                line={"color": ENVIRONMENT_COLORS[environment], "width": 3},
                marker={"size": 9},
                showlegend=True,
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scatter(
                x=uavs,
                y=[_mean(groups[key], "runtime_seconds") for key in uav_keys],
                error_y={"type": "data", "array": [_sd(groups[key], "runtime_seconds") for key in uav_keys], "visible": True},
                mode="lines+markers",
                name="Synthetic" if environment == "synthetic" else "DU outdoor",
                line={"color": ENVIRONMENT_COLORS[environment], "width": 3},
                marker={"size": 9},
                showlegend=False,
            ),
            row=1,
            col=2,
        )
    fig.update_xaxes(title_text="UAV count", tickvals=[3, 5, 8, 10])
    fig.update_yaxes(title_text="Service rate (%)", range=[0, 100], row=1, col=1)
    fig.update_yaxes(title_text="Runtime (s)", row=1, col=2)
    _layout(fig, height=600)
    fig.update_layout(title="V1 fleet sensitivity")
    return fig


def v1_runtime_bottleneck(rows: Sequence[Mapping[str, object]]) -> go.Figure:
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Route share of planner time", "Mean truncated dispatches"),
        horizontal_spacing=0.14,
    )
    groups = _group(rows, ("scenario_id",))
    values = {}
    for environment in ("synthetic", "du_outdoor"):
        env_rows = [row for row in rows if row["scenario_id"].startswith(environment)]
        values[environment] = env_rows
    labels = ["Synthetic", "DU outdoor"]
    keys = ["synthetic", "du_outdoor"]
    route_shares = [100.0 * _mean(values[key], "route_runtime_seconds") / _mean(values[key], "planner_runtime_seconds") for key in keys]
    route_errors = []
    trunc_means = []
    trunc_errors = []
    for key in keys:
        shares = [100.0 * float(row["route_runtime_seconds"]) / float(row["planner_runtime_seconds"]) if float(row["planner_runtime_seconds"]) else 0.0 for row in values[key]]
        route_errors.append(statistics.stdev(shares) if len(shares) > 1 else 0.0)
        trunc_values = [float(row.get("search_truncated_dispatches", 0)) for row in values[key]]
        trunc_means.append(statistics.mean(trunc_values) if trunc_values else 0.0)
        trunc_errors.append(statistics.stdev(trunc_values) if len(trunc_values) > 1 else 0.0)
    colors = [ENVIRONMENT_COLORS[key] for key in keys]
    fig.add_trace(go.Bar(x=labels, y=route_shares, error_y={"type": "data", "array": route_errors}, marker_color=colors, showlegend=False), row=1, col=1)
    fig.add_trace(go.Bar(x=labels, y=trunc_means, error_y={"type": "data", "array": trunc_errors}, marker_color=colors, showlegend=False), row=1, col=2)
    fig.update_yaxes(title_text="Route share (%)", range=[0, 100], row=1, col=1)
    fig.update_yaxes(title_text="Dispatches per run", row=1, col=2)
    _layout(fig, height=580)
    fig.update_layout(title="V1 computational bottleneck")
    return fig


def v1_baseline_comparison(rows: Sequence[Mapping[str, object]]) -> go.Figure:
    baseline = [row for row in rows if int(row["task_count"]) == 30 and int(row["uav_count"]) == 3]
    groups = _group(baseline, ("scenario_id",))
    envs = ["synthetic", "du_outdoor"]
    labels = ["Synthetic", "DU outdoor"]
    fig = make_subplots(
        rows=1,
        cols=3,
        subplot_titles=("Task service rate", "Average delay", "Runtime"),
        horizontal_spacing=0.1,
    )
    fields = (("service", None), ("average_completion_delay", "min"), ("runtime_seconds", "s"))
    for col, (field, unit) in enumerate(fields, start=1):
        values = []
        errors = []
        for env in envs:
            env_rows = [row for row in baseline if row["scenario_id"].startswith(env)]
            if field == "service":
                samples = [100.0 * _task_rate(row) for row in env_rows]
            else:
                samples = [float(row[field]) for row in env_rows]
            values.append(statistics.mean(samples) if samples else 0.0)
            errors.append(statistics.stdev(samples) if len(samples) > 1 else 0.0)
        fig.add_trace(go.Bar(x=labels, y=values, error_y={"type": "data", "array": errors}, marker_color=[BLUE, ORANGE], showlegend=False), row=1, col=col)
        title = "Service rate (%)" if field == "service" else f"{field.replace('_', ' ').title()} ({unit})"
        fig.update_yaxes(title_text=title, row=1, col=col)
    _layout(fig, height=570)
    fig.update_layout(title="V1 baseline: 30 tasks and 3 UAVs")
    return fig


def _paired_groups(rows: Sequence[Mapping[str, object]]):
    pairs = _group(rows, ("environment", "task_count", "uav_count", "seed"))
    result = []
    for key, pair in pairs.items():
        algorithms = {str(row["algorithm"]): row for row in pair}
        if set(algorithms) == {"V1", "V2"}:
            result.append((key, algorithms["V1"], algorithms["V2"]))
    return result


def v2_environment_comparison(rows: Sequence[Mapping[str, object]]) -> go.Figure:
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Objective value", "Average completion delay"), horizontal_spacing=0.14)
    for col, field, title, unit in ((1, "objective_value", "Objective", ""), (2, "average_completion_delay", "Delay", "min")):
        for algorithm in ("V1", "V2"):
            values = []
            errors = []
            labels = ["DU outdoor", "Synthetic"]
            for env in ("du_outdoor", "synthetic"):
                group = [row for row in rows if row["environment"] == env and row["algorithm"] == algorithm]
                values.append(_mean(group, field))
                errors.append(_sd(group, field))
            fig.add_trace(go.Bar(x=labels, y=values, error_y={"type": "data", "array": errors}, name=algorithm, marker_color=ALGORITHM_COLORS[algorithm], legendgroup=algorithm, showlegend=(col == 1)), row=1, col=col)
        fig.update_yaxes(title_text=f"{title}{f' ({unit})' if unit else ''}", row=1, col=col)
    _layout(fig, height=600)
    fig.update_layout(title="V2 versus V1 across environments", barmode="group")
    return fig


def v2_objective_gain_heatmap(rows: Sequence[Mapping[str, object]]) -> go.Figure:
    pairs = _paired_groups(rows)
    fig = make_subplots(rows=1, cols=2, subplot_titles=("DU outdoor", "Synthetic"), horizontal_spacing=0.15)
    for col, env in ((1, "du_outdoor"), (2, "synthetic")):
        data = defaultdict(list)
        for key, v1, v2 in pairs:
            environment, task_count, uav_count, _ = key
            if environment == env:
                data[(task_count, uav_count)].append(float(v2["objective_value"]) - float(v1["objective_value"]))
        tasks = [30, 60, 90]
        uavs = [3, 5, 8, 10]
        z = [[statistics.mean(data[(task, uav)]) if data[(task, uav)] else 0.0 for uav in uavs] for task in tasks]
        fig.add_trace(go.Heatmap(x=uavs, y=tasks, z=z, zmid=0, colorscale=[[0.0, "#B2182B"], [0.5, "#F7F7F7"], [1.0, "#2166AC"]], showscale=(col == 2), colorbar={"title": "Delta objective", "len": 0.8}, text=[[f"{value:.2f}" for value in row] for row in z], texttemplate="%{text}", hovertemplate="Tasks=%{y}<br>UAVs=%{x}<br>Delta objective=%{z:.2f}<extra></extra>"), row=1, col=col)
        fig.update_xaxes(
            title_text="UAV count",
            tickmode="array",
            tickvals=uavs,
            ticktext=[str(uav) for uav in uavs],
            row=1,
            col=col,
        )
        fig.update_yaxes(
            title_text="Task load",
            autorange="reversed",
            tickmode="array",
            tickvals=tasks,
            ticktext=[str(task) for task in tasks],
            row=1,
            col=col,
        )
    _layout(fig, height=570)
    fig.update_layout(title="V2 objective gain over V1")
    return fig


def v2_recourse_decisions(rows: Sequence[Mapping[str, object]]) -> go.Figure:
    v2_rows = [row for row in rows if row["algorithm"] == "V2"]
    accepted = sum(int(row.get("accepted_replacements", 0)) for row in v2_rows)
    rejected = sum(int(row.get("rejected_replacements", 0)) for row in v2_rows)
    reasons = defaultdict(int)
    for row in v2_rows:
        for reason, count in dict(row.get("rejection_reasons_dict", {})).items():
            reasons[reason] += int(count)
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Replacement outcomes", "Rejection reasons"), horizontal_spacing=0.16)
    fig.add_trace(go.Bar(x=["Accepted", "Rejected"], y=[accepted, rejected], marker_color=[TEAL, VERMILLION], showlegend=False), row=1, col=1)
    ordered = sorted(reasons.items(), key=lambda item: item[1], reverse=True)
    fig.add_trace(go.Bar(x=[item[0].replace("_", " ") for item in ordered], y=[item[1] for item in ordered], marker_color=PURPLE, showlegend=False), row=1, col=2)
    fig.update_yaxes(title_text="Decisions", row=1, col=1)
    fig.update_yaxes(title_text="Evidence count", row=1, col=2)
    fig.update_xaxes(tickangle=-25, row=1, col=2)
    _layout(fig, height=600)
    fig.update_layout(title="V2 recourse decision evidence")
    return fig


def v2_tradeoff(rows: Sequence[Mapping[str, object]]) -> go.Figure:
    pairs = _paired_groups(rows)
    cells = defaultdict(list)
    for key, v1, v2 in pairs:
        cells[key[:3]].append((v1, v2))
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Objective gain versus runtime overhead", "Energy and distance change"), horizontal_spacing=0.15)
    for env in ("du_outdoor", "synthetic"):
        points = []
        for (environment, task_count, uav_count), cell in cells.items():
            if environment != env:
                continue
            v1_runtime = _mean([pair[0] for pair in cell], "runtime_seconds")
            v2_runtime = _mean([pair[1] for pair in cell], "runtime_seconds")
            points.append((100.0 * (v2_runtime / v1_runtime - 1.0) if v1_runtime else 0.0, _mean([pair[1] for pair in cell], "objective_value") - _mean([pair[0] for pair in cell], "objective_value"), f"{task_count} tasks, {uav_count} UAVs"))
        fig.add_trace(go.Scatter(x=[point[0] for point in points], y=[point[1] for point in points], text=[point[2] for point in points], mode="markers", name="Synthetic" if env == "synthetic" else "DU outdoor", marker={"size": 11, "color": ENVIRONMENT_COLORS[env]}, hovertemplate="%{text}<br>Runtime overhead=%{x:.1f}%<br>Objective gain=%{y:.2f}<extra></extra>"), row=1, col=1)
    fig.add_hline(y=0, line_dash="dot", line_color=GRID, row=1, col=1)
    changes = []
    for env in ("du_outdoor", "synthetic"):
        env_cells = [(key, cell) for key, cell in cells.items() if key[0] == env]
        v1_energy = _mean([row for _, cell in env_cells for row, _ in cell], "total_energy")
        v2_energy = _mean([row for _, cell in env_cells for _, row in cell], "total_energy")
        v1_distance = _mean([row for _, cell in env_cells for row, _ in cell], "total_distance")
        v2_distance = _mean([row for _, cell in env_cells for _, row in cell], "total_distance")
        changes.append(("Synthetic" if env == "synthetic" else "DU outdoor", 100.0 * (v2_energy / v1_energy - 1.0), 100.0 * (v2_distance / v1_distance - 1.0), ENVIRONMENT_COLORS[env]))
    labels = [item[0] for item in changes]
    fig.add_trace(go.Bar(x=labels, y=[item[1] for item in changes], name="Total energy", marker_color=[item[3] for item in changes], offsetgroup="energy"), row=1, col=2)
    fig.add_trace(go.Bar(x=labels, y=[item[2] for item in changes], name="Distance", marker_color=[PURPLE, VERMILLION], opacity=0.72, offsetgroup="distance"), row=1, col=2)
    fig.update_xaxes(title_text="Runtime overhead (%)", row=1, col=1)
    fig.update_yaxes(title_text="Objective gain", row=1, col=1)
    fig.update_yaxes(title_text="Change versus V1 (%)", row=1, col=2)
    _layout(fig, height=620)
    fig.update_layout(title="V2 performance trade-offs", barmode="group")
    return fig


def write_all_charts(
    v1_metrics: Path = V1_METRICS,
    v2_metrics: Path = V2_METRICS,
    output_root: Path = CHART_ROOT,
) -> Dict[str, Path]:
    """Generate all eight report figures and return their paths."""

    v1_rows = _load_csv(Path(v1_metrics))
    v2_rows = _load_csv(Path(v2_metrics))
    v1_output = Path(output_root) / "v1"
    v2_output = Path(output_root) / "v2"
    v1_output.mkdir(parents=True, exist_ok=True)
    v2_output.mkdir(parents=True, exist_ok=True)
    figures = {
        "v1_workload_pressure": v1_workload_pressure(v1_rows),
        "v1_fleet_sensitivity": v1_fleet_sensitivity(v1_rows),
        "v1_runtime_bottleneck": v1_runtime_bottleneck(v1_rows),
        "v1_baseline_comparison": v1_baseline_comparison(v1_rows),
        "v2_environment_comparison": v2_environment_comparison(v2_rows),
        "v2_objective_gain_heatmap": v2_objective_gain_heatmap(v2_rows),
        "v2_recourse_decisions": v2_recourse_decisions(v2_rows),
        "v2_tradeoff": v2_tradeoff(v2_rows),
    }
    paths: Dict[str, Path] = {}
    for name, figure in figures.items():
        target = (v1_output if name.startswith("v1_") else v2_output) / f"{name}.pdf"
        figure.write_image(str(target), format="pdf")
        paths[name] = target
    manifest = {}
    manifest_root = Path(output_root).resolve()
    for name, path in paths.items():
        resolved_path = path.resolve()
        try:
            manifest[name] = str(resolved_path.relative_to(ROOT))
        except ValueError:
            manifest[name] = str(resolved_path.relative_to(manifest_root))
    (Path(output_root) / "chart_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return paths


if __name__ == "__main__":
    generated = write_all_charts()
    for name, path in generated.items():
        print(f"{name}: {path}")
