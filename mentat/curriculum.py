"""Topic mastery — learn (almost) everything about ONE domain, the honest way.

The vision: point Mentat at a domain (here, the stock market), and have it study it
facet by facet. For EACH facet it searches hypotheses, BACKTESTS every one (the
verifier), keeps only what survives out-of-sample after costs and deflation,
remembers those as grounded lessons, records the honest negatives, and moves on to
the next facet. What accumulates is a *verified* understanding of the domain — every
claim backed by a backtest, nothing asserted.

This is the kernel's propose -> verify -> remember -> reflect loop, sequenced into a
curriculum, with one persistent memory carried across facets (so it never re-learns
what it already proved, and never trusts what it couldn't).

Run:  python3 -m mentat.curriculum
      python3 -m mentat.curriculum --data data/fred_SP500.csv   (study a real market)
"""
from __future__ import annotations

import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .core import BrainConfig, Lesson, Memory, solve
from .trade_lab import (
    CONSTANTS,
    AlphaProblem,
    expr_to_str,
    load_price_csv,
    synthetic_universe,
    valid_alpha,
)

# Each facet of the market = a question + the features a hypothesis may use to answer
# it. The agent searches alphas built ONLY from that facet's features, so a "finding"
# is attributable to that facet.
FACETS = [
    ("momentum", "Do recent returns predict future returns?", ["mom5", "mom10", "mom20", "accel"]),
    ("mean_reversion", "Do recent moves reverse?", ["ret1", "accel", "price_ma_gap"]),
    ("volatility", "Does volatility predict returns?", ["vol10", "vol20"]),
    ("volume", "Does volume carry a signal?", ["volume_z"]),
    ("trend", "Does distance from trend predict returns?", ["price_ma_gap", "mom20"]),
    ("range", "Does intrabar range predict returns?", ["hl_range", "vol20"]),
]
_UNARY = ["neg", "sign", "zscore", "tanh", "abs"]
_BINARY = ["add", "sub", "mul", "safe_div"]


def _rand_expr(rng: random.Random, features, depth: int = 0):
    """A small random alpha built ONLY from this facet's features (+ constants)."""
    if depth >= 2 or (depth > 0 and rng.random() < 0.5):
        return (rng.choice(features) if rng.random() < 0.75
                else rng.choice(list(CONSTANTS)))
    if rng.random() < 0.45:
        return [rng.choice(_UNARY), _rand_expr(rng, features, depth + 1)]
    return [rng.choice(_BINARY), _rand_expr(rng, features, depth + 1),
            _rand_expr(rng, features, depth + 1)]


@dataclass
class FacetProposer:
    """Searches within ONE facet: random in-family alphas, plus mutations of what's
    already verified (the elite pool). Stays inside the facet's feature set."""
    rng: random.Random
    features: list

    def propose(self, problem, memory: Memory, mind, k: int):
        ex = mind.explore_rate()
        pool = [c for _, c in memory.elites]
        out = []
        for _ in range(k):
            if not pool or self.rng.random() < max(ex, 0.4):
                out.append(_rand_expr(self.rng, self.features))
            else:                                   # graft a fresh in-family subexpr onto a parent
                a = self.rng.choice(pool)
                out.append([self.rng.choice(_BINARY), a, _rand_expr(self.rng, self.features)])
        return [c for c in out if valid_alpha(c)] or [self.features[0]]


@dataclass
class KnowledgeBase:
    """The accumulated, verified understanding — one entry per facet studied."""
    domain: str
    facets: dict = field(default_factory=dict)

    def record(self, facet, *, tested, best_alpha, best_score, target, verified):
        self.facets[facet] = {
            "tested": tested,
            "best_alpha": best_alpha,
            "best_deflated_oos_sharpe": round(best_score, 3),
            "verified": verified,        # cleared the OOS+cost+deflation gate?
            "bar": target,
        }

    def save(self, path):
        Path(path).write_text(json.dumps({"domain": self.domain, "facets": self.facets},
                                         indent=2))

    def report(self) -> str:
        verified = [f for f, d in self.facets.items() if d["verified"]]
        lines = [f"WHAT MENTAT LEARNED ABOUT: {self.domain}", ""]
        for facet, d in self.facets.items():
            tag = "VERIFIED EDGE" if d["verified"] else "no robust edge (honest negative)"
            lines.append(f"  {facet:15} {tag}")
            lines.append(f"      best: {d['best_alpha']}  "
                         f"(deflated OOS Sharpe {d['best_deflated_oos_sharpe']:+.2f}, "
                         f"bar {d['bar']:.2f}, ~{d['tested']} hypotheses searched)")
        lines.append("")
        lines.append(f"=> Studied {len(self.facets)} facets; {len(verified)} hold up "
                     "out-of-sample after costs + deflation: "
                     f"{', '.join(verified) or 'none'}.")
        lines.append("   Every conclusion — positive AND negative — is backed by a "
                     "walk-forward, cost-aware, deflated backtest. Nothing asserted.")
        return "\n".join(lines)


def study(domain: str, bars, *, facets=None, gens: int = 12, k: int = 16, seed: int = 7,
          mem_path: Path | None = None) -> tuple[KnowledgeBase, Memory]:
    facets = facets or FACETS
    kb = KnowledgeBase(domain=domain)
    knowledge = Memory()                    # accumulates verified LESSONS across facets
    problem = AlphaProblem(bars=bars, n_trials=len(facets) * gens * k)
    for facet, question, features in facets:
        # FRESH search memory per facet so its elite pool can't leak another facet's
        # signal in — every finding is attributable to THIS facet's own features.
        facet_mem = Memory()
        proposer = FacetProposer(random.Random(seed), features)
        result = solve(problem, proposer, facet_mem, generations=gens, k=k,
                       log=lambda *_: None, brain=BrainConfig())
        verified = result.best_score >= problem.target
        best_alpha = (expr_to_str(facet_mem.best_candidate)
                      if facet_mem.best_candidate is not None else "(none)")
        # Remember it (grounded lesson) only if it truly cleared the gate — and move on.
        if verified and facet_mem.best_candidate is not None:
            knowledge.learn(Lesson(
                when=f"trading the {facet} facet of {domain}",
                do=f"use the verified alpha {best_alpha}",
                avoid="alphas strong in-sample but failing the deflated OOS gate",
                evidence=result.verdict.detail if result.verdict else ""))
        kb.record(facet, tested=gens * k, best_alpha=best_alpha,
                  best_score=result.best_score, target=problem.target, verified=verified)
    if mem_path:
        kb.save(mem_path)
    return kb, knowledge


def main() -> int:
    paths = [a.split("=", 1)[1] if a.startswith("--data=") else None for a in sys.argv]
    data = next((p for p in paths if p), None)
    if "--data" in sys.argv:
        i = sys.argv.index("--data")
        if i + 1 < len(sys.argv):
            data = sys.argv[i + 1]
    if data:
        bars = load_price_csv(data)
        domain = f"the market: {Path(data).stem}"
    else:
        bars = synthetic_universe()
        domain = "the stock market (synthetic testbed)"

    print(f"STUDYING   {domain}")
    print(f"METHOD     {len(FACETS)} facets; each searched, every hypothesis backtested "
          "OOS + cost + deflation\n")
    kb, knowledge = study(domain, bars,
                          mem_path=Path(__file__).parent / "market_knowledge.json")
    print(kb.report())
    if knowledge.lessons:
        print(f"\n   {len(knowledge.lessons)} verified lesson(s) now in durable memory "
              "(carried to the next study).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
