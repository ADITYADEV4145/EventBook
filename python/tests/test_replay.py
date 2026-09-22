import pytest
from eventbook.models import BookEvent,Side,Action
from eventbook.orderbook import OrderBook
from eventbook.replay import ReplayEngine,ReplayConfig
from eventbook.synthetic.generate import write_jsonl

def e(action,quantity=5): return BookEvent(1,1,"X",Side.BID,action,50,quantity)
def test_order_book_add_modify_cancel_trade_and_invariants():
    b=OrderBook();b.apply(e(Action.ADD));b.apply(BookEvent(2,2,"X",Side.BID,Action.MODIFY,50,7));b.apply(BookEvent(3,3,"X",Side.BID,Action.TRADE,50,2));assert b.levels[Side.BID][50]==5
    with pytest.raises(ValueError): b.apply(BookEvent(4,4,"X",Side.BID,Action.CANCEL,50,6))
def test_impossible_quantity_rejected():
    with pytest.raises(ValueError): BookEvent(1,1,"X",Side.BID,Action.ADD,50,0)
def test_deterministic_synthetic_replay(tmp_path):
    p=write_jsonl(tmp_path/"events.jsonl"); a=ReplayEngine.from_jsonl(p).run();b=ReplayEngine.from_jsonl(p).run();assert a.final_books["TEMP_GT_50"].spread==10 and len(a.fills)==len(b.fills)
def test_partial_fill_behavior():
    ev=[BookEvent(1,1,"X",Side.ASK,Action.ADD,60,2)]
    def strategy(e,books): return [{"side":"bid","limit_cents":60,"quantity":5}]
    r=ReplayEngine(ev).run(strategy,ReplayConfig());assert sum(x.quantity for x in r.fills)==2 and r.signal_log[0]["reason"]!="filled"
def test_fee_computation():
    ev=[BookEvent(1,1,"X",Side.ASK,Action.ADD,50,3)]
    r=ReplayEngine(ev).run(lambda e,b:[{"side":"bid","limit_cents":50,"quantity":3}],ReplayConfig(fee_bps=100));assert r.fills[0].fee_cents==2
def test_latency_causes_missed_execution():
    ev=[BookEvent(1,1,"X",Side.ASK,Action.ADD,40,1)]
    r=ReplayEngine(ev).run(lambda e,b:[{"side":"bid","limit_cents":40,"quantity":1,"submitted_ns":1}],ReplayConfig(latency_ns=2));assert not r.fills

def test_passive_order_fills_only_after_visible_queue_trades():
    ev=[
        BookEvent(1,1,"X",Side.BID,Action.ADD,50,5),
        BookEvent(2,2,"X",Side.BID,Action.TRADE,50,5),
        BookEvent(3,3,"X",Side.BID,Action.ADD,50,10),
        BookEvent(4,4,"X",Side.BID,Action.TRADE,50,10),
    ]
    def strategy(e,b): return [{"side":"bid","limit_cents":50,"quantity":3,"order_id":"maker"}] if e.sequence==1 else []
    r=ReplayEngine(ev).run(strategy,ReplayConfig(maker_fee_bps=100));assert len(r.fills)==1 and r.fills[0].liquidity=="maker" and r.fills[0].quantity==3 and r.fills[0].fee_cents==2

def test_conservative_queue_assumption_defers_passive_fill():
    ev=[BookEvent(1,1,"X",Side.BID,Action.ADD,50,5),BookEvent(2,2,"X",Side.BID,Action.ADD,50,3),BookEvent(3,3,"X",Side.BID,Action.TRADE,50,8)]
    r=ReplayEngine(ev).run(lambda e,b:[{"side":"bid","limit_cents":50,"quantity":3,"order_id":"m"}] if e.sequence==1 else [],ReplayConfig(queue_assumption="conservative",priority_ahead_multiplier=1));assert not r.fills

def test_settlement_pnl_and_position_limit():
    ev=[BookEvent(1,1,"X",Side.ASK,Action.ADD,40,5)]
    r=ReplayEngine(ev).run(lambda e,b:[{"side":"bid","limit_cents":40,"quantity":5}],ReplayConfig(position_limit=2,taker_fee_bps=100));assert r.position("X")==2 and r.settlement_pnl_cents({"X":True})==(120,119)

def test_seeded_stochastic_latency_is_deterministic_and_cancelable():
    ev=[BookEvent(1,1,"X",Side.ASK,Action.ADD,40,1),BookEvent(2,2,"X",Side.ASK,Action.CANCEL,40,1)]
    def strategy(e,b):
        if e.sequence==1:return [{"side":"bid","limit_cents":40,"quantity":1,"order_id":"late"}]
        return [{"action":"cancel","order_id":"late"}]
    a=ReplayEngine(ev).run(strategy,ReplayConfig(latency_ns=1,stochastic_latency_max_ns=4,seed=22));b=ReplayEngine(ev).run(strategy,ReplayConfig(latency_ns=1,stochastic_latency_max_ns=4,seed=22));assert not a.fills and a.canceled_orders==b.canceled_orders==1
