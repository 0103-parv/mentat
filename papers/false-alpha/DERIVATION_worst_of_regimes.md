# The worst of regimes deflation, derived from scratch

*A study note so you can defend this at a whiteboard. This is the single load bearing novel claim in the paper, so you need to be able to reproduce every line of it cold. Independently Monte Carlo checked on 2026-07-05; the numbers below match both the paper and a fresh simulation.*

## 1. The problem in one sentence

Your gate does not score a strategy by one Sharpe. It scores a strategy by its **worst** Sharpe across k out of sample regimes, then keeps the best of N strategies. The standard deflated Sharpe correction was derived for the **best of N single Sharpes**. That is the wrong null, and it is too harsh. Here is exactly why, and by how much.

## 2. Two nulls, side by side

Let Z be a standard normal (a Sharpe under the null of no skill, standardized).

**Standard deflated Sharpe null.** Search N strategies, each with one Sharpe. The best one under pure luck has expected value

  E[max over i of Z_i],  i = 1..N.

This is the classic extreme value quantity. Its leading order is sqrt(2 ln N), and its exact expectation for N = 1000 is about 3.24. This is what Bailey and Lopez de Prado deflate by.

**Your gate's null.** Each strategy has k regime Sharpes. Its score is the minimum of them (the worst regime). Then you take the best of N. So the right null is

  E[ max over i of ( min over g of Z_{i,g} ) ],  i = 1..N,  g = 1..k.

Call the inner quantity W_i = min over g of Z_{i,g}. You are taking the max of N copies of W. The whole question is: how big is E[max of N of W] compared to E[max of N of Z]?

## 3. Why the worst of k is so much smaller

The distribution of W = min of k standard normals is pushed to the left and, crucially, has a **thin upper tail**. Its CDF is

  G(w) = P(min of k <= w) = 1 minus P(all k > w) = 1 minus (1 minus Phi(w))^k,

where Phi is the standard normal CDF. For W to be large, **all k** regimes have to be large at once, and the probability of that is (1 minus Phi(w))^k, which for k = 3 is the cube of an already small tail. That cube is the whole story: extremes of W are rare, so the best of N of W sits far below the best of N of Z.

## 4. The leading order value (the one line you can recompute)

The best of N of any variable sits near the point where its CDF equals 1 minus 1/N (the typical maximum). Set G(w) = 1 minus 1/N:

  1 minus (1 minus Phi(w))^k = 1 minus 1/N
  (1 minus Phi(w))^k = 1/N
  1 minus Phi(w) = N^{ minus 1/k }
  Phi(w) = 1 minus N^{ minus 1/k }
  **w* = Phi^{ minus 1}( 1 minus N^{ minus 1/k } ).**

That is the whole derivation. For N = 1000, k = 3: N^{ minus 1/3} = 1000^{ minus 1/3} = 0.1, so Phi(w) = 0.9 and w* = Phi^{ minus 1}(0.9) = 1.28. The expected max is a touch above this quantile, about 1.38. Compare to the single Sharpe envelope of 3.24. So the standard correction is about 3.24 / 1.38 = 2.35 times too harsh for a 3 regime gate.

## 5. The numbers (independent Monte Carlo, matches the paper)

| quantity | value | how to get it |
|---|---|---|
| E[max of 1000 single Z] | 3.24 | expected max of 1000 normals |
| E[max of 1000 of min of 3] | 1.38 | the formula above, w* = Phi^{-1}(0.9) plus a small expected-max margin |
| over deflation ratio, k = 3 | 2.35 times | 3.24 / 1.38 |
| k = 2 | 1.65 times | thinner cube becomes a square, less shrinkage |
| k = 5 | 4.3 times | fifth power, much more shrinkage |

The ratio grows fast with k. State it as "about 2.4 times for the 3 regime gate," not as a universal constant.

## 6. The robustness dividend, and its clean closed form

Here is the intuition that makes the whole thing memorable. Ask: a search over N strategies with a worst of k gate has the same false discovery ceiling as a search over how many strategies with an ordinary single Sharpe gate? Call that number N prime. Match the two typical maxima:

  Phi^{ minus 1}(1 minus 1/N prime) = Phi^{ minus 1}(1 minus N^{ minus 1/k})
  1 / N prime = N^{ minus 1/k}
  **N prime = N^{ 1/k }.**

So requiring k independent regimes shrinks an effective N strategy search down to N^{1/k}. For N = 1000, k = 3 that is 1000^{1/3} = 10 at the quantile level (about 7 for the exact expected max). **Searching a thousand strategies but demanding they clear three independent regimes is, for multiple testing purposes, like having searched only about seven to ten strategies.** Requiring robustness is itself an implicit multiple testing correction. That single sentence is the paper's cleanest idea, and now you can derive it from N prime = N^{1/k}.

## 7. Why it collapses on real data (the part that resolves the tension)

The dividend N prime = N^{1/k} assumes the k regimes are **independent**. Real market sub periods are not independent, they are correlated. Model the regimes with one common factor,

  Z_g = sqrt(rho) F + sqrt(1 minus rho) eps_g,

where F is a shared shock and rho is the regime correlation. As rho rises, the k regimes carry less independent information, so the min of k is less punishing, the envelope rises back toward the single Sharpe one, and N prime climbs back toward N. Independent Monte Carlo, worst of 3 at N = 1000:

| regime correlation rho | 0.0 | 0.4 | 0.6 | 0.8 | 0.95 |
|---|---|---|---|---|---|
| N prime | 7 | 28 | 62 | 160 | 426 |

The real S&P sits around rho = 0.67, which gives N prime about 84 to 100. So on real data the robustness dividend has mostly collapsed (from about 7 up to about 84), which is exactly why the explicit deflation becomes load bearing on real markets, while on the adversarial synthetic null (independent regimes) the worst of regimes requirement alone already does the work. That is the resolution of the section 4.3 versus section 4.9 tension, and it is quantitative, not hand waving.

## 8. What to say if a referee pushes

- "Your gate is not the DSR statistic." Correct, and that is the point. The DSR is the max of N single Sharpes; my gate is the max of N of the min of k. I derived the right envelope, E[max of N of min of k], with leading order Phi^{-1}(1 minus N^{-1/k}), Monte Carlo validated. It is about 2.4 times smaller for three regimes, so the standard DSR over deflates. The real market zero survives the corrected, weaker bar, so my conclusion is if anything conservative.
- "Is 2.4 times a general number?" No. It is the three regime value. It is about 1.6 times for two regimes and about 4.3 times for five, because the shrinkage is the k th power of the tail.
- "So robustness replaces multiple testing?" Only when regimes are independent, where N prime = N^{1/k}. Real regimes correlate at about 0.67, which pushes N prime from about 7 back up to about 84, so on real data you still need the explicit deflation. Robustness and multiple testing are the same coin; how much each contributes depends on regime correlation, which I measure per market.

## 9. Reproduce it yourself

`independent_verify_deflation.py` recomputes sections 4, 5, and 6 from scratch in a minute. Run it, change k, watch the ratio move as the k th power predicts. Once you can rederive N prime = N^{1/k} on a napkin and explain the thin upper tail of the min of k, you own this result.
