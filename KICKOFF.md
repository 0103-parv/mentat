# Start-here for the next session

Context/cache do NOT transfer between sessions — this file + `CLAUDE.md` + the saved
memory are how state persists. Open a new session **in `~/mentat`** (laptop on/plugged in)
and paste the prompt below.

## Paste this to start
> Read CLAUDE.md, VISION.md, and FINDINGS.md, then continue the project. Two tracks:
> (1) LEARN: use the `paperqa` CLI (`pqa`) over ~/papers to study the project's pillars —
> verification-gated discovery (FunSearch / AlphaEvolve), grounded agent memory
> (ExpeL / AWM / Mem0, already in ~/papers), and overfit-robust backtesting (deflated /
> probabilistic Sharpe, López de Prado). For each real insight, distil ONE grounded lesson
> into Jarvis (learn_lesson) or a notes file — cite the paper. (paperclip is biomedical-only,
> so use it only if a bio angle comes up; pqa is the right tool here.)
> (2) BUILD: implement `trade_lab.py` per VISION.md — an alpha DSL + a walk-forward,
> cost-aware, multiple-testing-corrected OOS backtest verifier + an AlphaProblem, mirroring
> math_lab/self_research. Reuse alpha-evolver's numpy backtest path; ask me for a data CSV or
> fetch a liquid universe. Then run it looping. Tests green before every commit; small commits;
> update OVERNIGHT_LOG.md.

## Why this order
The anti-overfit thesis (VISION.md) is the whole edge: the backtest verifier (OOS + costs +
multiple-testing penalty) is what makes a self-improving alpha agent real instead of one that
dies live. Reading the deflated-Sharpe / FunSearch papers first makes the verifier correct.

## Honest reminders
- For real discovery you need REAL compute time — leave `mentat.improve` / `mentat.discover` /
  `mentat.discover_capset` (and later `mentat.trade`) looping for hours, laptop awake.
- Known bug to fix early: the spawn sandbox in `run_construction` breaks under `-c`/stdin
  (fine via `-m`). Use fork on macOS or avoid re-importing `__main__`.
- The north star (a brain-like, truly-learning agent) is a direction, not a one-shot build.
  Progress only counts when a verifier proves it. That gate is the project.
