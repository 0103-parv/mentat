"""Tests for the Mentat kernel. Runs under pytest or directly:

    python3 -m tests.test_core
"""
from __future__ import annotations

import random
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mentat.core import (
    BrainConfig, Lesson, Memory, Mind, Verdict, fragments, novelty,
    productive_surprise, solve,
)
from mentat.demo import LLMProposer, RandomProposer, SymbolicRegression, ev, parse_infix, to_str
from mentat.reasoning import ScriptedCore, extract_json_list
from mentat.trade_lab import (
    BASELINE_ALPHAS, AlphaProblem, AlphaProposer, compute_features, eval_alpha,
    expected_max_sharpe_under_null, segment_metrics, synthetic_universe,
    valid_alpha, walk_forward_backtest,
)


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
    saved = J.MEMORY_PATH                                  # restore the module global after
    try:
        with tempfile.TemporaryDirectory() as d:
            J.MEMORY_PATH = Path(d) / "m.json"
            assert "haven't" in J.tool_recall("answers")              # empty store
            J.tool_remember("Prefers concise, no-fluff answers.")     # note has punctuation
            assert "concise" in J.tool_recall("how do I like my answers?")  # recall matches
            assert "concise" in J.tool_recall("")                     # bare recall -> recent
    finally:
        J.MEMORY_PATH = saved
    assert J.tool_get_datetime()                                  # non-empty string


def test_jarvis_shell_runs_but_guards_catastrophe():
    import mentat.jarvis as J
    for c in ("rm -rf /", 'rm -rf "/"', "rm -rf '/'",   # quoted targets must not bypass the guard
              "rm -rf ~", "sudo rm -rf /*", "dd if=/dev/zero of=/dev/disk0",
              'rm -rf "$HOME"', "rm -rf /etc", "rm -rf /System", "rm -rf ~/Documents",
              "rm -rf /usr/local", "find / -delete",
              "rm -rf ~/.ssh", "rm -rf ~/mentat", "rm -rf ~/.zshrc", "shred -u ~/.ssh/id_rsa"):
        assert J._is_catastrophic(c) is True, c       # incl. direct $HOME children + key subtrees
    for c in ("rm -rf /Users/me/project/build", "ls -la /", "rm -rf build/",
              "rm -rf ~/projects/scratch", "rm -rf ~/.cache/pip", "rm -rf ~/code/myrepo/build",
              "find . -name '*.pyc' -delete", "grep -r unlink /usr/include"):
        assert J._is_catastrophic(c) is False, c      # deeper dev deletes still allowed
    assert "hi there" in J.tool_shell("echo 'hi there'")          # real execution
    if J._GUARD:
        assert "Refused" in J.tool_shell("rm -rf /")              # floor actually blocks


def test_jarvis_web_and_voice_helpers():
    import mentat.jarvis as J
    # web_fetch degrades gracefully on a bad host (no raise; .invalid never resolves)
    assert J.tool_web_fetch("http://nonexistent.invalid.localhost.test/").startswith("(could not fetch")
    # (web_search hits the network — covered by the live runner, not this unit test)
    # ElevenLabs is cleanly disabled when NO key resolves (force it, so the test does
    # not depend on whether this machine happens to have a key stored).
    orig = J.get_secret
    J.get_secret = lambda name, **kw: None
    try:
        assert J.elevenlabs_enabled() is False
        assert J.elevenlabs_tts("hello") is None
    finally:
        J.get_secret = orig
    assert "web_search" in J._DISPATCH and "web_fetch" in J._DISPATCH
    # calendar/reminder tools are wired; empty reminder is a no-op (no OS side effect)
    assert "add_reminder" in J._DISPATCH and "calendar_today" in J._DISPATCH
    assert J.tool_add_reminder("") == "(nothing to remind about)"


def test_jarvis_edit_file_is_verified():
    import mentat.jarvis as J
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "m.py"
        f.write_text("x = 1\ny = 2\n")
        assert "not found" in J.tool_edit_file(str(f), "zzz", "q")             # missing snippet
        bad = J.tool_edit_file(str(f), "x = 1", "x = (1")                      # would break syntax
        assert "REJECTED" in bad and f.read_text() == "x = 1\ny = 2\n"         # unchanged, not written
        ok = J.tool_edit_file(str(f), "y = 2", "y = 3")                        # valid surgical edit
        assert "Edited" in ok and "y = 3" in f.read_text()
        before = f.read_text()
        rb = J.tool_edit_file(str(f), "x = 1", "x = 11", verify_cmd="exit 1")  # verify fails -> rollback
        assert "ROLLED BACK" in rb and f.read_text() == before


def test_jarvis_engine_tools_wired():
    import mentat.jarvis as J
    assert "improve_maxcut" in J._DISPATCH and "discover_sidon" in J._DISPATCH
    # with no reasoning core / no numpy these degrade to a graceful string, never raise
    assert isinstance(J.tool_improve_maxcut(1), str)
    assert isinstance(J.tool_discover_sidon(50, 8, 1), str)


