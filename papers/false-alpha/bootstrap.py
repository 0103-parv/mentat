"""Distribution-free multiple-testing test for the false-alpha gate (Task 1).

The deflated Sharpe ratio (Bailey & Lopez de Prado) is a *parametric* haircut derived
for a single in-sample Sharpe over N independent trials — not for the WORST-of-regimes
statistic our gate actually uses. This module closes that gap with a distribution-free
alternative: a stationary block bootstrap (Politis & Romano 1994) of the per-bar OOS
strategy returns that **preserves the worst-of-regimes operator inside each resample**,
feeding White's Reality Check (2000) / Romano-Wolf (2005) single-step studentized test
for per-candidate snooping-adjusted p-values, and a Hansen (2005) SPA p-value.

Key properties:
  - Block resampling is done WITHIN each OOS regime and the block plan is SHARED across
    all strategies in a replicate (preserving cross-strategy dependence — essential for
    the max statistic).
  - The worst-of-regimes min is recomputed inside every resample, so the bootstrapped
    null is the null of the *actual gate statistic*, not a proxy.
  - Block sums use per-strategy prefix sums, so a resample is O(#blocks), not O(#bars).
  - Mean block length is reported and the survivor count is shown stable across choices.
  - Deterministic: every RNG is CRC-seeded from (market, gen, b).

Output: bootstrap_results.json. DSR survivor counts are reported alongside so the two
corrections can be compared head to head.

  cd ~/mentat && python3 papers/false-alpha/bootstrap.py
  cd ~/mentat && python3 papers/false-alpha/bootstrap.py --quick   # fewer replicates
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from mentat.nsweep import (  # noqa: E402
    COST, TARGET, _ANN, _draw_pool, _seed, backtest_raw, deflated_ann,
    noise_universe, planted_universe,
)
from mentat.trade_lab import (  # noqa: E402
    _positions, compute_features, eval_alpha, load_price_csv, synthetic_universe,
)

ALPHA = 0.05                       # significance level for the survivor count
BLOCKS = [10, 25, 50]              # mean block lengths (stability check)
B_DEFAULT = 300                    # bootstrap replicates
SWEEP = [30, 100, 300, 1000]
POOL = 1000                        # offline pool; llm capped by its cache


# --------------------------------------------------------------------------- #
# per-regime OOS returns + prefix sums                                        #
# --------------------------------------------------------------------------- #
def regime_returns(expr, bars, cost: float = COST) -> list[list[float]] | None:
    """Per-bar OOS strategy returns (next-bar, after cost) split BY regime. Returns
    None for a degenerate (never-trades) alpha — the same filter the gate applies."""
    feats = compute_features(bars)
    pos = _positions(eval_alpha(expr, feats))
    segs, turn_tot, n_tot = [], 0.0, 0
    for label, s, e in bars.regimes:
        if label.startswith("is"):
            continue
        seg = []
        for t in range(max(s, 2), e):
            seg.append(pos[t - 1] * bars.ret[t] - cost * abs(pos[t - 1] - pos[t - 2]))
            turn_tot += abs(pos[t - 1] - pos[t - 2])
            n_tot += 1
        if len(seg) >= 2:
            segs.append(seg)
    if not segs or n_tot == 0 or turn_tot / max(n_tot, 1) < 1e-6:
        return None
    return segs


def _prefix(seg: list[float]):
    """Prefix sums of x and x^2 (length L+1) for O(1) block sums."""
    L = len(seg)
    P = [0.0] * (L + 1)
    Q = [0.0] * (L + 1)
    for i, x in enumerate(seg):
        P[i + 1] = P[i] + x
        Q[i + 1] = Q[i] + x * x
    return P, Q, L


def _block_plan(L: int, b: int, rng: random.Random):
    """Stationary-bootstrap block plan covering exactly L positions: random starts,
    geometric(1/b) lengths, circular. Shared across strategies in a replicate."""
    p = 1.0 / b
    plan, total = [], 0
    while total < L:
        start = rng.randrange(L)
        length = 1
        while length < L and rng.random() > p:
            length += 1
        take = min(length, L - total)
        plan.append((start, take))
        total += take
    return plan


def _resample_sharpe(P, Q, L, plan) -> float:
    """Per-bar Sharpe of one strategy under a shared block plan (circular)."""
    s = ss = 0.0
    for start, ln in plan:
        end = start + ln
        if end <= L:
            s += P[end] - P[start]
            ss += Q[end] - Q[start]
        else:                                   # circular wrap
            s += (P[L] - P[start]) + P[end - L]
            ss += (Q[L] - Q[start]) + Q[end - L]
    n = L
    m = s / n
    var = (ss - s * s / n) / (n - 1)
    if var <= 1e-18:
        return 0.0
    return m / math.sqrt(var)


def _resample_mean(P, L, plan) -> float:
    s = 0.0
    for start, ln in plan:
        end = start + ln
        s += (P[end] - P[start]) if end <= L else ((P[L] - P[start]) + P[end - L])
    return s / L


# --------------------------------------------------------------------------- #
# the bootstrap test for one (market, generator)                              #
# --------------------------------------------------------------------------- #
def bootstrap_market(market: str, bars, gen: str, *, pool: int, B: int,
                     sweep=None, log=print) -> list[dict]:
    """Both the Reality Check / Romano-Wolf survivor count and the Hansen SPA p-value test
    the SAME statistic the gate uses — the worst-of-regimes per-bar Sharpe — so they are
    directly comparable to the DSR survivor count."""
    sweep = sweep or SWEEP
    alphas = _draw_pool(gen, market, pool, log=lambda *_: None)
    if not alphas:
        return []
    pref, obs_sh, n_min, raws = [], [], [], []
    for a in alphas:
        segs = regime_returns(a, bars)
        r = backtest_raw(a, bars)
        if segs is None or r is None:
            continue
        sh = [_prefix(seg) for seg in segs]                 # (P,Q,L) per regime
        wsh = min((P[L] / L) / math.sqrt(max((Q[L] - P[L] ** 2 / L) / (L - 1), 1e-18))
                  for P, Q, L in sh)
        pref.append(sh)
        obs_sh.append(wsh)
        n_min.append(min(L for _, _, L in sh))
        raws.append(r)
    K = len(pref)
    if K == 0:
        return []
    log(f"  [{market}/{gen}] tradeable={K}")

    rows = []
    for b in BLOCKS:
        rng = random.Random(_seed("boot", market, gen, b))
        star = [[0.0] * K for _ in range(B)]                # f*_{b,k}: resampled worst Sharpe
        n_reg = len(pref[0])
        Ls = [pref[0][g][2] for g in range(n_reg)]
        for rep in range(B):
            plans = [_block_plan(Ls[g], b, rng) for g in range(n_reg)]
            for k in range(K):
                star[rep][k] = min(_resample_sharpe(P, Q, L, plans[g])
                                   for g, (P, Q, L) in enumerate(pref[k]))
        se = [_std([star[r][k] for r in range(B)]) for k in range(K)]
        # RC/RW centered studentized bootstrap stats: Z*_{b,k} = (f* - f)/se_k
        Z = [[((star[r][k] - obs_sh[k]) / se[k] if se[k] > 1e-12 else 0.0)
              for k in range(K)] for r in range(B)]
        for N in sweep:
            if N > K and N != sweep[0]:
                continue
            n = min(N, K)
            # studentized single-step Reality Check / Romano-Wolf (FWER control):
            Mb = [max(Z[r][k] for k in range(n)) for r in range(B)]
            rc_surv, min_p = 0, 1.0
            for k in range(n):
                Tk = obs_sh[k] / se[k] if se[k] > 1e-12 else 0.0
                p_k = sum(1 for r in range(B) if Mb[r] >= Tk) / B
                min_p = min(min_p, p_k)
                if p_k < ALPHA and obs_sh[k] > 0:
                    rc_surv += 1
            spa_p = _spa_pvalue(obs_sh, star, se, n_min, n, B)
            dsr_surv = sum(1 for k in range(n) if deflated_ann(raws[k], N) >= TARGET)
            rows.append({
                "market": market, "generator": gen, "N": N, "block_len": b,
                "tradeable": K, "B": B,
                "dsr_survivors": dsr_surv, "rc_survivors": rc_surv,
                "rc_best_p": round(min_p, 4), "spa_p": round(spa_p, 4),
            })
    return rows


def _std(xs):
    n = len(xs)
    m = sum(xs) / n
    v = sum((x - m) ** 2 for x in xs) / max(n - 1, 1)
    return math.sqrt(max(v, 0.0))


def _spa_pvalue(obs_sh, star, se, n_min, n, B) -> float:
    """Hansen (2005) SPA consistent p-value on the WORST-REGIME SHARPE (same statistic as
    the gate). Studentize by the bootstrap se; recenter only strategies that are not
    implausibly bad (the consistent threshold g_c), which makes SPA more powerful than the
    fully-recentered Reality Check while remaining valid."""
    spa_T, g_hat = 0.0, [0.0] * n
    for k in range(n):
        s = se[k] if se[k] > 1e-12 else 1e-12
        t = obs_sh[k] / s
        spa_T = max(spa_T, max(0.0, t))
        nn = max(n_min[k], 4)
        thr = -s * math.sqrt(2.0 * math.log(math.log(nn)))   # consistent recentering band
        g_hat[k] = obs_sh[k] if t >= thr / s else 0.0
    cnt = 0
    for r in range(B):
        mb = 0.0
        for k in range(n):
            s = se[k] if se[k] > 1e-12 else 1e-12
            mb = max(mb, max(0.0, (star[r][k] - g_hat[k]) / s))
        if mb >= spa_T:
            cnt += 1
    return cnt / B


# --------------------------------------------------------------------------- #
def main() -> int:
    quick = "--quick" in sys.argv
    B = 120 if quick else B_DEFAULT
    real = ("real:fred_SP500", load_price_csv("data/fred_SP500.csv"))
    markets = [
        ("planted", synthetic_universe()),          # strong edge: bootstrap should find survivors
        ("noise", noise_universe()),                # pure null: 0
        ("small_planted", planted_universe(0.06)),  # small edge: like real
        real,
    ]
    gens = ["random", "creative", "llm"]
    print(f"DISTRIBUTION-FREE BOOTSTRAP (White RC / Romano-Wolf + Hansen SPA)  B={B}")
    print(f"  alpha={ALPHA} | block lengths {BLOCKS} | stationary block bootstrap, "
          "worst-of-regimes preserved per resample\n")
    all_rows = []
    for name, bars in markets:
        compute_features(bars)
        for gen in gens:
            rows = bootstrap_market(name, bars, gen, pool=POOL, B=B)
            all_rows.extend(rows)

    # table
    print(f"  {'market':16} {'gen':9} {'N':>5} {'blk':>4} {'DSR_surv':>9} "
          f"{'RC_surv':>8} {'RC_best_p':>10} {'SPA_p':>7}")
    cur = None
    for r in all_rows:
        if (r["market"], r["generator"]) != cur:
            print()
            cur = (r["market"], r["generator"])
        print(f"  {r['market']:16} {r['generator']:9} {r['N']:>5} {r['block_len']:>4} "
              f"{r['dsr_survivors']:>9} {r['rc_survivors']:>8} {r['rc_best_p']:>10.3f} "
              f"{r['spa_p']:>7.3f}")

    out = "papers/false-alpha/bootstrap_results.json"
    Path(out).write_text(json.dumps({
        "config": {"alpha": ALPHA, "blocks": BLOCKS, "B": B, "pool": POOL, "sweep": SWEEP,
                   "test": "studentized single-step Reality Check (White 2000; "
                           "Romano-Wolf 2005) on worst-regime Sharpe; Hansen 2005 SPA on "
                           "worst-regime mean; stationary block bootstrap"},
        "rows": all_rows,
    }, indent=2))
    print(f"\n(results -> {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
