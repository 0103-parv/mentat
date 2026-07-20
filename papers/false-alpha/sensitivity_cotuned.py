"""Sensitivity sweep for the co-tuned judge ablation (answers the panel's criticism #1).

Question: are the qualitative claims (H1: B>A inflation; H2: C>2xD; H3: D smallest;
H4: D true quality >= B) robust to the arbitrary knobs, or artifacts of one aggressive
parameterization? One-factor-at-a-time around the baseline (eta=0.5 accumulate, K=30,
ENS=10, top_frac=0.2):

  eta       0.1, 0.25, 0.5, 1.0     (co-tuning rate)
  update    accumulate vs interpolate (u += eta*m  vs  u += eta*(m-u))  <- the big one
  K         10, 30, 100             (feature dims; M_true=3 fixed)
  ENS       3, 10, 30               (ensemble size)
  top_frac  0.1, 0.2, 0.5           (fraction the judge refits on)

Per cell: 8 seeds x 6 reps, N in {100, 1000}, all four conditions; report seed-averaged
inflations/true quality at N=1000 and per-seed directional pass rates. Pre-registered
success criterion: all four directions hold in every cell (magnitudes may vary freely
and are reported as ranges). Deterministic, dependency-free.

  python3.14 papers/false-alpha/sensitivity_cotuned.py
"""
from __future__ import annotations
import json, random, statistics
from pathlib import Path

M_TRUE = 3
NS = [100, 1000]
SEEDS = 8
REPS = 6
BASE_SEED = 7


def dot(a, b): return sum(x * y for x, y in zip(a, b))


