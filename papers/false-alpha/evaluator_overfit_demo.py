"""Evaluator overfitting in a generate-and-select loop (winner's curse in an LLM-style discovery loop).

The mechanism, in one breath: an automated judge scores each proposed candidate. It rewards a few
features that carry TRUE quality and many SPURIOUS features that carry none (the judge's own
quirks). A loop that proposes many candidates and keeps the best JUDGE score increasingly selects
candidates that exploit the judge's spurious tastes. So the judge score of the winner climbs
steeply with the number of proposals N, while the winner's TRUE quality rises only marginally and
its score on an INDEPENDENT held-out judge stays near its starting level with no reliable trend.
That widening gap is false-discovery inflation, the winner's curse, and it appears with NO
measurement noise, purely from selecting against a fixed evaluator. (Seed-robust: see
evaluator_overfit_robustness.py, where every directional claim holds in 100% of 24 reseeds.)

The sharper thesis: a fixed evaluator becomes an exploitable environment under repeated selection,
so an LLM-in-the-loop discovery system can look like it is improving while it is only overfitting
the judge. The fix is not one held-out judge (that just gets overfit too) but an ENSEMBLE of
independent judges, whose spurious tastes cancel, which recovers real quality.

Connections: winner's curse in quality-diversity (Flageat, Cully); deflated-Sharpe multiple testing
(Bailey & Lopez de Prado); chronological/held-out evaluation of coding agents (J. Yang); the value
of a cheap independent verifier (R. Lange). Deterministic, no dependencies, no API; a live LLM
generator/judge plugs into the same loop, the mechanism is evaluator-agnostic.

  python3.14 papers/false-alpha/evaluator_overfit_demo.py
"""
from __future__ import annotations
import json, random
from pathlib import Path

K = 30            # feature dimensions of a proposed candidate ("idea")
M_TRUE = 3        # only the first M_TRUE features carry real quality; the other 27 are quirks
NS = [10, 30, 100, 300, 1000, 3000]
REPS = 60         # independent best-of-N draws averaged per N (each draws FRESH candidates)
N_JUDGES = 10     # independent judges for the ensemble correction
SEED = 7

TRUE_W = [1.0] * M_TRUE + [0.0] * (K - M_TRUE)          # real quality
# each judge shares the true component but has its OWN independent spurious taste
_r = random.Random(SEED)
JUDGES = [[0.0] * M_TRUE + [_r.gauss(0, 1) for _ in range(K - M_TRUE)] for _ in range(N_JUDGES + 1)]
FIXED = JUDGES[0]          # the judge the loop optimizes against
HELDOUT = JUDGES[1]        # one independent held-out judge (for reporting)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))

def true_quality(c):   return dot(c, TRUE_W)
def score(c, quirk):   return dot(c, TRUE_W) + dot(c, quirk)     # true + that judge's taste


def main() -> int:
    gen = random.Random(SEED + 1)   # candidate generator; each rep draws a FRESH set of N candidates
                                    # (no shared pool -> unbiased expected best-of-N, no single-draw artifact)

    print("EVALUATOR OVERFITTING DEMO  (winner's curse in a generate-and-select loop)\n")
    print(f"  {K} features per idea, only the first {M_TRUE} carry real quality; the other "
          f"{K - M_TRUE} are the")
    print("  judge's exploitable quirks. No measurement noise anywhere.\n")
    print(f"  {'N':>6} {'judge score (opt.)':>18} {'independent judge':>18} {'true quality':>13} "
          f"{'inflation':>10} | {'ensemble-fix true q':>19}")

    rows = []
    for N in NS:
        j = h = t = ct = 0.0
        for _ in range(REPS):
            cands = [[gen.gauss(0, 1) for _ in range(K)] for _ in range(N)]   # fresh candidates
            # NAIVE: keep the candidate with the best score on the FIXED judge it optimizes against
            w = max(cands, key=lambda c: score(c, FIXED))
            j += score(w, FIXED)               # what the loop reports (optimized judge)
            h += score(w, HELDOUT)             # same winner, fresh independent judge
            t += true_quality(w)               # what it is actually worth
            # CORRECTED: select on the ENSEMBLE of independent judges (spurious tastes cancel)
            wc = max(cands, key=lambda c: sum(score(c, q) for q in JUDGES[1:]) / N_JUDGES)
            ct += true_quality(wc)
        j /= REPS; h /= REPS; t /= REPS; ct /= REPS
        rows.append({"N": N, "optimized_judge": round(j, 3), "independent_judge": round(h, 3),
                     "true_quality": round(t, 3), "inflation": round(j - h, 3),
                     "ensemble_fix_true_quality": round(ct, 3)})
        print(f"  {N:>6} {j:>18.2f} {h:>18.2f} {t:>13.2f} {j - h:>10.2f} | {ct:>19.2f}")

    f, l = rows[0], rows[-1]
    print("\n=> Reading the table:")
    print(f"   Optimized-judge score of the winner climbs {l['optimized_judge']/f['optimized_judge']:.1f}x "
          f"as the search grows ({f['optimized_judge']:.1f} -> {l['optimized_judge']:.1f}),")
    print(f"   while its real quality rises only marginally ({f['true_quality']:.1f} -> {l['true_quality']:.1f}), "
          f"an order of magnitude below the optimized score, and a fresh")
    print(f"   independent judge stays near its start ({f['independent_judge']:.1f} -> {l['independent_judge']:.1f}), "
          f"confirming the climb is illusory.")
    print(f"   The inflation (optimized minus independent) GROWS with N: {f['inflation']:.1f} -> {l['inflation']:.1f}.")
    print("   Pure evaluator overfitting: no noise, just selecting harder against a fixed judge.")
    print(f"   Selecting on an ensemble of independent judges recovers real quality: "
          f"{l['ensemble_fix_true_quality']:.1f} vs the naive {l['true_quality']:.1f} at N={l['N']}.")

    out = Path(__file__).resolve().parent / "evaluator_overfit_demo_results.json"
    out.write_text(json.dumps({"config": {"K": K, "M_true": M_TRUE, "candidates": "fresh per rep",
                                          "NS": NS, "reps": REPS, "n_judges": N_JUDGES, "seed": SEED},
                               "rows": rows}, indent=2))
    print(f"\n(results -> {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
