"""Independent verification of the paper's central novel claim (section 4.9):

The gate scores a strategy by the MINIMUM of its k out-of-sample regime Sharpes, then
searches N strategies. The standard deflated-Sharpe haircut is E[max of N single Sharpes],
which is the WRONG null. The paper claims the correct envelope E[max_{i<=N} min_{g<=k} Z]
is far smaller, so the standard DSR over-deflates by ~2.4x. Reported anchors to reproduce:

  N=1000, single-Sharpe envelope E[max_N Z] ~ 3.26
  N=1000, k=3 worst-of-regimes envelope E[max_N min_3 Z] ~ 1.38
  ratio ~ 2.3 to 2.8x (called ~2.4x for k=3)
  robustness dividend: worst-of-3 at N=1000 ~ single-Sharpe search over N' ~ 7

This script writes its OWN Monte Carlo from scratch (numpy only), independent of the repo.
"""
import numpy as np

rng = np.random.default_rng(20260705)

def emax_single(N, reps=400_000, batch=40_000):
    """E[max of N iid standard normals]."""
    acc, n = 0.0, 0
    while n < reps:
        r = min(batch, reps - n)
        z = rng.standard_normal((r, N))
        acc += z.max(axis=1).sum(); n += r
    return acc / reps

def emax_minK(N, k, reps=200_000, batch=None):
    """E[max_{i<=N} min_{g<=k} Z_{i,g}] with independent regimes."""
    if batch is None:
        batch = max(1000, int(4e8 / (N * k)))   # ~cap memory per batch
    acc, n = 0.0, 0
    while n < reps:
        r = min(batch, reps - n)
        z = rng.standard_normal((r, N, k))
        acc += z.min(axis=2).max(axis=1).sum(); n += r
    return acc / reps

def n_prime(target, lo=1, hi=100000):
    """Smallest-ish N' with E[max_{N'} Z] ~ target, via E[max_N Z] ~ sqrt(2 ln N) - ... ;
    just search over a grid of N' with a quick MC."""
    grid = [2,3,5,7,10,15,20,34,50,100]
    vals = {m: emax_single(m, reps=120_000) for m in grid}
    best = min(grid, key=lambda m: abs(vals[m] - target))
    return best, vals

print("=== (A) single-Sharpe envelope  E[max_N Z]  (Bailey-Lopez de Prado / DSR null) ===")
for N in [10, 100, 1000, 3000]:
    v = emax_single(N)
    print(f"  N={N:>5}: E[max_N Z] = {v:.3f}   (leading order sqrt(2 ln N) = {np.sqrt(2*np.log(N)):.3f})")

print("\n=== (B) worst-of-k-regimes envelope  E[max_N min_k Z]  (paper's new null) ===")
rows = {}
for N in [1000, 3000]:
    for k in [2, 3, 5]:
        v = emax_minK(N, k)
        rows[(N,k)] = v
        print(f"  N={N:>5}, k={k}: E[max_N min_k Z] = {v:.3f}")

print("\n=== (C) over-deflation ratio  single / worst-of-k ===")
sN = {N: emax_single(N) for N in [1000, 3000]}
for N in [1000, 3000]:
    for k in [2, 3, 5]:
        ratio = sN[N] / rows[(N,k)]
        print(f"  N={N:>5}, k={k}: single {sN[N]:.3f} / worst-of-k {rows[(N,k)]:.3f} = {ratio:.2f}x")

print("\n=== (D) robustness dividend: N' such that single-Sharpe search matches worst-of-3 @ N=1000 ===")
target = rows[(1000,3)]
best, vals = n_prime(target)
print(f"  worst-of-3 @ N=1000 envelope = {target:.3f}")
print(f"  closest single-Sharpe N' (E[max_N' Z] ~ {target:.3f}) = N'~{best}  (E[max_{best} Z]={vals[best]:.3f})")
print(f"  neighbourhood: " + ", ".join(f"N'={m}:{vals[m]:.2f}" for m in [3,5,7,10,15]))

print("\n=== VERDICT vs paper anchors (N=1000, k=3) ===")
print(f"  paper says single ~3.26, got {sN[1000]:.3f}  -> {'MATCH' if abs(sN[1000]-3.26)<0.1 else 'DIFF'}")
print(f"  paper says worst-of-3 ~1.38, got {rows[(1000,3)]:.3f}  -> {'MATCH' if abs(rows[(1000,3)]-1.38)<0.12 else 'DIFF'}")
r = sN[1000]/rows[(1000,3)]
print(f"  paper says ratio ~2.4x, got {r:.2f}x  -> {'MATCH' if 2.2<r<2.6 else 'DIFF'}")
print(f"  paper says N'~7, got N'~{best}  -> {'MATCH' if best in (5,7,10) else 'DIFF'}")
