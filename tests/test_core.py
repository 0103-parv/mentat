"""Tests for the Mentat kernel. Runs under pytest or directly:

    python3 -m tests.test_core
"""
from __future__ import annotations

import random
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mentat.core import Lesson, Memory, Mind, Verdict, productive_surprise, solve
from mentat.demo import LLMProposer, RandomProposer, SymbolicRegression, ev, parse_infix, to_str
from mentat.reasoning import ScriptedCore, extract_json_list


def test_grounding_firewall_rejects_fabrication():
    """A lesson whose claim shares no vocabulary with its evidence is rejected."""
    grounded = Lesson(when="reducing rmse on target", do="reuse motif rmse target",
                      evidence="this motif lowered rmse on the target samples")
    fabricated = Lesson(when="do something vague", do="trust the vibes",
                        evidence="completely unrelated citation about turtles")
    assert grounded.grounded()
    assert not fabricated.grounded()

    mem = Memory()
    assert mem.learn(grounded) is True          # enters memory
    assert mem.learn(fabricated) is False       # blocked at the firewall
    assert len(mem.lessons) == 1


def test_corroboration_merges_not_duplicates():
    mem = Memory()
    le = Lesson(when="reducing rmse", do="reuse rmse motif",
                evidence="rmse motif reduced rmse")
    assert mem.learn(le) is True
    again = Lesson(when="reducing rmse", do="reuse rmse motif",
                   evidence="rmse motif reduced rmse")
    assert mem.learn(again) is False            # merged
    assert len(mem.lessons) == 1
    assert mem.lessons[0].corroboration == 2    # strengthened, not duplicated


def test_productive_surprise_is_inverted_u():
    """Peaks at moderate surprise; the extremes earn less signal."""
    peak = productive_surprise(1.0, 1.0)
    boring = productive_surprise(0.05, 1.0)
    extreme = productive_surprise(8.0, 1.0)
    assert peak > boring
    assert peak > extreme
    assert productive_surprise(float("inf"), 1.0) == 0.0   # guarded


def test_mode_switches_on_stall_and_junk():
    m = Mind()
    assert m.reflect(improved=True, quarantine_rate=0.0) == "focus"
    m.reflect(improved=False, quarantine_rate=0.0)
    assert m.reflect(improved=False, quarantine_rate=0.0)  # 2 stalls...
    assert m.reflect(improved=False, quarantine_rate=0.0) == "dream"  # 3rd -> dream
    assert m.reflect(improved=True, quarantine_rate=0.9) == "recover"  # junk -> recover


def test_memory_roundtrips_and_recall_reverifies():
    xs = [round(i * 0.2, 2) for i in range(-10, 11)]
    problem = SymbolicRegression(lambda x: x ** 3 - 2 * x + 1, xs, tol=0.10)

    mem = Memory()
    for seed in (11, 12, 13, 14, 15):
        r = solve(problem, RandomProposer(random.Random(seed)), mem,
                  generations=80, k=48, log=lambda *_: None)
        if r.solved:
            break
    assert mem.best_candidate is not None

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "m.json"
        mem.save(path)
        loaded = Memory.load(path)
        # JSON stores the tree as nested lists; compare canonical string form.
        assert to_str(loaded.best_candidate) == to_str(mem.best_candidate)
        assert len(loaded.lessons) == len(mem.lessons)
        # warm start recalls AND re-verifies the remembered law
        warm = solve(problem, RandomProposer(random.Random(99)), loaded,
                     generations=80, k=48, log=lambda *_: None)
        assert warm.solved
        assert warm.generations == 1            # instant recall, re-verified


def test_parse_infix_matches_target_and_rejects_junk():
    xs = [-1.0, 0.0, 1.0, 2.0]
    tree = parse_infix("x**3 - 2*x + 1")          # powers expand into the +-*/ DSL
    assert ev(tree, xs) == [(x ** 3 - 2 * x + 1) for x in xs]
    assert parse_infix("-x")[0] == "*"             # unary minus -> (-1 * x)
    for junk in ("y + 1", "sin(x)", "x ** 9", "__import__('os')"):
        try:
            parse_infix(junk)
            assert False, f"should have rejected {junk!r}"
        except (ValueError, SyntaxError):
            pass


