"""Unit tests for the new math + experiment invariants (run under python3.14).

  cd ~/mentat/papers/false-alpha && python3.14 test_theory.py
Asserts the extreme-value identities, the worst-of-k over-deflation direction, the
participation-ratio monotonicities, and the load-bearing experiment invariants (real
markets give 0 survivors; the gate still passes the planted edge). Keeps the math honest.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from theory import (  # noqa: E402
    deflation_equivalent_N, effective_n_participation, evt_expected_max_analytic,
    evt_quantile, mc_expected_max, worst_of_k_quantile,
)

_n = 0


def check(cond, name):
    global _n
    _n += 1
    print(f"  {'ok ' if cond else 'FAIL'} {name}")
    assert cond, name


def main() -> int:
    print("THEORY + EXPERIMENT INVARIANT TESTS\n")

    # (A) EVT: MC ~ Gumbel analytic; quantile < E[max] < sqrt(2 ln N)+small
    for N in (100, 1000):
        mc = mc_expected_max(N, 1, reps=3000, seed=3)
        g = evt_expected_max_analytic(N)
        check(abs(mc - g) < 0.12, f"EVT MC≈Gumbel at N={N} (mc={mc:.3f} g={g:.3f})")
        check(evt_quantile(N) < mc < math.sqrt(2 * math.log(N)) + 0.1,
              f"EVT ordering quantile<E[max]<~sqrt(2lnN) at N={N}")

    # (B) worst-of-k: min-of-3 envelope is well below the single-Sharpe one (over-deflation)
    for N in (100, 1000):
        e1 = evt_expected_max_analytic(N)
        e3 = mc_expected_max(N, 3, reps=3000, seed=3)
        check(e3 < e1, f"worst-of-3 envelope < single-Sharpe at N={N}")
        check(1.8 < e1 / e3 < 4.0, f"over-deflation ratio in [1.8,4] at N={N} ({e1/e3:.2f})")
    # min-of-3 quantile < single quantile; envelope increases in M
    check(worst_of_k_quantile(1000, 3) < worst_of_k_quantile(1000, 1),
          "worst-of-3 quantile < worst-of-1 quantile")
    check(mc_expected_max(5, 3, 2000) < mc_expected_max(1000, 3, 2000),
          "worst-of-3 envelope increases with M")
    # the trap: small M -> near-zero envelope (why the M_eff plug-in fails)
    check(mc_expected_max(5, 3, 2000) < 0.1, "worst-of-3 envelope ~0 at M=5 (the M_eff trap)")

    # (B2) robustness dividend: N' << N, and smaller for more regimes
    np3 = deflation_equivalent_N(1000, 3, reps=3000)
    np2 = deflation_equivalent_N(1000, 2, reps=3000)
    check(np3 < 30, f"worst-of-3 at N=1000 ~ single-Sharpe at N'<30 (N'={np3:.0f})")
    check(np3 < np2, "more regimes -> smaller deflation-equivalent N' (more protection)")

    # (B2c) the dividend collapses as regimes correlate
    from theory import deflation_equivalent_N_corr, mc_max_of_min_correlated
    check(mc_max_of_min_correlated(1000, 3, 0.0, 1500)
          < mc_max_of_min_correlated(1000, 3, 0.9, 1500),
          "worst-of-k envelope rises with regime correlation rho")
    check(deflation_equivalent_N_corr(1000, 3, 0.0, 1500)
          < deflation_equivalent_N_corr(1000, 3, 0.8, 1500),
          "deflation-equivalent N' rises with rho_reg (dividend collapses)")
    rc = json.loads((Path(__file__).resolve().parent
                     / "regime_correlation_results.json").read_text())
    rho = {r["market"]: r["rho_reg"] for r in rc["measured"]}
    noise_rho = next(v for k, v in rho.items() if k.startswith("noise"))
    check(rho["real:fred_SP500"] > noise_rho,
          "measured: real regimes more correlated than the adversarial synthetic null")

    # (B3) the engine-level corrected haircut matches the theory direction
    from mentat.trade_lab import expected_max_sharpe_under_null, expected_max_worst_of_k
    h1 = expected_max_sharpe_under_null(1000, 500, 0.0)
    hk = expected_max_worst_of_k(1000, 3, 500, 0.0)
    check(hk < h1, "engine: worst-of-3 haircut < single-Sharpe haircut")
    check(1.8 < h1 / hk < 4.0, f"engine: over-deflation ratio in [1.8,4] ({h1/hk:.2f})")
    check(expected_max_worst_of_k(1000, 1, 500, 0.0) > 0, "engine: k=1 worst-of-k is positive")

    # (B4) Lo (2002) HAC variance ratio on series with known autocorrelation
    from theory import hac_variance_ratio
    from mentat.trade_lab import _LCG
    rng = _LCG(5)
    iid = [rng.gauss() for _ in range(3000)]
    check(abs(hac_variance_ratio(iid) - 1.0) < 0.3, "HAC eta^2 ~1 on i.i.d.")
    rng = _LCG(6); ar = [0.0]
    for _ in range(3000):
        ar.append(0.6 * ar[-1] + rng.gauss())
    check(hac_variance_ratio(ar[1:]) > 1.5, "HAC eta^2 >1 on AR(1) positive (persistence)")
    rng = _LCG(7); mr = [0.0]
    for _ in range(3000):
        mr.append(-0.5 * mr[-1] + rng.gauss())
    check(hac_variance_ratio(mr[1:]) < 1.0, "HAC eta^2 <1 on mean-reverting")
    # the Lo diagnostic recorded: autocorrelation is NOT the cause (eta^2~1.07, Var(z)~4.6)
    lo = json.loads((Path(__file__).resolve().parent / "lo_diagnostic_results.json").read_text())
    check(all(0.9 < lo[g]["eta2_median"] < 1.3 for g in lo),
          "Lo diag: strategy autocorrelation is negligible (eta^2~1)")
    check(all(lo[g]["var_z_iid"] > 2.0 for g in lo),
          "Lo diag: Var(z) >> 1 from structural heterogeneity, not autocorrelation")

    # (C) participation-ratio effective-N
    check(abs(effective_n_participation(0.0, 1000) - 1000) < 1e-6, "M_eff(0)=N")
    check(effective_n_participation(0.05, 1000) < effective_n_participation(0.005, 1000),
          "M_eff decreases with <rho^2>")
    check(effective_n_participation(0.2, 3000) < 10, "M_eff(0.2,3000)≈5 (the trap value)")

    # (D) experiment invariants from committed artifacts (no recompute drift)
    base = Path(__file__).resolve().parent
    nsweep = json.loads((base / "nsweep_results.json").read_text())["rows"]
    real0 = [r for r in nsweep if r["market"].startswith("real") and r["survivors"] > 0]
    check(not real0, "nsweep: 0 survivors on real S&P at every N")
    planted_pos = [r for r in nsweep if r["market"] == "planted" and r["N"] >= 1000
                   and r["survivors"] > 0]
    check(bool(planted_pos), "nsweep: planted control has survivors at large N")
    boot = json.loads((base / "bootstrap_results.json").read_text())["rows"]
    real_boot = [r for r in boot if r["market"].startswith("real") and r["rc_survivors"] > 0]
    check(not real_boot, "bootstrap: 0 RC survivors on real at every N/block")
    cd = json.loads((base / "corrected_deflation_results.json").read_text())
    check(cd["verdict"]["worstk_at_N_real_survivors"] == 0,
          "corrected: worst-of-k@N keeps 0 survivors on real")
    check(cd["verdict"]["effectiveN_plugin_real_survivors"] > 0,
          "corrected: effective-N plug-in DOES manufacture false survivors (the trap, recorded)")

    print(f"\n{_n} checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
