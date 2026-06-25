"""N-sweep: does scaling LLM-style strategy search discover edge or manufacture mirages?

This is the experiment behind the false-discovery paper (papers/false-alpha/PAPER.md).
It is deliberately SEPARATE from the kernel's adaptive solve() loop: we want N
*independent-ish* draws from a generator, not an evolved population, so that the
best-of-N data-snooping curve is clean and attributable.

For each (market, generator) we draw a pool of M alphas in a fixed order, backtest
each ONCE (walk-forward, after-cost, worst-of-regimes OOS Sharpe — the trade_lab
verifier minus its haircut), then for every N along a geometric sweep we read off:

  - naive_pos      : # alphas with raw worst-OOS Sharpe > 0          (a naive "winner")
  - naive_bar      : # alphas with raw worst-OOS Sharpe > 1.0 ann.   (a "good" winner)
  - best_naive     : max raw worst-OOS Sharpe over the first N       (the data-snoop curve)
  - survivors      : # alphas whose DEFLATED worst-OOS Sharpe (haircut at n_trials=N)
                     clears the target AND survives a 3x-cost stress  (the honest gate)
  - novelty        : mean pairwise token-Jaccard distance among the naive winners
  - n_eff          : effective # independent trials implied by best_naive vs the
                     i.i.d. expected-max envelope (correlated draws => n_eff < N)

Three markets form the experimental matrix:
  - planted : synthetic_universe()  — a real, regime-consistent edge is embedded
              (POSITIVE control: the gate SHOULD keep survivors > 0).
  - noise   : a pure random walk, no edge
              (NULL control: naive winners rise with N, the gate SHOULD stay at 0).
  - real    : --data data/fred_SP500.csv — the headline
              (behaves like the null on a near-efficient market).

Run:
  python3 -m mentat.nsweep                                  # planted + noise
  python3 -m mentat.nsweep --data data/fred_SP500.csv       # add the real market
  python3 -m mentat.nsweep --pool 3000 --out papers/false-alpha/nsweep_results.json
"""
from __future__ import annotations

import json
import math
import random
import sys
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from .imagine import blend, invert, reshape, specialize, transfer
from .trade_lab import (
    BASELINE_ALPHAS,
    CONSTANTS,
    FEATURES,
    PERIODS_PER_YEAR,
    AlphaProblem,
    Bars,
    _LCG,
    _positions,
    compute_features,
    eval_alpha,
    expected_max_sharpe_under_null,
    expr_to_str,
    load_price_csv,
    segment_metrics,
    synthetic_universe,
    valid_alpha,
)

TARGET = 0.5            # annualized deflated worst-regime OOS Sharpe bar (same as the engine)
COST = 0.0010          # per-unit-turnover transaction cost
_ANN = math.sqrt(PERIODS_PER_YEAR)


def _seed(*parts) -> int:
    """A STABLE seed from string parts (zlib.crc32 — unlike hash(), not salted per
    process, so the whole run is bit-for-bit reproducible)."""
    return zlib.crc32("|".join(map(str, parts)).encode()) & 0x7FFFFFFF
_UNARY = ["neg", "abs", "sign", "tanh", "zscore"]
_BINARY = ["add", "sub", "mul", "safe_div", "min", "max"]


# --------------------------------------------------------------------------- #
# markets                                                                     #
# --------------------------------------------------------------------------- #
def planted_universe(reversion: float, seed: int = 11) -> Bars:
    """A regime-structured market with a tunable lag-1 mean-reversion edge of strength
    `reversion` (same sign in every regime). reversion=0 is the pure-noise null;
    reversion=0.40 is the strong control (huge edge); small values (~0.05) give a
    REALISTICALLY small edge for the gate's power analysis."""
    rng = _LCG(seed)
    plan = [
        ("is_train", 750, 0.0004, 0.010),
        ("oos_bull", 500, 0.0006, 0.008),
        ("oos_bear", 500, -0.0005, 0.016),
        ("oos_chop", 500, 0.0000, 0.012),
    ]
    close, high, low, volume, ret = [], [], [], [], []
    regimes: list[tuple[str, int, int]] = []
    price, idx, prev_r = 100.0, 0, 0.0
    for label, n_bars, drift, vol in plan:
        start = idx
        for _ in range(n_bars):
            r = drift - reversion * prev_r + rng.gauss() * vol
            prev_r = r
            new_price = max(1e-3, price * (1.0 + r))
            realized = new_price / price - 1.0
            intrabar = abs(rng.gauss()) * vol * new_price
            close.append(new_price)
            high.append(max(price, new_price) + 0.5 * intrabar)
            low.append(max(1e-3, min(price, new_price) - 0.5 * intrabar))
            volume.append(1_000_000.0 * (1.0 + 0.3 * abs(rng.gauss())))
            ret.append(realized)
            price = new_price
            idx += 1
        regimes.append((label, start, idx))
    return Bars(close, high, low, volume, ret, regimes)


