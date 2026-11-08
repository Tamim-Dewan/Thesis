"""Merge independently run PGBM V2 matrix parts with coverage checks."""

import argparse
import csv
import json
from pathlib import Path


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--metrics-parts", nargs="+", required=True)
parser.add_argument("--trace-parts", nargs="+", required=True)
parser.add_argument("--metrics-output", required=True)
parser.add_argument("--trace-output", required=True)
args = parser.parse_args()


def add_queue_changes(trace):
    """Make queue transitions explicit in traces from older V2 workers."""

    v2 = trace.get("v2", {})
    for decision in v2.get("recourse_decisions", []):
        if "queue_changes" in decision:
            continue
        if decision.get("accepted"):
            decision["queue_changes"] = [
                {"action": "assigned_to_mission", "task_id": decision["new_task_id"]},
                {"action": "returned_to_queue", "task_id": decision["displaced_task_id"]},
            ]
        else:
            decision["queue_changes"] = [
                {"action": "kept_in_queue", "task_id": decision["new_task_id"]},
            ]
    return trace

rows = []
fieldnames = None
for path in args.metrics_parts:
    with Path(path).open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if fieldnames is None:
            fieldnames = reader.fieldnames
        elif fieldnames != reader.fieldnames:
            raise SystemExit("metrics header mismatch: {}".format(path))
        rows.extend(reader)

if fieldnames is None:
    raise SystemExit("no metrics parts supplied")

key = lambda row: (row["environment"], int(row["task_count"]), int(row["uav_count"]), int(row["seed"]), row["algorithm"])
rows.sort(key=key)
keys = [key(row) for row in rows]
if len(keys) != len(set(keys)):
    raise SystemExit("duplicate paired metric key found")
if len(rows) != 480:
    raise SystemExit("expected 480 paired rows after merge, found {}".format(len(rows)))

metrics_output = Path(args.metrics_output)
metrics_output.parent.mkdir(parents=True, exist_ok=True)
with metrics_output.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

traces = []
trace_keys = set()
for path in args.trace_parts:
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            trace = add_queue_changes(json.loads(line))
            trace_key = (trace["environment"], int(trace["task_count"]), int(trace["uav_count"]), int(trace["seed"]))
            if trace_key in trace_keys:
                raise SystemExit("duplicate trace key found: {}".format(trace_key))
            trace_keys.add(trace_key)
            traces.append(trace)
if len(traces) != 240:
    raise SystemExit("expected 240 traces after merge, found {}".format(len(traces)))
traces.sort(key=lambda item: (item["environment"], int(item["task_count"]), int(item["uav_count"]), int(item["seed"])))

trace_output = Path(args.trace_output)
trace_output.parent.mkdir(parents=True, exist_ok=True)
with trace_output.open("w", encoding="utf-8") as handle:
    for trace in traces:
        handle.write(json.dumps(trace, sort_keys=True) + "\n")

print("Merged metric rows: {}".format(len(rows)))
print("Merged decision traces: {}".format(len(traces)))
