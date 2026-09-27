"""Generate a self contained Plotly preview of one simulation environment."""

import argparse
from pathlib import Path

from pgbm_sim import ExperimentConfig, generate_environment, plot_environment


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/phase1_default.json")
    parser.add_argument("--output", default="results/environment_preview.html")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    config = ExperimentConfig.from_json(args.config)
    environment = generate_environment(config.environment, seed=args.seed)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    plot_environment(environment).write_html(str(output), include_plotlyjs=True, full_html=True)

    print("Environment preview: {}".format(output))
    print("Seed: {}".format(environment.seed))
    print("Obstacles: {}".format(len(environment.obstacles)))
    print("Kinds: {}".format(", ".join(obstacle.kind for obstacle in environment.obstacles)))
    print("Base: {}".format(environment.base.position))


if __name__ == "__main__":
    main()
