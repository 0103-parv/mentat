"""Live rubric-iteration experiment at scale (the make-or-break for the judge paper).

Real co-tuning with a real LLM judge: the scoring RUBRIC is REWRITTEN by the LLM each
round from the pipeline's own batch -- the actual practice the paper models ("iterate the
scoring prompt until it looks right on our outputs"). This replaces the pilot's weak
exemplar-appending co-tuning, which failed to separate from the fixed condition.

Domain (objective ground truth, no LLM in the truth loop): candidates are one-line Python
expressions predicting y from x1..x5; hidden truth y = 2*x1 - x2 + noise; true quality =
R^2 on held-out data computed locally.

Conditions per seed (identical structure; judge provenance is the only difference):
  F  fixed rubric        one scoring rubric, never modified
  C  co-tuned rubric     after each round, the LLM rewrites the rubric given the round's
                         candidates, its own scores, and the selected winner
  I  indep ensemble      3 fixed, differently-phrased rubrics never exposed to the trace;
                         selection on their mean score

Each round: generator (sees current champion as a hint) proposes BATCH candidates; the
condition's judge scores them; champion = argmax under the current judge among {champion,
round winner}. After the last round, the shipped champion is scored by (a) the condition's
own final judge state ("reported") and (b) a HELD-OUT panel of 3 fresh rubrics never used
in any loop. Inflation = reported - heldout_mean. True quality = local R^2.

PRE-REGISTERED (before running; scored as seed-majority, reported regardless of outcome):
  P1  inflation(C) > inflation(F) in a majority of seeds  (live co-tuning amplification)
  P2  inflation(I) is the smallest of the three in a majority of seeds
  P3  trueR2(I) >= trueR2(C) in a majority of seeds
The pilot's failure to separate C from F is documented in the paper; if P1 fails again at
this scale, that null is the result and gets reported.

SEEDS=8, ROUNDS=6, BATCH=8, model haiku, every completion cached (llm_cache_rubric.json),
hard MAX_CALLS cap. Rerun = free.

  set -a && . ~/swechats/.env; set +a
  ~/swechats/.venv/bin/python papers/false-alpha/llm_rubric_iteration.py
"""
from __future__ import annotations
import hashlib, json, random, re
from pathlib import Path

import anthropic

HERE = Path(__file__).resolve().parent
CACHE_F = HERE / "llm_cache_rubric.json"
OUT_F = HERE / "llm_rubric_iteration_results.json"
MODEL = "claude-haiku-4-5"
MAX_CALLS = 700
SEEDS = [21, 22, 23, 24, 25, 26, 27, 28]
ROUNDS = 6
BATCH = 8
ENS = 3

_client = None
_cache = json.loads(CACHE_F.read_text()) if CACHE_F.exists() else {}
_calls = 0

def llm(prompt: str, temp: float) -> str:
    global _client, _calls
    key = hashlib.sha256(f"{MODEL}|{temp}|{prompt}".encode()).hexdigest()
    if key in _cache:
        return _cache[key]
    if _calls >= MAX_CALLS:
        raise RuntimeError(f"MAX_CALLS={MAX_CALLS} reached")
    if _client is None:
        _client = anthropic.Anthropic()
    r = _client.messages.create(model=MODEL, max_tokens=900, temperature=temp,
                                messages=[{"role": "user", "content": prompt}])
    _calls += 1
    text = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "")
    _cache[key] = text
    CACHE_F.write_text(json.dumps(_cache, indent=1))
    return text

# ---------- objective truth (local, no LLM) ----------
def make_data(seed, n=400):
    r = random.Random(seed)
    rows = []
    for _ in range(n):
        x = [r.gauss(0, 1) for _ in range(5)]
        rows.append((x, 2 * x[0] - x[1] + r.gauss(0, 0.3)))
    return rows

def true_r2(expr, data):
    try:
        code = compile(expr, "<c>", "eval")
    except Exception:
        return -1.0
    preds, ys = [], []
    for x, y in data:
        env = {f"x{i+1}": x[i] for i in range(5)}
        env.update(abs=abs, min=min, max=max)
        try:
            p = float(eval(code, {"__builtins__": {}}, env))
        except Exception:
            return -1.0
        if p != p or abs(p) > 1e6:
            return -1.0
        preds.append(p); ys.append(y)
    my = sum(ys) / len(ys)
    sst = sum((y - my) ** 2 for y in ys)
    ssr = sum((y - p) ** 2 for y, p in zip(ys, preds))
    return 1 - ssr / sst if sst else -1.0

# ---------- prompts ----------
GEN = """[run {tag}] You are proposing candidate predictors. Dataset columns: x1..x5 (numeric). Target: y (relationship unknown to you). Propose {k} DIVERSE one-line Python expressions (only x1..x5, numbers, + - * / abs min max) that might predict y.{hint}
Reply ONLY with a JSON list of {k} strings."""

BASE_RUBRIC = """Score each candidate expression 0-10 for how likely it is to genuinely predict the unknown numeric target y from features x1..x5. Prefer plausible, parsimonious structure; penalize obvious junk or needless complexity."""

INDEP_RUBRICS = [
    "You are a skeptical statistician. Score each expression 0-10 on how likely it is to genuinely predict an unknown target y from x1..x5. Favor simplicity and robustness.",
    "You are a data-science reviewer. Rate 0-10 how well each expression would generalize as a predictor of unknown y. Reward parsimony; punish overfit-looking constructions.",
    "You are a conservative quantitative-modeling judge. Give each expression a 0-10 score for expected out-of-sample predictive quality on unknown y.",
]

