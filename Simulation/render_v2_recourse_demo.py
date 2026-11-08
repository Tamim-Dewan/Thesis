"""Render one compact PGBM V2 recourse episode for supervisor demonstration."""

import argparse
import html
from pathlib import Path

import plotly.graph_objects as go

from pgbm_sim.disaster_scene import plot_disaster_scene
from pgbm_sim.v2.experiment import V2ExperimentConfig, run_paired_episode


def _route_trace(name, route, color, dash="solid", width=7):
    points = tuple(tuple(point) for point in route)
    return go.Scatter3d(
        x=[point[0] for point in points],
        y=[point[1] for point in points],
        z=[point[2] for point in points],
        mode="lines",
        name=name,
        line={"color": color, "width": width, "dash": dash},
        hoverinfo="name",
    )


def _marker_trace(name, point, color, symbol, size=10, text=None):
    point = tuple(point)
    return go.Scatter3d(
        x=[point[0]],
        y=[point[1]],
        z=[point[2]],
        mode="markers+text" if text else "markers",
        text=[text] if text else None,
        textposition="top center",
        name=name,
        marker={"color": color, "size": size, "symbol": symbol},
        hovertemplate="<b>%s</b><extra></extra>" % html.escape(name),
    )


def _find_old_route(v2_result, decision):
    selected_uav = decision.selected_uav_id
    displaced = decision.displaced_task_id
    candidates = []
    for plan in v2_result.dispatch_plans:
        planning_time = float(plan.metadata.get("planning_time", 0.0))
        if planning_time > decision.trigger_time + 1e-7:
            continue
        for assignment in plan.assignments:
            if assignment.uav_id != selected_uav or displaced not in assignment.task_ids:
                continue
            return assignment.route
        candidates.append(plan)
    for plan in reversed(candidates):
        for assignment in plan.assignments:
            if assignment.uav_id == selected_uav:
                return assignment.route
    return ()


def _decision_row(decision):
    if decision.accepted:
        return (
            decision.trigger_time,
            decision.new_task_id,
            "Accepted",
            "{} → {}".format(decision.displaced_task_id, decision.selected_uav_id),
            "ΔJ = {:.3f}".format(decision.delta_value),
        )
    return (
        decision.trigger_time,
        decision.new_task_id,
        "Rejected",
        "Queue retained",
        decision.reason,
    )


