# Autonomous session 4 — 2026-06-22 (LIVE BRAIN, ~16:5x PDT start)

**Mandate (user, leaving, full permission):** the API works now, so genuinely improve the system
autonomously with the live brain while away. Keep Jarvis up. Improve itself.

**Cost discipline I hold myself to (the user has ~$20 of credits):**
- Use a CHEAP model for the grind (Sonnet 4.6, not Opus) — Jarvis stays on Opus for the user.
- Bounded blocks; only a few dollars total. If any call returns "credit balance too low", STOP.
- Commit ONLY genuinely verified gains — no theater, no padding.
- Verify before believing; every block ends green; small commits; logged here.
- Only ~/mentat (+ read-only swechats/alpha-evolver/venv/data). No destructive actions.

## Roadmap (live-brain discovery; re-pick highest-value each block)
1. **Live Max Cut improvement** — beat the offline best (0.7813) with the LLM proposer.
2. **Live math discovery** — push a harder construction (Sidon past 15 / cap set) with the core.
3. **Research autopilot** with the live core (bounded), keep only proven findings.
4. **Creative synthesis (imagine)** with the live brain on a verifier-backed domain.
5. Stop when budget-aware OR genuinely dry; leave a wake-up summary.

## Log
- **block 1 (live Max Cut) — STOPPED, honest finding.** One live propose with Sonnet takes ~50s
  and the first batch only matched baseline (0.7788); the offline search already pushed Max Cut to
  0.7813 (near-optimal). So live discovery on the saturated domains is SLOW + MARGINAL + a steady
  drain on the user's ~$20. Decision: do NOT grind credits on it — keep the $20 for the user's
  interactive Jarvis (Opus), and spend the autonomous time on FREE codebase improvements (the agent
  runs on a separate budget, so improving mentat's code costs the user's credits nothing) + keeping
  Jarvis up. This is the responsible reading of "improve itself" given the budget.
- **block 2 (16:5x) — SEMANTIC memory recall (free).** Jarvis auto-recall now ranks durable
  notes by embedding similarity (model2vec under the venv) instead of keyword overlap — surfaces
  the relevant memory ("where do I live" -> only San Ramon). +1 test (74 green). Committed 4d353da.
- **block 3 — robustness test** locking in real telemetry + semantic recall. 74 green.
