from dataclasses import dataclass
@dataclass(frozen=True)
class Signal:
    type:str; theoretical_discrepancy_cents:int; executable_discrepancy_cents:int; quantity:int; fee_adjusted_edge_cents:int; latency_adjusted_edge_cents:int; rejected_reason:str|None=None
def threshold_monotonicity(lower_ask:int,higher_bid:int,quantity:int,fee_cents:int=0,latency_penalty_cents:int=0)->Signal:
    # Buy lower threshold / sell higher threshold only if executable order of probabilities is inverted.
    edge=higher_bid-lower_ask-fee_cents
    latency=edge-latency_penalty_cents
    reason=None if latency>0 and quantity>0 else ("insufficient_depth" if quantity<=0 else "net_executable_edge_nonpositive")
    return Signal("threshold_monotonicity",higher_bid-lower_ask,higher_bid-lower_ask,quantity,edge,latency,reason)
