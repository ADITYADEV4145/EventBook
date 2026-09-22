# Modeling assumptions

All prices are integer cents and timestamps are UTC nanoseconds. L2 depth is aggregated by price; individual queue position is unobservable. `optimistic` consumes displayed depth; `conservative` subtracts a configured priority-ahead quantity at the first executable level. Fees are rounded up in integer cents using basis points. Orders use a deterministic fixed latency in this vertical slice. A marketable order may partially fill and is never assumed to receive a midpoint fill.

Settlement, stochastic latency, per-order identifiers, and full Python/C++ pybind packaging are planned extensions; this slice deliberately has no live order submission, credentials, or external collection.
