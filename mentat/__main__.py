"""mentat — a verification-gated cognitive kernel. One front door for the whole system.

    python3 -m mentat                  # overview: what this is, what's live, the engines
    python3 -m mentat <engine> [args]  # run any engine, e.g.  python3 -m mentat trade --fresh
    python3 -m mentat list             # just the engine names

Nothing becomes memory, an opinion, or an action until a verifier passes it. Every engine
below is an instance of that loop — propose -> verify -> remember -> reflect.
"""
from __future__ import annotations

import importlib
import sys

ENGINES = {
    "demo": "rediscover a hidden law from samples (offline kernel demo)",
    "think": "rediscover a hidden law with the Claude reasoning core",
    "discover": "discover a verified Sidon set (math, exhaustively proven)",
    "discover_diverse": "illuminate a catalog of proven Sidon sets (the frontier)",
    "discover_capset": "discover a verified AP-free / cap set",
    "costas": "discover a verified Costas array (2-D Sidon; radar/sonar)",
    "improve": "improve alpha-evolver's Max Cut heuristic (self-research)",
    "trade": "anti-overfit alpha discovery (deflated worst-regime OOS gate)",
    "realm": "map a market until dry (toward omniscient-in-one-realm, honestly)",
    "curriculum": "study a market facet by facet (topic mastery)",
    "creativity": "novelty ablation — brain off vs on",
    "illuminate": "MAP-Elites illumination — a diverse portfolio of verified designs",
    "imagine": "creative synthesis (Boden operators + risk dial), all gated",
    "selfimprove": "measured cold-vs-warm + transfer — does it really learn?",
    "cognition": "creative cognition loop — propose, verify, remember, sleep, get sharper",
    "selfmodel": "self-awareness — capabilities + grounded effort/time estimation",
    "work": "budgeted self-improvement — a verified curriculum, compounding, honest dry-stop",
    "local_brain": "a local on-device LLM (mlx) proposing in the gated loop — no API (.venv-mlx)",
    "cad": "CAD-as-code — design a verified parametric part, emit OpenSCAD (zero GPU)",
    "consolidate": "fast+slow memory consolidation (the brain's sleep)",
    "rag": "grounded finance QA — cites sources or refuses",
    "research": "research autopilot — loop the gated engines and keep what's proven",
    "operate": "full-authority MANDATE executor (you have authority to X)",
    "secrets": "store/inspect credentials (env / Keychain / .env)",
    "jarvis": "the personal-ops assistant (voice UI + tools)",
}


def overview() -> int:
    print("mentat — a verification-gated cognitive kernel")
    print("  nothing becomes memory, an opinion, or an action until a verifier passes it.\n")
    try:
        from .jarvis import integrations_report
        print(integrations_report() + "\n")
    except Exception:
        pass
    print("engines:  python3 -m mentat <name> [args]")
    for name, desc in ENGINES.items():
        print(f"  {name:17} {desc}")
    print("\ntests:    python3 -m tests.test_core")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "overview"):
        return overview()
    if argv[0] == "list":
        print("\n".join(ENGINES))
        return 0
    name = argv[0]
    if name not in ENGINES:
        print(f"unknown engine: {name!r}\n")
        return overview() or 1
    sys.argv = [f"mentat.{name}"] + argv[1:]      # let the engine parse its own args
    mod = importlib.import_module(f"mentat.{name}")
    fn = getattr(mod, "main", None)
    if fn is None:                                # e.g. secrets exposes _cli
        cli = getattr(mod, "_cli", None)
        return cli(argv[1:]) if cli else 0
    return fn() or 0


if __name__ == "__main__":
    raise SystemExit(main())
