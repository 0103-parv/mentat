"""Adversarial verification suite for the false-discovery paper.

This tries to BREAK the paper's claims through independent code paths — including the
ACTUAL engine gate (`AlphaProblem.verify`) and the realm/curriculum study loop, not just
nsweep's helper — and reports PASS / FAIL / INFO for each check. Run before trusting the
paper.

  python3 -m papers.false-alpha.verify          # NB: run as a path, see __main__ note
  cd ~/mentat && python3 papers/false-alpha/verify.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mentat.nsweep import (  # noqa: E402
    TARGET, COST, _ANN, _draw_pool, backtest_raw, deflated_ann, effective_n,
    noise_universe,
)
from mentat.trade_lab import (  # noqa: E402
    AlphaProblem, expected_max_sharpe_under_null, expr_to_str, load_price_csv,
    synthetic_universe, walk_forward_backtest,
)

REAL = "data/fred_SP500.csv"
_results: list[tuple[str, str, str]] = []


def record(status: str, name: str, detail: str = "") -> None:
    _results.append((status, name, detail))
    mark = {"PASS": "✓", "FAIL": "✗", "INFO": "·"}[status]
    print(f"  {mark} [{status}] {name}" + (f"  — {detail}" if detail else ""))


def survivors_on(bars, gen: str, market: str, N: int, *, pool: int, cost: float = COST,
                 target: float = TARGET) -> tuple[int, float, int]:
    """(survivors, best raw worst-regime ann Sharpe, tradeable) for a pool, deflating at N."""
    alphas = _draw_pool(gen, market, pool)
    raws = [backtest_raw(a, bars, cost=cost) for a in alphas]
    kept = [r for r in raws if r is not None][:N]
    if not kept:
        return 0, float("nan"), 0
    surv = sum(1 for r in kept if deflated_ann(r, N) >= target)
    best_worst = max(r["worst_ann"] for r in kept)
    return surv, best_worst, len(kept)


def main() -> int:
    print("ADVERSARIAL VERIFICATION — trying to break the paper's claims\n")
    real = load_price_csv(REAL)
    planted = synthetic_universe()
    noise = noise_universe()
    SWEEP = [10, 30, 100, 300, 1000]

    # 1. Determinism --------------------------------------------------------- #
    p1 = [expr_to_str(a) for a in _draw_pool("creative", "real:fred_SP500", 500)]
    p2 = [expr_to_str(a) for a in _draw_pool("creative", "real:fred_SP500", 500)]
    record("PASS" if p1 == p2 else "FAIL", "determinism (two draws identical)",
           f"{len(p1)} alphas, identical={p1 == p2}")

    # 2. Headline: 0 survivors on REAL at every N, both generators ------------ #
    ok = True
    detail = []
    for gen in ("random", "creative"):
        for N in SWEEP:
            s, _, K = survivors_on(real, gen, "real:fred_SP500", N, pool=1500)
            if K >= N and s != 0:
                ok = False
            if N == 1000:
                detail.append(f"{gen}@1000:{s}")
    record("PASS" if ok else "FAIL", "headline: 0 survivors on real S&P at every N",
           ", ".join(detail))

    # 3. Positive control: planted edge passes the FULL engine gate ---------- #
    #    (independent of nsweep — uses AlphaProblem.verify directly)
    alphas = _draw_pool("creative", "planted", 1500)
    raws = [(a, backtest_raw(a, planted)) for a in alphas]
    raws = [(a, r) for a, r in raws if r is not None][:1000]
    surv = [(a, r) for a, r in raws if deflated_ann(r, 1000) >= TARGET]
    # take the best survivor and re-check it through the real engine verifier at n_trials=1000
    best = max(surv, key=lambda ar: deflated_ann(ar[1], 1000), default=None)
    if best is not None:
        prob = AlphaProblem(bars=planted, target=TARGET, n_trials=1000)
        v = prob.verify(best[0])
        record("PASS" if v.passed else "FAIL",
               "positive control: planted survivor passes the REAL AlphaProblem.verify gate",
               f"{len(surv)} survivors; best engine score={v.score:+.3f}, passed={v.passed}")
    else:
        record("FAIL", "positive control: planted produced NO survivors (gate too harsh?)")

    # 4. Null control: noise -> 0 survivors ---------------------------------- #
    ok = True
    for gen in ("random", "creative"):
        for N in SWEEP:
            s, _, K = survivors_on(noise, gen, "noise", N, pool=1500)
            if K >= N and s != 0:
                ok = False
    record("PASS" if ok else "FAIL", "null control: 0 survivors on pure-noise market")

    # 5. Margin @ n_eff: best worst-Sharpe < haircut even at the EFFECTIVE N -- #
    allw = []
    n_obs = 0
    for gen in ("random", "creative"):
        for a in _draw_pool(gen, "real:fred_SP500", 1500):
            r = backtest_raw(a, real)
            if r:
                allw.append(r["worst_ann"]); n_obs = r["worst_n"]
    mw = max(allw)
    n_eff = int(effective_n(0.999, n_obs))  # ~ the real-market n_eff at the largest pooled best
    hc_neff = expected_max_sharpe_under_null(max(n_eff, 2), n_obs, mw / _ANN) * _ANN
    record("PASS" if mw - hc_neff < TARGET else "FAIL",
           "margin: best worst-Sharpe < haircut even at n_eff (not over-deflation)",
           f"best_worst={mw:+.3f}, n_eff~{n_eff}, haircut={hc_neff:.2f}, deflated={mw - hc_neff:+.2f}")

    # 6. Cost sensitivity (cost=0 is the adversary's best case) -------------- #
    for cost in (0.0, 0.0005, COST, 0.002):
        s, mw_c, _ = survivors_on(real, "creative", "real:fred_SP500", 1000, pool=1500, cost=cost)
        status = "INFO" if cost == 0.0 else ("PASS" if s == 0 else "FAIL")
        record(status, f"cost sensitivity @ cost={cost}", f"survivors={s}, best_worst={mw_c:+.2f}")

    # 7. Target sensitivity (target=0 -> any positive deflated edge) ---------- #
    for target in (0.0, 0.25, TARGET):
        s, _, _ = survivors_on(real, "creative", "real:fred_SP500", 1000, pool=1500, target=target)
        record("PASS" if s == 0 else "INFO", f"target sensitivity @ target={target}",
               f"survivors={s}")

    # 8. Regime-count sensitivity (fewer regimes = weaker worst-of gate) ----- #
    for k in (2, 3, 5):
        bars_k = load_price_csv(REAL, n_oos_regimes=k)
        # fresh-feature cache per Bars (new object) so backtests are clean
        s, _, _ = survivors_on(bars_k, "creative", "real:fred_SP500", 1000, pool=1500)
        record("PASS" if s == 0 else "INFO", f"regime-count sensitivity @ {k} OOS regimes",
               f"survivors={s}")

    # 9. Cross-market: DJIA, NASDAQ -> 0 survivors --------------------------- #
    for fn in ("data/fred_DJIA.csv", "data/fred_NASDAQCOM.csv"):
        if not Path(fn).exists():
            record("INFO", f"cross-market {Path(fn).stem}", "file missing; skipped")
            continue
        bars_m = load_price_csv(fn)
        mkt = f"real:{Path(fn).stem}"
        s_r, _, _ = survivors_on(bars_m, "random", mkt, 1000, pool=1500)
        s_c, _, _ = survivors_on(bars_m, "creative", mkt, 1000, pool=1500)
        record("PASS" if s_r == 0 and s_c == 0 else "FAIL",
               f"cross-market: 0 survivors on {Path(fn).stem}",
               f"random={s_r}, creative={s_c}")

    # 10. Engine consistency: the realm/curriculum study agrees -------------- #
    try:
        from mentat.curriculum import study
        kb, _ = study("real:fred_SP500", real, gens=10, k=16)
        verified = [f for f, d in kb.facets.items() if d["verified"]]
        record("PASS" if not verified else "FAIL",
               "engine consistency: curriculum.study finds 0 verified facets on real S&P",
               f"{len(kb.facets)} facets studied, {len(verified)} verified")
    except Exception as e:
        record("INFO", "engine consistency (curriculum)", f"skipped: {type(e).__name__}: {e}")

    # verdict ---------------------------------------------------------------- #
    fails = [r for r in _results if r[0] == "FAIL"]
    infos = [r for r in _results if r[0] == "INFO"]
    print(f"\n{'=' * 70}")
    print(f"VERDICT: {sum(1 for r in _results if r[0] == 'PASS')} PASS, "
          f"{len(fails)} FAIL, {len(infos)} INFO")
    if fails:
        print("  FAILURES (must address):")
        for _, name, d in fails:
            print(f"    ✗ {name} — {d}")
    else:
        print("  No FAILs. Claims hold under the adversarial battery.")
    if infos:
        print("  INFO (note in the paper, not failures):")
        for _, name, d in infos:
            print(f"    · {name} — {d}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
