"""Self-research: point the Mentat kernel at the user's OWN project.

The reasoning core proposes a Max Cut local-search heuristic in alpha-evolver's
DSL; the verifier is alpha-evolver's REAL benchmark — `maxcut_lab.evaluate_program`
over a fixed graph suite — which is fast (~0.1s), offline, and deterministic. So
Mentat is trying to beat the heuristic in the user's own repo, scored by that
repo's own metric. Off-grammar programs are quarantined by the verifier; better
ones enter the verified library. This is the discovery loop turned on your work.

Run:  python3 -m mentat.improve     (needs a reasoning core; alpha-evolver + numpy)
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .core import Lesson, Memory, Mind, Problem, Verdict

ALPHA_EVOLVER = str(Path.home() / "alpha-evolver")
_STEPS, _RESTARTS, _TABU = (1, 2, 4, 8), (1, 2, 4), (0, 1, 3, 5)


def _load_lab():
    if ALPHA_EVOLVER not in sys.path:
        sys.path.insert(0, ALPHA_EVOLVER)
    import maxcut_lab as lab
    return lab


def _nearest(v, allowed):
    try:
        v = int(v)
    except (TypeError, ValueError):
        return allowed[0]
    return min(allowed, key=lambda a: abs(a - v))


def _normalize(p: dict) -> dict:
    """Coerce a proposed program to exactly the 5 keys + legal hyperparameters.
    Expressions are left as-is; the verifier's valid_program checks the grammar."""
    return {
        "init": p.get("init", ["rank", "degree"]),
        "move": p.get("move", "flip_gain"),
        "steps_per_node": _nearest(p.get("steps_per_node", 4), _STEPS),
        "restarts": _nearest(p.get("restarts", 2), _RESTARTS),
        "tabu_window": _nearest(p.get("tabu_window", 1), _TABU),
    }


# A few valid hand-written programs — offline fallback + something to evolve from.
BASELINE_VARIANTS = [
    {"init": ["rank", "degree"], "move": "flip_gain",
     "steps_per_node": 4, "restarts": 2, "tabu_window": 1},
    {"init": ["rank", "weighted_degree"],
     "move": ["add", "flip_gain", ["mul", "c_05", "triangle_score"]],
     "steps_per_node": 4, "restarts": 2, "tabu_window": 1},
    {"init": ["rank", "degree"],
     "move": ["sub", "flip_gain", ["mul", "c_05", "flip_age"]],
     "steps_per_node": 8, "restarts": 2, "tabu_window": 3},
    {"init": ["zscore", "weighted_degree"],
     "move": ["add", ["mul", "c_2", "flip_gain"], ["neg", "cross_weight"]],
     "steps_per_node": 4, "restarts": 4, "tabu_window": 1},
]


