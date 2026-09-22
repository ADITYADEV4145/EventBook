from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum

class Side(StrEnum): BID="bid"; ASK="ask"
class Action(StrEnum): ADD="add"; MODIFY="modify"; CANCEL="cancel"; TRADE="trade"
@dataclass(frozen=True)
class BookEvent:
    timestamp_ns: int; sequence: int; ticker: str; side: Side; action: Action; price_cents: int; quantity: int; order_id: str = ""
    def __post_init__(self):
        if self.timestamp_ns < 0 or self.sequence < 0: raise ValueError("timestamp and sequence must be nonnegative")
        if not 0 <= self.price_cents <= 100 or self.quantity <= 0: raise ValueError("price must be 0..100 cents; quantity must be positive")
@dataclass(frozen=True)
class Fill:
    ticker: str; side: Side; price_cents: int; quantity: int; fee_cents: int; timestamp_ns: int
