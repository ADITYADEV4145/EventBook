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

The demo deterministically creates a synthetic event stream with widening spread, partial depth, cancel-before-fill, a threshold discrepancy, and a resolved-contract quote. For Parquet ingestion install `pip install -e '.[data]'`, then use `ReplayEngine.from_parquet(...)`.

## Future local collector checklist

- Read local credentials from an ignored environment file; never log them.
- Verify account ownership and exchange terms before collection.
- Validate sequence continuity and write raw captures only below ignored `data/raw/`.
- Convert local captures to a documented Parquet schema and retain provenance locally.
- Keep the collector read-only: no order submission, funding, or account mutation.

See [architecture](docs/architecture.md), [assumptions](docs/assumptions.md), [protocol](docs/research_protocol.md), and [data governance](docs/data_governance.md).
