"""Explicit relationship rules for research-only relative-value signals."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from eventbook.models import Side
from eventbook.orderbook import OrderBook

RelationshipType = Literal["threshold_monotonicity", "mutually_exclusive", "intersection_upper_bound", "union_lower_bound"]


@dataclass(frozen=True)
class Relationship:
    relationship_type: RelationshipType
    event_id: str
    tickers: tuple[str, ...]
    payoff_bound_cents: int = 100


@dataclass(frozen=True)
class ExecutionAssumptions:
    taker_fee_bps: int = 0
    latency_penalty_cents: int = 0

    def __post_init__(self) -> None:
        if self.taker_fee_bps < 0 or self.latency_penalty_cents < 0:
            raise ValueError("fee and latency assumptions must be nonnegative")


@dataclass(frozen=True)
class RelativeValueSignal:
    relationship_type: RelationshipType
    event_id: str
    tickers: tuple[str, ...]
    theoretical_discrepancy_cents: int
    executable_discrepancy_cents: int
    available_quantity: int
    fee_adjusted_edge_cents: int
    latency_adjusted_edge_cents: int
    rejected_reason: str | None


def load_relationships(path: str | Path) -> list[Relationship]:
    """Load only explicit, human-reviewed semantic mappings from YAML."""
    document = yaml.safe_load(Path(path).read_text()) or {}
    return [_parse_relationship(entry) for entry in document.get("relationships", [])]


def _parse_relationship(entry: dict) -> Relationship:
    relationship_type = entry["type"]
    event_id = entry["event"]
    if relationship_type == "threshold_monotonicity":
        tickers = (entry["lower_threshold_ticker"], entry["higher_threshold_ticker"])
    elif relationship_type == "mutually_exclusive":
        tickers = tuple(entry["tickers"])
    elif relationship_type in {"intersection_upper_bound", "union_lower_bound"}:
        tickers = (entry["primary_ticker"], entry["first_component_ticker"], entry["second_component_ticker"])
    else:
        raise ValueError(f"unsupported relationship type: {relationship_type}")
    if len(tickers) < 2 or len(set(tickers)) != len(tickers):
        raise ValueError("relationship must contain distinct tickers")
    return Relationship(relationship_type, event_id, tickers, entry.get("payoff_bound_cents", 100))


def detect_relationships(books: dict[str, OrderBook], relationships: list[Relationship], assumptions: ExecutionAssumptions) -> list[RelativeValueSignal]:
    return [detect_relationship(books, relationship, assumptions) for relationship in relationships]


def detect_relationship(books: dict[str, OrderBook], relationship: Relationship, assumptions: ExecutionAssumptions) -> RelativeValueSignal:
    if relationship.relationship_type == "threshold_monotonicity":
        return _threshold_signal(books, relationship, assumptions)
    if relationship.relationship_type == "mutually_exclusive":
        return _mutually_exclusive_signal(books, relationship, assumptions)
    return _probability_bound_signal(books, relationship, assumptions)


def _quote(book: OrderBook, side: Side) -> tuple[int, int] | None:
    price = book.best_ask if side is Side.ASK else book.best_bid
    return None if price is None else (price, book.levels[side][price])


def _threshold_signal(books: dict[str, OrderBook], relationship: Relationship, assumptions: ExecutionAssumptions) -> RelativeValueSignal:
    lower_ticker, higher_ticker = relationship.tickers
    # Selling the higher threshold and buying the lower is the executable monotonicity trade.
    lower_ask = _quote(books.get(lower_ticker, OrderBook()), Side.ASK)
    higher_bid = _quote(books.get(higher_ticker, OrderBook()), Side.BID)
    if lower_ask is None or higher_bid is None:
        return _rejected(relationship, "missing_executable_quote")
    buy_price, buy_quantity = lower_ask
    sell_price, sell_quantity = higher_bid
    return _signal(relationship, sell_price - buy_price, min(buy_quantity, sell_quantity), buy_price + sell_price, assumptions)


def _mutually_exclusive_signal(books: dict[str, OrderBook], relationship: Relationship, assumptions: ExecutionAssumptions) -> RelativeValueSignal:
    bids = [_quote(books.get(ticker, OrderBook()), Side.BID) for ticker in relationship.tickers]
    if any(quote is None for quote in bids):
        return _rejected(relationship, "missing_executable_quote")
    executable_bids = [quote for quote in bids if quote is not None]
    total_bid = sum(price for price, _ in executable_bids)
    quantity = min(quantity for _, quantity in executable_bids)
    return _signal(relationship, total_bid - relationship.payoff_bound_cents, quantity, total_bid, assumptions)


def _probability_bound_signal(books: dict[str, OrderBook], relationship: Relationship, assumptions: ExecutionAssumptions) -> RelativeValueSignal:
    primary, first_component, second_component = relationship.tickers
    primary_bid = _quote(books.get(primary, OrderBook()), Side.BID)
    primary_ask = _quote(books.get(primary, OrderBook()), Side.ASK)
    component_asks = [_quote(books.get(ticker, OrderBook()), Side.ASK) for ticker in (first_component, second_component)]
    component_bids = [_quote(books.get(ticker, OrderBook()), Side.BID) for ticker in (first_component, second_component)]
    if relationship.relationship_type == "intersection_upper_bound":
        if primary_bid is None or any(quote is None for quote in component_asks):
            return _rejected(relationship, "missing_executable_quote")
        comparison = min(quote for quote in component_asks if quote is not None)
        return _signal(relationship, primary_bid[0] - comparison[0], min(primary_bid[1], comparison[1]), primary_bid[0] + comparison[0], assumptions)
    if primary_ask is None or any(quote is None for quote in component_bids):
        return _rejected(relationship, "missing_executable_quote")
    comparison = max(quote for quote in component_bids if quote is not None)
    return _signal(relationship, comparison[0] - primary_ask[0], min(primary_ask[1], comparison[1]), primary_ask[0] + comparison[0], assumptions)


def _signal(relationship: Relationship, discrepancy: int, quantity: int, fee_notional: int, assumptions: ExecutionAssumptions) -> RelativeValueSignal:
    fee = (fee_notional * assumptions.taker_fee_bps + 9_999) // 10_000
    fee_adjusted = discrepancy - fee
    latency_adjusted = fee_adjusted - assumptions.latency_penalty_cents
    reason = None if quantity > 0 and latency_adjusted > 0 else "insufficient_depth" if quantity <= 0 else "net_executable_edge_nonpositive"
    return RelativeValueSignal(relationship.relationship_type, relationship.event_id, relationship.tickers, discrepancy, discrepancy, quantity, fee_adjusted, latency_adjusted, reason)


def _rejected(relationship: Relationship, reason: str) -> RelativeValueSignal:
    return RelativeValueSignal(relationship.relationship_type, relationship.event_id, relationship.tickers, 0, 0, 0, 0, 0, reason)
