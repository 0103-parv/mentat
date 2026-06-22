"""The creative cognition loop — propose creatively, verify, remember, sleep, get sharper.

This is the spine of a self-improving creative agent. It runs autonomous ROUNDS over any
verifier-backed domain, carrying VERIFIED memory forward and CONSOLIDATING it between rounds
(the brain's sleep), so each round starts from everything prior rounds proved. Then it MEASURES
whether that memory actually made it sharper (cold vs warm), and the verifier gates everything,
so creativity never decays into fabrication. The brain's modes + the novelty/elite pool drive
the creative proposals; nothing is believed until it passes the gate.

Domain-agnostic: hand it `(make_problem, make_proposer)`. It ships with a zero-dep demo domain
(formula synthesis) so it runs anywhere; point `make_problem` at the Max Cut heuristic
(`mentat.self_research`) for real code/algorithm discovery under the venv, or any future domain
(CAD-as-code, etc.). This is what makes Jarvis *generate-and-keep* instead of merely answer.

  python3 -m mentat cognition                 # autonomous creative loop on the demo domain
  python3 -m mentat cognition --rounds 6
"""
from __future__ import annotations

import argparse
import copy
import random
from dataclasses import dataclass

from .consolidate import consolidate
from .core import BrainConfig, Memory, solve


@dataclass
class RoundReport:
    round: int
    solved: bool
    best_score: float
    distinct_verified: int
    lessons: int
    principles: int


def run_loop(make_problem, make_proposer, *, rounds: int = 5, generations: int = 60,
             k: int = 32, brain: BrainConfig | None = None, seed0: int = 1,
             mem: Memory | None = None, log=None):
    """Run `rounds` of creative-propose -> verify -> remember -> consolidate, memory carried
    forward (and slept on) between rounds. Returns (memory, [RoundReport])."""
    brain = brain if brain is not None else BrainConfig()
    mem = mem if mem is not None else Memory()
    traj: list[RoundReport] = []
    for r in range(1, rounds + 1):
        res = solve(make_problem(), make_proposer(random.Random(seed0 + r)), mem,
                    generations=generations, k=k, log=lambda *_: None, brain=brain)
        rep = consolidate(mem)                       # sleep between rounds: strengthen/abstract/prune
        rr = RoundReport(r, res.solved, mem.best_score, res.distinct_verified,
                         len(mem.lessons), int(rep.get("new_principles", 0)))
        traj.append(rr)
        if log:
            log(f"  round {r}: best={mem.best_score:+.4f}  verified={res.distinct_verified}  "
                f"lessons={len(mem.lessons)}  principles={rr.principles}"
                + ("  SOLVED" if res.solved else ""))
    return mem, traj


def _trials(make_problem, make_proposer, mk_mem, seeds, generations, k, brain):
    scores, solved, gens = [], 0, []
    for s in seeds:
        res = solve(make_problem(), make_proposer(random.Random(100 + s)), mk_mem(),
                    generations=generations, k=k, log=lambda *_: None, brain=brain)
        scores.append(res.best_score)
        if res.solved:
            solved += 1
            gens.append(res.generations)
    med = sorted(gens)[len(gens) // 2] if gens else None
    return {"best": max(scores), "solved": solved, "med_gens": med}


def measure(make_problem, make_proposer, warm_mem, *, generations: int = 60, k: int = 32,
            seeds=(1, 2, 3), brain: BrainConfig | None = None) -> dict:
    """Cold (fresh memory) vs warm (the loop's accumulated + consolidated memory), same seeds.
    Proves the loop compounds: warm should solve more, faster, or score higher — never worse."""
    brain = brain if brain is not None else BrainConfig()
    cold = _trials(make_problem, make_proposer, Memory, seeds, generations, k, brain)
    warm = _trials(make_problem, make_proposer, lambda: copy.deepcopy(warm_mem),
                   seeds, generations, k, brain)
    return {"n": len(seeds), "cold": cold, "warm": warm}


def got_sharper(m: dict) -> bool:
    cold, warm = m["cold"], m["warm"]
    if warm["solved"] != cold["solved"]:
        return warm["solved"] > cold["solved"]
    if warm["med_gens"] is not None and cold["med_gens"] is not None \
            and warm["med_gens"] != cold["med_gens"]:
        return warm["med_gens"] < cold["med_gens"]          # same solve count, fewer gens = sharper
    return warm["best"] > cold["best"] + 1e-9


def _demo_domain():
    from .demo import RandomProposer, SymbolicRegression
    xs = [round(i * 0.2, 2) for i in range(-10, 11)]

    def target(x):                              # a cubic the offline creative search can crack
        return x ** 3 - x
    return (lambda: SymbolicRegression(target, xs, tol=0.10),
            lambda rng: RandomProposer(rng))


def main() -> int:
    ap = argparse.ArgumentParser(prog="mentat cognition")
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--generations", type=int, default=60)
    ap.add_argument("--k", type=int, default=32)
    args = ap.parse_args()

    make_problem, make_proposer = _demo_domain()
    print("CREATIVE COGNITION LOOP — propose creatively, verify, remember, sleep, get sharper")
    print("  domain: formula synthesis (zero-dep demo). The SAME loop runs on the Max Cut")
    print("  heuristic (code/algorithms) under the venv, and on any verifier-backed domain.\n")
    print(f"  {args.rounds} autonomous rounds, consolidating (sleeping) between each:")
    mem, traj = run_loop(make_problem, make_proposer, rounds=args.rounds,
                         generations=args.generations, k=args.k, log=print)

    print("\n  did the accumulated + consolidated memory make it SHARPER? (cold vs warm)")
    m = measure(make_problem, make_proposer, mem, generations=args.generations, k=args.k)
    cg = f"median {m['cold']['med_gens']} gens" if m["cold"]["med_gens"] else "none solved"
    wg = f"median {m['warm']['med_gens']} gens" if m["warm"]["med_gens"] else "none solved"
    print(f"    cold (fresh memory):  solved {m['cold']['solved']}/{m['n']}  {cg}   (must rediscover the law)")
    print(f"    warm (loop's memory): solved {m['warm']['solved']}/{m['n']}  {wg}   (recalls + RE-VERIFIES it)")
    print(f"    => {'SHARPER — the memory compounded' if got_sharper(m) else 'no measurable gain this run'}")
    print("\n  warm is not blind trust: it re-runs the verifier on the remembered law every time.")
    print("=> Creativity that improves itself, with a verifier between every idea and belief.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
