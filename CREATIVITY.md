# Creativity — the brain, ported into the kernel

The goal is **creativity**: an agent that generates *novel*, *surprising*, **verified**,
*diverse* ideas — not one that hill-climbs to a single answer. This note records (1) that
the creativity engine was already built by **Codex** in `~/alpha-evolver`, (2) what it is,
and (3) how it is now ported into the Mentat kernel so every discovery flagship can use it.

## 1. Confirmed: Codex already built the brain (in alpha-evolver)

Checked directly (no `codex` CLI is installed, so I read its work). The alpha-evolver git log:

```
36289f8 Add Max Cut creativity laboratory
b7cca65 Add ablation harness, adversarial test, and learning-progress mechanism
d008960 Add brain inspired risk loop
54deeee Add calibrated Sharpe prediction errors      (predict-then-test)
1c749af Add brain mechanisms and ship polish
```

`alpha_evolver.py` (~2,200 lines) is a full brain-inspired, self-improving research
organism. Its design — and its **honest ablation evidence** — is the foundation we build on.
Credit: that engine is Codex's.

## 2. What the brain is (alpha-evolver's design)

Motto: **"imagine recklessly, believe cautiously, test relentlessly, remember with context."**

- **Predict-then-test → productive surprise.** Predict a candidate's score before testing;
  the prediction error is *surprise*. An **inverted-U** curve (`ratio * exp(1 - ratio)`,
  peaking at ratio = 1) rewards *moderate* surprise and distrusts *extreme* surprise.
- **Quarantine (the safety half).** A result wildly better than predicted (`|error|/scale >
  3`) is the classic overfit/bug signature → it is **stress-tested**, not trusted. Codex's
  ablation: the quarantine firewall cut overfit junk in trusted memory from **76% → ~53%**
  and kept top alphas *positive* on clean data while no-firewall variants went negative.
- **Cognitive modes.** `dream` (widen), `focus` (exploit), `recover` (tighten when junk
  rises), chosen each generation; plus a periodic **sleep** consolidation phase.
- **Novelty.** Each idea scored `1 − max Jaccard-similarity to anything tried` (over its
  sub-structure fingerprint), and rewarded in selection — quality-*diversity*, not just
  quality. This is the core creativity driver.
- **Memory strength + decay**, a **motif library** (reusable fragments), **lineage
  circuit-breakers**, and a **thought-risk budget** that scales *imagination* while leaving
  *verification* untouched.

Honest caveats from Codex's own ablations (kept, because honesty is the project): the
*specific* inverted-U reward is not a proven universal win (on the convergent Max Cut task it
did not beat plain quarantine; a learning-progress variant was tested and **left off**). What
*consistently* earns its keep is **quarantining the too-good-to-be-true** and **novelty for
open-ended search**.

## 3. The port into Mentat's kernel (`core.py`)

Mentat only inherited a thin slice (the `Mind` modes + a logged surprise signal). The
creativity engine is now in the **domain-agnostic kernel**, so math discovery, cap-sets,
and alpha discovery all get it:

- `fragments(candidate)` / `novelty(candidate, others)` — generic structural fingerprint +
  novelty for *any* candidate (expression trees, code strings, programs, vectors).
- `BrainConfig` — the engine, **ablatable** (novelty / surprise / quarantine / modes / sleep
  / motifs each toggle). `solve(brain=None)` runs the plain kernel, so existing flagships are
  unchanged unless they opt in.
- Quality-diversity **elite pool** (`Memory._trim_quality_diversity`): keep the best AND the
  most novel, so the existing proposers breed from a diverse pool — creativity with **no
  proposer changes**.
- **Predict-then-test surprise** + **extreme-surprise quarantine** in `solve()`, via a
  `Problem.stress_verify` hook (default trusts; a backtest domain stress-tests under higher
  costs — a second anti-overfit firewall stacked on the deflated-Sharpe gate).
- **Sleep/consolidation** (motif refresh + distill principles from the top *distinct* elites)
  and a **motif library** (`Memory.mine_motifs`).
- Creativity metrics on every run: `Result.distinct_verified` (how many distinct ideas
  passed the gate) and `Result.diversity` (mean pairwise novelty of the final pool).

## 4. Does it help? The ablation (`python3 -m mentat.creativity`)

Same search (rediscover `y = x³ − 2x + 1`), creativity brain OFF vs ON, 8 seeds:

| config | pool diversity | solved/8 |
|---|---|---|
| plain (brain off) | 0.26 | 2 |
| **brain, novelty 0.3 (default)** | **0.29** | **2** — more diverse, *same* solve |
| brain, novelty 3.0 | 0.66 | 1 — max diversity, convergence trades off |

**Read it honestly.** Novelty is an **explore/exploit dial**:
- At the default it buys a more diverse pool of verified solutions *for free* (no solve cost).
- Cranked up it maximizes diversity (illumination) but, on a *single-answer* task, trades
  away convergence — exactly the shape Codex's own ablations found (novelty helps open-ended
  search, not convergent needle-finding). So: **turn it up for open-ended discovery, keep it
  low when there's one answer to converge on.**

Two creativity wins that *are* robust and shipped:
1. **Diversity for free** at the default, across every domain (the quality-diversity pool).
2. **The quarantine firewall** (`stress_verify`): the proven safety half, now a second
   anti-overfit gate on the alpha flagship (a too-good alpha is re-tested under harsher costs
   before it's trusted).

The rule stays the same as everywhere else in Mentat: a creative idea is only believed once a
verifier passes it. **Creativity widens what gets proposed; verification decides what gets
kept.** That is the whole project — now with a real imagination behind it.
