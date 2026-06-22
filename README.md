# Mentat

*A verification-gated cognitive kernel with grounded, persistent memory — the spine
of a personal thinking machine.* (Codename; rename freely. A Mentat, in Dune, is a
human trained to think like a computer — which is the goal stated plainly.)

This is **not** a chatbot and **not** "install Jarvis." Following the best of the
builds that inspired it: *Jarvis isn't something you install, it's something you
build* — a hub that connects a reasoning core to memory, to verifiers, to
specialist agents, to tools, to channels. Mentat is the hub's spine.

## The one rule

> The kernel never lets a candidate become memory, an opinion, or an action until
> a **verifier** returns a verdict on it.

Verification is the gate. It is the single thing that separates a thinking machine
from a confident bullshitter, and everything else — durable memory, opinions, a
library of what works, eventually real discovery — is built only on verified
claims. A machine is only as trustworthy as the things it refuses to believe.

## What it fuses (both already on this laptop)

- **The memory organ** — from `swechats`. Lessons are *decision-card-shaped*
  (`when / do / avoid / evidence`) and learned from real outcomes. A lesson may
  not enter memory unless it is **grounded**: its claim must share real vocabulary
  with the evidence it cites. This is the anti-fabrication firewall.
- **The thinking organ** — from `alpha-evolver`. Brain-inspired search with
  cognitive modes (**focus / dream / recover**) and an inverted-U *productive
  surprise* signal that drives exploration while **quarantining** results too
  extreme to trust.

## The loop

```
        propose ──▶ verify ──▶ remember ──▶ reflect ──┐
          ▲           │            │            │      │
          │      (the gate)   (grounded)   (pick mode) │
          └──────────────── next generation ──────────┘
```

`propose` (a proposer — offline mutation today, an LLM reasoning core next) →
`verify` (a domain verifier; nothing skips it) → `remember` (only grounded
lessons + an elite pool persist) → `reflect` (read search health, choose the next
cognitive mode). Recall is **re-verified**, never blindly trusted.

## Status (honest)

The kernel is real and runs end-to-end with zero dependencies. `mentat/demo.py`
is a deliberately small, cheap-to-verify domain (symbolic rediscovery) so the whole
machine runs in seconds with no API key. On it:

```
COLD (no memory)   solved 1/5 seeds   median 52 gens
WARM (memory)      solved 5/5 seeds   median  1 gen
```

Memory turns a 1-in-5 search into 5-in-5. Known wrinkle, kept on purpose: **naive
memory can hurt** (negative transfer — entrenching a bad basin). That is exactly
why the critic gate, quarantine, and dream-mode escape exist. We do not hide it.

### The brain is wired in

`mentat/think.py` replaces the mutation proposer with a real reasoning core
(`claude-opus-4-8`, adaptive thinking). Same loop, same gate, same memory — but
candidates now come from reasoning about the data. The core sees the samples,
never the hidden law, and every candidate it proposes is still re-verified:

```
core proposed: x**3 - 2*x + 1; x*x*x - 2*x + 1; 1 + x*(x*x - 2); ...
-> SOLVED in 1 generation   (the offline mutation proposer needed ~52)
```

It is never trusted because the model said so — only its *verified* output is
kept, and a network/API failure degrades to the offline proposer (the loop never
starves).

### A real verifier: math discovery

`mentat/discover.py` points the loop at real mathematics: the largest Sidon set
in [1, n] (a set whose pairwise sums are all distinct). The core proposes a
**construction as Python code**; the verifier **executes it in a sandbox and
exhaustively searches for a counterexample** (two pairs with equal sum), checked
at two sizes so a hardcoded table can't fake it. Invalid constructions are
quarantined; valid ones enter a verified library.

```
gen 1 focus   best=14   (greedy)
gen 4 dream   best=14   (stalled -> exploration mode)
gen 7 focus   best=15   (core wrote multi-start greedy — a better algorithm)
-> best VERIFIED size 15 in [1,200]; it never claims a size it couldn't prove.
```

### Talk to it: Jarvis

`mentat/jarvis.py` is the personal-ops ring of the hub — the reasoning core with
real tools (time, weather, your research repos, and a remember/recall memory of
your decisions) and a **browser voice UI**: tap the mic, speak, and it speaks back
(Web Speech for speech-to-text in, speech synthesis out). Durable memory survives
restarts — tell it a preference once and it recalls it in a fresh process. Tools
are a registry; Gmail / analytics / calendar slot in the same way.

```bash
python3 -m mentat.jarvis                       # serve the voice UI -> open in Chrome
python3 -m mentat.jarvis --text "how's mentat going?" --say   # one-shot, spoken
```

