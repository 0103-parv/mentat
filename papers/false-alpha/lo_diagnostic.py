"""Why did the envelope-departure effective-N fail — and does Lo (2002) fix it?

Diagnosis. Under the null, a correctly standardized in-sample Sharpe z = SR/SE should have
cross-sectional variance ~1. The envelope-departure used the i.i.d. SE
SE_iid = sqrt((1+0.5 SR^2)/T); if strategy returns are autocorrelated (positions persist),
the true SE is larger (Lo 2002), so z is over-stated and its variance exceeds 1, inflating
the realized max and the implied effective-N. We measure:

  - eta^2 : the Newey-West HAC variance inflation per strategy (theory.hac_variance_ratio),
  - Var(z_iid)  : cross-sectional variance of the i.i.d.-standardized Sharpe,
  - Var(z_lo)   : same with Lo's serial-correlation-adjusted SE,
  - Var(z_emp)  : same with a purely empirical (cross-sectional) SD.

If Var(z_lo) ~ 1 while Var(z_iid) >> 1, autocorrelation was the culprit and Lo rescues the
effective-N analysis. If Var(z_lo) is still far from 1, the failure is NOT (only)
autocorrelation, and the bootstrap remains the necessary tool — which we then report.

  python3.14 papers/false-alpha/lo_diagnostic.py
"""
from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mentat.nsweep import _ANN, _draw_pool, backtest_raw, noise_universe  # noqa: E402
from mentat.trade_lab import (  # noqa: E402
    _positions, compute_features, eval_alpha, valid_alpha,
)
from theory import hac_variance_ratio  # noqa: E402

POOL = 1500


def is_returns(expr, bars):
    feats = compute_features(bars)
    pos = _positions(eval_alpha(expr, feats))
    seg = next((r for r in bars.regimes if r[0].startswith("is")), bars.regimes[0])
    s, e = seg[1], seg[2]
    return [pos[t - 1] * bars.ret[t] - 0.0010 * abs(pos[t - 1] - pos[t - 2])
            for t in range(max(s, 2), e)]


def main() -> int:
    bars = noise_universe()
    print("LO (2002) DIAGNOSTIC — is the envelope-departure failure due to autocorrelation?\n")
    out = {}
    for gen in ("random", "creative"):
        alphas = _draw_pool(gen, "noise", POOL, log=lambda *_: None)
        etas, z_iid, z_lo, srs = [], [], [], []
        for a in alphas:
            if not valid_alpha(a):
                continue
            r = backtest_raw(a, bars)
            if r is None:
                continue
            rr = is_returns(a, bars)
            if len(rr) < 20:
                continue
            T = len(rr)
            m = sum(rr) / T
            var = sum((x - m) ** 2 for x in rr) / (T - 1)
            if var < 1e-18:
                continue
            sr = m / math.sqrt(var)                       # per-bar IS Sharpe
            eta2 = hac_variance_ratio(rr)
            se_iid = math.sqrt((1.0 + 0.5 * sr * sr) / T)
            se_lo = math.sqrt(max(eta2 * (1.0 + 0.5 * sr * sr) / T, 1e-18))
            etas.append(eta2)
            srs.append(sr)
            z_iid.append(sr / se_iid)
            z_lo.append(sr / se_lo)
        # empirical standardization: divide centered SR by cross-sectional SD of SR
        msr = statistics.mean(srs)
        sdsr = statistics.pstdev(srs)
        z_emp = [(s - msr) / sdsr for s in srs] if sdsr > 0 else srs
        # variance decomposition: total cross-sectional Var(SR) = within (estimation) +
        # between (STRUCTURAL). within_i = SE_iid_i^2 = (1+0.5 SR^2)/T.
        T0 = len(is_returns(alphas[0], bars))
        total = statistics.pvariance(srs)
        within = statistics.mean((1.0 + 0.5 * s * s) / max(T0, 2) for s in srs)
        struct_frac = max(0.0, 1.0 - within / total) if total > 0 else 0.0
        rec = {
            "n": len(srs),
            "eta2_median": round(statistics.median(etas), 3),
            "eta2_p90": round(sorted(etas)[int(0.9 * len(etas))], 3),
            "var_z_iid": round(statistics.pvariance(z_iid), 3),
            "var_z_lo": round(statistics.pvariance(z_lo), 3),
            "var_z_emp": round(statistics.pvariance(z_emp), 3),
            "structural_fraction": round(struct_frac, 3),
        }
        out[gen] = rec
        print(f"  [{gen}] n={rec['n']}  eta^2 median={rec['eta2_median']} "
              f"(p90={rec['eta2_p90']})")
        print(f"        Var(z_iid)={rec['var_z_iid']}  Var(z_lo)={rec['var_z_lo']}  "
              f"Var(z_emp)={rec['var_z_emp']}   (target ~1.0)")
        print(f"        variance decomposition: {rec['structural_fraction']*100:.0f}% of "
              f"cross-sectional Var(Sharpe) is STRUCTURAL (between-strategy), "
              f"{(1-rec['structural_fraction'])*100:.0f}% estimation noise")

    print("\n=> Verdict:")
    worst_lo = max(out[g]["var_z_lo"] for g in out)
    worst_iid = max(out[g]["var_z_iid"] for g in out)
    if worst_lo < 1.6:
        print("   Lo's HAC correction pulls Var(z) to ~1 — autocorrelation WAS the culprit;")
        print("   the serial-correlation-adjusted SE rescues a usable per-generator effective-N.")
    elif worst_lo < worst_iid * 0.7:
        print(f"   Lo helps (Var(z) {worst_iid:.1f}->{worst_lo:.1f}) but does not reach ~1:")
        print("   autocorrelation is PART of the story; residual non-Gaussianity/clustering")
        print("   remains, so the bootstrap stays the arbiter. (Honest partial result.)")
    else:
        print(f"   Lo does NOT fix it (Var(z) {worst_iid:.1f}->{worst_lo:.1f}, still >>1): the")
        print("   failure is non-Gaussianity/strategy clustering, not serial correlation.")
        print("   Confirms the §4.9 conclusion — no analytic effective-N; bootstrap required.")
    Path("papers/false-alpha/lo_diagnostic_results.json").write_text(json.dumps(out, indent=2))
    print("\n(results -> papers/false-alpha/lo_diagnostic_results.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
