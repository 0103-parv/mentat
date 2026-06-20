# Mentat: A Verification-Gated Cognitive Kernel with Brain-Inspired Creativity and Fast/Slow Memory

*Working research note. Co-built by Parv Mehndiratta with Claude (Anthropic) as the reasoning core.*
*Repo: github.com/0103-parv/mentat. Every quantitative claim below is produced by code in the
repo and covered by the test suite (`python3 -m tests.test_core`, 61 tests).*

## Abstract
Large language models are fluent but ungrounded: they generate plausible text and leave
verification to the user, they forget across sessions, and they answer even when they should
not. Mentat is a small system that wraps a frozen LLM in an architecture designed to fix
exactly those failures. Its one rule — **nothing becomes memory, an opinion, or an action until
a verifier passes it** — is implemented as a domain-agnostic `propose → verify → remember →
reflect` kernel. Around it we add (1) grounded, anti-fabrication memory; (2) a brain-inspired
creativity engine (novelty, quality-diversity illumination, productive surprise, a tunable
risk dial); (3) retrieval-grounded QA that refuses rather than hallucinate; and (4) a fast/slow
memory consolidation loop modeled on Complementary Learning Systems. We demonstrate it on
verified mathematics, anti-overfit alpha discovery, and grounded QA. The headline result is an
honest one: on real S&P 500 data, **0 of 12 strategy facets survived 3,840 deflated
out-of-sample tests** — a rigorous map of what does *not* work, where naive search would
"discover" false edges. Mentat is not a new model and not AGI; its contribution is the *fusion*
of these mechanisms under a strict honesty discipline.

## 1. Thesis
The difference between a thinking machine and a confident bullshitter is a **gate**. An LLM
optimizes to be a helpful responder; Mentat optimizes to be *provably right in a narrow domain
and to never fool itself*. The same reasoning core (Claude, via API) proposes ideas — but Mentat
believes them only after an external verifier (an exhaustive proof, a backtest, a test suite)
confirms them. Everything downstream — memory, opinions, a library of "what works" — is built on
verified claims only.

## 2. Architecture
**Kernel (`core.py`).** `Problem`/`Verdict` (the verifier *is* the problem), `Memory` + `Lesson`
(decision-card-shaped, grounded), `Mind` (cognitive modes + productive surprise), and `solve()`,
the propose→verify→remember→reflect loop. Zero dependencies.

**Grounded memory (the anti-fabrication firewall).** A lesson may enter memory only if its claim
shares real vocabulary with the *verified* evidence it cites (≥2 significant keywords). This
kills hallucinated facts at the write path. Memory persists across runs (warm starts) and decays
(use-it-or-lose-it).

**Creativity engine (`BrainConfig`, `imagine.py`).** Ported from the authors' prior project
(alpha-evolver) and made domain-agnostic and *ablatable*: generic novelty (1 − max Jaccard
similarity), a quality-diversity elite pool, a MAP-Elites illumination archive, predict-then-test
productive surprise with an inverted-U that quarantines too-good-to-be-true results, and Boden's
three creativity forms as operators (blend = combinatorial; reshape/specialize = exploratory;
invert/transfer = transformational) with a tunable **risk dial**.

**Grounding (`rag.py`, `embed.py`).** Hybrid retrieval (BM25 + embeddings; semantic via model2vec,
else a dependency-free hashing fallback) over a corpus, answering only from retrieved passages
with citations and **refusing** when retrieval is too weak.

**Fast/slow memory (`consolidate.py`, `finetune/`).** Complementary Learning Systems: the grounded
memory/RAG is the fast hippocampal store; LoRA fine-tune is the slow neocortical store; a "sleep"
pass replays verified lessons, abstracts principles, prunes, and exports a consolidation dataset
for the slow step.

