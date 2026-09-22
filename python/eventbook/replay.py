from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
from .models import BookEvent, Side, Action, Fill
from .orderbook import OrderBook

@dataclass(frozen=True)
class ReplayConfig:
    latency_ns: int = 0
    fee_bps: int = 0
    queue_assumption: str = "optimistic"  # optimistic or conservative
    priority_ahead_multiplier: int = 0
    position_limit: int = 100
    seed: int = 7

@dataclass
class ReplayResult:
    fills: list[Fill]; signal_log: list[dict]; final_books: dict[str,OrderBook]
    @property
    def gross_pnl_cents(self): return 0
    @property
    def net_pnl_cents(self): return -sum(f.fee_cents for f in self.fills)

class ReplayEngine:
    def __init__(self, events:list[BookEvent]): self.events=sorted(events,key=lambda e:(e.timestamp_ns,e.sequence))
    @classmethod
    def from_jsonl(cls,path:str|Path):
        return cls([BookEvent(timestamp_ns=r["timestamp_ns"],sequence=r["sequence"],ticker=r["ticker"],side=Side(r["side"]),action=Action(r["action"]),price_cents=r["price_cents"],quantity=r["quantity"],order_id=r.get("order_id", "")) for r in map(json.loads,Path(path).read_text().splitlines()) if r])
    @classmethod
    def from_parquet(cls,path:str|Path):
        try:
            import polars as pl
        except ImportError as exc: raise RuntimeError("Parquet support requires `pip install -e .[data]`") from exc
        return cls([BookEvent(**r,side=Side(r["side"]),action=Action(r["action"])) for r in pl.read_parquet(path).to_dicts()])
    def run(self,strategy=None,config=ReplayConfig()):
        books={}; fills=[]; log=[]; last_seq={}
        for e in self.events:
            if e.sequence<=last_seq.get(e.ticker,-1): raise ValueError("non-monotonic book sequence")
            last_seq[e.ticker]=e.sequence; book=books.setdefault(e.ticker,OrderBook()); book.apply(e)
            if strategy:
                for o in strategy(e,books) or []:
                    if e.timestamp_ns < o.get("submitted_ns",e.timestamp_ns)+config.latency_ns: continue
                    qty=o["quantity"]; side=Side(o["side"]); visible=book.executable(side,o["limit_cents"],qty)
                    if config.queue_assumption=="conservative" and visible:
                        p,q=visible[0]; visible[0]=(p,max(0,q-config.priority_ahead_multiplier))
                    total=sum(q for _,q in visible); fee=lambda p,q:(p*q*config.fee_bps+9999)//10000
                    for p,q in visible:
                        if q: fills.append(Fill(e.ticker,side,p,q,fee(p,q),e.timestamp_ns))
                    log.append({"timestamp_ns":e.timestamp_ns,"ticker":e.ticker,"requested":qty,"filled":total,"reason":"filled" if total==qty else "insufficient_depth_or_latency"})
        return ReplayResult(fills,log,books)
