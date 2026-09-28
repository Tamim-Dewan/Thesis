"""Generate the formatted Initial Solution V1 LaTeX report."""

import argparse
from collections import defaultdict
from pathlib import Path

from generate_pgbm_v1_results_report import (
    _maximum,
    _mean,
    _minimum,
    _mode,
    _read,
    _route_share,
    _sd,
    _service_rate,
)


def _fmt(value, digits=3):
    return ("{:0." + str(digits) + "f}").format(value)


def _pm(rows, field):
    return "{} $\\pm$ {}".format(_fmt(_mean(rows, field)), _fmt(_sd(rows, field)))


def _tex(value):
    replacements = (
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("#", r"\#"),
        ("_", r"\_"),
    )
    result = str(value)
    for old, new in replacements:
        result = result.replace(old, new)
    return result


def _table(lines, columns, headers, rows, caption=None, label=None, long=False):
    if caption:
        lines.append("\\caption{{{}}}".format(caption))
    if label:
        lines.append("\\label{{{}}}".format(label))
    if long:
        lines.append("\\toprule")
        lines.append(" & ".join(headers) + r" \\")
        lines.append("\\midrule")
        lines.append("\\endfirsthead")
        lines.append("\\toprule")
        lines.append(" & ".join(headers) + r" \\")
        lines.append("\\midrule")
        lines.append("\\endhead")
    else:
        lines.append("\\toprule")
        lines.append(" & ".join(headers) + r" \\")
        lines.append("\\midrule")
    for row in rows:
        lines.append(" & ".join(row) + r" \\")
    lines.append("\\bottomrule")


