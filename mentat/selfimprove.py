"""Does mentat genuinely LEARN? A measured cold-vs-warm self-improvement benchmark.

Two offline, deterministic tests on the symbolic-regression domain:

 1. SAME-TASK: carry verified memory from prior runs into a fresh run on the same target.
    Does it solve faster / more often? (Learning, but partly memorization.)

 2. TRANSFER (the real test): accumulate verified memory across a FAMILY of source tasks,
    then test on a HELD-OUT target the system never trained on. If warm beats cold here, it
    learned reusable building blocks — generalization, not memorization, because the test
    target was never in training.

Metric: solve rate and median generations-to-solve, averaged over seeds. Everything is
deterministic (seeded) and offline (no API), so the numbers are reproducible.

  python3 -m mentat.selfimprove
"""
from __future__ import annotations

import copy
import random
import statistics

from .core import Memory, solve
from .demo import RandomProposer, SymbolicRegression

XS = [round(i * 0.2, 2) for i in range(-10, 11)]
SOURCE_TARGETS = [lambda x: x * x - 1, lambda x: x * x + x,
                  lambda x: 2 * x * x - x, lambda x: x * x - 2 * x]
HELD_OUT = lambda x: x * x - 3          # a NEW quadratic, not in the source family
SAME_TASK = lambda x: x * x - 2 * x - 1     # solvable at this budget, so warm-vs-cold is visible


def _run(problem, seed, mem, gens, k):
    return solve(problem, RandomProposer(random.Random(seed)), mem,
                 generations=gens, k=k, log=lambda *_: None)


def _summary(results) -> tuple[int, int, float | None]:
    solved = [r for r in results if r.solved]
    gens = sorted(r.generations for r in solved)
    return len(solved), len(results), (statistics.median(gens) if gens else None)


def _learn_family(targets, train_seeds, gens, k, tol) -> Memory:
    learned = Memory()
    for t in targets:
        prob = SymbolicRegression(t, XS, tol)
        for s in train_seeds:
            _run(prob, s, learned, gens, k)     # accumulate VERIFIED memory across the family
    return learned


def same_task(*, train_seeds, test_seeds, gens, k, tol):
    prob = SymbolicRegression(SAME_TASK, XS, tol)
    learned = Memory()
    for s in train_seeds:
        _run(prob, s, learned, gens, k)
    cold = [_run(prob, s, Memory(), gens, k) for s in test_seeds]
    warm = [_run(prob, s, copy.deepcopy(learned), gens, k) for s in test_seeds]
    return _summary(cold), _summary(warm)


def transfer(*, train_seeds, test_seeds, gens, k, tol):
    learned = _learn_family(SOURCE_TARGETS, train_seeds, gens, k, tol)
    test = SymbolicRegression(HELD_OUT, XS, tol)
    cold = [_run(test, s, Memory(), gens, k) for s in test_seeds]
    warm = [_run(test, s, copy.deepcopy(learned), gens, k) for s in test_seeds]
    return _summary(cold), _summary(warm), len(learned.lessons)


def main() -> int:
    cfg = dict(train_seeds=range(1, 4), test_seeds=range(20, 32), gens=40, k=24, tol=0.10)
    print("SELF-IMPROVEMENT — does verified memory make mentat learn? (offline, deterministic)\n")

    c, w = same_task(**cfg)
    print("SAME-TASK (warm = memory from prior runs on the same target):")
    print(f"  cold: solved {c[0]}/{c[1]}, median {c[2]} gens"
          f"   |   warm: solved {w[0]}/{w[1]}, median {w[2]} gens")

    tc, tw, n_lessons = transfer(**cfg)
    print("\nTRANSFER (warm = memory from a FAMILY of other tasks; test target HELD OUT):")
    print(f"  cold: solved {tc[0]}/{tc[1]}, median {tc[2]} gens"
          f"   |   warm: solved {tw[0]}/{tw[1]}, median {tw[2]} gens"
          f"   ({n_lessons} grounded lessons learned)")

    print("\n=> Warm carries VERIFIED memory only. If warm beats cold on the HELD-OUT target,")
    print("   it generalized — learned reusable building blocks, not a memorized answer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