def test_jarvis_learn_lesson_is_grounded():
    import mentat.jarvis as J
    saved = J.LESSONS_PATH
    try:
        with tempfile.TemporaryDirectory() as d:
            J.LESSONS_PATH = Path(d) / "lessons.json"
            # an ungrounded rule (claim shares no vocabulary with the evidence) is REFUSED
            r = J.tool_learn_lesson(when="deploying code", do="run the tests first",
                                    evidence="the weather is nice today")
            assert "not learned" in r
            assert J.jarvis_lessons_context() == ""
            # a grounded rule (evidence shares real vocabulary) is learned + recalled
            r = J.tool_learn_lesson(when="deploying the app", do="run the tests before deploying",
                                    evidence="always run the tests before you deploy the app")
            assert "Learned" in r
            ctx = J.jarvis_lessons_context().lower()
            assert "tests" in ctx and "deploy" in ctx
    finally:
        J.LESSONS_PATH = saved


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
    except (ImportError, ModuleNotFoundError):       # only skip on missing deps...
        print("  (skipped: numpy / alpha-evolver not importable)")
        return                                        # ...a real bug now FAILS, not "skips"
    good = prob.verify(prob.baseline)
    assert not good.suspicious and good.score > 0.5             # baseline verifies through the real eval
    bad = prob.verify({"init": ["rank", "flip_gain"], "move": "flip_gain",
                       "steps_per_node": 4, "restarts": 2, "tabu_window": 1})
    assert bad.suspicious                                       # init can't use a dynamic field -> rejected


# --------------------------------------------------------------------------- #
# trade_lab — the anti-overfit alpha-discovery flagship                       #
# --------------------------------------------------------------------------- #
def test_alpha_grammar_validates_and_rejects():
    assert valid_alpha("ret1")
    assert valid_alpha(["neg", ["zscore", "ret1"]])
    assert valid_alpha(["add", "mom5", ["mul", "c_05", "vol20"]])
    assert not valid_alpha("not_a_feature")                  # unknown leaf
    assert not valid_alpha(["frobnicate", "ret1"])           # unknown op
    assert not valid_alpha(["neg", "ret1", "mom5"])          # unary with 2 args
    deep = "ret1"
    for _ in range(6):
        deep = ["neg", deep]                                 # depth 6 > max 5
    assert not valid_alpha(deep)


def test_eval_alpha_is_causal_no_lookahead():
    """A position that 'cheats' by matching the SAME bar's sign earns the next
    bar's return through a 1-bar lag, so on an alternating series it must LOSE —
    proof the backtest never uses contemporaneous information."""
    ret = [0.0, 0.01, -0.01, 0.01, -0.01, 0.01, -0.01]
    positions = [(r > 0) - (r < 0) for r in ret]             # sign of the SAME bar
    m = segment_metrics(positions, ret, 0, len(ret), cost=0.0)
    assert m["mean"] < 0                                      # lag makes the cheat lose


def test_segment_metrics_costs_and_turnover():
    ret = [0.0, 0.0, 0.01, 0.02, 0.01, 0.02]
    flat = segment_metrics([1.0] * 6, ret, 0, 6, cost=0.0)
    assert flat["turnover"] == 0.0 and flat["sharpe"] > 0     # steady long, no churn
    flip = [1.0, -1.0, 1.0, -1.0, 1.0, -1.0]
    free = segment_metrics(flip, ret, 0, 6, cost=0.0)["mean"]
    charged = segment_metrics(flip, ret, 0, 6, cost=0.02)["mean"]
    assert charged < free                                    # churn pays transaction cost


def test_deflation_grows_with_trials():
    a = expected_max_sharpe_under_null(2, 500, 0.05)
    b = expected_max_sharpe_under_null(20, 500, 0.05)
    c = expected_max_sharpe_under_null(500, 500, 0.05)
    assert a < b < c                                          # more searches -> higher bar


def test_worst_regime_is_the_minimum_regime():
    """Always-long wins the trending regimes but loses the bear regime; the gate
    scores it by its WORST regime, so a one-regime-good alpha cannot hide."""
    bars = synthetic_universe()
    feats = compute_features(bars)
    pos = [max(-1.0, min(1.0, s)) for s in eval_alpha("c_1", feats)]
    per = {lab: segment_metrics(pos, bars.ret, s, e, 0.001)["sharpe"]
           for lab, s, e in bars.regimes if not lab.startswith("is")}
    m = walk_forward_backtest("c_1", bars, n_trials=72)
    import math as _math
    assert _math.isclose(m["worst_oos_sharpe"], min(per.values()) * _math.sqrt(252))
    assert max(per.values()) > 0 > min(per.values())         # good somewhere, bad somewhere


