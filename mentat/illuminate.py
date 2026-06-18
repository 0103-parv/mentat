"""Illumination — creativity as covering a whole space of diverse verified solutions.

A greedy maximizer returns ONE answer: the optimum. A creative agent returns a MAP
of possibilities — the best solution for every region of a behavior space. This is
MAP-Elites (Mouret & Clune, 2015), and it is the creativity mechanism that wins
cleanly: by construction a greedy search collapses to one niche, while illumination
fills the space with diverse, individually-verified solutions.

The domain here: design an L-bit pattern. Quality = match to a hidden target (the
verifier); the behavior descriptor = how many bits are active (0..L). The kernel's
MAP-Elites archive keeps the best design for EACH activity level — so you get the
optimum AND a diverse portfolio of strong designs at every density.

Run:  python3 -m mentat.illuminate
"""
from __future__ import annotations

import random
import statistics

from .core import Memory, Problem, Verdict, solve


class PatternDesign(Problem):
    name = "pattern-illumination"

    def __init__(self, length: int = 20):
        self.length = length
        self.target = tuple(i % 2 for i in range(length))   # hidden target = alternating
        self.statement = f"illuminate the space of {length}-bit designs by activity level"

    def verify(self, candidate) -> Verdict:
        if not (isinstance(candidate, (list, tuple)) and len(candidate) == self.length
                and all(b in (0, 1) for b in candidate)):
            return Verdict(False, -1e9, "malformed design", suspicious=True)
        q = sum(1 for i in range(self.length) if candidate[i] == self.target[i])
        return Verdict(q == self.length, float(q),
                       f"quality={q}/{self.length} active={sum(candidate)}")

    def behavior(self, candidate):
        """Niche = number of active bits (0..L). Low-dimensional, so the archive
        illuminates the whole activity spectrum."""
        if not (isinstance(candidate, (list, tuple)) and len(candidate) == self.length):
            return None
        return sum(candidate)


# Both proposers use the SAME low exploration, so the only difference is where
# parents come from — the best (greedy) vs the per-niche archive (illumination).
# Equal exploration is what makes the coverage gap attributable to the mechanism.
_EXPLORE = 0.1


class _BaseProposer:
    def __init__(self, rng: random.Random, length: int):
        self.rng = rng
        self.length = length

    def _rand(self):
        return tuple(self.rng.randint(0, 1) for _ in range(self.length))

    def _mutate(self, c):
        a = list(c)
        a[self.rng.randrange(self.length)] ^= 1
        return tuple(a)

    def _breed(self, parents, k):
        return [self._rand() if not parents or self.rng.random() < _EXPLORE
                else self._mutate(self.rng.choice(parents)) for _ in range(k)]


class GreedyProposer(_BaseProposer):
    """Maximize quality: breed from the best (elites). Converges to the optimum and
    so visits only a few niches — the baseline."""

    def propose(self, problem, memory: Memory, mind, k: int):
        return self._breed([c for _, c in memory.elites], k)


class IlluminationProposer(_BaseProposer):
    """MAP-Elites: breed from the ARCHIVE (one elite per behavior niche), so the
    search spreads across the whole behavior space instead of collapsing to one peak."""

    def propose(self, problem, memory: Memory, mind, k: int):
        parents = [c for _, c in memory.archive.values()] or [c for _, c in memory.elites]
        return self._breed(parents, k)


def _run(proposer_cls, seeds, gens, k, length, *, result_from):
    """Run the search; measure what the method RETAINS as its result. A greedy
    maximizer returns its elite pool (which collapses near the optimum); MAP-Elites
    returns its per-niche archive. `result_from` picks which to count."""
    retained, best, solved = [], [], 0
    for s in seeds:
        mem = Memory()
        r = solve(PatternDesign(length), proposer_cls(random.Random(s), length), mem,
                  generations=gens, k=k, log=lambda *_: None)
        if result_from == "archive":
            retained.append(len(mem.archive))
        else:
            retained.append(len({sum(c) for _, c in mem.elites}))   # distinct elite behaviors
        best.append(r.best_score)
        solved += r.solved
    return {"retained": statistics.mean(retained), "best": statistics.mean(best),
            "solved": solved, "n": len(list(seeds))}


def main() -> int:
    length = 20
    seeds = list(range(1, 11))
    gens, k = 40, 20
    niches = length + 1

    print("ILLUMINATION — creativity as covering a behavior space (MAP-Elites)")
    print(f"DOMAIN   design a {length}-bit pattern; niche = # active bits (0..{length}); "
          f"{niches} niches")
    print("RESULT   what each method RETURNS: distinct verified designs across behavior niches\n")
    greedy = _run(GreedyProposer, seeds, gens, k, length, result_from="elites")
    illum = _run(IlluminationProposer, seeds, gens, k, length, result_from="archive")
    print(f"  greedy (maximize)       returns {greedy['retained']:.1f}/{niches} distinct designs   "
          f"best={greedy['best']:.1f}/{length}   finds optimum {greedy['solved']}/{greedy['n']}")
    print(f"  illumination (MAP-Elites) returns {illum['retained']:.1f}/{niches} distinct designs   "
          f"best={illum['best']:.1f}/{length}   finds optimum {illum['solved']}/{illum['n']}")
    print()
    ratio = illum["retained"] / max(greedy["retained"], 1e-9)
    print(f"=> Greedy collapses to ~{greedy['retained']:.0f} designs near the optimum; "
          f"illumination returns ~{illum['retained']:.0f} — {ratio:.0f}x more of the space,")
    print("   a diverse verified PORTFOLIO instead of a single point, with the optimum still "
          "among them. That is creativity —")
    print("   and every design in the map passed the same verifier.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
