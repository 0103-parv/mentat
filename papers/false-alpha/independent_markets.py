"""Run the single-index N-sweep + gate on truly independent real markets (Task 4).

Reads the FX / commodity / crypto CSVs fetched by fetch_markets.py and runs the SAME sweep
+ gate as the S&P study. Writes independent_markets.json. Survivors per market per N per
generator; if a survivor appears in a less-efficient market it is reported, not suppressed.

  cd ~/mentat && python3 papers/false-alpha/independent_markets.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mentat.nsweep import SweepRow, sweep_market  # noqa: E402
from mentat.trade_lab import load_price_csv  # noqa: E402

POOL = 3000
SWEEP = [10, 30, 100, 300, 1000, 3000]
FILES = [("fx:EURUSD", "data/yh_EURUSD.csv"),
         ("commodity:GOLD", "data/yh_GOLD.csv"),
         ("crypto:BTCUSD", "data/yh_BTCUSD.csv")]


def main() -> int:
    rows: list[SweepRow] = []
    present = [(name, f) for name, f in FILES if Path(f).exists()]
    if not present:
        print("No market CSVs — run fetch_markets.py first.")
        return 1
    for name, f in present:
        bars = load_price_csv(f)
        rows.extend(sweep_market(name, bars, pool=POOL, sweep=SWEEP,
                                 generators=["random", "creative"]))

    hdr = f"  {'market':16} {'gen':9} {'N':>5} {'bestOOS':>8} {'robust':>7} {'surv':>6} {'rho':>6}"
    cur = None
    for r in rows:
        if (r.market, r.generator) != cur:
            print(); print(hdr); cur = (r.market, r.generator)
        print(f"  {r.market:16} {r.generator:9} {r.N:>5} {r.best_naive:>+8.2f} "
              f"{r.robust_raw:>7.2f} {r.survivors:>6.2f} {r.rho_bar:>6.2f}")

    surv = [(r.market, r.generator, r.N, r.survivors) for r in rows if r.survivors > 0]
    print("\n=> Survivors on independent markets:",
          surv or "NONE at any N (the zero holds across FX, commodity, and crypto).")
    out = "papers/false-alpha/independent_markets.json"
    Path(out).write_text(json.dumps(
        {"config": {"pool": POOL, "sweep": SWEEP, "markets": [f for _, f in present]},
         "rows": [r.__dict__ for r in rows]}, indent=2))
    print(f"(results -> {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
