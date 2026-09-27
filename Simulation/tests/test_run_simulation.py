import json
import subprocess
import sys
from pathlib import Path


def test_export_only_writes_v2_input_without_planner_output(tmp_path):
    output = tmp_path / "synthetic.scenario.json"
    command = [
        sys.executable,
        str(Path(__file__).parents[1] / "run_simulation.py"),
        "--mode",
        "synthetic",
        "--severity",
        "moderate",
        "--seed",
        "1234",
        "--task-count",
        "4",
        "--uav-count",
        "2",
        "--export-only",
        "--output",
        str(output),
    ]

    result = subprocess.run(command, capture_output=True, text=True, check=False)

    assert result.returncode == 0
    assert "Schema: scenario.v2" in result.stdout
    exported = json.loads(output.read_text(encoding="utf-8"))
    assert exported["schema_version"] == "scenario.v2"
    assert len(exported["tasks"]) == 4
    assert "initial_plan" not in exported
    assert "execution" not in exported