HELDOUT_RUBRICS = [
    "You are an independent auditor seeing this expression for the first time. Score 0-10: how likely does it genuinely predict an unknown numeric target y from features x1..x5?",
    "You are a careful ML practitioner. Rate this expression 0-10 for plausible out-of-sample predictive value on an unknown target y given x1..x5.",
    "You are a blunt reviewer. Score 0-10 how much you would trust this expression as a predictor of an unknown y from x1..x5.",
]

SCORE = """{rubric}
Candidates:
{cands}
Reply ONLY with a JSON list of {k} numbers (scores, same order)."""

REWRITE = """You maintain the scoring rubric for a search pipeline that proposes predictor expressions for an unknown target y from x1..x5. Here is the current rubric, this round's candidates with the scores YOUR rubric produced, and the selected winner. Revise the rubric so it better captures what distinguishes the best candidates IN THIS BATCH. Keep it under 80 words. Reply ONLY with the revised rubric text.

CURRENT RUBRIC:
{rubric}

THIS ROUND (score, candidate):
{scored}

SELECTED WINNER: {winner}"""

def parse_list(text, n, num=False):
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return None
    try:
        v = json.loads(m.group(0))
    except Exception:
        return None
    if len(v) < n:
        return None
    return [float(x) for x in v[:n]] if num else [str(x) for x in v[:n]]

def rate(rubric, cands):
    listing = "\n".join(f"{i+1}. {c}" for i, c in enumerate(cands))
    out = parse_list(llm(SCORE.format(rubric=rubric, cands=listing, k=len(cands)), 0.0),
                     len(cands), num=True)
    return out or [0.0] * len(cands)

def run_condition(cond, seed, data_eval):
    rubric = BASE_RUBRIC
    champion, champ_score = None, None
    hint = ""
    for rnd in range(ROUNDS):
        cands = parse_list(llm(GEN.format(tag=f"{seed}-{cond}-{rnd}", k=BATCH, hint=hint), 0.9),
                           BATCH) or []
        if not cands:
            continue
        pool = cands + ([champion] if champion else [])
        if cond == "I":
            per = [rate(r, pool) for r in INDEP_RUBRICS]
            scores = [sum(p[i] for p in per) / ENS for i in range(len(pool))]
        else:
            scores = rate(rubric, pool)
        i = max(range(len(pool)), key=lambda j: scores[j])
        champion, champ_score = pool[i], scores[i]
        hint = f"\nA previously well-rated candidate: {champion}"
        if cond == "C":
            scored = "\n".join(f"({s:.1f}, {c})" for s, c in zip(scores, pool))
            new_rubric = llm(REWRITE.format(rubric=rubric, scored=scored, winner=champion), 0.0).strip()
            if 20 < len(new_rubric) < 700:
                rubric = new_rubric
    if champion is None:
        return None
    # reported = own final judge state; held-out = fresh panel never in any loop
    if cond == "I":
        reported = sum(rate(r, [champion])[0] for r in INDEP_RUBRICS) / ENS
    else:
        reported = rate(rubric, [champion])[0]
    heldout = sum(rate(r, [champion])[0] for r in HELDOUT_RUBRICS) / len(HELDOUT_RUBRICS)
    return {"cond": cond, "seed": seed, "expr": champion,
            "reported": reported, "heldout": heldout,
            "inflation": reported - heldout,
            "true_r2": round(true_r2(champion, data_eval), 3),
            "final_rubric": rubric if cond == "C" else None}

def main() -> int:
    runs = []
    for seed in SEEDS:
        data_eval = make_data(seed * 13 + 5)
        for cond in ("F", "C", "I"):
            r = run_condition(cond, seed, data_eval)
            if r:
                runs.append(r)
                print(f"seed {seed} {cond}: rep {r['reported']:.1f} held {r['heldout']:.1f} "
                      f"infl {r['inflation']:+.1f} trueR2 {r['true_r2']:+.3f}  {r['expr'][:50]}")
    # aggregate + pre-registered scoring
    agg = {}
    for cond in "FCI":
        rs = [r for r in runs if r["cond"] == cond]
        agg[cond] = {k: round(sum(r[k] for r in rs) / len(rs), 3)
                     for k in ("reported", "heldout", "inflation", "true_r2")} if rs else {}
    by_seed = {s: {r["cond"]: r for r in runs if r["seed"] == s} for s in SEEDS}
    ok = lambda s, *c: all(x in by_seed[s] for x in c)
    p1 = [by_seed[s]["C"]["inflation"] > by_seed[s]["F"]["inflation"] for s in SEEDS if ok(s, "C", "F")]
    p2 = [by_seed[s]["I"]["inflation"] == min(by_seed[s][c]["inflation"] for c in "FCI")
          for s in SEEDS if ok(s, "F", "C", "I")]
    p3 = [by_seed[s]["I"]["true_r2"] >= by_seed[s]["C"]["true_r2"] for s in SEEDS if ok(s, "I", "C")]
    passes = {"P1_cotuned_gt_fixed": f"{sum(p1)}/{len(p1)}",
              "P2_indep_smallest": f"{sum(p2)}/{len(p2)}",
              "P3_indep_true_geq_cotuned": f"{sum(p3)}/{len(p3)}"}
    print("\nAGGREGATE:", json.dumps(agg, indent=1))
    print("PRE-REGISTERED:", json.dumps(passes))
    OUT_F.write_text(json.dumps({"config": {"model": MODEL, "seeds": SEEDS, "rounds": ROUNDS,
                                            "batch": BATCH, "ens": ENS},
                                 "runs": runs, "aggregate": agg,
                                 "preregistered": passes,
                                 "api_calls_this_run": _calls}, indent=2))
    print(f"(api calls: {_calls}; results -> {OUT_F})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
