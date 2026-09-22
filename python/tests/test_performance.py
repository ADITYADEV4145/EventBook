from eventbook.metrics.performance import EquityPoint, evaluate_research_run
from eventbook.models import Fill, Side
from eventbook.strategies.relationships import RelativeValueSignal


def signal(rejected_reason: str | None = None) -> RelativeValueSignal:
    return RelativeValueSignal("threshold_monotonicity", "WEATHER", ("GT_50", "GT_60"), 3, 3, 2, 2, 1, rejected_reason)


def test_evaluation_reports_settlement_pnl_depth_and_rejections() -> None:
    fills = [
        Fill("YES", Side.BID, 40, 2, 1, 10, order_id="buy"),
        Fill("NO", Side.ASK, 70, 1, 1, 20, order_id="sell"),
    ]
    metrics = evaluate_research_run(
        fills,
        {"YES": True, "NO": False},
        [EquityPoint(1, 0), EquityPoint(2, 10), EquityPoint(3, 5)],
        [{"requested": 4, "filled": 3}],
        [signal(), signal("net_executable_edge_nonpositive")],
        canceled_orders=1,
        submitted_order_count=4,
        post_fill_marks={"buy": 38, "sell": 65},
    )
    assert metrics.gross_pnl_cents == 190
    assert metrics.net_pnl_cents == 188
    assert metrics.fill_rate == 0.75
    assert metrics.canceled_order_rate == 0.25
    assert metrics.maximum_drawdown_cents == 5
    assert metrics.displayed_depth_capacity == 2
    assert metrics.rejection_reasons == {"net_executable_edge_nonpositive": 1}
    assert metrics.adverse_selection_cents == -1.5


def test_metrics_do_not_fabricate_unavailable_settlement_or_sharpe() -> None:
    metrics = evaluate_research_run([], None, [EquityPoint(1, 0)], [], [], 0, 0)
    assert metrics.gross_pnl_cents is None
    assert metrics.sharpe_ratio is None
    assert metrics.fill_rate is None


def test_fifo_holding_period_uses_closed_lots_only() -> None:
    fills = [
        Fill("YES", Side.BID, 40, 2, 0, 10),
        Fill("YES", Side.ASK, 60, 1, 0, 30),
        Fill("YES", Side.ASK, 60, 1, 0, 50),
    ]
    metrics = evaluate_research_run(fills, {"YES": True}, [], [], [], 0, 0)
    assert metrics.average_holding_period_ns == 30
