# Vision — and the honest, buildable path

## The north star (what you actually want)
A brain-like agent: novel, real creativity; learns from things *really* learns; a human-style
mind with the world's information and an AI's processing speed. From that: an ultimate trading
agent, and novel thinking that cracks open unsolved math/physics.

**Honest truth:** nobody can build a human-brain-speed, omniscient AGI today — not us, not the
$1B labs. The brain is still unmatched. So this is a *direction*, not a deliverable. What makes
it real instead of a fantasy is that we make **verifiable, incremental** progress toward it, and
never confuse the north star with what we've actually proven. That discipline IS the project.

What we already have that genuinely points at it: a system that **thinks by proposing then
verifying** (novel ideas, but only kept if proven), **really learns** (grounded decision-cards
from real outcomes, firewalled against fabrication), and runs **brain-inspired modes**
(focus/dream/recover + an inverted-U "productive surprise" that rejects too-good-to-be-true).
That's a baby version of "novel thinking that learns." We grow it.

## The buildable flagship now: a self-improving, anti-OVERFIT alpha-discovery agent
This is the honest version of "ultimate trading agent." Not "take apart the whole stock system"
(markets are adversarial and near-efficient — that part is hype). What's real and rare:

**The key idea (this is the whole edge): verification IS the anti-overfit mechanism.** Naive
alpha search overfits because it keeps what looked good in-sample. The same "verification is the
gate" principle that runs our kernel, pointed at trading, becomes the discipline real quants use:

- **Proposer** (the reasoning core): proposes an alpha as a formula in a small DSL over
  price/volume/features (alpha-evolver already uses S-expressions for exactly this).
- **Verifier = a brutal backtest, not a friendly one.** In-sample fit, then scored on a
  *held-out out-of-sample* window + *multiple market regimes* + *realistic transaction costs*,
  with a **multiple-testing / deflated-Sharpe penalty** (you searched N alphas — discount the
  best accordingly). An alpha only survives if it generalizes. This is what kills overfit.
- **Memory**: a grounded library of alpha *motifs that genuinely held up OOS* — not ones that
  looked good once.
- **The loop**: propose → OOS-verify → keep only what survives → reflect → repeat. It runs its
  own backtests, accumulates verified-robust alphas, and self-improves each cycle. Brain-inspired
  modes drive exploration; a sleep/consolidation pass distills durable lessons. This is exactly
  what alpha-evolver was reaching for, now with the reasoning core proposing and a strict gate.

**Why this is novel + valuable + honest:** most self-improving alpha bots overfit and die live.
One that improves *only against an OOS+cost+multiple-testing gate* is the real thing — and an
LLM-driven, self-researching version of it is genuinely new. It's also real research/admissions
currency.

## First build (for a fresh ~/mentat session, laptop on)
Mirror `math_lab.py` / `self_research.py`:
1. `trade_lab.py` — an alpha DSL (features: returns, momentum, vol, volume, etc.) + a
   `walk_forward_backtest(alpha)` verifier with: train/OOS split, ≥2 regimes, transaction costs,
   and a deflated-Sharpe / multiple-testing correction. The verifier returns OOS-Sharpe-after-costs.
2. An `AlphaProblem(Problem)` wrapping it (passed = beats a baseline OOS Sharpe by a margin that
   survives the multiple-testing penalty); a `Lesson` distilled only from OOS-robust winners.
3. An `AlphaProposer` (reuse the CodeProposer/HeuristicProposer pattern) + a runner `mentat.trade`.
4. **Data**: real OHLCV (user provides a CSV/parquet, or we fetch a liquid universe). alpha-evolver
   already has a pure-numpy offline backtest path to reuse/adapt.
5. Leave it looping for real hours/days — that's where genuinely robust alphas (and honest
   negative results) show up.

## The rule that keeps it real
Every claim — an alpha "works", a result is "novel", the agent "learned" — must pass a verifier
before we believe it. Out-of-sample, cost-aware, multiple-testing-corrected. That gate is the
only thing separating "an ultimate trading agent / a thinking brain" from a confident bullshitter.
We build toward the north star one *verified* step at a time. That's how the answer becomes yes.
