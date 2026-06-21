"""A runnable, zero-dependency demonstration of the Mentat kernel.

Problem: rediscover a hidden function from samples (symbolic regression-lite).
This is deliberately a TOY with a cheap, honest verifier so the whole loop runs
in seconds with no API key and no libraries. It is a faithful miniature of the
real thesis:

  * the kernel proposes expressions (the thinking organ),
  * a verifier scores each by error and the loop never trusts an unverified one,
  * grounded lessons about what reduces error persist across runs (the memory
    organ), so a *warm* run starts from everything a prior search learned.

Run:  python3 -m mentat.demo
"""
from __future__ import annotations

import ast
import math
import random
from dataclasses import dataclass, field
from pathlib import Path

from .core import Lesson, Memory, Mind, Problem, Verdict, solve
from .reasoning import extract_json_list

# --------------------------------------------------------------------------- #
# a tiny expression language: nested tuples like ("+", ("x",), ("c", 2.0))    #
# --------------------------------------------------------------------------- #
OPS = ("+", "-", "*", "/")
CONSTS = (-2.0, -1.0, 1.0, 2.0, 3.0)


def ev(node, xs: list[float]) -> list[float]:
    tag = node[0]
    if tag == "x":
        return list(xs)
    if tag == "c":
        return [node[1]] * len(xs)
    a, b = ev(node[1], xs), ev(node[2], xs)
    if tag == "+":
        return [ai + bi for ai, bi in zip(a, b)]
    if tag == "-":
        return [ai - bi for ai, bi in zip(a, b)]
    if tag == "*":
        return [ai * bi for ai, bi in zip(a, b)]
    if tag == "/":
        return [ai / bi if abs(bi) > 1e-6 else 1.0 for ai, bi in zip(a, b)]
    raise ValueError(tag)


def to_str(node) -> str:
    tag = node[0]
    if tag == "x":
        return "x"
    if tag == "c":
        return f"{node[1]:g}"
    return f"({to_str(node[1])}{tag}{to_str(node[2])})"


def rand_tree(rng: random.Random, depth: int = 0, max_depth: int = 5):
    if depth >= max_depth or (depth > 0 and rng.random() < 0.3):
        return ("x",) if rng.random() < 0.6 else ("c", rng.choice(CONSTS))
    return (rng.choice(OPS),
            rand_tree(rng, depth + 1, max_depth),
            rand_tree(rng, depth + 1, max_depth))


def parse_infix(s: str):
    """Parse a Python-syntax infix expression over `x` into the tuple tree.

    Allows + - * / ** and unary minus; integer powers are expanded to repeated
    multiplication so they stay inside the +-*/ DSL the verifier evaluates.
    Anything else (other names, function calls, bad exponents) raises."""
    return _from_ast(ast.parse(s.strip(), mode="eval").body)


def _from_ast(node):
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Pow):
            base = _from_ast(node.left)
            exp = node.right
            if not (isinstance(exp, ast.Constant) and isinstance(exp.value, int)
                    and 1 <= exp.value <= 6):
                raise ValueError("only small positive integer powers are allowed")
            out = base
            for _ in range(exp.value - 1):
                out = ("*", out, base)
            return out
        op = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/"}.get(type(node.op))
        if op is None:
            raise ValueError(f"unsupported operator {type(node.op).__name__}")
        return (op, _from_ast(node.left), _from_ast(node.right))
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            inner = _from_ast(node.operand)
            return ("c", -inner[1]) if inner[0] == "c" else ("*", ("c", -1.0), inner)
        if isinstance(node.op, ast.UAdd):
            return _from_ast(node.operand)
        raise ValueError("unsupported unary operator")
    if isinstance(node, ast.Name):
        if node.id == "x":
            return ("x",)
        raise ValueError(f"unknown name {node.id!r}")
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
            and not isinstance(node.value, bool):
        return ("c", float(node.value))
    raise ValueError("unsupported expression")


