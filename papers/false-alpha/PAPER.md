# More Strategies, Same Zero: Does LLM-Scale Alpha Search Discover Edge or Manufacture False Discoveries?

**A controlled N-sweep test of the false-strategy theorem with a live LLM proposer — and why scaling the search raises the discovery bar faster than it finds edge**

*Parv Mehndiratta. Working paper, draft v0.4 (2026-06-25).*
*Engine: `~/mentat/mentat/{trade_lab,nsweep,panel_lab,imagine}.py`. Experiments + verification: `papers/false-alpha/{verify,power,bootstrap,theory,corrected_deflation,seed_variance,envelope_departure,panel_sweep,independent_markets,task5_llm,fetch_*,plot_svg}.py` (Mentat repo, github.com/0103-parv/mentat). Every number is produced by a committed script and written to a JSON artifact; runs are CRC-seeded and deterministic (use `python3.14`). v0.3 added, against a five-task reviewer brief: a distribution-free bootstrap (§4.6), a cross-sectional equity panel (§4.7), independent real markets (§4.8), a 2-D power surface (§4.5), the live-LLM arm to N=300 (§4.4). v0.4 adds the math: the derived worst-of-regimes deflation and robustness-dividend identity (§4.9), seed-variance bands (§6), two cautionary effective-N negatives (§4.9), 21 math/invariant unit tests, and dependency-free figures. See §10 for the audit trail.*

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

