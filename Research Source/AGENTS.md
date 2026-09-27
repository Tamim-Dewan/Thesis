# Research Source

## Overview

This area contains the thesis report source, figures, bibliography, and several
mathematical formulation drafts. It is research material, separate from the
runtime simulation package.

## Key files

| File | Owns |
|---|---|
| `Full Report/main.tex` | Intended book style thesis entry point |
| `Full Report/Chapters/` | Report chapters and template material |
| `Full Report/Bibliography.bib` | Report bibliography |
| `Problem Formulation/problem_formulation_from_scratch.tex` | Detailed formulation draft |
| `Problem Formulation/check_formulation.py` | Formulation regression checks |

## Commands

```bash
cd "Research Source/Problem Formulation"
python3 check_formulation.py
pdflatex problem_formulation_from_scratch.tex
```

## Conventions

- Select and name one canonical formulation before deleting or archiving the other drafts.
- Keep generated PDFs and LaTeX auxiliary files in a build or archive location, not beside active source.
- Keep figures in `Full Report/Figures/`; package copies do not belong in the figures directory.
- Preserve the distinction between the report formulation and the executable heuristic baseline.

## Gotchas

- `Full Report/main.tex` currently references missing title, front matter, and chapter files and also requests `vector.sty`.
- The formulation drafts are parallel working documents, not interchangeable versions.
- `mathematical_model_backup_20260905_1409.tex` is byte identical to `mathematical_model_v1_complete.tex`.

## Related specs

- [Simulation and planner scope](../docs/scope/scope.md)
- [Planner and execution contract](../docs/specs/0005-pgbm-planner-execution.md)

_Drafted by /audit from the repo, worth a quick human pass. Edit freely: once a line stops matching this draft, later runs treat it as curated and will flag rather than overwrite it._
