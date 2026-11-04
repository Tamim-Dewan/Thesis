from pathlib import Path

from Simulation.report_charts import V1_CHART_NAMES, V2_CHART_NAMES, write_all_charts


def test_report_chart_pipeline_writes_four_figures_per_report(tmp_path: Path):
    paths = write_all_charts(output_root=tmp_path)

    assert set(paths) == set(V1_CHART_NAMES + V2_CHART_NAMES)
    assert all(path.exists() and path.stat().st_size > 1000 for path in paths.values())
    assert all(path.suffix == ".pdf" for path in paths.values())
    assert (tmp_path / "chart_manifest.json").exists()
