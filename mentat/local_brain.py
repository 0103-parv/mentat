"""A LOCAL reasoning brain — mlx on Apple Silicon, no API, no credits.

Runs a small local LLM (Qwen2.5-0.5B-Instruct-4bit) as the proposer's core so the creative loop
can THINK, not just mutate, with zero credits. The verifier still gates every proposal, so a weak
local model can't hurt correctness — at worst it wastes a proposal the gate rejects. This module
MEASURES, honestly, whether the local brain actually helps the verifier-gated loop versus plain
random+crossover search (a 0.5B model is weak; we report what's true, not what's hoped).

Needs the ISOLATED venv (not the shared swechats venv):
  PYTHONPATH=. .venv-mlx/bin/python -m mentat.local_brain
"""
from __future__ import annotations

import random
import time

from .core import BrainConfig, Memory, solve
from .demo import RandomProposer, SymbolicRegression, parse_infix
from .reasoning import extract_json_list

MODEL = "mlx-community/Qwen2.5-0.5B-Instruct-4bit"


class LocalMLXCore:
    """A local LLM with the same .complete_text(system, user) interface as the Claude core."""

    def __init__(self, model: str = MODEL):
        from mlx_lm import load
        self.model = model
        self._m, self._t = load(model)

    def complete_text(self, system: str, user: str, max_tokens: int = 120) -> str:
        from mlx_lm import generate
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        prompt = self._t.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        return generate(self._m, self._t, prompt=prompt, max_tokens=max_tokens, verbose=False)


def _clean(s: str) -> str:
    s = s.strip().split("=")[-1].strip()       # drop a leading 'y=' / 'f(x)='
    return s.replace("^", "**")                # ^ means power in math, ** in Python


class LocalProposer:
    """Local-LLM proposer over the formula DSL; tops up / falls back to random so it never starves.
    Tracks how many of its raw outputs were VALID parseable expressions (the honest signal)."""

    _SYSTEM = ("You propose math formulas for y = f(x). Reply ONLY a JSON array of Python "
               "expressions using x, the operators + - * / **, parentheses and numbers. "
               'Example: ["x**2 - 1", "x**3 - 2*x + 1"]. No prose, no "y=", no "^".')

    def __init__(self, core, fallback: RandomProposer):
        self.core, self.fallback = core, fallback
        self.valid = 0
        self.attempts = 0
        self.last: list = []
        self.note = ""

    def propose(self, problem, memory: Memory, mind, k: int):
        user = problem.brief() + f"\n\nPropose {k} candidate expressions."
        out, self.last, self.note = [], [], ""
        try:
            text = self.core.complete_text(self._SYSTEM, user, max_tokens=120)
            for s in extract_json_list(text)[:k]:
                self.attempts += 1
                try:
                    out.append(parse_infix(_clean(s)))
                    self.valid += 1
                    self.last.append(s)
                except (ValueError, SyntaxError, RecursionError):
                    pass
        except Exception as e:
            self.note = f"local core error ({type(e).__name__})"
        if len(out) < k:
            out += self.fallback.propose(problem, memory, mind, k - len(out))
        return out


def main() -> int:
    try:
        import mlx_lm  # noqa: F401
    except Exception:
        print("The local brain needs mlx-lm, which lives in the ISOLATED venv (not the shared one).")
        print("Run it with:\n  PYTHONPATH=. .venv-mlx/bin/python -m mentat.local_brain")
        return 1
    xs = [round(i * 0.2, 2) for i in range(-10, 11)]
    target = lambda x: x ** 3 - 2 * x + 1            # noqa: E731  (the hard cubic)
    prob = SymbolicRegression(target, xs, tol=0.10)

    print("LOCAL BRAIN — a small on-device LLM proposing inside the verifier-gated loop (no API)")
    print(f"  model: {MODEL}   target: y = x^3 - 2x + 1   gate: RMSE < {prob.tol}\n")
    t = time.time()
    core = LocalMLXCore()
    print(f"  loaded the local model in {time.time() - t:.1f}s\n")

    GENS, K = 12, 8
    # local-brain run
    local = LocalProposer(core, RandomProposer(random.Random(1)))
    t = time.time()
    rl = solve(prob, local, Memory(), generations=GENS, k=K, log=lambda *_: None, brain=BrainConfig())
    lt = time.time() - t
    # random baseline (same budget)
    t = time.time()
    rr = solve(prob, RandomProposer(random.Random(1)), Memory(), generations=GENS, k=K,
               log=lambda *_: None, brain=BrainConfig())
    rt = time.time() - t

    valid_pct = (100 * local.valid / local.attempts) if local.attempts else 0
    print(f"  LOCAL BRAIN : best RMSE {-rl.best_score:.4f}  solved={rl.solved}  "
          f"({local.valid}/{local.attempts} of its proposals parsed, {valid_pct:.0f}%)  {lt:.1f}s")
    print(f"  RANDOM-ONLY : best RMSE {-rr.best_score:.4f}  solved={rr.solved}  {rt:.1f}s")
    print()
    if local.valid == 0:
        print("=> HONEST: the 0.5B model produced no valid expressions here — the loop ran on the")
        print("   random fallback. A local brain is wired and gated, but this model is too weak to")
        print("   help on this task. The verifier kept it correct regardless.")
    elif rl.best_score >= rr.best_score:
        print("=> The local brain matched or helped — and every idea was verified before being kept.")
    else:
        print("=> HONEST: the local brain under-performed random+crossover on this task (it's only")
        print("   0.5B). It's wired and gated; bigger local models or the API would do better.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
