# More Strategies, Same Zero: Does LLM-Scale Alpha Search Discover Edge or Manufacture False Discoveries?

**A controlled N-sweep test of the false-strategy theorem with a live LLM proposer — and why scaling the search raises the discovery bar faster than it finds edge**

*Parv Mehndiratta. Working paper, draft v0.2 (2026-06-24).*
*Engine and experiment: `~/mentat/mentat/trade_lab.py`, `imagine.py`, `nsweep.py`; verification `papers/false-alpha/{verify,power}.py` (Mentat repo, github.com/0103-parv/mentat). Every number is produced by `python3 -m mentat.nsweep` and reproducible from the repo. This draft has been hardened against an adversarial multi-reviewer + power-curve audit (see §6, §10).*

---

## 0. In plain English (read this first)

Suppose you hand an AI a stock chart and say: *"invent trading strategies."* It is tireless, so it invents ten, then a hundred, then three thousand. You backtest each one — replay it on history and measure how good it would have been. Some look great. The more strategies you try, the better the *best* one looks.

Here is the trap. **If you flip enough coins, one of them comes up heads ten times in a row — and that coin isn't special.** A strategy that looks brilliant on past data might be the trading equivalent of that lucky coin: it fit the noise, not a real pattern. The technical name is *backtest overfitting* or *data snooping*, and there is a known theorem (López de Prado & Bailey's "false strategy theorem") that says the best-looking strategy out of N tries will look good *purely by luck*, and looks better the larger N is.

Now the modern twist: **large language models make N enormous and cheap.** An LLM can propose strategies all day. So the worry isn't academic. If you point an LLM at the market and let it "discover" strategies, do the genuinely profitable ones pile up — or do you just manufacture an ever-growing pile of lucky-coin mirages?

This paper answers that with an experiment. I take a real trading engine that has a deliberately *brutal* test built in — it makes a strategy prove itself out-of-sample, across several different market periods, after paying realistic trading costs, **and** it applies the statistical correction for "you tried N things, so discount the best one accordingly." Then I do something simple but revealing: I **sweep N** — 10, 30, 100, 300, 1,000, 3,000 strategies — using both a dumb random generator and the LLM-style *creative* generator, on three markets:

