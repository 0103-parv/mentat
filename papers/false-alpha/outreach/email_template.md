# Cold-email template (honest, specific, low-burden)

Principles: short (≤150 words), lead with *their* work, state the genuinely-novel bit, make
the ask tiny and specific, attach the SSRN/arXiv link, never overclaim, be honest you're a
high-school researcher. Send from a clean email with a real signature.

---

## Template (fill the [brackets])

**Subject:** [specific hook, e.g., "A worst-of-regimes correction to the deflated Sharpe — feedback?"]

Dear Professor [Last name],

I'm a high-school senior doing independent research in quantitative finance / ML. I read
[their specific paper / line of work] and it directly shaped a project I just posted as a
preprint.

I ran a controlled "N-sweep": as an LLM (and simpler generators) propose more and more
trading strategies, do real edges accumulate or only false discoveries? Across seven real
markets the answer is zero survivors under a strict deflated, worst-of-regimes gate. Along the
way [one-line novel result + their-work hook — see professors.md].

I'd be grateful for [one tiny, specific ask: "20 minutes of feedback on whether that
derivation is correct/known" / "a pointer to prior art I may have missed"]. The preprint
(reproducible code + tests) is here: [SSRN link] (also arXiv: [link]).

Thank you for your time.

[Full name]
[School, grade] · [city] · [email]

---

## Worked example — Prof. López de Prado (Tier 1, best target)

**Subject:** Worst-of-regimes correction to the Deflated Sharpe Ratio — is this known?

Dear Professor López de Prado,

I'm a high-school senior doing independent quant-finance research; your Deflated Sharpe Ratio
is the backbone of the evaluation gate in a preprint I just posted.

I ran a controlled N-sweep — as an LLM and simpler generators propose 10→3,000 strategies, do
real edges accumulate or only false discoveries? Across seven real markets, zero survive the
gate. In deriving the gate I found the standard DSR is calibrated for a single Sharpe, but my
gate scores the *minimum over k regimes*; the correct null is E[max_N min_k Z], which the
single-Sharpe DSR over-deflates by ~2.4× (N=1000, k=3). The real-market zero survives even
this corrected, weaker bar.

Is this worst-of-regimes correction already known? I'd be grateful for a pointer or a quick
reaction. Preprint (with reproducible code + 38 tests): [SSRN link].

Thank you very much for your time.

Parv Mehndiratta
[School], 12th grade · [city] · whizkid783@gmail.com

---

## Do / Don't
- DO send 3 personalized emails, not 1 mass email. DO post the preprint first.
- DO use the acknowledgment/mentor language honestly *only if* they actually help.
- DON'T say "I proved markets are efficient" or "I found a money machine" — overclaiming is
  the fastest rejection.
- DON'T attach a 30-page file; link the preprint. DON'T ask for co-authorship up front.
- DON'T be discouraged by silence — it's the norm; follow up once after ~1 week, politely.