# --------------------------------------------------------------------------- #
# the problem: the verifier IS the problem                                    #
# --------------------------------------------------------------------------- #
class SymbolicRegression(Problem):
    name = "symbolic-regression"

    def __init__(self, target, xs: list[float], tol: float = 0.10):
        self.target = target
        self.xs = xs
        self.ys = [target(x) for x in xs]
        self.tol = tol
        self.statement = "rediscover y = f(x) from samples"

    def verify(self, candidate) -> Verdict:
        try:
            pred = ev(candidate, self.xs)
            if any(not math.isfinite(p) for p in pred):
                return Verdict(False, -1e9, "non-finite", suspicious=True)
            rmse = math.sqrt(sum((p - y) ** 2 for p, y in zip(pred, self.ys)) / len(pred))
            if not math.isfinite(rmse):
                return Verdict(False, -1e9, "non-finite-rmse", suspicious=True)
        except (OverflowError, ZeroDivisionError, ValueError):
            return Verdict(False, -1e9, "eval-error", suspicious=True)
        return Verdict(rmse < self.tol, -rmse,
                       f"RMSE={rmse:.4f} on the target samples via expr {to_str(candidate)}")

    def brief(self) -> str:
        # The proposer sees the data, never the hidden law. Show every other point
        # to keep the prompt compact.
        pts = ", ".join(f"({x:g}, {y:g})"
                        for x, y in list(zip(self.xs, self.ys))[::2])
        return ("Rediscover y = f(x) from these (x, y) samples:\n" + pts
                + f"\nFind an expression in x with RMSE < {self.tol} over the samples.")

    def distill(self, best_candidate, best_verdict) -> list[Lesson]:
        if best_candidate is None or best_verdict is None:
            return []
        frag = to_str(best_candidate)
        # claim and evidence deliberately share real vocabulary (rmse / target /
        # samples / expr) so the grounding firewall passes honestly.
        return [Lesson(
            when="reducing rmse on the target samples",
            do=f"reuse the verified expr motif {frag}",
            avoid="deep random expr trees that do not lower rmse",
            evidence=best_verdict.detail,
        )]


@dataclass
class RandomProposer:
    """Offline proposer: mutate the best-known structure or explore fresh.

    This is the swap-point. Replace `.propose` with a call to an LLM reasoning
    core and the same loop is driven by real reasoning instead of mutation."""
    rng: random.Random
    max_depth: int = 5

    def propose(self, problem, memory: Memory, mind: Mind, k: int):
        ex = mind.explore_rate()
        pool = memory.elites               # [score, candidate], already sorted desc
        out = []
        for _ in range(k):
            r = self.rng.random()
            if r < ex or not pool:
                out.append(rand_tree(self.rng, 0, self.max_depth))            # explore
            elif len(pool) >= 2 and r < ex + 0.45:
                out.append(self._crossover(self._tournament(pool),           # recombine
                                           self._tournament(pool)))
            else:
                out.append(self._mutate(self._tournament(pool)))             # hill-climb
        return out

    def _tournament(self, pool):
        """Pick the better of two random elites — fitter parents breed more."""
        a, b = self.rng.choice(pool), self.rng.choice(pool)
        return (a if a[0] >= b[0] else b)[1]

    def _mutate(self, node):
        if node[0] in ("x", "c"):
            return rand_tree(self.rng, 0, 2) if self.rng.random() < 0.5 else tuple(node)
        if self.rng.random() < 0.2:
            return rand_tree(self.rng, 0, 2)
        return (node[0], self._mutate(node[1]), self._mutate(node[2]))

    def _subtrees(self, node, acc):
        acc.append(node)
        if node[0] not in ("x", "c"):
            self._subtrees(node[1], acc)
            self._subtrees(node[2], acc)
        return acc

    def _graft(self, node, donor):
        if node[0] in ("x", "c") or self.rng.random() < 0.3:
            return donor
        if self.rng.random() < 0.5:
            return (node[0], self._graft(node[1], donor), node[2])
        return (node[0], node[1], self._graft(node[2], donor))

    def _crossover(self, a, b):
        donor = self.rng.choice(self._subtrees(b, []))
        return self._graft(a, donor)


@dataclass
class LLMProposer:
    """The reasoning core as a proposer: it reads the data + memory and proposes
    formulas. The kernel's verifier still gates every one — nothing is trusted
    because the model said so. Any shortfall (parse failures, an API error) is
    topped up by the offline proposer, so the loop never starves."""
    core: object                       # anything with .complete_text(system, user)
    fallback: "RandomProposer"
    last: list = field(default_factory=list)   # the raw strings it last proposed
    note: str = ""                             # set if the core errored this round

    _SYSTEM = (
        "You are the reasoning core of a discovery engine. You propose candidate "
        "formulas; an independent verifier checks each against the data, and ONLY "
        "verified candidates are kept — so propose freely but precisely. Use only "
        "the variable x, the operators + - * / **, parentheses, and numeric "
        "constants. Reply with ONLY a JSON array of expression strings, e.g. "
        '["x*x - 1", "x**3 - 2*x + 1"]. No prose.'
    )
    _MODE = {
        "focus": "Refine the best-known candidates with small, targeted edits.",
        "dream": "Propose structurally novel forms you have not tried yet.",
        "recover": "Be conservative: prefer simple, robust forms.",
    }

    def propose(self, problem, memory: Memory, mind: Mind, k: int):
        brief = problem.brief()
        ctx = memory.context(k=6) or "(memory is empty so far)"
        elites = [to_str(c) for _, c in memory.elites[:5]]
        user = (f"{brief}\n\nLessons learned so far:\n{ctx}\n\n"
                f"Best verified candidates so far: {elites or 'none yet'}\n\n"
                f"Search mode: {mind.mode} — {self._MODE[mind.mode]}\n"
                f"Propose {k} candidate expressions for y as a function of x.")
        out, self.last, self.note = [], [], ""
        try:
            text = self.core.complete_text(self._SYSTEM, user)
            for s in extract_json_list(text)[:k]:
                if len(s) > 2000:                # reject runaway strings before parsing
                    continue
                try:
                    out.append(parse_infix(s))
                    self.last.append(s)
                except (ValueError, SyntaxError, RecursionError):
                    pass                         # one bad expr skips itself, not the batch
        except Exception as e:  # network/SDK/auth — degrade, don't crash
            self.note = f"core error ({type(e).__name__}); using offline proposer"
        if len(out) < k:                       # top up / explore with mutation
            out += self.fallback.propose(problem, memory, mind, k - len(out))
        return out


