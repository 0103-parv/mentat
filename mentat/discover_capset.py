"""Run the discovery loop on the 3-term-AP-free domain (see mentat.cap_set):
the reasoning core proposes a construction, the verifier proves AP-free by exhaustive
counterexample search. Same kernel as mentat.discover, a second math domain.

Run:  python3 -m mentat.discover_capset
"""
from __future__ import annotations

from .cap_set import CAPSET_BASELINES, NoThreeAP
from .core import Memory, solve
from .math_lab import CodeProposer
from .reasoning import AnthropicCore, core_available


def main():
    problem = NoThreeAP(n=100, target=24)
    if not core_available():
        print("No reasoning core (needs anthropic + a key). Offline self-check: python3 -m mentat.cap_set")
        return
    proposer = CodeProposer(core=AnthropicCore(), fallback_codes=list(CAPSET_BASELINES))
    print(f"PROBLEM   {problem.statement}")
    print(f"VERIFIER  exhaustive 3-AP counterexample search at two sizes; target {problem.target}\n")
    res = solve(problem, proposer, Memory(), generations=8, k=4,
                log=lambda m: print("  " + m) if "gen " in m or "solved" in m else None)
    size = int(res.best_score) if res.best_score > 0 else 0
    print(f"\nbest VERIFIED 3-AP-free set in [1,{problem.n}]: size {size} (target {problem.target})")
    print(f"  {res.verdict.detail[:160]}")


if __name__ == "__main__":
    main()
