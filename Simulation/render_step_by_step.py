"""Render an initial solution as a readable assignment and mission replay."""

import argparse
import html
import json
import math
from pathlib import Path
from typing import Iterable, Optional, Sequence

import plotly.graph_objects as go

from pgbm_sim import load_scenario, plot_disaster_scene


UAV_COLORS = ("#2563eb", "#db2777", "#059669", "#d97706", "#7c3aed", "#0891b2")
STATUS_COLORS = {
    "pending": "#94a3b8",
    "assigned": "#2563eb",
    "active": "#f59e0b",
    "served": "#16a34a",
    "unassigned": "#dc2626",
}
STATUS_SYMBOLS = {
    "pending": "circle-open",
    "assigned": "circle",
    "active": "diamond-open",
    "served": "diamond",
    "unassigned": "x",
}
EXECUTION_STEP_SECONDS = 2.0
PLAY_FRAME_DURATION_MS = 625
PLAY_TRANSITION_DURATION_MS = 140
SERVICE_HOLD_SECONDS = 5.0
SERVICE_HOLD_FRAME_COUNT = max(
    1,
    int(round(SERVICE_HOLD_SECONDS * 1000 / PLAY_FRAME_DURATION_MS)),
)
TIME_EPSILON = 1e-7
EVENT_TIME_EPSILON = 1e-5


