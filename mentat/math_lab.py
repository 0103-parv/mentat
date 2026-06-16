"""Math / algorithm discovery for the Mentat kernel (FunSearch-lineage).

The reasoning core proposes a CONSTRUCTION as Python code. The verifier:
  1. EXECUTES it in a restricted sandbox (no imports, safe builtins, a timeout), and
  2. ADVERSARIALLY SEARCHES for a counterexample to the defining property.

A construction that the search breaks is quarantined (the kernel's existing
quarantine path). A construction that survives enters the verified library (the
elite pool), and the loop pushes for larger ones. This is the same kernel as the
toy demo — propose / verify / remember / reflect — pointed at real, checkable math.

Flagship problem: the largest Sidon set in [1, n] (a set whose pairwise sums are
all distinct). The verifier's counterexample search is exhaustive over pairs, so
"valid" here means *proven* valid, not asserted.

Run:  python3 -m mentat.discover     (needs a reasoning core; see mentat.reasoning)
"""
from __future__ import annotations

import builtins
import signal
from dataclasses import dataclass, field

from .core import Lesson, Memory, Mind, Problem, Verdict
from .reasoning import extract_code_blocks

# --------------------------------------------------------------------------- #
# restricted execution of model-proposed code                                 #
# --------------------------------------------------------------------------- #
_SAFE_BUILTINS = {n: getattr(builtins, n) for n in (
    "range len abs min max sum sorted set list dict tuple int float bool "
    "enumerate zip map filter reversed all any round pow divmod True False None"
).split() if hasattr(builtins, n)}

_FORBIDDEN = ("import", "__", "exec(", "eval(", "compile(", "globals(", "locals(",
              "getattr", "setattr", "open(", "input(", "subprocess", "os.", "sys.",
              "socket", "lambda")  # lambda banned only to keep the static scan simple


def run_construction(code: str, n: int, time_limit: float = 2.0) -> list[int]:
    """Execute a candidate `def build(n): ...` under tight restrictions and return
    the integer list it produces. Raises on anything unsafe, malformed, or slow."""
    for tok in _FORBIDDEN:
        if tok in code:
            raise ValueError(f"forbidden construct: {tok!r}")
    compiled = compile(code, "<candidate>", "exec")
    ns: dict = {"__builtins__": _SAFE_BUILTINS}

    def _timeout(signum, frame):
        raise TimeoutError("construction exceeded the time limit")

    prev = signal.signal(signal.SIGALRM, _timeout)
    signal.setitimer(signal.ITIMER_REAL, time_limit)
    try:
        exec(compiled, ns)
        build = ns.get("build")
        if not callable(build):
            raise ValueError("no build(n) defined")
        raw = build(n)
        result = [int(x) for x in raw]
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, prev)

    if any(x < 1 or x > n for x in result):
        raise ValueError("an element fell outside [1, n]")
    return sorted(set(result))


def counterexample_sidon(s: list[int]):
    """Exhaustive counterexample search: return two pairs with equal sum, or None.
    None means the Sidon property is *proven* over this set (all pairs checked)."""
    seen: dict[int, tuple[int, int]] = {}
    for i in range(len(s)):
        for j in range(i, len(s)):
            total = s[i] + s[j]
            if total in seen:
                return (seen[total], (s[i], s[j]))
            seen[total] = (s[i], s[j])
    return None


