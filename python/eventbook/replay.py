from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
from random import Random
from .models import BookEvent, Side, Action, Fill, OrderRequest
from .orderbook import OrderBook

@dataclass(frozen=True)
class ReplayConfig:
    latency_ns: int = 0
    stochastic_latency_max_ns: int = 0
    maker_fee_bps: int = 0
    taker_fee_bps: int = 0
    fee_bps: int = 0  # Phase 1 compatibility; used as taker fee when set.
    queue_assumption: str = "optimistic"
    priority_ahead_multiplier: float = 0.0
    position_limit: int = 100
    seed: int = 7
    def __post_init__(self):
        if self.queue_assumption not in {"optimistic", "conservative"}: raise ValueError("unknown queue assumption")
        if min(self.latency_ns,self.stochastic_latency_max_ns,self.maker_fee_bps,self.taker_fee_bps,self.fee_bps,self.position_limit) < 0: raise ValueError("config values must be nonnegative")

@dataclass
class _LiveOrder:
    request: OrderRequest; arrival_ns: int; remaining: int; queue_ahead: int = 0; active: bool = False

@dataclass
class ReplayResult:
    fills: list[Fill]; signal_log: list[dict]; final_books: dict[str,OrderBook]; canceled_orders: int = 0
    def position(self, ticker:str) -> int:
        return sum(f.quantity if f.side is Side.BID else -f.quantity for f in self.fills if f.ticker == ticker)
    def fee_cents(self) -> int: return sum(f.fee_cents for f in self.fills)
    def settlement_pnl_cents(self, settlements:dict[str,bool]) -> tuple[int,int]:
        """Return gross/net PnL in cents, with YES settlement represented by True."""
        gross=0
        for f in self.fills:
            payout=100 if settlements.get(f.ticker, False) else 0
            gross += (payout-f.price_cents)*f.quantity if f.side is Side.BID else (f.price_cents-payout)*f.quantity
        return gross, gross-self.fee_cents()
    @property
    def gross_pnl_cents(self): return 0  # settlement status is required for meaningful PnL
    @property
    def net_pnl_cents(self): return -self.fee_cents()

class ReplayEngine:
    def __init__(self, events:list[BookEvent]): self.events=sorted(events,key=lambda e:(e.timestamp_ns,e.sequence))
    @classmethod
    def from_jsonl(cls,path:str|Path):
        return cls([BookEvent(timestamp_ns=r["timestamp_ns"],sequence=r["sequence"],ticker=r["ticker"],side=Side(r["side"]),action=Action(r["action"]),price_cents=r["price_cents"],quantity=r["quantity"],order_id=r.get("order_id", "")) for r in map(json.loads,Path(path).read_text().splitlines()) if r])
    @classmethod
    def from_parquet(cls,path:str|Path):
        try: import polars as pl
        except ImportError as exc: raise RuntimeError("Parquet support requires `pip install -e .[data]`") from exc
        return cls([BookEvent(**r,side=Side(r["side"]),action=Action(r["action"])) for r in pl.read_parquet(path).to_dicts()])
    @staticmethod
    def _fee(price:int, quantity:int, bps:int) -> int: return (price*quantity*bps+9999)//10000
    def run(self, strategy=None, config=ReplayConfig()):
        books:dict[str,OrderBook]={}; fills:list[Fill]=[]; log:list[dict]=[]; last_seq={}; live:dict[str,_LiveOrder]={}; canceled=0; rng=Random(config.seed)
        def normalize(raw, now, ticker):
            if isinstance(raw, OrderRequest): return raw
            return OrderRequest(ticker=raw.get("ticker",ticker),side=Side(raw["side"]),limit_cents=raw["limit_cents"],quantity=raw["quantity"],submitted_ns=raw.get("submitted_ns",now),order_id=raw.get("order_id",f"order-{len(live)+1}"))
        def capacity(request):
            pos=sum(f.quantity if f.side is Side.BID else -f.quantity for f in fills if f.ticker==request.ticker)
            return max(0, config.position_limit - abs(pos))
        def activate(order:_LiveOrder, now:int):
            book=books.get(order.request.ticker)
            if not book: return
            req=order.request; requested=min(order.remaining,capacity(req)); visible=book.executable(req.side,req.limit_cents,requested)
            if visible:
                book.consume(req.side,visible)
                for price,q in visible: fills.append(Fill(req.ticker,req.side,price,q,self._fee(price,q,config.taker_fee_bps or config.fee_bps),now,"taker",req.order_id))
                order.remaining-=sum(q for _,q in visible)
                log.append({"timestamp_ns":now,"ticker":req.ticker,"order_id":req.order_id,"requested":requested,"filled":sum(q for _,q in visible),"liquidity":"taker","reason":"filled" if not order.remaining else "partial_fill"})
            if order.remaining:
                displayed=book.levels[req.side].get(req.limit_cents,0)
                order.queue_ahead=displayed+(int(displayed*config.priority_ahead_multiplier) if config.queue_assumption=="conservative" else 0)
                order.active=True
        for current in self.events:
            if current.sequence<=last_seq.get(current.ticker,-1): raise ValueError("non-monotonic book sequence")
            last_seq[current.ticker]=current.sequence; book=books.setdefault(current.ticker,OrderBook())
            if current.action is Action.TRADE:
                for order in list(live.values()):
                    if not order.active or order.request.ticker!=current.ticker or order.request.side is not current.side or order.request.limit_cents!=current.price_cents: continue
                    ahead=min(order.queue_ahead,current.quantity); order.queue_ahead-=ahead; q=min(current.quantity-ahead,order.remaining,capacity(order.request))
                    if q:
                        order.remaining-=q; fills.append(Fill(order.request.ticker,order.request.side,current.price_cents,q,self._fee(current.price_cents,q,config.maker_fee_bps),current.timestamp_ns,"maker",order.request.order_id)); log.append({"timestamp_ns":current.timestamp_ns,"ticker":current.ticker,"order_id":order.request.order_id,"requested":q,"filled":q,"liquidity":"maker","reason":"passive_fill"})
            book.apply(current)
            for order in list(live.values()):
                if not order.active and order.arrival_ns<=current.timestamp_ns: activate(order,current.timestamp_ns)
            if strategy:
                for raw in strategy(current,books) or []:
                    if raw.get("action") == "cancel":
                        canceled += bool(live.pop(raw["order_id"],None)); continue
                    req=normalize(raw,current.timestamp_ns,current.ticker); jitter=rng.randint(0,config.stochastic_latency_max_ns) if config.stochastic_latency_max_ns else 0
                    live[req.order_id]=_LiveOrder(req,req.submitted_ns+config.latency_ns+jitter,req.quantity)
            for order in list(live.values()):
                if not order.active and order.arrival_ns<=current.timestamp_ns: activate(order,current.timestamp_ns)
            for oid,order in list(live.items()):
                if order.remaining==0: del live[oid]
        return ReplayResult(fills,log,books,canceled)
