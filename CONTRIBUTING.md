# Contributing to EventBook

EventBook is a research project. Changes should make the model more inspectable, deterministic, or empirically honest—not add live trading behavior.

## Before opening a pull request

1. Keep prices and fees in integer cents or basis points.
2. Add a test that describes the market behavior being changed.
3. Document a new microstructure assumption in `docs/assumptions.md`.
4. Never commit raw captures, credentials, or generated local research data.
5. Run both test suites:

```bash
uv run --with pytest pytest -q
cmake -S . -B build && cmake --build build
ctest --test-dir build --output-on-failure
```

## Scope

Pull requests must preserve research-only and paper-only operation. Do not add live order submission, account funding, credential collection, or semantic inference from contract text without an explicit design review.

## Code standards

Prefer small domain-specific functions, typed data models, fixed-point finance arithmetic, deterministic seeds, and tests based on realistic book behavior. Explain why a modeling choice is needed; do not write comments that merely restate code.
