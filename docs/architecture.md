# Architecture

```mermaid
flowchart LR
  S[Synthetic or account-holder local data] --> I[Python validation / ingestion]
  I --> P[Parquet or JSONL local dataset]
  P --> R[Deterministic replay]
  R --> B[C++20 L2 book core]
  R --> E[Execution simulator]
  E --> M[Metrics and research report]
```

The C++ core owns aggregated L2 state and invariants. Python owns local ingestion, experiment configuration, relationship rules, and reporting. Bindings are intentionally an optional build integration: no live exchange client exists.
