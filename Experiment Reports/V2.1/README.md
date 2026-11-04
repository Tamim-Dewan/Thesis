# PGBM Initial Solution V2.1

This folder contains the Version 2.1 cache aware recourse report package. It
follows the same layout and report flow as the V1 and V2 folders: core feature,
algorithm and feasibility rules, experiment configuration, metrics, paired
findings, charts, limitations, and next decision.

- `pgbm_v2_1_cache_aware_findings_bn.md`: readable Bengali findings report.
- `pgbm_v2_1_cache_aware_findings_bn.tex`: editable Bengali XeLaTeX source.
- `pgbm_v2_1_cache_aware_findings_bn.pdf`: compiled report.
- `build/`: XeLaTeX auxiliary files and the build copy of the PDF.
- `../assets/v2_1/`: four vector PDF figures used in the report.

The report is generated from the bounded paired matrix at
`Simulation/results/pgbm_v2_1_cache_experiments/`. The matrix contains 240
seeded scenarios, 720 metric rows, 240 decision traces, and one manifest. It
compares the V2 control with the uniform cache policy and the explicitly
labelled water heavy sensitivity policy.

The report generator is
`Simulation/generate_pgbm_v21_report.py`. Run it from the repository root to
regenerate the Markdown, LaTeX source, and vector figures. Compile the LaTeX
source with XeLaTeX from this directory after the figures have been generated.

The V2.1 decision is to retain one cache slot and defer a second slot or an
adaptive prior. Most loaded reserve parcels returned unused, and the
water-heavy sensitivity produced higher cache energy overhead.
