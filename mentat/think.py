"""Run the Mentat kernel with the real reasoning core driving the proposer.

This is the brain wired in: same loop, same verification gate, same grounded
memory as `mentat.demo` — but candidates now come from Claude reasoning about the
data instead of from blind mutation. Every candidate it proposes is still run
through the verifier before it can become the answer.

Run (needs the `anthropic` SDK + an ANTHROPIC_API_KEY in env or .env):
    python3 -m mentat.think
Falls back with a clear message if no reasoning core is available.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

from .core import Memory, solve
from .demo import LLMProposer, RandomProposer, SymbolicRegression, to_str
from .reasoning import AnthropicCore, core_available


def _logger(proposer: LLMProposer):
    def log(msg: str):
        if proposer.note:
            print(f"      [{proposer.note}]")
        elif proposer.last:
            shown = "; ".join(proposer.last[:6])
            print(f"      core proposed: {shown}")
        print(f"   {msg}")
    return log


def main():
    xs = [round(i * 0.2, 2) for i in range(-10, 11)]
    problem = SymbolicRegression(lambda x: x ** 3 - 2 * x + 1, xs, tol=0.05)

    if not core_available():
        print("No reasoning core available.")
        print("  Need: `pip install anthropic` + ANTHROPIC_API_KEY (env or a .env file).")
        print("  The offline-proposer demo still runs without either:  python3 -m mentat.demo")
        return

    core = AnthropicCore()
    proposer = LLMProposer(core=core, fallback=RandomProposer(random.Random(0)))

    print(f"REASONING CORE   {core.model} (adaptive thinking)")
    print(f"PROBLEM          rediscover a hidden y = f(x) from 21 samples")
    print(f"GATE             a candidate is believed only if RMSE < {problem.tol}")
    print("                 (the core sees the data, never the hidden law)\n")

    mem_path = Path(__file__).parent / "think_memory.json"   # warm-start across runs
    memory = Memory() if "--fresh" in sys.argv else Memory.load(mem_path)
    result = solve(problem, proposer, memory, generations=6, k=6, log=_logger(proposer))
    memory.save(mem_path)

    print()
    if result.solved:
        print(f"SOLVED in {result.generations} generation(s) of reasoning.")
        print(f"  law:     {to_str(result.best_candidate)}")
        print(f"  verdict: {result.verdict.detail}")
        print("  (the offline mutation proposer needed ~52 generations for the same gate.)")
    else:
        print(f"best after {result.generations} generations: {to_str(result.best_candidate)}")
        print(f"  {result.verdict.detail}")


if __name__ == "__main__":
    main()
