"""Unit tests for the new math + experiment invariants (run under python3.14).

  cd ~/mentat/papers/false-alpha && python3.14 test_theory.py
Asserts the extreme-value identities, the worst-of-k over-deflation direction, the
participation-ratio monotonicities, and the load-bearing experiment invariants (real
markets give 0 survivors; the gate still passes the planted edge). Keeps the math honest.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from theory import (  # noqa: E402
    effective_n_participation, evt_expected_max_analytic, evt_quantile, mc_expected_max,
    worst_of_k_quantile,
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

    # (C) participation-ratio effective-N
    check(abs(effective_n_participation(0.0, 1000) - 1000) < 1e-6, "M_eff(0)=N")
    check(effective_n_participation(0.05, 1000) < effective_n_participation(0.005, 1000),
          "M_eff decreases with <rho^2>")
    check(effective_n_participation(0.2, 3000) < 10, "M_eff(0.2,3000)≈5 (the trap value)")

    # (D) experiment invariants from committed artifacts (no recompute drift)
    import json
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
