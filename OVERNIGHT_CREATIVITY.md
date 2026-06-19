# Overnight: building creativity into an AI — 2026-06-17 → 18

**Mandate (from the user):** spend the night on ONE thing — *creativity*. Build an AI that
genuinely creates: brain-blueprinted, with the improved/verified memory we built, that
**synthesizes ideas, backtests what it thinks, and only keeps what's proven** — applied to the
stock market. "Imagine a human brain that had everything AI could do in it, with improved
memory." Learn from the literature (paperqa/paperclip), from Codex's design (alpha-evolver),
and from the original plan (VISION.md). Think in a way that is *risky*; verify relentlessly.

This file is the log + the design. Every claim here is backed by code that runs and tests.

## What it would become, and do in the stock market (the honest synthesis)
Not an oracle — the market's verifier (the backtest) only certifies the past, and edges decay.
What it becomes is rarer and real: **a creative research mind that dreams up genuinely novel
trading ideas by analogy and recombination, backtests every one out-of-sample with deflation,
remembers only what survives, and grows more inventive as its verified vocabulary grows.** It
imagines boldly and believes cautiously. In the market that means: a self-extending, diverse
*portfolio* of verified-robust signal ideas (not one fragile alpha), an honest map of what's a
mirage, and a search that escapes the local optima that trap everyone who only optimizes. The
edge isn't prediction — it's **creative coverage under a brutal honesty gate**, which almost
no one runs.

## Design principles, grounded in the creativity literature
(Papers pulled into `~/papers`; foundational works cited by author. pqa local-index refresh is
a known follow-up — these are grounded from the literature + the fetched PDFs.)

1. **Creativity ≠ optimization.** Pure objective-chasing converges and stops being novel.
   Search for *novelty/behavioral diversity* explores far more of the space — Lehman & Stanley,
   "Abandoning Objectives: Evolution Through the Search for Novelty Alone" (2011); Stanley,
   *Why Greatness Cannot Be Planned*. → our **novelty signal + quality-diversity pool**.
2. **Illumination, not a single best.** MAP-Elites keeps the best solution per *behavior niche*,
   returning a whole map of diverse high-quality solutions — Mouret & Clune, "Illuminating
   search spaces by mapping elites" (arXiv 1504.04909). → our **archive + `illuminate`/`realm`**.
3. **Boden's three forms of creativity** — combinatorial (new combinations), exploratory (move
   within a space), transformational (change the space). Boden, *The Creative Mind* (1990/2004).
   → our **creative operators** in `imagine.py`: `blend` / `reshape`,`specialize` / `invert`,`transfer`.
4. **Intrinsic curiosity / productive surprise.** Reward learnable surprise (prediction error /
   compression progress), distrust the extremes — Schmidhuber, "Formal Theory of Creativity, Fun,
   and Intrinsic Motivation" (2010); Pathak et al., "Curiosity-driven Exploration" (arXiv
   1705.05363). → our **inverted-U productive surprise + extreme-surprise quarantine**.
5. **Open-endedness.** Keep generating new challenges/ideas so the search never saturates —
   Wang et al., POET (arXiv 1901.01753); novelty-driven neuroevolution (arXiv 1712.06560). →
   our **loop-until-dry** and the (next) **self-extending facet/idea generation**.
6. **The brain blueprint: dream ↔ focus dual process.** Creative cognition alternates a
   generative/associative mode (default-mode-network-like "dream") with an evaluative/control
   mode (executive-control-network-like "focus") — Beaty et al. on DMN↔ECN dynamics; predictive
   coding / free-energy (Friston) as predict-then-correct. → our **`Mind` modes** drive which
   creative operators fire.
7. **Verified discovery at scale** (the proof it works on real problems): FunSearch
   (Romera-Paredes et al., *Nature* 2023) and AlphaEvolve — an LLM proposes, a verifier gates,
   only proven results are kept; this found genuinely new mathematics. → our whole
   propose→verify→remember→reflect kernel.

**The synthesis (ours):** Boden's creative operators, fired by a brain-like dual-process mind,
biased by novelty + productive surprise, kept diverse by MAP-Elites illumination, compounding
on a grounded memory of *verified* motifs — every idea gated by a brutal verifier. Imagine
boldly; believe only what's proven.

## Built tonight (block 1)
- **`mentat/imagine.py` — the creative synthesizer.** Creative operators (`blend`/`invert`/
  `transfer`/`reshape`/`specialize` = Boden's 3 forms) over the alpha DSL; a `CreativeProposer`
  that synthesizes hypotheses from the VERIFIED knowledge base (elites + illumination archive),
  with the brain's modes choosing operators; and an `LLMImaginer` that has the reasoning core
  invent a novel CONCEPT (with rationale) grounded in verified motifs, then renders it — falling
  back to the offline proposer. It CREATES FROM what it verified, so creativity compounds.
- Demo (`python3 -m mentat.imagine`): the creative synthesizer discovers a verified reversion
  variant (`mul(neg(zscore(ret1)), c_1)`, deflated OOS +1.18) and covers MORE signal-family
  niches than random/baseline search — more creative diversity, every idea gated.
- 53 tests green (operators, proposer in all modes, LLM-imaginer parse + fallback, end-to-end
  creative discovery of a verified edge).

## Roadmap for the rest of the night (verify each; commit per block)
- **B2 — creative loop-until-dry + compounding:** let `imagine` feed its verified discoveries
  back as substrate and run until it stops finding novel verified ideas; measure creativity
  (distinct verified families × novelty) vs the random baseline across seeds. Honest ablation.
- **B3 — self-extending idea space:** the LLM imaginer proposes NEW behavior descriptors/facets,
  not just alphas — the open-endedness lever (principle 5).
- **B4 — risk dial:** wire a "thought-risk budget" (alpha-evolver's idea) so it can think more
  riskily on demand (bolder operators, higher novelty weight), while the gate holds.
- **B5 — wire `imagine` into `realm`/`research`** so the overnight autopilot uses creative
  synthesis, not random search, to map the market.
- Stretch: a 2nd realm to show the creative mind transfers; a write-up of the creativity ablation.
