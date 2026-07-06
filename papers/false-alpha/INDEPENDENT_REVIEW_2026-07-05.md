# Independent verification and adversarial review of the false alpha paper

*Prepared 2026-07-05. This is a review and reproduction report, not part of the paper. Every empirical claim below comes from a fresh script written from scratch (numpy only), not from re running the paper's own code, so it is genuine independent confirmation. Scripts: `independent_verify_deflation.py`, `independent_verify_evaluator.py`.*

## Bottom line

The two pieces that are genuinely yours both survive independent reproduction. The worst of regimes deflation reproduces almost exactly. The evaluator overfitting mechanism reproduces and is robust once one methodological wrinkle in the demo is fixed. The paper is honest and holds up. The action items are small: state the k dependence of the over deflation precisely, and fix the single pool noise in the demo. Details follow.

## 1. The worst of regimes deflation (section 4.9), VERIFIED

This is the paper's strongest original claim: the gate scores a strategy by its minimum across k out of sample regimes, so the right multiple testing null is E[max over N of (min over k)], which is far below the single Sharpe envelope E[max over N] that the standard deflated Sharpe uses. I recomputed both envelopes from scratch by Monte Carlo.

| quantity | paper | independent MC | match |
|---|---|---|---|
| single Sharpe envelope, E[max of 1000 normals] | 3.26 | 3.241 | yes |
| worst of 3 regimes, E[max of 1000 of min of 3] | 1.38 | 1.377 | yes |
| over deflation ratio at k = 3 | about 2.4 times | 2.35 times | yes |
| robustness dividend N prime | about 7 | 7 (E[max of 7] = 1.35) | yes |

The math is correct and reproduces to two decimals. This is the part of the paper you should be most confident in.

**One honest nuance the paper undersells.** The over deflation factor depends strongly on the number of regimes k, so a single number like "about 2.4 times" or the stated range "2.3 to 2.8 times" is really the k = 3 case. My sweep:

| k regimes | over deflation ratio at N = 1000 | at N = 3000 |
|---|---|---|
| 2 | 1.65 times | 1.61 times |
| 3 | 2.35 times | 2.26 times |
| 5 | 4.32 times | 3.90 times |

So state it as "about 2.4 times for the 3 regime gate, rising steeply with the number of regimes." That is more precise and a reviewer will respect it. It does not weaken the conclusion, since the real market zero survives the corrected bar either way.

**The correlated regime collapse also reproduces exactly.** The paper's resolution of its own central tension (why worst of regimes robustness is enough on the synthetic null but explicit deflation is load bearing on real data) rests on the robustness dividend collapsing as regimes correlate. I reproduced it with a one factor equicorrelated model:

| regime correlation | 0.0 | 0.4 | 0.6 | 0.8 | 0.95 |
|---|---|---|---|---|---|
| paper N prime | 7 | 28 | 62 | 160 | 426 |
| independent MC | 7 | 28 | 62 | 160 | 426 |

Exact at every point, and the real S&P at correlation about 0.67 gives N prime about 84 to 100. So the whole of section 4.9, the independent envelope, the over deflation ratio, the dividend, and its collapse under correlation, is independently confirmed. This is the most defensible part of the paper.

## 2. The evaluator overfitting demo, VERIFIED with one fix

I reimplemented the mechanism from scratch and swept the parameters. The qualitative claims all hold: the optimized judge score of the winner climbs about 2.3 times with the search size, the inflation (optimized minus independent judge) grows, and selecting on an ensemble of independent judges recovers real quality. Supporting checks:

- **Control.** With a quirk free judge (the judge equals true quality), there is no inflation, selection just improves real quality. So the inflation is genuinely driven by the spurious features, not by selection alone. Good, this is the mechanism working.
- **Ensemble scaling.** One held out judge barely beats naive selection (it is itself exploitable), and recovery grows with the number of judges and saturates around ten to thirty. This is exactly the paper's point that a single held out judge is not the fix.
- **Sensitivity.** The effect shrinks when the judge is mostly aligned with truth (few inert features) and grows when there are many inert features to exploit. Sensible and worth stating.

**The one real problem, and the fix.** The committed demo fixes a single pool of 6000 candidates and draws subsets from it. At large N the winner converges to that one pool's single most extreme candidate, so the true quality and independent judge values at N = 1000 and 3000 are one noisy draw, not an expectation. In my first single pool run they swung negative (true quality went to about negative 1.4); the paper's seed happened to show them rising. Redrawing the pool each repetition removes this. The honest multi pool expectation is clean and matches the paper's story:

| N | optimized judge | independent judge | true quality | inflation | ensemble true quality |
|---|---|---|---|---|---|
| 10 | 8.36 | 0.82 | 0.86 | 7.54 | 1.97 |
| 100 | 13.71 | 1.35 | 1.45 | 12.37 | 3.20 |
| 1000 | 17.62 | 1.92 | 1.80 | 15.70 | 4.11 |
| 3000 | 19.29 | 1.90 | 1.99 | 17.39 | 4.46 |

So: optimized judge climbs 2.3 times, true quality and independent judge stay roughly flat near 1 to 2, inflation grows to about 17, ensemble recovers to about 4.5. **Fix the demo to redraw the pool per repetition** (a one line change) and the "stays flat" claim becomes robust rather than seed lucky. Right now a skeptical reader who reruns with a different seed could see true quality diverge and think the demo is broken.

## 3. Adversarial read: what a sharp referee will push on

- **The headline is not new, and that is fine if you lead with it.** Say up front that the "machine scale search manufactures false discoveries" result is known (FINSABER, Sullivan Timmermann White) and that your contribution is the apparatus plus the two corrections. The paper already does this; keep it front and center, do not let the abstract read as if the zero is the discovery.
- **Low recall bounds every claim.** The zero is a precision statement; the gate misses any edge below a worst regime Sharpe of about 2 to 3 at N = 1000. Never let "zero survivors" be read as "no edge exists." The paper is careful here, keep it that way.
- **The demo proves a mechanism, not an effect size.** It is a linear synthetic model where the quirks are literally random weights, so selection exploiting them is close to true by construction. That is fine for illustrating the mechanism, but do not imply it measures how big the effect is in a real LLM loop. The live LLM generator and judge version is what would turn it from illustration into evidence, and that is the honest next step.
- **State the k dependence** of the over deflation (see section 1 above).
- **The robustness dividend assumes independent regimes.** Real regimes correlate (the paper measures the S&P at about 0.67), which collapses the dividend to N prime about 84. The paper handles this, but a reviewer will check that the collapse is stated wherever the clean N prime about 7 is quoted, so pair them everywhere.

## 4. Prioritized to do

1. Fix the demo to redraw the pool per repetition, then regenerate its results and figure. Small change, removes the only real fragility I found.
2. In section 4.9 and the abstract, state the over deflation as k dependent (about 2.4 times at k = 3) rather than a single constant.
3. Everywhere the clean robustness dividend (N prime about 7) appears, pair it with the correlated regime collapse (N prime about 84 for the real S&P) so the two are never read in isolation.
4. When you build the demo into a live LLM generator and judge result, that is what upgrades Part III from illustration to evidence. It is the single highest value next experiment for the novelty budget.

## 5. What this review did not check

I verified the extreme value mathematics and the demo mechanism independently, which are the two novel pieces. I did not rerun the full trading pipeline (nsweep, bootstrap, panel, independent markets) because that needs the mentat engine and, for the live arm, the API; those are already committed with their own JSON artifacts and a 20 check suite. The highest leverage independent checks were the two above, and both passed.
