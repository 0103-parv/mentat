"""Illuminated math discovery — a DIVERSE catalog of verified Sidon sets.

A plain search for "the largest Sidon set" returns one answer. This illuminates the
size-vs-span frontier: for each span bucket (how far the set reaches), keep the
LARGEST set that is a *proven* Sidon set fitting in that span. The result is a whole
catalog of distinct verified constructions — the kind of frontier perfect-ruler
research actually tabulates — not a single point.

Every entry is proven by an EXHAUSTIVE pairwise-sum counterexample search (reused
from math_lab): "valid" means proven, not asserted. The candidate is the set itself
(fast, pure-Python), so the loop runs anywhere with no deps.

Run:  python3 -m mentat.discover_diverse
"""
from __future__ import annotations

import random
import statistics

from .core import Memory, Problem, Verdict, solve
from .math_lab import counterexample_sidon

SPAN_BUCKET = 10   # niche = max(set) // SPAN_BUCKET  -> the reach of the construction


class DiverseSidon(Problem):
    name = "diverse-sidon"

    def __init__(self, n: int = 100):
        self.n = n
        self.statement = f"illuminate the size-vs-span frontier of Sidon sets in [1,{n}]"

    def _as_set(self, candidate):
        if not (isinstance(candidate, (list, tuple)) and candidate):
            return None
        if not all(isinstance(x, int) and 1 <= x <= self.n for x in candidate):
            return None
        return sorted(set(candidate))

    def verify(self, candidate) -> Verdict:
        s = self._as_set(candidate)
        if s is None:
            return Verdict(False, -1e9, "malformed set", suspicious=True)
        if counterexample_sidon(s) is not None:        # exhaustive proof it's NOT Sidon
            return Verdict(False, -1e9, "two pairs share a sum (not a Sidon set)",
                           suspicious=True)
        # Open-ended (passed stays False so the loop never early-exits and keeps
        # illuminating); score = SIZE (we want the largest set per span niche).
        return Verdict(False, float(len(s)),
                       f"proven Sidon set of size {len(s)} (span {max(s)}): {s[:10]}"
                       + ("..." if len(s) > 10 else ""))

    def solved(self, v: Verdict) -> bool:
        return False                                   # illumination task: run the full budget

    def behavior(self, candidate):
        s = self._as_set(candidate)
        return None if s is None else max(s) // SPAN_BUCKET


class SidonSetProposer:
    """Mutates SETS directly (grow / shrink / shift), breeding from the illumination
    archive so the search spreads across span buckets. Growing usually breaks the
    Sidon property (-> quarantined); the valid growths are what climb each niche."""

    def __init__(self, rng: random.Random, n: int):
        self.rng = rng
        self.n = n

    def _rand(self):
        k = self.rng.randint(2, 6)
        return tuple(sorted(self.rng.sample(range(1, self.n + 1), k)))

    def _mutate(self, c):
        s = set(c)
        r = self.rng.random()
        if r < 0.55 and len(s) < self.n:               # grow (most exciting move)
            s.add(self.rng.randint(1, self.n))
        elif r < 0.8 and len(s) > 2:                   # shrink
            s.discard(self.rng.choice(sorted(s)))
        elif s:                                        # shift one element
            s.discard(self.rng.choice(sorted(s)))
            s.add(self.rng.randint(1, self.n))
        return tuple(sorted(s)) if s else self._rand()

    def propose(self, problem, memory: Memory, mind, k: int):
        ex = mind.explore_rate()
        parents = [c for _, c in memory.archive.values()] or [c for _, c in memory.elites]
        return [self._rand() if not parents or self.rng.random() < ex
                else self._mutate(self.rng.choice(parents)) for _ in range(k)]


def _catalog(memory: Memory):
    """The illuminated frontier: (span bucket, best size, the set), sorted by span."""
    rows = []
    for niche, (size, cset) in sorted(memory.archive.items()):
        rows.append((niche, int(size), cset))
    return rows


def main() -> int:
    n = 100
    seeds = list(range(1, 6))
    gens, k = 60, 24

    print("ILLUMINATED MATH DISCOVERY — a diverse catalog of PROVEN Sidon sets")
    print(f"DOMAIN   Sidon sets in [1,{n}]; niche = span bucket (max//{SPAN_BUCKET}); "
          f"quality = set size\n")

    def run():
        mem = Memory()
        for s in seeds:                                # accumulate the catalog across seeds
            solve(DiverseSidon(n), SidonSetProposer(random.Random(s), n), mem,
                  generations=gens, k=k, log=lambda *_: None)
        return mem

    mem = run()
    rows = _catalog(mem)
    print(f"  illuminated {len(rows)} span niches, each with a PROVEN Sidon set:")
    for niche, size, cset in rows:
        lo, hi = niche * SPAN_BUCKET, (niche + 1) * SPAN_BUCKET - 1
        print(f"    span {lo:>3}-{hi:<3}:  size {size:>2}   {cset[:size] if size<=10 else cset[:10]}"
              + ("..." if size > 10 else ""))
    if rows:
        best = max(rows, key=lambda r: r[1])
        print(f"\n  largest proven set found: size {best[1]} within span "
              f"{best[0]*SPAN_BUCKET}-{(best[0]+1)*SPAN_BUCKET-1}")
    print("\n=> Not one answer — a verified FRONTIER: the largest proven Sidon set at every "
          "reach.\n   A greedy search returns only the single biggest; illumination returns "
          "the whole catalog.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
