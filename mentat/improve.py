"""Run the Mentat kernel on the user's own research: beat alpha-evolver's Max Cut
heuristic, scored by alpha-evolver's own offline benchmark.

Run:  python3 -m mentat.improve
"""
from __future__ import annotations

from .core import Memory, solve
from .reasoning import AnthropicCore, core_available
from .self_research import HeuristicProposer, MaxCutHeuristic, _normalize


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


def main():
    problem = MaxCutHeuristic()
    core = AnthropicCore() if core_available() else None
    proposer = HeuristicProposer(core=core or _Broken())

    print("PROJECT          alpha-evolver — Max Cut heuristics (your own repo)")
    print("VERIFIER         maxcut_lab.evaluate_program on the train suite (offline, ~0.1s)")
    print(f"BASELINE         fitness {problem.baseline_fitness:.4f}  (alpha-evolver's baseline heuristic)")
    print(f"REASONING CORE   {core.model if core else 'offline baseline variants only'}")
    print("GOAL             propose a heuristic that beats the baseline\n")

    memory = Memory()
    result = solve(problem, proposer, memory, generations=10, k=6, log=_logger(proposer, problem))

    best = result.best_score
    delta = best - problem.baseline_fitness
    print()
    print(f"BEST verified fitness: {best:.4f}   (baseline {problem.baseline_fitness:.4f}, "
          f"{'+' if delta >= 0 else ''}{delta:.4f})")
    if result.solved:
        print("=> Beat the baseline. The discovery loop improved your own project's heuristic.")
    else:
        print("=> Did not beat the baseline in budget — reported only what verified (honest).")
    if memory.best_candidate:
        prog = _normalize(memory.best_candidate)
        print(f"best move: {problem.lab.expr_to_str(prog['move'])}")
        print(f"program:   {prog}")


if __name__ == "__main__":
    main()
