"""Creative synthesizer — structured IDEA generation, not random search.

This is the heart of "creativity in an AI": the system IMAGINES boldly and BELIEVES
cautiously. It synthesizes novel hypotheses by composing creative OPERATORS over its
own VERIFIED knowledge base (motifs, elite ideas, the illumination archive), the
brain's modes choose which operators fire, novelty + productive surprise bias what's
kept, and the verifier gates everything — so it is creative without ever becoming a
confident bullshitter.

Boden's three forms of creativity, made executable as operators over the alpha DSL:
  - COMBINATORIAL    `blend`     : fuse two verified ideas into a new one
  - EXPLORATORY      `reshape` / `specialize` : move within a conceptual space
  - TRANSFORMATIONAL `invert` / `transfer`    : flip a known edge, or carry it by
                                                 analogy onto different features

Two imaginers share the interface:
  - CreativeProposer : offline, deterministic operators over the knowledge base. Runs
    and tests anywhere (no API). It CREATES FROM what it has already verified, so the
    more it proves, the richer its raw material — creativity compounds.
  - LLMImaginer : the reasoning core synthesizes a novel alpha CONCEPT *with a rationale*
    grounded in the verified motifs/lessons, then renders it to the DSL. Falls back to
    CreativeProposer so the loop never starves.

Run:  python3 -m mentat.imagine        (offline creative discovery on the synthetic market)
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .core import BrainConfig, Memory, Mind, Problem, fragments, novelty, solve
from .trade_lab import (
    BASELINE_ALPHAS,
    CONSTANTS,
    FEATURES,
    AlphaProblem,
    _extract_alphas,
    expr_to_str,
    normalize_alpha,
    valid_alpha,
)

_UNARY = ["neg", "abs", "sign", "tanh", "zscore"]
_BINARY = ["add", "sub", "mul", "safe_div", "min", "max"]
# Seeds to create from before anything is verified yet: each feature as a bare idea.
SEED_IDEAS = [f for f in FEATURES] + list(BASELINE_ALPHAS)


# --------------------------------------------------------------------------- #
# creative operators (Boden's three forms)                                    #
# --------------------------------------------------------------------------- #
def _map_features(expr, fn):
    if isinstance(expr, str):
        return fn(expr) if expr in FEATURES else expr
    if isinstance(expr, (list, tuple)) and expr:
        return [expr[0]] + [_map_features(a, fn) for a in expr[1:]]
    return expr


def blend(rng, a, b):
    """COMBINATORIAL: fuse two ideas (the engine of most human creativity)."""
    return [rng.choice(["add", "sub", "safe_div", "mul", "min", "max"]), a, b]


def invert(rng, a):
    """TRANSFORMATIONAL: what if the opposite? (flip a known edge's sign)."""
    return ["neg", a]


def reshape(rng, a):
    """EXPLORATORY: change the shape of an idea (squash, rank, sign, ...)."""
    return [rng.choice(_UNARY), a]


def specialize(rng, a):
    """EXPLORATORY: tune an idea by scaling it against a constant."""
    return [rng.choice(["mul", "safe_div"]), a, rng.choice(list(CONSTANTS))]


def transfer(rng, a):
    """TRANSFORMATIONAL by analogy: carry an idea's STRUCTURE onto different features
    (the move behind 'momentum works in stocks — does it work in volatility?')."""
    return _map_features(a, lambda f: rng.choice([x for x in FEATURES if x != f]))


_OPS_BY_MODE = {
    "dream": [blend, invert, transfer, reshape],     # widen: bold, transformational
    "focus": [specialize, reshape, blend],           # refine within a promising space
    "recover": [specialize, invert],                 # conservative recombination
}


# --------------------------------------------------------------------------- #
# the offline creative proposer                                               #
# --------------------------------------------------------------------------- #
@dataclass
class CreativeProposer:
    """Synthesizes novel hypotheses by composing creative operators over the VERIFIED
    knowledge base. Not random mutation — every candidate is a deliberate creative move
    (blend / invert / transfer / reshape / specialize) on something that already exists.

    `risk` is the THOUGHT-RISK DIAL (0 = conservative, 1 = bold). High risk forces the
    transformational operators and COMPOSES two of them per idea (wilder synthesis);
    low risk stays with safe recombination; mid follows the brain's current mode. The
    verifier gates everything regardless — so it can think recklessly and still never
    believe a bad idea."""
    rng: random.Random
    risk: float = 0.5
    last: list = field(default_factory=list)
    note: str = ""

    def _substrate(self, memory: Memory) -> list:
        # Create FROM what's been verified (elites + illumination archive); seed ideas
        # until there is something to build on.
        pool = [c for _, c in memory.elites] + [c for _, c in memory.archive.values()]
        return pool or list(SEED_IDEAS)

    def _ops(self, mind: Mind) -> list:
        if self.risk >= 0.66:
            return _OPS_BY_MODE["dream"]          # bold: transformational/combinatorial
        if self.risk <= 0.33:
            return _OPS_BY_MODE["recover"]         # safe recombination
        return _OPS_BY_MODE.get(mind.mode, _OPS_BY_MODE["focus"])

    def _apply(self, op, pool):
        if op is blend:
            return blend(self.rng, self.rng.choice(pool), self.rng.choice(pool))
        return op(self.rng, self.rng.choice(pool))

    def propose(self, problem, memory: Memory, mind: Mind, k: int):
        ops = self._ops(mind)
        pool = self._substrate(memory)
        out = []
        for _ in range(k):
            cand = self._apply(self.rng.choice(ops), pool)
            # Riskier thinking COMPOSES operators — a creative leap, not a single step.
            if self.risk >= 0.66 and self.rng.random() < self.risk:
                cand = self._apply(self.rng.choice(ops), pool + [cand])
            if not valid_alpha(cand):              # creativity is bounded by the grammar
                cand = self.rng.choice(pool)
            out.append(cand)
        self.last = [expr_to_str(c)[:44] for c in out[:3]]
        self.note = ""
        return out


# --------------------------------------------------------------------------- #
# the LLM imaginer — synthesize a CONCEPT with a rationale, then render it      #
# --------------------------------------------------------------------------- #
@dataclass
class LLMImaginer:
    core: object
    fallback: CreativeProposer
    last: list = field(default_factory=list)
    note: str = ""

    _SYSTEM = (
        "You are the CREATIVE core of a discovery engine. You INVENT novel trading alphas "
        "by blending, inverting, or transferring (by analogy) the VERIFIED ideas you are "
        "given — bold, original combinations, not the obvious ones. An independent verifier "
        "backtests each out-of-sample, so imagine freely; only what survives is kept. Reply "
        "with ONLY a JSON array of alpha expressions in the DSL described — no prose.")
    _MODE = {
        "dream": "Be bold: invert an edge, or transfer it by analogy to unrelated features.",
        "focus": "Refine the most promising verified idea with a small creative twist.",
        "recover": "Stay close to what verified; make safe recombinations.",
    }

    def propose(self, problem, memory: Memory, mind: Mind, k: int):
        import json
        verified = [expr_to_str(c) for _, c in memory.elites[:6]] or ["(none yet)"]
        user = (f"{problem.brief()}\n\nVERIFIED ideas to create from:\n{verified}\n\n"
                f"Mode: {mind.mode} — {self._MODE.get(mind.mode, '')}\n"
                f"Invent {k} NOVEL alpha expressions as a JSON array.")
        out, self.last, self.note = [], [], ""
        try:
            text = self.core.complete_text(self._SYSTEM, user, max_tokens=2000)
            for p in _extract_alphas(text):
                alpha = normalize_alpha(p)
                if valid_alpha(alpha):
                    out.append(alpha)
                    self.last.append(expr_to_str(alpha)[:44])
        except Exception as e:
            self.note = f"core error ({type(e).__name__}); using the offline creative proposer"
        if len(out) < k:                          # top up so the loop never starves
            out += self.fallback.propose(problem, memory, mind, k - len(out))
        return out


# --------------------------------------------------------------------------- #
# B2: creativity ablation — is creative synthesis measurably more creative?    #
# --------------------------------------------------------------------------- #
class _Broken:
    def complete_text(self, *a, **k):
        raise RuntimeError("no core")


def creativity_ablation(seeds=range(1, 6), gens: int = 12, k: int = 16) -> list:
    """Random/baseline search vs creative synthesis at rising risk, averaged over seeds.
    Creativity metrics: distinct verified ideas, pool diversity, signal-family coverage.
    Returns rows (label, distinct, diversity, coverage, best)."""
    import statistics

    from .trade_lab import AlphaProblem, AlphaProposer, synthetic_universe
    configs = [("random/baseline", None), ("creative risk=0.2", 0.2),
               ("creative risk=0.5", 0.5), ("creative risk=0.9", 0.9)]
    rows = []
    for label, risk in configs:
        dv, div, cov, best = [], [], [], []
        for s in seeds:
            prob = AlphaProblem(bars=synthetic_universe(), n_trials=gens * k)
            prop = (AlphaProposer(core=_Broken()) if risk is None
                    else CreativeProposer(random.Random(s), risk=risk))
            r = solve(prob, prop, Memory(), generations=gens, k=k, log=lambda *_: None,
                      brain=BrainConfig())
            dv.append(r.distinct_verified)
            div.append(r.diversity)
            cov.append(r.coverage)
            best.append(r.best_score)
        rows.append((label, statistics.mean(dv), statistics.mean(div),
                     statistics.mean(cov), statistics.mean(best)))
    return rows


def main() -> int:
    print("CREATIVITY ABLATION — random search vs creative synthesis at rising risk")
    print("(synthetic market; everything gated by the deflated-OOS verifier)\n")
    rows = creativity_ablation()
    print(f"  {'config':18} {'distinct':>8} {'diversity':>10} {'families':>9} {'best OOS':>9}")
    for label, dv, div, cov, best in rows:
        print(f"  {label:18} {dv:>8.1f} {div:>10.2f} {cov:>9.1f} {best:>+9.2f}")
    base = rows[0]
    bold = max(rows[1:], key=lambda r: r[3])               # most family-coverage among creative
    print(f"\n=> Honest read: creative synthesis EXPLORES more of the idea space — signal-family "
          f"coverage rises {base[3]:.1f} -> {bold[3]:.1f} as risk climbs — but trades peak score "
          f"for breadth\n   (best OOS {base[4]:+.2f} -> {bold[4]:+.2f}). Risk is an explore/exploit "
          "DIAL: turn it up to invent widely, down to sharpen.")
    print("   Every kept idea still passed the verifier — imagine boldly, believe only what's proven.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