def build_tex(rows):
    modes = tuple(sorted({_mode(row) for row in rows}))
    task_counts = tuple(sorted({int(row["task_count"]) for row in rows}))
    uav_counts = tuple(sorted({int(row["uav_count"]) for row in rows}))
    seeds = tuple(sorted({int(row["seed"]) for row in rows}))
    mode_groups = defaultdict(list)
    for row in rows:
        mode_groups[_mode(row)].append(row)
    baseline = [
        row for row in rows
        if int(row["task_count"]) == min(task_counts) and int(row["uav_count"]) == 3
    ] or rows
    baseline_groups = defaultdict(list)
    for row in baseline:
        baseline_groups[_mode(row)].append(row)
    matrix_groups = defaultdict(list)
    for row in rows:
        matrix_groups[(_mode(row), row["task_count"], row["uav_count"])].append(row)
    task_effect_groups = defaultdict(list)
    fleet_effect_groups = defaultdict(list)
    phase_groups = defaultdict(list)
    for row in rows:
        task_effect_groups[(_mode(row), row["task_count"])].append(row)
        fleet_effect_groups[(_mode(row), row["uav_count"])].append(row)
        phase_groups[(row["task_count"], row["phase_high_tasks"], row["phase_medium_tasks"], row["phase_low_tasks"])].append(row)

    route_share = _route_share(rows)
    total_truncated = sum(int(row.get("search_truncated_dispatches", 0)) for row in rows)
    fastest_mode = min(modes, key=lambda mode: _mean(mode_groups[mode], "runtime_seconds"))
    slowest_mode = max(modes, key=lambda mode: _mean(mode_groups[mode], "runtime_seconds"))

    lines = [
        r"\documentclass[10pt,a4paper]{article}",
        r"\usepackage[T1]{fontenc}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage{lmodern}",
        r"\usepackage[a4paper,margin=22mm,headheight=24pt]{geometry}",
        r"\usepackage{amsmath}",
        r"\usepackage{array}",
        r"\usepackage{booktabs}",
        r"\usepackage{enumitem}",
        r"\usepackage{fancyhdr}",
        r"\usepackage{longtable}",
        r"\usepackage{microtype}",
        r"\usepackage{pdflscape}",
        r"\usepackage{tabularx}",
        r"\usepackage[table]{xcolor}",
        r"\usepackage{hyperref}",
        r"\definecolor{navy}{HTML}{17365D}",
        r"\definecolor{bluegray}{HTML}{EAF1F8}",
        r"\definecolor{lightgray}{HTML}{F4F6F8}",
        r"\definecolor{midgray}{HTML}{5B6573}",
        r"\definecolor{rulegray}{HTML}{C9D1D9}",
        r"\hypersetup{colorlinks=true,linkcolor=navy,urlcolor=navy,citecolor=navy,pdftitle={Initial Solution V1 Heavy Experiment Findings Report},pdfauthor={PGBM Thesis Simulation Work}}",
        r"\setlist[itemize]{leftmargin=*,itemsep=2pt,topsep=3pt}",
        r"\setlist[enumerate]{leftmargin=*,itemsep=4pt,topsep=3pt}",
        r"\setlength{\parindent}{0pt}",
        r"\setlength{\parskip}{6pt}",
        r"\pagestyle{fancy}",
        r"\fancyhf{}",
        r"\fancyhead[L]{\textcolor{midgray}{PGBM Thesis Simulation}}",
        r"\fancyhead[R]{\textcolor{midgray}{Initial Solution V1}}",
        r"\fancyfoot[C]{\textcolor{midgray}{\thepage}}",
        r"\renewcommand{\headrulewidth}{0.4pt}",
        r"\renewcommand{\headrule}{\hbox to\headwidth{\color{rulegray}\leaders\hrule height \headrulewidth\hfill}}",
        r"\newcommand{\code}[1]{\path{#1}}",
        r"\begin{document}",
        r"\begin{titlepage}",
        r"\thispagestyle{empty}",
        r"\vspace*{18mm}",
        r"{\color{navy}\rule{\textwidth}{1.5pt}}\\[10mm]",
        r"{\color{navy}\sffamily\bfseries\fontsize{25}{31}\selectfont Initial Solution V1\\Heavy Experiment Findings Report\par}",
        r"\vspace{6mm}",
        r"{\color{midgray}\sffamily\Large Seeded two hour earthquake style simulation evidence\par}",
        r"\vfill",
        r"\begin{tabular}{@{}ll@{}}",
        r"\textbf{Project:} & PGBM thesis and simulation work\\",
        r"\textbf{Solution type:} & Bounded brute force reference planner\\",
        r"\textbf{Environments:} & Synthetic and DU outdoor\\",
        r"\textbf{{Experiment rows:}} & {}\\".format(len(rows)),
        r"\textbf{Report date:} & 27 September 2026",
        r"\end{tabular}",
        r"\vfill",
        r"\begin{center}",
        r"\colorbox{bluegray}{\begin{minipage}{0.88\textwidth}",
        r"\textbf{Purpose.} This report presents the stronger replacement evidence for the PGBM initial solution V1. It is an engineering and experimental baseline report, not a claim that the bounded planner is the final mathematical PGBM optimizer.",
        r"\end{minipage}}",
        r"\end{center}",
        r"\vspace{12mm}",
        r"{\color{navy}\rule{\textwidth}{1.5pt}}",
        r"\end{titlepage}",
        r"\tableofcontents",
        r"\clearpage",
        r"\section{Executive summary}",
        "Initial Solution V1 was evaluated as a seeded, two hour, event driven bounded brute force reference planner. The replacement evidence contains \\textbf{{{}}} rows over {} environments, task loads {}, UAV counts {}, and seeds {} through {}.".format(
            len(rows), len(modes), ", ".join(str(value) for value in task_counts),
            ", ".join(str(value) for value in uav_counts), min(seeds), max(seeds),
        ),
        "The workload is intentionally heavier than the earlier six task report. New tasks are detected in high, medium, and low phases, wait in a queue when all UAVs are active, and are planned only at dispatch opportunities. Active routes remain fixed, so recourse and rerouting are excluded from V1.",
        "Across the complete matrix, route evaluation accounts for approximately \\textbf{{{}\\%}} of planner time. {} is faster on average, while {} is slower. The run observed \\textbf{{{}}} dispatches at the candidate search limit; those results are reported as bounded V1 behavior rather than hidden as optimal results.".format(_fmt(route_share), fastest_mode, slowest_mode, total_truncated),
        r"\section{Scope and formulation}",
        r"The implementation follows the full report and the selected \code{problem_formulation_v5.tex} source. It uses severity based exponential service value at completion:",
        r"\begin{equation}",
        r"v_i(C_i) = s_i \exp\!\left[-\lambda\left(C_i-t_i\right)\right].",
        r"\end{equation}",
        r"At each dispatch opportunity, V1 enumerates bounded joint assignments and within UAV task orders. A candidate is accepted only when its route is collision free, its parcel count and mass fit the UAV, its energy stays above the reserve, service completes within the horizon, and the UAV returns to base. The selected candidate maximizes the sum of completion time service values with deterministic tie breaks.",
        r"\begin{itemize}",
        r"\item New task detections are queued during the full 120 minute event horizon.",
        r"\item Active missions are immutable until return to base.",
        r"\item The UAV has a 2 kilogram payload limit, four parcel slots, and a five minute base turnaround.",
        r"\item Collision aware three dimensional routing, payload, energy reserve, service time, and return feasibility are checked for every candidate.",
        r"\end{itemize}",
        r"\section{Experiment protocol}",
        r"\begin{table}[htbp]",
        r"\centering",
        r"\caption{Heavy V1 experiment protocol.}",
        r"\label{tab:protocol}",
        r"\rowcolors{2}{lightgray}{white}",
        r"\begin{tabularx}{0.94\textwidth}{@{}>{\bfseries}lX@{}}",
    ]
    protocol_rows = [
        ["Horizon", "120 minutes"],
        ["Arrival phases", "High: 0 to 40 minutes; medium: 40 to 80; low: 80 to 120"],
        ["Relative phase weights", "3:2:1"],
        ["Task loads", ", ".join(str(value) for value in task_counts)],
        ["UAV counts", ", ".join(str(value) for value in uav_counts)],
        ["Seeds", "{} through {} ({} seeds)".format(min(seeds), max(seeds), len(seeds))],
        ["Total rows", str(len(rows))],
        ["Payload capacity", "2.0 kg and 4 parcels per UAV"],
        ["Base turnaround", "5 minutes"],
        ["Search bound", "At most 8 pending tasks and 50,000 candidates per dispatch"],
        ["Recourse", "Disabled"],
    ]
    lines.append(r"\toprule")
    lines.append(r"Item & Setting \\")
    lines.append(r"\midrule")
    lines.extend(r"{} & {} \\".format(_tex(row[0]), _tex(row[1])) for row in protocol_rows)
    lines.extend([
        r"\bottomrule",
        r"\end{tabularx}",
        r"\end{table}",
        r"The deterministic phase quotas are 15/10/5 for 30 tasks, 30/20/10 for 60 tasks, and 45/30/15 for 90 tasks. A seed reproduces the same scene and task set when the full configuration is unchanged. Changing task load changes the generated task set, so the load sweep is a controlled seeded replicate study rather than a nested prefix comparison.",
        r"\section{Main 30 task, 3 UAV baseline}",
        r"The main baseline provides a readable reference point. Values are means over the ten seeds and standard deviations are shown after $\pm$.",
        r"\begin{table}[htbp]",
        r"\centering",
        r"\scriptsize",
        r"\caption{Main 30 task, 3 UAV baseline.}",
        r"\label{tab:baseline}",
        r"\setlength{\tabcolsep}{3.5pt}",
        r"\rowcolors{2}{lightgray}{white}",
        r"\begin{tabular}{@{}lrrrrrrr@{}}",
    ])
    baseline_rows = []
    for mode in modes:
        group = baseline_groups[mode]
        baseline_rows.append([
            _tex(mode), _pm(group, "served_tasks"), _fmt(_service_rate(group)) + r"\%",
            _pm(group, "deferred_tasks"), _fmt(_mean(group, "peak_queue_size")),
            _fmt(_mean(group, "average_completion_delay")), _fmt(_mean(group, "runtime_seconds")),
        ])
    _table(lines, "@{}lrrrrrrr@{}", ["Environment", "Served", "Rate", "Deferred", "Peak queue", "Delay min", "Runtime s"], baseline_rows, long=False)
    lines.extend([
        r"\end{tabular}",
        r"\end{table}",
        r"\clearpage",
        r"\begin{landscape}",
        r"\section{Complete task load and fleet matrix}",
        r"Each row below aggregates the ten seed replicates for one environment, task load, and UAV count case.",
        r"\scriptsize",
        r"\begin{longtable}{@{}llrrrrrrrr@{}}",
    ])
    matrix_rows = []
    for key, group in sorted(matrix_groups.items(), key=lambda item: (item[0][0], int(item[0][1]), int(item[0][2]))):
        matrix_rows.append([
            _tex(key[0]), key[1], key[2], _pm(group, "served_tasks"),
            _fmt(_service_rate(group)) + r"\%", _pm(group, "deferred_tasks"),
            _fmt(_mean(group, "peak_queue_size")), _fmt(_mean(group, "average_completion_delay")),
            _fmt(_mean(group, "runtime_seconds")), _fmt(_route_share(group)) + r"\%",
        ])
    _table(lines, "@{}llrrrrrrrr@{}", ["Environment", "Tasks", "UAVs", "Served", "Rate", "Deferred", "Peak queue", "Delay min", "Runtime s", "Route share"], matrix_rows, long=True)
    lines.extend([
        r"\end{longtable}",
        r"\end{landscape}",
        r"\begin{landscape}",
        r"\section{Task load and fleet effects}",
        r"The next two tables aggregate across the other experimental factor. They show how workload and fleet size influence service and computation.",
        r"\scriptsize",
        r"\begin{longtable}{@{}llrrrrrrr@{}}",
    ])
    task_rows = []
    for key, group in sorted(task_effect_groups.items(), key=lambda item: (item[0][0], int(item[0][1]))):
        task_rows.append([
            _tex(key[0]), key[1], _pm(group, "served_tasks"), _fmt(_service_rate(group)) + r"\%",
            _fmt(_mean(group, "peak_queue_size")), _fmt(_mean(group, "candidate_count")),
            _fmt(_mean(group, "planner_runtime_seconds")), _fmt(_route_share(group)) + r"\%",
        ])
    _table(lines, "@{}llrrrrrrr@{}", ["Environment", "Tasks", "Served", "Rate", "Peak queue", "Candidates", "Planner s", "Route share"], task_rows, long=True)
    lines.extend([
        r"\end{longtable}",
        r"\vspace{4mm}",
        r"\begin{longtable}{@{}llrrrrrr@{}}",
    ])
    fleet_rows = []
    for key, group in sorted(fleet_effect_groups.items(), key=lambda item: (item[0][0], int(item[0][1]))):
        fleet_rows.append([
            _tex(key[0]), key[1], _pm(group, "served_tasks"), _fmt(_service_rate(group)) + r"\%",
            _fmt(_mean(group, "deferred_tasks")), _fmt(_mean(group, "peak_queue_size")),
            _fmt(_mean(group, "runtime_seconds")), _fmt(100.0 * _mean(group, "payload_utilization")) + r"\%",
        ])
    _table(lines, "@{}llrrrrrr@{}", ["Environment", "UAVs", "Served", "Rate", "Deferred", "Peak queue", "Runtime s", "Parcel util"], fleet_rows, long=True)
    lines.extend([
        r"\end{longtable}",
        r"\end{landscape}",
        r"\section{Arrival phase verification}",
        r"Every completed row reproduced the intended phase quota. This is a generation contract check rather than a performance result.",
        r"\begin{table}[htbp]",
        r"\centering",
        r"\rowcolors{2}{lightgray}{white}",
        r"\begin{tabular}{@{}rrrrr@{}}",
    ])
    phase_rows = []
    for key, group in sorted(phase_groups.items(), key=lambda item: int(item[0][0])):
        phase_rows.append([key[0], key[1], key[2], key[3], str(len(group))])
    _table(lines, "@{}rrrr@{}", ["Tasks", "High", "Medium", "Low", "Rows"], phase_rows, long=False)
    lines.extend([
        r"\end{tabular}",
        r"\end{table}",
        r"\section{Runtime and search bottlenecks}",
        r"Route share is total route evaluation time divided by total planner time. Candidate counts are the bounded joint candidates evaluated over dispatches.",
        r"\begin{table}[htbp]",
        r"\centering",
        r"\scriptsize",
        r"\rowcolors{2}{lightgray}{white}",
        r"\begin{tabular}{@{}lrrrrrr@{}}",
    ])
    runtime_rows = []
    for mode in modes:
        group = mode_groups[mode]
        runtime_rows.append([
            _tex(mode), _fmt(_mean(group, "planner_runtime_seconds")),
            _fmt(_minimum(group, "planner_runtime_seconds")), _fmt(_maximum(group, "planner_runtime_seconds")),
            _fmt(_mean(group, "candidate_count")), _fmt(_maximum(group, "max_candidate_count")),
            _fmt(_route_share(group)) + r"\%",
        ])
    _table(lines, "@{}lrrrrrr@{}", ["Environment", "Mean planner s", "Min s", "Max s", "Mean candidates", "Max dispatch candidates", "Route share"], runtime_rows, long=False)
    lines.extend([
        r"\end{tabular}",
        r"\end{table}",
        r"\begin{landscape}",
        r"\scriptsize",
        r"\begin{longtable}{@{}lrrrrrrrr@{}}",
    ])
    slow_rows = []
    for row in sorted(rows, key=lambda item: float(item["runtime_seconds"]), reverse=True)[:10]:
        slow_rows.append([
            _tex(_mode(row)), row["seed"], row["task_count"], row["uav_count"], row["served_tasks"],
            _fmt(float(row["runtime_seconds"])), _fmt(float(row["planner_runtime_seconds"])),
            row.get("search_truncated_dispatches", "0"),
        ])
    _table(lines, "@{}lrrrrrrr@{}", ["Environment", "Seed", "Tasks", "UAVs", "Served", "Runtime s", "Planner s", "Truncated"], slow_rows, long=True)
    lines.extend([
        r"\end{longtable}",
        r"\end{landscape}",
        r"\section{Findings}",
        r"\begin{enumerate}",
        r"\item The earlier six task experiment was too small to characterize queue pressure. The replacement matrix uses 30, 60, and 90 tasks and produces a wider range of deferred work and runtime.",
        r"\item The 3:2:1 high, medium, and low arrival structure is reproduced exactly for every task load. The high phase creates the initial queue pressure that the event runner must absorb.",
        r"\item More UAVs generally improve service rate and reduce queue pressure, but fleet growth also increases assignment combinations and is not computationally free.",
        r"\item DU outdoor runs are expected to be slower and less serviceable than Synthetic runs in this implementation because mapped polygon geometry creates more difficult route searches and longer travel paths. The measured matrix reports the magnitude without treating it as a universal real world law.",
        r"\item Route evaluation is the dominant measured cost. Route caching, reuse of fixed leg paths, early feasibility pruning, and a scalable candidate search are immediate targets for the next solution.",
        r"\item Search truncation is reported explicitly. A case reaching the 50,000 candidate limit demonstrates bounded V1 behavior under load and must not be interpreted as a global optimum.",
        r"\item Safe return rate is a model feasibility result, not a field reliability estimate, because the current energy coefficients, speed, turnaround time, and base supply policy are research assumptions.",
        r"\end{enumerate}",
        r"\section{Limitations and next step}",
        r"V1 is a transparent bounded reference planner, not the final mathematical PGBM optimizer. It keeps the individual task model, current Synthetic and DU scene generators, one sufficient base supply, fixed active routes, and the existing collision aware routing layer. Recourse and rerouting are deliberately deferred. The next step is to design an efficient planner using the route and search bottleneck evidence, then compare that planner against this heavy V1 reference before introducing recourse.",
        r"\section{Reproducibility artifacts}",
        r"The report is supported by the following local artifacts:",
        r"\begin{itemize}",
        r"\item \code{Simulation/results/pgbm_v1_two_hour_experiments/raw_metrics/pgbm_v1_two_hour_matrix_metrics_tasks_30_60_90_uavs_3_5_8_10_seeds_101_110.csv}, containing all raw rows.",
        r"\item \code{Simulation/run_pgbm_v1_experiment_matrix.py}, which runs the default heavy matrix.",
        r"\item \code{Simulation/pgbm_sim/experiment.py}, which assembles the experiment rows.",
        r"\item \code{Simulation/pgbm_sim/event_simulation.py}, which implements the 120 minute event clock and queue execution.",
        r"\item \code{Experiment Reports/V1/pgbm_v1_simulation_findings_bn.tex}, this report source.",
        r"\end{itemize}",
        r"\vfill",
        r"\begin{center}\color{midgray}\small End of report\end{center}",
        r"\end{document}",
    ])
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--metrics",
        default=(
            "results/pgbm_v1_two_hour_experiments/raw_metrics/"
            "pgbm_v1_two_hour_matrix_metrics_tasks_30_60_90_uavs_3_5_8_10_seeds_101_110.csv"
        ),
    )
    parser.add_argument("--output", default="../Experiment Reports/V1/pgbm_v1_simulation_findings_bn.tex")
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_tex(_read(args.metrics)), encoding="utf-8")
    print("LaTeX report: {}".format(output))


if __name__ == "__main__":
    main()
