"""A second math-discovery domain: the largest 3-term-AP-free set in [1, n].

The 1-D analogue of the cap-set problem (and a face of Roth's theorem): find a large
subset of [1, n] with NO three elements a < b < c in arithmetic progression
(a + c = 2b). Reuses math_lab's sandboxed `run_construction` and the same
propose -> execute -> exhaustively-search-for-a-counterexample loop as the Sidon
domain — so the reasoning core proposes a construction as code, and only sets the
verifier *proves* AP-free (every pair checked) survive.

Run:  python3 -m mentat.discover_capset      (needs a reasoning core)
Offline self-check:  python3 -m mentat.cap_set
"""
from __future__ import annotations

from .core import Lesson, Problem, Verdict
from .math_lab import run_construction


def counterexample_3ap(s: list[int]):
    """Exhaustive search: return a 3-term AP (a, b, c) in the set, or None.
    None means AP-free is *proven* over this set (all pairs checked)."""
    present = set(s)
    for i in range(len(s)):
        for k in range(i + 1, len(s)):
            total = s[i] + s[k]
            if total % 2 == 0:
                mid = total // 2
                if mid != s[i] and mid != s[k] and mid in present:
                    return (s[i], mid, s[k])      # s[i] < mid < s[k], an arithmetic progression
    return None


# Offline fallbacks + something for the core to evolve from.
# The base-3 construction (integers whose base-3 digits avoid 2) is the classic
# AP-free set, of size ~ n^0.63.
BASE3 = """
def build(n):
    out = []
    for x in range(1, n + 1):
        y, ok = x, True
        while y > 0:
            if y % 3 == 2:
                ok = False
                break
            y //= 3
        if ok:
            out.append(x)
    return out
""".strip()

GREEDY3 = """
def build(n):
    chosen, have = [], set()
    for x in range(1, n + 1):
        ok = True
        for b in chosen:
            if (2 * b - x) in have:        # a=2b-x already in -> a,b,x is a 3-AP
                ok = False
                break
        if ok:
            chosen.append(x)
            have.add(x)
    return chosen
""".strip()

CAPSET_BASELINES = [BASE3, GREEDY3]


class NoThreeAP(Problem):
    name = "largest-3AP-free-set"

    def __init__(self, n: int = 100, target: int | None = None, check_ns: list[int] | None = None):
        self.n = n
        self.target = target if target is not None else max(2, int(n ** 0.62))
        self.check_ns = check_ns or [n, n // 2 + 7]
        if n not in self.check_ns:                  # self.n must be scored
            self.check_ns = [n] + self.check_ns
        self.statement = f"find the largest 3-term-AP-free set in [1, {n}]"

    def brief(self) -> str:
        return (f"Find a large subset of [1, {self.n}] with NO 3-term arithmetic progression: no "
                f"three elements a<b<c where b is the exact midpoint (a+c = 2b). Maximise the size. "
                f"The construction must be a general algorithm in n — it is also checked at a "
                f"second, smaller n, so a table hardcoded for one n will fail. Reaching size "
                f"{self.target} counts as solved. (A classic idea: keep the integers whose base-3 "
                f"digits avoid a 2.)")

    def verify(self, code) -> Verdict:
        try:
            primary = None
            for n in self.check_ns:
                s = run_construction(code, n)
                w = counterexample_3ap(s)
                if w is not None:
                    a, b, c = w
                    return Verdict(False, -1e9, f"counterexample at n={n}: {a},{b},{c} is a 3-AP "
                                   f"({a}+{c} = 2*{b})", suspicious=True)
                if n == self.n:
                    primary = s
            size = len(primary)
            if size == 0:
                return Verdict(False, -1e9, "construction produced an empty set", suspicious=True)
            shown = primary[:12]
            return Verdict(size >= self.target, float(size),
                           f"verified 3-AP-free set of size {size} in [1,{self.n}]: {shown}"
                           f"{'...' if size > 12 else ''}")
        except (ValueError, TimeoutError, ArithmeticError, TypeError, IndexError, KeyError,
                RecursionError, MemoryError, AttributeError) as e:
            return Verdict(False, -1e9, f"rejected: {type(e).__name__}: {e}", suspicious=True)

    def solved(self, v: Verdict) -> bool:
        return v.passed

    def distill(self, best_candidate, best_verdict) -> list[Lesson]:
        if best_candidate is None or best_verdict is None or not best_verdict.detail:
            return []
        return [Lesson(
            when="building a large 3-term-AP-free set in the range",
            do="reuse the verified construction reaching this set size",
            avoid="sets containing three elements in arithmetic progression",
            evidence=best_verdict.detail)]


def _selftest():
    assert counterexample_3ap([1, 2, 3]) == (1, 2, 3)            # 1,2,3 is a 3-AP
    assert counterexample_3ap([1, 2, 4, 8, 9]) is None           # AP-free
    prob = NoThreeAP(n=81, target=1000)                          # target huge -> never "solved"
    v = prob.verify(BASE3)
    assert not v.suspicious and v.score >= 12, v.detail          # base-3 set is valid + sizable
    bad = prob.verify("def build(n):\n    return [1, 2, 3, 4, 5]")
    assert bad.suspicious                                        # contains 3-APs -> rejected
    print(f"cap_set self-check OK — base-3 AP-free set in [1,81]: {v.detail}")


if __name__ == "__main__":
    _selftest()
