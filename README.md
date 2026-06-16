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
scored by your research.

## Roadmap

1. ~~Real proposer — an LLM reasoning core driving the loop.~~ ✓
2. Real verifiers — three flagships:
   - ~~**Math / algorithms** — propose constructions as code, verify by execution +
     exhaustive counterexample search (`mentat.discover`).~~ ✓
   - ~~**Personal-ops Jarvis** — tools + machine control + durable memory + voice (`mentat.jarvis`).~~ ✓
   - ~~**Self-research** — beat alpha-evolver's own Max Cut benchmark (`mentat.improve`).~~ ✓
3. **Transfer** — lessons learned on one problem accelerate a *different* one
   (swechats already has the counterfactual harness to measure it). *(next)*
4. **The hub** — agents, tools, and channels around the spine.

## Run it

```bash
python3 -m mentat.demo      # offline proposer — no dependencies, ~seconds
python3 -m tests.test_core  # 12 tests, no network

# the real reasoning core (needs `pip install anthropic` + an API key):
ANTHROPIC_API_KEY=sk-... python3 -m mentat.think      # rediscover a hidden law
ANTHROPIC_API_KEY=sk-... python3 -m mentat.discover   # discover a verified Sidon set
# the key may instead live in a .env file; MENTAT_MODEL overrides the model.
```
