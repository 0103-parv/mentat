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
from .trade_lab import AlphaProblem, AlphaProposer, expr_to_str, load_price_csv, synthetic_universe


class _Broken:
    def complete_text(self, *a, **k):
        raise RuntimeError("no core")


def _data_args() -> list[str]:
    paths = []
    for i, a in enumerate(sys.argv):
        if a == "--data" and i + 1 < len(sys.argv):
            paths.append(sys.argv[i + 1])
        elif a.startswith("--data="):
            paths.append(a.split("=", 1)[1])
    return paths


def _load_bars():
    """(label, bars) pairs to run. Real CSVs via --data, else the synthetic testbed."""
    paths = _data_args()
    if not paths:
        return [("synthetic", synthetic_universe())]
    out = []
    for p in paths:
        try:
            out.append((Path(p).stem, load_price_csv(p)))
        except Exception as e:
            print(f"  ! skipping {p}: {type(e).__name__}: {e}")
    return out or [("synthetic", synthetic_universe())]


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
    core = AnthropicCore() if core_available() else None
    series = _load_bars()

    print("PROJECT          anti-overfit alpha discovery (VISION.md flagship)")
    print("VERIFIER         walk-forward OOS across regimes, after costs, deflated Sharpe")
    print(f"REASONING CORE   {core.model if core else 'offline baseline alphas only'}")
    print(f"SERIES           {', '.join(label for label, _ in series)}\n")

    fresh = "--fresh" in sys.argv
    solved_any = False
    for label, bars in series:
        # Fixed multiple-testing N = the alphas this study will try. The deflation
        # uses it so the bar reflects the full search, not a single lucky draw.
        problem = AlphaProblem(bars=bars, n_trials=generations * k)
        proposer = AlphaProposer(core=core or _Broken())
        print(f"--- {label}: {len(bars.close)} bars, {len(bars.regimes)} regimes "
              f"(cost={problem.cost:.4f}, N={problem.n_trials}, "
              f"bar>={problem.target:.2f}) ---")
        # One memory file per series so warm-starts don't mix alphas across markets.
        mem_path = Path(__file__).parent / f"trade_memory_{label}.json"
        memory = Memory() if fresh else Memory.load(mem_path)
        result = solve(problem, proposer, memory, generations=generations, k=k,
                       log=_logger(proposer))
        memory.save(mem_path)

        if result.solved:
            solved_any = True
            verdict = "survived OOS across regimes, after costs, deflated"
        elif result.best_score > 0:
            verdict = "positive deflated OOS edge, under the bar (honest)"
        else:
            verdict = "no alpha cleared the gate — honest negative result"
        best = expr_to_str(memory.best_candidate) if memory.best_candidate is not None else "(none)"
        print(f"  => {label}: deflated OOS Sharpe {result.best_score:+.3f} "
              f"[bar {problem.target:.2f}] — {verdict}")
        print(f"     best alpha: {best}")
        if result.verdict and result.verdict.detail:
            print(f"     {result.verdict.detail}\n")
    print("Verification is the gate: every number above is a worst-regime, after-cost, "
          f"deflated OOS Sharpe.{'' if solved_any else ' Nothing cleared the bar — honest.'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