# --------------------------------------------------------------------------- #
# the problem: verifier IS the problem                                        #
# --------------------------------------------------------------------------- #
class SidonSet(Problem):
    name = "largest-sidon-set"

    def __init__(self, n: int = 200, target: int = 14, check_ns: list[int] | None = None):
        self.n = n
        self.target = target
        # Validity is checked at a SECOND size too, so a construction hardcoded for
        # n can't fake it — a real algorithm generalises; a memorised table doesn't.
        self.check_ns = check_ns or [n, n // 2 + 11]
        self.statement = f"find the largest Sidon set in [1, {n}]"

    def brief(self) -> str:
        return (f"Find a Sidon set in [1, {self.n}]: a set of distinct integers in which "
                f"every pairwise sum a+b (with a <= b) is DISTINCT. Maximise the size of "
                f"the set. The construction must be a general algorithm in n — it is also "
                f"checked at a second, smaller n, so a table hardcoded for one n will fail. "
                f"Reaching size {self.target} counts as solved.")

    def verify(self, code) -> Verdict:
        try:
            primary = None
            for n in self.check_ns:
                s = run_construction(code, n)
                witness = counterexample_sidon(s)
                if witness is not None:
                    (a, b), (c, d) = witness
                    return Verdict(False, -1e9,
                                   f"counterexample at n={n}: {a}+{b} = {c}+{d} = {a + b} "
                                   f"(two pairs, same sum — not a Sidon set)", suspicious=True)
                if n == self.n:
                    primary = s
            size = len(primary)
            shown = primary[:12]
            tail = "..." if size > 12 else ""
            return Verdict(size >= self.target, float(size),
                           f"verified Sidon set of size {size} in [1,{self.n}]: {shown}{tail}")
        except (ValueError, TimeoutError, ArithmeticError, TypeError, IndexError,
                KeyError, RecursionError, MemoryError, AttributeError) as e:
            return Verdict(False, -1e9, f"rejected: {type(e).__name__}: {e}", suspicious=True)

    def distill(self, best_candidate, best_verdict) -> list[Lesson]:
        if best_candidate is None or best_verdict is None or not best_verdict.detail:
            return []
        # claim shares real vocabulary with the evidence (sidon / set / size / pairwise)
        # so the grounding firewall passes honestly.
        return [Lesson(
            when="building a large sidon set with distinct pairwise sums",
            do="reuse the verified construction reaching this set size",
            avoid="sets with two pairs sharing a pairwise sum",
            evidence=best_verdict.detail,
        )]


# --------------------------------------------------------------------------- #
# baseline constructions (offline fallback + something to evolve from)         #
# --------------------------------------------------------------------------- #
GREEDY = """
def build(n):
    chosen = []
    sums = set()
    for x in range(1, n + 1):
        fresh = []
        ok = True
        for a in chosen:
            s = a + x
            if s in sums or s in fresh:
                ok = False
                break
            fresh.append(s)
        d = x + x
        if ok and d not in sums and d not in fresh:
            fresh.append(d)
            chosen.append(x)
            for s in fresh:
                sums.add(s)
    return chosen
""".strip()

POWERS = """
def build(n):
    out = []
    x = 1
    while x <= n:
        out.append(x)
        x = x * 2
    return out
""".strip()


@dataclass
class CodeProposer:
    """The reasoning core proposing programs. Candidates are code strings; the
    verifier executes and counterexample-checks each. Any shortfall is filled with
    baseline constructions so the loop never starves (and runs offline in tests)."""
    core: object
    fallback_codes: list = field(default_factory=lambda: [GREEDY, POWERS])
    last: list = field(default_factory=list)
    note: str = ""

    _SYSTEM = (
        "You are the reasoning core of a mathematical discovery engine. You propose "
        "constructions as Python code; an independent verifier EXECUTES each one and "
        "SEARCHES exhaustively for a counterexample, so only proven-valid constructions "
        "are kept and larger valid ones win. Use only basic Python — no imports, no I/O. "
        "Each candidate is a complete `def build(n):` returning a list of distinct "
        "integers in [1, n]. Put each candidate in its own ```python code block."
    )
    _MODE = {
        "focus": "Refine the best-known construction to push the size higher.",
        "dream": "Try a structurally different idea (number-theoretic, greedy, search).",
        "recover": "Fall back to a simple, certainly-valid construction.",
    }

    def propose(self, problem, memory: Memory, mind: Mind, k: int):
        best = memory.elites[0][1] if memory.elites else None
        best_block = (f"\n\nBest verified construction so far — improve on it:\n```python\n{best}\n```"
                      if best else "")
        ctx = memory.context(k=5) or "(no lessons yet)"
        user = (f"{problem.brief()}\n\nLessons so far:\n{ctx}{best_block}\n\n"
                f"Search mode: {mind.mode} — {self._MODE[mind.mode]}\n"
                f"Propose {k} different `def build(n):` constructions, each in its own "
                f"```python block. Maximise the set size while keeping all pairwise sums distinct.")
        out, self.last, self.note = [], [], ""
        try:
            text = self.core.complete_text(self._SYSTEM, user, max_tokens=3500)
            for block in extract_code_blocks(text)[:k]:
                out.append(block)
                head = next((ln.strip() for ln in block.splitlines()
                             if ln.strip() and not ln.strip().startswith("#")), "def build")
                self.last.append(head[:64])
        except Exception as e:                      # network/SDK/auth — degrade
            self.note = f"core error ({type(e).__name__}); using baseline constructions"
        i = 0
        while len(out) < k and self.fallback_codes:
            out.append(self.fallback_codes[i % len(self.fallback_codes)])
            i += 1
        return out
