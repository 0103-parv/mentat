"""Live LLM-judge instantiation of the co-tuned ablation (Instantiation B, preliminary).

Domain: candidates are one-line Python expressions predicting y from x1..x5 on a synthetic
dataset with hidden truth y = 2*x1 - x2 + noise (x3..x5 are distractors). TRUE quality is
objective and computed locally (R^2 on held-out data, no LLM involved). An LLM judge rates
each candidate 0-10 by READING it (a proxy, exactly like a rubric-based reviewer).

Conditions (mirroring ablation_cotuned.py, reduced for cost):
  B' co-tuned judge   the judge rubric ACCUMULATES the pipeline's own past winners as
                      exemplars each round -- its criteria absorb the search trace
  A' fixed judge      same base rubric, never updated
  D' indep ensemble   3 judges with fixed, differently-phrased rubrics never shown the
                      trace; selection on their mean rating

Per round the LLM generator proposes a batch (it sees the previous round's top-rated
candidate, so a search trace exists); the condition's judge rates the batch; best-rated is
kept. After R rounds, the final winner's own-judge rating is compared with (a) ratings of
the SAME winner by held-out judges and (b) its true R^2.

Pre-registered predictions: (P1) the co-tuned judge rates its winner higher than held-out
judges rate the same winner, and the gap exceeds the fixed judge's gap; (P2) independent-
ensemble selection achieves true R^2 >= the co-tuned condition's.

All completions cached to llm_cache_judge.json (rerun = free). Hard cap MAX_CALLS.
Model: claude-haiku-4-5 (cheap); judge temperature 0.

  set -a && . ~/swechats/.env; set +a
  ~/swechats/.venv/bin/python papers/false-alpha/llm_judge_instantiation.py
"""
from __future__ import annotations
import hashlib, json, os, random, re, sys
from pathlib import Path

import anthropic

HERE = Path(__file__).resolve().parent
CACHE_F = HERE / "llm_cache_judge.json"
OUT_F = HERE / "llm_judge_instantiation_results.json"
MODEL = "claude-haiku-4-5"
MAX_CALLS = 80                      # hard budget cap (haiku, ~500 tok/call -> well under $1)
ROUNDS = 3
BATCH = 6
SEEDS = [11, 12]
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
        raise RuntimeError(f"MAX_CALLS={MAX_CALLS} reached -- budget cap")
    if _client is None:
        _client = anthropic.Anthropic()
    r = _client.messages.create(model=MODEL, max_tokens=700, temperature=temp,
                                messages=[{"role": "user", "content": prompt}])
    _calls += 1
    text = r.content[0].text
    _cache[key] = text
    CACHE_F.write_text(json.dumps(_cache, indent=1))
    return text

# ---------- objective ground truth (no LLM) ----------
def make_data(seed, n=400):
    r = random.Random(seed)
    rows = []
    for _ in range(n):
        x = [r.gauss(0, 1) for _ in range(5)]
        y = 2 * x[0] - x[1] + r.gauss(0, 0.3)
        rows.append((x, y))
    return rows

def true_r2(expr: str, data) -> float:
    """R^2 of the expression on held-out data; invalid/degenerate -> -1."""
    try:
        code = compile(expr, "<cand>", "eval")
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
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - p) ** 2 for y, p in zip(ys, preds))
    return 1 - ss_res / ss_tot if ss_tot else -1.0

# ---------- LLM roles ----------
GEN_PROMPT = """You are proposing candidate predictors. Dataset columns: x1,x2,x3,x4,x5 (all numeric).
Target: y. Propose {k} DIVERSE one-line Python expressions (no imports, only x1..x5, numbers,
+ - * / and abs/min/max) that might predict y.{hint}
Reply ONLY with a JSON list of {k} strings."""

BASE_RUBRIC = """You are a strict reviewer. Rate how good each candidate expression likely is at
predicting y from x1..x5 (unknown relationship), 0-10. Prefer plausible structure; penalize
obvious junk.{exemplars}
Candidates:
{cands}
Reply ONLY with a JSON list of {k} numbers (the scores, same order)."""

