# Creative Jarvis — self-aware, self-improving, verifier-gated

The upgrade from "a chatbot with tools" to a system that **knows what it can do, budgets its own
time, improves itself, and designs/discovers — with a verifier between every idea and belief.**
Built to do honestly what the driftworks J.A.R.V.I.S. only markets: real creative reasoning, real
self-improvement, real grounding. Everything here runs **offline with no API credits.**

## What's new

| Capability | Engine / tool | What it does | Verified result |
|---|---|---|---|
| **Self-awareness** | `selfmodel` · `capabilities` | Introspects its own engines, tools, verification checks, integrations | "22 engines, 22 tools, 71 checks", with honest limits |
| **Time budgeting** | `selfmodel` · `estimate_effort` | Estimates effort from MEASURED timings, recommends a budget + safety buffer | "9h → 12h budget (25% buffer)" |
| **Self-improvement** | `work` · `work_on` | A verified curriculum, memory carried forward (transfer), honest dry-stop | hard-cubic uncrackable cold (0/3) → solved via carried memory |
| **Creative loop** | `cognition` · `creative_think` | propose → verify → remember → sleep → sharper | discovers a law in round 4; warm 3/3 vs cold 1/3 |
| **Code & algorithms** | `improve` (offline) | Offline creative search over the Max Cut program DSL | baseline 0.7788 → **0.7813**, no API |
| **Engineering / CAD** | `cad` · `design_part` | Parametric part as code, verified analytically, emits OpenSCAD | verified 100×25×3mm bracket, 19.5g, printable |
| **Robust Jarvis** | `jarvis` | Degrades gracefully offline (no SDK/credits) — tools still work | no crash; offline intent router |

## The throughline: a verifier between every idea and belief

Nothing becomes memory, an opinion, an "improvement", or a design until a verifier passes it.
That is the one thing the marketing-grade assistants skip, and it is what makes "novel thinking"
trustworthy instead of confident nonsense. The honest corollary: novel thinking is only
*certifiable where a verifier exists* — math, code, CAD-with-physics, markets. Elsewhere the system
brainstorms but won't claim certainty. That honesty is the product.

## Run it (all offline, no credits)

```bash
python3 -m mentat                       # the front door: every engine
python3 -m mentat cognition             # the creative self-improvement loop
python3 -m mentat work                  # budgeted self-improvement (curriculum + real code)
python3 -m mentat cad                   # design a verified part, print the OpenSCAD
python3 -m mentat selfmodel             # capabilities + effort estimates
~/swechats/.venv/bin/python -m mentat improve --fresh   # offline beat the Max Cut baseline (needs numpy)
python3 -m mentat.jarvis --text "what can you do"        # offline Jarvis
```

## Honest limits (the real bottlenecks)

1. **Verifier-bounded novelty** — trustworthy only where the answer can be checked.
2. **Offline saturation** — the offline creative search exhausts toy domains; richer exploration
   needs API credits (the LLM proposer) or new domains. The system says so rather than padding.
3. **Hardware wall** — real-time vision / 3D rendering / large local models need hardware not
   present; CAD-as-code routes around it by staying in verified code.

See `AUTONOMOUS_SESSION3.md` for the block-by-block build log.
