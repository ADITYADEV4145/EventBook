# EventBook

EventBook is a local-first, research-only L2 replay and execution-simulation project for Kalshi-style binary contracts. It answers whether apparent cross-contract inconsistencies survive spreads, fees, displayed depth, partial fills, queue assumptions, and latency. It does **not** place live orders, fund accounts, collect credentials, or claim profitability.

## Quick start

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
cmake -S . -B build && cmake --build build && ctest --test-dir build --output-on-failure
PYTHONPATH=python pytest -q
PYTHONPATH=python python -m eventbook.reports.run --config configs/synthetic_baseline.yaml --output results/synthetic_baseline
```

The demo deterministically creates a synthetic event stream with widening spread, partial depth, cancel-before-fill, a threshold discrepancy, and a resolved-contract quote. It writes a one-page research report, Parquet trades, CSV outputs, and SVG charts. Use `ReplayEngine.from_parquet(...)` for local Parquet replay datasets.

## Future local collector checklist

- Read local credentials from an ignored environment file; never log them.
- Verify account ownership and exchange terms before collection.
- Validate sequence continuity and write raw captures only below ignored `data/raw/`.
- Convert local captures to a documented Parquet schema and retain provenance locally.
- Keep the collector read-only: no order submission, funding, or account mutation.

See [architecture](docs/architecture.md), [assumptions](docs/assumptions.md), [protocol](docs/research_protocol.md), and [data governance](docs/data_governance.md).

## Local-only collector and C++ bindings

Convert an account-holder local JSONL capture to ignored Parquet and DuckDB metadata:

```bash
uv run python -m eventbook.collector.local_ingest /absolute/path/to/local_capture.jsonl
```

The capture must contain the documented event fields (`timestamp_ns`, `sequence`, `ticker`, `side`, `action`, `price_cents`, `quantity`, and optional `order_id`). The output stays under ignored `data/processed/` and `data/local_metadata.duckdb`.

Build the optional pybind11 C++ order-book module:

```bash
uv run --with pybind11 python -m pybind11 --cmakedir
cmake -S . -B build -DEVENTBOOK_BUILD_PYTHON_BINDINGS=ON -Dpybind11_DIR="$(uv run --with pybind11 python -m pybind11 --cmakedir)"
cmake --build build
```

This exposes the C++ `OrderBook`, `BookLevel`, and `Side` primitives as `_eventbook_core`. The current Python replay is still the event-driven simulator; the binding gives researchers a verified C++ book primitive before a larger replay-core migration.