INDEP_RUBRICS = [
    "You are a skeptical statistician. Score each expression 0-10 on how likely it is to genuinely predict an unknown numeric target y from features x1..x5. Favor simplicity and robustness; punish needless complexity.\nCandidates:\n{cands}\nReply ONLY with a JSON list of {k} numbers.",
    "You are a data-science reviewer. Rate 0-10 how well each one-line expression would generalize as a predictor of y (relationship unknown). Reward parsimony, penalize overfit-looking constructions.\nCandidates:\n{cands}\nReply ONLY with a JSON list of {k} numbers.",
    "You are a quantitative modeling judge. Give each candidate expression a 0-10 score for expected out-of-sample predictive quality on target y given inputs x1..x5. Be conservative.\nCandidates:\n{cands}\nReply ONLY with a JSON list of {k} numbers.",
]

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

def gen_batch(k, hint, temp):
    text = llm(GEN_PROMPT.format(k=k, hint=hint), temp)
    out = parse_list(text, k)
    return out or []

def rate(rubric_text, cands):
    listing = "\n".join(f"{i+1}. {c}" for i, c in enumerate(cands))
    text = llm(rubric_text.format(cands=listing, k=len(cands)), 0.0)
    return parse_list(text, len(cands), num=True) or [0.0] * len(cands)

# ---------- one condition run ----------
def run_condition(cond, seed, data_eval):
    exemplars = ""          # co-tuned rubric state (the absorbed trace)
    hint = ""
    best = None             # (own_rating, expr)
    for rnd in range(ROUNDS):
        cands = gen_batch(BATCH, hint, temp=0.8)
        if not cands:
            continue
        if cond == "D":
            ratings_per_judge = [rate(r, cands) for r in INDEP_RUBRICS]
            ratings = [sum(rs[i] for rs in ratings_per_judge) / ENS for i in range(len(cands))]
        else:
            rubric = BASE_RUBRIC.replace("{exemplars}", exemplars)
            ratings = rate(rubric, cands)
        i_best = max(range(len(cands)), key=lambda i: ratings[i])
        w, wr = cands[i_best], ratings[i_best]
        if best is None or wr > best[0]:
            best = (wr, w)
        hint = f"\nA previous well-rated candidate: {w}"
        if cond == "B":     # co-tuning: rubric absorbs the pipeline's own winners
            exemplars += f"\nExemplar of a high-quality candidate (score it and similar ones highly): {w}"
    if best is None:
        return None
    own, expr = best
    heldout = [rate(r, [expr])[0] for r in INDEP_RUBRICS]
    return {"expr": expr, "own_rating": own,
            "heldout_mean": sum(heldout) / len(heldout),
            "gap": own - sum(heldout) / len(heldout),
            "true_r2": round(true_r2(expr, data_eval), 3)}

def main() -> int:
    results = {"config": {"model": MODEL, "rounds": ROUNDS, "batch": BATCH, "seeds": SEEDS,
                          "ens": ENS, "max_calls": MAX_CALLS}, "runs": []}
    for seed in SEEDS:
        data_eval = make_data(seed * 7 + 1)
        for cond, name in (("A", "fixed judge"), ("B", "co-tuned judge"), ("D", "indep ensemble")):
            r = run_condition(cond, seed, data_eval)
            if r:
                r.update({"seed": seed, "cond": cond, "name": name})
                results["runs"].append(r)
                print(f"seed {seed} {name:>15}: own {r['own_rating']:.1f}  heldout {r['heldout_mean']:.1f}"
                      f"  gap {r['gap']:+.1f}  trueR2 {r['true_r2']:+.3f}   {r['expr'][:60]}")
    # aggregate
    agg = {}
    for cond in "ABD":
        rs = [r for r in results["runs"] if r["cond"] == cond]
        if rs:
            agg[cond] = {k: round(sum(r[k] for r in rs) / len(rs), 3)
                         for k in ("own_rating", "heldout_mean", "gap", "true_r2")}
    results["aggregate"] = agg
    results["api_calls_this_run"] = _calls
    OUT_F.write_text(json.dumps(results, indent=2))
    print(f"\naggregate: {json.dumps(agg, indent=1)}")
    print(f"(api calls this run: {_calls}; results -> {OUT_F})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
