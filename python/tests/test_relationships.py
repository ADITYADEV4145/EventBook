from eventbook.models import Action, BookEvent, Side
from eventbook.orderbook import OrderBook
from eventbook.strategies.relationships import (
    ExecutionAssumptions,
    Relationship,
    detect_relationship,
    load_relationships,
)


def book_with_quote(ticker: str, bid: tuple[int, int], ask: tuple[int, int]) -> tuple[str, OrderBook]:
    book = OrderBook()
    book.apply(BookEvent(1, 1, ticker, Side.BID, Action.ADD, *bid))
    book.apply(BookEvent(2, 2, ticker, Side.ASK, Action.ADD, *ask))
    return ticker, book


def test_threshold_violation_uses_executable_prices_and_depth() -> None:
    books = dict([book_with_quote("GT_50", (58, 10), (62, 7)), book_with_quote("GT_60", (66, 3), (68, 10))])
    relationship = Relationship("threshold_monotonicity", "WEATHER", ("GT_50", "GT_60"))
    signal = detect_relationship(books, relationship, ExecutionAssumptions(taker_fee_bps=100))
    assert signal.available_quantity == 3
    assert signal.executable_discrepancy_cents == 4
    assert signal.fee_adjusted_edge_cents == 2
    assert signal.rejected_reason is None


def test_fee_and_latency_can_reject_apparent_threshold_edge() -> None:
    books = dict([book_with_quote("GT_50", (58, 10), (62, 1)), book_with_quote("GT_60", (63, 1), (68, 10))])
    relationship = Relationship("threshold_monotonicity", "WEATHER", ("GT_50", "GT_60"))
    signal = detect_relationship(books, relationship, ExecutionAssumptions(taker_fee_bps=100, latency_penalty_cents=1))
    assert signal.executable_discrepancy_cents == 1
    assert signal.rejected_reason == "net_executable_edge_nonpositive"


def test_mutually_exclusive_overpricing_uses_bids_not_midpoints() -> None:
    books = dict([book_with_quote("A", (55, 4), (57, 4)), book_with_quote("B", (48, 2), (50, 2))])
    relationship = Relationship("mutually_exclusive", "ELECTION", ("A", "B"))
    signal = detect_relationship(books, relationship, ExecutionAssumptions())
    assert signal.executable_discrepancy_cents == 3
    assert signal.available_quantity == 2
    assert signal.rejected_reason is None


def test_missing_quote_is_explicitly_rejected() -> None:
    relationship = Relationship("threshold_monotonicity", "WEATHER", ("GT_50", "GT_60"))
    signal = detect_relationship({}, relationship, ExecutionAssumptions())
    assert signal.rejected_reason == "missing_executable_quote"


def test_relationships_are_loaded_only_from_manual_yaml() -> None:
    relationships = load_relationships("configs/synthetic_relationships.yaml")
    assert relationships[0].tickers == ("TEMP_GT_50", "TEMP_GT_60")


def test_intersection_and_union_bounds_use_executable_crosses() -> None:
    books = dict([
        book_with_quote("INTERSECTION", (60, 2), (62, 2)),
        book_with_quote("UNION", (48, 2), (50, 2)),
        book_with_quote("A", (55, 3), (57, 3)),
        book_with_quote("B", (50, 4), (52, 4)),
    ])
    intersection = Relationship("intersection_upper_bound", "EVENT", ("INTERSECTION", "A", "B"))
    union = Relationship("union_lower_bound", "EVENT", ("UNION", "A", "B"))
    intersection_signal = detect_relationship(books, intersection, ExecutionAssumptions())
    union_signal = detect_relationship(books, union, ExecutionAssumptions())
    assert intersection_signal.executable_discrepancy_cents == 8
    assert union_signal.executable_discrepancy_cents == 5
