"""Mandate runner — "you have full authority to <task>" and Mentat does it itself.

Grant a task on the command line; Mentat plans and executes it autonomously with its
tools (shell, files, web, AppleScript, the discovery engines), using the credentials
you've stored, narrating each step. The safety floor stays on (it refuses irreversible
destruction and tells you), and anything that genuinely needs a human is reported back.

Run:
    python3 -m mentat.operate "audit the mentat repo for TODOs and write them to TODO.md"
    python3 -m mentat.operate --steps 40 "<task>"
    python3 -m mentat.operate --no-guard "<task>"     # remove the safety floor (your call)

Needs a Claude key (env / Keychain / .env). Store one with: python3 -m mentat.secrets set ANTHROPIC_API_KEY
"""
from __future__ import annotations

import os
import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    steps = 25
    if "--no-guard" in argv:                 # explicit, user-chosen: drop the safety floor
        os.environ["JARVIS_NO_GUARD"] = "1"
        argv.remove("--no-guard")
    if "--steps" in argv:
        i = argv.index("--steps")
        if i + 1 < len(argv):
            steps = int(argv[i + 1])
            del argv[i:i + 2]
    goal = " ".join(argv).strip()
    if not goal:
        print('usage: python3 -m mentat.operate [--steps N] [--no-guard] "<task>"')
        return 1

    from .jarvis import Jarvis, integrations_report
    from .reasoning import core_available

    if not core_available():
        print("No Claude key found. Store one: python3 -m mentat.secrets set ANTHROPIC_API_KEY")
        return 1

    print(integrations_report())
    print(f"\nMANDATE: {goal}\n" + "-" * 60)
    jarvis = Jarvis()

    def narrate(step: int, msg: str) -> None:
        print(f"  [{step + 1:>2}] {msg.strip()[:300]}")

    report = jarvis.operate(goal, max_steps=steps, on_step=narrate)
    print("-" * 60 + "\nREPORT:\n" + report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
