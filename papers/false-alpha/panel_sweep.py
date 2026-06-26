"""Cross-sectional panel N-sweep (Task 2) — the generalization test.

Runs the SAME N-sweep + SAME gate (nsweep.sweep_market) on cross-sectional panel markets
instead of single index series. The four-control structure:
  cs_planted  : strong cross-sectional reversal edge (gate should pass it)
  cs_small    : a moderate cross-sectional edge below the bar (the recall story)
  cs_noise    : pure cross-sectional null
  real_panel  : 15 real large-caps (Yahoo OHLCV, data/panel_sp.csv) — REAL data

Long-short dollar-neutral portfolio per alpha; range/volume features are ACTIVE (real
OHLCV). If a survivor appears on the real panel it is reported, not suppressed — the gate
is byte-identical to the single-index path (the integrity invariant verify.py encodes).

  cd ~/mentat && python3 papers/false-alpha/panel_sweep.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mentat.nsweep import SweepRow, sweep_market  # noqa: E402
from mentat.panel_lab import load_panel_csv, synthetic_panel  # noqa: E402

POOL = 2000
SWEEP = [10, 30, 100, 300, 1000]
GENERATORS = ["random", "creative"]   # llm-on-panel needs the API; run separately if desired


def main() -> int:
    real_csv = Path(__file__).resolve().parents[2] / "data" / "panel_sp.csv"
    markets = [
        ("cs_planted", synthetic_panel(0.20)),   # strong edge
        ("cs_small", synthetic_panel(0.12)),     # moderate edge (below the bar)
        ("cs_noise", synthetic_panel(0.0)),      # null
    ]
    if real_csv.exists():
        markets.append(("real_panel:sp15", load_panel_csv(str(real_csv))))
    else:
        print(f"  (no {real_csv} — run fetch_panel.py first; skipping the real panel)")

    print("CROSS-SECTIONAL PANEL N-SWEEP — same gate, dollar-neutral long-short portfolio")
    print(f"  pool={POOL} | generators={GENERATORS} | range/volume features ACTIVE\n")
    all_rows: list[SweepRow] = []
    for name, panel in markets:
        rows = sweep_market(name, panel, pool=POOL, sweep=SWEEP, generators=GENERATORS)
        all_rows.extend(rows)

    hdr = (f"  {'market':18} {'gen':9} {'N':>5} {'nOOS>0':>7} {'bestOOS':>8} "
           f"{'robust':>7} {'surv@N':>7} {'rho':>6}")
    cur = None
    for r in all_rows:
        if (r.market, r.generator) != cur:
            print()
            print(hdr)
            cur = (r.market, r.generator)
        print(f"  {r.market:18} {r.generator:9} {r.N:>5} {r.naive_pos:>7} "
              f"{r.best_naive:>+8.2f} {r.robust_raw:>7.2f} {r.survivors:>7.2f} {r.rho_bar:>6.2f}")

    surv = [(r.market, r.generator, r.N, r.survivors) for r in all_rows
            if r.market.startswith("real_panel") and r.survivors > 0]
    print("\n=> Real panel survivors:", surv or "NONE at any N (zero holds on a real "
          "cross-sectional panel with range/volume active).")

    out = "papers/false-alpha/panel_results.json"
    Path(out).write_text(json.dumps({
        "config": {"pool": POOL, "sweep": SWEEP, "generators": GENERATORS,
                   "synthetic_edges": {"cs_planted": 0.20, "cs_small": 0.12, "cs_noise": 0.0},
                   "real_panel": "data/panel_sp.csv (15 large-caps, Yahoo OHLCV)"},
        "rows": [r.__dict__ for r in all_rows],
    }, indent=2))
    print(f"\n(results -> {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
