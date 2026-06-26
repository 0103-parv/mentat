# Submission package — IEEE PDF + SSRN posting (do this today)

Everything you need to (a) turn the IEEE LaTeX into a polished PDF, and (b) post that PDF to
SSRN. The final clicks are yours — SSRN publishes permanently under your name and is indexed,
so it must be your account and your decision. I can't (and shouldn't) submit it for you.

---

## STEP 1 — Make the PDF (Overleaf, ~2 minutes, free, no install)

1. Go to https://www.overleaf.com → sign in (free) → **New Project → Upload Project**.
2. Upload `false_alpha_ieee.tex` (this folder). Overleaf already includes the `IEEEtran`
   class — nothing else to install.
3. Top-left menu → **Compiler: pdfLaTeX** → click **Recompile**. (Compile twice so the
   references resolve.)
4. **Download PDF.** That's your submission file. It is a standard 2-column IEEE conference
   layout.

> Single-column alternative: finance/SSRN readers often expect single column. If you prefer
> that look, change line 1 of the .tex from `\documentclass[conference]{IEEEtran}` to
> `\documentclass[journal,onecolumn]{IEEEtran}` and recompile. (You asked for IEEE, so the
> default 2-column is what's set.)

## STEP 1b — VERIFY two references before final submission (30 seconds each)
Two entries are flagged with `% VERIFY` in the .tex because I reconstructed them from a
literature search, not the source page:
- **[finsaber]** arXiv:2505.07078 — confirm the exact title and full author list at
  https://arxiv.org/abs/2505.07078 and paste them in.
- **[alphaagent]** arXiv:2502.16789 — confirm the author list (title is verbatim-correct) at
  https://arxiv.org/abs/2502.16789.
Everything else (White, STW, Hansen, Bailey–López de Prado, Politis–Romano, Lo, Nyholt,
Li–Ji, Romano–Wolf, Harvey-Liu-Zhu) is standard and accurate.

---

## STEP 2 — Post to SSRN (you, ~15 minutes)

1. https://www.ssrn.com → **Sign in / create account** (free).
2. Top menu → **Submit a Paper** (SSRN "Submit" / "Upload").
3. Network/Subject: **Financial Economics Network (FEN)**; also tick **Econometrics** and
   **Machine Learning eJournal** if offered. (FEN is the right home for this.)
4. Upload the PDF from Step 1. SSRN accepts any PDF — no formatting requirement.
5. Paste the metadata below.
6. Submit. SSRN reviews briefly (usually 1–2 business days) before it goes live — so
   submitting today = live this week, with a citeable abstract page and a timestamp that
   establishes priority.

### Title
More Strategies, Same Zero: Does LLM-Scale Alpha Search Discover Edge or Manufacture False
Discoveries?

### Abstract (plain text — paste as-is)
Large language models can propose and backtest trading strategies at effectively unbounded
scale, reviving backtest overfitting in a regime where the number of trials N is enormous and
cheap. We ask whether scaling generative strategy search accumulates genuine edge or only
false discoveries that vanish under proper multiple-testing correction. Using a
dependency-free alpha engine with a strict verifier (causal next-bar execution, transaction
costs, worst-of-regimes out-of-sample Sharpe, and a deflated-Sharpe haircut), we sweep N from
10 to 3,000 across three generators — uniform-random, evolutionary "creative" synthesis, and a
live LLM (Claude Opus 4.8) — on four controls (strong/small planted edge, pure noise, real
data). The naive best-of-N Sharpe rises with N on every market including pure noise; the gate
holds survivors at exactly zero on the real S&P 500 at all N and all generators, while
recovering a strong planted edge. A power surface shows the detectable-edge threshold rising
about sqrt(2 ln N), so moderate real edges become unprovable at scale. The zero generalizes
under a distribution-free block bootstrap, on a real cross-sectional equity panel, and across
FX, gold, and crypto — seven real markets, zero survivors. We derive the worst-of-regimes
deflation the gate actually needs (the standard single-Sharpe deflated Sharpe over-deflates
the minimum-over-regimes statistic by about 2.4x) and a robustness-dividend identity:
requiring a strategy to survive worst-of-k independent regimes is equivalent to a single-Sharpe
search over only about 7 strategies, an implicit multiple-testing correction that collapses as
regimes correlate (measured: regime correlation 0.67 on real S&P, equivalent search size about
84). We report four refutations, including two analytic effective-trial-count shortcuts that
manufacture false discoveries and are corrected by the bootstrap. We do not claim market
efficiency; we claim that LLM-scale search manufactures false discoveries while the only
correction that stops them simultaneously renders moderate genuine edges unprovable. All
results are reproducible from committed scripts; a verification suite of 20 adversarial checks
and 38 unit tests is green.

### Keywords
backtest overfitting; deflated Sharpe ratio; multiple testing; data snooping; large language
models; false discovery; quantitative trading; reproducibility; extreme value theory

### JEL Classification Codes
C12 (Hypothesis Testing); C15 (Statistical Simulation, Bootstrap); C45 (Neural Networks);
C58 (Financial Econometrics); G14 (Market Efficiency); G17 (Financial Forecasting)

### Author
Parv Mehndiratta — Independent Researcher. (Affiliation: as you wish to list it.)

### Suggested "Date written"
2026 — and note in the SSRN comments field that code/data are available on request, which
SSRN reviewers and readers like.

---

## After SSRN: the rest of the publication path
- **arXiv** (cs.LG; cross-list q-fin.ST): cs.LG needs no endorser — post the same PDF. The
  q-fin.ST cross-list needs an endorser (a Stanford contact could help; not a blocker).
- **ACM ICAIF** (the on-topic venue): note ICAIF uses the ACM `sigconf` template, not IEEE —
  easy swap from this .tex if/when you target it (Aug deadline).
- Keep the working paper (`PAPER.md`, v0.4) as the long-form companion / appendix.
