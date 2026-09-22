from __future__ import annotations
import argparse,json,csv
from pathlib import Path
from eventbook.replay import ReplayEngine,ReplayConfig
from eventbook.synthetic.generate import write_jsonl
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--config");ap.add_argument("--output",required=True);a=ap.parse_args()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=True); src=write_jsonl(); r=ReplayEngine.from_jsonl(src).run(config=ReplayConfig())
    summary={"mode":"research","synthetic":True,"fill_count":len(r.fills),"gross_pnl_cents":r.gross_pnl_cents,"net_pnl_cents":r.net_pnl_cents,"limitations":"No claim of profitability; synthetic replay only."}
    (out/"summary.json").write_text(json.dumps(summary,indent=2));
    try:
        import polars as pl
        pl.DataFrame([f.__dict__ | {"side": str(f.side)} for f in r.fills]).write_parquet(out/"trades.parquet")
    except ImportError:
        # The stdlib-only slice remains runnable; installing the data extra upgrades this to Parquet.
        (out/"trades.parquet.unavailable.txt").write_text("Install eventbook[data] to produce trades.parquet.\n")
    with (out/"signal_log.csv").open("w",newline="") as f: csv.DictWriter(f,fieldnames=["timestamp_ns","ticker","requested","filled","reason"]).writeheader()
    (out/"equity_curve.csv").write_text("timestamp_ns,net_pnl_cents\n")
    (out/"report.md").write_text("# Synthetic EventBook research report\n\n## Why apparent arbitrage may not be tradable\n\nDisplayed quotes can be stale, too shallow, canceled before arrival, or consumed before execution. Fees, spread crossing, partial fills, and fixed latency can eliminate a theoretical discrepancy. This synthetic report makes no profitability claim.\n")
    print(out)
if __name__=="__main__": main()
