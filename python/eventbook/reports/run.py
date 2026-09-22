"""Generate a reproducible, synthetic-only EventBook research report."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path

import polars as pl
import yaml

from eventbook.metrics import EquityPoint, evaluate_research_run
from eventbook.models import Action, Fill, Side
from eventbook.replay import ReplayConfig, ReplayEngine
from eventbook.strategies.relationships import ExecutionAssumptions, RelativeValueSignal, detect_relationship, load_relationships
from eventbook.synthetic.generate import write_jsonl


@dataclass(frozen=True)
class ReportConfiguration:
    taker_fee_bps: int
    position_limit: int
    settlements: dict[str, bool]
    latency_sensitivity_ns: list[int]


def main() -> None:
    arguments = _parse_arguments()
    generate_report(Path(arguments.config), Path(arguments.output))


def generate_report(config_path: Path | str, output_directory: Path | str) -> None:
    configuration = _load_configuration(Path(config_path))
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    replay, signals = _run_synthetic_study(configuration, latency_ns=0)
    equity_curve = _settlement_marked_equity(replay.fills, configuration.settlements)
    submitted_orders = len({entry["order_id"] for entry in replay.signal_log})
    metrics = evaluate_research_run(
        replay.fills,
        configuration.settlements,
        equity_curve,
        replay.signal_log,
        signals,
        replay.canceled_orders,
        submitted_orders,
    )
    latency_rows = _latency_sensitivity(configuration)
    _write_outputs(output_directory, replay.fills, replay.signal_log, equity_curve, metrics.to_dict(), latency_rows)


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the synthetic EventBook research report.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def _load_configuration(path: Path) -> ReportConfiguration:
    document = yaml.safe_load(path.read_text())
    execution = document["execution"]
    report = document["report"]
    return ReportConfiguration(
        taker_fee_bps=execution["taker_fee_bps"],
        position_limit=execution["position_limit"],
        settlements=report["synthetic_settlements"],
        latency_sensitivity_ns=report["latency_sensitivity_ns"],
    )


def _run_synthetic_study(configuration: ReportConfiguration, latency_ns: int) -> tuple[object, list[RelativeValueSignal]]:
    event_path = write_jsonl()
    relationships = load_relationships("configs/synthetic_relationships.yaml")
    threshold_relationship = relationships[0]
    captured_signals: list[RelativeValueSignal] = []

    def strategy(event, books):
        if event.ticker != "TEMP_GT_60" or event.action is not Action.ADD or event.price_cents != 65:
            return []
        signal = detect_relationship(books, threshold_relationship, ExecutionAssumptions(configuration.taker_fee_bps))
        captured_signals.append(signal)
        if signal.rejected_reason is not None:
            return []
        quantity = signal.available_quantity
        return [
            {"ticker": "TEMP_GT_50", "side": "bid", "limit_cents": 62, "quantity": quantity, "order_id": "buy-lower"},
            {"ticker": "TEMP_GT_60", "side": "ask", "limit_cents": 65, "quantity": quantity, "order_id": "sell-higher"},
        ]

    engine = ReplayEngine.from_jsonl(event_path)
    config = ReplayConfig(
        latency_ns=latency_ns,
        taker_fee_bps=configuration.taker_fee_bps,
        position_limit=configuration.position_limit,
    )
    return engine.run(strategy=strategy, config=config), captured_signals


def _settlement_marked_equity(fills: list[Fill], settlements: dict[str, bool]) -> list[EquityPoint]:
    cumulative_pnl = 0
    points = [EquityPoint(0, 0)]
    for fill in fills:
        payout = 100 if settlements[fill.ticker] else 0
        gross = (payout - fill.price_cents) * fill.quantity if fill.side is Side.BID else (fill.price_cents - payout) * fill.quantity
        cumulative_pnl += gross - fill.fee_cents
        points.append(EquityPoint(fill.timestamp_ns, cumulative_pnl))
    return points


def _latency_sensitivity(configuration: ReportConfiguration) -> list[dict]:
    rows = []
    for latency_ns in configuration.latency_sensitivity_ns:
        replay, signals = _run_synthetic_study(configuration, latency_ns)
        gross_pnl, net_pnl = replay.settlement_pnl_cents(configuration.settlements)
        rows.append({
            "latency_ns": latency_ns,
            "gross_pnl_cents": gross_pnl,
            "net_pnl_cents": net_pnl,
            "fill_count": len(replay.fills),
            "accepted_signal_count": sum(signal.rejected_reason is None for signal in signals),
        })
    return rows


def _write_outputs(output_directory: Path, fills: list[Fill], signal_log: list[dict], equity_curve: list[EquityPoint], metrics: dict, latency_rows: list[dict]) -> None:
    _write_json(output_directory / "summary.json", {"mode": "research", "synthetic": True, "metrics": metrics, "limitations": "Synthetic data only; no live-performance or profitability claim."})
    _write_trades(output_directory / "trades.parquet", fills)
    _write_csv(output_directory / "equity_curve.csv", [point.__dict__ for point in equity_curve], ["timestamp_ns", "equity_cents"])
    _write_csv(output_directory / "signal_log.csv", signal_log, ["timestamp_ns", "ticker", "order_id", "requested", "filled", "liquidity", "reason"])
    _write_csv(output_directory / "latency_sensitivity.csv", latency_rows, list(latency_rows[0]) if latency_rows else ["latency_ns"])
    _write_charts(output_directory / "charts", equity_curve, metrics, latency_rows)
    _write_report(output_directory / "report.md", metrics, latency_rows)


def _write_json(path: Path, content: dict) -> None:
    path.write_text(json.dumps(content, indent=2, sort_keys=True) + "\n")


def _write_trades(path: Path, fills: list[Fill]) -> None:
    schema = {"ticker": pl.String, "side": pl.String, "price_cents": pl.Int64, "quantity": pl.Int64, "fee_cents": pl.Int64, "timestamp_ns": pl.Int64, "liquidity": pl.String, "order_id": pl.String}
    rows = [{**fill.__dict__, "side": str(fill.side)} for fill in fills]
    pl.DataFrame(rows, schema=schema).write_parquet(path)


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_charts(directory: Path, equity_curve: list[EquityPoint], metrics: dict, latency_rows: list[dict]) -> None:
    directory.mkdir(exist_ok=True)
    equity_values = [point.equity_cents for point in equity_curve]
    drawdowns = _drawdowns(equity_values)
    _line_chart(directory / "equity_curve.svg", "Settlement-marked synthetic equity", equity_values)
    _line_chart(directory / "drawdown.svg", "Synthetic drawdown", drawdowns)
    _bar_chart(directory / "gross_vs_net_pnl.svg", "Gross versus net PnL", {"gross": metrics["gross_pnl_cents"] or 0, "net": metrics["net_pnl_cents"] or 0})
    _bar_chart(directory / "fill_quality.svg", "Fill quality", {"fill rate %": round((metrics["fill_rate"] or 0) * 100), "canceled rate %": round((metrics["canceled_order_rate"] or 0) * 100)})
    _bar_chart(directory / "latency_sensitivity.svg", "Latency sensitivity: net PnL", {f"{row['latency_ns']} ns": row["net_pnl_cents"] for row in latency_rows})


def _drawdowns(values: list[int]) -> list[int]:
    peak = values[0] if values else 0
    drawdowns = []
    for value in values:
        peak = max(peak, value)
        drawdowns.append(peak - value)
    return drawdowns


def _line_chart(path: Path, title: str, values: list[int]) -> None:
    points = _points(values)
    path.write_text(_svg(title, f'<polyline points="{points}" fill="none" stroke="#147d92" stroke-width="3"/>'))


def _bar_chart(path: Path, title: str, values: dict[str, int]) -> None:
    maximum = max([abs(value) for value in values.values()] or [1])
    bars = []
    for index, (label, value) in enumerate(values.items()):
        height = abs(value) / maximum * 150
        x = 60 + index * 130
        y = 220 - height if value >= 0 else 220
        color = "#147d92" if value >= 0 else "#b5483c"
        bars.append(f'<rect x="{x}" y="{y}" width="70" height="{height}" fill="{color}"/><text x="{x}" y="250">{label}</text><text x="{x}" y="{y - 8}">{value}</text>')
    path.write_text(_svg(title, "".join(bars)))


def _points(values: list[int]) -> str:
    if not values:
        return "40,220 360,220"
    minimum, maximum = min(values), max(values)
    scale = maximum - minimum or 1
    return " ".join(f"{40 + index * 320 / max(1, len(values) - 1):.1f},{220 - (value - minimum) * 160 / scale:.1f}" for index, value in enumerate(values))


def _svg(title: str, body: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="440" height="280" viewBox="0 0 440 280"><style>text{{font:13px sans-serif;fill:#243746}}.title{{font-size:16px;font-weight:bold}}</style><text class="title" x="20" y="28">{title}</text><line x1="40" y1="220" x2="410" y2="220" stroke="#9aabb5"/>{body}</svg>'


def _write_report(path: Path, metrics: dict, latency_rows: list[dict]) -> None:
    report = f"""# Synthetic EventBook research report

This is a deterministic research-only simulation using committed synthetic events. It does not establish profitability, arbitrage, or live performance.

## Assumptions

The report crosses displayed best quotes, charges configured taker fees, caps positions, and marks the resulting synthetic fills to explicit synthetic settlement outcomes. The equity curve is settlement-marked for evaluation clarity, not a live mark-to-market series.

## Why apparent arbitrage may not be tradable

Displayed liquidity can disappear before an order arrives, be insufficient for the required quantity, sit behind an unobservable queue, or be consumed by others. Spread crossing, partial fills, fees, and latency can turn a theoretical discrepancy into a rejected or losing paper trade.

## Metrics

```json
{json.dumps(metrics, indent=2, sort_keys=True)}
```

## Latency sensitivity

```json
{json.dumps(latency_rows, indent=2)}
```

Charts are in `charts/`. Their values are synthetic and should be used only to verify model behavior.
"""
    path.write_text(report)


if __name__ == "__main__":
    main()