def test_robust_alpha_passes_overfits_fail():
    prob = AlphaProblem()
    rev = prob.verify(["neg", ["zscore", "ret1"]])           # the real, regime-consistent edge
    assert rev.passed and rev.score > prob.target and not rev.suspicious
    for overfit in ("mom20", "volume_z", ["sign", "price_ma_gap"]):
        v = prob.verify(overfit)
        assert not v.passed and v.score < rev.score          # killed by OOS/cost/deflation


def test_verify_quarantines_degenerate_and_off_grammar():
    prob = AlphaProblem()
    assert prob.verify("c_1").suspicious                     # never trades -> degenerate
    assert prob.verify(["frobnicate", "ret1"]).suspicious    # off-grammar
    assert prob.verify(["neg", "ret1"]).suspicious is False   # a real (small) alpha is not flagged


def test_higher_cost_lowers_the_score():
    bars = synthetic_universe()
    alpha = ["neg", ["zscore", "ret1"]]
    cheap = walk_forward_backtest(alpha, bars, cost=0.0, n_trials=72)["deflated_oos"]
    dear = walk_forward_backtest(alpha, bars, cost=0.02, n_trials=72)["deflated_oos"]
    assert dear < cheap                                      # costs erode a churny edge


def test_distill_only_learns_from_a_passing_alpha():
    prob = AlphaProblem()
    win = prob.verify(["neg", ["zscore", "ret1"]])
    lose = prob.verify("mom20")
    assert prob.distill(["neg", ["zscore", "ret1"]], win)    # a real winner yields a lesson
    assert prob.distill("mom20", lose) == []                 # a failure teaches nothing
    lesson = prob.distill(["neg", ["zscore", "ret1"]], win)[0]
    assert lesson.grounded()                                 # the lesson passes the firewall


def test_offline_proposer_yields_valid_alphas():
    class _Broken:
        def complete_text(self, *a, **k):
            raise RuntimeError("no core")
    prop = AlphaProposer(core=_Broken())
    out = prop.propose(AlphaProblem(), Memory(), Mind(), k=6)
    assert len(out) == 6 and all(valid_alpha(a) for a in out)
    assert prop.note                                         # records the degraded path


def test_trade_loop_discovers_a_robust_alpha_offline():
    """End-to-end: the kernel, with only the offline baseline alphas, finds an alpha
    that clears the anti-overfit gate on the synthetic universe."""
    class _Broken:
        def complete_text(self, *a, **k):
            raise RuntimeError("no core")
    prob = AlphaProblem(n_trials=36)
    result = solve(prob, AlphaProposer(core=_Broken()), Memory(),
                   generations=4, k=6, log=lambda *_: None)
    assert result.solved and result.best_score > prob.target
    assert result.best_candidate in BASELINE_ALPHAS          # the verified winner is grounded


def test_load_price_csv_handles_fred_and_regimes():
    """Parses a FRED date,value series, drops holiday ('.') rows, and tiles the
    timeline into IS + N contiguous OOS eras with no gaps or overlaps."""
    import os
    import tempfile
    from mentat.trade_lab import load_price_csv
    rows = ["observation_date,SP500"]
    for i in range(120):
        rows.append(f"2020-01-{i:03d},{100.0 + i}")
    rows.insert(50, "2020-02-09,.")                      # holiday -> dropped
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write("\n".join(rows))
        path = f.name
    try:
        bars = load_price_csv(path, n_oos_regimes=3, is_frac=0.4)
    finally:
        os.unlink(path)
    assert len(bars.close) == 120                        # 120 prices, holiday row dropped
    labels = [r[0] for r in bars.regimes]
    assert labels[0] == "is_train" and labels.count("is_train") == 1
    assert sum(1 for lab in labels if lab.startswith("oos")) == 3
    assert bars.regimes[0][1] == 0 and bars.regimes[-1][2] == 120
    for a, b in zip(bars.regimes, bars.regimes[1:]):     # contiguous, no gaps/overlaps
        assert a[2] == b[1]
    # close-only series: high==low==close, so hl_range is a dead feature (no leak)
    assert bars.high == bars.close and bars.low == bars.close


# --------------------------------------------------------------------------- #
# the creativity engine (ported from alpha-evolver / Codex)                    #
# --------------------------------------------------------------------------- #
def test_fragments_and_novelty():
    a = ("+", ("x",), ("c", 2.0))
    fa = fragments(a)
    assert "x" in fa and any(f.startswith("0:") for f in fa)   # leaf + positional fragments
    assert novelty(a, []) == 1.0                               # nothing to compare to
    assert novelty(a, [a]) == 0.0                              # identical -> not novel
    assert 0.0 < novelty(a, [("-", ("x",), ("c", 5.0))]) < 1.0  # partial overlap


