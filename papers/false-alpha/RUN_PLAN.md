# Run plan — the LLM false-discovery study

Companion to `PAPER.md`. How to (re)produce every number, run the pre-registered live-LLM
arm with the creativity engine, and extend the study. All commands run from `~/mentat`.

> **Jarvis is always-on via launchd — do not restart it.** Everything here runs as a
> separate, short-lived `python3 -m mentat.*` process. None of it touches `run-jarvis.sh`,
> the launchd agent, or any Jarvis state. No `launchctl`, no kill, no restart.

---

## Stage 0 — reproduce the offline result + verification (done; no API key needed)

```bash
cd ~/mentat
python3 -m mentat.nsweep --pool 4000 --data data/fred_SP500.csv \
        --out papers/false-alpha/nsweep_results.json   # the §4 sweep
python3 papers/false-alpha/verify.py                   # 17-check adversarial suite (17 PASS)
python3 papers/false-alpha/power.py                    # the gate power curve (§4.5)
```

- Deterministic (CRC-seeded; two runs are byte-identical — verified).
- ~45 s, pure Python, no dependencies, no network.
- Produces the four-market (planted / small_planted / noise / real) × generator sweep,
  the correlation-based effective-trials (ρ̄, N_eff), and `nsweep_results.json`.
- `verify.py` cross-checks the headline through the real engine gate, cost/target/regime
  sensitivities, DJIA + NASDAQ, and the independent `curriculum.study`.

Controls only (planted + small_planted + noise, faster): `python3 -m mentat.nsweep`.

---

## Stage 1 — the live-LLM arm (DONE; reproduces free from cache)

This swaps the **live LLM imaginer** (`imagine.LLMImaginer`, Claude Opus 4.8 via the
Anthropic API) in as the generator. It has been **run** (§4.4): H1, H3, H4 confirmed, H2
refuted. The LLM-proposed pools are cached at `papers/false-alpha/llm_cache_*.json`, so the
command below reproduces the arm with **zero API calls**; delete the cache to draw cold.

**Key:** the always-on Jarvis service sources its key from `~/swechats/.env`; reuse it for a
cold draw without touching the daemon:
```bash
cd ~/mentat
set -a && . "$HOME/swechats/.env"; set +a            # load the key into this shell only
"$HOME/swechats/.venv/bin/python" -m mentat.nsweep --pool 300 --llm \
    --data data/fred_SP500.csv --out papers/false-alpha/nsweep_results_llm.json
```
(Or, from any env with `anthropic` + `ANTHROPIC_API_KEY` set:
`python3 -m mentat.nsweep --pool 300 --llm --data data/fred_SP500.csv --out …`.)
Verify the core is live: `python3 -c "from mentat.reasoning import core_available; print(core_available())"  # -> True`

**Run (pre-registered settings):**
```bash
# Smaller pool for the LLM arm (cost): N-sweep to 300 is enough to show the curve.
python3 -m mentat.nsweep --pool 300 --llm --data data/fred_SP500.csv \
        --out papers/false-alpha/nsweep_results_llm.json
```

- The `llm` generator draws in batches of 16 from `LLMImaginer.propose`, each batch
  imagining from the problem **brief** with a **fresh empty memory** (no elite feedback)
  so the draws approximate the LLM's *cold* proposal distribution — "LLM as generator,"
  not an adaptive evolutionary loop. (Model: whatever `AnthropicCore` defaults to; uses
  the latest Claude per the repo's `reasoning.py`.)
- If no key/SDK is present the arm prints a clear skip line and the offline arms still run
  (already verified). So this command is safe to run regardless.
- **Token budget / stop rule (pre-registered):** pool = 300 (≈ 19 batches/market × 3
  markets ≈ 57 calls, ≤ ~2,500 output tokens each). Stop at pool; do not loop. If a batch
  errors, `LLMImaginer` falls back to the offline creative proposer for that batch (logged)
  — note the fallback count in the writeup; if fallbacks exceed 20%, re-run that market.

**Pre-registered hypotheses** (write these down *before* looking at the output):
- **H1** live-LLM bestOOS rises with N like the offline arms (same data-snooping).
- **H2** live-LLM n_eff < random's (LLM proposals cluster around "sensible" ideas → more
  correlated → fewer effective trials).