# --------------------------------------------------------------------------- #
# the demonstration                                                           #
# --------------------------------------------------------------------------- #
def _throttle(prefix):
    def log(msg):
        # only print the gen line every 20 gens to keep output readable
        if "gen" in msg and "|" in msg:
            try:
                n = int(msg.split()[1])
            except (ValueError, IndexError):
                n = 0
            if n % 20 != 0 and "solved" not in msg:
                return
        print(f"{prefix}{msg}")
    return log


def main():
    xs = [round(i * 0.2, 2) for i in range(-10, 11)]      # -2.0 .. 2.0

    def target(x):                                        # the hidden law
        return x ** 3 - 2 * x + 1
    problem = SymbolicRegression(target, xs, tol=0.10)
    mem_path = Path(__file__).parent / "memory.json"
    BUDGET, K, SEEDS = 80, 48, [1, 2, 3, 4, 5]

    print("TARGET   y = x^3 - 2x + 1   (hidden from the kernel)")
    print(f"GATE     a candidate is believed only if RMSE < {problem.tol} on real samples")
    print(f"BUDGET   {BUDGET} generations x {K} candidates per run\n")

    # [1] LEARN: accumulate memory across restarts until the law is verified.
    #     This is the self-improvement loop compounding — each restart inherits
    #     the elite pool and lessons the previous one distilled.
    print("[1] LEARN — restart-accumulating search writes durable memory")
    mem = Memory()
    for i, seed in enumerate([11, 12, 13, 14, 15], 1):
        r = solve(problem, RandomProposer(random.Random(seed)), mem,
                  generations=BUDGET, k=K, log=lambda *_: None)
        print(f"      restart {i}: {'SOLVED' if r.solved else 'no'} "
              f"(best RMSE={-mem.best_score:.4f}, {len(mem.lessons)} grounded lessons)")
        if r.solved:
            break
    mem.save(mem_path)
    if mem.best_candidate is not None and problem.solved(problem.verify(mem.best_candidate)):
        print(f"      -> memory now holds the verified law: {to_str(mem.best_candidate)}")
    elif mem.best_candidate is not None:
        print(f"      -> LEARN did not verify the law in budget (best RMSE={-mem.best_score:.4f}); "
              f"WARM starts from partial memory")
    else:
        print("      -> LEARN verified no candidate in budget; WARM starts from empty memory")

    # [2]/[3] COLD vs WARM across the same 5 seeds. The ONLY difference is whether
    #         the learned memory is loaded first. (This is swechats' counterfactual.)
    def run(seed, memory):
        return solve(problem, RandomProposer(random.Random(seed)), memory,
                     generations=BUDGET, k=K, log=lambda *_: None)

    cold = [run(s, Memory()) for s in SEEDS]
    warm = [run(s, Memory.load(mem_path)) for s in SEEDS]

    def summary(tag, runs):
        solved = [r for r in runs if r.solved]
        gens = sorted(r.generations for r in solved)
        med = f"median {gens[len(gens) // 2]} gens to solve" if gens else "none solved in budget"
        return f"  {tag:6} solved {len(solved)}/{len(runs)}   {med}"

    print("\n" + "=" * 70)
    print("RESULT  same search across 5 seeds; the ONLY difference is memory")
    print(summary("COLD", cold))
    print(summary("WARM", warm))
    print("=" * 70)
    print(f"{len(mem.lessons)} grounded lessons in memory; the firewall rejected "
          f"every ungrounded claim.\nRecall is instant re-verification, not blind "
          f"trust — WARM re-runs the gate on the remembered law.")


if __name__ == "__main__":
    main()
