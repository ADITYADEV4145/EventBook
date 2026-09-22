# Modeling assumptions

All prices are integer cents and timestamps are UTC nanoseconds. L2 depth is aggregated by price; individual queue position is unobservable. `optimistic` consumes displayed depth; `conservative` subtracts a configured priority-ahead quantity at the first executable level. Fees are rounded up in integer cents using basis points. Orders use a deterministic fixed latency in this vertical slice. A marketable order may partially fill and is never assumed to receive a midpoint fill.

Phase 2 adds seeded uniform stochastic latency, marketable limits, passive maker orders, maker/taker fees, position caps, cancellation, and settlement PnL. A passive order is placed behind displayed same-side quantity; conservative mode adds `displayed_depth * priority_ahead_multiplier`. A passive fill is recognized only after a subsequent explicit trade event consumes that queue. This slice deliberately has no live order submission, credentials, or external collection.
