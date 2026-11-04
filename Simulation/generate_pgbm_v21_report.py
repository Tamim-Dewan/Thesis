"""Generate the complete Bengali V2.1 report package."""

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import plotly.graph_objects as go
from plotly.subplots import make_subplots


ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = ROOT / (
    "Simulation/results/pgbm_v2_1_cache_experiments/raw_metrics/"
    "pgbm_v2_1_cache_matrix_metrics_bounded_workers8.csv"
)
MANIFEST_PATH = ROOT / (
    "Simulation/results/pgbm_v2_1_cache_experiments/manifests/"
    "pgbm_v2_1_cache_manifest_bounded_workers8.json"
)
REPORT_DIR = ROOT / "Experiment Reports/V2.1"
ASSET_DIR = ROOT / "Experiment Reports/assets/v2_1"

INT_FIELDS = {"seed", "task_count", "uav_count", "served_tasks", "deferred_tasks"}
FLOAT_FIELDS = {
    "objective_value",
    "average_completion_delay",
    "total_distance",
    "total_energy",
    "parcel_delivery_rate",
    "safe_return_rate",
    "runtime_seconds",
    "cache_loaded_parcels",
    "cache_used_parcels",
    "cache_returned_parcels",
    "cache_match_count",
    "cache_hit_count",
    "cache_hit_rate",
    "cache_assisted_count",
    "cache_energy_overhead",
}

VARIANTS = ("v2_control", "uniform", "water_heavy_sensitivity")
VARIANT_LABELS = {
    "v2_control": "V2 control",
    "uniform": "Uniform cache",
    "water_heavy_sensitivity": "Water heavy sensitivity",
}


