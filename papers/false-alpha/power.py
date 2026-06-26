"""Gate power — does the deflated worst-regime gate admit a REALISTICALLY small edge, or
is it so conservative it rejects everything? (Tasks: the #1 reviewer/Jarvis critique.)

Two outputs:
  - a 1-D power curve at fixed N (the original slice), and
  - a 2-D power SURFACE over (planted edge magnitude x N) -> survivors and best realized
    worst-regime Sharpe (Task 3). The surface makes the central mechanism — the detectable
    edge threshold rising with N like ~sqrt(2 ln N) — a single artifact (power_surface.json),
    rendered by plot.py.

  cd ~/mentat && python3 papers/false-alpha/power.py            # curve + surface
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mentat.nsweep import (  # noqa: E402
    TARGET, _draw_pool, backtest_raw, deflated_ann, planted_universe,
)

STRENGTHS = [0.0, 0.02, 0.04, 0.06, 0.10, 0.15, 0.25, 0.40]
NS = [10, 30, 100, 300, 1000, 3000]
POOL = 3000


def _pool_metrics(strength: float):
    """Backtest a fixed pool once on planted_universe(strength); return per-alpha
    (worst_ann, raw) so survivors can be counted at any N by prefix."""
    bars = planted_universe(strength)
    alphas = _draw_pool("creative", f"power_{strength}", POOL)
    kept = [(a, r) for a in alphas for r in [backtest_raw(a, bars)] if r is not None]
    return kept


def surface():
    """2-D grid: rows = edge strength, cols = N. Each cell: survivors (deflated at N) and
    the best realized worst-regime Sharpe over the first N draws."""
    grid = []
    for s in STRENGTHS:
        kept = _pool_metrics(s)
        row = {"strength": s, "tradeable": len(kept), "cells": []}
        for N in NS:
            window = kept[:N]
            if not window:
                continue
            best_worst = max(r["worst_ann"] for _, r in window)
            surv = sum(1 for _, r in window if deflated_ann(r, N) >= TARGET)
            row["cells"].append({"N": N, "survivors": surv,
                                 "best_worst_sharpe": round(best_worst, 3)})
        grid.append(row)
    return grid


def main() -> int:
    print("GATE POWER SURFACE — survivors over (edge strength x N), creative search\n")
    grid = surface()
    Ns = NS
    print("  survivors  (rows=edge strength, cols=N):")
    print("    edge\\N  " + "".join(f"{N:>7}" for N in Ns))
    for row in grid:
        cells = {c["N"]: c for c in row["cells"]}
        print(f"    {row['strength']:>5.2f}  " +
              "".join(f"{cells[N]['survivors']:>7}" if N in cells else f"{'-':>7}" for N in Ns))
    print("\n  best worst-regime Sharpe  (rows=edge strength, cols=N):")
    print("    edge\\N  " + "".join(f"{N:>7}" for N in Ns))
    for row in grid:
        cells = {c["N"]: c for c in row["cells"]}
        print(f"    {row['strength']:>5.2f}  " +
              "".join(f"{cells[N]['best_worst_sharpe']:>+7.1f}" if N in cells else f"{'-':>7}"
                      for N in Ns))

    # detectable-edge threshold per N: smallest strength with >=1 survivor
    print("\n  detectable-edge threshold (smallest edge with a survivor) vs N:")
    for N in Ns:
        thr = next((row["strength"] for row in grid
                    if any(c["N"] == N and c["survivors"] >= 1 for c in row["cells"])), None)
        bw = None
        if thr is not None:
            r = next(row for row in grid if row["strength"] == thr)
            bw = next(c["best_worst_sharpe"] for c in r["cells"] if c["N"] == N)
        print(f"    N={N:>5}: edge>={thr if thr is not None else '>0.40'}"
              + (f"  (worst-Sharpe {bw:+.1f})" if bw is not None else "  (none admitted)"))

    out = "papers/false-alpha/power_surface.json"
    Path(out).write_text(json.dumps({
        "config": {"strengths": STRENGTHS, "Ns": NS, "pool": POOL, "target": TARGET,
                   "generator": "creative", "market": "planted_universe(strength)"},
        "grid": grid,
    }, indent=2))
    print(f"\n=> The detectable-edge threshold RISES with N: the same true edge that the "
          "gate admits\n   at small N is rejected at large N. Scaling the search raises the "
          "bar faster than it\n   finds edge — moderate edges become unprovable at scale. "
          f"(surface -> {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
