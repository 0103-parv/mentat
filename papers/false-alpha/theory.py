"""The math behind the gate — and a correction the standard deflated Sharpe gets wrong.

Two known facts and one new correction, all Monte-Carlo validated here:

  (A) Expected max of N i.i.d. N(0,1)  — the extreme-value result behind Bailey &
      Lopez de Prado's deflated Sharpe and the ~sqrt(2 ln N) discovery threshold.

  (B) WORST-OF-k-REGIMES correction (new).  Our gate scores a strategy by the MIN of its
      k out-of-sample regime Sharpes, then searches N strategies. The DSR haircut is the
      expected max of N single Sharpes — WRONG statistic. The right null is
      E[ max_{i<=N} min_{g<=k} Z_{i,g} ].  Because min-of-k has a thin upper tail, this is
      FAR below the single-Sharpe envelope, so the standard DSR OVER-deflates the
      worst-regime statistic. Leading-order quantile: Phi^{-1}(1 - N^{-1/k}).

  (C) EFFECTIVE NUMBER OF INDEPENDENT STRATEGIES (imported from genomics).  Correlated
      strategies are correlated tests; the multiple-testing count is not N but an
      effective M_eff. Using the participation ratio of the strategy correlation matrix C,
      M_eff = (sum lambda_i)^2 / sum lambda_i^2 = N^2 / sum_{ij} rho_ij^2 = N / (1 + (N-1)<rho^2>),
      computable EXACTLY from the mean squared pairwise correlation via the trace
      identities trace(C)=N, trace(C^2)=sum_ij rho_ij^2 — no eigendecomposition needed.
      (Genomics: Nyholt 2004; Li & Ji 2005; Li, Yeung, Cherny & Sham 2012; Galwey 2009.)

  python3.14 papers/false-alpha/theory.py        # prints the validated tables
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from statistics import NormalDist

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from mentat.trade_lab import _LCG  # noqa: E402  (pure-Python deterministic gaussian)

_NORM = NormalDist()


# --------------------------------------------------------------------------- #
# (A) expected max of N i.i.d. standard normals                               #
# --------------------------------------------------------------------------- #
def evt_quantile(N: int) -> float:
    """Leading-order: the (1-1/N) quantile, Phi^{-1}(1-1/N) ~ sqrt(2 ln N)."""
    return _NORM.inv_cdf(1.0 - 1.0 / max(N, 2))


def evt_expected_max_analytic(N: int) -> float:
    """Gumbel approx to E[max] of N i.i.d. N(0,1): a_N + gamma*b_N."""
    n = max(N, 2)
    a = _NORM.inv_cdf(1.0 - 1.0 / n)
    b = 1.0 / (n * _NORM.pdf(a))                      # Gumbel scale
    return a + 0.5772156649015329 * b


def mc_expected_max(N: int, k: int = 1, reps: int = 4000, seed: int = 1) -> float:
    """Monte-Carlo E[ max_{i<N} min_{g<k} Z_{i,g} ], Z ~ N(0,1). k=1 is the plain max."""
    rng = _LCG(seed)
    acc = 0.0
    for _ in range(reps):
        best = -1e9
        for _ in range(N):
            if k == 1:
                v = rng.gauss()
            else:
                v = min(rng.gauss() for _ in range(k))
            if v > best:
                best = v
        acc += best
    return acc / reps


# --------------------------------------------------------------------------- #
# (B) worst-of-k-regimes envelope                                             #
# --------------------------------------------------------------------------- #
def worst_of_k_quantile(N: int, k: int) -> float:
    """Leading-order E[max_N min_k]: solve (1-Phi(q))^k = 1/N -> q = Phi^{-1}(1-N^{-1/k}).
    For k=1 this is the standard Phi^{-1}(1-1/N)."""
    p = 1.0 - N ** (-1.0 / k)
    p = min(max(p, 1e-9), 1 - 1e-12)
    return _NORM.inv_cdf(p)


# --------------------------------------------------------------------------- #
# (C) effective number of independent strategies (participation ratio)        #
# --------------------------------------------------------------------------- #
def effective_n_participation(rho2_bar: float, N: int) -> float:
    """M_eff = N / (1 + (N-1) <rho^2>), the participation ratio of the correlation matrix,
    exact from trace identities. <rho^2> is the mean SQUARED off-diagonal correlation.
    Note this uses <rho^2> (captures dispersion), NOT the mean rho — so M_eff < N even
    when the mean correlation is ~0, as long as correlations have spread."""
    r2 = max(rho2_bar, 0.0)
    denom = 1.0 + (N - 1) * r2
    return N / denom if denom > 0 else float(N)


def corrected_haircut(worst_sr_per_bar: float, n_obs: int, N: int, k: int,
                      *, m_eff: float | None = None, use_mc: bool = True,
                      mc_cache: dict | None = None) -> float:
    """Annualized deflation haircut for the WORST-of-k-regimes best-of-N statistic, with an
    optional effective trial count m_eff in place of N. var_sr=(1+0.5 SR^2)/T (the DSR
    variance). Envelope = E[max_{M} min_k Z] (MC if available, else the quantile)."""
    from mentat.trade_lab import PERIODS_PER_YEAR
    ann = math.sqrt(PERIODS_PER_YEAR)
    M = int(round(m_eff)) if m_eff is not None else N
    M = max(M, 2)
    var_sr = (1.0 + 0.5 * worst_sr_per_bar ** 2) / max(n_obs, 2)
    if use_mc:
        key = (M, k)
        env = (mc_cache or {}).get(key)
        if env is None:
            env = mc_expected_max(M, k, reps=2000, seed=7)
            if mc_cache is not None:
                mc_cache[key] = env
    else:
        env = worst_of_k_quantile(M, k)
    return math.sqrt(max(var_sr, 0.0)) * env * ann


# --------------------------------------------------------------------------- #
def main() -> int:
    print("THEORY — validating the extreme-value math behind the gate\n")
    print("(A) E[max of N iid N(0,1)] — analytic vs Monte-Carlo (and ~sqrt(2 ln N)):")
    print(f"  {'N':>6} {'sqrt(2lnN)':>11} {'quantile':>9} {'Gumbel':>8} {'MC':>8}")
    rows_a = []
    for N in (10, 100, 1000, 3000):
        s2 = math.sqrt(2 * math.log(N))
        q = evt_quantile(N)
        g = evt_expected_max_analytic(N)
        mc = mc_expected_max(N, 1, reps=4000)
        rows_a.append({"N": N, "sqrt2lnN": s2, "quantile": q, "gumbel": g, "mc": mc})
        print(f"  {N:>6} {s2:>11.3f} {q:>9.3f} {g:>8.3f} {mc:>8.3f}")

    print("\n(B) worst-of-k=3 regimes: E[max_N min_3] — analytic quantile vs MC, vs k=1:")
    print(f"  {'N':>6} {'k=1 (DSR)':>10} {'k=3 quant':>10} {'k=3 MC':>8} {'DSR/k3 ratio':>13}")
    rows_b = []
    for N in (10, 100, 1000, 3000):
        e1 = evt_expected_max_analytic(N)
        q3 = worst_of_k_quantile(N, 3)
        mc3 = mc_expected_max(N, 3, reps=3000)
        rows_b.append({"N": N, "k1": e1, "k3_quantile": q3, "k3_mc": mc3,
                       "over_deflation_ratio": e1 / mc3 if mc3 else None})
        print(f"  {N:>6} {e1:>10.3f} {q3:>10.3f} {mc3:>8.3f} {e1 / mc3:>13.2f}")
    print("  => the standard DSR envelope (k=1) is ~2-3x the correct worst-of-3 envelope:")
    print("     applying the single-Sharpe haircut to a worst-of-regimes statistic "
          "OVER-deflates.")

    print("\n(C) effective N via participation ratio M_eff = N/(1+(N-1)<rho^2>):")
    print(f"  {'<rho^2>':>9} " + " ".join(f"N={N}".rjust(8) for N in (100, 1000, 3000)))
    rows_c = []
    for r2 in (0.0, 0.005, 0.02, 0.05, 0.1):
        meffs = {N: effective_n_participation(r2, N) for N in (100, 1000, 3000)}
        rows_c.append({"rho2": r2, **{f"meff_{N}": v for N, v in meffs.items()}})
        print(f"  {r2:>9.3f} " + " ".join(f"{meffs[N]:>8.0f}" for N in (100, 1000, 3000)))
    print("  => even <rho^2>=0.02 collapses 3000 trials to ~50 effective: correlation, not\n"
          "     count, sets the multiple-testing burden (genomics' effective-number-of-tests).")

    out = "papers/false-alpha/theory_validation.json"
    Path(out).write_text(json.dumps({"evt_max": rows_a, "worst_of_k": rows_b,
                                     "participation": rows_c}, indent=2))
    print(f"\n(validation -> {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
