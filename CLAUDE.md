# Mentat — project guide for Claude Code

Read this first. It is the canonical context for this repo so a fresh session knows
everything without re-deriving it.

## What this is
**Mentat** is a *verification-gated cognitive kernel*: a `propose → verify → remember →
reflect` loop where nothing becomes memory, an opinion, or an action until a **verifier**
passes it. That gate is the whole thesis — it is what separates a thinking machine from a
confident bullshitter. Built by fusing two of the user's existing projects:
`~/swechats` (grounded decision-card memory + anti-fabrication firewall) and
`~/alpha-evolver` (brain-inspired search: focus/dream/recover modes + an inverted-U
"productive surprise" signal). Repo: **github.com/0103-parv/mentat** (private).

The vision the user is driving toward: a system that (a) *functions like Claude Code*
(reliable agentic tools + coding) and (b) *thinks like a brain* (supreme grounded memory,
novel verified discovery). This is also research/admissions currency for the user (a rising
high-school senior; see the swechats-project memory + ~/college-strategy).

## Modules (`mentat/`)
- `core.py` — the kernel: `Problem`/`Verdict`, `Memory` + `Lesson` (decision-card-shaped,
  grounded, anti-fabrication firewall), `Mind` (modes + surprise), `solve()`, and the
  **creativity engine** `BrainConfig` (novelty / quality-diversity pool / productive surprise
  / extreme-surprise quarantine / sleep / motifs — ported from alpha-evolver/Codex,
  ablatable; `solve(brain=None)` is the plain kernel). Zero deps.
- `reasoning.py` — `AnthropicCore` (Claude-backed proposer), `_load_key` (reads
  ANTHROPIC_API_KEY from env or a `.env`), `elevenlabs_tts`, JSON/code extractors.
- `demo.py` — symbolic-rediscovery domain (offline mutation proposer + `LLMProposer`).
- `math_lab.py` — Sidon-set discovery: sandboxed (spawned, resource-capped, hard-killable
  child process) execution of model code + exhaustive counterexample search.
- `discover.py` — runner: discover a verified Sidon set.
- `self_research.py` + `improve.py` — improve the user's OWN `~/alpha-evolver` Max Cut
  heuristic, scored by alpha-evolver's own offline `maxcut_lab.evaluate_program`.
- `trade_lab.py` + `trade.py` — anti-overfit alpha discovery (VISION.md flagship): an alpha
  DSL + a walk-forward, cost-aware, multi-regime, **deflated-Sharpe** OOS verifier. Pure
  Python. Verification IS the anti-overfit gate. Synthetic universe by default;
  `AlphaProblem(bars=...)` takes real OHLCV.
- `think.py` — runner: rediscover a hidden law from samples.
- `creativity.py` — runner: the novelty ablation (brain off vs on). Shows novelty is an
  explore/exploit dial — diversity for free at the default. See `CREATIVITY.md`.
- `illuminate.py` — runner: **MAP-Elites illumination**, the clean creativity win. A greedy
  maximizer returns ~5 designs; illumination returns ~18 distinct verified designs across a
  behavior space (a portfolio, not a point). Uses the kernel's `Problem.behavior` hook + archive.
- `discover_diverse.py` — illuminated MATH: a diverse catalog of *proven* Sidon sets (the
  size-vs-span frontier), each exhaustively verified. Creativity on a real domain.
- `curriculum.py` — **topic mastery**: study a domain (the stock market) facet by facet —
  search, backtest every hypothesis (OOS+cost+deflation), keep verified findings as grounded
  lessons, record honest negatives, move on. One memory carried across facets; each facet
  isolated so findings are attributable. `--data <csv>` studies a real market.
- `jarvis.py` — the personal-ops hub: browser voice UI (Web Speech) + a manual Anthropic
  tool-use loop + **17 tools** (see below). The big one.
- `tests/test_core.py` — **44 tests**, run with the system `python3` (no deps needed).
  Capture the exit code directly (`python3 -m tests.test_core; echo $?`) — piping to `tail`
  masks a failing exit.

