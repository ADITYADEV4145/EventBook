from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from eventbook.metrics import evaluate_research_run
from eventbook.replay import ReplayConfig, ReplayEngine
from eventbook.strategies.relationships import ExecutionAssumptions, detect_relationships, load_relationships
from eventbook.synthetic.generate import write_jsonl


def main() -> None:
    arguments = _parse_arguments()
    output_directory = Path(arguments.output)
    output_directory.mkdir(parents=True, exist_ok=True)

    event_path = write_jsonl()
    replay = ReplayEngine.from_jsonl(event_path).run(config=ReplayConfig())
    relationships = load_relationships("configs/synthetic_relationships.yaml")
    signals = detect_relationships(replay.final_books, relationships, ExecutionAssumptions())
    submitted_orders = len({entry["order_id"] for entry in replay.signal_log if "order_id" in entry})
    metrics = evaluate_research_run(
        replay.fills,
        settlements=None,
        equity_curve=[],
        signal_log=replay.signal_log,
        signals=signals,
        canceled_orders=replay.canceled_orders,
        submitted_order_count=submitted_orders,
    )

    _write_json(output_directory / "summary.json", _summary(metrics.to_dict()))
    _write_signal_log(output_directory / "signal_log.csv", replay.signal_log)
    _write_equity_curve(output_directory / "equity_curve.csv")
    _write_trades(output_directory, replay)
    _write_report(output_directory / "report.md", metrics.to_dict())
    print(output_directory)


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the synthetic EventBook research report.")
    parser.add_argument("--config", required=True, help="Reserved for the next configuration-driven report pass.")
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def _summary(metrics: dict) -> dict:
    return {
        "mode": "research",
        "synthetic": True,
        "metrics": metrics,
        "limitations": "Synthetic replay only. No result is a claim of profitability or live performance.",
    }


def _write_json(path: Path, content: dict) -> None:
    path.write_text(json.dumps(content, indent=2, sort_keys=True) + "\n")


def _write_signal_log(path: Path, signal_log: list[dict]) -> None:
    fieldnames = ["timestamp_ns", "ticker", "order_id", "requested", "filled", "liquidity", "reason"]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(signal_log)


def _write_equity_curve(path: Path) -> None:
    # No settlement map is supplied in the synthetic detector-only report, so no equity is invented.
    path.write_text("timestamp_ns,net_pnl_cents\n")


def _write_trades(output_directory: Path, replay) -> None:
    try:
        import polars as polars
    except ImportError:
        (output_directory / "trades.parquet.unavailable.txt").write_text("Install eventbook[data] to produce trades.parquet.\n")
        return
    rows = [fill.__dict__ | {"side": str(fill.side)} for fill in replay.fills]
    polars.DataFrame(rows).write_parquet(output_directory / "trades.parquet")


def _write_report(path: Path, metrics: dict) -> None:
    report = """# Synthetic EventBook research report

This report uses deterministic synthetic data only. It is a research artifact, not evidence of profitability or live performance.

## Evaluation coverage

Gross and net settlement PnL are unavailable because this detector-only run has no executed orders or settlement map. Sharpe, drawdown, holding period, and adverse selection remain unavailable when their required inputs are absent; the report does not substitute estimates.

## Why apparent arbitrage may not be tradable

Displayed quotes can be stale, too shallow, canceled before arrival, or consumed before execution. Fees, spread crossing, partial fills, queue position, and latency can eliminate a theoretical discrepancy. Signals with missing executable quotes or nonpositive adjusted edge are rejected and counted separately.

## Metrics

```json
%s
```
""" % json.dumps(metrics, indent=2, sort_keys=True)
    path.write_text(report)


if __name__ == "__main__":
    main()
