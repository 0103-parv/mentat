# Why an AI goes "hazy" — and the honest fix (grounding, not a from-scratch rebuild)

The hypothesis on the table: AI gets blurry because it was trained on too many things, so
we should retrain a finance-only model FROM SCRATCH (no pretrained weights, no general
corpus). I researched this (papers pulled into `~/papers`, read via pqa). The honest
verdict: **the diagnosis has a kernel of truth, but the from-scratch fix is backwards.**

## What actually causes "haziness"
Not breadth of training — breadth is where competence (language, reasoning, instruction-
following) *comes from*. Haziness is mostly **ungrounded generation**: a probabilistic
model with no source to check against will fill gaps with plausible guesses. The fix is to
**ground answers in a real corpus and refuse when there's no source** — which is exactly
the verification gate, applied to question-answering.

## The evidence (cited, via pqa over the papers)
- **From scratch is brutally expensive and not the lesson.** BloombergGPT (50B params,
  363B tokens) does beat general models on finance benchmarks — but cost **~$3M / ~1.3M
  GPU-hours** (Wu et al. 2023, arXiv 2303.17564). Crucially, even it was **~half general
  data**, not finance-only — because finance-only-from-scratch can't learn to reason.
- **Fine-tune + RAG dominates on cost and stays competitive.** FinGPT fine-tunes an open
  model with LoRA — **3.67M trainable params, ~$300/run, ~4 orders of magnitude cheaper**
  than BloombergGPT (Yang et al. 2023, arXiv 2306.06031).
- **RAG directly reduces hallucination/vagueness** by grounding outputs in an external
  knowledge base, with continuous updates and no retraining (Gao et al. 2023 RAG survey,
  arXiv 2312.10997; Lewis et al. 2020, arXiv 2005.11401).

pqa's synthesis: *"fine-tuning plus RAG is substantially more cost-effective than training
from scratch, and RAG demonstrably reduces hallucination and vagueness."*

## The brain analogy (the honest version of your intuition)
You don't make a finance genius by depriving a child of all general knowledge and teaching
only finance from birth — they'd be unable to reason. You give them **general intelligence
first, then specialize, and keep them grounded in real references.** The map:
- general intelligence  → a capable pretrained/general model (don't throw this away)
- specialization        → light fine-tuning (LoRA), optional
- grounding (no haze)   → **RAG**: answer only from retrieved sources, cite them, refuse otherwise
- judgment / no bullshit → **mentat's verification gate**

## What we built (the right Part 2, shipped)
`mentat/rag.py` + `mentat/finance_docs/` — grounded finance QA: pure-Python BM25 retrieval
over a finance corpus, answers ONLY from retrieved passages **with citations**, and
**refuses** ("I don't have a grounded source") when retrieval is too weak. That refusal is
the anti-haze guarantee. Wired as the Jarvis `finance_qa` tool. With the reasoning core it
synthesizes a cited answer; offline it returns the top sourced passage. `python3 -m
mentat.rag "what is the deflated sharpe ratio?"`.

## On Part 1 (from scratch) — my recommendation
Skip it as a path to a *sharp* finance AI; it would be **less** capable and **more** hazy,
at enormous cost. Two honest alternatives if you want to "specialize the model":
1. **LoRA fine-tune** a small open model on finance (FinGPT-style, ~$300) — real, doable,
   keeps general reasoning. The legitimate "specialize" move.
2. A **tiny from-scratch model** (nanoGPT on finance text) purely as a learning exercise —
   educational, but a toy: it will be incoherent, not sharper. Clearly labeled as such.
The grounding + verification stack above is what actually kills haziness.
