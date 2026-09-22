from __future__ import annotations
from collections import defaultdict
from .models import BookEvent, Side, Action
class OrderBook:
    def __init__(self): self.levels={Side.BID:defaultdict(int),Side.ASK:defaultdict(int)}
    def apply(self,e:BookEvent):
        d=self.levels[e.side]; existing=d[e.price_cents]
        if e.action is Action.ADD: d[e.price_cents]+=e.quantity
        elif e.action is Action.MODIFY:
            if not existing: raise ValueError("modify of absent level")
            d[e.price_cents]=e.quantity
        else:
            if existing<e.quantity: raise ValueError("removal exceeds displayed depth")
            d[e.price_cents]-=e.quantity
            if not d[e.price_cents]: del d[e.price_cents]
        self._check()
    def _check(self):
        if any(q<=0 for d in self.levels.values() for q in d.values()): raise AssertionError("nonpositive level")
    @property
    def best_bid(self): return max(self.levels[Side.BID],default=None)
    @property
    def best_ask(self): return min(self.levels[Side.ASK],default=None)
    @property
    def spread(self): return None if self.best_bid is None or self.best_ask is None else self.best_ask-self.best_bid
    def executable(self,side:Side,limit:int,quantity:int):
        levels=self.levels[Side.ASK] if side is Side.BID else self.levels[Side.BID]
        prices=sorted(levels) if side is Side.BID else sorted(levels,reverse=True)
        left=quantity; fills=[]
        for p in prices:
            if (side is Side.BID and p>limit) or (side is Side.ASK and p<limit): break
            q=min(left,levels[p]); fills.append((p,q));left-=q
            if not left: break
        return fills
    def consume(self, side:Side, fills:list[tuple[int,int]]):
        """Remove taker fills from the opposite displayed book."""
        d=self.levels[Side.ASK] if side is Side.BID else self.levels[Side.BID]
        for price, quantity in fills:
            if d[price] < quantity: raise ValueError("fill exceeds displayed depth")
            d[price] -= quantity
            if not d[price]: del d[price]
        self._check()
