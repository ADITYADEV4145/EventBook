# Research protocol

Use chronological train, validation, and held-out test splits. Never use a future book update to decide an earlier trade. Report the fee schedule, latency, queue assumption, gross and net PnL separately, and per-market as well as aggregate results. Run sensitivity sweeps across latency and queue assumptions and use bootstrap confidence intervals when samples permit. Reject results that are not stable across reasonable assumptions.

Every signal must use executable bid/ask depth, account for partial fills, and state rejection reasons. Do not optimize parameters on the test split. Results are research observations, never claims of arbitrage or future profitability.

Evaluation reports net and gross settlement PnL, turnover, fill and cancellation rates, drawdown, win rate, displayed-depth capacity, accepted and rejected signal counts, and rejection reasons. Sharpe uses equally spaced equity changes and the stated annualization factor; it is unavailable when there are too few observations or zero return variance. Average holding period is unavailable until a position-lot matcher is supplied. Adverse selection requires explicitly supplied post-fill marks. Bootstrap intervals use a fixed seed and must be reported as sensitivity evidence rather than proof of robustness.