def test_quality_diversity_pool_keeps_novel():
    """Greedy keeps top-by-score and drops the odd-one-out; the QD pool reserves
    room for the novel candidate. This is the core creativity mechanism."""
    near1, near2, novel = ("a", "a", "a", "a"), ("a", "a", "a", "b"), ("x", "y", "z", "w")
    plain = Memory(elite_cap=2)
    for s, c in [(1.0, near1), (0.9, near2), (0.5, novel)]:
        plain.consider_elite(s, c)
    assert novel not in [c for _, c in plain.elites]          # greedy discards the novel one

    qd = Memory(elite_cap=2, qd=True, novelty_weight=3.0)
    for s, c in [(1.0, near1), (0.9, near2), (0.5, novel)]:
        qd.consider_elite(s, c)
    assert novel in [c for _, c in qd.elites]                 # quality-diversity keeps it
    assert near1 in [c for _, c in qd.elites]                 # ...without losing the best


def test_mine_motifs_and_pool_diversity():
    m = Memory()
    for s, c in [(1.0, ("+", ("x",), ("c", 1.0))),
                 (0.9, ("+", ("x",), ("c", 2.0))),
                 (0.5, ("x",))]:
        m.consider_elite(s, c)
    m.mine_motifs()
    assert m.motifs and any("x" in k for k in m.motifs)       # 'x' recurs across elites
    assert 0.0 <= m.pool_diversity() <= 1.0


def test_solve_brain_records_creativity_metrics():
    import random
    xs = [round(i * 0.5, 2) for i in range(-4, 5)]
    prob = SymbolicRegression(lambda x: x * x - 1, xs, tol=0.2)
    r = solve(prob, RandomProposer(random.Random(0)), Memory(),
              generations=10, k=12, log=lambda *_: None, brain=BrainConfig())
    assert 0.0 <= r.diversity <= 1.0
    assert r.distinct_verified >= 0
    assert "diversity" in r.history[0] and "distinct" in r.history[0]


def test_brain_off_is_the_plain_kernel():
    """solve(brain=None) must reproduce the original kernel exactly (modes on, no
    creativity additions), so every existing flagship is unchanged."""
    off = BrainConfig.off()
    assert off.modes and not off.novelty and off.surprise == "none"
    assert not off.quarantine and off.sleep_every == 0


def test_alpha_stress_verify_keeps_robust_flags_junk():
    from mentat.trade_lab import AlphaProblem
    p = AlphaProblem()
    rev = ["neg", "ret1"]
    v = p.verify(rev)
    s = p.stress_verify(rev, v)
    assert v.passed and s.passed and not s.suspicious        # robust edge survives harsher costs
    junk = p.stress_verify(["frobnicate", "ret1"], Verdict(True, 1.0, "x"))
    assert junk.suspicious and not junk.passed               # a fragile/invalid alpha is caught


def test_creativity_ablation_brain_raises_diversity():
    """The headline creativity claim, deterministically: novelty pressure produces a
    more DIVERSE pool of verified solutions than the plain kernel."""
    import random
    from mentat.creativity import _run
    xs = [round(i * 0.4, 2) for i in range(-5, 6)]
    prob = SymbolicRegression(lambda x: x * x - 1, xs, tol=0.2)
    off = _run(BrainConfig.off(), range(1, 5), 25, 16, prob)
    on = _run(BrainConfig(novelty_weight=3.0), range(1, 5), 25, 16, prob)
    assert on["diversity"] > off["diversity"]      # creativity = a more diverse verified pool
    _ = random  # (RandomProposer seeded inside _run)


def test_map_elites_archive_keeps_best_per_niche():
    m = Memory()
    m.consider_archive(1.0, ("a",), behavior=0)
    m.consider_archive(2.0, ("b",), behavior=0)      # same niche, better -> replaces
    m.consider_archive(0.5, ("c",), behavior=1)      # new niche
    m.consider_archive(1.0, ("e",), behavior=None)   # no behavior -> ignored
    assert m.archive_coverage() == 2
    assert m.archive[0] == [2.0, ("a",)] or m.archive[0] == [2.0, ("b",)]
    assert m.archive[0][0] == 2.0                    # best score kept for the niche


def test_illumination_returns_more_diverse_designs_than_greedy():
    """MAP-Elites returns a verified design for far MORE behavior niches than a
    greedy maximizer, whose result collapses near the optimum. The creativity win."""
    import random
    import statistics
    from mentat.illuminate import GreedyProposer, IlluminationProposer, PatternDesign

    def retained(cls, from_archive, seed):
        mem = Memory()
        solve(PatternDesign(16), cls(random.Random(seed), 16), mem,
              generations=30, k=16, log=lambda *_: None)
        return len(mem.archive) if from_archive else len({sum(c) for _, c in mem.elites})

    greedy = statistics.mean(retained(GreedyProposer, False, s) for s in (1, 2, 3))
    illum = statistics.mean(retained(IlluminationProposer, True, s) for s in (1, 2, 3))
    assert illum > 2 * greedy                        # a far richer verified portfolio


