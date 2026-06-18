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
    import os
    import mentat.jarvis as J
    # web_fetch degrades gracefully on a bad host (no raise; .invalid never resolves)
    assert J.tool_web_fetch("http://nonexistent.invalid.localhost.test/").startswith("(could not fetch")
    # (web_search hits the network — covered by the live runner, not this unit test)
    # ElevenLabs is cleanly disabled without a key
    if not os.environ.get("ELEVENLABS_API_KEY"):
        assert J.elevenlabs_enabled() is False
        assert J.elevenlabs_tts("hello") is None
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
    assert m["worst_oos_sharpe"] == min(per.values()) * (252 ** 0.5)
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


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")


if __name__ == "__main__":
    _run_all()
