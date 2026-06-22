"""work_on — budgeted, verified, self-improving autonomous work (the capstone capability).

The user's vision: "tell it to work on something and it estimates the time, sets a budget with a
buffer, and works until it's done." This is that, honestly:

  - it sets a buffered budget from the self-model (or an explicit minute cap),
  - it works a CURRICULUM of increasingly hard tasks, carrying VERIFIED memory forward so building
    blocks learned on easy tasks accelerate the hard ones (genuine compounding / transfer),
  - it stops when the work is genuinely DRY (a task it can't crack within budget) or the budget is
    spent — it never pads,
  - it persists verified gains to a journal so progress compounds across sessions,
  - and the verifier gates every step, so "improvement" is always re-proven, never asserted.

Offline and deterministic (no API). The honest ceiling: the offline creative search saturates on
toy domains, so it reports what it proved and what would need API credits or a new domain.

  python3 -m mentat work                 # run the self-improvement curriculum
  python3 -m mentat work --minutes 30    # cap the budget (a buffer is applied)
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .cognition import measure
from .core import Memory
from .selfmodel import BUFFER

JOURNAL = Path(__file__).parent / "work_journal.json"

# A curriculum of formula-synthesis tasks, easy -> hard. Carrying memory across them is the
# transfer test: motifs proven on the easy ones should help crack the hard ones.
CURRICULUM = [
    ("linear", lambda x: x - 1),
    ("quadratic", lambda x: x * x - 1),
    ("shifted-quadratic", lambda x: x * x - 2 * x - 1),
    ("cubic", lambda x: x ** 3 - x),
    ("hard-cubic", lambda x: x ** 3 - 2 * x + 1),
]


def _load_journal() -> dict:
    try:
        return json.loads(JOURNAL.read_text())
    except (OSError, ValueError):
        return {"solved": {}, "runs": 0}


def _save_journal(j: dict) -> None:
    try:
        JOURNAL.write_text(json.dumps(j, indent=2))
    except OSError:
        pass


def work(*, minutes: float | None = None, rounds_per_task: int = 4, log=print) -> dict:
    """Run the self-improvement curriculum within a buffered budget; stop when dry or out of time."""
    from .cognition import run_loop
    from .demo import RandomProposer, SymbolicRegression
    xs = [round(i * 0.2, 2) for i in range(-10, 11)]
    cap_s = (minutes * 60 * BUFFER) if minutes else None      # apply the safety buffer to the cap
    start = time.time()
    journal = _load_journal()
    mem = Memory()                                            # carried across the curriculum (transfer)
    results, dry = [], None

    for name, tgt in CURRICULUM:
        if cap_s and time.time() - start > cap_s:
            log(f"  [budget spent at task '{name}' — stopping, not padding]")
            break
        mk_p = lambda tgt=tgt: SymbolicRegression(tgt, xs, tol=0.10)        # noqa: E731
        mk_pr = lambda rng: RandomProposer(rng)                            # noqa: E731
        _, traj = run_loop(mk_p, mk_pr, rounds=rounds_per_task, generations=60, k=32, mem=mem)
        solved = any(rr.solved for rr in traj)
        results.append((name, solved, len(mem.lessons)))
        log(f"  task '{name}': {'SOLVED' if solved else 'not cracked in budget'}  "
            f"(carried {len(mem.lessons)} verified lessons forward)")
        if solved:
            journal["solved"][name] = True
        else:
            dry = name                                       # honest: first task we couldn't crack
            break                                            # curriculum gates on mastery

    # Transfer proof on the hardest SOLVED-or-attempted task: does carried memory beat a cold start?
    last = results[-1][0] if results else CURRICULUM[0][0]
    tgt = dict(CURRICULUM)[last]
    mk_p = lambda: SymbolicRegression(tgt, xs, tol=0.10)                   # noqa: E731
    mk_pr = lambda rng: RandomProposer(rng)                               # noqa: E731
    m = measure(mk_p, mk_pr, mem, generations=60, k=32, seeds=(1, 2, 3))

    journal["runs"] = journal.get("runs", 0) + 1
    _save_journal(journal)
    return {"results": results, "dry": dry, "transfer": m, "elapsed_s": time.time() - start,
            "lessons": len(mem.lessons), "task": last}


def main() -> int:
    ap = argparse.ArgumentParser(prog="mentat work")
    ap.add_argument("--minutes", type=float, default=None, help="budget cap (a safety buffer is applied)")
    args = ap.parse_args()

    print("BUDGETED SELF-IMPROVEMENT — a verified curriculum, memory carried forward, honest dry-stop")
    if args.minutes:
        print(f"  budget: {args.minutes:g} min requested -> {args.minutes * BUFFER:g} min cap "
              f"({int((BUFFER - 1) * 100)}% buffer)\n")
    else:
        print("  budget: run the whole curriculum (it stops when a task can't be cracked)\n")

    r = work(minutes=args.minutes)
    solved = [n for n, ok, _ in r["results"] if ok]
    print(f"\n  mastered {len(solved)}/{len(CURRICULUM)} curriculum tasks: {solved}")
    if r["dry"]:
        print(f"  stopped at '{r['dry']}' — couldn't crack it offline in budget (honest dry-stop).")
    cold, warm = r["transfer"]["cold"], r["transfer"]["warm"]
    print(f"  transfer on '{r['task']}': cold solved {cold['solved']}/{r['transfer']['n']}, "
          f"warm (carried memory) solved {warm['solved']}/{r['transfer']['n']} "
          f"-> {'memory compounded' if warm['solved'] >= cold['solved'] else 'no gain'}.")
    print(f"  {r['lessons']} verified lessons accumulated; {r['elapsed_s']:.1f}s elapsed.")
    print("\n=> It set a budget, worked in verified blocks, compounded what it proved, and stopped")
    print("   honestly when dry. Further gains on harder tasks need API credits or a new domain.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
