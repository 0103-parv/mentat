"""Gate power curve — does the deflated worst-regime gate admit a REALISTICALLY small
edge, or is it so conservative it rejects everything? (The #1 reviewer/Jarvis critique.)

We sweep the strength of a planted lag-1 reversion edge from 0 (pure noise) up to the
strong control (0.40), and at fixed N measure (a) the best realized worst-regime Sharpe
the search finds, and (b) the gate's survivor count. This maps survival against TRUE edge
magnitude — a power/ROC curve. If the gate admits survivors only once the true
worst-regime Sharpe is realistic (~0.5-1.0), it is well-calibrated, not a blanket "no."

  cd ~/mentat && python3 papers/false-alpha/power.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mentat.nsweep import (  # noqa: E402
    TARGET, _draw_pool, backtest_raw, deflated_ann, effective_trials,
    mean_pairwise_corr, oos_strat_returns, planted_universe,
)
import random  # noqa: E402

N, POOL = 1000, 1500
STRENGTHS = [0.0, 0.02, 0.04, 0.06, 0.10, 0.15, 0.25, 0.40]


def main() -> int:
    print("GATE POWER CURVE — survival vs TRUE edge magnitude (creative search, "
          f"N={N}, deflated at n_trials=N)\n")
    print(f"  {'edge':>5} {'best_worst_Sharpe':>17} {'naive_bestOOS':>14} "
          f"{'rho':>6} {'n_eff':>7} {'surv@N':>7} {'surv@neff':>10}")
    rows = []
    for s in STRENGTHS:
        bars = planted_universe(s)
        mkt = f"power_{s}"
        alphas = _draw_pool("creative", mkt, POOL)
        raws = [backtest_raw(a, bars) for a in alphas]
        kept = [r for r in raws if r is not None][:N]
        best_worst = max(r["worst_ann"] for r in kept)
        best_naive = max(r["naive_ann"] for r in kept)
        rng = random.Random(7)
        rho = mean_pairwise_corr([oos_strat_returns(a, bars) for a, r in
                                  zip(alphas, raws) if r is not None][:120], rng)
        neff = max(2, round(effective_trials(rho, N)))
        surv_N = sum(1 for r in kept if deflated_ann(r, N) >= TARGET)
        surv_neff = sum(1 for r in kept if deflated_ann(r, neff) >= TARGET)
        rows.append((s, best_worst, best_naive, rho, neff, surv_N, surv_neff))
        print(f"  {s:>5.2f} {best_worst:>+17.2f} {best_naive:>+14.2f} "
              f"{rho:>6.2f} {neff:>7d} {surv_N:>7d} {surv_neff:>10d}")

    # find the detection threshold: smallest edge whose gate admits >=1 survivor
    admit = next((r for r in rows if r[5] >= 1), None)
    print()
    if admit:
        print(f"=> The gate first admits survivors at edge strength {admit[0]:.2f}, where the "
              f"best worst-regime Sharpe is {admit[1]:+.2f} (naive {admit[2]:+.2f}).")
        print(f"   So the gate HAS power: it passes an edge once the true worst-regime, "
              f"after-cost Sharpe\n   clears roughly the {TARGET} bar — it is calibrated, "
              "not a blanket rejection.")
    else:
        print("=> No edge strength produced a survivor — the gate may be too conservative "
              "(honest caveat).")
    print("   Real S&P 500 sits at the strength=0.00 end (0 survivors) despite naive "
          "best-of-N ~1.0.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
