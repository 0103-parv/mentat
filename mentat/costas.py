"""Costas-array discovery — a 2nd verified-discovery domain (the kernel generalizes).

A Costas array of order n is a permutation p of {1..n} in which every displacement vector
(j-i, p[j]-p[i]) between a pair of points is DISTINCT — a 2-D analogue of a Sidon set, used
in radar/sonar because it gives an ideal "thumbtack" ambiguity function. The verifier
exhaustively checks all O(n^2) pairwise displacements, so "valid" means PROVEN, not asserted.

Same kernel as the Sidon discovery: propose a permutation, verify, keep what's proven, and
the loop climbs by reducing displacement collisions until none remain. Pure-Python, offline.

  python3 -m mentat.costas          # discover a verified Costas array
"""
from __future__ import annotations

import random

from .core import BrainConfig, Memory, Problem, Verdict, solve


class CostasArray(Problem):
    name = "costas-array"

    def __init__(self, n: int = 8):
        self.n = n
        self.statement = f"find a Costas array of order {n} (a permutation with all distinct "
        self.statement += "pairwise displacement vectors)"

    def verify(self, candidate) -> Verdict:
        if not (isinstance(candidate, (list, tuple))
                and sorted(candidate) == list(range(1, self.n + 1))):
            return Verdict(False, -1e9, "not a permutation of 1..n", suspicious=True)
        seen: set[tuple[int, int]] = set()
        collisions = 0
        for i in range(self.n):
            for j in range(i + 1, self.n):
                v = (j - i, candidate[j] - candidate[i])
                if v in seen:
                    collisions += 1
                else:
                    seen.add(v)
        ok = collisions == 0
        detail = (f"PROVEN Costas array of order {self.n}: {tuple(candidate)} "
                  "(all pairwise displacement vectors distinct)" if ok
                  else f"{collisions} displacement collisions")
        return Verdict(ok, float(-collisions), detail)   # score climbs to 0 == solved

    def solved(self, v: Verdict) -> bool:
        return v.passed


class CostasProposer:
    """Propose permutations; breed from verified-better ones by swapping two positions
    (a swap changes only the displacement vectors touching those two points)."""

    def __init__(self, rng: random.Random, n: int):
        self.rng = rng
        self.n = n

    def _rand(self):
        p = list(range(1, self.n + 1))
        self.rng.shuffle(p)
        return tuple(p)

    def _mutate(self, p):
        a = list(p)
        i, j = self.rng.randrange(self.n), self.rng.randrange(self.n)
        a[i], a[j] = a[j], a[i]
        return tuple(a)

    def propose(self, problem, memory: Memory, mind, k: int):
        ex = mind.explore_rate()
        pool = [c for _, c in memory.elites]
        return [self._rand() if not pool or self.rng.random() < ex
                else self._mutate(self.rng.choice(pool)) for _ in range(k)]


def discover_costas(n: int = 8, *, seed: int = 0, generations: int = 40, k: int = 24):
    return solve(CostasArray(n), CostasProposer(random.Random(seed), n), Memory(),
                 generations=generations, k=k, log=lambda *_: None, brain=BrainConfig())


def main() -> int:
    n = 9
    print(f"COSTAS-ARRAY DISCOVERY — order {n} (a 2-D Sidon set; radar/sonar)")
    print("GATE   exhaustive: ALL pairwise displacement vectors must be distinct\n")
    r = discover_costas(n, generations=60, k=24)
    if r.solved:
        print(f"DISCOVERED (proven): {r.verdict.detail}")
    else:
        print(f"Best after {r.generations} gens: {-int(r.best_score)} collisions remaining "
              f"(order {n} is harder — raise the budget).")
    print("\n=> Same kernel as the Sidon engine, a genuinely different problem — propose,")
    print("   verify exhaustively, keep only what's proven. The gate generalizes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
