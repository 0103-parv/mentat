# PUBLISH KIT — do this to go live today
*Built 2026-07-12. The paper is finalized, verified, figures embedded. Everything below is copy-paste ready. Steps marked 🔴 only YOU can do (your logins / a human email).*

---

## The final files (upload these)
- **`PAPER_piazzesi.pdf`** ← the submission PDF (Piazzesi/NBER working-paper format: serif, centered title block, indented abstract, justified body, booktabs tables, embedded figures, centered page numbers, no TOC). Upload THIS to SSRN. Rebuild anytime with `python3.14 build_piazzesi_pdf.py`.
- Older `PAPER.pdf` (plain Chrome render) and `PAPER.docx` (black-template) are superseded by the Piazzesi PDF for submission.
- Backup: `FALSE_ALPHA_FULL_PACKET.pdf` (everything-in-one, heavier) and `PAPER_SHORT.docx` (short version). You do **not** need these for SSRN; `PAPER.pdf` is the clean one.

---

## TOP 3 VENUES — FINAL (this is the decision, don't re-open it)
1. **SSRN** — post today. No review, immediate, this is where the finance crowd (López de Prado / Harvey) actually reads. 🔴 needs your login only. **This is the win that gives you a live link.**
2. **arXiv** (cs.LG primary + q-fin.ST cross-list) — post this week. Free, timestamped, citable, the academic-facing link. 🔴 needs a one-click **endorser** first (email below).
3. **ICAIF 2026** (ACM Intl. Conf. on AI in Finance, Milan, Nov 14–17) — **submission deadline Aug 2, 2026**, 8pp ACM two-column, double-blind via CMT. The real reviewed-conference target. The 8-page condensation is the only remaining *work*; substance is done.
   - *Slow-journal backup (don't chase now):* Journal of Financial Data Science (pm-research), ~6–12mo.

Frame everywhere as an **evaluation / robustness** result, not a finance discovery. The "zero edge" is the setup, not the headline (that part is prior art). Lead with the derived worst-of-regimes deflation + the power-surface characterization.

---

## STEP 1 🔴 — POST TO SSRN (≈15 min, do this first)
Go to https://www.ssrn.com → sign in (or create a free account) → **Submit a Paper**. Fill:

**Title**
> More Strategies, Same Zero: Multiple Testing Against LLM-Scale Alpha Search

**Subtitle / short description**
> A controlled N-sweep test of the false-strategy theorem with a live LLM proposer, and why scaling the search raises the discovery bar faster than it finds edge.

**Author:** Parv Mehndiratta (sole author). Affiliation: Independent researcher (you can leave institution blank or "Independent").

**Abstract:** paste the block in `ABSTRACT_FOR_UPLOAD.txt` (next to this file — it's the paper's abstract, plain text, ready to paste).

**Keywords:** backtest overfitting, multiple testing, false discovery rate, deflated Sharpe ratio, data snooping, LLM agents, automated strategy search, quantitative finance, evaluation and robustness

**JEL codes:** C12, C45, C52, C58, G11, G17

**Classification / eJournals to request** (SSRN will suggest; pick these): Econometrics: Mathematical Methods & Programming; Financial Economics Network → Capital Markets: Asset Pricing & Valuation; Machine Learning eJournal.

**Upload:** `PAPER.pdf`. Submit. It clears review in ~a day and you get a permanent SSRN URL. **That URL is the outreach unlock.**

---

## STEP 2 🔴 — GET AN arXiv ENDORSER (send this email now, it doubles as a warm touch)
arXiv cs.LG requires a one-click endorsement from an existing cs.LG author. John Yang is the most natural (you already correspond; he's a SWE-bench/SWE-agent author). Send from **0103.parv@gmail.com** to the John Yang address you already have (SALT-NLP / jyangballin):

> **Subject:** Quick arXiv endorsement — cs.LG?
>
> Hi John,
>
> I am about to post my first paper to arXiv (cs.LG, cross-listed q-fin.ST) and the system asks a first-time submitter for a one-click endorsement from an existing cs.LG author. Would you be willing?
>
> The paper is a controlled experiment on LLM-scale trading-strategy search: it shows the search manufactures backtest-overfitting false discoveries, and that the multiple-testing correction that stops them also makes moderate genuine edges unprovable at scale. Sole-authored, all results reproducible from committed scripts.
>
> No rush and no worries at all if it is not something you do. Happy to send the draft first.
>
> Thank you,
> Parv

If he declines or is slow, other qualifying endorsers you already talk to: Jeff Clune, Antoine Cully, Jean-Baptiste Mouret, Robert Lange. Once endorsed, submit at https://arxiv.org/submit with primary **cs.LG**, cross-list **q-fin.ST**, same title/abstract/PDF.

---

## STEP 3 — THE MOMENT SSRN IS LIVE
Come back and tell me "SSRN is live, here's the link." Then I fire the **marquee outreach** (drafts already written in `~/research-outreach/drafts-marquee-fire-on-preprint.md`) — the live link is exactly what those emails were waiting for.

---

## INTEGRITY LINE (hold it)
Sole author; AI disclosed as a coding/writing aid under your direction; the professors you emailed **encouraged**, they did not co-write — say "corresponded with X who encouraged the work," never "collaborated." Every number is defensible by simulation. This is a preprint/ICAIF-scale contribution — real, narrow, honest. Don't let anyone (including you at 2am) inflate it.
