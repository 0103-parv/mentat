"""Seed-variance bands — does the single-seed result generalize? (addresses a §6 limitation)

Each (market, generator) pool in the main sweep uses ONE seed, so the curves are single
realizations. Here we redraw the pool under K independent seeds and report mean +/- SD of
the headline metrics, so the reader sees the sampling spread, not one lucky/unlucky draw.

DoD: on real markets, survivors are 0 under EVERY seed (not just the reported one); bestOOS
has a tight band; the planted control's survivors are positive under every seed.

  python3.14 papers/false-alpha/seed_variance.py
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
    TARGET, backtest_raw, creative_alpha, deflated_ann, noise_universe, random_alpha,
    valid_alpha,
)
from mentat.trade_lab import load_price_csv, synthetic_universe  # noqa: E402

K_SEEDS = 8
POOL = 1000
NS = [100, 300, 1000]
GENS = {"random": lambda rng: random_alpha(rng),
        "creative": lambda rng: creative_alpha(rng, risk=0.7)}


def one_seed(market_bars, gen: str, seed: int):
    rng = random.Random(seed)
    fn = GENS[gen]
    raws, tries = [], 0
    while len(raws) < POOL and tries < POOL * 40:
        tries += 1
        a = fn(rng)
        if valid_alpha(a):
            r = backtest_raw(a, market_bars)
            if r is not None:
                raws.append(r)
    out = {}
    for N in NS:
        w = raws[:N]
        if len(w) < N:
            continue
        out[N] = {"best": max(r["naive_ann"] for r in w),
                  "surv": sum(1 for r in w if deflated_ann(r, N) >= TARGET)}
    return out


def main() -> int:
    markets = [("planted", synthetic_universe()), ("noise", noise_universe()),
               ("real:fred_SP500", load_price_csv("data/fred_SP500.csv"))]
    print(f"SEED-VARIANCE BANDS — {K_SEEDS} independent seeds per (market, generator)\n")
    print(f"  {'market':16} {'gen':9} {'N':>5} {'bestOOS mean±sd':>18} "
          f"{'survivors mean±sd':>18} {'surv range':>12}")
    rows = []
    for name, bars in markets:
        for gen in GENS:
            per = [one_seed(bars, gen, 1000 + s) for s in range(K_SEEDS)]
            for N in NS:
                bests = [p[N]["best"] for p in per if N in p]
                survs = [p[N]["surv"] for p in per if N in p]
                if not bests:
                    continue
                bm, bsd = statistics.mean(bests), (statistics.pstdev(bests))
                sm, ssd = statistics.mean(survs), (statistics.pstdev(survs))
                rows.append({"market": name, "generator": gen, "N": N,
                             "best_mean": round(bm, 3), "best_sd": round(bsd, 3),
                             "surv_mean": round(sm, 2), "surv_sd": round(ssd, 2),
                             "surv_min": min(survs), "surv_max": max(survs), "seeds": K_SEEDS})
                print(f"  {name:16} {gen:9} {N:>5} {bm:>+9.2f} ± {bsd:<5.2f}   "
                      f"{sm:>7.1f} ± {ssd:<5.1f}   [{min(survs)},{max(survs)}]")

    real_bad = [r for r in rows if r["market"].startswith("real") and r["surv_max"] > 0]
    plant_bad = [r for r in rows if r["market"] == "planted" and r["surv_min"] == 0
                 and r["N"] == 1000]
    print("\n=> Real markets: survivors are 0 under EVERY seed at every N:",
          "CONFIRMED" if not real_bad else f"VIOLATED in {len(real_bad)} cells")
    print("   Planted: survivors > 0 under every seed (N=1000):",
          "CONFIRMED" if not plant_bad else "varies")
    out = "papers/false-alpha/seed_variance_results.json"
    Path(out).write_text(json.dumps({"config": {"seeds": K_SEEDS, "pool": POOL, "NS": NS},
                                     "rows": rows}, indent=2))
    print(f"\n(results -> {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
