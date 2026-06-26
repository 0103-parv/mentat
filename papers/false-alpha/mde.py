"""Minimum detectable edge vs N — the analytic recall floor behind the power surface.

The power surface (§4.5) shows empirically that the detectable-edge threshold rises with N.
Here is its closed form. A strategy with TRUE per-bar worst-regime Sharpe mu clears the gate
(at the median, power 0.5) when mu - sqrt(var)*env(N,k) >= target, with var=(1+0.5 mu^2)/T
the Lo (2002) Sharpe-estimator variance and env(N,k) the best-of-N null envelope. Solving
for mu gives the Minimum Detectable Edge:

  MDE(N) = the smallest true worst-regime Sharpe a strategy needs to survive a search of
           size N.

We report it under the STANDARD single-Sharpe envelope (what the DSR uses) and the CORRECTED
worst-of-k envelope (§4.9). The corrected MDE is the honest recall floor; the standard one
is ~2.4x's worth too high. Both rise like ~sqrt(2 ln N): scaling the search lifts the floor.

  python3.14 papers/false-alpha/mde.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mentat.trade_lab import PERIODS_PER_YEAR, expected_max_sharpe_under_null  # noqa: E402
from theory import mc_expected_max  # noqa: E402

_ANN = math.sqrt(PERIODS_PER_YEAR)
NS = [10, 30, 100, 300, 1000, 3000]
T = 500            # worst-regime OOS length on real markets
K = 3
TARGET = 0.5       # annualized survival bar


def mde(N: int, env_per_obs: float, target_ann: float = TARGET, t: int = T) -> float:
    """Solve mu_pb = target_pb + env*sqrt((1+0.5 mu_pb^2)/t) by fixed point; return annualized."""
    target_pb = target_ann / _ANN
    mu = target_pb
    for _ in range(50):
        var = (1.0 + 0.5 * mu * mu) / t
        mu_new = target_pb + env_per_obs * math.sqrt(max(var, 0.0))
        if abs(mu_new - mu) < 1e-9:
            break
        mu = mu_new
    return mu * _ANN


def main() -> int:
    print(f"MINIMUM DETECTABLE EDGE vs N  (worst-of-{K} regimes, T={T}, target={TARGET} ann)\n")
    print(f"  {'N':>6} {'MDE standard DSR':>18} {'MDE corrected (§4.9)':>22} {'ratio':>7}")
    rows = []
    for N in NS:
        env_std = expected_max_sharpe_under_null(N, T, 0.0) * math.sqrt(T)  # per-obs units
        env_cor = mc_expected_max(N, K, 3000, seed=9)
        mde_std = mde(N, env_std)
        mde_cor = mde(N, env_cor)
        rows.append({"N": N, "mde_standard": round(mde_std, 3),
                     "mde_corrected": round(mde_cor, 3),
                     "ratio": round(mde_std / mde_cor, 3) if mde_cor else None})
        print(f"  {N:>6} {mde_std:>18.2f} {mde_cor:>22.2f} {mde_std/mde_cor:>7.2f}")
    print("\n=> The honest recall floor (corrected) rises from a true worst-regime Sharpe of")
    print(f"   ~{rows[0]['mde_corrected']:.1f} at N=10 to ~{rows[-1]['mde_corrected']:.1f} at "
          f"N=3000 — so at LLM scale a strategy needs a genuine worst-regime Sharpe well above")
    print("   1 just to be PROVABLE. The standard DSR overstates this floor ~2.4x. Either way,")
    print("   moderate real edges fall below the floor and cannot be claimed — the §4.5 result,")
    print("   now in closed form.")
    out = "papers/false-alpha/mde_results.json"
    Path(out).write_text(json.dumps({"config": {"T": T, "k": K, "target": TARGET, "NS": NS},
                                     "rows": rows}, indent=2))
    print(f"\n(results -> {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
