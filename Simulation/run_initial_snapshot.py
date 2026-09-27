"""Run the approved t=30 initial snapshot for the DU and synthetic scenes."""

import argparse
import json
import subprocess
import sys
from pathlib import Path


DEFAULT_CONFIG = Path(__file__).with_name("configs") / "initial_snapshot.json"


def load_config(path: Path):
    values = json.loads(path.read_text(encoding="utf-8"))
    if values.get("schema_version") != "initial_snapshot.v1":
        raise ValueError("unsupported initial snapshot configuration")
    planning = values["planning"]
    scenario = values["scenario"]
    if not planning.get("no_recourse", False):
        raise ValueError("the initial snapshot must disable recourse")
    if float(planning["start_time"]) != 30.0:
        raise ValueError("the initial snapshot must use start_time 30")
    if not scenario.get("task_count") or not scenario.get("uav_count"):
        raise ValueError("task_count and uav_count must be positive")
    if len(values.get("runs", ())) != 2:
        raise ValueError("the initial snapshot must contain DU and synthetic runs")
    if {item["mode"] for item in values["runs"]} != {"du_outdoor", "synthetic"}:
        raise ValueError("the initial snapshot must contain one DU and one synthetic run")
    return values


def build_command(config, run):
    planning = config["planning"]
    scenario = config["scenario"]
    return [
        sys.executable,
        str(Path(__file__).with_name("run_simulation.py")),
        "--mode",
        run["mode"],
        "--severity",
        scenario["severity"],
        "--seed",
        str(run["seed"]),
        "--task-count",
        str(scenario["task_count"]),
        "--uav-count",
        str(scenario["uav_count"]),
        "--start-time",
        str(planning["start_time"]),
        "--planner",
        planning["planner"],
        "--no-recourse",
        "--output",
        run["report"],
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--dry-run", action="store_true", help="print commands without executing them")
    args = parser.parse_args()
    config = load_config(args.config)
    for run in config["runs"]:
        command = build_command(config, run)
        print(" ".join(command))
        if not args.dry_run:
            subprocess.run(command, check=True, cwd=str(Path(__file__).parent))


if __name__ == "__main__":
    main()
