"""Run a small reproducible comparison of the PGBM heuristic and a baseline."""
import argparse
from pgbm_sim import ResearchExperimentConfig, write_experiment_metrics

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--seeds", type=int, nargs="+", default=[101,102,103,104,105])
parser.add_argument("--mode", choices=("synthetic","du_outdoor","laquila_informed"), default="du_outdoor")
parser.add_argument("--severity", choices=("light","moderate","severe"), default="moderate")
parser.add_argument("--start-time", type=float, default=30.0, help="planning and execution start time in the scenario time unit")
parser.add_argument("--with-recourse", action="store_true", help="enable the current one replacement recourse fixture")
parser.add_argument("--output", default="results/research_metrics_initial.csv")
args=parser.parse_args()
records=write_experiment_metrics(args.seeds,args.output,ResearchExperimentConfig(mode=args.mode,severity=args.severity,start_time=args.start_time,recourse_enabled=args.with_recourse))
print("Experiment records: {}".format(len(records))); print("Metrics: {}".format(args.output))
print("Recourse: {}".format("enabled" if args.with_recourse else "disabled"))