def noise_universe(seed: int = 11) -> Bars:
    """The pure random walk null (no edge): every apparent OOS winner is data-snooping
    luck, so the gate must hold survivors at zero."""
    return planted_universe(0.0, seed)


# --------------------------------------------------------------------------- #
# generators (independent draws — NOT an evolved loop)                        #
# --------------------------------------------------------------------------- #
def random_alpha(rng: random.Random, depth: int = 0):
    """A uniform-ish random valid alpha over the FULL DSL — the i.i.d. baseline
    search a brute-force quant would run."""
    if depth >= 3 or (depth > 0 and rng.random() < 0.45):
        return (rng.choice(FEATURES) if rng.random() < 0.8 else rng.choice(list(CONSTANTS)))
    if rng.random() < 0.4:
        return [rng.choice(_UNARY), random_alpha(rng, depth + 1)]
    return [rng.choice(_BINARY), random_alpha(rng, depth + 1), random_alpha(rng, depth + 1)]


_CREATIVE_SUBSTRATE = [f for f in FEATURES] + list(BASELINE_ALPHAS)
_CREATIVE_OPS = [blend, invert, reshape, specialize, transfer]


def creative_alpha(rng: random.Random, risk: float = 0.7):
    """A creative-synthesis draw: apply Boden-style operators (blend/invert/reshape/
    specialize/transfer) over a shared substrate of seed ideas + verified baselines.
    Draws are CORRELATED through the shared substrate — exactly the structure an LLM
    'imaginer' produces — which is the object of study (n_eff < N)."""
    pool = _CREATIVE_SUBSTRATE
    op = rng.choice(_CREATIVE_OPS)
    cand = blend(rng, rng.choice(pool), rng.choice(pool)) if op is blend else op(rng, rng.choice(pool))
    if risk >= 0.66 and rng.random() < risk:            # bold: compose two operators
        op2 = rng.choice(_CREATIVE_OPS)
        cand = blend(rng, cand, rng.choice(pool)) if op2 is blend else op2(rng, cand)
    return cand


# --------------------------------------------------------------------------- #
# one backtest (worst-of-regimes OOS, after cost) — haircut applied later     #
# --------------------------------------------------------------------------- #
def backtest_raw(expr, bars: Bars, cost: float = COST) -> dict | None:
    """Three after-cost Sharpe views of one alpha, backtested ONCE. Returns None for
    an off-grammar or degenerate (never-trades) alpha.

      naive_oos : a SINGLE pooled out-of-sample holdout Sharpe (no regime split, no
                  deflation) — what a naive practitioner validates on and snoops over.
      worst_oos : the WORST of the OOS regimes — the robustness half of the gate.
      is        : in-sample Sharpe — the overfit reference.

    Deflation is applied afterward, per N, from `worst_per_bar` + `worst_n`, so each
    alpha is backtested only once."""
    if not valid_alpha(expr):
        return None
    feats = compute_features(bars)
    pos = _positions(eval_alpha(expr, feats))
    oos = [r for r in bars.regimes if not r[0].startswith("is")]
    is_seg = next((r for r in bars.regimes if r[0].startswith("is")), bars.regimes[0])
    if not oos:
        return None
    worst, worst_label, turn = None, "none", []
    for label, s, e in oos:
        m = segment_metrics(pos, bars.ret, s, e, cost)
        turn.append(m["turnover"])
        if worst is None or m["sharpe"] < worst["sharpe"]:
            worst, worst_label = m, label
    avg_turn = sum(turn) / len(turn)
    if avg_turn < 1e-6:                                  # never trades -> no information
        return None
    # the naive practitioner's single holdout: all OOS bars as ONE segment
    pooled = segment_metrics(pos, bars.ret, oos[0][1], oos[-1][2], cost)
    is_m = segment_metrics(pos, bars.ret, is_seg[1], is_seg[2], cost)
    return {
        "naive_per_bar": pooled["sharpe"],
        "naive_n": int(pooled["n"]),
        "naive_ann": pooled["sharpe"] * _ANN,
        "worst_per_bar": worst["sharpe"],
        "worst_n": int(worst["n"]),
        "worst_ann": worst["sharpe"] * _ANN,
        "is_ann": is_m["sharpe"] * _ANN,
        "turnover": avg_turn,
        "worst_regime": worst_label,
    }