def load_rows(path: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for raw in csv.DictReader(handle):
            row: Dict[str, object] = dict(raw)
            for field in INT_FIELDS:
                row[field] = int(raw[field])
            for field in FLOAT_FIELDS:
                row[field] = float(raw.get(field, 0.0) or 0.0)
            row["cache_enabled"] = raw.get("cache_enabled", "False").lower() == "true"
            rows.append(row)
    if not rows:
        raise ValueError("V2.1 metrics file is empty")
    return rows


def groups(rows: Iterable[Mapping[str, object]], keys: Sequence[str]):
    result = defaultdict(list)
    for row in rows:
        result[tuple(row[key] for key in keys)].append(row)
    return result


def mean(rows: Sequence[Mapping[str, object]], field: str) -> float:
    return statistics.mean(float(row[field]) for row in rows) if rows else 0.0


def std(rows: Sequence[Mapping[str, object]], field: str) -> float:
    values = [float(row[field]) for row in rows]
    return statistics.stdev(values) if len(values) > 1 else 0.0


def pm(rows: Sequence[Mapping[str, object]], field: str, digits: int = 2) -> str:
    return "{0:.{d}f} ± {1:.{d}f}".format(mean(rows, field), std(rows, field), d=digits)


def pct(value: float, digits: int = 1) -> str:
    return "{0:.{d}f}%".format(100.0 * value, d=digits)


def key_for(row: Mapping[str, object]) -> Tuple[object, ...]:
    return (row["environment"], row["task_count"], row["uav_count"], row["seed"])


def paired_deltas(rows: Sequence[Mapping[str, object]]) -> List[Dict[str, object]]:
    controls = {key_for(row): row for row in rows if row["cache_variant"] == "v2_control"}
    result = defaultdict(list)
    for row in rows:
        variant = str(row["cache_variant"])
        if variant == "v2_control":
            continue
        control = controls.get(key_for(row))
        if control is None:
            continue
        result[variant].append(
            {
                "objective_delta": float(row["objective_value"]) - float(control["objective_value"]),
                "served_delta": float(row["served_tasks"]) - float(control["served_tasks"]),
                "deferred_delta": float(row["deferred_tasks"]) - float(control["deferred_tasks"]),
                "delay_delta": float(row["average_completion_delay"]) - float(control["average_completion_delay"]),
                "delivery_delta": float(row["parcel_delivery_rate"]) - float(control["parcel_delivery_rate"]),
                "energy_delta": float(row["total_energy"]) - float(control["total_energy"]),
            }
        )
    summaries = []
    for variant in ("uniform", "water_heavy_sensitivity"):
        members = result[variant]
        summaries.append(
            {
                "variant": variant,
                "episodes": len(members),
                "objective_delta": statistics.mean(item["objective_delta"] for item in members),
                "served_delta": statistics.mean(item["served_delta"] for item in members),
                "deferred_delta": statistics.mean(item["deferred_delta"] for item in members),
                "delay_delta": statistics.mean(item["delay_delta"] for item in members),
                "delivery_delta": statistics.mean(item["delivery_delta"] for item in members),
                "energy_delta": statistics.mean(item["energy_delta"] for item in members),
            }
        )
    return summaries


def latex_text(value: object) -> str:
    text = str(value)
    for old, new in (
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
    ):
        text = text.replace(old, new)
    return text


def markdown_table(rows: Sequence[Mapping[str, object]], fields: Sequence[Tuple[str, str]]) -> str:
    lines = [
        "| " + " | ".join(label for _, label in fields) + " |",
        "| " + " | ".join("---" for _ in fields) + " |",
    ]
    for row in rows:
        values = []
        for key, _ in fields:
            value = row.get(key, "")
            values.append("{:.4f}".format(value) if isinstance(value, float) else str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _layout(fig: go.Figure, title: str, height: int = 620) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        width=1200,
        height=height,
        title={"text": title, "font": {"family": "Avenir Next, Arial, sans-serif", "size": 19}},
        font={"family": "Avenir Next, Arial, sans-serif", "size": 13},
        margin={"l": 75, "r": 35, "t": 85, "b": 75},
        paper_bgcolor="white",
        plot_bgcolor="white",
        legend={"orientation": "h", "y": -0.18, "x": 0.5, "xanchor": "center"},
    )
    fig.update_xaxes(showgrid=False, linecolor="#C9D1D9", mirror=True)
    fig.update_yaxes(gridcolor="#D9E1E8", linecolor="#C9D1D9", mirror=True)
    return fig


def write_figures(rows: Sequence[Mapping[str, object]]) -> Dict[str, str]:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    cache_rows = [row for row in rows if row["cache_variant"] != "v2_control"]
    by_variant = groups(cache_rows, ("cache_variant",))
    labels = [VARIANT_LABELS[name] for name in ("uniform", "water_heavy_sensitivity")]

    activity = go.Figure()
    for field, label, color in (
        ("cache_loaded_parcels", "Loaded", "#17365D"),
        ("cache_used_parcels", "Used", "#009E73"),
        ("cache_returned_parcels", "Returned", "#D55E00"),
        ("cache_hit_count", "Accepted hits", "#7B61A8"),
    ):
        activity.add_trace(
            go.Bar(
                x=labels,
                y=[mean(by_variant[(name,)], field) for name in ("uniform", "water_heavy_sensitivity")],
                name=label,
                marker_color=color,
            )
        )
    activity.update_layout(barmode="group", yaxis_title="Mean parcels per episode")
    activity_path = ASSET_DIR / "v2_1_cache_activity.pdf"
    _layout(activity, "V2.1 reserve parcel activity")
    activity.write_image(str(activity_path), format="pdf")

    paired = paired_deltas(rows)
    performance = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("Objective delta", "Served task delta"),
        horizontal_spacing=0.14,
    )
    performance.add_trace(
        go.Bar(
            x=labels,
            y=[item["objective_delta"] for item in paired],
            name="Δ objective",
            marker_color="#0072B2",
        ),
        row=1,
        col=1,
    )
    performance.add_trace(
        go.Bar(
            x=labels,
            y=[item["served_delta"] for item in paired],
            name="Δ served tasks",
            marker_color="#009E73",
        ),
        row=1,
        col=2,
    )
    performance.update_yaxes(title_text="V2.1 minus V2", row=1, col=1)
    performance.update_yaxes(title_text="Tasks per episode", row=1, col=2)
    performance_path = ASSET_DIR / "v2_1_paired_performance.pdf"
    _layout(performance, "V2.1 paired service performance")
    performance.write_image(str(performance_path), format="pdf")

    environment_rows = groups(cache_rows, ("cache_variant", "environment"))
    hit = go.Figure()
    for variant, color in (("uniform", "#0072B2"), ("water_heavy_sensitivity", "#D55E00")):
        hit.add_trace(
            go.Bar(
                x=["Synthetic", "DU outdoor"],
                y=[
                    mean(environment_rows[(variant, environment)], "cache_hit_rate")
                    for environment in ("synthetic", "du_outdoor")
                ],
                name=VARIANT_LABELS[variant],
                marker_color=color,
            )
        )
    hit.update_layout(barmode="group", yaxis={"title": "Accepted hit rate", "range": [0.0, 1.0]})
    hit_path = ASSET_DIR / "v2_1_hit_rate_environment.pdf"
    _layout(hit, "V2.1 cache hit rate by environment")
    hit.write_image(str(hit_path), format="pdf")

    energy = go.Figure()
    for variant, color in (("uniform", "#0072B2"), ("water_heavy_sensitivity", "#D55E00")):
        energy.add_trace(
            go.Box(
                y=[float(row["cache_energy_overhead"]) for row in cache_rows if row["cache_variant"] == variant],
                name=VARIANT_LABELS[variant],
                marker_color=color,
                boxmean=True,
            )
        )
    energy.update_layout(yaxis_title="Cache energy overhead")
    energy_path = ASSET_DIR / "v2_1_energy_overhead.pdf"
    _layout(energy, "V2.1 cache energy overhead")
    energy.write_image(str(energy_path), format="pdf")

    return {
        "activity": activity_path.name,
        "performance": performance_path.name,
        "hit_rate": hit_path.name,
        "energy": energy_path.name,
    }


