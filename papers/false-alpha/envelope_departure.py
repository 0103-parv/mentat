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
from theory import mc_expected_max  # noqa: E402

POOL = 3000
NS = [10, 30, 100, 300, 1000, 3000]
BOOT = 30


def _t_is(bars) -> int:
    seg = next((r for r in bars.regimes if r[0].startswith("is")), bars.regimes[0])
    return seg[2] - seg[1]


def invert_envelope(target: float, k: int = 1, cache=None) -> float:
    """Smallest M with E[max_M of (min_k N(0,1))] >= target (the empirical effective-N)."""
    if target <= mc_expected_max(2, k, 1500):
        return 2.0
    lo, hi = 2, 10 ** 7
    cache = cache if cache is not None else {}
    def env(M):
        M = max(2, int(M))
        if M not in cache:
            cache[M] = mc_expected_max(M, k, 1500, seed=11)
        return cache[M]
    if env(hi) < target:
        return float(hi)
    for _ in range(40):
        mid = int(math.isqrt(lo * hi)) if hi - lo > 8 else (lo + hi) // 2
        if env(mid) < target:
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
    rows, env_cache = [], {}
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
            iid = mc_expected_max(N, 1, 2000, seed=5)
            m_emp = invert_envelope(realized, 1, env_cache)
            rows.append({"generator": gen, "N": N, "realized_z": round(realized, 3),
                         "iid_Emax": round(iid, 3), "ratio": round(realized / iid, 3),
                         "M_emp": round(m_emp, 1), "M_emp_over_N": round(m_emp / N, 3)})
            print(f"  {gen:9} {N:>5} {realized:>11.3f} {iid:>11.3f} {realized/iid:>6.2f} "
                  f"{m_emp:>8.0f} {m_emp/N:>8.2f}")
        print()

    print("=> Read: ratio<1 and M_emp<N mean the generator snoops LESS than N i.i.d. trials")
    print("   (correlated/redundant search). M_emp is the CORRECT effective-N (calibrated")
    print("   from the realized max, like the bootstrap) — contrast the participation-ratio")
    print("   M_eff~5 that failed. The gap M_emp vs N quantifies each generator's redundancy.")
    out = "papers/false-alpha/envelope_departure_results.json"
    Path(out).write_text(json.dumps({"config": {"pool": POOL, "NS": NS, "T_is": T},
                                     "rows": rows}, indent=2))
    print(f"\n(results -> {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
