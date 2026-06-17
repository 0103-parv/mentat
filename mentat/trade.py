"""Run the Mentat kernel on anti-overfit alpha discovery (VISION.md's flagship).

The reasoning core proposes trading alphas; the verifier is a brutal walk-forward
backtest — out-of-sample across regimes, after transaction costs, with a deflated-
Sharpe / multiple-testing haircut. Only alphas that genuinely generalise survive.

Run:  python3 -m mentat.trade            (offline baseline alphas if no core)
      python3 -m mentat.trade --fresh    (ignore warm-started memory)

Data: defaults to a deterministic synthetic multi-regime universe with a small,
real, regime-consistent edge (so robust alphas can be found and overfits get
killed). Drop in real OHLCV later by building a Bars from a CSV and passing it to
AlphaProblem(bars=...).
"""
from __future__ import annotations

import sys
from pathlib import Path

from .core import Memory, solve
from .reasoning import AnthropicCore, core_available
from .trade_lab import AlphaProblem, AlphaProposer, expr_to_str


class _Broken:
    def complete_text(self, *a, **k):
        raise RuntimeError("no core")


def _logger(proposer):
    def log(msg: str):
        if proposer.note:
            print(f"      [{proposer.note}]")
        elif proposer.last:
            print(f"      core proposed: {proposer.last[0]} ...")
        print(f"   {msg}")
    return log


def main() -> int:
    generations, k = 12, 6
    # Fixed multiple-testing N = the alphas this study will try. The deflation uses
    # it so the bar to clear reflects the full search, not a single lucky draw.
    problem = AlphaProblem(n_trials=generations * k)
    core = AnthropicCore() if core_available() else None
    proposer = AlphaProposer(core=core or _Broken())

    print("PROJECT          anti-overfit alpha discovery (VISION.md flagship)")
    print("VERIFIER         walk-forward OOS across regimes, after costs, deflated Sharpe")
    print(f"DATA             synthetic multi-regime universe "
          f"({len(problem.bars.close)} bars, {len(problem.bars.regimes)} regimes)")
    print(f"BAR/COST         cost={problem.cost:.4f} per unit turnover; "
          f"multiple-testing N={problem.n_trials}")
    print(f"REASONING CORE   {core.model if core else 'offline baseline alphas only'}")
    print(f"GOAL             deflated worst-regime OOS Sharpe >= {problem.target:.2f}\n")

    mem_path = Path(__file__).parent / "trade_memory.json"   # warm-start across runs
    memory = Memory() if "--fresh" in sys.argv else Memory.load(mem_path)
    result = solve(problem, proposer, memory, generations=generations, k=k,
                   log=_logger(proposer))
    memory.save(mem_path)

    print()
    print(f"BEST verified deflated OOS Sharpe: {result.best_score:+.3f}   "
          f"(bar to clear {problem.target:.2f})")
    if result.solved:
        print("=> Found an alpha that survived OOS across regimes, after costs, deflated.")
    elif result.best_score > 0:
        print("=> Positive deflated OOS edge but under the bar to count as solved (honest).")
    else:
        print("=> No alpha cleared the anti-overfit gate in budget — an honest negative result.")
    if memory.best_candidate is not None:
        print(f"best alpha: {expr_to_str(memory.best_candidate)}")
        print(f"expr:       {memory.best_candidate}")
    if result.verdict and result.verdict.detail:
        print(f"detail:     {result.verdict.detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
