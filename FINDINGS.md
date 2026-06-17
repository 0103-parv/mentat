# Findings — engine runs (2026-06-16, afternoon)

You asked me to "go work and impress you" while you were out. Here's the honest version.

**The honest constraint first:** a powered-off laptop runs nothing — no process, no API
calls, no compute. So I can't work for hours on a dark machine; I can't invent new physics
or beat markets in a turn. What I *can* do (and did) is run our **verification-gated
discovery engines** for real while the machine was on, and leave you proven results. Every
number below is **proven by exhaustive search**, not asserted.

## Math discovery — proven verified sets
The engine proposes a construction as code; the verifier *executes it and exhaustively
checks the defining property*. Sizes below are certified (every pair/triple checked):

| Sidon set (all pairwise sums distinct) | AP-free set (no 3-term arithmetic progression) |
|---|---|
| [1,200] → **14** | [1,243] → **32** |
| [1,500] → **20** | [1,729] → **64** |
| [1,1000] → **27** | [1,2187] → **128** |

Honest caveat: these come from *known* constructions (greedy Sidon; the base-3 "no digit 2"
AP-free set). They are real and rigorously verified, but they are not *new* mathematics.
Beating the known frontier (a genuinely novel construction) is what FunSearch/AlphaEvolve
do — and it takes **days of search**, not one turn. Our machine is built to do exactly that
kind of search; it just needs to be left running.

## Self-research — improving your own alpha-evolver heuristic
Ran `mentat.improve` (the loop proposes a Max Cut heuristic; the verifier is alpha-evolver's
*own* benchmark). This run reached **fitness 0.7785 vs the 0.7788 baseline** — within 0.0003,
an honest near-miss this round (an earlier run hit 0.7800 and beat it). Memory now persists,
so each run warm-starts from the last. Best move found: `add(flip_gain, sign(cross_weight))`.

## New this session — a second discovery domain
Added `mentat/cap_set.py` + `mentat/discover_capset.py`: the largest 3-term-AP-free set in
[1,n] (the 1-D cap-set / Roth's-theorem analog), reusing the proven sandbox + counterexample
search. The engine is now genuinely multi-domain (Sidon + AP-free + Max Cut self-research).

## Known issue found (for next session to fix)
The process-sandbox (`run_construction`, spawn-based) fails when the caller's entry point is
a `-c`/stdin script (it tries to re-import `<stdin>`). It works fine via `python3 -m ...`
(tests + all runners), so normal usage is unaffected — but it should be hardened (use `fork`
on macOS, or pass the candidate without re-importing main).

## To actually push the frontier (needs the laptop ON, ideally a fresh ~/mentat session)
```bash
cd ~/mentat && set -a && . ~/swechats/.env && set +a
~/swechats/.venv/bin/python -m mentat.improve          # keeps beating your own heuristic (persists)
~/swechats/.venv/bin/python -m mentat.discover         # larger verified Sidon sets
~/swechats/.venv/bin/python -m mentat.discover_capset  # larger verified AP-free sets
```
Leave these looping for real hours of compute and the discoveries get genuinely interesting.
