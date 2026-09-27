"""Render an initial simulation report with task assignments and UAV routes."""

import argparse
import json
from pathlib import Path

from pgbm_sim import load_scenario, plot_disaster_scene


def _scenario_path(report_path: Path, stored_path: str) -> Path:
    candidates = (
        Path(stored_path),
        report_path.parent / Path(stored_path).name,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("scenario file not found: {}".format(stored_path))


def render_report(report_path: Path, output_path: Path) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    scenario = load_scenario(_scenario_path(report_path, report["scenario_file"]))
    plan = report["initial_plan"]
    routes = {
        assignment["uav_id"]: tuple(tuple(point) for point in assignment["route"])
        for assignment in plan["assignments"]
        if assignment["task_ids"]
    }
    task_assignees = {
        task_id: assignment["uav_id"]
        for assignment in plan["assignments"]
        for task_id in assignment["task_ids"]
    }
    task_assignees.update({task_id: "unassigned" for task_id in plan["unassigned_task_ids"]})
    figure = plot_disaster_scene(
        scenario.scene,
        tasks=scenario.tasks,
        routes=routes,
        task_assignees=task_assignees,
    )
    execution = report["execution"]
    figure.update_layout(
        title={
            "text": (
                "{} initial snapshot at t = {}<br>"
                "<sup>Planner: {} | Eligible tasks: {} | Served: {} | Missed: {} | "
                "Distance: {:.1f} m | Energy: {:.1f} | Recourse: disabled</sup>"
            ).format(
                scenario.scenario_id,
                plan["metadata"]["planning_time"],
                plan["method"],
                plan["metadata"]["eligible_task_count"],
                len(execution["served_task_ids"]),
                len(execution["missed_task_ids"]),
                execution["total_distance"],
                execution["total_energy"],
            ),
            "x": 0.5,
        }
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(str(output_path), include_plotlyjs=True, full_html=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or args.report.with_name(args.report.stem + "_visual.html")
    render_report(args.report, output)
    print("Initial solution view: {}".format(output))


if __name__ == "__main__":
    main()