- a **fake market with a real pattern secretly planted in it** (so I know the right answer is "there's an edge"),
- a **fake market that is pure randomness** (so I know the right answer is "there's nothing"),
- the **real S&P 500** (2016–2024, from the Federal Reserve's data).

The result, in one breath:

1. **The naive way of judging strategies gets fooled more and more as N grows.** On pure-noise data, the best strategy out of N climbs from a Sharpe of ~0.0 to ~0.35 as N goes 10→3,000; on the real S&P 500 it climbs to ~1.0 — a number a person would happily call "a good strategy." Hundreds of strategies look like winners. *None of them are real.*
2. **The brutal gate holds the line at exactly zero, no matter how large N gets.** Across thousands of strategies on the real S&P 500, **zero** survive the full test — at N=10 and at N=3,000 alike. More search did not produce more real edge. It produced more mirages. **A live Claude (Opus 4.8) actually proposing the strategies gives the same zero** — the "LLM" in the title is not a metaphor.
3. **The gate is not just "reject everything."** On the planted-edge market, the same gate *passes* strategies (and finds more as N grows, because the edge is really there). So it can tell a *strong* real edge from fakes — it isn't a blanket "no."
4. **But the gate is strict, and that strictness has an honest cost.** When we plant a *moderate* edge — one a real fund would kill for, a true Sharpe near 1–2 — the gate **also rejects it**. Why? Because once you've searched 1,000 strategies, the bar for "this isn't luck" is itself a Sharpe of ~2.3, so a genuinely-good-but-not-spectacular strategy is *statistically indistinguishable from the best of 1,000 lucky coins.* **This is the deepest point of the paper: scaling the search doesn't just fail to find edge — it raises the bar for proving *any* edge faster than the search finds one.** Moderate real edges become *unprovable at scale.* So we do **not** claim "the S&P has no edge"; we claim "no edge big enough to prove after searching this hard," which is a different and more honest statement.
5. **AI "creativity" makes the problem look worse, not better.** The creative generator (and the live LLM) produce *more* original-looking winners than random search (196 vs 115 "regime-robust" mirages on the real S&P) — but convert exactly **zero** into survivors. Creativity amplifies whatever is there: a strong real edge when it exists (~5× more survivors on the planted market), mirages when it doesn't. **The creativity is in the inventing; the honesty has to come from the gate.**

The one-sentence takeaway: **LLM-scale search manufactures false discoveries, and the multiple-testing correction that stops them simultaneously raises the bar for proving any genuine edge — so on real data the honest answer is zero, not because the market is provably efficient, but because at this search scale a moderate edge is unprovable.** This is a *negative* result by design, and that is the point: it maps where AI-driven strategy search confidently fools you, and where even an honest gate must shrug.

A subtle finding worth flagging even in plain English: on the *real* market, requiring a strategy to work across several time periods was **not enough** on its own — you still find ~115 "robust-looking" mirages, because real market periods resemble each other. It was the *multiple-testing correction* that did the decisive work there. On the adversarial fake-noise market, the cross-period requirement alone already killed everything. You need both, and the multiple-testing correction is the one that always pulls its weight.

---

## Abstract

Large language models can propose and backtest trading strategies at effectively unbounded scale, reviving an old hazard — backtest overfitting — in a new regime where the number of trials N is enormous and cheap. We ask whether scaling LLM-style strategy search accumulates genuine edge or only statistically false discoveries that vanish under proper multiple-testing correction. Using a pure-Python alpha engine with a deliberately brutal verifier (causal next-bar execution, transaction costs, worst-of-regimes out-of-sample scoring, and a deflated-Sharpe multiple-testing haircut; Bailey & López de Prado 2014), we sweep N from 10 to 3,000 across three generators — uniform-random, Boden-operator "creative" synthesis, and a **live LLM proposer (Claude Opus 4.8)** — on four markets: a strong planted edge (positive control), a *realistically small* planted edge (power control), a pure random-walk null, and real S&P 500 data (FRED, 2016–2024). We find: (1) the naive single-holdout best-of-N Sharpe rises monotonically with N on every market, including pure noise (+0.04→+0.34) and real S&P 500 (+0.72→+0.99 annualized), reproducing the false-strategy theorem with a generative search engine, the live LLM included; (2) the deflated worst-regime gate holds survivors at exactly **0** on the real market for all N and all three generators, while *recovering* the strong planted edge (survivors grow with N) — it discriminates, it is not a blanket reject; (3) a **gate power curve** is the central new result: the gate admits an edge only once its true worst-regime Sharpe clears the multiple-testing floor (~2.3 at N=1,000), so a *moderate* real edge (Sharpe ~1–2) is also rejected — scaling the search raises the discovery bar (≈√(2 ln N)) faster than search finds edge, making moderate edges *unprovable at scale*; (4) an ablation shows worst-regime robustness alone is insufficient on real data (it admits 115–196 "robust" mirages that grow with N) and the deflation is load-bearing; (5) we measure search redundancy directly by the mean pairwise return correlation ρ̄ of the strategies — on real data ρ̄≈0 (near-independent), so deflating at N is the *correct* multiple-testing count, not an over-penalty, and the zero is not an over-deflation artifact; (6) creative and LLM search manufacture more original-looking mirages than random but convert zero to survivors, amplifying a real edge ~5× only when one exists. We therefore do **not** claim market efficiency; we claim that LLM-scale search manufactures false discoveries while the only correction that stops them also renders moderate genuine edges unprovable. The contribution is the controlled multi-generator demonstration (live LLM included), the power-curve precision/recall characterization of the anti-overfit gate, and the ρ̄-based effective-trials accounting — all reproducible, with an adversarial verification suite that holds at 17/17.

---

## 1. Introduction and research question

A backtest certifies the past, not the future, and the more strategies you test the more certain it is that the best one is lucky rather than good. Bailey & López de Prado formalize this as the **false-strategy theorem**: under the null of no skill, the expected maximum Sharpe ratio over N independent trials grows like √(2 ln N), so any sufficiently large search "discovers" an impressive-looking strategy with probability approaching one. The classical remedy is to *deflate* the observed Sharpe by exactly this expected best-of-N under the null (the Deflated Sharpe Ratio, DSR).

Large language models change the operative regime of this theorem. They can propose candidate strategies essentially without limit and with superficial novelty, so N — historically bounded by human and compute budgets — becomes large and cheap, and the proposals are *correlated* (drawn from shared structure) rather than independent. Recent systems (e.g. AlphaAgent, KDD 2025; FinGPT; agentic "alpha-mining" pipelines) explicitly use LLMs to generate and screen alphas, and report in-sample or single-holdout improvements. This raises a direct, testable question:

> **When an LLM-style generator proposes and backtests more and more trading strategies, do genuinely profitable strategies accumulate — or only statistically false ones that vanish under proper multiple-testing correction?**

We decompose this into three measurable sub-questions:

- **Q1 (false discovery vs N).** Does the count of naive "winners," and the best naive Sharpe, rise with N as data-snooping theory predicts — and at what rate, given that LLM/creative proposals are correlated, not independent?
- **Q2 (does the gate hold, and what does it cost).** Does a worst-regime, after-cost, deflated out-of-sample gate drive survivors to ≈0 regardless of N on real data — *while still recovering a genuine edge when one is present* (so that "zero survivors" is a discriminating result, not a degenerate one) — and **how strong must an edge be for the gate to see it** (its power/recall)?
- **Q3 (does creativity help).** Does LLM-style "creative" search (novel structures) find any real edge that brute-force random search misses — or only more original-looking false positives?

Our contribution is not a new statistic (the DSR is López de Prado & Bailey's) and not a claim to beat the market. It is an **empirical, three-control demonstration** that LLM-scale generative search manufactures false discoveries exactly as the theorem predicts; a **measurement** of how much correlated creative search actually snoops (the effective number of independent trials); and a clean **ablation** of which gate component is load-bearing on real versus adversarial data. The result is deliberately, mostly negative — a rigorous map of where naive AI-driven alpha search would fool you.

---

## 2. The engine and the gate (what each strategy must survive)

The experiment is built on `trade_lab.py`, a dependency-free alpha-discovery engine. A strategy ("alpha") is an expression in a small S-expression DSL over causal price/volume features (`ret1`, `mom5/10/20`, `vol10/20`, `accel`, `price_ma_gap`, `hl_range`, `volume_z`), combined by unary (`neg, abs, sign, tanh, zscore`) and binary (`add, sub, mul, safe_div, min, max`) operators, depth ≤ 5, size ≤ 40. An expression evaluates causally to a per-bar signal, squashed to a position in [−1, 1].

The **verifier** (the gate) is intentionally adversarial, and is what makes "discovery" mean something:

1. **No look-ahead.** The position formed from information through bar *t*−1 earns bar *t*'s return: `strat[t] = pos[t−1]·ret[t] − cost·|Δpos|`.
2. **Transaction costs.** Every position change pays `cost = 0.0010` per unit turnover, so churny alphas bleed out.
3. **Worst-of-regimes out-of-sample.** The timeline is split into an in-sample segment and several contiguous out-of-sample (OOS) regimes; an alpha is scored by its **worst** OOS regime. One good regime is not enough — it must generalize.
4. **Deflated-Sharpe multiple-testing haircut.** The score is the worst-regime Sharpe minus the expected best-of-N Sharpe under the null for N trials (`expected_max_sharpe_under_null`, the Bailey–López de Prado term, Euler–Mascheroni–weighted Gumbel form). Searching more raises the bar.

An alpha is "verified" only if its annualized, after-cost, worst-regime, deflated OOS Sharpe clears a positive bar (target = 0.50). This is the same gate that produced Mentat's headline honest null — *0 of 12 market facets survived 3,840 deflated OOS hypotheses on real S&P 500* — which this paper turns from a single snapshot into a controlled N-sweep.

**Generators.** Two stand in for "the search engine," deliberately independent of the kernel's adaptive loop so that best-of-N is clean and attributable:
- **`random`** — uniform draws over the full DSL (the brute-force quant baseline; approximately i.i.d.).
- **`creative`** — Boden's three creativity forms made executable as operators (`blend` = combinatorial, `reshape/specialize` = exploratory, `invert/transfer` = transformational; `imagine.py`) applied over a shared substrate of seed ideas and verified baselines, at risk = 0.7 (which composes two operators per idea). Draws are **correlated through the shared substrate** — exactly the structure an LLM "imaginer" produces, which is itself an object of study (Q3, n_eff). The **live LLM imaginer** (`LLMImaginer`, Claude via API) is the same interface and is the pre-registered third arm (§7).

---

## 3. Method: the N-sweep

For each (market, generator) we draw a fixed pool of M = 4,000 alphas, **backtest each exactly once** to obtain three after-cost Sharpe views — a single pooled-OOS holdout (the *naive* metric a practitioner validates on), the worst-of-regimes OOS (the gate's robustness term), and in-sample — and the worst-regime bar count for deflation. Deflation is then applied analytically per N, so no alpha is backtested twice. For each N ∈ {10, 30, 100, 300, 1,000, 3,000} we estimate the *expected* best-of-N curve and counts by averaging over 25 bootstrap subsets of size N drawn from the pool (single pass when N equals the pool). We report:

- **bestOOS** = E[ max naive pooled-OOS Sharpe ] over N — the data-snoop curve (Q1).
- **nOOS>0 / nOOS>1** = count of naive winners above 0 and above 1.0 annualized.
- **robust** = count clearing worst-regime + cost but **no** deflation (ablation: isolates generalization vs multiple-testing).
- **survivors** = count clearing the **full** deflated gate at n_trials = N (Q2).
- **novelty** = mean pairwise token-Jaccard distance among naive winners (Q3).
- **n_eff** = the number of *independent* trials whose i.i.d. expected-max equals the realized bestOOS — correlated draws give n_eff ≪ N (Q1/Q3; interpreted on the null markets).

Three markets form the experimental matrix: **planted** (synthetic universe with a lag-1 mean-reversion edge, same sign in every regime → a real edge *should* survive), **noise** (pure random walk, same regime structure, no edge → naive winners *should* rise, gate *should* stay 0), and **real:fred_SP500** (S&P 500 daily, 2016-06 to 2024, ~2,600 bars, close-only so the range/volume features go dark).

All randomness is seeded; the full per-N table and config are written to `nsweep_results.json`.

---

## 4. Results

Condensed from the full sweep (pool = 4,000; bootstrap = 25). Full table in the JSON artifact.

### 4.1 Q1 — the naive metric is fooled, and worse as N grows

The expected best-of-N pooled-OOS holdout Sharpe rises monotonically with N on **every** market, including pure noise:

| market | gen | N=10 | N=100 | N=1000 | N=3000 | nOOS>0 @max N |
|---|---|---:|---:|---:|---:|---:|
| noise | random | +0.04 | +0.20 | +0.30 | +0.34 | 376 |
| noise | creative | +0.01 | +0.13 | +0.26 | +0.29 | 275 |
| real S&P 500 | random | +0.72 | +0.98 | +0.99 | — | 319 (@1000) |
| real S&P 500 | creative | +0.53 | +0.81 | +0.89 | +0.96 | 658 |

On the real S&P 500, scaling the search surfaces a best strategy with an annualized **OOS** holdout Sharpe near **1.0** — a number most practitioners would accept — and hundreds of "winners" (658 with positive OOS Sharpe for creative at N=3,000). On pure noise, where the ground truth is *nothing*, the best-of-N still climbs to +0.34. This is the false-strategy theorem reproduced with a generative search engine: **naive validation, even out-of-sample, is fooled by scale.**

**How redundant is the search?** We measure it directly: the mean pairwise correlation ρ̄ of the strategies' out-of-sample return series, giving an effective number of independent trials N_eff = N/(1+(N−1)ρ̄). On the real market ρ̄ is tiny — **+0.029 (random), −0.050 (creative), +0.007 (live LLM)** — i.e. the proposals are essentially *independent* in return space. (An earlier draft reported ρ̄ via inverting the best-of-N envelope, which is numerically unstable; the correlation estimate is the correct, stable measure and overturns the earlier "creative snoops more" claim — creative is, if anything, *more* diverse.) This matters for the gate: because the trials are near-independent, the honest multiple-testing count really is ≈N, so **deflating at N is the correct correction, not an over-penalty** (we verify this below). Correlated or not, the count of naive mirages still grows with N.

### 4.2 Q2 — the deflated gate holds at zero on real data, and recovers a real edge

| market | gen | survivors @ N=10 | @100 | @1000 | @3000 |
|---|---|---:|---:|---:|---:|
| **real S&P 500** | random | 0.00 | 0.00 | 0.00 | — |
| **real S&P 500** | creative | 0.00 | 0.00 | 0.00 | **0.00** |
| noise | random | 0.00 | 0.00 | 0.00 | 0.00 |
| noise | creative | 0.00 | 0.00 | 0.00 | 0.00 |
| **planted** (real edge) | random | 0.00 | 1.92 | 11.2 | **206 robust → 31.4 survive** |
| **planted** (real edge) | creative | 0.68 | 7.08 | 58.3 | **559 robust → 154.4 survive** |

Across thousands of strategies on the real S&P 500, **survivors = 0 at every N**, for both generators (and the live LLM, §4.4). Scaling the search 100×–300× added zero real discoveries. Critically, this is **not** a degenerate "the gate rejects everything": on the strong-planted market the same gate *passes* strategies, and passes **more** as N grows (survivors 0.0 → 31 for random, 0.7 → 154 for creative) because the edge is genuinely there. But how strong must an edge be to pass? That is the power question, and §4.5 shows the answer is "very strong" — which reframes the whole result. **The gate separates a strong real edge from spurious ones; whether it can see a moderate one is the subject of §4.5.**

### 4.3 Q3 — the ablation: which tightener does the work, and the over-deflation check

The `robust` column (worst-regime + cost, **no** deflation) reveals a non-obvious asymmetry:

| market | gen | robust @10 | @100 | @1000 | @3000 | survivors @max N |
|---|---|---:|---:|---:|---:|---:|
| noise | random | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| real S&P 500 | random | 1.2 | 11.4 | 114.7 | — | 0.00 |
| real S&P 500 | creative | 0.9 | 7.9 | 67.5 | **196.4** | **0.00** |

- On the **adversarial noise** market, the worst-regime requirement *alone* kills the snoop (robust = 0 everywhere): a pure-noise alpha cannot be simultaneously positive across regimes engineered to differ in drift and volatility.
- On the **real** market, the worst-regime requirement is **not enough** — because real 2016–2024 sub-periods resemble each other, an alpha can be luckily positive in all of them, so `robust` *grows with N* to 115 (random, @N=1,000) and 196 (creative, @N=3,000) "regime-robust" mirages. **It is the multiple-testing deflation that collapses these to exactly 0.** On real data the deflation is the load-bearing component.

This pre-empts the "you calibrated the haircut to N, so survivors=0 is tautological" objection three ways. (i) The *same* haircut does **not** zero out the strong planted edge (§4.2) — opposite outcomes from the same correction prove it discriminates. (ii) Because the search is near-independent (ρ̄≈0, §4.1), the effective trial count is ≈N, so deflating at N is the *correct* multiple-testing count, not an over-penalty; and computing the gate with deflation at the (smaller) effective N instead of N leaves survivors at **0** on real for every N (`survivors_neff` column in the artifact). (iii) A direct margin check: the single best worst-regime Sharpe across all **5,994** tradeable real-S&P alphas is **+0.847** annualized; even at a deliberately generous effective trial count, the multiple-testing floor exceeds it (the deflated value stays negative). Zero survivors is **not** an over-deflation artifact — and §4.5 shows it is also not "the gate rejects everything," because a sufficiently strong edge *does* pass.

**On creativity (and the LLM):** creative synthesis and the live LLM manufacture *more* apparent discovery than random search — more naive winners (658 vs 319 at N=3,000) and nearly 2× the regime-robust mirages on real S&P (196 vs 115) — yet convert **zero** of them into survivors. Where a strong real edge exists (planted), the same creativity amplifies it ~5× (154 vs 31 survivors at N=3,000). Per-winner structural novelty is similar across generators (~0.87), and contrary to our pre-registered guess the creative/LLM proposals are *not* more correlated than random (§4.1, §4.4). The honest reading: **creativity amplifies whatever is present — a strong real edge when it exists, mirages when it doesn't — and the gate, not the generator, is what tells them apart.** Creative/LLM search finds more *original-looking* candidates, not more *survivable* ones.

### 4.4 The live-LLM arm — Claude Opus 4.8 actually proposes the strategies

The arms above use random and offline-creative generators. We also ran a **live LLM proposer**: Claude Opus 4.8 imagines alpha expressions in batches of 16, cold from the problem brief (fresh memory, no elite feedback — the LLM's prior, not an adaptive loop), capped at a pool of 300 for cost and cached for reproducibility. The gate, markets, sweep, and metrics are held fixed.

| market | N=10 | N=30 | N=100 | survivors (all N) | ρ̄ |
|---|---:|---:|---:|---:|---:|
| real S&P 500 (bestOOS) | +0.43 | +0.70 | +0.79 | **0.00** | +0.007 |
| planted (bestOOS / survivors@N=10) | +2.89 / **0.92** | +3.62 | +4.11 | grows with N | +0.015 |

Pre-registered hypotheses, scored:
- **H1 — LLM bestOOS rises with N:** ✓ confirmed (+0.43→+0.79 on real S&P).
- **H2 — LLM proposals are *more* correlated than random (lower N_eff):** ✗ **refuted.** ρ̄(LLM)=+0.007 is *no higher* than random (+0.029) — the LLM's returns are as near-independent as brute force. (We report the refutation as pre-registered; the LLM does produce fewer *distinct valid* expressions — ~73 vs ~97 per 100 — i.e. more textual repetition, but that does not translate into correlated *returns*.)
- **H3 — LLM survivors = 0 on real at all N:** ✓ confirmed.
- **H4 — LLM recovers a strong planted edge at smaller N than random:** ✓ confirmed (survivors 0.92 at N=10 vs random's 0.00; on par with offline-creative).

So a *real LLM* reproduces the headline exactly: it manufactures plausible candidates whose best-of-N naive Sharpe climbs, the gate admits none on real data, and it finds a strong planted edge faster than brute force. The one surprise is the honest H2 refutation — LLM "creativity" here is diverse, not redundant. (The LLM arm reaches N≤100 by design; extending it to N=3,000 is future work, §7.)

### 4.5 The gate's power curve — and why "zero" does not mean "efficient"

The sharpest objection (raised independently by an adversarial statistics reviewer and by the system's own reasoning core acting as critic): a gate that returns 0 on real data is only interesting if it *would* have returned >0 for a realistic edge. §4.2 shows it passes a *strong* planted edge — but how strong must an edge be? We sweep the planted edge magnitude and, at N=1,000, record the best realized worst-regime Sharpe the search finds and whether the gate admits anything (`power.py`):

| planted edge strength | best worst-regime Sharpe | best naive OOS | gate survivors |
|---:|---:|---:|---:|
| 0.00 (noise) | −0.07 | +0.22 | 0 |
| 0.06 (≈ a realistic small edge) | +0.17 | +0.41 | 0 |
| 0.15 | +0.48 | +1.34 | 0 |
| 0.25 | **+1.94** | +2.49 | **0** |
| 0.40 (strong) | +4.47 | +4.67 | 61 |

The gate admits nothing until the true worst-regime Sharpe is **between +1.94 and +4.47** — an edge with a genuine worst-regime Sharpe of **+1.94 (a strategy any fund would covet) still yields zero survivors.** This is not a flaw; it is the multiple-testing floor made visible. After searching N=1,000 strategies, the expected best-of-N under the null is a Sharpe of ~2.3, so to *claim* a discovery you must clear ~2.3+target — a moderate real edge simply cannot be distinguished from the best of 1,000 lucky draws. The `small_planted` control (a realistic small edge, naive OOS ≈ +0.5) is invisible to the gate at every N — exactly like the real S&P.

**This is the paper's deepest and most honest result.** The deflation bar grows like √(2 ln N): **scaling the search raises the threshold for proving any edge faster than the search discovers one.** Consequences:
1. We **cannot and do not** claim the S&P 500 has no exploitable edge. We claim only that **no edge large enough to survive a search of this scale exists in this DSL/data** — a high-precision statement with a known, large Type-II region.
2. The contribution is therefore a **precision/recall characterization of anti-overfit gating**: this gate has (empirically) ~zero false-discovery rate across noise, small-edge, real, DJIA, and NASDAQ controls, at the cost of failing to detect edges below a worst-regime Sharpe of ≈2–3 at N=1,000. That tradeoff *itself* tightens as N grows — the engine of the whole phenomenon.
3. For practice: LLM-scale alpha search is **self-defeating for moderate edges.** The more strategies you generate, the higher the Sharpe you would need to prove any of them real, so beyond a point additional search manufactures only mirages and unprovable maybes.

---

## 5. Related work

- **Deflated Sharpe / false-strategy theorem.** Bailey & López de Prado, *The Deflated Sharpe Ratio* (2014) and *The Probability of Backtest Overfitting* (2016); López de Prado, *Advances in Financial Machine Learning* (2018). The DSR haircut is theirs; we apply it inside a multi-generator N-sweep with controls, and characterize its *power* (§4.5), which the original work does not.
- **Data-snooping tests we should be compared to (and partly do not yet run).** Sullivan, Timmermann & White (1999), "Data-Snooping, Technical Trading Rule Performance, and the Bootstrap" — *almost exactly our setup* (a rule universe × snooping correction on an index), and the closest prior art; White (2000) Reality Check; Hansen (2005) Superior Predictive Ability; Romano & Wolf (2005) stepwise multiple testing; Harvey, Liu & Zhu (2016) and Harvey & Liu, "Backtesting" (2015) and "Lucky Factors" (2021) on the factor zoo and the t>3 threshold; Barras, Scaillet & Wermers (2010) on FDR in fund returns. **Honest gap:** our deflation is the parametric DSR; a distribution-free White/Hansen block-bootstrap is the natural complement and is *planned, not yet run* (§7) — we flag this rather than imply the bootstrap was done.
- **LLM / agentic alpha mining.** AlphaAgent (KDD 2025) and related LLM alpha-mining pipelines; Lopez-Lira & Tang (2023), "Can ChatGPT Forecast Stock Price Movements"; FinGPT (2306.06031), BloombergGPT (2303.17564). These typically report in-sample or single-holdout gains; we provide the adversarial-gate, N-sweep, power-curve counterpoint with a live LLM proposer.
- **Verified LLM discovery & quality-diversity.** FunSearch (Romera-Paredes et al., *Nature* 2023) and AlphaEvolve (verification-gated program search); MAP-Elites (Mouret & Clune 2015) and novelty search (Lehman & Stanley 2011) underlie the creative generator. Boden, *The Creative Mind*, supplies the operator taxonomy.
- **Anti-overfit machinery in this engine** (walk-forward, worst-regime, deflation) follows the above; the engine is the author's prior system (Mentat, `PAPER.md`).

The positioning: prior LLM-alpha work asks *"can an LLM find alphas?"* and answers with favorable in-sample/holdout numbers. We ask *"does scaling LLM search find real alpha or manufacture false discoveries — and what is the recall cost of the correction that stops them?"* and answer with a controlled negative on real data, a positive control proving the gate discriminates, and a power curve quantifying what it misses.

---

## 6. Limitations (honest)

- **Low recall is the headline caveat, not a footnote (§4.5).** The gate's zero on real data is a *precision* statement; its power curve shows it misses any edge with a true worst-regime Sharpe below ≈2–3 at N=1,000. So "0 survivors" must always be read as "no edge provable at this search scale," never as "no edge exists." This is intrinsic to multiple-testing at scale, not a bug, but it bounds every claim in the paper.
- **The worst-regime statistic is not the statistic the DSR was derived for.** Bailey–López de Prado's expected-max-under-null is for a single in-sample Sharpe over N trials; we apply the haircut to the *minimum across regimes*, whose null distribution is not standard-normal. The worst-regime operator already tightens the bar, so stacking the standard DSR on top is *conservative but heuristic* — it is no longer the named theorem. A distribution-free White/Hansen block-bootstrap of the worst-regime best-of-N statistic is the correct closure and is planned (§7), not yet run.
- **The DSL and data are modest.** Close-only FRED series disable the range/volume features; the feature set is small and daily; no cross-sectional, intraday, or alternative data. A richer DSL might surface a survivor — the method (N-sweep + ablation + power curve), not the specific null, is the transferable result.
- **Reported counts are finite-pool quantities, not independent-per-N draws.** `bestOOS` and the winner/robust/survivor counts are bootstrap means over nested subsets of one fixed pool (≤4,000 per market-generator); for N near the pool there is essentially one sample. They estimate within-pool expectations, not an independent accumulation across N — the monotone "rise with N" is a property of E[best-of-N], reported as such.
- **Single seed per (market, generator); √252 annualization.** Each pool uses one seed, so curves are single realizations without seed-variance bands (the verify.py controls give cross-condition robustness instead). Daily Sharpes are √252-annualized with no serial-correlation adjustment, which can overstate "annual Sharpe ~1.0" rhetoric.
- **Synthetic controls are stylized.** The strong planted edge is high-frequency mean reversion (deliberately easy, to verify the gate *can* pass); the noise market's adversarial regimes make worst-regime alone sufficient there, which is *why* the real-market ablation (where it is insufficient) is the informative case. The `small_planted` and power controls (§4.5) address "is the null rigged easy?" directly.
- **Backtests certify the past.** Even a survivor would be provisional; markets are adversarial and non-stationary.

---

## 7. Future work

The live-LLM arm (§4.4) is done; what remains:
- **Extend the LLM arm to N=3,000** (it currently reaches N≤100 at pool 300). The cached-pool mechanism makes this a cost question, not an engineering one.
- **Distribution-free multiple testing.** Replace/augment the parametric DSR with a stationary block-bootstrap White Reality Check / Hansen SPA on the worst-regime best-of-N statistic. This closes the "worst-regime ≠ the named theorem" gap (§6) and would make the zero-survivor claim distribution-free.
- **Power curve vs N.** §4.5's power curve is at N=1,000; sweeping it across N would directly trace how the detectable-edge threshold rises with search scale — the paper's central mechanism, turned into a single figure.
- **Richer DSL / data.** OHLCV with live volume and intraday bars, and a larger operator set, to test whether the zero is a property of the gate or of the impoverished signal space.

---

## 8. Reproducibility

```
cd ~/mentat
python3 -m mentat.nsweep                                          # planted + small_planted + noise
python3 -m mentat.nsweep --pool 4000 --data data/fred_SP500.csv \
                         --out papers/false-alpha/nsweep_results.json
python3 papers/false-alpha/verify.py                             # 17-check adversarial suite
python3 papers/false-alpha/power.py                              # the gate power curve (§4.5)
# live-LLM arm (needs anthropic + ANTHROPIC_API_KEY; pool capped at 300, cached after first run):
python3 -m mentat.nsweep --pool 300 --llm --data data/fred_SP500.csv \
                         --out papers/false-alpha/nsweep_results_llm.json
```

Offline arms: no dependencies, no API key, deterministic (CRC-seeded; two runs byte-identical). The engine is covered by the repo test suite (`python3 -m tests.test_core`, 74 tests). The deflated-Sharpe term is `trade_lab.expected_max_sharpe_under_null`; the gate is `AlphaProblem.verify`; the creative operators are in `imagine.py`; effective-trials is `nsweep.effective_trials`. Raw results: `papers/false-alpha/nsweep_results.json` (+ `…_llm.json`). The LLM-proposed pools are cached at `papers/false-alpha/llm_cache_*.json` so the live arm reproduces without re-billing the API.

---

## 9. Authorship and contributions

**Author:** Parv Mehndiratta — conceived the research question, designed the N-sweep and control structure, specified and built the experiment (`nsweep.py`) on the author's prior alpha engine (`trade_lab.py`, `imagine.py`), ran the analysis, and wrote the paper.

**Tools disclosed:** Implementation and drafting were done with AI assistance (Claude, Anthropic) used as a coding and writing aid under the author's direction; the underlying Mentat system uses a frozen LLM as a reasoning core, as disclosed in the Mentat paper. No undisclosed co-authors. (A previously referenced CRRA/Heston collaboration is *not* part of this work and is not claimed here pending independent verification.)

**Suggested venues** (tiered, no pay-to-publish HS journals): a NeurIPS/ICML/ICLR workshop on ML-for-finance or evaluation/robustness; ACM ICAIF (student-accessible track); arXiv (cs.LG, with a q-fin.ST cross-list via an endorser); SSRN for the finance audience. Frame as a workshop/preprint, not a journal article, at this stage.

---

## 10. Verification audit — how this draft was hardened

In keeping with the project's discipline (*prefer an honest negative to a confident guess*), draft v0.2 was adversarially stress-tested before release, by the same machinery the paper studies: three independent Claude review agents (statistics/methodology, finance-ML positioning, reproducibility/integrity), the system's live reasoning core acting as a skeptical critic, an executable 17-check suite (`verify.py`), and a power curve (`power.py`). What they caught, and what changed:

- **"The effective-trials number is numerically unstable."** True — the original n_eff inverted the best-of-N envelope (logarithmic, so it swung orders of magnitude). Replaced with a correlation-based N_eff = N/(1+(N−1)ρ̄). The fix *overturned a prior claim*: ρ̄≈0 shows creative/LLM search is **not** more correlated than random, so "creativity snoops more" was deleted, not defended.
- **"Survivors = 0 is tautological / you over-deflate at N."** Answered three ways (§4.3): ρ̄≈0 ⇒ deflating at N is the *correct* count; a `survivors_neff` column deflating at the smaller effective N still gives 0; and the planted edge survives the *same* haircut.
- **"The positive control is too easy; the null may be rigged."** This was the decisive critique (raised by both the statistics reviewer and the reasoning-core critic). It produced the paper's now-central result — the **power curve (§4.5)** and the `small_planted` control — which reframed the contribution from "no edge in the S&P" (an overclaim) to "moderate edges are unprovable at this search scale" (precision/recall).
- **"The title says LLM but no LLM was run."** Fixed by running the **live Claude-Opus arm** (§4.4); 3 of 4 pre-registered hypotheses held and **H2 was refuted and reported** as such.
- **Missing prior art** (Sullivan–Timmermann–White, White Reality Check, Hansen SPA, Romano–Wolf, Barras–Scaillet–Wermers, Lopez-Lira–Tang) was added (§5), with the distribution-free bootstrap honestly marked *not yet run*.
- A genuine **bug** (an unimported symbol that crashed the live-LLM arm) was surfaced by the verification run and fixed.

The reproducibility audit confirmed every number in §0/§4/Appendix A matches the artifact, two runs are byte-identical, and the authorship statement is clean. Residual honest gaps are listed in §6–§7. The point of this section is not to claim perfection but to show the result survived a serious attempt to break it.

---

## Appendix A — key numbers at a glance

- **Real S&P 500**, all 5,994 tradeable alphas (random + creative): best worst-regime annualized Sharpe = **+0.847**; best naive pooled-OOS = **+0.999**; **survivors = 0 at every N**, all three generators (random, creative, live LLM).
- **Deflation haircut** on real S&P at n_trials = {1000, 3000} = {2.31, 2.52} ann. → best deflated = {−1.46, −1.67}. Even at the smallest defensible *effective* trial count (~34, random's N_eff at N=1,000), the haircut (~1.5) still exceeds +0.847 → deflated < 0 → **0 survivors is not an over-deflation artifact.**
- **Search redundancy** ρ̄ on real S&P: random **+0.029**, creative **−0.050**, live LLM **+0.007** — near-independent; so deflating at N is the correct multiple-testing count.
- **Gate power curve** (N=1,000): admits 0 survivors until the true worst-regime Sharpe exceeds ~+2 (edge giving Sharpe **+1.94 → 0** survivors; only the strong edge at **+4.47 → 61**). A realistically small edge (`small_planted`, naive OOS ≈ +0.5) is invisible at every N — like the real S&P. The discovery bar grows ≈√(2 ln N).
- **Live LLM (Claude Opus 4.8):** H1 ✓ (bestOOS +0.43→+0.79 on real), H2 ✗ refuted (ρ̄=+0.007, not more correlated than random), H3 ✓ (0 survivors on real), H4 ✓ (recovers strong planted edge faster than random).
- **Strong planted control:** survivors grow with N (creative 0.7 → **154** at N=3,000) — the gate passes a strong real edge.
- **Creativity/LLM on real S&P:** **~2× the regime-robust mirages** of random (196 vs 115), **0** survivors regardless.
- **Adversarial verification:** `verify.py` → **17 PASS / 0 FAIL** (cost∈{0,…,0.002}, target∈{0,0.25,0.5}, 2/3/5 regimes, DJIA + NASDAQ all 0 survivors; independent `curriculum.study` agrees 0/6 verified facets; positive control passes the real `AlphaProblem.verify`, engine score +1.06).