def _scenario_path(report_path: Path, stored_path: str) -> Path:
    candidates = (
        Path(stored_path),
        report_path.parent / Path(stored_path).name,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("scenario file not found: {}".format(stored_path))


def _uav_label(uav_id: str) -> str:
    if uav_id.startswith("uav_"):
        return "UAV {}".format(uav_id.split("_")[-1])
    return uav_id


def _friendly(value: object) -> str:
    return str(value).replace("_", " ").replace("-", " ")


def _uav_color(uav_id: str) -> str:
    try:
        index = int(uav_id.split("_")[-1]) - 1
    except (TypeError, ValueError):
        index = 0
    return UAV_COLORS[index % len(UAV_COLORS)]


def _rgba(hex_color: str, alpha: float) -> str:
    color = hex_color.lstrip("#")
    red, green, blue = (int(color[index:index + 2], 16) for index in (0, 2, 4))
    return "rgba({}, {}, {}, {})".format(red, green, blue, alpha)


def _same_point(first: Sequence[float], second: Sequence[float]) -> bool:
    return len(first) == len(second) and all(
        abs(float(left) - float(right)) <= 1e-7
        for left, right in zip(first, second)
    )


def _task_state(
    scenario,
    assignment_state,
    unassigned,
    served=(),
    active_task=None,
    active_tasks=(),
):
    served = set(served)
    unassigned = set(unassigned)
    active = set(active_tasks)
    if active_task is not None:
        active.add(active_task)
    assigned = {
        task_id: uav_id
        for uav_id, task_ids in assignment_state.items()
        for task_id in task_ids
    }
    state = {}
    for task in scenario.tasks:
        if task.identifier in served:
            state[task.identifier] = "served"
        elif task.identifier in active:
            state[task.identifier] = "active"
        elif task.identifier in unassigned:
            state[task.identifier] = "unassigned"
        elif task.identifier in assigned:
            state[task.identifier] = "assigned"
        else:
            state[task.identifier] = "pending"
    return state, assigned


def _task_trace(
    scenario,
    states,
    assigned,
    current_service_values,
    show_labels=False,
):
    points = []
    colors = []
    symbols = []
    sizes = []
    hover = []
    labels = []
    for task in scenario.tasks:
        status = states[task.identifier]
        uav_id = assigned.get(task.identifier, "none")
        priority = current_service_values.get(task.identifier, 0.0)
        if status in {"active", "served", "pending", "unassigned"}:
            color = STATUS_COLORS[status]
        else:
            color = _uav_color(uav_id)
        points.append(task.survivor_position)
        colors.append(color)
        symbols.append(STATUS_SYMBOLS[status])
        sizes.append(12 if status == "active" else 8)
        labels.append(
            task.identifier
            if status == "active" or (show_labels and status == "assigned")
            else ""
        )
        hover.append(
            "<b>{}</b><br>Status: {}<br>Assigned UAV: {}<br>"
            "Current service value: {:.3f}<br>Detected at: {:.1f}<extra></extra>".format(
                html.escape(task.identifier),
                html.escape(_friendly(status).title()),
                html.escape(_uav_label(uav_id) if uav_id != "none" else "None"),
                priority,
                task.detected_at,
            )
        )
    return go.Scatter3d(
        x=[point[0] for point in points],
        y=[point[1] for point in points],
        z=[point[2] for point in points],
        mode="markers+text",
        text=labels,
        textposition="top center",
        name="task state",
        marker={"size": sizes, "color": colors, "symbol": symbols},
        hovertext=hover,
        hoverinfo="text",
        legendgroup="task-state",
        showlegend=False,
    )


def _dropoff_trace(scenario):
    points = [task.dropoff_waypoint for task in scenario.tasks]
    return go.Scatter3d(
        x=[point[0] for point in points],
        y=[point[1] for point in points],
        z=[point[2] for point in points],
        mode="markers",
        text=["{} drop off waypoint".format(task.identifier) for task in scenario.tasks],
        name="drop off waypoint",
        marker={"size": 5, "color": "#0891b2", "symbol": "diamond", "opacity": 0.72},
        hovertext=[
            "<b>{}</b><br>UAV drop off waypoint<extra></extra>".format(
                html.escape(task.identifier)
            )
            for task in scenario.tasks
        ],
        hoverinfo="text",
        legendgroup="drop-off",
        showlegend=False,
    )


def _dropoff_guides(scenario):
    x, y, z = [], [], []
    for task in scenario.tasks:
        survivor = task.survivor_position
        dropoff = task.dropoff_waypoint
        x.extend((survivor[0], dropoff[0], None))
        y.extend((survivor[1], dropoff[1], None))
        z.extend((survivor[2], dropoff[2], None))
    return go.Scatter3d(
        x=x,
        y=y,
        z=z,
        mode="lines",
        name="drop off guide",
        line={"color": "rgba(8, 145, 178, 0.28)", "width": 2, "dash": "dash"},
        hoverinfo="skip",
        legendgroup="drop-off",
        showlegend=False,
    )


def _route_trace(uav_id, points, style="planned"):
    points = tuple(tuple(point) for point in points)
    color = _uav_color(uav_id)
    if style == "planned":
        line = {"width": 3, "color": _rgba(color, 0.34), "dash": "dash"}
        name = "{} planned route".format(_uav_label(uav_id))
    elif style == "travelled":
        line = {"width": 7, "color": color, "dash": "solid"}
        name = "{} travelled route".format(_uav_label(uav_id))
    else:
        line = {"width": 10, "color": "#f97316", "dash": "solid"}
        name = "{} active leg".format(_uav_label(uav_id))
    return go.Scatter3d(
        x=[point[0] for point in points],
        y=[point[1] for point in points],
        z=[point[2] for point in points],
        mode="lines",
        name=name,
        line=line,
        hovertext=[name] * len(points),
        hoverinfo="text" if points else "skip",
        legendgroup="route-{}-{}".format(uav_id, style),
        showlegend=False,
    )


def _position_trace(
    positions,
    active_uavs,
    uav_states=None,
    uav_tasks=None,
):
    uav_states = uav_states or {}
    uav_tasks = uav_tasks or {}
    uav_ids = sorted(positions)
    points = [positions[uav_id] for uav_id in uav_ids]
    colors = [_uav_color(uav_id) for uav_id in uav_ids]
    sizes = [13 if uav_id in active_uavs else 9 for uav_id in uav_ids]
    hover = []
    for uav_id in uav_ids:
        state = uav_states.get(uav_id, "at base")
        task_id = uav_tasks.get(uav_id)
        task_suffix = "<br>Task: {}".format(html.escape(task_id)) if task_id else ""
        hover.append(
            "<b>{}</b><br>State: {}{}<extra></extra>".format(
                html.escape(_uav_label(uav_id)),
                html.escape(state),
                task_suffix,
            )
        )
    return go.Scatter3d(
        x=[point[0] for point in points],
        y=[point[1] for point in points],
        z=[point[2] for point in points],
        mode="markers+text",
        text=[_uav_label(uav_id) for uav_id in uav_ids],
        textposition="top center",
        name="UAV position",
        marker={
            "size": sizes,
            "color": colors,
            "symbol": "circle",
            "line": {"color": "white", "width": 1},
        },
        hovertext=hover,
        hoverinfo="text",
        legendgroup="uav-position",
        showlegend=False,
    )


def _candidate_summary(decision):
    parts = []
    for candidate in decision["candidates"]:
        uav_id = candidate["uav_id"]
        if candidate["feasible"]:
            parts.append(
                "{} ✓ {:.1f} m".format(
                    _uav_label(uav_id),
                    candidate["marginal_distance"],
                )
            )
        else:
            reasons = ", ".join(_friendly(reason) for reason in candidate.get("reasons", ()))
            parts.append(
                "{} ✕ {}".format(
                    _uav_label(uav_id),
                    reasons or "rejected",
                )
            )
    return " · ".join(parts)


def _title(text):
    return {
        "text": text,
        "x": 0.5,
        "xanchor": "center",
        "y": 0.985,
        "yanchor": "top",
        "font": {
            "family": "Arial, sans-serif",
            "size": 18,
            "color": "#1e3a5f",
        },
    }


def _status_title(
    phase: str,
    simulation_time: float,
    event_text: str,
    served_count: int,
    assigned_count: int,
    total_tasks: int,
    fleet_text: str,
    detail: str = "",
) -> str:
    lines = [
        "<b>Initial solution replay</b> "
        "<span style='font-size:14px;color:#64748b'>· {}</span>".format(
            html.escape(phase)
        ),
        "<span style='font-size:13px'><b>Simulation time</b> t = {:.1f} s "
        "&nbsp; | &nbsp; <b>Event</b> {}</span>".format(
            simulation_time,
            html.escape(event_text),
        ),
        "<span style='font-size:12px;color:#475569'><b>Progress</b> "
        "{}/{} served &nbsp; | &nbsp; {}/{} assigned &nbsp; | &nbsp; {}</span>".format(
            served_count,
            total_tasks,
            assigned_count,
            total_tasks,
            html.escape(fleet_text),
        ),
    ]
    if detail:
        lines.append(
            "<span style='font-size:12px;color:#64748b'>{}</span>".format(
                html.escape(detail)
            )
        )
    return "<br>".join(lines)


def _route_index(route: Sequence[Sequence[float]], start_index: int, target) -> Optional[int]:
    for index in range(start_index + 1, len(route)):
        if _same_point(route[index], target):
            return index
    if start_index < len(route) and _same_point(route[start_index], target):
        return start_index
    return None


def _distance(first: Sequence[float], second: Sequence[float]) -> float:
    return math.sqrt(sum((float(first[index]) - float(second[index])) ** 2 for index in range(3)))


def _interpolate_route(
    route: Sequence[Sequence[float]],
    start_index: int,
    end_index: int,
    fraction: float,
):
    if not route:
        return (0.0, 0.0, 0.0), start_index, None
    start_index = max(0, min(start_index, len(route) - 1))
    end_index = max(start_index, min(end_index, len(route) - 1))
    if end_index == start_index:
        return tuple(route[start_index]), end_index, None
    fraction = max(0.0, min(1.0, fraction))
    if fraction <= TIME_EPSILON:
        return tuple(route[start_index]), start_index, start_index + 1
    if fraction >= 1.0 - TIME_EPSILON:
        return tuple(route[end_index]), end_index, None
    leg_lengths = [
        _distance(route[index], route[index + 1])
        for index in range(start_index, end_index)
    ]
    total_length = sum(leg_lengths)
    if total_length <= TIME_EPSILON:
        return tuple(route[end_index]), end_index, None
    target_distance = total_length * fraction
    travelled = 0.0
    for offset, leg_length in enumerate(leg_lengths):
        index = start_index + offset
        if (
            target_distance < travelled + leg_length - TIME_EPSILON
            or offset == len(leg_lengths) - 1
        ):
            local = 0.0 if leg_length <= TIME_EPSILON else (target_distance - travelled) / leg_length
            local = max(0.0, min(1.0, local))
            first = route[index]
            second = route[index + 1]
            point = tuple(
                float(first[axis]) + (float(second[axis]) - float(first[axis])) * local
                for axis in range(3)
            )
            return point, index, index + 1
        travelled += leg_length
    return tuple(route[end_index]), end_index, None


def _build_uav_timeline(assignment, events, base, start_time):
    route = tuple(tuple(point) for point in assignment.get("route", (base,)))
    if not route:
        route = (tuple(base),)
    uav_events = sorted(
        [event for event in events if event["uav_id"] == assignment["uav_id"]],
        key=lambda event: event["time"],
    )
    segments = []
    current_time = float(start_time)
    route_index = 0
    for task_id in assignment.get("task_ids", ()):
        arrival = next(
            (
                event
                for event in uav_events
                if event["task_id"] == task_id and event["event"] == "arrive"
            ),
            None,
        )
        if arrival is None:
            continue
        target = tuple(arrival["position"])
        target_index = _route_index(route, route_index, target)
        if target_index is None:
            route = route[:route_index + 1] + (target,) + route[route_index + 1:]
            target_index = route_index + 1
        arrival_time = float(arrival["time"])
        if arrival_time > current_time + TIME_EPSILON:
            segments.append(
                {
                    "kind": "flight",
                    "start_time": current_time,
                    "end_time": arrival_time,
                    "start_index": route_index,
                    "end_index": target_index,
                    "task_id": task_id,
                }
            )
        current_time = arrival_time
        completion = next(
            (
                event
                for event in uav_events
                if event["task_id"] == task_id
                and event["time"] >= arrival_time - TIME_EPSILON
                and event["event"] in {"service_complete", "service_unavailable"}
            ),
            None,
        )
        if completion is not None:
            completion_time = float(completion["time"])
            if completion_time > current_time + TIME_EPSILON:
                segments.append(
                    {
                        "kind": "service",
                        "start_time": current_time,
                        "end_time": completion_time,
                        "start_index": target_index,
                        "end_index": target_index,
                        "task_id": task_id,
                    }
                )
            current_time = completion_time
        route_index = target_index

    return_event = next(
        (event for event in uav_events if event["event"] == "return_to_base"),
        None,
    )
    if return_event is not None:
        return_time = float(return_event["time"])
        return_index = _route_index(route, route_index, base)
        if return_index is None:
            route = route[:route_index + 1] + (tuple(base),)
            return_index = len(route) - 1
        if return_time > current_time + TIME_EPSILON:
            segments.append(
                {
                    "kind": "return",
                    "start_time": current_time,
                    "end_time": return_time,
                    "start_index": route_index,
                    "end_index": return_index,
                    "task_id": None,
                }
            )
        current_time = return_time

    return {
        "uav_id": assignment["uav_id"],
        "route": route,
        "base": tuple(base),
        "start_time": float(start_time),
        "end_time": current_time,
        "segments": segments,
    }


def _timeline_state(timeline, simulation_time):
    route = timeline["route"]
    if simulation_time < timeline["start_time"] - TIME_EPSILON:
        return {
            "position": timeline["base"],
            "kind": "idle",
            "task_id": None,
            "progress_index": 0,
            "active_leg": (),
        }
    for segment in timeline["segments"]:
        start = segment["start_time"]
        end = segment["end_time"]
        if simulation_time < start - TIME_EPSILON:
            break
        if simulation_time >= end - TIME_EPSILON:
            continue
        if segment["kind"] == "service":
            return {
                "position": tuple(route[segment["end_index"]]),
                "kind": "servicing",
                "task_id": segment["task_id"],
                "progress_index": segment["end_index"],
                "active_leg": (),
            }
        duration = max(end - start, TIME_EPSILON)
        fraction = (simulation_time - start) / duration
        position, edge_index, next_index = _interpolate_route(
            route,
            segment["start_index"],
            segment["end_index"],
            fraction,
        )
        active_leg = ()
        if next_index is not None and next_index < len(route):
            active_leg = (position, tuple(route[next_index]))
        return {
            "position": position,
            "kind": "returning" if segment["kind"] == "return" else "flying",
            "task_id": segment["task_id"],
            "progress_index": edge_index,
            "active_leg": active_leg,
        }
    return {
        "position": tuple(route[-1]),
        "kind": "at base" if _same_point(route[-1], timeline["base"]) else "complete",
        "task_id": None,
        "progress_index": len(route) - 1,
        "active_leg": (),
    }


def _travelled_route(timeline, state):
    route = timeline["route"]
    if not route:
        return ()
    progress_index = max(0, min(int(state["progress_index"]), len(route) - 1))
    points = list(route[:progress_index + 1])
    if not points or not _same_point(points[-1], state["position"]):
        points.append(tuple(state["position"]))
    return tuple(points)


def _event_description(event) -> str:
    uav = _uav_label(event["uav_id"])
    task = event.get("task_id") or "base"
    event_name = event["event"]
    if event_name == "arrive":
        return "{} arrived at {}".format(uav, task)
    if event_name == "service_complete":
        return "{} completed {}".format(uav, task)
    if event_name == "service_unavailable":
        return "{} could not serve {}".format(uav, task)
    if event_name == "return_to_base":
        return "{} returned to base".format(uav)
    return "{} {} {}".format(uav, _friendly(event_name), task)


def _service_popup_annotations(popups):
    annotations = []
    for popup in popups:
        position = popup["position"]
        message = "{} is serving {}".format(
            _uav_label(popup["uav_id"]),
            popup["task_id"],
        )
        annotations.append(
            {
                "x": position[0],
                "y": position[1],
                "z": position[2],
                "text": message,
                "showarrow": True,
                "arrowhead": 2,
                "arrowsize": 1,
                "arrowwidth": 2,
                "arrowcolor": "#f97316",
                "ax": 0,
                "ay": -52,
                "font": {"size": 13, "color": "#7c2d12"},
                "bgcolor": "rgba(255, 247, 237, 0.96)",
                "bordercolor": "#f97316",
                "borderwidth": 2,
                "borderpad": 5,
            }
        )
    return annotations


def _expand_service_holds(snapshots):
    """Repeat arrival frames so the service message remains visible for five seconds."""
    expanded = []
    for snapshot in snapshots:
        expanded.append(snapshot)
        if not snapshot.get("service_popups"):
            continue
        for hold_index in range(1, SERVICE_HOLD_FRAME_COUNT):
            hold = dict(snapshot)
            hold["name"] = "{}_hold_{}".format(snapshot["name"], hold_index)
            hold["show_in_slider"] = False
            expanded.append(hold)
    return expanded


def _execution_snapshots(report, scenario, final_assignment_state, final_routes):
    base = tuple(scenario.scene.environment.base.position)
    start_time = float(report["initial_plan"]["metadata"]["planning_time"])
    events = sorted(
        report["execution"]["events"],
        key=lambda event: (event["time"], event["uav_id"], event["event"]),
    )
    assignments = report["initial_plan"]["assignments"]
    timelines = {
        assignment["uav_id"]: _build_uav_timeline(assignment, events, base, start_time)
        for assignment in assignments
    }
    event_times = [float(event["time"]) for event in events]
    end_time = max(event_times or [start_time])
    times = {round(start_time, 6), round(end_time, 6)}
    current = start_time
    while current < end_time - TIME_EPSILON:
        times.add(round(current, 6))
        current += EXECUTION_STEP_SECONDS
    times.update(round(time, 6) for time in event_times)
    ordered_times = sorted(times)
    snapshots = []
    uav_ids = [assignment["uav_id"] for assignment in assignments]
    total_tasks = len(scenario.tasks)
    for index, simulation_time in enumerate(ordered_times):
        states_by_uav = {
            uav_id: _timeline_state(timelines[uav_id], simulation_time)
            for uav_id in uav_ids
        }
        positions = {
            uav_id: state["position"]
            for uav_id, state in states_by_uav.items()
        }
        active_uavs = {
            uav_id
            for uav_id, state in states_by_uav.items()
            if state["kind"] in {"flying", "servicing", "returning"}
        }
        active_tasks = {
            state["task_id"]
            for state in states_by_uav.values()
            if state["task_id"] is not None
        }
        served = {
            event["task_id"]
            for event in events
            if event["event"] == "service_complete"
            and float(event["time"]) <= simulation_time + TIME_EPSILON
        }
        events_at_time = [
            event
            for event in events
            if abs(float(event["time"]) - simulation_time) <= EVENT_TIME_EPSILON
        ]
        if events_at_time:
            event_text = " · ".join(_event_description(event) for event in events_at_time)
        elif active_uavs:
            event_text = " · ".join(
                "{} {}{}".format(
                    _uav_label(uav_id),
                    state["kind"],
                    " to {}".format(state["task_id"]) if state["task_id"] else "",
                )
                for uav_id, state in states_by_uav.items()
                if uav_id in active_uavs
            )
        elif simulation_time <= start_time + TIME_EPSILON:
            event_text = "Mission begins"
        else:
            event_text = "All UAVs are at base"
        phase_names = []
        if any(state["kind"] == "flying" for state in states_by_uav.values()):
            phase_names.append("Flight")
        if any(state["kind"] == "servicing" for state in states_by_uav.values()):
            phase_names.append("Service")
        if any(state["kind"] == "returning" for state in states_by_uav.values()):
            phase_names.append("Return")
        phase = " + ".join(phase_names) if phase_names else "Mission complete"
        fleet_text = " · ".join(
            "{}: {}{}".format(
                _uav_label(uav_id),
                state["kind"],
                " ({})".format(state["task_id"]) if state["task_id"] else "",
            )
            for uav_id, state in states_by_uav.items()
        )
        task_states, assigned = _task_state(
            scenario,
            final_assignment_state,
            report["initial_plan"]["unassigned_task_ids"],
            served=served,
            active_tasks=active_tasks,
        )
        service_popups = [
            {
                "uav_id": event["uav_id"],
                "task_id": event["task_id"],
                "position": tuple(event["position"]),
            }
            for event in events_at_time
            if event["event"] == "arrive" and event.get("task_id")
        ]
        route_detail = "Dashed route = planned · solid route = travelled · orange segment = active leg"
        popup_detail = ""
        if service_popups:
            popup_detail = "Arrival hold: 5 s · {}".format(
                " · ".join(
                    "{} is serving {}".format(
                        _uav_label(popup["uav_id"]),
                        popup["task_id"],
                    )
                    for popup in service_popups
                )
            )
        detail = "{}{}".format(
            popup_detail,
            " · " if popup_detail else "",
        ) + route_detail
        snapshots.append(
            {
                "name": "execution_{}".format(index),
                "label": "t={:.1f} · {}".format(simulation_time, event_text),
                "phase": phase,
                "simulation_time": simulation_time,
                "event_text": event_text,
                "fleet_text": fleet_text,
                "detail": detail,
                "service_popups": service_popups,
                "states": task_states,
                "assigned": assigned,
                "served": served,
                "active_tasks": active_tasks,
                "positions": positions,
                "active_uavs": active_uavs,
                "uav_states": {
                    uav_id: state["kind"]
                    for uav_id, state in states_by_uav.items()
                },
                "uav_tasks": {
                    uav_id: state["task_id"]
                    for uav_id, state in states_by_uav.items()
                    if state["task_id"]
                },
                "planned_routes": final_routes,
                "travelled_routes": {
                    uav_id: _travelled_route(timelines[uav_id], state)
                    for uav_id, state in states_by_uav.items()
                },
                "active_legs": {
                    uav_id: state["active_leg"]
                    for uav_id, state in states_by_uav.items()
                    if state["active_leg"]
                },
                "title": _status_title(
                    phase,
                    simulation_time,
                    event_text,
                    len(served),
                    len(assigned),
                    total_tasks,
                    fleet_text,
                    detail,
                ),
            }
        )
    return snapshots


def _deemphasize_environment(figure) -> None:
    """Keep the environment visible while giving replay overlays priority."""
    for trace in figure.data:
        trace.showlegend = False
        if getattr(trace, "type", None) == "mesh3d":
            opacity = trace.opacity if trace.opacity is not None else 1.0
            trace.opacity = min(float(opacity), 0.58)


def _visual_key(uav_ids: Iterable[str]) -> str:
    uav_parts = [
        "<span style='color:{}'><b>{}</b></span>".format(
            _uav_color(uav_id),
            html.escape(_uav_label(uav_id)),
        )
        for uav_id in uav_ids
    ]
    return (
        "Visual key: {} &nbsp; | &nbsp; "
        "<span style='color:#64748b'>dashed = planned route</span> &nbsp; | &nbsp; "
        "<span style='color:#334155'>solid = travelled route</span> &nbsp; | &nbsp; "
        "<span style='color:#f97316'><b>orange = active leg</b></span>"
    ).format(" · ".join(uav_parts))


def _frame_data(snapshot, uav_ids, base, current_values):
    task_data = _task_trace(
        snapshot["scenario"],
        snapshot["states"],
        snapshot["assigned"],
        current_values,
        show_labels=snapshot["phase"] == "Assignment",
    )
    route_data = []
    for uav_id in uav_ids:
        route_data.extend(
            (
                _route_trace(uav_id, snapshot["planned_routes"].get(uav_id, (base,)), "planned"),
                _route_trace(uav_id, snapshot["travelled_routes"].get(uav_id, (base,)), "travelled"),
                _route_trace(uav_id, snapshot["active_legs"].get(uav_id, ()), "active"),
            )
        )
    position_data = _position_trace(
        snapshot["positions"],
        snapshot["active_uavs"],
        snapshot.get("uav_states"),
        snapshot.get("uav_tasks"),
    )
    return [task_data, *route_data, position_data]


def render_step_by_step(report_path: Path, output_path: Path) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    scenario = load_scenario(_scenario_path(report_path, report["scenario_file"]))
    plan = report["initial_plan"]
    trace = plan["metadata"].get("decision_trace", [])
    if not trace:
        raise ValueError("report does not contain planner decision_trace")

    figure = plot_disaster_scene(scenario.scene, show_elevation_guides=False)
    _deemphasize_environment(figure)
    figure.add_trace(_dropoff_guides(scenario))
    figure.add_trace(_dropoff_trace(scenario))
    base = tuple(scenario.scene.environment.base.position)
    uav_ids = [assignment["uav_id"] for assignment in plan["assignments"]]
    dynamic_indices = []
    task_index = len(figure.data)
    figure.add_trace(
        _task_trace(
            scenario,
            {task.identifier: "pending" for task in scenario.tasks},
            {},
            {},
        )
    )
    dynamic_indices.append(task_index)
    for uav_id in uav_ids:
        for style in ("planned", "travelled", "active"):
            dynamic_indices.append(len(figure.data))
            figure.add_trace(_route_trace(uav_id, (base,), style))
    position_index = len(figure.data)
    figure.add_trace(
        _position_trace(
            {uav_id: base for uav_id in uav_ids},
            set(),
            {uav_id: "at base" for uav_id in uav_ids},
        )
    )
    dynamic_indices.append(position_index)

    current_values = {
        task["task_id"]: task["current_service_value"]
        for task in trace
    }
    final_assignment_state = {
        assignment["uav_id"]: assignment["task_ids"]
        for assignment in plan["assignments"]
    }
    final_routes = {
        assignment["uav_id"]: assignment["route"]
        for assignment in plan["assignments"]
        if assignment["task_ids"]
    }
    total_tasks = len(scenario.tasks)
    assignment_frames = []
    initial_assignment_state = {
        assignment["uav_id"]: () for assignment in plan["assignments"]
    }
    initial_states, initial_assigned = _task_state(
        scenario,
        initial_assignment_state,
        plan["unassigned_task_ids"],
    )
    initial_fleet = " · ".join("{}: at base".format(_uav_label(uav_id)) for uav_id in uav_ids)
    assignment_frames.append(
        {
            "name": "assignment_start",
            "label": "Assignment start",
            "phase": "Assignment",
            "simulation_time": plan["metadata"]["planning_time"],
            "event_text": "Assignment begins",
            "fleet_text": initial_fleet,
            "detail": "Tasks are ranked by service value before the first feasible UAV is selected",
            "states": initial_states,
            "assigned": initial_assigned,
            "served": set(),
            "active_tasks": set(),
            "positions": {uav_id: base for uav_id in uav_ids},
            "active_uavs": set(),
            "uav_states": {uav_id: "at base" for uav_id in uav_ids},
            "uav_tasks": {},
            "planned_routes": {uav_id: (base,) for uav_id in uav_ids},
            "travelled_routes": {uav_id: (base,) for uav_id in uav_ids},
            "active_legs": {},
        }
    )
    for decision in trace:
        assignment_state = decision["assignment_state"]
        states, assigned = _task_state(
            scenario,
            assignment_state,
            plan["unassigned_task_ids"],
            active_task=decision["task_id"],
        )
        selected = decision["selected_uav"]
        decision_text = "{} assigned to {}".format(
            decision["task_id"],
            _uav_label(selected) if selected else "no UAV",
        )
        fleet = " · ".join("{}: at base".format(_uav_label(uav_id)) for uav_id in uav_ids)
        detail = "Priority {:.3f} · Candidates: {}".format(
            decision["current_service_value"],
            _candidate_summary(decision),
        )
        assignment_frames.append(
            {
                "name": "assignment_{}".format(decision["step"]),
                "label": "A{}: {} → {}".format(
                    decision["step"],
                    decision["task_id"],
                    _uav_label(selected) if selected else "unassigned",
                ),
                "phase": "Assignment",
                "simulation_time": plan["metadata"]["planning_time"],
                "event_text": "Decision: {}".format(decision_text),
                "fleet_text": fleet,
                "detail": detail,
                "states": states,
                "assigned": assigned,
                "served": set(),
                "active_tasks": {decision["task_id"]},
                "positions": {uav_id: base for uav_id in uav_ids},
                "active_uavs": set(),
                "uav_states": {uav_id: "at base" for uav_id in uav_ids},
                "uav_tasks": {},
                "planned_routes": {
                    uav_id: tuple(route)
                    for uav_id, route in decision["route_state"].items()
                },
                "travelled_routes": {uav_id: (base,) for uav_id in uav_ids},
                "active_legs": {},
            }
        )

    snapshots = assignment_frames[:]
    execution_snapshots = _expand_service_holds(
        _execution_snapshots(
            report,
            scenario,
            final_assignment_state,
            final_routes,
        )
    )
    for snapshot in execution_snapshots:
        snapshot["scenario"] = scenario
        snapshots.append(snapshot)
    for snapshot in assignment_frames:
        snapshot["scenario"] = scenario
        snapshot["title"] = _status_title(
            snapshot["phase"],
            snapshot["simulation_time"],
            snapshot["event_text"],
            0,
            len(snapshot["assigned"]),
            total_tasks,
            snapshot["fleet_text"],
            snapshot["detail"],
        )

    frames = []
    slider_steps = []
    for snapshot in snapshots:
        frames.append(
            go.Frame(
                name=snapshot["name"],
                data=_frame_data(snapshot, uav_ids, base, current_values),
                traces=dynamic_indices,
                layout=go.Layout(
                    title=_title(snapshot["title"]),
                    scene={
                        "annotations": _service_popup_annotations(
                            snapshot.get("service_popups", ())
                        )
                    },
                ),
            )
        )
        if snapshot.get("show_in_slider", True):
            slider_steps.append(
                {
                    "label": snapshot["label"],
                    "method": "animate",
                    "args": [
                        [snapshot["name"]],
                        {
                            "mode": "immediate",
                            "frame": {"duration": 0, "redraw": True},
                            "transition": {"duration": 0},
                        },
                    ],
                }
            )

    initial = frames[0]
    figure.frames = frames
    figure.add_annotation(
        x=0.5,
        y=1.035,
        xref="paper",
        yref="paper",
        text=_visual_key(uav_ids),
        showarrow=False,
        font={"size": 11, "color": "#475569"},
        bgcolor="rgba(248, 250, 252, 0.92)",
        bordercolor="#cbd5e1",
        borderwidth=1,
        borderpad=4,
    )
    figure.update_layout(
        title=_title(initial.layout.title.text),
        showlegend=False,
        sliders=[
            {
                "active": 0,
                "currentvalue": {"prefix": "Replay: "},
                "pad": {"t": 18},
                "len": 0.92,
                "x": 0.04,
                "steps": slider_steps,
            }
        ],
        updatemenus=[
            {
                "type": "buttons",
                "showactive": False,
                "x": 0.02,
                "y": 1.13,
                "direction": "right",
                "buttons": [
                    {
                        "label": "Play",
                        "method": "animate",
                        "args": [
                            None,
                            {
                                "fromcurrent": True,
                                "mode": "immediate",
                                "frame": {
                                    "duration": PLAY_FRAME_DURATION_MS,
                                    "redraw": True,
                                },
                                "transition": {
                                    "duration": PLAY_TRANSITION_DURATION_MS,
                                },
                            },
                        ],
                    },
                    {
                        "label": "Pause",
                        "method": "animate",
                        "args": [
                            [None],
                            {
                                "mode": "immediate",
                                "frame": {"duration": 0, "redraw": False},
                                "transition": {"duration": 0},
                            },
                        ],
                    },
                ],
            }
        ],
        margin={"l": 0, "r": 0, "t": 185, "b": 82},
        hoverlabel={"namelength": -1},
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(str(output_path), include_plotlyjs=True, full_html=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or args.report.with_name(args.report.stem + "_step_by_step.html")
    render_step_by_step(args.report, output)
    print("Step by step view: {}".format(output))


if __name__ == "__main__":
    main()
