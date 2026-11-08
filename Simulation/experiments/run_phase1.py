"""Validate and materialize the Phase 1 experimental contract."""

import argparse
import json
from pathlib import Path

from pgbm_sim import ExperimentConfig, MetricsRecord, SeedManager, write_metrics_csv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/phase1_default.json")
    args = parser.parse_args()
    config = ExperimentConfig.from_json(args.config)
    seeds = SeedManager(config.base_seed)
    components = ["environment", "tasks", "uavs", "planner", "recourse"]
    manifest = {
        "config": config.as_dict(),
        "component_seeds": seeds.manifest(components),
        "metric_fields": list(MetricsRecord.__dataclass_fields__.keys()),
    }
    manifest_path = Path(config.manifest_output)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_metrics_csv([], config.metrics_output)
    print("Phase 1 contract validated")
    print("Manifest: {}".format(manifest_path))
    print("Metrics schema: {}".format(config.metrics_output))


if __name__ == "__main__":
    main()