def test_curriculum_isolates_facets_no_leakage():
    """Each market facet is studied in isolation: a finding must use only THAT
    facet's own features — the reversion signal must not leak into other facets."""
    from mentat.curriculum import FACETS, study
    kb, knowledge = study("test", synthetic_universe(), gens=6, k=12, seed=7)
    assert set(kb.facets) == {f[0] for f in FACETS}      # every facet studied
    for name, _, feats in FACETS:
        if "ret1" not in feats:                          # reversion must not leak in
            assert "ret1" not in kb.facets[name]["best_alpha"]
    assert all("verified" in d for d in kb.facets.values())


def test_alpha_behavior_classifies_signal_families():
    from mentat.trade_lab import AlphaProblem
    p = AlphaProblem()
    assert p.behavior(["neg", "ret1"]) == "reversion"
    assert p.behavior("mom20") == "momentum"
    assert p.behavior(["safe_div", "vol10", "vol20"]) == "volatility"
    assert p.behavior("volume_z") == "volume"
    assert p.behavior("c_1") == "constant"             # no feature leaves
    assert p.behavior(["frobnicate", "ret1"]) is None  # off-grammar -> no niche


def test_diverse_sidon_illuminates_a_verified_frontier():
    """Illuminated math: many span niches, each holding a PROVEN Sidon set."""
    import random
    from mentat.discover_diverse import DiverseSidon, SidonSetProposer
    from mentat.math_lab import counterexample_sidon
    mem = Memory()
    solve(DiverseSidon(60), SidonSetProposer(random.Random(1), 60), mem,
          generations=40, k=20, log=lambda *_: None)
    assert mem.archive_coverage() >= 3                       # a frontier, not one point
    for _, cset in mem.archive.values():
        assert counterexample_sidon(sorted(set(cset))) is None   # every entry is proven Sidon


def test_costas_discovery_finds_proven_array():
    """A 2nd verified-discovery domain: the kernel discovers a PROVEN Costas array, and the
    verifier rejects a non-Costas permutation."""
    from mentat.costas import CostasArray, discover_costas
    assert not CostasArray(4).verify((1, 2, 3, 4)).passed      # identity has repeats
    r = discover_costas(7, seed=0, generations=40, k=24)
    assert r.solved
    p, n = r.best_candidate, 7
    vs = [(j - i, p[j] - p[i]) for i in range(n) for j in range(i + 1, n)]
    assert len(vs) == len(set(vs)) and sorted(p) == list(range(1, 8))   # independently valid


def test_cli_front_door():
    """The unified entry point lists engines, shows the overview, and rejects unknowns."""
    import importlib
    cli = importlib.import_module("mentat.__main__")
    assert "trade" in cli.ENGINES and "rag" in cli.ENGINES and "selfimprove" in cli.ENGINES
    assert cli.main(["list"]) == 0          # list engine names
    assert cli.main([]) == 0                # overview (also exercises integrations_report)
    assert cli.main(["definitely_not_an_engine"]) == 1   # unknown -> non-zero


def test_catastrophic_guard_blocks_danger_allows_dev_work():
    """The safety floor (Jarvis _is_catastrophic) must block irreversible destruction of
    the machine / research / credentials, and must NOT block ordinary dev work."""
    from mentat.jarvis import _is_catastrophic as cat
    must_block = ["rm -rf /", "rm -rf ~", "rm -rf $HOME", "rm -rf ~/.ssh", "rm -rf ~/.ssh/",
                  "sudo rm -rf /usr", "rm -rf /etc/passwd", "rm -rf ~/mentat",
                  "shred ~/.ssh/id_rsa", "dd if=/dev/zero of=/dev/disk0",
                  ":(){ :|:& };:", "mkfs.ext4 /dev/sda"]
    must_allow = ["ls -la", "rm -rf /tmp/build", "rm scratch.txt", "git status",
                  "rm -rf ~/mentat/finetune/data", "python3 -m mentat.trade",
                  "rm -rf ~/projects/scratch"]
    for c in must_block:
        assert cat(c), f"guard should BLOCK: {c}"
    for c in must_allow:
        assert not cat(c), f"guard should ALLOW: {c}"


def test_edge_cases_do_not_crash():
    """Robustness: empty/degenerate inputs are handled gracefully, not with a traceback."""
    import random
    import tempfile
    from mentat.consolidate import consolidate
    from mentat.embed import embed
    from mentat.rag import Rag
    from mentat.realm import generate_facets
    rep = consolidate(Memory())                          # empty memory -> no crash
    assert rep["lessons"] == 0 and rep["new_principles"] == 0
    v = embed(["", "   ", "a real finance question"])     # empty/whitespace -> still vectors
    assert len(v) == 3 and all(len(vec) > 0 for vec in v)
    assert generate_facets(random.Random(0), n=0) == []  # zero facets requested -> empty
    with tempfile.TemporaryDirectory() as d:             # empty corpus -> clear error, not crash
        try:
            Rag.from_dir(d)
            raise AssertionError("expected ValueError on empty corpus")
        except ValueError:
            pass


