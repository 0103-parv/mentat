# SUBMISSION PACKAGE — false-alpha paper (ready to publish)

*Built 2026-07-12. The paper is final; the two pre-submit fixes (evaluator-demo estimator + k-dependence)
are integrated and verified. This doc is everything you need to actually post it.*

## The final artifacts
- **`PAPER_FINAL.pdf`** — the submission PDF (full paper, ~14 pp, reflects all fixes). Upload this.
- **`paper_final.html`** — same content as HTML. If you want to regenerate the PDF or tweak styling,
  open this in Chrome → Cmd+P → "Save as PDF."
- Source of truth: `PAPER.md`. Figures: `fig_headline.png`, `fig_verification.png`.

## The metadata (copy-paste fields)

**Title:** More Strategies, Same Zero: Does LLM-Scale Alpha Search Discover Edge or Manufacture False Discoveries?

**Author:** Parv Mehndiratta (sole author). Affiliation: Independent researcher (Dougherty Valley High School).

**Keywords:** backtest overfitting; multiple testing; deflated Sharpe ratio; false discovery rate;
data snooping; large language models; algorithmic trading; strategy search; model evaluation; quantitative finance.

**JEL codes (SSRN asks for these):** G11 (Portfolio Choice; Investment Decisions), G14 (Information and
Market Efficiency), C12 (Hypothesis Testing), C52 (Model Evaluation and Selection), C58 (Financial Econometrics).

**arXiv categories:** primary **cs.LG**, cross-list **q-fin.ST** (Statistical Finance) and **q-fin.TR** (Trading & Market Microstructure).

**Abstract:** use the abstract verbatim from `PAPER.md` §Abstract (it already carries the k-dependence caveat).

## Top 3 venues (decided — from PUBLICATION_ROADMAP.md)

| # | Venue | Type | Needs | Timeline |
|---|-------|------|-------|----------|
| 1 | **SSRN** | preprint, finance/econ audience, no review | free account + upload PDF | **can go live TODAY** |
| 2 | **arXiv** (cs.LG + q-fin.ST cross-list) | preprint, citable, timestamped | account + a one-click **endorser** (a prof who's published in cs.LG) | live within a day of endorsement |
| 3 | **ICAIF 2026** (ACM AI in Finance, Milan) | real peer-reviewed conference | cut to 8pp ACM two-column, double-blind, submit via CMT | **deadline Aug 2, 2026** |

Frame everywhere as an **evaluation/robustness** result (not a market-efficiency claim). The zero is the
setup; the contribution is the derived worst-of-regimes deflation + robustness-dividend + the
cross-generator/live-LLM demonstration.

## SSRN — do this first (fastest real "published" line)
1. Create a free SSRN account at ssrn.com (you have to do this — I can't create accounts).
2. Submit a paper → upload `PAPER_FINAL.pdf`.
3. Paste Title, Abstract, Keywords, JEL codes from above.
4. Classify under the eJournals: **Econometrics: Mathematical Methods & Programming**, **Capital Markets:
   Market Efficiency**, and **Machine Learning eJournal** if offered.
5. Submit. It goes to a short moderation queue (usually < 1–2 business days), then it's live with a citable URL.

## arXiv — needs the endorser (draft below)
arXiv requires a first-time cs.LG poster to be endorsed by someone who has published in cs.LG. You correspond
with several who qualify — **Robert Lange** and **Jeff Clune** are the cleanest fits (both clearly in the
ML/evolutionary space, both replied warmly). Send one of them the short note below. Once endorsed: create the
arXiv account, upload the same PDF, set categories, submit. (Note: arXiv preprints are generally fine with
ICAIF's double-blind — just don't name the preprint in the ICAIF submission; verify their exact policy.)

### Endorser email (send to Robert Lange OR Jeff Clune)
> Subject: Quick endorsement to post my first paper to arXiv (cs.LG)?
>
> Hi [Robert / Professor Clune],
>
> Thank you again for the encouragement earlier. I finished the paper we touched on, on how machine-driven
> strategy search behaves under a strict multiple-testing gate, and I am posting it to arXiv (cs.LG, cross-listed
> to q-fin.ST). As a first-time submitter I need a one-click endorsement from someone who has published in cs.LG.
> Would you be willing? It takes about a minute on arXiv's side, and I would be grateful.
>
> Happy to send the PDF first if you'd like to see it. Thank you either way.
>
> Warmly,
> Parv

## What's gated on you (I can't do these)
- Creating the SSRN / arXiv accounts and clicking submit.
- Sending the endorser email (I can send it via your Gmail if you say go).
- The ICAIF 8-page cut is real work (~Jul 15–30 window); the substance is done, it's a condensation + reformat.

## Integrity (from the roadmap — hold it)
Sole author; disclose AI tools (this is the research vehicle, NOT the Regeneron entry, so disclosed AI
assistance is fine). You must be able to defend every claim, especially the worst-of-regimes derivation —
own it by simulation if asked. Acknowledge a professor only if one genuinely helps and consents. Never dress
up correspondence as collaboration.