def _overall_rows(rows: Sequence[Mapping[str, object]]) -> List[Dict[str, object]]:
    grouped_rows = groups(rows, ("cache_variant",))
    result = []
    for variant in VARIANTS:
        members = grouped_rows[(variant,)]
        result.append(
            {
                "variant": VARIANT_LABELS[variant],
                "cache_variant": variant,
                "episodes": len(members),
                "objective": mean(members, "objective_value"),
                "served": mean(members, "served_tasks"),
                "delivery": mean(members, "parcel_delivery_rate"),
                "energy": mean(members, "total_energy"),
                "delay": mean(members, "average_completion_delay"),
                "loaded": mean(members, "cache_loaded_parcels"),
                "used": mean(members, "cache_used_parcels"),
                "returned": mean(members, "cache_returned_parcels"),
                "hits": mean(members, "cache_hit_count"),
                "hit_rate": mean(members, "cache_hit_rate"),
                "overhead": mean(members, "cache_energy_overhead"),
            }
        )
    return result


def _cell_rows(rows: Sequence[Mapping[str, object]]) -> List[Dict[str, object]]:
    grouped_rows = groups(rows, ("environment", "task_count", "uav_count", "cache_variant"))
    result = []
    for environment in ("du_outdoor", "synthetic"):
        for task_count in (30, 60, 90):
            for uav_count in (3, 5, 8, 10):
                for variant in ("v2_control", "uniform", "water_heavy_sensitivity"):
                    members = grouped_rows[(environment, task_count, uav_count, variant)]
                    result.append(
                        {
                            "environment": "DU outdoor" if environment == "du_outdoor" else "Synthetic",
                            "task_count": task_count,
                            "uav_count": uav_count,
                            "variant": VARIANT_LABELS[variant],
                            "objective": pm(members, "objective_value"),
                            "served": pm(members, "served_tasks"),
                            "delivery": pct(mean(members, "parcel_delivery_rate")),
                            "energy": pm(members, "total_energy"),
                            "hit_rate": pct(mean(members, "cache_hit_rate")),
                            "overhead": pm(members, "cache_energy_overhead"),
                        }
                    )
    return result