def test_extract_json_list_is_tolerant():
    assert extract_json_list('["x*x", "x+1"]') == ["x*x", "x+1"]
    # preamble + a numbered list still yields the candidates
    msgs = extract_json_list("Here are ideas:\n1. x*x\n2. x**3 - 2*x + 1\n")
    assert "x*x" in msgs and "x**3 - 2*x + 1" in msgs


def test_llm_proposer_path_solves_through_the_gate():
    """The reasoning-core path, exercised with a scripted core (no network).
    A proposed solution must still pass the verifier to count as solved."""
    xs = [round(i * 0.2, 2) for i in range(-10, 11)]
    problem = SymbolicRegression(lambda x: x ** 3 - 2 * x + 1, xs, tol=0.05)
    core = ScriptedCore(responses=['["x*x", "x**3 - 2*x + 1", "x+1"]'])
    proposer = LLMProposer(core=core, fallback=RandomProposer(random.Random(0)))
    result = solve(problem, proposer, Memory(), generations=2, k=6, log=lambda *_: None)
    assert result.solved
    assert proposer.last and any("x" in s for s in proposer.last)  # recorded its proposals


def test_llm_proposer_falls_back_when_core_errors():
    class BrokenCore:
        def complete_text(self, system, user, *, max_tokens=2048):
            raise RuntimeError("simulated network failure")

    xs = [round(i * 0.2, 2) for i in range(-10, 11)]
    problem = SymbolicRegression(lambda x: x ** 3 - 2 * x + 1, xs, tol=0.05)
    proposer = LLMProposer(core=BrokenCore(), fallback=RandomProposer(random.Random(1)))
    cands = proposer.propose(problem, Memory(), Mind(), k=6)
    assert len(cands) == 6                 # offline proposer filled the whole batch
    assert "core error" in proposer.note   # and the failure was recorded, not raised


def test_math_counterexample_search_and_sandbox():
    from mentat.math_lab import SidonSet, counterexample_sidon, run_construction

    assert counterexample_sidon([1, 2, 5, 11]) is None      # a real Sidon set
    assert counterexample_sidon([1, 2, 3, 4]) is not None    # 1+4 == 2+3

    prob = SidonSet(n=30, target=100, check_ns=[30, 17])     # target huge -> never "solved"
    good = prob.verify("def build(n):\n    return [1, 2, 5, 11]")
    assert not good.suspicious and good.score == 4           # valid, kept as a library entry
    bad = prob.verify("def build(n):\n    return [1, 2, 3, 4]")
    assert bad.suspicious                                     # counterexample found -> quarantined
    forbidden = prob.verify("def build(n):\n    import os\n    return [1]")
    assert forbidden.suspicious                               # sandbox rejects imports
    assert run_construction("def build(n):\n    return list(range(1, 4))", 10) == [1, 2, 3]


def test_math_sandbox_is_process_bounded():
    import time
    from mentat.math_lab import run_construction
    t = time.time()
    try:                                   # a CPU bomb must be killed, not hang
        run_construction("def build(n):\n    x = 0\n    while True:\n        x += 1", 30, time_limit=2.0)
        assert False, "resource bomb was not stopped"
    except (TimeoutError, ValueError):
        pass
    assert time.time() - t < 8, "sandbox did not bound runtime"
    try:                                   # floats rejected, not silently truncated
        run_construction("def build(n):\n    return [1, 2.5, 4]", 30)
        assert False, "float construction was not rejected"
    except ValueError:
        pass
    assert run_construction("def build(n):\n    return [1, 2, 5, 11]", 30) == [1, 2, 5, 11]