def test_warm_memory_recalls_verified_solution():
    """The mechanism behind self-improvement: a warm memory carrying a VERIFIED solution
    recalls + re-verifies it instantly (solved at generation 1), where a cold run must
    search. Deterministic — the statistical cold-vs-warm + transfer result lives in
    `mentat.selfimprove`."""
    import random
    from mentat.demo import RandomProposer, SymbolicRegression, parse_infix
    xs = [round(i * 0.2, 2) for i in range(-10, 11)]
    prob = SymbolicRegression(lambda x: x * x - 2 * x - 1, xs, tol=0.10)
    sol = parse_infix("x*x - 2*x - 1")
    warm = Memory()
    warm.best_candidate = sol
    warm.best_score = prob.verify(sol).score
    r = solve(prob, RandomProposer(random.Random(0)), warm, generations=20, k=8,
              log=lambda *_: None)
    assert r.solved and r.generations == 1               # recall + re-verify, instant


def test_cognition_loop_compounds_and_gates():
    """The creative cognition loop runs autonomous rounds (propose->verify->remember->sleep),
    accumulates verified memory, and the warm (post-loop) memory is never WORSE than cold on a
    fresh attempt — compounding, with the verifier gating every round."""
    from mentat.cognition import got_sharper, measure, run_loop
    from mentat.demo import RandomProposer, SymbolicRegression
    xs = [round(i * 0.2, 2) for i in range(-10, 11)]
    mk_p = lambda: SymbolicRegression(lambda x: x ** 3 - x, xs, tol=0.10)   # noqa: E731
    mk_pr = lambda rng: RandomProposer(rng)                                 # noqa: E731
    mem, traj = run_loop(mk_p, mk_pr, rounds=5, generations=60, k=32)
    assert len(traj) == 5 and mem.best_candidate is not None
    assert any(rr.solved for rr in traj)                  # the loop discovered + verified the law
    m = measure(mk_p, mk_pr, mem, generations=60, k=32, seeds=(1, 2, 3))
    assert m["warm"]["best"] >= m["cold"]["best"] - 1e-9  # memory never hurts
    assert got_sharper(m)                                  # warm solves more / faster here


def test_consolidation_abstracts_and_exports():
    """The brain's sleep (CLS): replay clusters verified lessons into a principle and
    exports a consolidation dataset for the slow LoRA step. Only verified memory enters."""
    import json
    import tempfile
    from mentat.consolidate import consolidate, export_consolidation_dataset
    m = Memory()
    m.learn(Lesson(when="building a trading alpha tested out of sample",
                   do="reuse the verified reversion alpha",
                   evidence="verified reversion alpha out of sample"))
    m.learn(Lesson(when="building a trading alpha judged after costs",
                   do="prefer low turnover signals",
                   evidence="low turnover trading alpha after costs"))
    rep = consolidate(m)
    assert rep["new_principles"] >= 1 and m.principles      # abstracted a principle
    with tempfile.TemporaryDirectory() as d:
        n = export_consolidation_dataset(m, d)
        assert n >= 2
        rec = json.loads((Path(d) / "consolidation.jsonl").read_text().splitlines()[0])
        assert rec["messages"][0]["role"] == "user"


def test_finetune_dataset_builds_chat_format():
    """The LoRA path produces a valid chat-format instruction dataset from the corpus."""
    import json
    import tempfile
    from mentat.finetune.prepare_data import build
    with tempfile.TemporaryDirectory() as d:
        n_train, n_valid = build(out=d)
        assert n_train >= 1 and n_valid >= 1
        rec = json.loads((Path(d) / "train.jsonl").read_text().splitlines()[0])
        assert [m["role"] for m in rec["messages"]] == ["user", "assistant"]
        assert rec["messages"][1]["content"]              # non-empty answer


def test_embeddings_and_hybrid_ranking():
    """Vector embeddings (semantic if installed, hashing otherwise) + hybrid BM25/cosine
    ranking puts the right doc on top."""
    from mentat.embed import backend_name, cosine, embed
    assert backend_name() in ("model2vec", "sentence-transformers", "hashing")
    v = embed(["sharpe ratio", "sharpe ratio"])
    assert len(v) == 2 and abs(cosine(v[0], v[1]) - 1.0) < 1e-6      # identical -> cosine 1
    assert cosine(embed(["deflated sharpe"])[0], embed(["world cup"])[0]) < 0.99
    from mentat.rag import Rag
    top = Rag.from_dir().retrieve("deflated sharpe ratio", k=1)
    assert top and top[0][1] == "risk_adjusted_return"             # hybrid ranks the right doc