def write_markdown(rows: Sequence[Mapping[str, object]], figures: Mapping[str, str], manifest: Mapping[str, object]) -> None:
    overall = _overall_rows(rows)
    paired = paired_deltas(rows)
    environment_groups = groups(
        [row for row in rows if row["cache_variant"] != "v2_control"],
        ("cache_variant", "environment"),
    )
    lines = [
        "# PGBM Initial Solution V2.1: cache aware recourse findings",
        "",
        "এই report-টি V1 এবং V2 report-এর একই experiment flow অনুসরণ করে। V1 এবং canonical V2 evidence অপরিবর্তিত রাখা হয়েছে।",
        "",
        "## V2.1-এর core feature",
        "",
        "V2.1 হলো V2-এর উপর নির্মিত একটি bounded cache aware recourse layer। Ordinary V2 mission route তৈরি হওয়ার পরে dispatch time-এ সর্বোচ্চ একটি reserve parcel load করার চেষ্টা করা হয়। Payload slot, payload mass, full route energy, reserve energy, return route এবং ১২০ মিনিটের horizon feasible হলেই reserve load হয়।",
        "",
        "Reserve parcel future undetected task দেখে নির্বাচন করা হয় না এবং flight-এর মাঝখানে reload করা হয় না। পরবর্তী replacement এখনও V2-এর one-for-one positive service-value gain rule অনুসরণ করে।",
        "",
        "## Experiment-এর সংক্ষিপ্ত চিত্র",
        "",
        markdown_table(
            [
                {"item": "Environment", "value": "Synthetic এবং DU outdoor"},
                {"item": "Operation window", "value": "১২০ মিনিট"},
                {"item": "Task load", "value": "৩০, ৬০, ৯০"},
                {"item": "UAV count", "value": "৩, ৫, ৮, ১০"},
                {"item": "Seed", "value": "১০১–১১০"},
                {"item": "Policies", "value": "V2 control, uniform, water heavy sensitivity"},
                {"item": "Evidence", "value": "২৪০ scenario, ৭২০ metrics row, ২৪০ paired trace"},
                {"item": "Planner bound", "value": "max_pending_tasks=4, max_candidate_plans=5000"},
            ],
            (("item", "বিষয়"), ("value", "ব্যবহৃত configuration")),
        ),
        "",
        "## Cache loading এবং hit mechanism",
        "",
        "প্রথমে ordinary route calculate হয়। Route-এর পরে payload capacity থাকলে configured prior থেকে item নির্বাচন করা হয়। Selected item-এর জন্য payload, mass, energy margin, return time এবং horizon check করা হয়। Load হলে reserve inventory mission state-এ আলাদা থাকে। Replacement candidate-এর demand cache বা displaced task থেকে satisfy হলে cache evidence record হয়, কিন্তু positive gain এবং route feasibility ছাড়া সেটি accepted hit হিসেবে গণনা হয় না।",
        "",
        "## Aggregate performance",
        "",
        markdown_table(
            overall,
            (("variant", "Variant"), ("episodes", "Episodes"), ("objective", "Objective"), ("served", "Served"), ("delivery", "Delivery rate"), ("energy", "Energy"), ("delay", "Mean delay")),
        ),
        "",
        "## Paired core findings",
        "",
        "প্রতিটি V2.1 row একই environment, task load, UAV count এবং seed-এর V2 control row-এর সঙ্গে তুলনা করা হয়েছে।",
        "",
        markdown_table(
            [
                {"variant": VARIANT_LABELS[item["variant"]], "episodes": item["episodes"], "objective": item["objective_delta"], "served": item["served_delta"], "deferred": item["deferred_delta"], "delay": item["delay_delta"], "delivery": item["delivery_delta"], "energy": item["energy_delta"]}
                for item in paired
            ],
            (("variant", "Variant"), ("episodes", "Paired episodes"), ("objective", "Δ objective"), ("served", "Δ served"), ("deferred", "Δ deferred"), ("delay", "Δ delay"), ("delivery", "Δ delivery"), ("energy", "Δ energy")),
        ),
        "",
        "**Core finding:** দুইটি one-slot policy-তেই objective সামান্য বেড়েছে। Uniform policy-তে mean objective gain 0.238 এবং served task gain 0.288। Water heavy sensitivity-তে gain 0.328 এবং 0.454। তবে reserve load-এর বড় অংশ unused অবস্থায় return করেছে এবং water heavy policy-তে cache energy overhead বেশি।",
        "",
        "## Cache behavior",
        "",
        markdown_table(
            overall[1:],
            (("variant", "Variant"), ("loaded", "Loaded"), ("used", "Used"), ("returned", "Returned"), ("hits", "Accepted hits"), ("hit_rate", "Hit rate"), ("overhead", "Cache energy overhead")),
        ),
        "",
        "এখানে hit rate হলো accepted cache hits divided by all accepted replacements। Loaded parcel-এর মধ্যে ব্যবহৃত fraction নয়।",
        "",
        "## Environment sensitivity",
        "",
        markdown_table(
            [
                {"environment": "Synthetic", "variant": VARIANT_LABELS[variant], "hit_rate": pct(mean(environment_groups[(variant, "synthetic")], "cache_hit_rate")), "overhead": mean(environment_groups[(variant, "synthetic")], "cache_energy_overhead")}
                for variant in ("uniform", "water_heavy_sensitivity")
            ]
            + [
                {"environment": "DU outdoor", "variant": VARIANT_LABELS[variant], "hit_rate": pct(mean(environment_groups[(variant, "du_outdoor")], "cache_hit_rate")), "overhead": mean(environment_groups[(variant, "du_outdoor")], "cache_energy_overhead")}
                for variant in ("uniform", "water_heavy_sensitivity")
            ],
            (("environment", "Environment"), ("variant", "Variant"), ("hit_rate", "Hit rate"), ("overhead", "Cache energy overhead")),
        ),
        "",
        "## Charts",
        "",
        "![V2.1 cache activity](../assets/v2_1/{})".format(figures["activity"]),
        "![V2.1 paired performance](../assets/v2_1/{})".format(figures["performance"]),
        "![V2.1 hit rate by environment](../assets/v2_1/{})".format(figures["hit_rate"]),
        "![V2.1 energy overhead](../assets/v2_1/{})".format(figures["energy"]),
        "",
        "## Decision and limitations",
        "",
        "The first full matrix supports retaining one cache slot. A second slot and adaptive prior are deferred because most loaded parcels returned unused, while the water heavy sensitivity increased energy overhead. The item prior is a sensitivity assumption, not a field-calibrated probability. The matrix uses bounded planner settings recorded in the manifest and does not claim unrestricted optimality.",
        "",
        "## Evidence files",
        "",
        "* Raw metrics: `Simulation/results/pgbm_v2_1_cache_experiments/raw_metrics/`",
        "* Decision traces: `Simulation/results/pgbm_v2_1_cache_experiments/decision_traces/`",
        "* Manifest: `Simulation/results/pgbm_v2_1_cache_experiments/manifests/pgbm_v2_1_cache_manifest_bounded_workers8.json`",
        "* Summary: `Simulation/results/pgbm_v2_1_cache_experiments/summary/`",
        "",
    ]
    (REPORT_DIR / "pgbm_v2_1_cache_aware_findings_bn.md").write_text("\n".join(lines), encoding="utf-8")


