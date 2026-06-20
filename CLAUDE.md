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
  ANTHROPIC_API_KEY from env / `.env` / Keychain), `elevenlabs_tts`, JSON/code extractors.
- `secrets.py` — credential layer so the system USES keys you authorized without re-entering
  them: `get_secret(NAME)` resolves env -> macOS Keychain -> gitignored `.env`. Store one with
  `python3 -m mentat.secrets set NAME` (typed hidden, saved to Keychain; values never logged).
  Jarvis reads ELEVENLABS/BRAVE/Anthropic keys through it. Not for bypassing anyone's security —
  only surfaces credentials you stored yourself.
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
  tool-use loop + **18 tools** (see below) + `Jarvis.operate()` MANDATE mode (full-authority
  autonomous task executor) + `integrations_report()`. The big one.
- `research.py` — the research AUTOPILOT: hand it a time budget (`--minutes N`) and walk away.
  Loops the gated discovery engines (Sidon frontier, market topics, design illumination),
  keeps only verifier-proven results, accumulates best-ever into a persistent journal
  (`research_journal.json`), writes up what held. Also a Jarvis tool (`run_research`), so
  mandate mode can launch an overnight run.
- `realm.py` — the REALM-MIND (toward "omniscient in one realm", honestly): maps a market
  across a broad facet space, gates every hypothesis (deflated-OOS), accumulates a PERSISTENT
  knowledge map of verified edges + ruled-out facets, LOOPS UNTIL DRY, reports coverage +
  open frontier + the honest "edges are provisional" caveat. `--data <csv>` for a real market.
  On real S&P 500: 0/12 facets survived 3,840 gated hypotheses — the honest anti-overfit map.
- `imagine.py` — the CREATIVE SYNTHESIZER: Boden's creative operators (blend/invert/transfer/
  reshape/specialize) over the alpha DSL, fired by the brain's modes, synthesizing novel
  hypotheses FROM the verified knowledge base (creativity compounds) — plus an `LLMImaginer`
  that invents a novel concept+rationale. Imagine boldly, verify everything. See `OVERNIGHT_CREATIVITY.md`.
- `rag.py` + `embed.py` + `finance_docs/` — grounded finance QA (anti-haze): HYBRID retrieval
  (BM25 + embedding cosine; `embed.py` is semantic via model2vec/sentence-transformers if installed,
  else a dependency-free hashing embedder), answers ONLY from retrieved passages WITH citations, and REFUSES when no
  source is relevant. Jarvis tool `finance_qa`. See `GROUNDING.md`. `python3 -m mentat.rag "..."`.
- `selfimprove.py` — MEASURED self-improvement: cold-vs-warm + TRANSFER. Warm verified
  memory solves a held-out task 9/12 vs cold 6/12 (generalization, not memorization), and
  recalls a known solution instantly. The "really learns" thesis, quantified. `python3 -m mentat.selfimprove`.
- `consolidate.py` — the brain's SLEEP (Complementary Learning Systems): replays the FAST
  grounded memory, strengthens corroborated lessons, abstracts recurring ones into principles,
  prunes the weak, and exports a consolidation dataset for the SLOW LoRA step. Only verified
  memory consolidates. `python3 -m mentat.consolidate`.
- `finetune/` — the LoRA path (cheap one-time specialization, NOT from-scratch): `prepare_data`
  builds a chat-format finance instruction set from the corpus; `train` runs LoRA free + local
  on Apple Silicon via mlx-lm (or prints the command). See `finetune/README.md`. (model2vec is
  installed in the swechats venv, so `rag` there uses true semantic embeddings.)
- `operate.py` — runner: "you have full authority to <task>" and Mentat does it itself.
  `python3 -m mentat.operate "<task>"` runs a bounded, logged, autonomous tool loop to
  completion (safety floor stays on; `--no-guard` to drop it; `--steps N`). Uses stored
  credentials, verifies its own work, reports what (if anything) still needs the human.
- `tests/test_core.py` — **62 tests**, run with the system `python3` (no deps needed).
  Capture the exit code directly (`python3 -m tests.test_core; echo $?`) — piping to `tail`
  masks a failing exit.

## The flagships (all proven, all in git history)
1. **Math discovery** (`mentat.discover`) — found a verified Sidon set 14→15 in [1,200].
2. **Self-research** (`mentat.improve`) — beat the alpha-evolver baseline (fitness 0.7800 vs 0.7788).
3. **Jarvis** (`mentat.jarvis`) — the assistant.
4. **Anti-overfit alpha discovery** (`mentat.trade`) — found a robust mean-reversion alpha
   (deflated worst-regime OOS Sharpe +1.66) while momentum/always-long/decoys were killed by
   the OOS+cost+deflation gate. Synthetic testbed; real OHLCV plugs in.

## Jarvis tools (20)
`get_datetime`, `get_weather`, `research_status`, `remember`/`recall` (flat notes),
`learn_lesson` (durable GROUNDED rules from corrections — injected into every future
chat), `shell`, `applescript`, `read_file`, `write_file`, `edit_file` (surgical,
syntax-checked, optional verify_cmd + ROLLBACK on failure), `web_search` (+Brave-ready),
`web_fetch`, `add_reminder`, `calendar_today`, `improve_maxcut` + `discover_sidon` +
`run_research` (the Hub — dispatch real verified discovery + the overnight autopilot).

## How to run
- **Tests** (any python, no deps): `cd ~/mentat && python3 -m tests.test_core`
- **Offline demo**: `python3 -m mentat.demo`
- **Anything using the reasoning core / engines** needs `anthropic` + (for the engines)
  `numpy` + `~/alpha-evolver`. The system `python3` (3.14) has neither; the **swechats
  venv** has both (anthropic 0.107.0, numpy 2.4.6). The ANTHROPIC key lives in
  `~/swechats/.env`. Standard incantation:
  ```bash
  cd ~/mentat && set -a && . ~/swechats/.env && set +a && \
    ~/swechats/.venv/bin/python -m mentat.<think|discover|improve|trade|creativity|illuminate|discover_diverse|curriculum|research|operate|realm|imagine|rag|jarvis>
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
