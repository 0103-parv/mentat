"""Seed-robustness sweep for the evaluator-overfitting demo.

Why this exists: the single-run demo (`evaluator_overfit_demo.py`) draws fresh candidates per rep,
but at 60 reps its two near-zero columns (true quality, independent-judge score) are still a noisy
single draw of the whole environment. An earlier review found that a different seed could flip the
winner's true quality negative. This harness rebuilds the ENTIRE experiment (judges + candidates)
from scratch under many independent master seeds and reports, per N: the seed-averaged mean and the
across-seed standard deviation of each column, plus how often each qualitative claim holds. If the
paper's story is real it should survive reseeding; the pass rates below are that test.

Vectorized numpy port of the pure-Python model in evaluator_overfit_demo.py (identical mechanism):
  K=30 features, only the first M_TRUE=3 carry real quality; each judge = true component + its own
  independent Gaussian taste over the 27 inert features; the loop keeps the best FIXED-judge score.

  python3.14 papers/false-alpha/evaluator_overfit_robustness.py
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np

K = 30
M_TRUE = 3
NS = [10, 30, 100, 300, 1000, 3000]
REPS = 200          # independent best-of-N draws per (seed, N)
N_JUDGES = 10
SEEDS = list(range(1, 25))   # 24 fully independent rebuilds of the whole experiment

COLS = ["optimized_judge", "independent_judge", "true_quality", "inflation", "ensemble_fix_true_quality"]


def run_one_seed(seed: int) -> dict:
    """One full instance: fresh judges and fresh candidates. Returns per-N column means."""
    jrng = np.random.default_rng(seed)                     # judges' idiosyncratic tastes
    crng = np.random.default_rng(seed + 10_000)            # candidate generator (separate stream)

    quirks = np.zeros((N_JUDGES + 1, K))
    quirks[:, M_TRUE:] = jrng.standard_normal((N_JUDGES + 1, K - M_TRUE))
    fixed = quirks[0]                 # the judge the loop optimizes against
    heldout = quirks[1]              # one independent held-out judge (for reporting)
    ens_bar = quirks[1:].mean(0)     # ensemble selects on the mean of the independent judges

    out = {c: [] for c in COLS}
    for N in NS:
        opt = ind = tru = ens = 0.0
        for _ in range(REPS):
            C = crng.standard_normal((N, K))
            true_q = C[:, :M_TRUE].sum(1)                  # real quality of each candidate
            fixed_score = true_q + C @ fixed               # what the loop optimizes
            w = int(np.argmax(fixed_score))
            opt += fixed_score[w]
            ind += true_q[w] + C[w] @ heldout              # same winner, fresh independent judge
            tru += true_q[w]
            wc = int(np.argmax(true_q + C @ ens_bar))      # ensemble-selected winner
            ens += true_q[wc]
        opt /= REPS; ind /= REPS; tru /= REPS; ens /= REPS
        out["optimized_judge"].append(opt)
        out["independent_judge"].append(ind)
        out["true_quality"].append(tru)
        out["inflation"].append(opt - ind)
        out["ensemble_fix_true_quality"].append(ens)
    return out


def main() -> int:
    per_seed = [run_one_seed(s) for s in SEEDS]
    arr = {c: np.array([ps[c] for ps in per_seed]) for c in COLS}   # each (n_seeds, n_N)

    mean = {c: arr[c].mean(0) for c in COLS}
    std = {c: arr[c].std(0, ddof=1) for c in COLS}

    lo, hi = 0, len(NS) - 1
    # Direction claims tested per seed (fraction of seeds where each holds):
    pass_opt_climbs = float((arr["optimized_judge"][:, hi] > arr["optimized_judge"][:, lo]).mean())
    pass_inflation_grows = float((arr["inflation"][:, hi] > arr["inflation"][:, lo]).mean())
    pass_ensemble_beats = float((arr["ensemble_fix_true_quality"][:, hi] > arr["true_quality"][:, hi]).mean())
    # honest estimate reveals illusion: at max N, optimized score is well above the independent one
    pass_illusion = float((arr["optimized_judge"][:, hi] > arr["independent_judge"][:, hi] + 5).mean())

    print(f"Seed-robustness sweep  ({len(SEEDS)} seeds x {REPS} reps, fresh judges+candidates each seed)\n")
    hdr = f"  {'N':>6}" + "".join(f"{c.replace('_',' '):>26}" for c in COLS)
    print(hdr)
    for i, N in enumerate(NS):
        cells = "".join(f"{mean[c][i]:>11.2f} +/-{std[c][i]:>6.2f}     " for c in COLS)
        print(f"  {N:>6}{cells}")

    print("\n  Direction claims (fraction of seeds where the claim holds):")
    print(f"    optimized-judge score climbs with N ...................... {pass_opt_climbs:.0%}")
    print(f"    inflation (optimized - independent) grows with N ......... {pass_inflation_grows:.0%}")
    print(f"    ensemble selection beats naive true quality (max N) ...... {pass_ensemble_beats:.0%}")
    print(f"    optimized score >> honest independent estimate (max N) ... {pass_illusion:.0%}")

    table = [{"N": N, **{c: round(float(mean[c][i]), 3) for c in COLS},
              **{f"{c}_std": round(float(std[c][i]), 3) for c in COLS}}
             for i, N in enumerate(NS)]
    result = {
        "config": {"K": K, "M_true": M_TRUE, "NS": NS, "reps": REPS,
                   "n_judges": N_JUDGES, "n_seeds": len(SEEDS), "candidates": "fresh per rep"},
        "seed_averaged_table": table,
        "direction_pass_rates": {
            "optimized_judge_climbs_with_N": pass_opt_climbs,
            "inflation_grows_with_N": pass_inflation_grows,
            "ensemble_beats_naive_true_quality": pass_ensemble_beats,
            "optimized_far_above_independent": pass_illusion,
        },
    }
    out = Path(__file__).resolve().parent / "evaluator_overfit_robustness.json"
    out.write_text(json.dumps(result, indent=2))
    print(f"\n(results -> {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