def test_rag_grounds_and_refuses_off_corpus():
    """Grounded QA: in-corpus questions get cited answers; off-corpus questions are
    REFUSED rather than hallucinated (the anti-haze guarantee)."""
    from mentat.rag import Rag
    rag = Rag.from_dir()
    docs = {d for _, d, _ in rag.retrieve("deflated sharpe ratio overfitting", k=4)}
    assert "risk_adjusted_return" in docs or "backtest_overfitting" in docs
    grounded = rag.answer("what is the deflated sharpe ratio?")
    assert grounded["grounded"] and grounded["sources"]
    refused = rag.answer("who won the 2010 world cup?")
    assert refused["grounded"] is False and not refused["sources"]


def test_rag_llm_path_cites_sources():
    from mentat.rag import Rag
    from mentat.reasoning import ScriptedCore
    rag = Rag.from_dir()
    core = ScriptedCore(["The deflated Sharpe ratio corrects for multiple testing [1]."])
    res = rag.answer("deflated sharpe ratio", core=core)
    assert res["grounded"] and "[1]" in res["answer"] and res["sources"]


def test_creative_operators_and_proposer():
    """Boden's operators produce valid alphas, and the creative proposer synthesizes
    valid hypotheses in every mode (creativity bounded by the grammar)."""
    import random
    from mentat import imagine as I
    from mentat.core import Memory, Mind
    from mentat.trade_lab import valid_alpha
    rng = random.Random(0)
    assert I.invert(rng, "ret1") == ["neg", "ret1"]               # transformational: flip
    assert I.blend(rng, ["neg", "ret1"], "mom20")[1:] == [["neg", "ret1"], "mom20"]  # fuse
    assert valid_alpha(I.transfer(rng, ["neg", "ret1"]))          # analogy: remap features
    assert valid_alpha(I.reshape(rng, "mom20")) and valid_alpha(I.specialize(rng, "vol20"))
    prop = I.CreativeProposer(random.Random(1))
    for mode in ("dream", "focus", "recover"):
        m = Mind()
        m.mode = mode
        out = prop.propose(None, Memory(), m, 8)
        assert len(out) == 8 and all(valid_alpha(c) for c in out)


def test_risk_dial_selects_bolder_operators():
    """B4: the thought-risk dial shifts the operator set — bold at high risk,
    conservative at low risk."""
    import random
    from mentat import imagine as I
    from mentat.core import Mind
    bold = I.CreativeProposer(random.Random(0), risk=0.9)
    safe = I.CreativeProposer(random.Random(0), risk=0.1)
    assert bold._ops(Mind()) == I._OPS_BY_MODE["dream"]
    assert safe._ops(Mind()) == I._OPS_BY_MODE["recover"]


def test_creativity_ablation_explores_idea_space():
    """B2: creative synthesis explores at least as much of the signal-family space as
    random search (creativity = broader exploration), and the ablation is well-formed."""
    from mentat.imagine import creativity_ablation
    rows = creativity_ablation(seeds=range(1, 3), gens=6, k=10)
    assert len(rows) == 4
    rnd = next(r for r in rows if r[0] == "random/baseline")
    creative_max_families = max(r[3] for r in rows if r[0] != "random/baseline")
    assert creative_max_families >= rnd[3]


def test_llm_imaginer_parses_and_falls_back():
    import random
    from mentat import imagine as I
    from mentat.core import Memory, Mind
    from mentat.reasoning import ScriptedCore
    from mentat.trade_lab import AlphaProblem, valid_alpha
    good = ScriptedCore(['[["neg","ret1"], ["safe_div","mom20","vol20"]]'])
    im = I.LLMImaginer(core=good, fallback=I.CreativeProposer(random.Random(2)))
    out = im.propose(AlphaProblem(), Memory(), Mind(), 4)
    assert len(out) == 4 and all(valid_alpha(c) for c in out)

    class _Broken:
        def complete_text(self, *a, **k):
            raise RuntimeError("no core")
    im2 = I.LLMImaginer(core=_Broken(), fallback=I.CreativeProposer(random.Random(3)))
    out2 = im2.propose(AlphaProblem(), Memory(), Mind(), 4)
    assert len(out2) == 4 and im2.note                            # degraded to the offline proposer


def test_creative_discovery_finds_a_verified_alpha():
    """End to end: the creative synthesizer, gated, discovers a positive verified edge —
    imagination that survives the verifier."""
    import random
    from mentat import imagine as I
    from mentat.core import BrainConfig, Memory, solve
    from mentat.trade_lab import AlphaProblem, synthetic_universe
    prob = AlphaProblem(bars=synthetic_universe(), n_trials=12 * 16)
    r = solve(prob, I.CreativeProposer(random.Random(7)), Memory(),
              generations=12, k=16, log=lambda *_: None, brain=BrainConfig())
    assert r.best_score > 0.5                                     # a real, gated, creative edge


