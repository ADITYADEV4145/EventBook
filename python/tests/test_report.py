import json

import polars as pl

from eventbook.reports.run import generate_report


def test_synthetic_report_contains_required_artifacts(tmp_path) -> None:
    output_directory = tmp_path / "report"
    generate_report("configs/synthetic_baseline.yaml", output_directory)
    required = ["summary.json", "trades.parquet", "equity_curve.csv", "signal_log.csv", "latency_sensitivity.csv", "report.md"]
    assert all((output_directory / name).exists() for name in required)
    assert pl.read_parquet(output_directory / "trades.parquet").height == 2
    summary = json.loads((output_directory / "summary.json").read_text())
    assert summary["metrics"]["gross_pnl_cents"] is not None
    assert len(list((output_directory / "charts").glob("*.svg"))) == 5
