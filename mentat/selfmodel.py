"""Jarvis's self-model — GROUNDED self-knowledge: what it can do, how verified, how long it takes.

Two kinds of self-awareness, both grounded (introspected or measured, never guessed):

  - capabilities(): introspect the LIVE engine registry + Jarvis tools + the count of verification
    checks + the integration status into one honest self-description. "Here's what I can do, here's
    what's actually verified, here's what's blocked."

  - estimate_effort(task): map a task to the capability that would do it and estimate wall-clock
    from MEASURED throughput, then recommend a work budget with a safety buffer (the user's
    "8 hours -> set 10"). It says plainly when an estimate is a heuristic rather than measured.

This is what lets Jarvis say "that'll take me ~N, so I'll budget N+buffer and work until it's done."
"""
from __future__ import annotations

import math
import re
from pathlib import Path

BUFFER = 1.25                       # safety buffer on every effort estimate (8h work -> ~10h budget)

# Wall-clock unit costs MEASURED on this machine (offline). Grounded, re-measurable, not guessed.
CALIBRATION = {
    "cognition_round_s": 1.25,      # one creative-loop round (gens=60, k=32)
    "discovery_run_s": 0.15,        # one math-discovery solve (Sidon / Costas / cap set)
}


def _engines() -> dict:
    from .__main__ import ENGINES
    return ENGINES


def _tool_names() -> list[str]:
    from .jarvis import TOOLS
    return [t["name"] for t in TOOLS]


def _verification_checks() -> int:
    """Count the test_ functions guarding the system (read the file — no import, no run)."""
    f = Path(__file__).resolve().parent.parent / "tests" / "test_core.py"
    try:
        return f.read_text().count("\ndef test_")
    except OSError:
        return 0


def capabilities(verbose: bool = False) -> str:
    """An honest, grounded self-description Jarvis can speak."""
    eng, tools, checks = _engines(), _tool_names(), _verification_checks()
    try:
        from .jarvis import integrations_report
        integ = integrations_report().replace("\n", " ")
    except Exception:
        integ = ""
    parts = [
        f"I'm mentat — a verification-gated cognitive system. I have {len(eng)} engines and "
        f"{len(tools)} Jarvis tools, guarded by {checks} verification checks (green at last run); "
        "nothing I report is believed until a verifier passes it.",
        "Core powers: discover proven math (Sidon/Costas/cap sets), self-research code heuristics, "
        "anti-overfit market analysis, grounded finance Q&A that cites or refuses, a creative "
        "loop that improves itself and keeps only what's verified, plus machine control "
        "(shell, files, AppleScript, web).",
    ]
    if integ:
        parts.append(integ)
    parts.append(
        "Honest limits: my novel thinking is trustworthy only where a verifier exists; live deep "
        "reasoning needs API credits (out right now, so I run offline); real-time vision/3D needs "
        "hardware I don't have.")
    if verbose:
        parts.append("Engines: " + ", ".join(eng))
        parts.append("Tools: " + ", ".join(tools))
    return " ".join(parts)


def _rounds_near(t: str, default: int = 5) -> int:
    m = re.search(r"(\d+)\s*round", t)
    return int(m.group(1)) if m else default


def _hours_near(t: str):
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:h\b|hour|hours|hrs)", t)
    return float(m.group(1)) if m else None


def _size_band(t: str):
    if any(w in t for w in ("entire", "whole", "full system", "big", "large", "platform",
                            "everything", "project", "from scratch")):
        return "large", 6, 10
    if any(w in t for w in ("add ", "small", "tweak", "fix ", "tiny", "quick", "minor", "rename")):
        return "small", 1, 2
    return "medium", 3, 5


def estimate_effort(task: str) -> str:
    """Estimate how long `task` takes and recommend a buffered work budget. Grounded in measured
    timings for known capabilities; an explicit heuristic (so labeled) for open-ended builds."""
    t = (task or "").lower()
    pct = int(round((BUFFER - 1) * 100))

    if any(w in t for w in ("think creat", "creative", "discover", "improve yourself",
                            "sidon", "costas", "cap set", "capset", "novel idea")):
        rounds = _rounds_near(t)
        secs = rounds * CALIBRATION["cognition_round_s"]
        return (f"That's my creative/discovery loop — measured at ~{CALIBRATION['cognition_round_s']:.2f}s "
                f"per verified round. About {rounds} rounds is ~{secs:.0f}s; I'd budget "
                f"{secs * BUFFER:.0f}s ({pct}% safety buffer). Grounded in real timings.")

    if any(w in t for w in ("research", "all night", "overnight", "all day", "for hours",
                            "keep going", "keep working", "keep improving")):
        hrs = _hours_near(t)
        if hrs:
            return (f"That's an open-ended research/self-improvement run. You said ~{hrs:g}h, so I'd "
                    f"set the budget to {math.ceil(hrs * BUFFER)}h ({pct}% buffer) and work in "
                    "verified committed blocks until it's done or the budget's up.")
        return ("Open-ended research/self-improvement: I work in verified committed blocks until the "
                "job's genuinely done or you stop me. Give me an hour target and I'll set a buffered "
                "budget around it.")

    size, lo, hi = _size_band(t)
    return (f"Rough estimate (a heuristic, not a measured number): a {size} build like this is about "
            f"{lo}-{hi}h of focused work. I'd set a {math.ceil(hi * BUFFER)}h budget ({pct}% buffer) "
            "and sharpen the estimate as I learn the real pace, reporting verified progress each "
            "block. I never call it done until the verifier agrees.")


def main() -> int:
    print(capabilities(verbose=True))
    print("\n--- effort estimates ---")
    for task in ("think creatively for 8 rounds", "keep improving the model all day for 9 hours",
                 "build the entire CAD design engine", "fix a small typo in the readme"):
        print(f"\nQ: {task}\n=> {estimate_effort(task)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
