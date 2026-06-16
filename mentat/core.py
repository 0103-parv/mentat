"""Mentat — the cognitive kernel.

A domain-agnostic  propose -> verify -> remember -> reflect  loop. This is the
fusion of two engines already on this laptop:

  - swechats       the "memory organ". Lessons are learned from real outcomes
                   and firewalled against fabrication. A lesson is
                   decision-card-shaped: when / do / avoid / evidence, and may
                   not enter memory unless it is *grounded* in real evidence.
  - alpha-evolver  the "thinking organ". Brain-inspired search with cognitive
                   modes (focus / dream / recover) and an inverted-U
                   "productive surprise" signal that drives exploration while
                   quarantining results too extreme to trust.

The one rule that makes this a thinking machine and not a confident bullshitter:
the kernel never lets a candidate become memory until a domain Verifier returns
a Verdict on it. Verification is the gate. Everything downstream — opinions,
discoveries, a library of what works — is built on top of verified claims only.

Swap the proposer for an LLM reasoning core and the Problem for a domain with a
real verifier (a proof checker, a test suite, a backtest) and this same loop is
doing real work.
"""
from __future__ import annotations

import json
import math
import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol


# --------------------------------------------------------------------------- #
# the honesty gate                                                            #
# --------------------------------------------------------------------------- #
@dataclass
class Verdict:
    """A domain verifier's judgement of a single candidate."""
    passed: bool             # did it satisfy the problem?
    score: float             # higher is better; comparable across candidates
    detail: str = ""         # human-readable evidence, e.g. "RMSE=0.013 expr=..."
    suspicious: bool = False  # degenerate / non-finite / too-good-to-trust


class Problem(ABC):
    """A problem the kernel can think about. The verifier *is* the problem."""

    name: str = "problem"
    statement: str = ""

    @abstractmethod
    def verify(self, candidate: Any) -> Verdict:
        """Check a candidate. Must be cheap, deterministic, and honest."""

    def solved(self, v: Verdict) -> bool:
        return v.passed

    def brief(self) -> str:
        """What a proposer is allowed to see about the problem — never the answer."""
        return self.statement

    def distill(self, best_candidate: Any, best_verdict: Verdict) -> list["Lesson"]:
        """Optionally turn the current best into grounded lesson(s). Default: none."""
        return []


# --------------------------------------------------------------------------- #
# cognitive modes + productive surprise   (from alpha-evolver)                #
# --------------------------------------------------------------------------- #
def productive_surprise(error: float, scale: float) -> float:
    """Inverted-U curiosity: peaks at moderate surprise, distrusts the extremes.

    Surprising-but-learnable results earn the most signal; results that are
    wildly off the expectation earn almost none (they are usually bugs)."""
    if not math.isfinite(error):
        return 0.0
    ratio = abs(error) / max(scale, 1e-9)
    return float(ratio * math.exp(1.0 - ratio))  # maximised at ratio == 1


@dataclass
class Mind:
    """Tracks search health and chooses the next exploration mode."""
    mode: str = "focus"
    stall: int = 0
    surprise_scale: float = 1.0

    def reflect(self, improved: bool, quarantine_rate: float) -> str:
        self.stall = 0 if improved else self.stall + 1
        if quarantine_rate > 0.6:
            self.mode = "recover"   # too much junk coming back -> tighten up
        elif self.stall >= 3:
            self.mode = "dream"     # stuck -> widen the search
        else:
            self.mode = "focus"     # making progress -> exploit it
        return self.mode

    def explore_rate(self) -> float:
        return {"focus": 0.25, "dream": 0.50, "recover": 0.15}[self.mode]


# --------------------------------------------------------------------------- #
# grounded memory   (from swechats)                                           #
# --------------------------------------------------------------------------- #
_STOP = {"the", "a", "an", "of", "to", "and", "or", "is", "in", "on", "for",
         "with", "that", "this", "it", "as", "be", "by", "use", "using", "when",
         "do", "avoid", "via", "are", "was", "from", "into", "than", "then"}


def keywords(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-zA-Z_][a-zA-Z0-9_]+", text.lower())
            if len(w) > 2 and w not in _STOP}


@dataclass
class Lesson:
    """A decision-card-shaped, grounded unit of memory."""
    when: str                 # the recurring situation
    do: str                   # the canonical move
    avoid: str = ""           # the anti-pattern
    evidence: str = ""        # a real value/quote from a *verified* candidate
    strength: float = 1.0
    corroboration: int = 1
    status: str = "trusted"   # or "quarantined"

    def grounded(self, min_overlap: int = 2) -> bool:
        """A lesson may only enter memory if its claim shares real vocabulary
        with the evidence it cites. This is the anti-fabrication firewall."""
        claim = f"{self.when} {self.do} {self.avoid}"
        return len(keywords(claim) & keywords(self.evidence)) >= min_overlap