- **H3** live-LLM survivors remain **0** on real S&P 500 at all N.
- **H4** on the planted market, the live LLM recovers the edge at *smaller* N than random
  (creativity as sample-efficiency *when there is something to find*).

Confirming H1–H3 (and ideally H4) completes the paper's claim for a real LLM.

---

## Stage 2 — robustness sweeps (strengthen, optional)

All reuse the same engine; each is one command + a note in §6.

1. **Other real markets** (does the zero hold beyond the S&P?):
   ```bash
   python3 -m mentat.nsweep --pool 4000 --data data/fred_DJIA.csv     --out .../nsweep_djia.json
   python3 -m mentat.nsweep --pool 4000 --data data/fred_NASDAQCOM.csv --out .../nsweep_nasdaq.json
   ```
   NASDAQ has ~14k bars (1971–) → more regimes, a stronger test.
2. **Cost / target sensitivity:** edit `COST` (e.g. 0.0005, 0.002) and `TARGET` (0.0, 0.5,
   1.0) at the top of `nsweep.py`; confirm survivors stay 0 on real across the grid.
3. **Creativity risk dial:** the offline creative arm runs at risk = 0.7. Sweeping
   `creative_alpha(..., risk=r)` for r ∈ {0.2, 0.5, 0.9} shows whether bolder synthesis
   buys any real survivors (expected: no — only more novel mirages). Ties Q3 to the
   `imagine.creativity_ablation` result already in the repo.
4. **Distribution-free multiple testing:** add a White Reality Check / Hansen SPA bootstrap
   alongside the parametric DSR haircut, to remove the Gumbel-approximation caveat (§6).

---

## Stage 3 — how the existing mentat engines tie in

The N-sweep is the *controlled experiment*; these are the same gate in "discovery" mode and
are the qualitative backdrop (the "0 of 12 facets / 3,840 hypotheses" headline):

```bash
python3 -m mentat.realm --data data/fred_SP500.csv          # map facets until dry
python3 -m mentat.realm --report                            # the accumulated realm map
python3 -m mentat.curriculum --data data/fred_SP500.csv     # facet-by-facet study
python3 -m mentat.imagine                                   # creativity ablation (B2)
```

- `realm.py` / `curriculum.py` = the 12-facet, 3,840-hypothesis null that the paper
  generalizes into an N-sweep with controls.
- `imagine.py` = the creativity engine (offline `CreativeProposer` + live `LLMImaginer`);
  `creativity_ablation()` is the risk-dial evidence for Q3.

---

## Stage 4 — assemble for submission

1. Final figures from the JSON: best-of-N curve (bestOOS vs N, all markets), survivors vs N
   (the flat-zero on real next to the rising planted), robust-vs-survivors ablation bar, and
   n_eff vs N. (A small `plot.py` over `nsweep_results*.json` — matplotlib — is the only
   added dependency, and only for the camera-ready.)
2. Fold the live-LLM arm (`nsweep_results_llm.json`) into §4 and resolve §7 into results.
3. Convert `PAPER.md` → the venue's format. Suggested first target: a NeurIPS/ICML/ICLR
   **workshop** on ML-for-finance or evaluation/robustness, or **ACM ICAIF** student track;
   arXiv cs.LG preprint (q-fin.ST cross-list via an endorser) in parallel; SSRN for the
   finance audience. Label as workshop/preprint, not a journal article.
4. **Before submission, resolve the authorship flag** in §9 and in memory
   `research-paper-plan.md`: the "CRRA/Heston with a Yale professor" item is *not* part of
   this paper and must not be implied. This paper stands on its own as sole-authored work.

---

## What needs you (decisions / inputs)

- **The API key** for Stage 1 (and which Claude model, if not the repo default).
- **Whether to run Stage 2** breadth now or after the live-LLM arm.
- **Endorser** for an arXiv q-fin.ST cross-list (cs.LG needs none).