## The flagships (all proven, all in git history)
1. **Math discovery** (`mentat.discover`) — found a verified Sidon set 14→15 in [1,200].
2. **Self-research** (`mentat.improve`) — beat the alpha-evolver baseline (fitness 0.7800 vs 0.7788).
3. **Jarvis** (`mentat.jarvis`) — the assistant.
4. **Anti-overfit alpha discovery** (`mentat.trade`) — found a robust mean-reversion alpha
   (deflated worst-regime OOS Sharpe +1.66) while momentum/always-long/decoys were killed by
   the OOS+cost+deflation gate. Synthetic testbed; real OHLCV plugs in.

## Jarvis tools (17)
`get_datetime`, `get_weather`, `research_status`, `remember`/`recall` (flat notes),
`learn_lesson` (durable GROUNDED rules from corrections — injected into every future
chat), `shell`, `applescript`, `read_file`, `write_file`, `edit_file` (surgical,
syntax-checked, optional verify_cmd + ROLLBACK on failure), `web_search` (+Brave-ready),
`web_fetch`, `add_reminder`, `calendar_today`, `improve_maxcut` + `discover_sidon` (the
Hub — dispatch real verified discovery).

## How to run
- **Tests** (any python, no deps): `cd ~/mentat && python3 -m tests.test_core`
- **Offline demo**: `python3 -m mentat.demo`
- **Anything using the reasoning core / engines** needs `anthropic` + (for the engines)
  `numpy` + `~/alpha-evolver`. The system `python3` (3.14) has neither; the **swechats
  venv** has both (anthropic 0.107.0, numpy 2.4.6). The ANTHROPIC key lives in
  `~/swechats/.env`. Standard incantation:
  ```bash
  cd ~/mentat && set -a && . ~/swechats/.env && set +a && \
    ~/swechats/.venv/bin/python -m mentat.<think|discover|improve|trade|creativity|illuminate|discover_diverse|curriculum|jarvis>
  ```
- **Jarvis server** runs at `http://localhost:8765` (open in Chrome). Restart it (in the
  background) whenever `jarvis.py` changes; the browser caches the old UI, so hard-refresh.

## Conventions / rules
- **Never commit broken code** — run `python3 -m tests.test_core` first. Small, reviewable
  commits. End git commit messages with the Co-Authored-By trailer.
- Kernel/demo/tests stay **dependency-free**; numpy/anthropic are optional (engines only).
- Runtime artifacts are gitignored: `memory.json`, `jarvis_memory.json`, `jarvis_lessons.json`,
  `jarvis_actions.log`, `jarvis_conversation.jsonl`, `maxcut_memory.json`, `think_memory.json`.
- Default model is `claude-opus-4-8` (house rule; `MENTAT_MODEL` overrides). For LLM-shaped
  work consult the `claude-api` skill.
- The catastrophic-command guard in `jarvis.py` (`_is_catastrophic`) blocks deletes of `/`,
  system roots, ANY direct child of `$HOME`, and credential subtrees (~/.ssh etc.); deeper
  dev deletes are allowed. `JARVIS_NO_GUARD=1` removes the floor.

## Current state & open items
- Phases done overnight (2026-06-16, ~01:40–03:05): **1** hardening (38-finding audit fixed),
  **2** grounded memory in Jarvis, **3** the Hub, **4** review fixes + `edit_file`. See
  `OVERNIGHT_LOG.md` for the full changelog.
- **Needs the USER**: the ElevenLabs key they added lacks the `text_to_speech` permission
  (401) — regenerate with "Has access to all", put it in `~/swechats/.env` as
  `ELEVENLABS_API_KEY=...`, restart Jarvis → human voice. Optional: `BRAVE_API_KEY` for live
  web search. (Boundaries held: no bypassing passwords/security, no creating accounts as the user.)
- Remaining roadmap: deepen "think like a brain" (a 2nd discovery domain e.g. cap sets; a
  transfer experiment; a consolidation/sleep pass) and polish (architecture doc). A few
  cosmetic audit lows remain (log wording, a non-true median).
