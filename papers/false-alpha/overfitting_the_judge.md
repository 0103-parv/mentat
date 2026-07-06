# Overfitting the Judge: False Discovery in LLM-in-the-Loop Search

*Parv Mehndiratta. Working note, draft v0.1. Companion demo: `evaluator_overfit_demo.py`; figure: `fig_evaluator_overfit.svg`.*

## Abstract

Many modern AI systems discover things by looping: an LLM (or an evolutionary
operator) proposes candidates, an automated judge scores them, the best-scoring ones
are kept, and the loop repeats. We show that this loop inflates apparent quality even
with zero measurement noise. Repeatedly selecting the best score against a fixed judge
increasingly finds candidates that exploit the judge's idiosyncrasies, so the score on
the optimized judge climbs with the number of proposals while the candidate's true
quality, and its score on an independent held-out judge, stay flat. The gap is a
selection effect: a winner's curse against a fixed evaluator. We give a clean,
deterministic demonstration and show that selecting on an ensemble of independent
judges removes most of the inflation and recovers real quality. The mechanism unifies
several known failure modes (backtest overfitting, reward hacking, evaluation leakage
in coding-agent benchmarks) and gives a simple, testable correction.

## 1. The failure mode, plainly

When you generate many candidates and keep the one your evaluator likes best, you are
running a selection. If the evaluator rewards a few things that reflect real quality and
many things that do not (its own quirks), then the more candidates you try, the more
likely the winner is one that happens to match the evaluator's quirks rather than one
that is genuinely good. The evaluator's score on the winner keeps rising with the size
of the search. Its real quality does not. You have not discovered a better candidate;
you have found a better exploiter of your evaluator.

This is important now because LLM-in-the-loop systems make the number of proposals
effectively unbounded and cheap, and because the evaluator is often a single fixed model
or benchmark that the loop optimizes against directly.

## 2. A clean demonstration

We make the mechanism concrete with a deterministic model that has no measurement noise
at all (`evaluator_overfit_demo.py`). Each candidate is a vector of features; only a few
carry real quality, the rest are inert. A judge scores a candidate by its real quality
plus that judge's own idiosyncratic taste over the inert features. The loop proposes N
candidates and keeps the best judge score. We sweep N and record three things about the
winner: its score on the optimized judge, its score on a fresh independent judge, and its
true quality.

| N | optimized judge | independent judge | true quality | inflation |
|---:|---:|---:|---:|---:|
| 10 | 7.0 | 0.4 | 1.0 | 6.6 |
| 100 | 11.4 | 0.1 | 1.6 | 11.2 |
| 1000 | 14.8 | 3.1 | 2.2 | 11.7 |
| 3000 | 16.2 | 4.3 | 2.4 | 11.9 |

The optimized-judge score of the winner climbs about 2.3 times as the search grows, while
its true quality stays low and a fresh independent judge agrees. The inflation (optimized
minus independent) grows with N. None of this comes from noise; it is pure selection
against a fixed evaluator (Figure 1).

## 3. Relationship to prior work (what is known, what is new)

This connects to several established results, and it is important to be precise about the
boundary.

- **Winner's curse in quality-diversity optimization** (Flageat and Cully). Keeping the
  best-scoring elite per niche produces an optimistic estimate of its performance, and
  correcting or re-evaluating elites is an active line of work. This is prior art for the
  effect under sampling noise, and we do not claim it.
- **Multiple testing and backtest overfitting** (Bailey and Lopez de Prado; Sullivan,
  Timmermann and White). The expected best-of-N statistic grows under the null, and
  data-snooping corrections deflate it. Prior art for the search-inflates-the-best effect.
- **Reward hacking and evaluation leakage.** Agents that optimize against a fixed reward
  or benchmark can exploit it; held-out and chronological evaluation are known defenses in
  the coding-agent literature.

What we add is narrow but, to our knowledge, not stated in this form: the same inflation
arises **from selection against a fixed evaluator with no measurement noise at all**, so
it is distinct from the noise-driven winner's curse; it is a single lens that unifies the
finance, evolutionary, and LLM-agent instances; and the natural correction is an
**ensemble of independent judges**, which we frame as buying independent information rather
than adding one more held-out judge (a single held-out judge is itself exploitable).

## 4. The correction

Selecting on an ensemble of independent judges removes most of the inflation, because the
judges share the true-quality component but their idiosyncratic tastes are independent and
partly cancel. In the demo, ensemble selection recovers markedly higher true quality than
naive selection at every N (about 4.3 versus 2.4 at N = 3000). This is the same idea, in
three vocabularies: a held-out or chronological split in coding-agent evaluation; a
deflation or reality-check correction in strategy search; and, in decision-theory terms,
spending query budget to buy independent information rather than more selection against one
evaluator.

## 5. Scope and limits (honest)

The demonstration is a deterministic synthetic model, chosen so the mechanism is visible
without any confound. It is not evidence about the size of the effect in any particular
real system. The obvious next step is the live instantiation: an LLM generator and an LLM
judge in the loop, showing the same curve and the same ensemble fix on a real task; the
mechanism is evaluator-agnostic, so the prediction is clear. We also do not claim novelty
for the winner's curse itself, only for the fixed-evaluator, no-noise framing, the
cross-domain unification, and the ensemble correction stated as an information-buying
policy.

## References (to complete)

- Barber, R. F., Candès, E. J. Controlling the false discovery rate via knockoffs (2015).
- Bailey, D. H., Lopez de Prado, M. The deflated Sharpe ratio (2014).
- Sullivan, R., Timmermann, A., White, H. Data-snooping, technical trading rule
  performance, and the bootstrap (1999).
- Flageat, M., Cully, A. Work on uncertainty and the winner's curse in quality-diversity
  optimization (to cite precisely from the paper Prof. Cully pointed to).
- Yang, J. et al. SWE-bench and coding-agent evaluation (held-out / chronological design).
