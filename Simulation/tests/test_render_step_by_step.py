import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from render_step_by_step import (
    SERVICE_HOLD_FRAME_COUNT,
    _build_uav_timeline,
    _execution_snapshots,
    _expand_service_holds,
    _interpolate_route,
    _service_popup_annotations,
    _status_title,
    _timeline_state,
    render_step_by_step,
)
from pgbm_sim import load_scenario


def test_interpolation_follows_the_route_polyline_instead_of_a_direct_line():
    route = ((0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0))

    point, edge_index, next_index = _interpolate_route(route, 0, 2, 0.75)

    assert point == (10.0, 5.0, 0.0)
    assert edge_index == 1
    assert next_index == 2


def test_uav_timeline_contains_flight_service_and_return_segments():
    base = (0.0, 0.0, 0.0)
    assignment = {
        "uav_id": "uav_1",
        "task_ids": ["task_1"],
        "route": [base, (10.0, 0.0, 0.0), (10.0, 10.0, 0.0), base],
    }
    events = [
        {"uav_id": "uav_1", "task_id": "task_1", "event": "arrive", "time": 10.0, "position": [10.0, 10.0, 0.0]},
        {"uav_id": "uav_1", "task_id": "task_1", "event": "service_complete", "time": 12.0, "position": [10.0, 10.0, 0.0]},
        {"uav_id": "uav_1", "task_id": None, "event": "return_to_base", "time": 22.0, "position": list(base)},
    ]

    timeline = _build_uav_timeline(assignment, events, base, 0.0)

    assert [segment["kind"] for segment in timeline["segments"]] == [
        "flight",
        "service",
        "return",
    ]
    assert timeline["segments"][0]["start_index"] == 0
    assert timeline["segments"][0]["end_index"] == 2
    assert timeline["segments"][-1]["end_time"] == 22.0


def test_timeline_state_interpolates_position_and_marks_service_pause():
    base = (0.0, 0.0, 0.0)
    assignment = {
        "uav_id": "uav_1",
        "task_ids": ["task_1"],
        "route": [base, (10.0, 0.0, 0.0), (10.0, 10.0, 0.0), base],
    }
    events = [
        {"uav_id": "uav_1", "task_id": "task_1", "event": "arrive", "time": 10.0, "position": [10.0, 10.0, 0.0]},
        {"uav_id": "uav_1", "task_id": "task_1", "event": "service_complete", "time": 12.0, "position": [10.0, 10.0, 0.0]},
        {"uav_id": "uav_1", "task_id": None, "event": "return_to_base", "time": 22.0, "position": list(base)},
    ]
    timeline = _build_uav_timeline(assignment, events, base, 0.0)

    in_flight = _timeline_state(timeline, 5.0)
    servicing = _timeline_state(timeline, 11.0)

    assert in_flight["kind"] == "flying"
    assert in_flight["position"] == (10.0, 0.0, 0.0)
    assert in_flight["active_leg"] == ((10.0, 0.0, 0.0), (10.0, 10.0, 0.0))
    assert servicing["kind"] == "servicing"
    assert servicing["task_id"] == "task_1"
    assert servicing["position"] == (10.0, 10.0, 0.0)


def test_status_title_exposes_phase_time_event_and_progress():
    title = _status_title(
        "Flight",
        34.5,
        "UAV 1 flying to task_1",
        1,
        4,
        6,
        "UAV 1: flying (task_1)",
        "Dashed route = planned",
    )

    assert "Initial solution replay" in title
    assert "Flight" in title
    assert "Simulation time" in title
    assert "34.5" in title
    assert "Progress" in title
    assert "1/6 served" in title


def test_arrival_snapshot_contains_a_popup_for_the_serving_uav():
    base = (0.0, 0.0, 0.0)
    assignment = {
        "uav_id": "uav_1",
        "task_ids": ["task_1"],
        "route": [base, (10.0, 0.0, 0.0)],
    }
    events = [
        {"uav_id": "uav_1", "task_id": "task_1", "event": "arrive", "time": 10.0, "position": [10.0, 0.0, 0.0]},
        {"uav_id": "uav_1", "task_id": "task_1", "event": "service_complete", "time": 12.0, "position": [10.0, 0.0, 0.0]},
        {"uav_id": "uav_1", "task_id": None, "event": "return_to_base", "time": 22.0, "position": list(base)},
    ]

    timeline = _build_uav_timeline(assignment, events, base, 0.0)
    assert timeline["segments"]

    popup = {
        "uav_id": "uav_1",
        "task_id": "task_1",
        "position": (10.0, 0.0, 0.0),
    }
    annotations = _service_popup_annotations([popup])

    assert len(annotations) == 1
    assert annotations[0]["text"] == "UAV 1 is serving task_1"
    assert annotations[0]["showarrow"] is True
    assert annotations[0]["x"] == 10.0


def test_service_hold_repeats_only_arrival_frames_and_hides_duplicates_from_slider():
    snapshots = [
        {"name": "flight", "service_popups": []},
        {
            "name": "arrival",
            "service_popups": [
                {"uav_id": "uav_1", "task_id": "task_1", "position": (1.0, 2.0, 3.0)}
            ],
        },
    ]

    expanded = _expand_service_holds(snapshots)

    assert len(expanded) == 1 + SERVICE_HOLD_FRAME_COUNT
    assert expanded[0]["name"] == "flight"
    assert expanded[1]["name"] == "arrival"
    assert all(not item.get("show_in_slider", True) for item in expanded[2:])


@pytest.mark.parametrize(
    "report_name",
    ["du_outdoor_initial.json", "synthetic_initial.json"],
)
def test_rendered_replay_contains_intermediate_frames_and_compact_ui(tmp_path, report_name):
    results_dir = (
        Path(__file__).parents[1]
        / "results"
        / "initial_runs"
        / "session_2026-09-27"
    )
    report_path = results_dir / report_name
    report = json.loads(report_path.read_text(encoding="utf-8"))
    scenario = load_scenario(results_dir / Path(report["scenario_file"]).name)
    assignment_state = {
        assignment["uav_id"]: assignment["task_ids"]
        for assignment in report["initial_plan"]["assignments"]
    }
    routes = {
        assignment["uav_id"]: assignment["route"]
        for assignment in report["initial_plan"]["assignments"]
        if assignment["task_ids"]
    }

    snapshots = _execution_snapshots(report, scenario, assignment_state, routes)
    output_path = tmp_path / "replay.html"
    render_step_by_step(report_path, output_path)
    html = output_path.read_text(encoding="utf-8")

    assert len(snapshots) > len(report["execution"]["events"])
    assert any(snapshot["active_legs"] for snapshot in snapshots)
    assert any(snapshot["service_popups"] for snapshot in snapshots)
    assert "Initial solution replay" in html
    assert "Simulation time" in html
    assert "is serving task_" in html
    assert "Arrival hold: 5 s" in html
    assert "dashed = planned route" in html
    assert "active leg" in html
    assert '"showlegend":false' in html
