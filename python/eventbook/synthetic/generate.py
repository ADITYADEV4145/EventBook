"""Deterministic, synthetic-only fixture generator; never exchange-derived data."""
from pathlib import Path
import json
def sample_events():
    t=1_700_000_000_000_000_000
    rows=[]; seq=0
    def add(ticker,side,action,price,qty,dt=1):
        nonlocal seq,t; seq+=1;t+=dt;rows.append(dict(timestamp_ns=t,sequence=seq,ticker=ticker,side=side,action=action,price_cents=price,quantity=qty,order_id=f"synthetic-{seq}"))
    add("TEMP_GT_50","bid","add",60,10); add("TEMP_GT_50","ask","add",62,10)
    add("TEMP_GT_60","bid","add",65,3); add("TEMP_GT_60","ask","add",68,5) # apparent monotonicity violation, shallow
    add("TEMP_GT_60","ask","cancel",68,5) # cancel before potential fill
    add("TEMP_GT_50","ask","modify",62,10); add("TEMP_GT_50","ask","trade",62,4) # partial depth left
    add("TEMP_GT_50","ask","cancel",62,6)
    add("TEMP_GT_50","ask","add",70,8) # widening spread after the near offer disappears
    add("RESOLVED_YES","bid","add",95,2); add("RESOLVED_YES","ask","add",100,2)
    return rows
def write_jsonl(path="data/synthetic/sample_events.jsonl"):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text("\n".join(json.dumps(r) for r in sample_events())+"\n");return p
if __name__=="__main__": print(write_jsonl())