**Autonomy (`operate.py`, `research.py`).** A bounded, audited mandate executor ("you have full
authority to X") and an overnight research autopilot that loops the gated engines and keeps only
proven results.

## 3. Methods and results
All numbers are reproducible from the repo.

**Verified mathematics (`discover.py`, `discover_diverse.py`).** The core proposes a construction
as code; the verifier executes it in a resource-capped sandbox and **exhaustively** searches for
a counterexample, so "valid" means *proven*. It found a verified Sidon set of size 15 in [1,200],
and illuminates the size-vs-span frontier as a catalog of ~11 distinct proven constructions.
*Honest caveat:* these are known constructions rigorously verified, not new mathematics.

**Anti-overfit alpha discovery (`trade_lab.py`, `realm.py`).** The verifier is a brutal
walk-forward backtest: positions trade next-bar (no look-ahead), every position change pays a
transaction cost, scoring takes the **worst** of multiple out-of-sample regimes, and a
**deflated-Sharpe** multiple-testing penalty (Bailey & López de Prado 2014) discounts the best of
N trials. On a synthetic universe with a planted, regime-consistent edge it recovers the edge
(deflated worst-regime OOS Sharpe **+1.66**) and rejects momentum/decoys. **On real S&P 500 data
(FRED), 0 of 12 facets survived 3,840 gated hypotheses** — the honest, valuable result: a map of
mirages, consistent with near-efficiency, where naive search overfits.

**Creativity ablation (`imagine.py`, `creativity.py`).** Creative synthesis vs random search at
rising risk (5 seeds): signal-family coverage rises from 3.0 to 5.4 as risk climbs, while peak
score falls — creativity is a tunable **explore/exploit dial**, not a free win. MAP-Elites
illumination returns ~18 distinct verified designs across a behavior space where a greedy
maximizer returns ~5.

**Grounded QA (`rag.py`).** In-corpus questions get cited answers; out-of-corpus questions are
refused ("I don't have a grounded source"). Hybrid retrieval surfaces the right document by
*meaning* even with no keyword overlap. This is the anti-haze guarantee.

**Fast/slow consolidation (`consolidate.py`).** A sleep pass abstracts clusters of verified
lessons into principles and exports a LoRA consolidation set — only verified memory consolidates.

## 4. Related work
The ingredients are established; the contribution is their fusion + the honesty discipline.
- Verified LLM discovery: FunSearch (Romera-Paredes et al., *Nature* 2023), AlphaEvolve.
- Quality-diversity / illumination: MAP-Elites (Mouret & Clune 2015, arXiv 1504.04909).
- Novelty search & open-endedness: Lehman & Stanley (2011); Conti et al. (2017, arXiv 1712.06560);
  POET (Wang et al. 2019, arXiv 1901.01753).
- Intrinsic motivation / curiosity: Schmidhuber (2010); Pathak et al. (2017, arXiv 1705.05363).
- Creativity theory: Boden, *The Creative Mind* (combinatorial/exploratory/transformational).
- Memory: Complementary Learning Systems (McClelland, McNaughton & O'Reilly 1995); ExpeL, AWM, Mem0.
- Anti-overfit finance: Bailey & López de Prado, the Deflated Sharpe Ratio (2014).
- Grounding: RAG (Lewis et al. 2020, arXiv 2005.11401; Gao et al. 2023 survey, arXiv 2312.10997).
- Domain LLMs: BloombergGPT (2303.17564) vs FinGPT (2306.06031) — fine-tune+RAG ≫ from-scratch.

## 5. Limitations (honest)
- **Built on a frozen LLM.** The reasoning core is Claude; Mentat is an *architecture*, not a new
  model. It is narrower, slower, and less general than the LLM it wraps.
- **Not AGI, not a brain.** The brain-inspired mechanisms are *inspired by*, not equal to,
  neuroscience. "Like a real brain" is a direction, not a deliverable.
- **The market ceiling is real.** A backtest certifies the past, not the future; edges decay.
  Our honest result on real data is mostly negative, by design.
- **Several claims use synthetic testbeds** (the planted-edge market, design illumination) to
  validate the *machinery*; real-data validation is partial.
- **The LoRA dataset is a seed**; real specialization needs a larger corpus.

## 6. Contribution
A single, coherent system in which (a) verification gates every belief, (b) memory is grounded and
firewalled against fabrication, (c) creativity is novelty/diversity-driven, tunable, and gated,
(d) QA refuses rather than hallucinates, and (e) memory consolidates on two timescales — all under
a discipline that prefers an honest negative to a confident guess. The value is the fusion and the
honesty, demonstrated on real and synthetic domains with reproducible code.

## 7. Reproducibility
`python3 -m tests.test_core` (61 tests, no dependencies). Engines: `discover`, `discover_diverse`,
`trade`, `realm`, `imagine`, `creativity`, `illuminate`, `curriculum`, `rag`, `consolidate`,
`research`, `operate`. See `CLAUDE.md` for the module map and `VISION.md`, `CREATIVITY.md`,
`GROUNDING.md` for the design rationale.