@dataclass
class Memory:
    lessons: list[Lesson] = field(default_factory=list)
    motifs: dict[str, float] = field(default_factory=dict)  # fragment -> best score
    best_candidate: Any = None
    best_score: float = -math.inf
    cap: int = 200
    elites: list = field(default_factory=list)   # [score, candidate], desc by score
    elite_cap: int = 12

    # -- persistence --------------------------------------------------------
    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps({
            "lessons": [asdict(le) for le in self.lessons],
            "motifs": self.motifs,
            "best_candidate": self.best_candidate,
            "best_score": self.best_score if math.isfinite(self.best_score) else None,
            "elites": self.elites,
        }, indent=2))

    @classmethod
    def load(cls, path: str | Path) -> "Memory":
        p = Path(path)
        if not p.exists():
            return cls()
        d = json.loads(p.read_text())
        bs = d.get("best_score")
        return cls(
            lessons=[Lesson(**le) for le in d.get("lessons", [])],
            motifs=d.get("motifs", {}),
            best_candidate=d.get("best_candidate"),
            best_score=bs if bs is not None else -math.inf,
            elites=d.get("elites", []),
        )

    def consider_elite(self, score: float, candidate: Any) -> None:
        """Keep a small pool of the best-verified candidates for recombination."""
        self.elites.append([score, candidate])
        self.elites.sort(key=lambda sc: sc[0], reverse=True)
        del self.elites[self.elite_cap:]

    # -- write path (firewalled: only grounded lessons enter) ---------------
    def learn(self, lesson: Lesson) -> bool:
        if not lesson.grounded():
            return False
        for ex in self.lessons:
            if ex.when == lesson.when and ex.do == lesson.do:
                ex.corroboration += 1
                ex.strength = min(4.0, ex.strength + 0.5)  # corroboration strengthens
                return False
        self.lessons.append(lesson)
        return True

    def reinforce_motif(self, fragment: str, score: float) -> None:
        self.motifs[fragment] = max(self.motifs.get(fragment, -math.inf), score)

    def decay(self, factor: float = 0.98) -> None:
        for le in self.lessons:
            le.strength *= factor
        self.lessons = [le for le in self.lessons if le.strength > 0.15]
        if len(self.lessons) > self.cap:
            self.lessons.sort(key=lambda le: le.strength, reverse=True)
            del self.lessons[self.cap:]

    def context(self, k: int = 8) -> str:
        top = sorted(self.lessons, key=lambda le: le.strength, reverse=True)[:k]
        return "\n".join(
            f"- WHEN {le.when}: DO {le.do}" + (f"; AVOID {le.avoid}" if le.avoid else "")
            for le in top
        )


# --------------------------------------------------------------------------- #
# the loop                                                                    #
# --------------------------------------------------------------------------- #
class Proposer(Protocol):
    def propose(self, problem: Problem, memory: Memory, mind: Mind, k: int) -> list[Any]:
        ...


@dataclass
class Result:
    solved: bool
    best_candidate: Any
    best_score: float
    verdict: Verdict
    generations: int
    history: list[dict]


def solve(problem: Problem, proposer: Proposer, memory: Memory,
          *, generations: int = 40, k: int = 24, log=print) -> Result:
    """Run propose -> verify -> remember -> reflect until solved or out of budget.

    `memory` is mutated in place and carries state across runs when persisted —
    a warm (loaded) memory is the difference between thinking from scratch and
    thinking with everything you learned last time still in hand.
    """
    mind = Mind()
    best_cand = memory.best_candidate
    best_score = memory.best_score
    best_v: Verdict | None = None
    # Recall + RE-VERIFY: a remembered best is re-run through the gate, never
    # trusted blindly. This is what lets a warm start recognise it already holds
    # a solution (and what catches a remembered claim that no longer verifies).
    if best_cand is not None:
        best_v = problem.verify(best_cand)
        best_score = best_v.score
    history: list[dict] = []

    for gen in range(1, generations + 1):
        candidates = proposer.propose(problem, memory, mind, k)
        improved = False
        quarantined = 0
        surprises: list[float] = []

        for cand in candidates:
            v = problem.verify(cand)             # <- the gate: nothing skips it
            if v.suspicious:
                quarantined += 1
                continue
            surprises.append(productive_surprise(best_score - v.score, mind.surprise_scale))
            memory.consider_elite(v.score, cand)
            if v.score > best_score:
                best_score, best_cand, best_v = v.score, cand, v
                improved = True

        qrate = quarantined / max(1, len(candidates))
        mind.surprise_scale = 0.8 * mind.surprise_scale + 0.2 * max(1e-6, abs(best_score))
        mode = mind.reflect(improved, qrate)

        if best_v is not None:
            for lesson in problem.distill(best_cand, best_v):
                memory.learn(lesson)
        memory.best_candidate, memory.best_score = best_cand, best_score
        memory.decay()

        mean_surprise = sum(surprises) / len(surprises) if surprises else 0.0
        history.append({"gen": gen, "mode": mode, "best": best_score,
                        "q": round(qrate, 2), "surprise": round(mean_surprise, 3)})
        log(f"gen {gen:>3} | {mode:7} | best={best_score:+.4f} "
            f"| quarantine={qrate:.2f} | surprise={mean_surprise:.2f}")

        if best_v is not None and problem.solved(best_v):
            log(f"  -> solved at gen {gen}: {best_v.detail}")
            return Result(True, best_cand, best_score, best_v, gen, history)

    solved = best_v is not None and problem.solved(best_v)
    return Result(solved, best_cand, best_score,
                  best_v or Verdict(False, best_score, "no candidate verified"),
                  generations, history)
