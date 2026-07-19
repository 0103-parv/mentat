"""Co-tuned judge ablation: is INDEPENDENCE (not ensembling) the active ingredient?

Extends evaluator_overfit_demo.py with the experiment the literature has not run. Prior work
covers selection against a STATIC proxy judge (Gao et al. 2023 best-of-n; 2506.19248) and
independent-ensemble fixes (Coste et al.; Eisenstein et al.; PoLL). What is unclaimed: a judge
CO-TUNED on the generator's own search trace, and the ablation separating trace-independence
from ensembling per se.

Mechanism. One generator searches adaptively (its proposal mean drifts toward round winners).
Four judge conditions, identical search structure, only judge provenance differs:
  A  fixed-single       one frozen judge, quirks drawn independently of the trace (baseline;
                        the evaluator_overfit_demo.py case, now with adaptive search)
  B  cotuned-single     one judge whose quirk is refit each round toward the inert features of
                        the round's winners -- the judge "iterated until it looks right" on the
                        generator's own batch
  C  cotuned-ensemble   ENS judges, all refit on the SAME shared trace (their errors become
                        correlated through the trace); selection on their mean
  D  indep-ensemble     ENS judges frozen, never exposed to the trace; selection on their mean

Pre-registered hypotheses (scored as directional pass rates across SEEDS reseeds):
  H1  inflation(B) > inflation(A): co-tuning amplifies beyond a merely exploitable static judge
      (mutual generator<->judge adaptation is a Goodhart runaway, not a fixed target).
  H2  inflation(C) >> inflation(D): ensembling does NOT close the gap when members share the
      trace -- co-tuned ensembles stay mis-calibrated.
  H3  inflation(D) is the smallest of all four: independence from the trace, not ensembling,
      is the active ingredient.
  H4  true quality under D >= true quality under B: the honest judge condition also selects
      genuinely better candidates.

Inflation is reported ADDITIVELY per condition: (that condition's own reported score of its
final winner) minus (the winner's true quality). This is each condition's calibration gap --
the quantity a practitioner actually consumes -- and avoids ratio-of-near-zero pathologies.
An untouched held-out judge (never selected on, never tuned) is also reported for reference.

Deterministic, dependency-free, seeded; every number lands in ablation_cotuned_results.json.

  python3.14 papers/false-alpha/ablation_cotuned.py            # full run (SEEDS x REPS)
  python3.14 papers/false-alpha/ablation_cotuned.py --smoke    # fast directional check
"""
from __future__ import annotations
import json, random, sys, statistics
from pathlib import Path

K = 30              # feature dims per candidate
M_TRUE = 3          # first M_TRUE dims carry real quality; the rest are exploitable quirks
NS = [10, 30, 100, 300, 1000, 3000]
ENS = 10            # ensemble size for conditions C and D
ETA = 0.5           # judge co-tuning rate (quirk step toward round winners' inert features)
ALPHA = 0.5         # generator adaptation rate (mean step toward round winner)
TOP_FRAC = 0.2      # fraction of a round's batch the co-tuned judge refits on
SEEDS = 24          # independent rebuilds of the whole experiment
REPS = 12           # independent search runs per seed per N per condition
BASE_SEED = 7

TRUE_W = [1.0] * M_TRUE + [0.0] * (K - M_TRUE)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))

def true_quality(c):
    return dot(c, TRUE_W)

def score(c, quirk):
    return dot(c, TRUE_W) + dot(c, quirk)


def fresh_quirk(r):
    return [0.0] * M_TRUE + [r.gauss(0, 1) for _ in range(K - M_TRUE)]