Large language models can propose and backtest trading strategies at effectively unbounded scale, reviving an old hazard — backtest overfitting — in a new regime where the number of trials N is enormous and cheap. We ask whether scaling LLM-style strategy search accumulates genuine edge or only statistically false discoveries that vanish under proper multiple-testing correction. Using a pure-Python alpha engine with a deliberately brutal verifier (causal next-bar execution, transaction costs, worst-of-regimes out-of-sample scoring, and a deflated-Sharpe multiple-testing haircut; Bailey & López de Prado 2014), we sweep N from 10 to 3,000 across three generators — uniform-random, Boden-operator "creative" synthesis, and a **live LLM proposer (Claude Opus 4.8)** — on four markets: a strong planted edge (positive control), a *realistically small* planted edge (power control), a pure random-walk null, and real S&P 500 data (FRED, 2016–2024). We find: (1) the naive single-holdout best-of-N Sharpe rises monotonically with N on every market, including pure noise (+0.04→+0.34) and real S&P 500 (+0.72→+0.99 annualized), reproducing the false-strategy theorem with a generative search engine, the live LLM included; (2) the deflated worst-regime gate holds survivors at exactly **0** on the real market for all N and all three generators, while *recovering* the strong planted edge (survivors grow with N) — it discriminates, it is not a blanket reject; (3) a **gate power surface** — our central characterization (and the *empirical instantiation*, across generator types and with calibrated controls, of Bailey–López de Prado's expected-max-of-N result, not a new theorem): the gate admits an edge only once its true worst-regime Sharpe clears the multiple-testing floor (~2.3 at N=1,000), so a *moderate* real edge (Sharpe ~1–2) is also rejected — scaling the search raises the discovery bar (≈√(2 ln N)) faster than search finds edge, making moderate edges *unprovable at scale*; (4) an ablation shows worst-regime robustness alone is insufficient on real data (it admits 115–196 "robust" mirages that grow with N) and the deflation is load-bearing; (5) the standard deflation is in fact *over-conservative* for the worst-of-regimes statistic (the single-Sharpe DSR over-deflates it ~2.4×, §4.9), yet the real-market zero survives the corrected, much weaker bar — so the conclusion is not an over-deflation artifact, and the assumption-free bootstrap independently agrees; (6) creative and LLM search manufacture more original-looking mirages than random but convert zero to survivors, amplifying a real edge ~5× only when one exists. We therefore do **not** claim market efficiency; we claim that LLM-scale search manufactures false discoveries while the only correction that stops them also renders moderate genuine edges unprovable. The result generalizes: it holds under a distribution-free block-bootstrap test (White/Romano–Wolf/Hansen), on a real cross-sectional equity panel (range/volume features active), and across three microstructurally-independent real markets (FX, gold, crypto) — **seven real markets, zero survivors at every N** — and the live LLM, extended to N=300, reproduces it. We also derive the **worst-of-regimes deflation** the gate actually needs — the standard single-Sharpe DSR over-deflates the min-over-regimes statistic by ~2.4× — and show the real-market zero is robust even to that much weaker, correct bar; this yields a unifying **"robustness dividend"** (requiring worst-of-k independent regimes ≈ deflating a thousand-strategy search to ~7), which collapses precisely when regimes correlate, explaining why explicit deflation is load-bearing on real data. We report two cautionary negatives in the same spirit: two analytic effective-trials shortcuts (a genomics participation-ratio import; an envelope-inversion) both fail, leaving the block bootstrap as the necessary arbiter. The contribution is the controlled multi-generator demonstration (live LLM included), the power-surface precision/recall characterization, the **derived worst-of-regimes deflation and robustness-dividend identity**, and the distribution-free confirmation — all reproducible, with a verification suite at 20/20 and 21 math/invariant unit tests.

---

## 1. Introduction and research question

A backtest certifies the past, not the future, and the more strategies you test the more certain it is that the best one is lucky rather than good. Bailey & López de Prado formalize this as the **false-strategy theorem**: under the null of no skill, the expected maximum Sharpe ratio over N independent trials grows like √(2 ln N), so any sufficiently large search "discovers" an impressive-looking strategy with probability approaching one. The classical remedy is to *deflate* the observed Sharpe by exactly this expected best-of-N under the null (the Deflated Sharpe Ratio, DSR).

Large language models change the operative regime of this theorem. They can propose candidate strategies essentially without limit and with superficial novelty, so N — historically bounded by human and compute budgets — becomes large and cheap, and the proposals are *correlated* (drawn from shared structure) rather than independent. Recent systems (e.g. AlphaAgent, KDD 2025; FinGPT; agentic "alpha-mining" pipelines) explicitly use LLMs to generate and screen alphas, and report in-sample or single-holdout improvements. This raises a direct, testable question:

> **When an LLM-style generator proposes and backtests more and more trading strategies, do genuinely profitable strategies accumulate — or only statistically false ones that vanish under proper multiple-testing correction?**

We decompose this into three measurable sub-questions:

- **Q1 (false discovery vs N).** Does the count of naive "winners," and the best naive Sharpe, rise with N as data-snooping theory predicts — and at what rate, given that LLM/creative proposals are correlated, not independent?
- **Q2 (does the gate hold, and what does it cost).** Does a worst-regime, after-cost, deflated out-of-sample gate drive survivors to ≈0 regardless of N on real data — *while still recovering a genuine edge when one is present* (so that "zero survivors" is a discriminating result, not a degenerate one) — and **how strong must an edge be for the gate to see it** (its power/recall)?
- **Q3 (does creativity help).** Does LLM-style "creative" search (novel structures) find any real edge that brute-force random search misses — or only more original-looking false positives?

**Contributions (and honest scope).** We do not claim a new statistic — the deflated Sharpe is López de Prado & Bailey's, the Reality Check is White's, and the "LLM edge evaporates" conclusion is already peer-reviewed (FINSABER, KDD'26; §5). Our contributions are:
1. A **derived worst-of-regimes deflation** (§4.9): the gate scores the *minimum across k regimes*, but the standard DSR is the expected max of N *single* Sharpes — the wrong null. We derive and Monte-Carlo-validate the correct envelope E[maxₙ minₖ Z] and show the standard DSR **over-deflates by ~2.4×**; the real-market zero survives the corrected, far-weaker bar. To our knowledge, no prior work deflates a min-over-regimes best-of-N statistic.
2. A **robustness-dividend identity** (§4.9): worst-of-k *independent* regimes ≈ a single-Sharpe search over only N′≈7 strategies — robustness *is* an implicit multiple-testing correction, which collapses as regimes correlate, explaining (§4.3) why explicit deflation is load-bearing on real data and not on the adversarial null.
3. A **controlled, multi-generator, multi-market evaluation protocol** — random vs evolutionary-creative vs a **live LLM** through one fixed gate; four planted/noise calibration controls; **seven real markets** (incl. a cross-sectional panel, FX, gold, crypto); a 2-D **power surface** (the empirical instantiation of the BLdP threshold) showing moderate edges become unprovable as N grows; and a distribution-free bootstrap that agrees everywhere.
4. **Three reported negatives** in the project's "report what doesn't work" discipline: a refuted pre-registered hypothesis (H2), and two analytic effective-N shortcuts (a genomics participation-ratio import; an envelope-inversion) that *manufacture false discoveries* and are corrected by the bootstrap — cross-disciplinary imports that look right and aren't.

The result is deliberately, mostly negative — a rigorous, reproducible map of where AI-driven alpha search fools you, and of the precise statistical price of not being fooled.

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

**How redundant is the search?** The *mean* pairwise correlation ρ̄ of the strategies' OOS returns is tiny on the real market — **+0.029 (random), −0.050 (creative), +0.007 (live LLM)** — so in mean terms the proposals look near-independent. But "near-independent in mean ρ̄" turns out **not** to pin down the right multiple-testing count: the mean-squared correlation ⟨ρ²⟩ ≈ 0.2 tells a different story, and §4.9 shows that *summarizing the correlation structure with any single analytic effective-N is unreliable here* (two shortcuts fail). The honest accounting is: the standard deflation at N is in fact **over-conservative** for our worst-of-regimes statistic (§4.9 quantifies it at ~2.4×), but the real-market zero survives even the corrected, much weaker bar — so the over-deflation is real yet not load-bearing for the conclusion. What is unambiguous and assumption-free is the block bootstrap (§4.6). Correlated or not, the count of naive mirages still grows with N.

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

This pre-empts the "you calibrated the haircut to N, so survivors=0 is tautological" objection three ways. (i) The *same* haircut does **not** zero out the strong planted edge (§4.2) — opposite outcomes from the same correction prove it discriminates. (ii) The objection is in fact *backwards*: §4.9 shows the standard DSR is **over**-deflating the worst-of-regimes statistic by ~2.4×, so if anything the bar is too harsh, not too lenient — and re-running with the *corrected*, far-weaker worst-of-k bar **still leaves 0 survivors on real** (best deflated rises only to ≈ −0.3). (iii) The assumption-free block bootstrap (§4.6), which calibrates the null directly from the data with no haircut at all, *also* finds 0. Zero survivors is **not** an over-deflation artifact — and §4.5 shows it is also not "the gate rejects everything," because a sufficiently strong edge *does* pass.

**On creativity (and the LLM):** creative synthesis and the live LLM manufacture *more* apparent discovery than random search — more naive winners (658 vs 319 at N=3,000) and nearly 2× the regime-robust mirages on real S&P (196 vs 115) — yet convert **zero** of them into survivors. Where a strong real edge exists (planted), the same creativity amplifies it ~5× (154 vs 31 survivors at N=3,000). Per-winner structural novelty is similar across generators (~0.87), and contrary to our pre-registered guess the creative/LLM proposals are *not* more correlated than random (§4.1, §4.4). The honest reading: **creativity amplifies whatever is present — a strong real edge when it exists, mirages when it doesn't — and the gate, not the generator, is what tells them apart.** Creative/LLM search finds more *original-looking* candidates, not more *survivable* ones.

### 4.4 The live-LLM arm — Claude Opus 4.8 actually proposes the strategies

The arms above use random and offline-creative generators. We also ran a **live LLM proposer**: Claude Opus 4.8 imagines alpha expressions in batches of 16, cold from the problem brief (fresh memory, no elite feedback — the LLM's prior, not an adaptive loop), cached for reproducibility. On real S&P 500 we drew a 1,000-strategy pool so the LLM itself reaches **N=300** (Task 5; the offline cap remains 300 elsewhere for cost). The gate, markets, sweep, and metrics are held fixed.

| real S&P 500 | N=10 | N=30 | N=100 | N=300 | survivors (all N) | ρ̄ |
|---|---:|---:|---:|---:|---:|---:|
| LLM bestOOS | +0.48 | +0.71 | +0.78 | +0.80 | **0.00** | +0.007 |
| LLM distinct alphas | 10 | 27 | 71 | **160** | — | — |

Pre-registered hypotheses, scored (at scale):
- **H1 — LLM bestOOS rises with N:** ✓ confirmed (+0.48→+0.80 to N=300).
- **H2 — LLM proposals are *more* correlated than random (lower N_eff):** ✗ **refuted, at scale.** ρ̄(LLM)=+0.007 is *no higher* than random (+0.029) — the LLM's returns are as near-independent as brute force.
- **H3 — LLM survivors = 0 on real at all N:** ✓ confirmed to N=300, with **0 offline-creative fallback batches** (the pool is 100% live-LLM).
- **H4 — LLM recovers a strong planted edge at smaller N than random:** ✓ confirmed (survivors 0.92 at N=10 vs random's 0.00).

A *real LLM* reproduces the headline exactly: best-of-N naive Sharpe climbs (+0.48→+0.80), the gate admits none on real data, and it finds a strong planted edge faster than brute force. Two honest surprises: (i) the pre-registered **H2 is refuted** — LLM proposals are diverse in *return space*, not redundant; but (ii) a new finding cuts the other way — the LLM's **structural** diversity saturates: a 1,000-draw pool yields only **160 distinct** valid expressions (vs ~280 for random), so the LLM repeats *ideas* even though their realized returns decorrelate. Scaling an LLM proposer therefore buys less new search than scaling random generation — a diversity ceiling that bounds how far the title's "LLM-scale" can actually go. (Pushing to N=3,000 would require ~10× the API budget; the cached-pool mechanism makes it a cost, not an engineering, question.)

### 4.5 The gate's power curve — and why "zero" does not mean "efficient"

The sharpest objection (raised independently by an adversarial statistics reviewer and by the system's own reasoning core acting as critic): a gate that returns 0 on real data is only interesting if it *would* have returned >0 for a realistic edge. §4.2 shows it passes a *strong* planted edge — but how strong must an edge be, and how does that threshold move with N? We sweep the planted edge magnitude **× the search scale N** into a 2-D power surface (`power.py` → `power_surface.json`; rendered by `plot.py`). Survivors (gate admits) per cell:

| edge \ N | 10 | 30 | 100 | 300 | 1000 | 3000 |
|---:|---:|---:|---:|---:|---:|---:|
| 0.00–0.15 | 0 | 0 | 0 | 0 | 0 | 0 |
| **0.25** | **1** | **0** | **0** | **0** | **0** | **0** |
| 0.40 (strong) | 2 | 2 | 8 | 20 | 61 | 168 |

The surface *is* the thesis. Read the **0.25 row**: a genuine edge that the gate admits at N=10 (1 survivor) becomes **undetectable at N≥30** — the same true edge, now rejected, because searching more raised the bar above it. Only the very strong 0.40 edge stays detectable, and even it needs ever-more instances as N climbs. The detectable-edge threshold **rises monotonically with N** (≈√(2 ln N)): at N=10 an edge of strength 0.25 is provable; by N=30 you need ≥0.40. A realistically small edge (`small_planted`, naive OOS ≈ +0.5) is invisible at every N — exactly like the real S&P.

**This is the paper's deepest and most honest result — though not a new theorem.** The threshold's √(2 ln N) growth is the leading-order asymptotic of Bailey–López de Prado's expected-max-Sharpe (their Exhibit 2 already plots it); our contribution is to *render it empirically as a survivor surface across generator types, with planted-edge controls that calibrate exactly where the gate's recall fails.* **Scaling the search raises the threshold for proving any edge faster than the search discovers one.** Consequences:
1. We **cannot and do not** claim the S&P 500 has no exploitable edge. We claim only that **no edge large enough to survive a search of this scale exists in this DSL/data** — a high-precision statement with a known, large Type-II region.
2. The contribution is therefore a **precision/recall characterization of anti-overfit gating**: this gate has (empirically) ~zero false-discovery rate across the noise and small-edge controls and **seven real markets** (S&P 500, DJIA, NASDAQ, a 15-stock cross-sectional panel, FX, gold, crypto), at the cost of failing to detect edges below a worst-regime Sharpe of ≈2–3 at N=1,000. That tradeoff *itself* tightens as N grows — the engine of the whole phenomenon.
3. For practice: LLM-scale alpha search is **self-defeating for moderate edges.** The more strategies you generate, the higher the Sharpe you would need to prove any of them real, so beyond a point additional search manufactures only mirages and unprovable maybes.

### 4.6 Distribution-free confirmation — the zero is not a parametric artifact

The deflated Sharpe haircut is *parametric* and was derived for a single in-sample Sharpe over N independent trials, not for the worst-of-regimes statistic our gate uses — so stacking it is conservative but heuristic (the obvious reviewer objection). We close this with a **distribution-free** test (`bootstrap.py`): a stationary block bootstrap (Politis & Romano 1994) of the per-bar OOS strategy returns that **resamples within each regime with a block plan shared across strategies**, so the worst-of-regimes min and the cross-strategy dependence are both preserved inside every resample. On the bootstrapped null we run the studentized single-step Reality Check (White 2000) / Romano–Wolf (2005) for per-candidate FWER-adjusted p-values, plus a Hansen (2005) SPA p-value on the *same* worst-regime Sharpe statistic, and count survivors at α=0.05.

| market | gen | DSR survivors | **bootstrap survivors (α=0.05)** | RC best p |
|---|---|---:|---:|---:|
| real S&P 500 | random | 0 (all N) | **0 (all N)** | 0.15–0.57 |
| real S&P 500 | creative | 0 (all N) | **0 (all N)** | 0.21–0.72 |
| real S&P 500 | live LLM | 0 (all N) | **0 (all N)** | 0.46–0.51 |
| planted (strong) | creative | 1→14 with N | **3→17 with N** | 0.000 |

The distribution-free survivor count is **0 at every N for all three generators on real S&P 500**, with no significant best p-value — and it *grows with N on the strong planted market*, exactly tracking the DSR. The result is **stable across mean block lengths {10, 25, 50}** (real-S&P bootstrap survivors are 0 at every block length). So the zero is not an artifact of the parametric haircut: a fully nonparametric multiple-testing test, run on the gate's own worst-regime statistic, reaches the identical conclusion. (Full grid in `bootstrap_results.json`.)

### 4.7 Generalization 1 — a cross-sectional equity panel (the DSL turned on)

A single index series only supports time-series momentum/reversion and (on close-only data) darkens the range/volume features. We add a **cross-sectional panel**: each DSL alpha is scored per asset, the scores are cross-sectionally demeaned and gross-normalized into a dollar-neutral, unit-gross weight vector (the cross-sectional "rank"), and the resulting long-short portfolio return series is fed to the **identical** worst-regime + cost + deflation gate (`panel_lab.py`, `panel_sweep.py`). Four controls, range/volume features **active**:

| panel market | gen | survivors vs N (10→1000) |
|---|---|---|
| **real: 15 large-caps** (Yahoo OHLCV, 2016–2026) | random / creative | **0 at every N** |
| cs_planted (strong cross-sectional reversal) | creative | 0.7 → 64 (grows with N) |
| cs_small (moderate cross-sectional edge, naive OOS +1.4) | creative | **0 at every N** |
| cs_noise (cross-sectional null) | both | 0 at every N |

The headline **holds on a real cross-sectional equity panel**: across 15 liquid large-caps with live volume and range features, **0 survivors at every N** for both generators (best naive cross-sectional Sharpe plateaus ~+0.5). The gate still *passes a strong cross-sectional edge* (survivors grow with N on cs_planted) and still *rejects a moderate one* (cs_small, naive OOS +1.4 → 0 survivors) — the precision/recall picture of §4.5 reproduces in the cross-section. This directly answers the "your data is too thin to have edge" objection: with the DSL fully active on real multi-asset data, the result is unchanged.

### 4.8 Generalization 2 — truly independent real markets

S&P/DJIA/NASDAQ are ~0.9 correlated and are not independent evidence. We add three markets with entirely different microstructure — **FX (EUR/USD), a commodity (gold), and crypto (BTC/USD)** — using real Yahoo OHLCV (`fetch_markets.py`, 2016–2026) and the same single-index sweep + gate (`independent_markets.py`):

| market | best naive OOS Sharpe (→N=1000) | gate survivors |
|---|---:|---:|
| FX — EUR/USD | +0.2 | **0 at every N** |
| commodity — gold | +0.9 | **0 at every N** |
| crypto — BTC/USD | +0.9 | **0 at every N** |

The zero **holds across all three**, for both generators — and not just under the parametric DSR: the **distribution-free block bootstrap** (§4.6) independently gives **0 RC survivors** on FX, gold, and crypto at every N (`bootstrap_independent.json`; crypto's best p-value, 0.20, is the lowest of the seven markets but still non-significant). Crypto — often argued to be the *least* efficient liquid market — is no exception: naive best-of-N reaches a ~0.9 Sharpe (a strategy a retail quant would chase), yet **zero survive** the multiple-testing gate. FX shows the weakest snooping (best ~+0.2), consistent with its near-random daily structure. Across S&P 500, DJIA, NASDAQ (§ verify.py), a real 15-stock cross-sectional panel (§4.7), FX, gold, and crypto — **seven real markets, three of them microstructurally independent — the survivor count is 0 at every N.**

### 4.9 The correct multiple-testing bar — a derived worst-of-regimes deflation, and a cautionary negative

A standing critique (§6): the deflated Sharpe is the expected max of N *single* Sharpes, but our gate scores the **minimum across k regimes**, then takes the best of N — so the standard haircut is the wrong null. We close this by deriving the right one (`theory.py`, Monte‑Carlo validated): the worst‑of‑regimes best‑of‑N null is **E[ maxᵢ₌₁..ₙ minₘ₌₁..ₖ Zᵢ,ₘ ]**, leading‑order quantile Φ⁻¹(1−N^(−1/k)). Because min‑of‑k has a thin upper tail, this envelope is **2.3–2.8× smaller** than the single‑Sharpe DSR envelope at relevant N (N=1,000: 3.26 → 1.38). **The standard DSR over‑deflates the worst‑regime statistic by ~2.4×.**

Re‑running survivors under the corrected envelope (`corrected_deflation.py`): on the real markets the best deflated Sharpe rises from the DSR's ≈ −1.5 to ≈ **−0.3** — much closer to the bar, but **still negative → 0 survivors**, while the strong planted control still passes (113 survivors). So the zero is **robust to the correct, far‑less‑conservative deflation**, not an artifact of an over‑harsh haircut; the true margin is thin (~0.3 Sharpe), which the DSR's −1.5 wildly overstated.

**The robustness dividend (a unifying result).** Because the worst‑of‑k envelope is so much lower than the single‑Sharpe one, the worst‑of‑regimes requirement *is itself* a multiple‑testing correction. We quantify it as the "deflation‑equivalent N′" — the single‑Sharpe search size with the *same* null max as worst‑of‑k at N (`theory.py(D)`): worst‑of‑3 regimes at N=1,000 has the false‑discovery ceiling of a single‑Sharpe search over only **N′≈7** strategies (N=3,000 → N′≈10; worst‑of‑5 → N′≈3). **Requiring a strategy to survive several independent regimes does the lion's share of the multiple‑testing work**, shrinking an effective thousand‑strategy search to a handful. This *resolves the apparent tension with §4.3*: the dividend assumes **independent** regimes, but real‑market sub‑periods are correlated, so the dividend collapses — which is precisely why, on real data, worst‑regime robustness alone admits mirages and the explicit deflation becomes load‑bearing (§4.3), while on the adversarial synthetic null (independent regimes) the worst‑regime requirement alone suffices. Robustness and multiple‑testing are the same coin; how much each contributes depends on regime independence.

**We measure exactly where each market sits on this trade‑off** (`regime_correlation.py`). Generalizing the dividend to *equicorrelated* regimes (a one‑factor model, `theory.mc_max_of_min_correlated`), N′ climbs with regime correlation ρ_reg: **7 (ρ=0) → 28 (0.4) → 62 (0.6) → 160 (0.8) → 426 (0.95)**. We then estimate the empirical ρ_reg per market as the mean cross‑sectional correlation between strategies' per‑regime Sharpes: the adversarial synthetic null sits at **ρ_reg = 0.24 → N′ ≈ 16** (dividend largely intact, worst‑regime alone suffices — matching robust=0 on noise in §4.3), while **real S&P 500 sits at ρ_reg = 0.67 → N′ ≈ 84** (DJIA 0.55→51, crypto 0.46→35) — the robustness dividend has **collapsed ~12×** (from N′≈7 to ≈84), so the worst‑regime requirement no longer protects and the explicit deflation must, exactly as §4.3's ablation found. The robustness/multiple‑testing trade‑off is not hand‑waving — it runs quantitatively along the measured regime correlation.

**A cautionary negative (reported because the data showed it).** Correlated strategies are correlated tests, so the multiple‑testing count is arguably an *effective* M_eff < N — the **effective‑number‑of‑independent‑tests** idea from genome‑wide association studies (Nyholt 2004; Li & Ji 2005; Li, Yeung, Cherny & Sham 2012; Galwey 2009), where linkage disequilibrium between SNPs is the exact analogue of shared structure between strategies. Computing M_eff exactly from the participation ratio of the strategy correlation matrix, M_eff = N/(1+(N−1)⟨ρ²⟩), gives M_eff ≈ 5 on our pools (⟨ρ²⟩ ≈ 0.2). Plugging that into the corrected envelope **manufactures ~500 "survivors" on real markets** — but they are spurious: at M_eff≈5 the worst‑of‑3 envelope is ≈0, so the haircut vanishes and raw Sharpes pass trivially. These "survivors" **directly contradict the distribution‑free bootstrap (§4.6), which makes no independence assumption and finds 0**. The lesson, which we flag as a trap rather than a result: **participation‑ratio dimensionality is not the effective number of *tail* tests for a maximum statistic, and naively importing the genomics effective‑N heuristic into best‑of‑N Sharpe testing is anti‑conservative — the bootstrap, not an analytic effective‑N, must be the arbiter.** (This is the kind of plausible cross‑disciplinary import that would have produced a false discovery; we ran it, it broke, and we report the break.)

We tried a *second* analytic shortcut (`envelope_departure.py`): calibrate an empirical effective‑N per generator by matching the realized best‑of‑N standardized in‑sample Sharpe on a null market to the i.i.d.‑Gaussian envelope E[max of N]. It also failed, and chasing *why* produced the most useful methodological result of this section. We first suspected serial correlation (the i.i.d. Sharpe SE var = (1+½SR²)/T ignores it) and implemented Lo's (2002) serial‑correlation‑adjusted standard error with a Newey–West HAC factor (`theory.hac_variance_ratio`, `lo_sharpe_se`). The diagnostic (`lo_diagnostic.py`) is decisive: the HAC inflation is **η² ≈ 1.07** (autocorrelation is negligible), yet the cross‑sectional variance of the standardized Sharpe is **≈ 4.6, not 1** — and Lo's correction barely moves it (4.6 → 4.4). So serial correlation is *not* the culprit. The real cause is **structural heterogeneity**: a generative search does not produce N noisy draws of a *single* null statistic; it produces N structurally *different* strategies (different drift exposure, different turnover‑cost drag), so the best‑of‑N is dominated by the structural tail, not estimation luck. **No standard‑error or correlation correction can capture that — the multiple‑testing "N i.i.d. trials" premise fails on the *identical* part, not just the independence part.** This is the deeper reason the distribution‑free block bootstrap (§4.6), which resamples each strategy's actual return path and so preserves its structure, is load‑bearing rather than a mere check. **Three analytic shortcuts (participation ratio, envelope inversion, Lo HAC), three failures, one mechanism — and one tool that works.**

---

## 5. Related work

- **Deflated Sharpe / false-strategy theorem.** Bailey & López de Prado, *The Deflated Sharpe Ratio* (2014) and *The Probability of Backtest Overfitting* (2016); López de Prado, *Advances in Financial Machine Learning* (2018). The DSR haircut is theirs; we apply it inside a multi-generator N-sweep with controls, and characterize its *power* (§4.5), which the original work does not.
- **Data-snooping tests we should be compared to (and partly do not yet run).** Sullivan, Timmermann & White (1999), "Data-Snooping, Technical Trading Rule Performance, and the Bootstrap" — *almost exactly our setup* (a rule universe × snooping correction on an index), and the closest prior art; White (2000) Reality Check; Hansen (2005) Superior Predictive Ability; Romano & Wolf (2005) stepwise multiple testing; Harvey, Liu & Zhu (2016) and Harvey & Liu, "Backtesting" (2015) and "Lucky Factors" (2021) on the factor zoo and the t>3 threshold; Barras, Scaillet & Wermers (2010) on FDR in fund returns. We **run** the White/Romano–Wolf studentized Reality Check and the Hansen SPA as a distribution-free complement to the parametric DSR (§4.6) — they agree on the zero.
- **The closest direct precedent — FINSABER (Liang et al., arXiv 2505.07078, KDD 2026).** Peer-reviewed; finds LLM trading agents (FinMem, FinAgent) generate **no statistically significant alpha** (p > 0.34) under a broad, long-horizon, survivorship-corrected evaluation, and concludes "LLM-derived alpha is likely a methodological artefact of narrow, biased evaluations." **Our headline conclusion — that LLM trading edge evaporates under rigorous evaluation — is therefore already established prior art.** FINSABER differs in *apparatus*: it controls snooping by *evaluation design* (20-year horizon, delisted names, rolling windows) and runs **no** deflated-Sharpe, White RC/Hansen SPA, N-sweep, power surface, or planted-edge controls. We are the formal-multiple-testing + N-sweep + calibrated-control complement to FINSABER's design-based result.
- **Same-lineage LLM alpha mining.** AlphaAgent (KDD 2025; targets alpha *decay* via AST regularization), QuantaAlpha (2602.07085; evolutionary LLM mining for discovery), AlphaForgeBench (2602.18481; benchmarks frontier LLMs), Lopez-Lira & Tang (2023), FinGPT, BloombergGPT. Verified: **none** applies multiple-testing correction, planted/noise controls, or an N-sweep power surface — so our methodological apparatus is differentiated within this lineage, but none of them is the source of the "edge vanishes" conclusion (that is FINSABER).
- **Verified LLM discovery & quality-diversity.** FunSearch (*Nature* 2023), AlphaEvolve; MAP-Elites (Mouret & Clune 2015); novelty search (Lehman & Stanley 2011); Boden, *The Creative Mind* (operator taxonomy).

**What is genuinely new here, stated honestly.** The statistical machinery is *not* ours: the multiple-testing gate is White (2000) / STW (1999) / Bailey–López de Prado (2014); STW(1999) already reported a data-snooping-adjusted **zero-survivor result on S&P 500 futures** (Reality-Check Sharpe p-values ≈ 0.99), transaction-cost-aware and OOS, on parameter-optimized rule grids; and the "discovery threshold rises with N" curve is the leading-order asymptotic of **BLdP Eq. 1, whose Exhibit 2 already plots the threshold rising with N** (so our "power surface" is the *empirical instantiation* of a known result, not a new theorem). What the surveyed literature does **not** contain, and what we contribute, is narrow but real: (i) a **derived worst-of-regimes deflation** — the expected max of N of the min over k regimes, E[maxₙ minₖ Z], which is ~2.4× smaller than the single-Sharpe DSR envelope the whole prior literature uses; deflating the *robustness* statistic correctly (rather than mis-applying the single-Sharpe haircut) is, to our knowledge, new, and it tightens the real-market margin from −1.5 to −0.3 while keeping the zero (§4.9); (ii) a **cross-generator design** — random vs evolutionary-creative vs a **live LLM** — through *one fixed gate*, isolating the generator's effect; (iii) **planted-edge / pure-noise controls** that *calibrate* the gate, absent from both the econometrics canon (one rule family) and the LLM-alpha work (real data only); (iv) a **cautionary negative** importing the GWAS effective-number-of-independent-tests machinery (Nyholt 2004; Li & Ji 2005; Galwey 2009) — it is anti-conservative for the best-of-N max statistic and the bootstrap must arbitrate (§4.9); and (v) the **LLM diversity-ceiling** finding (160 distinct from 1,000 draws). The honest one-line positioning: *we re-confirm a known negative (STW; FINSABER) with a more formal, generator-controlled apparatus, and contribute a correct worst-of-regimes deflation, a cross-generator/planted-edge calibration, a cross-disciplinary cautionary negative, and the LLM diversity ceiling.*

- **Effective number of independent tests (cross-disciplinary).** The correlated-tests problem we hit is solved in genome-wide association studies: Nyholt (2004), Li & Ji (2005), Li, Yeung, Cherny & Sham (2012), Galwey (2009) estimate the effective number of independent SNP tests from the correlation/LD eigenstructure; Carvajal-Rodríguez et al.'s SGoF even gains power as the number of tests grows. Finance's deflated-Sharpe/White-RC assume the full N; we import the genomics framing and report (§4.9) that the naive participation-ratio version fails for the maximum statistic — a transfer that *looks* right and isn't.

---

## 6. Limitations (honest)

- **Low recall is the headline caveat, not a footnote (§4.5).** The gate's zero on real data is a *precision* statement; its power curve shows it misses any edge with a true worst-regime Sharpe below ≈2–3 at N=1,000. So "0 survivors" must always be read as "no edge provable at this search scale," never as "no edge exists." This is intrinsic to multiple-testing at scale, not a bug, but it bounds every claim in the paper.
- **The worst-regime statistic is not the statistic the DSR was derived for** — *now addressed.* Bailey–López de Prado's expected-max-under-null is for a single in-sample Sharpe over N trials; we apply the haircut to the *minimum across regimes*, whose null distribution is not standard-normal, so the DSR is conservative-but-heuristic here. §4.6 closes this with a distribution-free stationary block bootstrap (White Reality Check / Romano–Wolf / Hansen SPA) on the worst-regime statistic itself; it reaches the identical zero on real data. The DSR remains the primary gate (cheap, per-candidate); the bootstrap is the nonparametric check.
- **The DSL and data are modest.** Close-only FRED series disable the range/volume features; the feature set is small and daily; no cross-sectional, intraday, or alternative data. A richer DSL might surface a survivor — the method (N-sweep + ablation + power curve), not the specific null, is the transferable result.
- **Reported counts are finite-pool quantities, not independent-per-N draws.** `bestOOS` and the winner/robust/survivor counts are bootstrap means over nested subsets of one fixed pool (≤4,000 per market-generator); for N near the pool there is essentially one sample. They estimate within-pool expectations, not an independent accumulation across N — the monotone "rise with N" is a property of E[best-of-N], reported as such.
- **Seed variance — now quantified (`seed_variance.py`).** Redrawing each pool under 8 independent seeds, the real-market survivor count is **0 ± 0 under every seed at every N** (bestOOS bands ±0.00–0.07), and the planted control is positive under every seed (creative N=1,000: 63 ± 7) — the single-seed curves are representative, not lucky draws. Residual: daily Sharpes are √252-annualized with no serial-correlation adjustment, which can flatter the "annual Sharpe ~1.0" rhetoric.
- **Synthetic controls are stylized.** The strong planted edge is high-frequency mean reversion (deliberately easy, to verify the gate *can* pass); the noise market's adversarial regimes make worst-regime alone sufficient there, which is *why* the real-market ablation (where it is insufficient) is the informative case. The `small_planted` and power controls (§4.5) address "is the null rigged easy?" directly.
- **Backtests certify the past.** Even a survivor would be provisional; markets are adversarial and non-stationary.

---

## 7. Future work

Most of the v0.2 future-work list is now done (§4.4–§4.8). What remains:
- **Extend the LLM arm from N=300 to N=3,000.** The diversity ceiling (§4.4) suggests diminishing returns, but confirming the full curve with a live model is the last gap between the offline scaling story and the LLM one. The cached-pool mechanism makes it a cost question (~10× the current API budget), not an engineering one. A multi-LLM comparison (GPT, Gemini, an open model) would also test whether the diversity ceiling is Claude-specific.
- **Romano–Wolf step-*down*** (more powerful than the single-step we run) and extending the bootstrap to the panel and independent-market settings.
- **Richer DSL / intraday data.** A larger operator set and live-volume intraday bars, to test whether the zero is a property of the gate or of the signal space — and a monthly-rebalanced cross-sectional factor variant (lower turnover than the daily panel).
- **Position the finding as a general failure mode.** "Verified generative search under fixed effect size and growing N" also describes molecule screening, neural-architecture search, and LLM hypothesis generation; one discussion section would broaden the citation surface beyond finance.

---

## 8. Reproducibility

```
cd ~/mentat                                                      # use python3.14
python3.14 -m mentat.nsweep --pool 4000 --data data/fred_SP500.csv \
                            --out papers/false-alpha/nsweep_results.json   # §4.1–4.3
python3.14 papers/false-alpha/power.py                           # power surface §4.5 -> power_surface.json
python3.14 papers/false-alpha/bootstrap.py                       # distribution-free test §4.6 -> bootstrap_results.json
python3.14 papers/false-alpha/fetch_panel.py && \
python3.14 papers/false-alpha/panel_sweep.py                     # cross-sectional panel §4.7 -> panel_results.json
python3.14 papers/false-alpha/fetch_markets.py && \
python3.14 papers/false-alpha/independent_markets.py             # FX/gold/crypto §4.8 -> independent_markets.json
python3.14 papers/false-alpha/verify.py                          # 20-check adversarial suite (20 PASS / 0 FAIL)
python3.14 papers/false-alpha/plot.py                            # render figures (needs matplotlib)
# live-LLM arm (needs anthropic + key sourced from ~/swechats/.env; cached after first run):
set -a && . ~/swechats/.env; set +a
~/swechats/.venv/bin/python papers/false-alpha/task5_llm.py 1000  # §4.4 -> task5_llm_results.json
```

Offline arms: no dependencies, no API key, deterministic (CRC-seeded; two runs byte-identical). The 74-test engine suite is `python3.14 -m tests.test_core`. Core symbols: deflated-Sharpe = `trade_lab.expected_max_sharpe_under_null`; gate = `AlphaProblem.verify`; cross-sectional portfolio = `panel_lab.panel_portfolio`; effective-trials = `nsweep.effective_trials`; bootstrap = `bootstrap.py`. Every reported number lives in a committed `*_results.json`. LLM pools are cached at `papers/false-alpha/llm_cache_*.json` so the live arm reproduces without re-billing the API.

---

## 9. Authorship and contributions

**Author:** Parv Mehndiratta — conceived the research question, designed the N-sweep and control structure, specified and built the experiment (`nsweep.py`) on the author's prior alpha engine (`trade_lab.py`, `imagine.py`), ran the analysis, and wrote the paper.

**Tools disclosed:** Implementation and drafting were done with AI assistance (Claude, Anthropic) used as a coding and writing aid under the author's direction; the underlying Mentat system uses a frozen LLM as a reasoning core, as disclosed in the Mentat paper. No undisclosed co-authors. (A previously referenced CRRA/Heston collaboration is *not* part of this work and is not claimed here pending independent verification.)

**Suggested venues** (tiered, no pay-to-publish HS journals): a NeurIPS/ICML/ICLR workshop on ML-for-finance or evaluation/robustness; ACM ICAIF (student-accessible track); arXiv (cs.LG, with a q-fin.ST cross-list via an endorser); SSRN for the finance audience. Frame as a workshop/preprint, not a journal article. **Framing matters for survival:** because the statistical core re-derives White/STW/BLdP and the "LLM edge vanishes" conclusion is already at KDD'26 (FINSABER), the defensible framing is an **evaluation/robustness** result — *how LLM-agent strategy search behaves under multiple-testing-correct gating, with calibrated controls and a cross-generator comparison* — rather than a finance-discovery result. The novelty budget rests on the cross-generator + planted-control + diversity-ceiling instantiation, which is workshop/ICAIF-scale, not main-track.

---

## 10. Verification audit — how this draft was hardened

In keeping with the project's discipline (*prefer an honest negative to a confident guess*), draft v0.2 was adversarially stress-tested before release, by the same machinery the paper studies: three independent Claude review agents (statistics/methodology, finance-ML positioning, reproducibility/integrity), the system's live reasoning core acting as a skeptical critic, an executable 17-check suite (`verify.py`), and a power curve (`power.py`). What they caught, and what changed:

- **"The effective-trials number is numerically unstable."** True — the original n_eff inverted the best-of-N envelope (logarithmic, so it swung orders of magnitude). Replaced with a correlation-based N_eff = N/(1+(N−1)ρ̄). The fix *overturned a prior claim*: ρ̄≈0 shows creative/LLM search is **not** more correlated than random, so "creativity snoops more" was deleted, not defended.
- **"Survivors = 0 is tautological / you over-deflate at N."** Answered (§4.3, §4.9): the planted edge survives the *same* haircut; the DSR actually *over*-deflates the worst-regime statistic ~2.4× and the corrected, weaker bar still gives 0 on real; and the assumption-free bootstrap also gives 0.
- **"The positive control is too easy; the null may be rigged."** This was the decisive critique (raised by both the statistics reviewer and the reasoning-core critic). It produced the paper's now-central result — the **power curve (§4.5)** and the `small_planted` control — which reframed the contribution from "no edge in the S&P" (an overclaim) to "moderate edges are unprovable at this search scale" (precision/recall).
- **"The title says LLM but no LLM was run."** Fixed by running the **live Claude-Opus arm** (§4.4); 3 of 4 pre-registered hypotheses held and **H2 was refuted and reported** as such.
- **Missing prior art** (Sullivan–Timmermann–White, White Reality Check, Hansen SPA, Romano–Wolf, Barras–Scaillet–Wermers, Lopez-Lira–Tang) was added (§5), with the distribution-free bootstrap honestly marked *not yet run*.
- A genuine **bug** (an unimported symbol that crashed the live-LLM arm) was surfaced by the verification run and fixed.

The reproducibility audit confirmed every number in §0/§4/Appendix A matches the artifact, two runs are byte-identical, and the authorship statement is clean. Residual honest gaps are listed in §6–§7. The point of this section is not to claim perfection but to show the result survived a serious attempt to break it.

**v0.3 hardening (a five-task external reviewer brief).** After v0.2, an external reviewer pass flagged two real holes — the parametric gate and the single-index narrowness — and three strengtheners. All five were implemented, each as a committed script → JSON artifact, with `verify.py` (now 20 PASS / 0 FAIL) and the 74-test suite green after each: (1) the distribution-free White/Romano–Wolf/Hansen bootstrap (§4.6) — *confirmed* the DSR zero; (2) the cross-sectional equity panel (§4.7) — the zero holds with range/volume active on real large-caps; (3) the 2-D power surface (§4.5) — the detectable-edge threshold visibly rises with N; (4) FX/gold/crypto (§4.8) — the zero holds across independent microstructures; (5) the live LLM extended to N=300 (§4.4) — H1/H3 hold, H2 stays refuted, and a *new* diversity-ceiling finding emerged. No headline claim was refuted; the new finding (LLM structural-diversity saturation, §4.4) was added because the data showed it. Real market data is genuinely real (downloaded by `fetch_panel.py`/`fetch_markets.py`, traceable to source); no data was fabricated.

**Novelty audit (a cited deep-research pass, 20 primary sources, 25 claims verified 3-0).** A separate adversarial literature search corrected two of *our own* novelty claims, applied here in the same spirit: (i) the "power surface" was initially described as a new result — it is the empirical instantiation of Bailey–López de Prado's expected-max curve (their Exhibit 2), now credited as such (§4.5, abstract); (ii) the "0 survivors on real S&P" and "LLM edge vanishes" conclusions are *prior art* — STW(1999) reported a data-snooping-adjusted zero on S&P 500 futures, and FINSABER (KDD'26) already establishes the LLM-edge-evaporates result — both now cited as the closest precedents (§5), with our contribution honestly narrowed to the cross-generator-through-one-gate design, the planted-edge calibration, and the LLM diversity ceiling. The search found no single prior work combining all four of our elements, but flagged (caveat) that it surveyed a finite set; Harvey-Liu-Zhu, AutoQuant (2512.22476), and Lopez-Lira–Tang were named-but-unverified and could narrow the gap further.

**v0.4 — the math, and three reported negatives.** A subsequent deep-dive into the extreme-value mathematics produced the paper's strongest genuinely-new results and three honest negatives, each a committed script → JSON with the 21-check `test_theory.py` and the 20-check `verify.py` green: (i) **derived the worst-of-regimes deflation** E[maxₙ minₖ Z] the gate actually needs (MC-validated) and showed the standard DSR over-deflates it ~2.4× — the real-market zero survives the corrected, far-weaker bar (§4.9); (ii) the **robustness-dividend identity** — worst-of-k regimes ≈ a single-Sharpe search over N′≈7 — which unifies robustness and multiple-testing and resolves the §4.3/§4.9 tension; (iii) **seed-variance bands** confirm 0±0 survivors on real markets across 8 seeds. The negatives, reported not buried: two analytic effective-N shortcuts (a genomics participation-ratio import, and an envelope-inversion) both manufacture false survivors or unstable estimates, so the block bootstrap remains the necessary arbiter — and one of them (the participation ratio) was a plausible cross-disciplinary import that *looked* right; running it and reporting its failure is the point. paperclip (biomedical corpus) confirmed the finance combination is absent there while surfacing the genomics effective-number-of-tests lineage we (cautiously) drew on.

---

## Appendix A — key numbers at a glance

- **Real S&P 500**, all 5,994 tradeable alphas (random + creative): best worst-regime annualized Sharpe = **+0.847**; best naive pooled-OOS = **+0.999**; **survivors = 0 at every N**, all three generators (random, creative, live LLM).
- **Deflation haircut** on real S&P at n_trials = {1000, 3000} = {2.31, 2.52} ann. → best deflated = {−1.46, −1.67}. Even at the smallest defensible *effective* trial count (~34, random's N_eff at N=1,000), the haircut (~1.5) still exceeds +0.847 → deflated < 0 → **0 survivors is not an over-deflation artifact.**
- **Search redundancy** ρ̄ on real S&P: random **+0.029**, creative **−0.050**, live LLM **+0.007** (mean correlation); but ⟨ρ²⟩≈0.2 and no single analytic effective-N is reliable (§4.9) — the bootstrap is the arbiter.
- **Worst-of-regimes deflation (§4.9):** standard DSR over-deflates the min-over-k statistic ~2.4×; corrected bar still gives 0 on real (best deflated ≈ −0.3). **Robustness dividend:** worst-of-3 at N=1,000 ≈ single-Sharpe search over N′≈7 — robustness *is* deflation, collapsing when regimes correlate.
- **Gate power curve** (N=1,000): admits 0 survivors until the true worst-regime Sharpe exceeds ~+2 (edge giving Sharpe **+1.94 → 0** survivors; only the strong edge at **+4.47 → 61**). A realistically small edge (`small_planted`, naive OOS ≈ +0.5) is invisible at every N — like the real S&P. The discovery bar grows ≈√(2 ln N).
- **Live LLM (Claude Opus 4.8):** H1 ✓ (bestOOS +0.43→+0.79 on real), H2 ✗ refuted (ρ̄=+0.007, not more correlated than random), H3 ✓ (0 survivors on real), H4 ✓ (recovers strong planted edge faster than random).
- **Strong planted control:** survivors grow with N (creative 0.7 → **154** at N=3,000) — the gate passes a strong real edge.
- **Creativity/LLM on real S&P:** **~2× the regime-robust mirages** of random (196 vs 115), **0** survivors regardless.
- **Generalization (Tasks 2 & 4):** the zero holds on a **real 15-stock cross-sectional panel** (range/volume active, 0 survivors all N) and on **three microstructurally independent real markets** — FX (best naive +0.2), gold (+0.9), crypto (+0.9) — all **0 survivors at every N**. Seven real markets, zero survivors.
- **Distribution-free check (Task 1):** stationary block-bootstrap White RC / Romano–Wolf / Hansen SPA on the worst-regime statistic → **0 survivors on real S&P at every N, all 3 generators** (RC p 0.15–0.72), stable across block lengths {10,25,50}; grows with N on strong planted. The zero is not a parametric-DSR artifact.
- **Power surface (Task 3):** detectable-edge threshold rises with N — edge 0.25 admitted at N=10 but rejected at N≥30; only the 0.40 edge stays admitted (2→168 survivors as N goes 10→3000).
- **Adversarial verification:** `verify.py` → **PASS / 0 FAIL** (cost∈{0,…,0.002}, target∈{0,0.25,0.5}, 2/3/5 regimes; S&P, DJIA, NASDAQ, FX, gold, crypto all 0 survivors; independent `curriculum.study` agrees 0/6 verified facets; positive control passes the real `AlphaProblem.verify`, engine score +1.06).