class MaxCutHeuristic(Problem):
    name = "maxcut-heuristic"

    def __init__(self, margin: float = 0.001):
        self.lab = _load_lab()
        self.graphs = self.lab.build_graph_suite("train")
        self.baseline = self.lab.baseline_program()
        self.baseline_fitness = float(self.lab.evaluate_program(self.baseline, self.graphs)["fitness"])
        self.target = self.baseline_fitness + margin
        self.statement = "design a Max Cut heuristic that beats alpha-evolver's baseline"

    def brief(self) -> str:
        return (
            "Design a Max Cut local-search heuristic that scores HIGHER than the baseline "
            f"on alpha-evolver's benchmark (baseline fitness = {self.baseline_fitness:.4f}).\n"
            "A program is JSON: {\"init\": <expr>, \"move\": <expr>, \"steps_per_node\": 1|2|4|8, "
            "\"restarts\": 1|2|4, \"tabu_window\": 0|1|3|5}.\n"
            "An <expr> is a field name (string), or [unary, expr], or [binary, expr, expr].\n"
            "  unary  = neg abs sign square rank zscore ;  binary = add sub mul safe_div min max\n"
            "  init may use ONLY: degree weighted_degree neighbor_degree triangle_score "
            "c_neg1 c_neg05 c_0 c_05 c_1 c_2\n"
            "  move may also use: flip_gain same_weight cross_weight side flip_age step_progress\n"
            "  (expr depth <= 5, total size <= 50). flip_gain is the local-search gain and is "
            "the strongest single signal; the baseline move is just \"flip_gain\".\n"
            "SCORING: fitness = mean_quality - 0.25*family_std - 0.002*complexity - 0.01*step_cost. "
            "So MORE steps/restarts and BIGGER expressions are PENALISED — raising steps_per_node "
            "usually LOWERS fitness. To win, raise cut quality while keeping steps_per_node LOW "
            "(2 or 4) and the move compact: a small, smart tie-break added to flip_gain (e.g. a "
            "tiny rank/zscore term, or mild tabu pressure) beats a big expensive expression.")

    def verify(self, candidate) -> Verdict:
        try:
            if not isinstance(candidate, dict):
                return Verdict(False, -1e9, "not a program object", suspicious=True)
            prog = _normalize(candidate)
            if not self.lab.valid_program(prog):
                return Verdict(False, -1e9, "off-grammar program (rejected by the verifier)",
                               suspicious=True)
            r = self.lab.evaluate_program(prog, self.graphs)
            fit, quality = float(r["fitness"]), float(r["mean_quality"])
            return Verdict(fit >= self.target, fit,
                           f"fitness={fit:.4f} mean_quality={quality:.4f} "
                           f"(baseline {self.baseline_fitness:.4f}) "
                           f"move={self.lab.expr_to_str(prog['move'])}")
        except Exception as e:
            return Verdict(False, -1e9, f"rejected: {type(e).__name__}: {e}", suspicious=True)

    def solved(self, v: Verdict) -> bool:
        return v.passed

    def distill(self, best_candidate, best_verdict) -> list[Lesson]:
        if best_candidate is None or best_verdict is None or not best_verdict.detail:
            return []
        return [Lesson(
            when="designing a max cut move heuristic to beat the baseline fitness",
            do="reuse the verified move heuristic reaching this fitness",
            avoid="off-grammar programs the verifier rejects",
            evidence=best_verdict.detail)]


@dataclass
class HeuristicProposer:
    """Reasoning core proposing heuristics for the user's own benchmark. Every
    program is verified by alpha-evolver's eval; shortfall is filled with baseline
    variants so the loop never starves (and runs offline in tests)."""
    core: object
    fallback: list = field(default_factory=lambda: list(BASELINE_VARIANTS))
    last: list = field(default_factory=list)
    note: str = ""

    _SYSTEM = (
        "You are the reasoning core of a self-improvement engine working on the user's own "
        "research project (alpha-evolver, a Max Cut heuristic search). You propose heuristic "
        "programs; an independent verifier runs each on a fixed graph benchmark and keeps only "
        "programs that BEAT the baseline fitness. Reply with ONLY a JSON array of program "
        "objects in the exact schema described — no prose, no code fences.")
    _MODE = {
        "focus": "Refine the best-known program with small changes to push fitness higher.",
        "dream": "Try a structurally different move expression.",
        "recover": "Fall back toward simple, certainly-valid programs.",
    }

    def propose(self, problem, memory: Memory, mind: Mind, k: int):
        best = memory.elites[0][1] if memory.elites else problem.baseline
        ctx = memory.context(k=5) or "(no lessons yet)"
        user = (f"{problem.brief()}\n\nLessons so far:\n{ctx}\n\n"
                f"Best verified program so far (improve on it):\n{json.dumps(best)}\n\n"
                f"Mode: {mind.mode} — {self._MODE[mind.mode]}\n"
                f"Propose {k} different program objects as a JSON array. Vary the `move` most.")
        out, self.last, self.note = [], [], ""
        try:
            text = self.core.complete_text(self._SYSTEM, user, max_tokens=3000)
            m = re.search(r"\[.*\]", text, re.S)
            arr = json.loads(m.group(0)) if m else []
            for p in arr:
                if isinstance(p, dict):
                    prog = _normalize(p)
                    out.append(prog)
                    try:
                        self.last.append(problem.lab.expr_to_str(prog["move"])[:48])
                    except Exception:
                        self.last.append(str(prog.get("move"))[:48])
        except Exception as e:
            self.note = f"core error ({type(e).__name__}); using baseline variants"
        i = 0
        while len(out) < k and self.fallback:
            out.append(self.fallback[i % len(self.fallback)])
            i += 1
        return out