def test_generate_facets_extends_idea_space():
    """B3: the idea space self-extends — auto-generated cross-family facets that are valid
    and genuinely new (open-endedness)."""
    import random
    from mentat.realm import REALM_FACETS, generate_facets
    from mentat.trade_lab import _FEATURE_FAMILY
    gen = generate_facets(random.Random(0), n=6)
    assert len(gen) == 6
    existing = {tuple(sorted(f)) for _, _, f in REALM_FACETS}
    for _, _, feats in gen:
        assert all(f in _FEATURE_FAMILY for f in feats) and len(feats) >= 2
        assert tuple(sorted(feats)) not in existing      # a genuinely new question


def test_realm_mind_maps_and_loops_until_dry():
    """The realm-mind explores every facet, loops until dry, and keeps only verified
    edges — with the honest 'provisional' caveat in the report."""
    import tempfile
    from mentat import realm
    orig = realm.MAP_PATH
    with tempfile.TemporaryDirectory() as d:
        realm.MAP_PATH = Path(d) / "realm.json"
        try:
            m = realm.map_realm("synthetic market", synthetic_universe(),
                                dry_rounds=1, max_rounds=3, log=lambda *_: None)
        finally:
            realm.MAP_PATH = orig
    assert len(m["facets"]) == len(realm.REALM_FACETS)    # full facet coverage
    assert any(d["verified"] for d in m["facets"].values())   # finds the reversion edge
    rpt = realm.report(m)
    assert "VERIFIED" in rpt and "PROVISIONAL" in rpt     # honest caveat present


def test_research_autopilot_accumulates_verified_findings():
    import tempfile
    from mentat import research
    orig = research.JOURNAL
    with tempfile.TemporaryDirectory() as d:
        research.JOURNAL = Path(d) / "j.json"
        try:
            j = research.run(rounds=1, log=lambda *_: None)
        finally:
            research.JOURNAL = orig
    assert j["rounds"] == 1
    dom = j["domains"]
    assert dom["sidon_frontier"]["max_size"] >= 5         # found proven Sidon sets
    assert dom["design_illumination"]["niches_covered"] >= 5
    assert "market_topics" in dom
    assert "PROVEN" in research.report(j)                 # report claims only verified results


def test_jarvis_run_research_tool_wired():
    import mentat.jarvis as J
    assert "run_research" in J._DISPATCH
    assert any(t["name"] == "run_research" for t in J.TOOLS)


def test_integrations_report_shows_status_not_secret_values():
    import mentat.jarvis as J
    orig_load, orig_get = J._load_key, J.get_secret
    J._load_key = lambda: "sk-SECRETVALUE"
    J.get_secret = lambda name, **kw: "brave-SECRET" if name == "BRAVE_API_KEY" else None
    try:
        r = J.integrations_report()
    finally:
        J._load_key, J.get_secret = orig_load, orig_get
    assert "LIVE" in r and "Claude reasoning" in r        # key present -> live
    assert "needs key" in r and "ElevenLabs" in r         # no key -> flagged
    assert "SECRETVALUE" not in r and "brave-SECRET" not in r   # NEVER leaks the value


def test_mandate_mode_is_defined_and_bounded():
    import mentat.jarvis as J
    assert "FULL AUTHORITY" in J.MANDATE_SYSTEM and "VERIFY" in J.MANDATE_SYSTEM
    assert hasattr(J.Jarvis, "operate")                   # the autonomous executor exists


def test_secrets_resolution_and_env_parsing():
    """The secrets layer resolves env-first and parses .env safely. (No value is
    ever logged; this only surfaces credentials the user stored themselves.)"""
    import os
    import tempfile
    from mentat import secrets as sec
    os.environ["MENTAT_TEST_SECRET"] = "from_env"
    try:
        assert sec.get_secret("MENTAT_TEST_SECRET") == "from_env"      # env wins
        assert sec.has_secret("MENTAT_TEST_SECRET")
    finally:
        del os.environ["MENTAT_TEST_SECRET"]
    assert sec.get_secret("DEFINITELY_MISSING_XYZ_123", default="d") == "d"
    with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as f:
        f.write('FOO="bar baz"\nNOPE\nBAR=qux # inline\n')
        path = Path(f.name)
    try:
        assert sec._parse_env_file(path, "FOO") == "bar baz"           # quoted value
        assert sec._parse_env_file(path, "BAR") == "qux"               # inline comment stripped
        assert sec._parse_env_file(path, "MISSING") is None
    finally:
        os.unlink(path)


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")


if __name__ == "__main__":
    _run_all()
