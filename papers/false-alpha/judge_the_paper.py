"""Judge the judge paper with independent LLM judges (single-pass, no co-tuning).

Recursive application of the paper's own machinery: a panel of K=3 independent reviewer
personas (rubrics written blind to the paper, never iterated on its content) each scores
the paper once. Per the paper's own finding, we do NOT iterate on these scores: one pass,
report verbatim. Re-running after edits until scores rise = co-tuning the judge = the
failure mode the paper measures. Treat output as signal, not target.

Cached to llm_cache_paperjudge.json; model claude-sonnet-5 (reviews need depth); 3 calls.

  set -a && . ~/swechats/.env; set +a
  ~/swechats/.venv/bin/python papers/false-alpha/judge_the_paper.py
"""
from __future__ import annotations
import hashlib, json, re, subprocess, sys
from pathlib import Path

import anthropic

HERE = Path(__file__).resolve().parent
CACHE_F = HERE / "llm_cache_paperjudge.json"
OUT_F = HERE / "judge_the_paper_results.json"
MODEL = "claude-sonnet-5"
MAX_CALLS = 6

_client = None
_cache = json.loads(CACHE_F.read_text()) if CACHE_F.exists() else {}
_calls = 0

def llm(prompt: str) -> str:
    global _client, _calls
    key = hashlib.sha256(f"{MODEL}|0|{prompt}".encode()).hexdigest()
    if key in _cache:
        return _cache[key]
    if _calls >= MAX_CALLS:
        raise RuntimeError("budget cap")
    if _client is None:
        _client = anthropic.Anthropic()
    r = _client.messages.create(model=MODEL, max_tokens=8000,
                                messages=[{"role": "user", "content": prompt}])
    _calls += 1
    text = next(b.text for b in r.content if getattr(b, "type", "") == "text")
    _cache[key] = text
    CACHE_F.write_text(json.dumps(_cache, indent=1))
    return text

# Three independent personas. Written BEFORE seeing any scores; never to be edited in
# response to scores (that would be co-tuning).
PERSONAS = {
    "skeptical_statistician": """You are a skeptical statistician reviewing for a trustworthy-ML venue. You care about: are the claims supported by the experimental design, are effect sizes honestly reported, are limitations real or cosmetic, is anything overclaimed. You are hard to impress and you say what is weak.""",
    "ml_eval_area_chair": """You are an area chair for an LLM-evaluation workshop. You care about: novelty relative to the reward-hacking / LLM-as-judge literature, whether the contribution is crisply positioned against prior work, and whether the community would learn something actionable. You know Gao et al. 2023, Coste et al., Eisenstein et al., Zheng et al. well.""",
    "clarity_reviewer": """You are a reviewer focused on scientific communication. You care about: can a graduate student reproduce this from the text alone, is the writing precise, are figures/tables self-contained, is the abstract an honest summary of the body.""",
}

RUBRIC = """Review the paper below. Reply ONLY with JSON:
{{"scores": {{"soundness": 0-10, "novelty": 0-10, "clarity": 0-10, "honesty_of_claims": 0-10}},
 "leaning": "accept|weak accept|weak reject|reject",
 "strengths": ["...", "..."], "weaknesses": ["...", "..."],
 "one_line_verdict": "..."}}

{persona}

PAPER:
{paper}"""

def main() -> int:
    tex = (HERE / "judge" / "overfitting_the_judge.tex").read_text()
    # strip LaTeX preamble/bib noise, keep body text
    body = tex[tex.index("\\begin{abstract}"):tex.index("\\begin{thebibliography}")]
    results = {}
    for name, persona in PERSONAS.items():
        text = llm(RUBRIC.format(persona=persona, paper=body))
        m = re.search(r"\{.*\}", text, re.S)
        results[name] = json.loads(m.group(0)) if m else {"raw": text}
        print(f"== {name} ==")
        print(json.dumps(results[name], indent=1)[:600], "\n")
    OUT_F.write_text(json.dumps(results, indent=2))
    avg = {}
    for dim in ("soundness", "novelty", "clarity", "honesty_of_claims"):
        vals = [r["scores"][dim] for r in results.values() if "scores" in r]
        if vals: avg[dim] = round(sum(vals) / len(vals), 1)
    print("PANEL AVERAGE:", json.dumps(avg))
    print(f"(api calls: {_calls}; results -> {OUT_F})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