def _tex_row(values: Sequence[object]) -> str:
    return " & ".join(latex_text(value) for value in values) + r" \\"


def write_tex(rows: Sequence[Mapping[str, object]], figures: Mapping[str, str], manifest: Mapping[str, object]) -> None:
    overall = _overall_rows(rows)
    paired = paired_deltas(rows)
    cells = _cell_rows(rows)
    matrix_rows = "\n".join(
        _tex_row((
            cell["environment"],
            cell["task_count"],
            cell["uav_count"],
            cell["variant"],
            cell["objective"],
            cell["served"],
            cell["delivery"],
            cell["energy"],
            cell["hit_rate"],
            cell["overhead"],
        ))
        for cell in cells
    )
    overall_rows = "\n".join(
        _tex_row((item["variant"], item["episodes"], pm([row for row in rows if row["cache_variant"] == item["cache_variant"]], "objective_value"), pm([row for row in rows if row["cache_variant"] == item["cache_variant"]], "served_tasks"), pct(mean([row for row in rows if row["cache_variant"] == item["cache_variant"]], "parcel_delivery_rate")), pm([row for row in rows if row["cache_variant"] == item["cache_variant"]], "total_energy"), pm([row for row in rows if row["cache_variant"] == item["cache_variant"]], "average_completion_delay")))
        for item in overall
    )
    paired_rows = "\n".join(
        _tex_row((VARIANT_LABELS[item["variant"]], item["episodes"], "{:.3f}".format(item["objective_delta"]), "{:.3f}".format(item["served_delta"]), "{:.3f}".format(item["deferred_delta"]), "{:.3f}".format(item["delay_delta"]), "{:.3f}".format(item["energy_delta"])))
        for item in paired
    )
    tex = r'''% Bengali report for PGBM Initial Solution V2.1.
\documentclass[10pt,a4paper]{article}
\usepackage{fontspec}
\usepackage{polyglossia}
\setmainlanguage{bengali}
\setotherlanguage{english}
\setmainfont[Script=Bengali]{Kohinoor Bangla}
\setsansfont[Script=Bengali]{Kohinoor Bangla}
\newfontfamily\bengalifonttt[Script=Bengali]{Kohinoor Bangla}
\newfontfamily\englishfont{Avenir Next}
\usepackage[a4paper,margin=20mm,headheight=24pt]{geometry}
\usepackage{amsmath,array,booktabs,enumitem,fancyhdr,float,graphicx,longtable,pdflscape,titlesec,xcolor,hyperref}
\definecolor{navy}{HTML}{17365D}
\definecolor{bluegray}{HTML}{EAF1F8}
\definecolor{midgray}{HTML}{5B6573}
\definecolor{rulegray}{HTML}{C9D1D9}
\hypersetup{colorlinks=true,linkcolor=navy,urlcolor=navy,pdftitle={PGBM Initial Solution V2.1 Cache Aware Recourse Report},pdfauthor={PGBM Thesis Simulation Work}}
\setlist[itemize]{label={-},leftmargin=*,itemsep=1pt,topsep=2pt}
\setlist[enumerate]{leftmargin=*,itemsep=3pt,topsep=2pt}
\titleformat{\section}{\Large\bfseries}{\thesection}{0.75em}{}
\titlespacing*{\section}{0pt}{2.5ex plus 0.4ex minus 0.2ex}{1ex plus 0.2ex}
\setlength{\parindent}{0pt}
\setlength{\parskip}{4pt}
\setlength{\emergencystretch}{2em}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\textcolor{midgray}{PGBM Thesis Simulation}}
\fancyhead[R]{\textcolor{midgray}{Initial Solution V2.1}}
\fancyfoot[C]{\textcolor{midgray}{\thepage}}
\renewcommand{\headrulewidth}{0.4pt}
\renewcommand{\headrule}{\hbox to\headwidth{\color{rulegray}\leaders\hrule height \headrulewidth\hfill}}
\begin{document}
\begin{titlepage}
\thispagestyle{empty}
\vspace*{18mm}
{\color{navy}\rule{\textwidth}{1.5pt}}\\[10mm]
{\color{navy}\englishfont\bfseries\fontsize{25}{32}\selectfont Initial Solution V2.1\\Cache Aware Recourse Report\par}
\vspace{6mm}
{\color{midgray}\sffamily\Large One slot reserve parcel, paired experiment এবং ফলাফল\par}
\vfill
\begin{tabular}{@{}ll@{}}
\textbf{Project:} & PGBM thesis and simulation work\\
\textbf{সমাধানের ধরন:} & Cache aware one slot recourse\\
\textbf{Environment:} & Synthetic এবং DU outdoor\\
\textbf{মোট configuration:} & ২৪০টি paired configuration, ৭২০টি metrics row\\
\textbf{Seed:} & ১০১--১১০\\
\textbf{Report date:} & ৭ অক্টোবর ২০২৬
\end{tabular}
\vfill
\begin{center}
\colorbox{bluegray}{\begin{minipage}{0.88\textwidth}
এই report-এ V2.1 cache loading rule, feasibility guard, paired V2 control, cache hit evidence এবং one slot policy decision একই flow-তে ব্যাখ্যা করা হয়েছে।
\end{minipage}}
\end{center}
\vspace{12mm}
{\color{navy}\rule{\textwidth}{1.5pt}}
\end{titlepage}
\tableofcontents
\clearpage
\section{V2.1-এর core feature}
V2.1 হলো V2-এর উপর নির্মিত bounded cache aware recourse layer। Ordinary V2 mission route তৈরি হওয়ার পরে dispatch time-এ সর্বোচ্চ একটি reserve parcel load করা হয়। Payload slot, payload mass, full route energy, reserve energy, return route এবং ১২০ মিনিটের horizon feasible হলেই reserve load হয়। Reserve future undetected task দেখে নির্বাচন করা হয় না এবং flight-এর মাঝখানে reload করা হয় না। পরবর্তী replacement V2-এর one-for-one positive service-value gain rule অনুসরণ করে।
\begin{itemize}
\item At most one reserve parcel: একটি mission-এ সর্বোচ্চ একটি cache slot।
\item Feasibility guards: payload, mass, energy reserve, return এবং horizon।
\item Configured prior: default uniform prior এবং labelled water-heavy sensitivity prior।
\item Cache evidence: load, use, match, accepted hit, miss এবং returned parcel আলাদা record।
\item V2 isolation: canonical V1 এবং V2 code path ও evidence overwrite করা হয়নি।
\end{itemize}
\section{Experiment-এর সংক্ষিপ্ত চিত্র}
V2 control এবং প্রতিটি V2.1 policy একই seeded scenario-তে চালানো হয়েছে। দুইটি environment, ৩০/৬০/৯০ task load, ৩/৫/৮/১০ UAV এবং ১০টি seed ব্যবহার করে ২৪০টি scenario, ৭২০টি metrics row এবং ২৪০টি decision trace তৈরি হয়েছে। Matrix generation-এর জন্য bounded planner settings manifest-এ সংরক্ষিত আছে।
\section{Cache loading এবং recourse flow}
প্রথমে ordinary V2 route calculate হয়। এরপর configured prior থেকে একটি item নির্বাচন করা হয়। Free payload slot, remaining mass, cache সহ full route energy, reserve margin, return time এবং horizon check করা হয়। সব guard pass করলে reserve inventory mission state-এ রাখা হয়। Later replacement-এ cache বা released displaced inventory candidate demand satisfy করতে পারে, কিন্তু candidate শুধুমাত্র feasible positive service-value gain হলে accepted hit হয়। Loaded কিন্তু unused parcel mission শেষে returned হিসেবে record হয়।
\section{Aggregate performance}
\begin{table}[htbp]\centering\scriptsize
\caption{V2 control এবং V2.1 policy aggregate result।}
\begin{tabular}{@{}lrrrrrr@{}}\toprule
Variant & Episodes & Objective & Served & Delivery & Energy & Delay\\\midrule
''' + overall_rows + r'''
\bottomrule\end{tabular}\end{table}
\section{Paired core findings}
প্রতিটি V2.1 row একই environment, task load, UAV count এবং seed-এর V2 control row-এর সঙ্গে তুলনা করা হয়েছে।
\begin{table}[htbp]\centering\scriptsize
\caption{V2.1 minus V2 paired delta।}
\begin{tabular}{@{}lrrrrrr@{}}\toprule
Variant & Episodes & $\Delta$ Objective & $\Delta$ Served & $\Delta$ Deferred & $\Delta$ Delay & $\Delta$ Energy\\\midrule
''' + paired_rows + r'''
\bottomrule\end{tabular}\end{table}
দুইটি one-slot policy-তেই objective সামান্য বেড়েছে। Uniform policy-তে mean objective gain 0.238 এবং served task gain 0.288। Water-heavy sensitivity-তে gain 0.328 এবং 0.454। তবে reserve load-এর বড় অংশ unused অবস্থায় return করেছে এবং water-heavy policy-তে cache energy overhead বেশি।
\begin{figure}[htbp]\centering\includegraphics[width=0.98\textwidth]{../assets/v2_1/v2_1_paired_performance.pdf}\caption{V2.1 paired objective এবং served task delta।}\end{figure}
\section{Cache activity এবং environment sensitivity}
\begin{figure}[htbp]\centering\includegraphics[width=0.98\textwidth]{../assets/v2_1/v2_1_cache_activity.pdf}\caption{Reserve parcel load, use, return এবং accepted hit।}\end{figure}
\begin{figure}[htbp]\centering\includegraphics[width=0.98\textwidth]{../assets/v2_1/v2_1_hit_rate_environment.pdf}\caption{Environment অনুযায়ী cache hit rate।}\end{figure}
\begin{figure}[htbp]\centering\includegraphics[width=0.98\textwidth]{../assets/v2_1/v2_1_energy_overhead.pdf}\caption{Cache energy overhead distribution।}\end{figure}
\begin{landscape}
\scriptsize
\begin{longtable}{@{}llrlrrrrrr@{}}
\caption{Environment, task load, fleet এবং policy অনুযায়ী সম্পূর্ণ V2.1 matrix summary।}\\
\toprule Environment & Task & UAV & Variant & Objective & Served & Delivery & Energy & Hit rate & Overhead\\\midrule
\endfirsthead
\toprule Environment & Task & UAV & Variant & Objective & Served & Delivery & Energy & Hit rate & Overhead\\\midrule
\endhead
''' + matrix_rows + r'''
\bottomrule
\end{longtable}
\end{landscape}
\section{Decision এবং limitations}
প্রথম full matrix one-slot cache policy retain করার পক্ষে evidence দিয়েছে। দ্বিতীয় slot এবং adaptive prior আপাতত defer করা হয়েছে, কারণ অধিকাংশ loaded parcel unused অবস্থায় return করেছে এবং water-heavy sensitivity cache energy overhead বাড়িয়েছে। Item prior field-calibrated probability নয়। Matrix bounded planner settings ব্যবহার করেছে এবং unrestricted optimality claim করে না।
\section{Evidence এবং reproducibility}
Raw metrics, decision traces, summary CSV এবং manifest Simulation results folder-এ সংরক্ষিত। V2.1 code আলাদা v2\_1 namespace-এ এবং এই report-এর editable source V2.1 report folder-এ রাখা হয়েছে।
\end{document}
'''
    (REPORT_DIR / "pgbm_v2_1_cache_aware_findings_bn.tex").write_text(tex, encoding="utf-8")


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_rows(METRICS_PATH)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    figures = write_figures(rows)
    write_markdown(rows, figures, manifest)
    write_tex(rows, figures, manifest)
    print("Report directory: {}".format(REPORT_DIR))
    print("Assets directory: {}".format(ASSET_DIR))
    print("Metrics rows: {}".format(len(rows)))
    print("Figures: {}".format(", ".join(figures.values())))


if __name__ == "__main__":
    main()
