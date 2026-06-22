"""Run the Mentat kernel on the user's own research: beat alpha-evolver's Max Cut
heuristic, scored by alpha-evolver's own offline benchmark.

Run:  python3 -m mentat.improve
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

from .core import Memory, solve
from .reasoning import AnthropicCore, core_available
from .self_research import (
    CreativeHeuristicProposer, HeuristicProposer, MaxCutHeuristic, _normalize,
)


class _Broken:
    def complete_text(self, *a, **k):
        raise RuntimeError("no core")


def _logger(proposer, problem):
    def log(msg: str):
        if proposer.note:
            print(f"      [{proposer.note}]")
        elif proposer.last:
            print(f"      core proposed moves: {proposer.last[0]} ...")
        print(f"   {msg}")
    return log


def main() -> int:
    try:
        problem = MaxCutHeuristic()
    except Exception as e:
        print(f"Cannot load the alpha-evolver Max Cut verifier: {type(e).__name__}: {e}\n"
              "This needs alpha-evolver + numpy, which live in alpha-evolver's venv. Run e.g.:\n"
              "  ~/alpha-evolver/.venv/bin/python -m mentat.improve\n"
              "  (or source ~/swechats/.env and use ~/swechats/.venv/bin/python, which has numpy)")
        return 1
    core = AnthropicCore() if core_available() else None
    if core:                                   # live reasoning core proposes programs
        proposer, gens, k = HeuristicProposer(core=core), 10, 6
    else:                                      # NO API: offline CREATIVE search over the program DSL
        proposer, gens, k = CreativeHeuristicProposer(random.Random(0), problem.baseline), 40, 24

    print("PROJECT          alpha-evolver — Max Cut heuristics (your own repo)")
    print("VERIFIER         maxcut_lab.evaluate_program on the train suite (offline, ~0.1s)")
    print(f"BASELINE         fitness {problem.baseline_fitness:.4f}  (alpha-evolver's baseline heuristic)")
    print(f"REASONING CORE   {core.model if core else 'offline creative search (no API)'}")
    print("GOAL             propose a heuristic that beats the baseline\n")

    mem_path = Path(__file__).parent / "maxcut_memory.json"   # warm-start across runs
    memory = Memory() if "--fresh" in sys.argv else Memory.load(mem_path)
    result = solve(problem, proposer, memory, generations=gens, k=k, log=_logger(proposer, problem))
    memory.save(mem_path)

    best = result.best_score
    delta = best - problem.baseline_fitness
    print()
    print(f"BEST verified fitness: {best:.4f}   (baseline {problem.baseline_fitness:.4f}, {delta:+.4f})")
    if result.solved:
        print("=> Beat the baseline. The discovery loop improved your own project's heuristic.")
    elif delta > 0:
        print("=> Edged the baseline but under the margin to count as solved (honest).")
    else:
        print("=> Did not beat the baseline in budget — reported only what verified (honest).")
    if memory.best_candidate:
        try:
            prog = _normalize(memory.best_candidate)
            print(f"best move: {problem.lab.expr_to_str(prog['move'])}")
            print(f"program:   {prog}")
        except Exception:
            print(f"best program: {memory.best_candidate}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
