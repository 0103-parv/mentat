"""Task 5 — extend the live-LLM arm toward the full sweep on the real market.

The offline scaling story runs to N=3000 but the live LLM previously capped at N<=100. This
raises the LLM pool on the REAL S&P market (the scaling-story market) using the existing
batch + cache mechanism, so the model itself demonstrates the scaling phenomenon. Bounded to
the real market to cap API cost; the cached pool makes re-runs free.

Needs the live core: source ~/swechats/.env into the shell first (do NOT touch the Jarvis
daemon). H1/H3 re-confirmed at scale; H2 re-checked and reported as-is.

  set -a && . ~/swechats/.env; set +a
  ~/swechats/.venv/bin/python papers/false-alpha/task5_llm.py 1000
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import mentat.nsweep as ns  # noqa: E402
from mentat.trade_lab import load_price_csv  # noqa: E402

TARGET_POOL = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
SWEEP = [10, 30, 100, 300, 1000]


def main() -> int:
    ns._LLM_POOL_CAP = TARGET_POOL                      # raise the per-arm cap for this run
    bars = load_price_csv("data/fred_SP500.csv")
    print(f"Task 5 — extending live-LLM arm on real S&P to pool {TARGET_POOL}")
    from mentat.reasoning import core_available
    print(f"  core_available: {core_available()}")
    rows = ns.sweep_market("real:fred_SP500", bars, pool=TARGET_POOL, sweep=SWEEP,
                           generators=["llm"])
    out_rows = [r.__dict__ for r in rows]
    print(f"\n  {'N':>5} {'distinct':>8} {'bestOOS':>8} {'robust':>7} {'surv':>6} {'rho':>6}")
    for r in rows:
        print(f"  {r.N:>5} {r.distinct:>8} {r.best_naive:>+8.2f} {r.robust_raw:>7.2f} "
              f"{r.survivors:>6.2f} {r.rho_bar:>6.2f}")
    Path("papers/false-alpha/task5_llm_results.json").write_text(
        json.dumps({"target_pool": TARGET_POOL, "sweep": SWEEP, "rows": out_rows}, indent=2))
    print("\n(results -> papers/false-alpha/task5_llm_results.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
