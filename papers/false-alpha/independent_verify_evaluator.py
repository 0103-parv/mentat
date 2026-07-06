"""Independent reimplementation + stress test of the evaluator-overfitting demo.

Mechanism under test: candidates are K-dim vectors; only the first M_TRUE features carry
real quality; a judge scores = true_quality + (that judge's random taste over the inert
features). A loop keeps the best score on a FIXED judge over N candidates. Claims:
  (1) optimized-judge score of the winner climbs with N (inflation), while true quality and
      an INDEPENDENT judge stay ~flat  -> selection overfits the fixed judge, no noise.
  (2) selecting on an ENSEMBLE of independent judges recovers real quality.

Questions this adds: is the effect robust to K, M_TRUE, n_judges? Is it just a function of
how much "quirk" variance there is (i.e., trivial), and does the ensemble fix scale as 1/sqrt(J)?
"""
import numpy as np
rng = np.random.default_rng(7)

def run(K=30, M=3, n_judges=10, NS=(10,30,100,300,1000,3000), reps=4000, pool=6000):
    true_w = np.zeros(K); true_w[:M] = 1.0
    # each judge: shares true component, own independent gaussian taste on inert features
    tastes = rng.standard_normal((n_judges+1, K)); tastes[:, :M] = 0.0
    fixed, held = tastes[0], tastes[1]
    pool_c = rng.standard_normal((pool, K))
    tq_pool   = pool_c @ true_w
    fix_pool  = pool_c @ (true_w + fixed)
    held_pool = pool_c @ (true_w + held)
    ens_pool  = pool_c @ (true_w + tastes[1:].mean(axis=0))   # ensemble mean score
    out = {}
    for N in NS:
        j=h=t=ce=0.0
        for _ in range(reps):
            idx = rng.integers(0, pool, N)
            w = idx[np.argmax(fix_pool[idx])]        # winner by FIXED judge
            j += fix_pool[w]; h += held_pool[w]; t += tq_pool[w]
            wc = idx[np.argmax(ens_pool[idx])]       # winner by ensemble of judges
            ce += tq_pool[wc]
        out[N] = (j/reps, h/reps, t/reps, ce/reps)
    return out

def show(title, res):
    print(f"\n{title}")
    print(f"  {'N':>5} {'optJudge':>9} {'indJudge':>9} {'trueQ':>7} {'inflation':>9} | {'ensFixTrueQ':>11}")
    for N,(j,h,t,ce) in res.items():
        print(f"  {N:>5} {j:>9.2f} {h:>9.2f} {t:>7.2f} {j-h:>9.2f} | {ce:>11.2f}")
    f=res[min(res)]; l=res[max(res)]
    print(f"  -> optJudge climbs {l[0]/f[0]:.2f}x; trueQ {f[2]:.2f}->{l[2]:.2f}; "
          f"indJudge {f[1]:.2f}->{l[1]:.2f}; ensemble trueQ at max N = {l[3]:.2f} vs naive {l[2]:.2f}")

print("=== BASELINE (paper config: K=30, M=3, judges=10) ===")
show("baseline", run())

print("\n=== ROBUSTNESS SWEEP ===")
show("more inert features K=100 (more quirks to exploit)", run(K=100))
show("fewer inert features K=10", run(K=10))
show("more real signal M=10", run(M=10))
show("only 3 judges in ensemble", run(n_judges=3))
show("30 judges in ensemble", run(n_judges=30))

print("\n=== CONTROL: quirk-free judge (taste=0) should show NO inflation ===")
def run_noquirk(K=30,M=3,NS=(10,1000),reps=4000,pool=6000):
    true_w=np.zeros(K); true_w[:M]=1.0
    pool_c=rng.standard_normal((pool,K)); tq=pool_c@true_w
    for N in NS:
        s=0.0
        for _ in range(reps):
            idx=rng.integers(0,pool,N); s+=tq[idx].max()
        print(f"  N={N}: winner true quality (judge==truth) = {s/reps:.2f}  (pure quality selection, expected to rise: this is REAL improvement, not inflation)")
run_noquirk()

print("\n=== ENSEMBLE SCALING: does true-quality recovery grow with #judges? ===")
for J in [1,2,5,10,30,100]:
    r=run(n_judges=J, NS=(3000,), reps=3000)
    print(f"  judges={J:>3}: ensemble true quality @N=3000 = {r[3000][3]:.2f}")