def test_math_loop_keeps_valid_quarantines_broken():
    from mentat.core import solve
    from mentat.math_lab import CodeProposer, GREEDY, SidonSet
    from mentat.reasoning import ScriptedCore

    prob = SidonSet(n=60, target=100, check_ns=[60, 31])     # never solved -> runs full budget
    # one block is a real Sidon construction; one is broken (a dense range, sums collide)
    reply = f"```python\n{GREEDY}\n```\n```python\ndef build(n):\n    return list(range(1, n + 1))\n```"
    proposer = CodeProposer(core=ScriptedCore([reply]), fallback_codes=[])
    mem = Memory()
    result = solve(prob, proposer, mem, generations=1, k=2, log=lambda *_: None)
    assert mem.best_candidate is not None                    # the greedy construction was kept
    assert result.best_score > 3                             # a non-trivial valid Sidon set
    assert any(s > 0 for s, _ in mem.elites)                 # verified library is non-empty


def test_jarvis_memory_roundtrip_survives_punctuation():
    import mentat.jarvis as J
    with tempfile.TemporaryDirectory() as d:
        J.MEMORY_PATH = Path(d) / "m.json"
        assert "haven't" in J.tool_recall("answers")              # empty store
        J.tool_remember("Prefers concise, no-fluff answers.")     # note has punctuation
        assert "concise" in J.tool_recall("how do I like my answers?")  # recall matches
        assert "concise" in J.tool_recall("")                     # bare recall -> recent
    assert J.tool_get_datetime()                                  # non-empty string


def test_jarvis_shell_runs_but_guards_catastrophe():
    import mentat.jarvis as J
    assert J._is_catastrophic("rm -rf /") is True
    assert J._is_catastrophic("rm -rf ~") is True
    assert J._is_catastrophic("sudo rm -rf /*") is True
    assert J._is_catastrophic("dd if=/dev/zero of=/dev/disk0") is True
    assert J._is_catastrophic("rm -rf /Users/me/project/build") is False   # normal cleanup ok
    assert J._is_catastrophic("ls -la /") is False
    assert "hi there" in J.tool_shell("echo 'hi there'")                   # real execution
    if J._GUARD:
        assert "Refused" in J.tool_shell("rm -rf /")                       # floor holds


def test_jarvis_web_and_voice_helpers():
    import os
    import mentat.jarvis as J
    # web_fetch degrades gracefully on a bad URL (no raise)
    assert J.tool_web_fetch("http://nonexistent.invalid.localhost.test/").startswith("(could not fetch")
    # web_search degrades gracefully if offline / blocked (returns a string, never raises)
    assert isinstance(J.tool_web_search("python"), str)
    # ElevenLabs is cleanly disabled without a key
    if not os.environ.get("ELEVENLABS_API_KEY"):
        assert J.elevenlabs_enabled() is False
        assert J.elevenlabs_tts("hello") is None
    assert "web_search" in J._DISPATCH and "web_fetch" in J._DISPATCH
    # calendar/reminder tools are wired; empty reminder is a no-op (no OS side effect)
    assert "add_reminder" in J._DISPATCH and "calendar_today" in J._DISPATCH
    assert J.tool_add_reminder("") == "(nothing to remind about)"


def test_elite_pool_dedups_and_guards_nan():
    from mentat.core import Memory
    m = Memory()
    for _ in range(20):
        m.consider_elite(0.5, ("x",))     # same candidate re-proposed every gen
    assert len(m.elites) == 1             # collapses to one slot, not 12 copies
    m.consider_elite(0.9, ("y",))
    assert len(m.elites) == 2
    m.consider_elite(float("nan"), ("z",))
    assert len(m.elites) == 2             # a NaN score is never pooled


def test_self_research_verifier_when_available():
    try:
        import numpy  # noqa: F401
        from mentat.self_research import MaxCutHeuristic
        prob = MaxCutHeuristic()
    except Exception:
        print("  (skipped: numpy / alpha-evolver not available on this interpreter)")
        return
    good = prob.verify(prob.baseline)
    assert not good.suspicious and good.score > 0.5             # baseline verifies through the real eval
    bad = prob.verify({"init": ["rank", "flip_gain"], "move": "flip_gain",
                       "steps_per_node": 4, "restarts": 2, "tabu_window": 1})
    assert bad.suspicious                                       # init can't use a dynamic field -> rejected


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")


if __name__ == "__main__":
    _run_all()