def run_search(N, judges, cotune, rng):
    """One adaptive generate-and-select run. judges: list of quirk vectors (selection = mean
    score over them). cotune: if True, every judge is refit each round on the round's winners
    (the shared trace). Returns (reported, true_q, heldout_score_fn_input=winner)."""
    judges = [list(q) for q in judges]              # private copies (co-tuning mutates)
    rounds = max(2, min(6, N // 2))
    batch = max(1, N // rounds)
    mu = [0.0] * K                                  # generator proposal mean (the search state)
    best_c, best_s = None, None
    for _ in range(rounds):
        cands = [[mu[i] + rng.gauss(0, 1) for i in range(K)] for _ in range(batch)]
        sel = lambda c: sum(score(c, q) for q in judges) / len(judges)
        ranked = sorted(cands, key=sel, reverse=True)
        w = ranked[0]
        ws = sel(w)
        if best_s is None or ws > best_s:
            best_c, best_s = w, ws
        # generator adapts toward what the judge(s) liked -- the search trace forms
        mu = [m + ALPHA * (x - m) for m, x in zip(mu, w)]
        if cotune:
            top = ranked[:max(1, int(TOP_FRAC * len(ranked)))]
            m_inert = [sum(c[i] for c in top) / len(top) for i in range(K)]
            for q in judges:                        # ALL judges refit on the SAME shared trace
                for i in range(M_TRUE, K):
                    q[i] += ETA * m_inert[i]
    return best_s, true_quality(best_c), best_c


def run_seed(seed, ns, reps):
    r = random.Random(seed)
    heldout = fresh_quirk(r)                        # never selected on, never tuned
    out = {}
    for N in ns:
        acc = {c: [0.0, 0.0, 0.0] for c in "ABCD"}  # reported, true, heldout
        for rep in range(reps):
            base = random.Random(seed * 100003 + N * 101 + rep)
            # same initial judges + same generator stream per condition -> paired comparison
            single = fresh_quirk(base)
            ens = [fresh_quirk(base) for _ in range(ENS)]
            g = base.random()                       # advance; per-condition rng forks below
            for cond, judges, cotune in (("A", [single], False), ("B", [single], True),
                                         ("C", ens, True), ("D", ens, False)):
                rng = random.Random(seed * 7919 + N * 13 + rep * 17 + ord(cond))
                rep_s, rep_t, w = run_search(N, judges, cotune, rng)
                acc[cond][0] += rep_s
                acc[cond][1] += rep_t
                acc[cond][2] += score(w, heldout)
        out[N] = {c: {"reported": acc[c][0] / reps, "true": acc[c][1] / reps,
                      "heldout": acc[c][2] / reps,
                      "inflation": (acc[c][0] - acc[c][1]) / reps} for c in "ABCD"}
    return out


def main() -> int:
    smoke = "--smoke" in sys.argv
    ns = [10, 100, 1000] if smoke else NS
    seeds = 3 if smoke else SEEDS
    reps = 4 if smoke else REPS

    per_seed = [run_seed(BASE_SEED + s, ns, reps) for s in range(seeds)]

    # seed-averaged table + per-hypothesis directional pass rates
    table = []
    for N in ns:
        row = {"N": N}
        for c in "ABCD":
            for k in ("reported", "true", "heldout", "inflation"):
                vals = [ps[N][c][k] for ps in per_seed]
                row[f"{c}_{k}"] = round(statistics.mean(vals), 3)
                row[f"{c}_{k}_std"] = round(statistics.stdev(vals) if len(vals) > 1 else 0.0, 3)
        table.append(row)

    maxN = ns[-1]
    def rate(pred):
        return sum(1 for ps in per_seed if pred(ps)) / len(per_seed)
    passes = {
        "H1_cotuned_worse_than_fixed":
            rate(lambda ps: ps[maxN]["B"]["inflation"] > ps[maxN]["A"]["inflation"]),
        "H2_cotuned_ensemble_stays_inflated":
            rate(lambda ps: ps[maxN]["C"]["inflation"] > 2 * ps[maxN]["D"]["inflation"]),
        "H3_indep_ensemble_smallest_inflation":
            rate(lambda ps: ps[maxN]["D"]["inflation"] ==
                 min(ps[maxN][c]["inflation"] for c in "ABCD")),
        "H4_indep_true_quality_geq_cotuned":
            rate(lambda ps: ps[maxN]["D"]["true"] >= ps[maxN]["B"]["true"]),
        "inflation_B_grows_with_N":
            rate(lambda ps: ps[maxN]["B"]["inflation"] > ps[ns[0]]["B"]["inflation"]),
    }

    print("CO-TUNED JUDGE ABLATION  (A fixed-single | B cotuned-single | C cotuned-ens | D indep-ens)\n")
    print(f"  {'N':>6} | " + " | ".join(f"{c}: rep/true/infl" for c in "ABCD"))
    for row in table:
        cells = " | ".join(f"{row[f'{c}_reported']:>6.1f}/{row[f'{c}_true']:>4.1f}/{row[f'{c}_inflation']:>6.1f}"
                           for c in "ABCD")
        print(f"  {row['N']:>6} | {cells}")
    print("\nDirectional pass rates across seeds:")
    for k, v in passes.items():
        print(f"  {k}: {v:.0%}")

    out = Path(__file__).resolve().parent / ("ablation_cotuned_smoke.json" if smoke
                                             else "ablation_cotuned_results.json")
    out.write_text(json.dumps({"config": {"K": K, "M_true": M_TRUE, "NS": ns, "ens": ENS,
                                          "eta": ETA, "alpha": ALPHA, "top_frac": TOP_FRAC,
                                          "seeds": seeds, "reps": reps, "base_seed": BASE_SEED},
                               "seed_averaged_table": table,
                               "direction_pass_rates": passes}, indent=2))
    print(f"\n(results -> {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
