# Overnight autonomous session — 2026-06-16

**Mandate (from the user, going to sleep ~01:38, waking ~10:00):** keep working
autonomously for ~8 hours. Make Mentat *function like Claude Code* (reliable
agentic tools + coding) and *think like a brain* (supreme grounded memory, novel
discovery, brain-inspired modes — using everything on this laptop). Full control
and judgement granted. Be impressive by morning.

Rules I'm holding myself to:
- Every change goes through git, committed in small reviewable steps. Never commit
  broken code — run the tests (and live checks) first.
- No destructive or irreversible actions; only touch `~/mentat` (read-only use of
  swechats/alpha-evolver). No account creation, no money spent beyond the LLM API.
- Quality over churn. Verify findings adversarially before acting on them.

## Roadmap (worked top-to-bottom, revised as I learn)

1. **Harden & fix** — audit the whole codebase, fix verified bugs, add error
   handling, Jarvis conversation context management.
2. **The Hub** — let Jarvis orchestrate the cognitive engines: tools that run the
   math-discovery loop, the self-research loop, and the kernel. Jarvis becomes the
   central hub (reasoning core → specialist engines → tools), à la the vision.
3. **Supreme memory** — give Jarvis the grounded decision-card memory (learns
   durable lessons from corrections, firewalled against fabrication) + a sleep/
   consolidation pass that distills experience into lessons.
4. **Novel thinking, deeper** — more discovery domains (cap sets, bin packing),
   a transfer experiment (lessons from one problem help a different one).
5. **Claude-Code-like coding agent** — `edit_file`, planning/todo, a stronger
   agentic loop so Jarvis can do real multi-step coding tasks.
6. **Polish** — comprehensive tests, architecture docs, a final report.
7. **Completeness critic loop** — keep finding and closing gaps until ~10:00.

## Log

- **01:38** — Session start. Restarted Jarvis (hardened audio fallback live).
  Wrote this log + roadmap. Kicking off Phase 1: a multi-agent audit of the whole
  codebase (find real bugs + high-value improvements, adversarially verified).