def deflated_ann(raw: dict, n_trials: int) -> float:
    """Annualized deflated worst-OOS Sharpe with the multiple-testing haircut for N
    trials (Bailey & Lopez de Prado). This is the score the honest gate reads."""
    hc = expected_max_sharpe_under_null(n_trials, raw["worst_n"], raw["worst_per_bar"])
    return (raw["worst_per_bar"] - hc) * _ANN


# --------------------------------------------------------------------------- #
# novelty + effective-N                                                       #
# --------------------------------------------------------------------------- #
def _tokens(expr) -> set[str]:
    s = expr_to_str(expr)
    return {t for t in __import__("re").split(r"[^a-zA-Z0-9_]+", s) if t}


def mean_pairwise_novelty(exprs: list, rng: random.Random, cap: int = 400) -> float:
    """Mean pairwise token-Jaccard DISTANCE among a set of alphas (1 = all disjoint).
    Sampled to `cap` pairs so it stays cheap on large winner sets."""
    toks = [_tokens(e) for e in exprs]
    if len(toks) < 2:
        return 0.0
    pairs, acc = 0, 0.0
    n = len(toks)
    want = min(cap, n * (n - 1) // 2)
    while pairs < want:
        i, j = rng.randrange(n), rng.randrange(n)
        if i == j:
            continue
        a, b = toks[i], toks[j]
        u = len(a | b)
        acc += 1.0 - (len(a & b) / u if u else 1.0)
        pairs += 1
    return acc / max(pairs, 1)


def effective_n(best_ann: float, n_obs: int) -> float:
    """DEPRECATED (kept for the verify.py margin check only). Inverts the i.i.d.
    expected-max envelope to back out an effective trial count. This is numerically
    UNSTABLE — the envelope is logarithmic in N, so n_eff is exponentially sensitive to
    best_ann (it can swing orders of magnitude from a 1-point Sharpe change). Use
    `effective_trials` (correlation-based) for any reported number."""
    if best_ann <= 0:
        return 0.0
    target = best_ann / _ANN
    lo, hi = 2, 10 ** 7
    if expected_max_sharpe_under_null(hi, n_obs, 0.0) < target:
        return float(hi)
    for _ in range(60):
        mid = math.isqrt(lo * hi) if hi - lo > 4 else (lo + hi) // 2
        if expected_max_sharpe_under_null(mid, n_obs, 0.0) < target:
            lo = mid + 1
        else:
            hi = mid
        if lo >= hi:
            break
    return float(lo)


def oos_strat_returns(expr, bars: Bars, cost: float = COST) -> list[float]:
    """Per-bar OOS strategy return series for one alpha (next-bar, after cost), used to
    measure how CORRELATED the search is."""
    feats = compute_features(bars)
    pos = _positions(eval_alpha(expr, feats))
    oos = [r for r in bars.regimes if not r[0].startswith("is")]
    if not oos:
        return []
    s, e = oos[0][1], oos[-1][2]
    return [pos[t - 1] * bars.ret[t] - cost * abs(pos[t - 1] - pos[t - 2])
            for t in range(max(s, 2), e)]


def mean_pairwise_corr(series: list[list[float]], rng: random.Random, cap: int = 400) -> float:
    """Mean pairwise Pearson correlation of strategy return series (sampled pairs).
    Degenerate/zero-variance series are dropped."""
    vecs = []
    for s in series:
        if len(s) < 10:
            continue
        m = sum(s) / len(s)
        d = [x - m for x in s]
        nrm = math.sqrt(sum(x * x for x in d))
        if nrm > 1e-12:
            vecs.append(([x / nrm for x in d], len(d)))
    n = len(vecs)
    if n < 2:
        return 0.0
    acc, cnt, want = 0.0, 0, min(cap, n * (n - 1) // 2)
    while cnt < want:
        i, j = rng.randrange(n), rng.randrange(n)
        if i == j:
            continue
        (di, li), (dj, lj) = vecs[i], vecs[j]
        L = min(li, lj)
        acc += sum(di[t] * dj[t] for t in range(L))
        cnt += 1
    return acc / max(cnt, 1)


def effective_trials(rho_bar: float, N: int) -> float:
    """Effective number of INDEPENDENT trials under equicorrelation ρ̄ (the standard
    effective-sample-size form; cf. López de Prado's effective-number-of-trials): a
    correlated search of N alphas with mean pairwise correlation ρ̄ carries the
    multiple-testing risk of N_eff = N / (1 + (N-1)·ρ̄) independent trials. Stable,
    monotone, and bounded by 1/ρ̄ — unlike the envelope-inversion above."""
    rho = max(rho_bar, 0.0)
    denom = 1.0 + (N - 1) * rho
    return N / denom if denom > 0 else float(N)


# --------------------------------------------------------------------------- #
# the sweep                                                                    #
# --------------------------------------------------------------------------- #
GENERATORS = {
    "random": lambda rng: random_alpha(rng),
    "creative": lambda rng: creative_alpha(rng, risk=0.7),
}
SWEEP = [10, 30, 100, 300, 1000, 3000]
_LLM_POOL_CAP = 300    # the live-LLM arm draws at most this many (API cost); offline arms use --pool


def _draw_pool_llm(market: str, m: int, *, batch: int = 16, log=print) -> list:
    """Pre-registered live-LLM arm: draw a pool from the LLM imaginer (Claude via the
    Anthropic API). Each batch imagines from the problem BRIEF with a FRESH empty
    memory (no elite feedback) so draws approximate the LLM's cold proposal
    distribution — the 'LLM as generator' we want to measure, not an adaptive loop.

    The drawn pool is CACHED to disk (papers/false-alpha/llm_cache_<market>.json) so
    re-runs with updated metrics cost zero API calls. Requires `anthropic` +
    ANTHROPIC_API_KEY for a cold draw; returns [] (with a clear message) if neither a
    cache nor a core is available, so the offline arms still run."""
    if market.startswith("small_planted"):
        return []                                          # control-only market; no LLM draw
    cache = _LLM_CACHE_DIR / f"llm_cache_{market.replace(':', '_')}.json"
    if cache.exists():
        try:
            pool = json.loads(cache.read_text())
            if isinstance(pool, list) and len(pool) >= m:
                log(f"  [llm] cache hit: {market} ({len(pool)} alphas, no API call)")
                return pool[:m]                            # stored in canonical DSL form
        except Exception:
            pass
    try:
        from .reasoning import AnthropicCore, core_available
    except Exception as e:                                 # SDK not installed
        log(f"  [llm] unavailable ({type(e).__name__}); skipping the live-LLM arm")
        return []
    if not core_available():
        log("  [llm] no cache + no ANTHROPIC_API_KEY / core; skipping the live-LLM arm "
            "(offline arms still run)")
        return []
    from .core import Memory, Mind
    from .imagine import CreativeProposer, LLMImaginer
    bars = _MARKET_BARS.get(market)
    problem = AlphaProblem(bars=bars)
    imaginer = LLMImaginer(core=AnthropicCore(),
                           fallback=CreativeProposer(random.Random(0), risk=0.9))
    out: list = []
    calls = 0
    while len(out) < m and calls < (m // batch) + 4:
        calls += 1
        mind = Mind()                                     # default 'dream' bias for novelty
        for cand in imaginer.propose(problem, Memory(), mind, batch):
            if valid_alpha(cand):
                out.append(cand)
        log(f"  [llm] batch {calls}: {len(out)}/{m} alphas")
    try:                                                   # persist so re-runs are free
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(out, indent=0))
    except Exception:
        pass
    return out[:m]


_MARKET_BARS: dict = {}        # set per run so the LLM drawer can see the active market
_LLM_CACHE_DIR = Path(__file__).resolve().parents[1] / "papers" / "false-alpha"


@dataclass
class SweepRow:
    market: str
    generator: str
    N: int
    distinct: int
    naive_pos: int        # # alphas with pooled-OOS Sharpe > 0
    naive_bar: int        # # alphas with pooled-OOS Sharpe > 1.0 ann
    best_naive: float     # max pooled-OOS Sharpe over the first N (the data-snoop curve)
    robust_raw: float     # # clearing worst-regime + cost, but NO deflation (ablation)
    survivors: float      # # clearing the deflated worst-regime gate at n_trials=N
    survivors_neff: float # # clearing the gate deflated at the EFFECTIVE N (not N) — the
                          # honest, conservative-critique-proof survivor count
    novelty: float        # mean pairwise token-Jaccard distance among naive winners
    rho_bar: float        # mean pairwise correlation of strategy OOS returns (search redundancy)
    n_eff: float          # effective # independent trials = N / (1 + (N-1)·ρ̄)


def _draw_pool(gen, market: str, m: int, log=print) -> list:
    """Draw m valid, non-degenerate-candidate alphas in a fixed order (seeded per
    market+generator so the run is fully reproducible)."""
    if gen == "llm":
        return _draw_pool_llm(market, m, log=log)
    rng = random.Random(_seed(market, gen))
    fn = GENERATORS[gen]
    out, tries = [], 0
    while len(out) < m and tries < m * 50:
        tries += 1
        cand = fn(rng)
        if valid_alpha(cand):
            out.append(cand)
    return out


_BOOT = 25             # bootstrap subsets per N for a smooth E[best-of-N] curve


def sweep_market(market: str, bars: Bars, *, pool: int, sweep=None,
                 generators=None, log=print) -> list[SweepRow]:
    import statistics
    sweep = sweep or SWEEP
    generators = generators or list(GENERATORS)
    _MARKET_BARS[market] = bars                           # expose to the live-LLM drawer
    rows: list[SweepRow] = []
    compute_features(bars)                               # warm the per-bars cache once
    for gen in generators:
        m = min(pool, _LLM_POOL_CAP) if gen == "llm" else pool
        alphas = _draw_pool(gen, market, m, log=log)
        if not alphas:                                    # e.g. live-LLM arm with no core
            continue
        raws = [backtest_raw(a, bars) for a in alphas]   # backtest each ONCE
        kept = [(a, r) for a, r in zip(alphas, raws) if r is not None]
        K = len(kept)
        log(f"  [{market}/{gen}] pool={len(alphas)} tradeable={K}")
        base = random.Random(_seed("sweep", market, gen))
        # search redundancy: mean pairwise correlation of strategy OOS returns, from a
        # sample of the pool (one number per market+generator -> stable effective-N)
        corr_rng = random.Random(_seed("corr", market, gen))
        sample = [a for a, _ in kept[:120]]
        rho_bar = mean_pairwise_corr([oos_strat_returns(a, bars) for a in sample], corr_rng)
        for N in sweep:
            if N > K and N != sweep[0]:
                continue
            n = min(N, K)
            reps = 1 if n >= K else _BOOT
            n_eff = effective_trials(rho_bar, N)
            neff_trials = max(2, round(n_eff))
            best_l, pos_l, bar_l, robust_l, surv_l, survn_l, nov_l, dist_l = (
                [], [], [], [], [], [], [], [])
            for _ in range(reps):
                idx = list(range(n)) if reps == 1 else base.sample(range(K), n)
                sub = [kept[i] for i in idx]
                naive = [r["naive_ann"] for _, r in sub]
                best_l.append(max(naive))
                pos_l.append(sum(1 for w in naive if w > 0.0))
                bar_l.append(sum(1 for w in naive if w > 1.0))
                # ablation: worst-regime + cost, but NO deflation -> isolates which
                # tightener kills the snoop (generalization vs multiple-testing)
                robust_l.append(sum(1 for _, r in sub if r["worst_ann"] >= TARGET))
                # the full gate, deflated at n_trials = N (the nominal search size) ...
                surv_l.append(sum(1 for _, r in sub if deflated_ann(r, N) >= TARGET))
                # ... and at the EFFECTIVE trial count (the conservative-critique-proof one)
                survn_l.append(sum(1 for _, r in sub if deflated_ann(r, neff_trials) >= TARGET))
                winners = [a for a, r in sub if r["naive_ann"] > 0.0]
                nov_l.append(mean_pairwise_novelty(winners, base))
                dist_l.append(len({expr_to_str(a) for a, _ in sub}))
            rows.append(SweepRow(
                market=market, generator=gen, N=N,
                distinct=round(statistics.mean(dist_l)),
                naive_pos=round(statistics.mean(pos_l)),
                naive_bar=round(statistics.mean(bar_l)),
                best_naive=round(statistics.mean(best_l), 3),
                robust_raw=round(statistics.mean(robust_l), 2),
                survivors=round(statistics.mean(surv_l), 2),
                survivors_neff=round(statistics.mean(survn_l), 2),
                novelty=round(statistics.mean(nov_l), 3),
                rho_bar=round(rho_bar, 3),
                n_eff=round(n_eff, 1),
            ))
    return rows


def _print_table(rows: list[SweepRow]) -> None:
    hdr = (f"  {'market':16} {'gen':9} {'N':>5} {'distinct':>8} {'nOOS>0':>7} "
           f"{'bestOOS':>8} {'robust':>7} {'surv@N':>7} {'surv@neff':>9} {'rho':>6} "
           f"{'n_eff':>7}")
    cur = None
    for r in rows:
        if (r.market, r.generator) != cur:
            print()
            print(hdr)
            cur = (r.market, r.generator)
        print(f"  {r.market:16} {r.generator:9} {r.N:>5} {r.distinct:>8} {r.naive_pos:>7} "
              f"{r.best_naive:>+8.2f} {r.robust_raw:>7.2f} {r.survivors:>7.2f} "
              f"{r.survivors_neff:>9.2f} {r.rho_bar:>6.2f} {r.n_eff:>7.0f}")


def main() -> int:
    argv = sys.argv[1:]
    pool = 3000
    out = None
    data = None
    if "--pool" in argv:
        pool = int(argv[argv.index("--pool") + 1])
    if "--out" in argv:
        out = argv[argv.index("--out") + 1]
    if "--data" in argv:
        data = argv[argv.index("--data") + 1]

    generators = list(GENERATORS)
    if "--llm" in argv:                                   # pre-registered live-LLM arm
        generators.append("llm")

    markets = [
        ("planted", synthetic_universe()),            # strong real edge (reversion=0.40)
        ("small_planted", planted_universe(0.06)),    # realistically SMALL edge (gate power)
        ("noise", noise_universe()),                  # pure null
    ]
    if data:
        markets.append((f"real:{Path(data).stem}", load_price_csv(data)))

    print("N-SWEEP — does scaling the search discover edge or manufacture mirages?")
    print(f"  target deflated OOS Sharpe = {TARGET:.2f} ann | cost = {COST} | pool = {pool}")
    print(f"  generators = {', '.join(generators)}")
    print("  naive = best pooled-OOS holdout (no deflation) | gate = worst-regime, "
          "deflated at n_trials=N\n  surv@neff = gate deflated at the EFFECTIVE trial "
          "count (correlation-based)\n")
    all_rows: list[SweepRow] = []
    for name, bars in markets:
        rows = sweep_market(name, bars, pool=pool, generators=generators)
        all_rows.extend(rows)
    _print_table(all_rows)

    print("\n=> Read: best_naive (the data-snoop curve) RISES with N; survivors (the "
          "deflated gate)\n   stays ~0 on noise/real but POSITIVE on planted — scale "
          "manufactures false alpha,\n   the gate separates it from real edge. Creative "
          "draws raise novelty but not survivors\n   (more ORIGINAL mirages, lower n_eff "
          "= more correlated search).")

    if out:
        payload = {
            "config": {"target": TARGET, "cost": COST, "boot": _BOOT,
                       "generators": generators, "pool": pool, "sweep": SWEEP},
            "rows": [r.__dict__ for r in all_rows],
        }
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(payload, indent=2))
        print(f"\n(results written to {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