### Improve your own work: self-research

`mentat/improve.py` turns the loop on the user's *own* project: the core proposes a
Max Cut heuristic in alpha-evolver's DSL, and the verifier is alpha-evolver's own
offline benchmark (`maxcut_lab.evaluate_program`). It beat the baseline —
`move = add(flip_gain, zscore(flip_gain))`, fitness **0.7800 vs 0.7788** — keeping
`steps_per_node` low because it inferred the cost structure, and only claimed the
win after the real eval confirmed it. The discovery engine improving your research,
scored by your research. And now **offline**: a creative mutator over the same DSL
(`CreativeHeuristicProposer`) beats the baseline with **no API** — fitness **0.7813**,
`move = add(flip_gain, abs(same_weight))` — so the loop sharpens your code even with credits out.

### Self-aware, self-improving, and designing — all offline

The system now **knows its own capabilities** (`mentat.selfmodel` — engines, tools, verification
checks, integrations) and **budgets its own work** ("~9h → 12h with a safety buffer", grounded in
*measured* timings). `mentat.work` runs a **verified curriculum that carries proven building blocks
forward** (transfer) across formula synthesis *and* real code, stopping honestly when dry. The
creative loop (`mentat.cognition`) proposes → verifies → remembers → sleeps → gets sharper. And
`mentat.cad` designs a **verified parametric part** — checked analytically for fit, clearance,
strength, and mass — then emits printable OpenSCAD, so it prototypes with **no GPU**. Every one of
these runs with **no API credits**, and Jarvis degrades gracefully to an offline tool router when
the reasoning core is unavailable. See `CREATIVE_JARVIS.md`.

## Roadmap

1. ~~Real proposer — an LLM reasoning core driving the loop.~~ ✓
2. Real verifiers — three flagships:
   - ~~**Math / algorithms** — propose constructions as code, verify by execution +
     exhaustive counterexample search (`mentat.discover`).~~ ✓
   - ~~**Personal-ops Jarvis** — tools + machine control + durable memory + voice (`mentat.jarvis`).~~ ✓
   - ~~**Self-research** — beat alpha-evolver's own Max Cut benchmark (`mentat.improve`).~~ ✓
3. ~~**Transfer** — lessons learned on one problem accelerate a *different* one.~~ ✓
   Measured (`mentat.selfimprove`): warm memory from a family of tasks solves a **held-out**
   target **9/12 vs 6/12 cold** — generalization, not memorization.
4. ~~**Creativity** — novelty, quality-diversity illumination, a tunable risk dial.~~ ✓
   (`mentat.imagine` / `illuminate`; see `CREATIVITY.md`.)
5. ~~**Grounding** — anti-haze RAG that cites or refuses; fast/slow consolidation; a LoRA
   specialization path.~~ ✓ (`mentat.rag` / `consolidate` / `finetune`; see `GROUNDING.md`.)
6. **The hub** — more agents, tools, and channels around the spine. *(ongoing)*

## What's built (every claim backed by runnable, tested code)
A verification-gated kernel plus grounded anti-fabrication memory; a creativity engine
(novelty, quality-diversity **illumination**, productive surprise, a tunable risk dial —
ported from `alpha-evolver`); **anti-haze RAG** (cites sources or refuses); **fast/slow
memory consolidation** (Complementary Learning Systems); a **LoRA** specialization path;
**measured self-improvement**; and a full-authority autonomy mode. Honest headline results:
a verified Sidon-set frontier (math); on real S&P 500, **0/12 strategy facets survived
3,840 deflated out-of-sample tests** (the anti-overfit map — where naive search would "find"
false edges); transfer memory solves a held-out task **9/12 vs 6/12**. See `PAPER.md`.

## Run it

```bash
python3 -m mentat              # one front door: what's live + every engine
python3 -m mentat list        # engine names
python3 -m tests.test_core    # 62 tests, no dependencies, no network

# a few engines (offline + deterministic unless noted):
python3 -m mentat selfimprove   # MEASURED learning: cold vs warm + transfer
python3 -m mentat illuminate    # MAP-Elites: a diverse portfolio of verified designs
python3 -m mentat realm         # map a market until dry (deflated-OOS gate)
python3 -m mentat rag "what is the deflated sharpe ratio?"   # grounded QA: cites or refuses

# the live reasoning core (Claude) needs an API key (env / .env / Keychain):
python3 -m mentat think         # rediscover a hidden law with the live core
python3 -m mentat discover      # discover a verified Sidon set with the live core
```