def run_search(N, judges, cotune, rng, K, eta, alpha, top_frac, interpolate,
               refresh_every=None, shrink=None):
    true_w = [1.0] * M_TRUE + [0.0] * (K - M_TRUE)
    judges = [list(q) for q in judges]
    q0 = [list(q) for q in judges]                  # initial state (for shrink regularization)
    rounds = max(2, min(6, N // 2))
    batch = max(1, N // rounds)
    mu = [0.0] * K
    best_c, best_s = None, None
    for rnd in range(rounds):
        if cotune and refresh_every and rnd > 0 and rnd % refresh_every == 0:
            # mitigation: periodically replace the iterated judge with a fresh one
            judges = [[0.0] * M_TRUE + [rng.gauss(0, 1) for _ in range(K - M_TRUE)]
                      for _ in judges]
            q0 = [list(q) for q in judges]
        cands = [[mu[i] + rng.gauss(0, 1) for i in range(K)] for _ in range(batch)]
        sel = lambda c: sum(dot(c, true_w) + dot(c, q) for q in judges) / len(judges)
        ranked = sorted(cands, key=sel, reverse=True)
        w = ranked[0]
        ws = sel(w)
        if best_s is None or ws > best_s:
            best_c, best_s = w, ws
        mu = [m + alpha * (x - m) for m, x in zip(mu, w)]
        if cotune:
            top = ranked[:max(1, int(top_frac * len(ranked)))]
            m_inert = [sum(c[i] for c in top) / len(top) for i in range(K)]
            for q in judges:
                for i in range(M_TRUE, K):
                    q[i] += eta * (m_inert[i] - q[i]) if interpolate else eta * m_inert[i]
            if shrink is not None:
                # mitigation: regularize rubric drift back toward initialization each round
                for q, qz in zip(judges, q0):
                    for i in range(M_TRUE, K):
                        q[i] = qz[i] + shrink * (q[i] - qz[i])
    return best_s, dot(best_c, true_w)


def run_cell(name, K=30, ens=10, eta=0.5, top_frac=0.2, interpolate=False, alpha=0.5,
             refresh_every=None, shrink=None):
    def quirk(r): return [0.0] * M_TRUE + [r.gauss(0, 1) for _ in range(K - M_TRUE)]
    per_seed = []
    for s in range(SEEDS):
        seed = BASE_SEED + s
        out = {}
        for N in NS:
            acc = {c: [0.0, 0.0] for c in "ABCD"}
            for rep in range(REPS):
                base = random.Random(seed * 100003 + N * 101 + rep)
                single = quirk(base)
                ens_j = [quirk(base) for _ in range(ens)]
                for cond, judges, cotune in (("A", [single], False), ("B", [single], True),
                                             ("C", ens_j, True), ("D", ens_j, False)):
                    rng = random.Random(seed * 7919 + N * 13 + rep * 17 + ord(cond))
                    rs, rt = run_search(N, judges, cotune, rng, K, eta, alpha, top_frac, interpolate,
                                        refresh_every=refresh_every, shrink=shrink)
                    acc[cond][0] += rs
                    acc[cond][1] += rt
            out[N] = {c: {"infl": (acc[c][0] - acc[c][1]) / REPS,
                          "true": acc[c][1] / REPS} for c in "ABCD"}
        per_seed.append(out)
    maxN = NS[-1]
    rate = lambda pred: sum(1 for ps in per_seed if pred(ps)) / len(per_seed)
    passes = {
        "H1_B_gt_A": rate(lambda ps: ps[maxN]["B"]["infl"] > ps[maxN]["A"]["infl"]),
        "H2_C_gt_2D": rate(lambda ps: ps[maxN]["C"]["infl"] > 2 * ps[maxN]["D"]["infl"]),
        "H3_D_smallest": rate(lambda ps: ps[maxN]["D"]["infl"] ==
                              min(ps[maxN][c]["infl"] for c in "ABCD")),
        "H4_D_true_geq_B": rate(lambda ps: ps[maxN]["D"]["true"] >= ps[maxN]["B"]["true"]),
    }
    mean = {c: {k: round(statistics.mean(ps[maxN][c][k] for ps in per_seed), 2)
                for k in ("infl", "true")} for c in "ABCD"}
    return {"cell": name, "config": {"K": K, "ens": ens, "eta": eta, "top_frac": top_frac,
                                     "update": "interpolate" if interpolate else "accumulate",
                                     "refresh_every": refresh_every, "shrink": shrink},
            "meanN1000": mean, "passes": passes,
            "all_pass": all(v == 1.0 for v in passes.values())}


def main() -> int:
    cells = [
        run_cell("baseline"),
        run_cell("eta=0.1", eta=0.1),
        run_cell("eta=0.25", eta=0.25),
        run_cell("eta=1.0", eta=1.0),
        run_cell("interpolate", interpolate=True),
        run_cell("interp+eta=1.0", interpolate=True, eta=1.0),
        run_cell("K=10", K=10),
        run_cell("K=100", K=100),
        run_cell("ENS=3", ens=3),
        run_cell("ENS=30", ens=30),
        run_cell("top=0.1", top_frac=0.1),
        run_cell("top=0.5", top_frac=0.5),
        run_cell("mit:refresh k=2", refresh_every=2),
        run_cell("mit:refresh k=1", refresh_every=1),
        run_cell("mit:shrink 0.5", shrink=0.5),
    ]
    print(f"{'cell':>16} | {'A':>7} {'B':>8} {'C':>8} {'D':>6} | B/A  C/D | H1 H2 H3 H4")
    for c in cells:
        m = c["meanN1000"]
        p = c["passes"]
        ba = m["B"]["infl"] / m["A"]["infl"] if m["A"]["infl"] else float("nan")
        cd = m["C"]["infl"] / m["D"]["infl"] if m["D"]["infl"] else float("nan")
        flags = " ".join("OK" if p[h] == 1.0 else f"{p[h]:.0%}" for h in
                         ("H1_B_gt_A", "H2_C_gt_2D", "H3_D_smallest", "H4_D_true_geq_B"))
        print(f"{c['cell']:>16} | {m['A']['infl']:>7.1f} {m['B']['infl']:>8.1f} "
              f"{m['C']['infl']:>8.1f} {m['D']['infl']:>6.1f} | {ba:>4.1f} {cd:>4.1f} | {flags}")
    n_all = sum(1 for c in cells if c["all_pass"])
    print(f"\ncells with ALL four directions at 100% of seeds: {n_all}/{len(cells)}")
    out = Path(__file__).resolve().parent / "sensitivity_cotuned_results.json"
    out.write_text(json.dumps({"config": {"NS": NS, "seeds": SEEDS, "reps": REPS,
                                          "M_true": M_TRUE}, "cells": cells}, indent=2))
    print(f"(results -> {out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
