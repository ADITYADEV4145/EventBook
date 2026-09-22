import pytest
from eventbook.models import BookEvent,Side,Action
from eventbook.orderbook import OrderBook
from eventbook.replay import ReplayEngine,ReplayConfig
from eventbook.synthetic.generate import write_jsonl
from eventbook.strategies.relationships import threshold_monotonicity

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
def test_threshold_signal_rejects_negative_net_edge():
    s=threshold_monotonicity(62,65,3,fee_cents=4);assert s.rejected_reason=="net_executable_edge_nonpositive"
def test_latency_causes_missed_execution():
    ev=[BookEvent(1,1,"X",Side.ASK,Action.ADD,40,1)]
    r=ReplayEngine(ev).run(lambda e,b:[{"side":"bid","limit_cents":40,"quantity":1,"submitted_ns":1}],ReplayConfig(latency_ns=2));assert not r.fills
