"""Research autopilot — hand it a time budget and walk away.

This is mandate mode aimed at the discovery engines: it loops the verification-gated
engines for as long as you give it, keeps ONLY what each engine's verifier proves,
accumulates the best-ever findings into a persistent journal, and writes up what held.
Safe to leave running for hours — every engine is deterministic, offline, pure-Python,
and gated, so the journal only ever grows with PROVEN results (or honest negatives).

  python3 -m mentat.research --minutes 30      # run for ~30 minutes, then report
  python3 -m mentat.research --rounds 3         # or a fixed number of rounds
  python3 -m mentat.research --report           # just print the accumulated journal

The journal (gitignored `research_journal.json`) carries across runs, so each session
builds on the last — more compute, more proven results.
"""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

from .core import Memory, solve

JOURNAL = Path(__file__).parent / "research_journal.json"


# --------------------------------------------------------------------------- #
# research jobs — each runs ONE gated engine and returns verified findings     #
# --------------------------------------------------------------------------- #
def job_sidon_frontier(seed: int) -> dict:
    """Illuminated math: the largest PROVEN Sidon set per span bucket."""
    from .discover_diverse import DiverseSidon, SidonSetProposer, SPAN_BUCKET
    mem = Memory()
    solve(DiverseSidon(120), SidonSetProposer(random.Random(seed), 120), mem,
          generations=40, k=20, log=lambda *_: None)
    frontier = {str(niche): int(size) for niche, (size, _) in sorted(mem.archive.items())}
    return {"domain": "sidon_frontier", "span_bucket": SPAN_BUCKET,
            "frontier": frontier, "max_size": max(frontier.values(), default=0)}


def job_market_topics(seed: int) -> dict:
    """Topic mastery: which market facets hold up out-of-sample, after costs, deflated."""
    from .curriculum import study
    from .trade_lab import synthetic_universe
    kb, _ = study("synthetic market", synthetic_universe(), gens=8, k=14, seed=seed)
    verified = [f for f, d in kb.facets.items() if d["verified"]]
    return {"domain": "market_topics", "verified": verified,
            "facets_studied": len(kb.facets)}


def job_design_illumination(seed: int) -> dict:
    """MAP-Elites: how much of a design behavior space gets filled with verified designs."""
    from .illuminate import IlluminationProposer, PatternDesign
    mem = Memory()
    solve(PatternDesign(20), IlluminationProposer(random.Random(seed), 20), mem,
          generations=40, k=20, log=lambda *_: None)
    return {"domain": "design_illumination", "niches_covered": mem.archive_coverage(),
            "of": 21}


JOBS = [job_sidon_frontier, job_market_topics, job_design_illumination]


# --------------------------------------------------------------------------- #
# journal: keep the best-ever finding per domain across all rounds/sessions    #
# --------------------------------------------------------------------------- #
def _load() -> dict:
    if JOURNAL.exists():
        try:
            return json.loads(JOURNAL.read_text())
        except Exception:
            pass
    return {"rounds": 0, "domains": {}}


def _merge(journal: dict, finding: dict) -> None:
    """Accumulate: keep the strongest result seen for each domain."""
    dom = finding["domain"]
    cur = journal["domains"].get(dom)
    if dom == "sidon_frontier":
        merged = dict(cur.get("frontier", {})) if cur else {}
        for span, size in finding["frontier"].items():
            if size > merged.get(span, 0):                 # best (largest) proven set per span
                merged[span] = size
        journal["domains"][dom] = {"span_bucket": finding["span_bucket"],
                                   "frontier": merged,
                                   "max_size": max(merged.values(), default=0)}
    elif dom == "market_topics":
        verified = sorted(set((cur or {}).get("verified", [])) | set(finding["verified"]))
        journal["domains"][dom] = {"verified": verified,
                                   "facets_studied": finding["facets_studied"]}
    elif dom == "design_illumination":
        best = max(finding["niches_covered"], (cur or {}).get("niches_covered", 0))
        journal["domains"][dom] = {"niches_covered": best, "of": finding["of"]}


def report(journal: dict) -> str:
    lines = [f"RESEARCH JOURNAL — {journal['rounds']} round(s) of verified discovery", ""]
    d = journal["domains"]
    if "sidon_frontier" in d:
        f = d["sidon_frontier"]
        lines.append(f"  Sidon frontier (proven sets): {len(f['frontier'])} span niches, "
                     f"largest size {f['max_size']}")
    if "market_topics" in d:
        m = d["market_topics"]
        lines.append(f"  Market topics: {len(m['verified'])}/{m['facets_studied']} facets hold "
                     f"up OOS — {', '.join(m['verified']) or 'none (honest)'}")
    if "design_illumination" in d:
        i = d["design_illumination"]
        lines.append(f"  Design illumination: {i['niches_covered']}/{i['of']} behavior niches "
                     "filled with verified designs")
    lines.append("")
    lines.append("  Every line above is a verifier-PROVEN result (or an honest negative). "
                 "Nothing asserted.")
    return "\n".join(lines)


def run(*, rounds: int | None = None, minutes: float | None = None, log=print) -> dict:
    journal = _load()
    start = time.monotonic()
    r = 0
    while True:
        if rounds is not None and r >= rounds:
            break
        if minutes is not None and (time.monotonic() - start) >= minutes * 60:
            break
        if rounds is None and minutes is None and r >= 1:
            break
        seed = 1000 + journal["rounds"]                    # vary per accumulated round
        for job in JOBS:
            try:
                finding = job(seed)
                _merge(journal, finding)
                log(f"  round {journal['rounds'] + 1}: {job.__name__} -> "
                    f"{ {k: v for k, v in finding.items() if k != 'domain'} }")
            except Exception as e:                          # one engine failing never aborts the night
                log(f"  round {journal['rounds'] + 1}: {job.__name__} skipped ({type(e).__name__})")
        journal["rounds"] += 1
        JOURNAL.write_text(json.dumps(journal, indent=2))   # checkpoint after every round
        r += 1
    return journal


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--report" in argv:
        print(report(_load()))
        return 0
    rounds = minutes = None
    if "--rounds" in argv:
        rounds = int(argv[argv.index("--rounds") + 1])
    if "--minutes" in argv:
        minutes = float(argv[argv.index("--minutes") + 1])
    if rounds is None and minutes is None:
        rounds = 2
    horizon = f"{minutes} min" if minutes else f"{rounds} round(s)"
    print(f"RESEARCH AUTOPILOT — running gated discovery engines for {horizon}\n")
    journal = run(rounds=rounds, minutes=minutes)
    print("\n" + report(journal))
    print(f"\n(journal saved to {JOURNAL.name}; re-run any time to keep building on it.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
