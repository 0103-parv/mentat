"""Point the kernel at real math: discover the largest Sidon set in [1, n].

The reasoning core proposes constructions; the verifier executes each and searches
exhaustively for a counterexample. Quarantined proposals are ones the search broke;
the verified library is everything that survived. Same kernel as mentat.demo.

Run:  python3 -m mentat.discover
"""
from __future__ import annotations

import random

from .core import BrainConfig, Memory, solve
from .math_lab import CodeProposer, GREEDY, POWERS, SidonSet
from .reasoning import AnthropicCore, core_available


def _first_line(code: str) -> str:
    for ln in code.splitlines():
        if ln.strip() and not ln.strip().startswith("#"):
            return ln.strip()
    return code[:60]


def _logger(proposer: CodeProposer):
    def log(msg: str):
        if proposer.note:
            print(f"      [{proposer.note}]")
        elif proposer.last:
            print(f"      core proposed {len(proposer.last)}: {proposer.last[0]} ...")
        print(f"   {msg}   (quarantine = fraction caught by counterexample search)")
    return log


def main():
    problem = SidonSet(n=200, target=17)   # a stretch near the known frontier (~15-16)

    if not core_available():
        print("No reasoning core available — running the OFFLINE baselines only.")
        print("  (for the real discovery loop: pip install anthropic + an API key)\n")
        core = None
    else:
        core = AnthropicCore()

    proposer = (CodeProposer(core=core) if core
                else CodeProposer(core=_Broken(), fallback_codes=[GREEDY, POWERS]))

    head = core.model if core else "offline baselines"
    print(f"REASONING CORE   {head}")
    print(f"PROBLEM          {problem.statement}")
    print(f"GATE             a construction is kept only if an exhaustive pairwise-sum")
    print(f"                 counterexample search finds NOTHING (checked at n=200 and a")
    print(f"                 second smaller n, so a hardcoded table can't fake it)\n")

    memory = Memory()
    # Brain ON: the quality-diversity pool keeps a DIVERSE library of verified
    # constructions (creativity), not just near-duplicates of the single largest.
    result = solve(problem, proposer, memory, generations=8, k=5,
                   log=_logger(proposer), brain=BrainConfig())

    print()
    if result.solved:
        print(f"DISCOVERED a verified Sidon set of size {int(result.best_score)} "
              f"(target {problem.target}) in {result.generations} generations.")
    else:
        best = int(result.best_score) if result.best_score > 0 else 0
        print(f"Best VERIFIED Sidon set after {result.generations} generations: size {best} "
              f"(target {problem.target}).")
    print(f"  {result.verdict.detail}")

    lib = [(int(s), c) for s, c in memory.elites if s > 0]
    if lib:
        print(f"\nverified library ({len(lib)} constructions survived the counterexample search):")
        for size, code in lib[:4]:
            print(f"  size {size:>2}:  {_first_line(code)[:70]}")
    if memory.best_candidate:
        print("\nbest construction (the discovery):")
        for ln in str(memory.best_candidate).splitlines():
            print(f"    {ln}")


class _Broken:
    """Forces the proposer onto its baseline constructions when no core exists."""
    def complete_text(self, *a, **k):
        raise RuntimeError("no core")


if __name__ == "__main__":
    main()
