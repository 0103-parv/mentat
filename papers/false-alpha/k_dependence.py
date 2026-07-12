"""How much the standard single-Sharpe DSR over-deflates the worst-of-k-regimes statistic,
as a function of the number of regimes k.

The gate scores each strategy by its worst (minimum) Sharpe across k out-of-sample regimes,
then keeps the best of N. The standard deflated-Sharpe envelope is E[max_N Z] for a single
Sharpe; the correct envelope is E[max_N min_k Z]. Their ratio is the over-deflation factor.
Because min-of-k has an ever-thinner upper tail as k grows, that factor is NOT a universal
constant — it grows with k. This script reports it at the relevant N so the paper's "~2.4x"
is stated as what it is: the value for our 3-regime gate.

  python3.14 papers/false-alpha/k_dependence.py
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np

N = 1000                 # representative search size (LLM-scale)
KS = [2, 3, 5]
REPS = 40_000            # replicates of a best-of-N draw
SEED = 20260709


def envelopes(N: int, reps: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    # single-Sharpe DSR envelope: E[max over N of Z]
    e_single = float(rng.standard_normal((reps, N)).max(1).mean())
    out = {"N": N, "reps": reps, "E_max_single": round(e_single, 4), "by_k": {}}
    for k in KS:
        z = rng.standard_normal((reps, N, k))
        e_wok = float(z.min(2).max(1).mean())          # E[max_N min_k Z]
        out["by_k"][str(k)] = {"E_max_min_k": round(e_wok, 4),
                               "over_deflation_x": round(e_single / e_wok, 3)}
    return out


def main() -> int:
    r = envelopes(N, REPS, SEED)
    print(f"Over-deflation of the worst-of-k statistic by the single-Sharpe DSR  (N={N}, {REPS} reps)\n")
    print(f"  E[max_N Z]  (single-Sharpe envelope): {r['E_max_single']:.3f}\n")
    print(f"  {'k (regimes)':>12} {'E[max_N min_k Z]':>18} {'over-deflation':>16}")
    for k in KS:
        d = r["by_k"][str(k)]
        print(f"  {k:>12} {d['E_max_min_k']:>18.3f} {d['over_deflation_x']:>14.2f}x")
    print(f"\n  Our gate uses k=3 -> ~{r['by_k']['3']['over_deflation_x']:.1f}x is the relevant figure; "
          f"it grows with k (thinner min-of-k tail), so it is not a universal constant.")
    out = Path(__file__).resolve().parent / "k_dependence.json"
    out.write_text(json.dumps(r, indent=2))
    print(f"\n(results -> {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
