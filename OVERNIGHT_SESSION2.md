# Overnight session 2 — 2026-06-21

**Mandate (user, going to sleep, Mac kept awake by Amphetamine):** keep developing mentat
all night, get it working, download whatever's needed, use mentat to verify, full
discretion. Work in disciplined committed blocks; keep tests green; log everything here.

**Rules I hold myself to:** every block ends green (`python3 -m tests.test_core; echo $?`),
small commit + push, logged below. Verify before believing. Stop scheduling when the
roadmap is genuinely dry (don't pad). No destructive actions; only ~/mentat (+ read-only use
of swechats/alpha-evolver, the venv, and downloaded data/models).

## Roadmap (re-pick the next undone, highest-value item each block)
1. **Actualize the LoRA fine-tune** (currently scaffold-only): richer finance instruction
   dataset (generate + try a public download), `uv pip install mlx-lm`, run LoRA locally on
   the Mac (free, overnight), verify the adapter improves finance answers. The real "get it
   working" deliverable.
2. **Perf pass**: profile the brain/novelty path; speed up long runs (cache, fewer O(pool^2)
   recomputes). Verify tests green + measurably faster.
3. **Live verified discovery (bounded)**: run discover / improve with the LIVE core for a
   bounded budget; accumulate real verified results (push Sidon past 15; beat the maxcut
   baseline). Persist + report.
4. **Robustness / coverage**: edge-case tests, lint pass, fix any rough edges found.
5. **Self-amplifying loop demo**: wire live propose -> verify -> remember -> consolidate ->
   sharper-next-run into one watchable runner.
6. Stop when dry; leave a clear wake-up summary at the bottom.

## Log
- **start** — Amphetamine confirmed holding the Mac awake; mlx-lm install launched; roadmap set.
- **block 2 (01:00) — LoRA verified + PERF 13.6x (roadmap #1 done, #2 done).** LoRA finished
  (600 iters, val loss 3.35→2.79 — it learned). Verified honestly (base vs adapter on a
  finance question): the adapter shifted STYLE toward finance Q&A but didn't clearly beat the
  base on accuracy — confirms the thesis (LoRA = style/surface; facts belong in RAG; full
  stack = LoRA-style + RAG-facts + gate). Then PROFILED the brain path: the real bottleneck
  was `compute_features` recomputed on every alpha eval (~85% of runtime) though features
  depend only on the bars. Cached features on the Bars instance → **creative solve 0.476s →
  0.035s (13.6x)**; every market engine (trade/realm/curriculum/imagine/research) is now ~13x
  faster. 62 tests green; committed. NEXT: roadmap #3 (bounded live verified discovery).
- **block 1 — LoRA ACTUALIZED (roadmap #1).** Downloaded a real dataset (finance-alpaca,
  68,912 records). Enhanced `prepare_data --extra` to ingest it -> 2412 train / 604 valid
  examples (finance-alpaca + local corpus). Installed mlx-lm (0.31.3). Launched a real LoRA
  fine-tune of Qwen2.5-0.5B-Instruct-4bit on the Mac (free, local): train loss dropping
  3.10 -> 2.65, adapter -> `mentat/finetune/adapters` (gitignored). 62 tests green; committed
  ce73c22. NEXT: verify the trained adapter improves finance answers vs the base model, then
  roadmap #2 (perf) / #3 (live discovery).