"""Metrics for research results with explicit inputs and unavailable values."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections import deque
from dataclasses import asdict, dataclass
from math import sqrt
from random import Random
from statistics import mean, stdev

from eventbook.models import Fill, Side
from eventbook.strategies.relationships import RelativeValueSignal


@dataclass(frozen=True)
class EquityPoint:
    timestamp_ns: int
    equity_cents: int


@dataclass(frozen=True)
class EvaluationMetrics:
    gross_pnl_cents: int | None
    net_pnl_cents: int | None
    sharpe_ratio: float | None
    maximum_drawdown_cents: int | None
    win_rate: float | None
    turnover_cents: int
    average_holding_period_ns: float | None
    fill_rate: float | None
    canceled_order_rate: float | None
    adverse_selection_cents: float | None
    displayed_depth_capacity: int
    signal_count: int
    accepted_trade_count: int
    rejected_trade_count: int
    rejection_reasons: dict[str, int]
    bootstrap_net_pnl_interval_cents: tuple[float, float] | None

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate_research_run(
    fills: list[Fill],
    settlements: dict[str, bool] | None,
    equity_curve: list[EquityPoint],
    signal_log: list[dict],
    signals: list[RelativeValueSignal],
    canceled_orders: int,
    submitted_order_count: int,
    post_fill_marks: dict[str, int] | None = None,
    annualization_periods: int = 252,
    bootstrap_seed: int = 7,
) -> EvaluationMetrics:
    gross_pnl, net_pnl, trade_pnls = _settlement_pnl(fills, settlements)
    accepted = [signal for signal in signals if signal.rejected_reason is None]
    rejected = [signal for signal in signals if signal.rejected_reason is not None]
    requested = sum(entry.get("requested", 0) for entry in signal_log)
    filled = sum(entry.get("filled", 0) for entry in signal_log)
    reasons = Counter(signal.rejected_reason for signal in rejected)
    return EvaluationMetrics(
        gross_pnl_cents=gross_pnl,
        net_pnl_cents=net_pnl,
        sharpe_ratio=_sharpe_ratio(equity_curve, annualization_periods),
        maximum_drawdown_cents=_maximum_drawdown(equity_curve),
        win_rate=_win_rate(trade_pnls),
        turnover_cents=sum(fill.price_cents * fill.quantity for fill in fills),
        average_holding_period_ns=_average_holding_period(fills),
        fill_rate=filled / requested if requested else None,
        canceled_order_rate=canceled_orders / submitted_order_count if submitted_order_count else None,
        adverse_selection_cents=_adverse_selection(fills, post_fill_marks),
        displayed_depth_capacity=sum(signal.available_quantity for signal in accepted),
        signal_count=len(signals),
        accepted_trade_count=len(accepted),
        rejected_trade_count=len(rejected),
        rejection_reasons=dict(reasons),
        bootstrap_net_pnl_interval_cents=_bootstrap_interval(trade_pnls, bootstrap_seed),
    )


def _settlement_pnl(fills: list[Fill], settlements: dict[str, bool] | None) -> tuple[int | None, int | None, list[int]]:
    if settlements is None or any(fill.ticker not in settlements for fill in fills):
        return None, None, []
    trade_pnls: list[int] = []
    for fill in fills:
        payout = 100 if settlements[fill.ticker] else 0
        gross = (payout - fill.price_cents) * fill.quantity if fill.side is Side.BID else (fill.price_cents - payout) * fill.quantity
        trade_pnls.append(gross - fill.fee_cents)
    gross_pnl = sum(trade_pnls) + sum(fill.fee_cents for fill in fills)
    return gross_pnl, sum(trade_pnls), trade_pnls


def _sharpe_ratio(equity_curve: list[EquityPoint], annualization_periods: int) -> float | None:
    if len(equity_curve) < 3:
        return None
    returns = [later.equity_cents - earlier.equity_cents for earlier, later in zip(equity_curve, equity_curve[1:])]
    if len(returns) < 2 or stdev(returns) == 0:
        return None
    return mean(returns) / stdev(returns) * sqrt(annualization_periods)


def _maximum_drawdown(equity_curve: list[EquityPoint]) -> int | None:
    if not equity_curve:
        return None
    peak = equity_curve[0].equity_cents
    maximum_drawdown = 0
    for point in equity_curve:
        peak = max(peak, point.equity_cents)
        maximum_drawdown = max(maximum_drawdown, peak - point.equity_cents)
    return maximum_drawdown


def _win_rate(trade_pnls: list[int]) -> float | None:
    return sum(pnl > 0 for pnl in trade_pnls) / len(trade_pnls) if trade_pnls else None


def _average_holding_period(fills: list[Fill]) -> float | None:
    """Match closing YES positions against the oldest open lot for each contract."""
    open_lots: dict[str, deque[list[int]]] = defaultdict(deque)
    holding_periods: list[int] = []
    for fill in sorted(fills, key=lambda item: item.timestamp_ns):
        direction = 1 if fill.side is Side.BID else -1
        remaining = fill.quantity
        lots = open_lots[fill.ticker]
        while remaining and lots and lots[0][0] * direction < 0:
            lot_direction, lot_quantity, opened_at = lots[0]
            closed_quantity = min(remaining, lot_quantity)
            holding_periods.extend([fill.timestamp_ns - opened_at] * closed_quantity)
            remaining -= closed_quantity
            lot_quantity -= closed_quantity
            if lot_quantity:
                lots[0][1] = lot_quantity
            else:
                lots.popleft()
        if remaining:
            lots.append([direction, remaining, fill.timestamp_ns])
    return mean(holding_periods) if holding_periods else None


def _adverse_selection(fills: list[Fill], post_fill_marks: dict[str, int] | None) -> float | None:
    if not fills or post_fill_marks is None:
        return None
    outcomes = []
    for fill in fills:
        if fill.order_id not in post_fill_marks:
            continue
        mark = post_fill_marks[fill.order_id]
        outcomes.append((fill.price_cents - mark) if fill.side is Side.BID else (mark - fill.price_cents))
    return mean(outcomes) if outcomes else None


def _bootstrap_interval(trade_pnls: list[int], seed: int, samples: int = 1_000) -> tuple[float, float] | None:
    if len(trade_pnls) < 2:
        return None
    random = Random(seed)
    sampled_totals = sorted(sum(random.choice(trade_pnls) for _ in trade_pnls) for _ in range(samples))
    return sampled_totals[int(samples * 0.025)], sampled_totals[int(samples * 0.975)]