def render_demo(output_path: Path, mode: str, seed: int, task_count: int, uav_count: int) -> None:
    config = V2ExperimentConfig(max_pending_tasks=8, max_candidate_plans=50000)
    _, _, payload = run_paired_episode(mode, seed, task_count, uav_count, config)
    scenario, _, v2 = payload

    accepted = next(
        (decision for decision in v2.recourse_decisions if decision.accepted),
        None,
    )
    if accepted is None:
        raise RuntimeError("demo episode did not contain an accepted replacement")
    selected = next(
        candidate
        for candidate in accepted.candidates
        if candidate.uav_id == accepted.selected_uav_id
        and candidate.displaced_task_id == accepted.displaced_task_id
    )

    figure = plot_disaster_scene(
        scenario.scene,
        tasks=scenario.tasks,
        show_context=False,
        show_candidate_sites=False,
        show_elevation_guides=False,
    )
    figure.update_layout(
        title={
            "text": "PGBM V2 recourse demo · {} · seed {}".format(mode, seed),
            "x": 0.5,
            "xanchor": "center",
            "font": {"size": 20, "color": "#1e3a5f"},
        },
        height=760,
        margin={"l": 0, "r": 0, "t": 60, "b": 0},
        legend={"orientation": "h", "y": 0.01, "x": 0.02},
    )

    old_route = _find_old_route(v2, accepted)
    if old_route:
        figure.add_trace(_route_trace("Before replacement", old_route, "#64748b", "dash", 5))
    figure.add_trace(_route_trace("After replacement", selected.route, "#2563eb", "solid", 8))
    if selected.projection is not None:
        figure.add_trace(
            _marker_trace(
                "Current UAV position",
                selected.projection.position,
                "#f97316",
                "diamond",
                12,
                "{} at t={:.1f}".format(accepted.selected_uav_id, accepted.trigger_time),
            )
        )
    task_by_id = {task.identifier: task for task in scenario.tasks}
    figure.add_trace(
        _marker_trace(
            "New task {}".format(accepted.new_task_id),
            task_by_id[accepted.new_task_id].dropoff_waypoint,
            "#16a34a",
            "diamond",
            12,
            accepted.new_task_id,
        )
    )
    figure.add_trace(
        _marker_trace(
            "Displaced task {}".format(accepted.displaced_task_id),
            task_by_id[accepted.displaced_task_id].dropoff_waypoint,
            "#dc2626",
            "x",
            12,
            accepted.displaced_task_id,
        )
    )

    rows = [_decision_row(decision) for decision in v2.recourse_decisions[:10]]
    table_rows = "".join(
        "<tr><td>{:.2f}</td><td>{}</td><td class='{}'>{}</td><td>{}</td><td>{}</td></tr>".format(
            time_value,
            html.escape(task_id),
            "accepted" if status == "Accepted" else "rejected",
            status,
            html.escape(action),
            html.escape(detail),
        )
        for time_value, task_id, status, action, detail in rows
    )
    summary = """
    <div class="summary">
      <div><b>Episode:</b> {} · seed {} · {} tasks · {} UAVs</div>
      <div><b>V2 objective:</b> {:.3f} &nbsp; <b>Served:</b> {} &nbsp; <b>Accepted:</b> {} &nbsp; <b>Rejected:</b> {}</div>
      <div class="explain"><b>Highlighted decision:</b> at t={:.2f}, {} replaced {} on {} with ΔJ = {:.3f}; the displaced task returned to the waiting queue.</div>
    </div>
    """.format(
        mode,
        seed,
        task_count,
        uav_count,
        v2.objective_value,
        len(v2.served_task_ids),
        v2.accepted_replacements,
        v2.rejected_replacements,
        accepted.trigger_time,
        accepted.new_task_id,
        accepted.displaced_task_id,
        accepted.selected_uav_id,
        accepted.delta_value,
    )
    table = """
    <h2>Recourse decision trace</h2>
    <table>
      <thead><tr><th>Trigger time</th><th>New task</th><th>Decision</th><th>Assignment</th><th>Reason / gain</th></tr></thead>
      <tbody>{}</tbody>
    </table>
    """.format(table_rows)
    body = figure.to_html(include_plotlyjs=True, full_html=False)
    document = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>PGBM V2 recourse demo</title>
<style>
body {{ margin:0; font-family: Arial, sans-serif; color:#0f172a; background:#f8fafc; }}
main {{ max-width:1400px; margin:0 auto; padding:18px 24px 42px; }}
.summary {{ background:white; border:1px solid #cbd5e1; border-left:6px solid #2563eb; padding:14px 18px; line-height:1.65; margin:0 0 14px; }}
.explain {{ color:#334155; margin-top:5px; }}
h2 {{ color:#1e3a5f; margin:26px 0 10px; }}
table {{ width:100%; border-collapse:collapse; background:white; font-size:14px; }}
th, td {{ border:1px solid #cbd5e1; padding:8px 10px; text-align:left; }}
th {{ background:#e2e8f0; }}
.accepted {{ color:#15803d; font-weight:700; }}
.rejected {{ color:#b91c1c; font-weight:700; }}
</style></head><body><main>{}{}</main></body></html>""".format(summary, body + table)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", default="du_outdoor", choices=("du_outdoor", "synthetic"))
    parser.add_argument("--seed", type=int, default=102)
    parser.add_argument("--task-count", type=int, default=30)
    parser.add_argument("--uav-count", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render_demo(args.output, args.mode, args.seed, args.task_count, args.uav_count)
    print("V2 recourse demo: {}".format(args.output))


if __name__ == "__main__":
    main()
