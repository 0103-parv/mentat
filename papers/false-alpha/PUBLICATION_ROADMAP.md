# Publication roadmap, false alpha paper

*Written 2026-07-06. Goal: a real, citable publication plus a live "published" line for college, without overreaching on venue.*

## The decision, in one line

**Post to arXiv and SSRN now (the guaranteed win and the outreach unlock), and submit the 8 page version to ICAIF 2026 by August 2 (the real conference).** Frame it as an evaluation and robustness result, not a finance discovery, per the honest novelty audit.

## The venue, and why

- **arXiv (cs.LG, with a q-fin.ST cross list).** Free, immediate, timestamped, citable. This is what makes you able to say you published, and a live link makes every professor email far stronger. Needs a one click endorsement from someone who has published in cs.LG (see step 2). This is the backbone; everything else is on top.
- **SSRN.** The standard finance and economics preprint repo, no review, immediate. Puts the paper in front of the finance audience (the López de Prado / Harvey crowd) in the place they actually read. Post the same PDF.
- **ICAIF 2026 (primary conference target).** The ACM International Conference on AI in Finance, Milan, Nov 14 to 17. **Deadline August 2, 2026.** 8 pages, ACM two column, double blind, submitted via CMT. Reputable, exactly on topic (AI in finance), student accessible, and double blind means your age is invisible in review. This is the right level for the paper: not a main ML track, a real applied AI in finance conference where the cross generator plus planted control plus diversity ceiling contribution is the right size.
- **Later or fallback:** a NeurIPS or ICML 2026 workshop on ML for finance or evaluation and robustness (deadlines land ~September), and finance data science journals (J. of Financial Data Science, J. of Investment Strategies) if you want a slower reviewed venue. Keep these as backups, do not chase all of them.

## Honest framing (hold this in the abstract)

Lead with the evaluation and robustness result: how machine driven strategy search behaves under multiple testing correct gating, with calibrated planted and noise controls and a cross generator comparison. Make the zero the setup, not the headline, since the zero itself is prior art (STW 1999, FINSABER). Lead the contribution with the derived worst of regimes deflation and the structural variance diagnosis (both independently reproduced 2026-07-05, see `INDEPENDENT_REVIEW_2026-07-05.md` and `DERIVATION_worst_of_regimes.md`). Never claim "no edge" or "market efficiency."

## What has to happen first (small, do these before submitting)

1. Apply the two fixes from the independent review: the demo single pool bug (redraw the pool per repetition, regenerate the table in `overfitting_the_judge.md`), and state the over deflation as k dependent (about 2.4 times at k = 3) in section 4.9 and the abstract.
2. Get an arXiv endorser. You correspond with several people who qualify (John Yang is the most natural; Clune, Cully, Mouret, Lange also). One short honest email: "I am posting my first paper to arXiv cs.LG and need an endorsement, would you be willing." This is a small, relationship appropriate ask, and it doubles as a warm touch.

## Timeline to August 2 (tight but doable, the paper already exists)

- **By ~Jul 12:** apply the two fixes; ask an endorser; register SSRN.
- **By ~Jul 15:** post to arXiv and SSRN. You are now "published," and every outreach follow up gets a link. (arXiv preprints are generally compatible with ICAIF double blind; just do not name the preprint in the submission. Verify ICAIF's specific policy.)
- **Jul 15 to Jul 30:** cut the full paper to the 8 page ACM two column version. The figures exist (`fig_headline`, `fig_verification`). This is the real work; the substance is done, it is a condensation and reformat.
- **Aug 2:** submit to ICAIF via CMT.

If August 2 slips, nothing is lost: the arXiv and SSRN preprint stands on its own, and a September ML workshop is the next window.

## Authorship and integrity (non negotiable)

Sole author, AI tools disclosed (this is a research vehicle, not the Regeneron entry, so disclosed AI assistance is fine here, but you still must be able to defend every claim, especially the worst of regimes derivation). Acknowledge a professor only if one genuinely helps and consents. Cite freely. Do not dress up correspondence as collaboration.

## The one sentence status

The paper is written and its two novel results are independently verified; the only things between here and "published" are two small fixes, an endorsement, and a reformat, so the realistic move is arXiv and SSRN within two weeks and ICAIF by August 2.
