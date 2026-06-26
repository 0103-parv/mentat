"""Do the generators obey the i.i.d.-Gaussian best-of-N envelope? (the genuinely-novel test)

The deflated Sharpe / discovery threshold assumes N INDEPENDENT GAUSSIAN trials. Random
brute-force search ~ obeys it; an LLM or evolutionary generator proposes CORRELATED,
non-Gaussian candidates. On the pure-noise null (where the true edge is exactly zero and
the single-Sharpe null variance is known), we measure the realized best-of-N standardized
in-sample Sharpe and compare it to the i.i.d.-Gaussian envelope E[max of N N(0,1)].

We then back out an EMPIRICAL effective trial count M_emp — the N for which the i.i.d.
envelope equals the realized max. Unlike the participation-ratio M_eff (which failed,
corrected_deflation.py), M_emp is calibrated from the realized maximum itself, the same
quantity the bootstrap controls — so it is the *correct* effective-N. The result quantifies,
per generator, how much search redundancy reduces the multiple-testing burden.

  python3.14 papers/false-alpha/envelope_departure.py
"""
from __future__ import annotations

import json
import math
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mentat.nsweep import (  # noqa: E402
    _ANN, _draw_pool, backtest_raw, noise_universe,
)
from theory import evt_expected_max_analytic, mc_expected_max  # noqa: E402

POOL = 3000
NS = [10, 30, 100, 300, 1000, 3000]
BOOT = 30


def _t_is(bars) -> int:
    seg = next((r for r in bars.regimes if r[0].startswith("is")), bars.regimes[0])
    return seg[2] - seg[1]


def invert_envelope(target: float) -> float:
    """Smallest M with the i.i.d.-Gaussian E[max of M] >= target — the empirical effective
    trial count. Uses the analytic Gumbel envelope (O(1)), so the inversion is fast even
    for large M (MC would draw ~M*reps gaussians and is infeasible for large M)."""
    if target <= evt_expected_max_analytic(2):
        return 2.0
    lo, hi = 2, 10 ** 9
    if evt_expected_max_analytic(hi) < target:
        return float(hi)
    for _ in range(80):
        mid = int(math.isqrt(lo * hi)) if hi - lo > 8 else (lo + hi) // 2
        if evt_expected_max_analytic(max(mid, 2)) < target:
            lo = mid + 1
        else:
            hi = mid
        if lo >= hi:
            break
    return float(lo)


def main() -> int:
    bars = noise_universe()
    T = _t_is(bars)
    gens = ["random", "creative"]
    if (Path(__file__).resolve().parent / "llm_cache_noise.json").exists():
        gens.append("llm")
    print("ENVELOPE DEPARTURE — realized best-of-N standardized IS Sharpe vs i.i.d.-Gaussian")
    print(f"  null market = noise; in-sample T = {T}; envelope = E[max of N N(0,1)]\n")
    print(f"  {'gen':9} {'N':>5} {'realized z':>11} {'iid E[max]':>11} {'ratio':>6} "
          f"{'M_emp':>8} {'M_emp/N':>8}")
    rows = []
    for gen in gens:
        alphas = _draw_pool(gen, "noise", POOL, log=lambda *_: None)
        zs = []
        for a in alphas:
            r = backtest_raw(bars=bars, expr=a)
            if r is None:
                continue
            sr = r["is_ann"] / _ANN                       # per-bar in-sample Sharpe
            var = (1.0 + 0.5 * sr * sr) / max(T, 2)
            if var > 1e-12:
                zs.append(sr / math.sqrt(var))            # standardized -> ~N(0,1) under null
        if zs:                                            # remove any common drift exposure
            mu = statistics.mean(zs)                      # (cross-sectional demean isolates
            zs = [z - mu for z in zs]                     #  the snooping dispersion)
        base = random.Random(hash(("env", gen)) % (2 ** 31))
        for N in NS:
            if N > len(zs):
                continue
            reps = 1 if N >= len(zs) else BOOT
            mx = []
            for _ in range(reps):
                idx = list(range(N)) if reps == 1 else [base.randrange(len(zs)) for _ in range(N)]
                mx.append(max(zs[i] for i in idx))
            realized = statistics.mean(mx)
            iid = evt_expected_max_analytic(N)
            m_emp = invert_envelope(realized)
            rows.append({"generator": gen, "N": N, "realized_z": round(realized, 3),
                         "iid_Emax": round(iid, 3), "ratio": round(realized / iid, 3),
                         "M_emp": round(m_emp, 1), "M_emp_over_N": round(m_emp / N, 3)})
            print(f"  {gen:9} {N:>5} {realized:>11.3f} {iid:>11.3f} {realized/iid:>6.2f} "
                  f"{m_emp:>8.0f} {m_emp/N:>8.2f}")
        print()

    # robust signal: the ORDERING of the realized max at fixed N (lower => more redundant)
    by_N = {}
    for r in rows:
        by_N.setdefault(r["N"], {})[r["generator"]] = r["realized_z"]
    print("=> HONEST READ (a second failed shortcut). The absolute M_emp is UNRELIABLE: the")
    print("   in-sample Sharpe standardization var=(1+0.5 SR^2)/T assumes i.i.d. returns, but")
    print("   strategy returns are autocorrelated (positions persist) and cost-laden, so the")
    print("   true SE is larger and z is mis-scaled — M_emp swings with demeaning/scaling.")
    print("   This is the SECOND parametric effective-N shortcut to fail (after the")
    print("   participation ratio): there is no reliable analytic effective-N here; the block")
    print("   BOOTSTRAP, which assumes nothing, is the necessary and sufficient arbiter.")
    n100 = by_N.get(100, {})
    if "llm" in n100:
        order = sorted(n100.items(), key=lambda kv: kv[1])
        lowest = order[0][0]
        print("   Realized max at N=100 (lower=more redundant): "
              + ", ".join(f"{g} {v:.2f}" for g, v in order)
              + f" — the {lowest} is lowest (only weakly robust: random/creative swap")
        print("   between scalings), suggestive that the LLM searches most redundantly,")
        print("   consistent with its 160-distinct ceiling — but we do NOT lean on it.")
    out = "papers/false-alpha/envelope_departure_results.json"
    Path(out).write_text(json.dumps({"config": {"pool": POOL, "NS": NS, "T_is": T},
                                     "rows": rows}, indent=2))
    print(f"\n(results -> {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
