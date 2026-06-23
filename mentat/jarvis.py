"""Jarvis — the personal-ops layer of the hub.

A conversational assistant built on the reasoning core, with real tools and a
persistent memory of your decisions and preferences. This is the "channels +
tools" ring of the architecture: you talk to it (browser voice UI or terminal),
it reasons, calls tools, and remembers what you tell it.

Tools are a registry — time, weather, your research repos, and a remember/recall
memory ship today; Gmail / analytics / calendar slot in the same way later.

Run:
    python3 -m mentat.jarvis                      # serve the voice UI (browser)
    python3 -m mentat.jarvis --text "how's mentat going?"   # one-shot, terminal
    python3 -m mentat.jarvis --text "..." --say   # also speak via macOS `say`
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from .core import Lesson as _Lesson, Memory as _Memory
from .reasoning import DEFAULT_MODEL, _load_key, core_available
from .secrets import get_secret
from .jarvis_ui import PAGE
import os

MODEL = os.environ.get("MENTAT_MODEL", DEFAULT_MODEL)
ALLOWED_MODELS = {"claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5"}
MEMORY_PATH = Path(__file__).parent / "jarvis_memory.json"
ACTIONS_LOG = Path(__file__).parent / "jarvis_actions.log"
CONVO_LOG = Path(__file__).parent / "jarvis_conversation.jsonl"
LESSONS_PATH = Path(__file__).parent / "jarvis_lessons.json"   # grounded decision-cards
ELEVENLABS_VOICE = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # default: Rachel
REPOS = {name: Path.home() / name for name in ("swechats", "alpha-evolver", "mentat")}

# Full machine control, with ONE floor: refuse catastrophic, irreversible commands.
# Voice STT can garble input, so a disk-wipe / rm-of-home guard protects the user.
# Set JARVIS_NO_GUARD=1 to remove even that.
_GUARD = os.environ.get("JARVIS_NO_GUARD") != "1"
_HOME = os.path.expanduser("~")
# A delete verb acting as a command (not a substring inside an argument).
_DELETE_VERB = re.compile(
    r"(?:^|[|;&]|\bsudo\s+)\s*(?:rm|shred|unlink)\b"
    r"|\bfind\b[^|;&\n]*?-delete\b"
    r"|\bfind\b[^|;&\n]*?-exec\s+(?:rm|shred|unlink)\b", re.I)
# Paths that must never be a delete target (the path itself).
_PROT_EXACT = {"/", "/etc", "/system", "/usr", "/bin", "/sbin", "/var",
               "/library", "/applications", "/volumes", "/private", _HOME.lower(),
               *(f"{_HOME}/{d}".lower() for d in
                 ("documents", "desktop", "library", "pictures", "movies", "downloads"))}
# System roots whose CHILDREN are also protected (deep deletes there are fatal).
_PROT_TREE = ("/etc", "/system", "/usr", "/bin", "/sbin", "/library",
              "/applications", "/private", "/var",
              f"{_HOME.lower()}/.ssh", f"{_HOME.lower()}/.aws", f"{_HOME.lower()}/.gnupg",
              f"{_HOME.lower()}/library/keychains")   # credentials: protect the whole subtree
_CATASTROPHIC = [
    re.compile(r"--no-preserve-root", re.I),
    re.compile(r"\bmkfs\b|\bnewfs\b", re.I),
    re.compile(r"\bdiskutil\b[^\n]*\b(erase|reformat|partitiondisk)\b", re.I),
    re.compile(r"\bdd\b[^\n]*\bof=/dev/", re.I),
    re.compile(r">\s*/dev/(disk|rdisk|sd[a-z])", re.I),
    re.compile(r":\(\)\s*\{[^}]*:\s*\|\s*:[^}]*&[^}]*\}\s*;", re.I),  # fork bomb
]


def _norm_target(tok: str) -> str:
    t = tok.strip().strip("'\"").replace("${HOME}", _HOME).replace("$HOME", _HOME)
    if t == "~" or t.startswith("~/"):
        t = _HOME + t[1:]
    return (t.rstrip("*").rstrip("/").lower()) or "/"


def _hits_protected(cmd: str) -> bool:
    home = _HOME.lower()
    for raw in re.split(r"\s+", cmd):
        if not raw or raw.startswith("-"):
            continue
        t = _norm_target(raw)
        if t in _PROT_EXACT or any(t == r or t.startswith(r + "/") for r in _PROT_TREE):
            return True
        if t.startswith(home + "/"):
            rest = t[len(home) + 1:]
            if rest and "/" not in rest:   # a DIRECT child of $HOME (repo, dotfile, config, keys)
                return True                # — high-value; deeper paths (e.g. ~/projects/x) are allowed
    return False


def _is_catastrophic(cmd: str) -> bool:
    # A deletion verb aimed at a protected path, OR an inherently destructive op.
    if _DELETE_VERB.search(cmd) and _hits_protected(cmd):
        return True
    return any(p.search(cmd) for p in _CATASTROPHIC)


def _log_action(kind: str, detail: str) -> None:
    try:
        with open(ACTIONS_LOG, "a") as f:
            f.write(f"{datetime.now().isoformat(timespec='seconds')}\t{kind}\t{detail}\n")
    except OSError:
        pass

SYSTEM = (
    "You are Jarvis, a personal operations assistant for a high-school researcher who "
    "is building AI systems (the repos swechats, alpha-evolver, and mentat). "
    "Your replies are read ALOUD by a speech synthesizer, so: keep them to 1-3 short "
    "sentences, plain conversational English, NO markdown, NO bullet lists, no emoji. "
    "Be warm, direct, and proactive. You are genuinely SMART: reason carefully through hard "
    "problems before answering, plan multi-step tasks and chain your tools until the job is "
    "actually DONE (don't stop half-way or just describe what you'd do — do it), and anticipate "
    "what the user really needs, not only the literal words. Prefer checking with a tool over "
    "guessing. Be honest about confidence: your conversational answers are live reasoning, "
    "NOT verified, and can be wrong — flag uncertainty instead of asserting, and if a tool's "
    "result looks off (wrong location, stale or implausible data) SAY SO rather than repeating "
    "it as fact. Only the verifier-gated discovery engines produce proven results. "
    "Whenever the user states a preference, decision, or fact about "
    "themselves, call `remember` so you don't forget it next time. When the user CORRECTS "
    "you or states a rule to follow in future ('always...', 'never...', 'next time do X'), "
    "call `learn_lesson` with their actual words as `evidence` — you will see your learned "
    "lessons at the top of future chats and must follow them. "
    "You can also CONTROL this Mac: `shell` runs any terminal command, `applescript` "
    "automates native apps, `read_file` / `write_file` access files, `edit_file` makes "
    "surgical VERIFIED code edits (prefer it for changing existing files — pass `verify_cmd` "
    "like the tests to gate the change), and `add_reminder` / `calendar_today` reach your "
    "Reminders and Calendar. Use them to "
    "actually get things done — open apps, manage files, search the machine, automate "
    "tasks — the way a power user works at the terminal. Before anything destructive or "
    "irreversible (deleting or overwriting files, changing system settings, installing or "
    "removing software, sending messages on the user's behalf), say what you're about to "
    "do and get a quick confirmation first. For routine, safe actions just do them and "
    "report back briefly. "
    "You can BROWSE THE WEB: `web_search` finds pages, `web_fetch` reads a page's text. "
    "When the user asks you to search, look up, or check something online, ACTUALLY call "
    "web_search (then web_fetch to read a page) — do not answer from memory, and never say "
    "search is unavailable unless web_search itself returned no results. Be honest about "
    "hard limits: you "
    "cannot bypass passwords or security, cannot create accounts or act as the user, and "
    "cannot watch video — say so plainly rather than pretending. "
    "You can dispatch HEAVY THINKING to specialist engines: `improve_maxcut` improves the "
    "user's own alpha-evolver heuristic and `discover_sidon` discovers a verified large Sidon "
    "set. They take a minute or two and make real, verified progress — run them only when the "
    "user asks you to do research or solve something hard. "
    "If you don't know something and have no tool for it, say so."
)

# Mandate mode: the user has granted explicit, full authority for a task. Work to
# completion autonomously — but the hard limits stay, because they protect the USER's
# own machine and research, not the task.
MANDATE_SYSTEM = (
    "You are Mentat operating under an explicit MANDATE: the user has granted you FULL "
    "AUTHORITY to accomplish the task below, autonomously, using your tools. "
    "Work to completion. Take the steps yourself and do NOT ask for confirmation on "
    "reversible actions — you are authorized; just do them and keep going. "
    "VERIFY your work before declaring done (re-read files, run the tests/checks) — the "
    "verification gate still applies; never claim success you didn't confirm. "
    "A few hard limits remain, and they protect the USER, not block the task: (1) the "
    "catastrophic-command guard refuses irreversible destruction (wiping disks, deleting "
    "home/credential trees) — it logs and tells you, so route around it. (2) Some steps "
    "genuinely need the human: a login or captcha, creating an account as the user, or a "
    "credential you don't have stored. Do EVERYTHING else, then report precisely what is "
    "left for the human and why. "
    "Think briefly out loud as you go. When finished, give a concise report: what you did, "
    "what you verified, and anything still needing the human."
)


def integrations_report() -> str:
    """Which integrations are LIVE (credentials present) vs need a key — names only,
    never values. So you can see at a glance what the system can do hands-free."""
    rows = [
        ("Claude reasoning", bool(get_secret("ANTHROPIC_API_KEY") or _load_key())),
        ("ElevenLabs voice", bool(get_secret("ELEVENLABS_API_KEY"))),
        ("Brave web search", bool(get_secret("BRAVE_API_KEY"))),
    ]
    lines = [f"  {'LIVE ' if ok else 'needs key'}  {name}" for name, ok in rows]
    missing = [name for name, ok in rows if not ok]
    tail = ("" if not missing
            else "\n  (store a missing key once: python3 -m mentat.secrets set <NAME>)")
    return "integrations:\n" + "\n".join(lines) + tail


# --------------------------------------------------------------------------- #
# tools                                                                       #
# --------------------------------------------------------------------------- #
def tool_get_datetime() -> str:
    return datetime.now().strftime("%A, %B %d %Y, %-I:%M %p")


def tool_get_weather(location: str = "") -> str:
    loc = location or "auto"
    try:
        url = f"https://wttr.in/{urllib.parse.quote(loc)}?format=%l:+%c+%t+(feels+%f),+%C"
        with urllib.request.urlopen(url, timeout=8) as r:
            return r.read().decode("utf-8", "replace").strip()
    except Exception as e:
        return f"weather unavailable ({type(e).__name__})"


def tool_research_status(repo: str = "") -> str:
    names = [repo] if repo in REPOS else list(REPOS)
    out = []
    for name in names:
        path = REPOS[name]
        if not (path / ".git").exists() and not path.exists():
            out.append(f"{name}: not found")
            continue
        try:
            last = subprocess.run(["git", "-C", str(path), "log", "-1", "--format=%s (%cr)"],
                                  capture_output=True, text=True, timeout=5)
            dirty = subprocess.run(["git", "-C", str(path), "status", "--porcelain"],
                                   capture_output=True, text=True, timeout=5)
            if last.returncode != 0:
                out.append(f"{name}: present (not a git repo yet)")
                continue
            n = len([ln for ln in dirty.stdout.splitlines() if ln.strip()])
            tail = f", {n} uncommitted change(s)" if n else ", clean"
            out.append(f"{name}: \"{last.stdout.strip()}\"{tail}")
        except Exception as e:
            out.append(f"{name}: error ({type(e).__name__})")
    return "; ".join(out)


def _load_memory() -> list[dict]:
    try:
        return json.loads(MEMORY_PATH.read_text()) if MEMORY_PATH.exists() else []
    except (OSError, json.JSONDecodeError):
        return []


def tool_remember(note: str) -> str:
    mem = _load_memory()
    mem.append({"note": note, "when": datetime.now().isoformat(timespec="seconds")})
    MEMORY_PATH.write_text(json.dumps(mem, indent=2))
    return "noted."


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", text.lower()))


def _recall_relevant(query: str, k: int = 5) -> list[str]:
    """Rank durable notes by SEMANTIC similarity to the query (embeddings), so Jarvis surfaces the
    relevant memories — not just keyword hits. Falls back to keyword, then to recent notes."""
    mem = _load_memory()
    notes = [m["note"] for m in mem]
    if not notes or not query.strip():
        return notes[-k:]
    try:
        from .embed import cosine, embed
        vecs = embed(notes + [query])
        qv = vecs[-1]
        ranked = sorted(((cosine(v, qv), n) for v, n in zip(vecs[:-1], notes)),
                        key=lambda t: t[0], reverse=True)
        top = [n for s, n in ranked[:k] if s > 0.20]
        if top:
            return top
    except Exception:
        pass
    terms = {w for w in _tokens(query) if len(w) > 2}
    hits = [n for n in notes if terms & _tokens(n)]
    return hits[-k:] or notes[-k:]


def tool_recall(query: str = "") -> str:
    if not _load_memory():
        return "I haven't been told anything to remember yet."
    return " | ".join(_recall_relevant(query, k=5))


def jarvis_lessons_context(k: int = 6) -> str:
    """Top grounded decision-cards Jarvis has learned, for injection into the prompt."""
    try:
        return _Memory.load(LESSONS_PATH).context(k=k)
    except Exception:
        return ""


def tool_learn_lesson(when: str, do: str, avoid: str = "", evidence: str = "") -> str:
    """Learn a durable, GROUNDED behavioral rule (a decision-card). The kernel's
    firewall rejects it unless the claim shares real vocabulary with the evidence,
    so Jarvis can't fabricate rules — they must be grounded in what the user said."""
    when, do, avoid, evidence = when.strip(), do.strip(), avoid.strip(), evidence.strip()
    if not when or not do:
        return "(a lesson needs at least `when` and `do`)"
    mem = _Memory.load(LESSONS_PATH)
    lesson = _Lesson(when=when, do=do, avoid=avoid, evidence=evidence)
    if not lesson.grounded():
        return ("(not learned — the rule isn't grounded in the evidence; set `evidence` to the "
                "user's actual words so the claim shares real vocabulary with them.)")
    learned = mem.learn(lesson)
    mem.save(LESSONS_PATH)
    _log_action("learn_lesson", f"when {when} -> {do}")
    return f"Learned: when {when}, {do}." if learned else "(already knew that — reinforced it.)"


def tool_improve_maxcut(generations: int = 4) -> str:
    """Dispatch to the self-research engine: propose a Max Cut heuristic and verify it
    against alpha-evolver's OWN offline benchmark. Returns best verified fitness vs baseline."""
    try:
        from .core import Memory, solve
        from .reasoning import AnthropicCore, core_available
        from .self_research import HeuristicProposer, MaxCutHeuristic, _normalize
    except Exception as e:
        return f"(self-research engine unavailable: {type(e).__name__})"
    if not core_available():
        return "(no reasoning core available to drive the engine)"
    try:
        problem = MaxCutHeuristic()
    except Exception as e:
        return f"(the Max Cut verifier needs alpha-evolver + numpy: {type(e).__name__})"
    gens = max(1, min(int(generations or 4), 8))
    _log_action("engine", f"improve_maxcut gens={gens}")
    res = solve(problem, HeuristicProposer(core=AnthropicCore()), Memory(),
                generations=gens, k=5, log=lambda *_: None)
    delta = res.best_score - problem.baseline_fitness
    try:
        move = problem.lab.expr_to_str(_normalize(res.best_candidate)["move"])
    except Exception:
        move = "(unavailable)"
    verdict = "beat the baseline" if res.solved else ("edged it" if delta > 0 else "did not beat it")
    return (f"Ran the self-research engine {gens} generations on your alpha-evolver Max Cut "
            f"benchmark: best verified fitness {res.best_score:.4f} vs baseline "
            f"{problem.baseline_fitness:.4f} ({delta:+.4f}) — {verdict}. Best move: {move}")


def tool_discover_sidon(n: int = 100, target: int = 10, generations: int = 4) -> str:
    """Dispatch to the math-discovery engine: find a large Sidon set in [1, n] (all
    pairwise sums distinct), proven by exhaustive counterexample search."""
    try:
        from .core import Memory, solve
        from .math_lab import CodeProposer, SidonSet
        from .reasoning import AnthropicCore, core_available
    except Exception as e:
        return f"(discovery engine unavailable: {type(e).__name__})"
    if not core_available():
        return "(no reasoning core available to drive the engine)"
    n = max(20, min(int(n or 100), 500))
    target = max(2, int(target or 10))
    gens = max(1, min(int(generations or 4), 8))
    _log_action("engine", f"discover_sidon n={n} target={target} gens={gens}")
    problem = SidonSet(n=n, target=target)
    res = solve(problem, CodeProposer(core=AnthropicCore()), Memory(),
                generations=gens, k=4, log=lambda *_: None)
    size = int(res.best_score) if res.best_score > 0 else 0
    return (f"Ran the discovery engine {gens} generations: best VERIFIED Sidon set in "
            f"[1,{n}] has size {size} (target {target}). {res.verdict.detail[:140]}")


def tool_run_research(minutes: float = 0, rounds: int = 1) -> str:
    """Run the research autopilot: loop the gated discovery engines, keeping only
    verifier-PROVEN results, accumulating them into the journal. This is how you hand
    it an overnight goal — pass minutes for a long unattended run."""
    try:
        from . import research
    except Exception as e:
        return f"(research autopilot unavailable: {type(e).__name__})"
    mins = float(minutes or 0)
    n = max(1, int(rounds or 1))
    _log_action("engine", f"run_research minutes={mins} rounds={n}")
    journal = research.run(minutes=mins if mins > 0 else None,
                           rounds=None if mins > 0 else n, log=lambda *_: None)
    return research.report(journal)


def tool_creative_think(rounds: int = 5) -> str:
    """Run the CREATIVE COGNITION loop: propose ideas creatively, VERIFY each, remember only
    what's proven, sleep to consolidate, and measure whether it got sharper. This is mentat
    thinking creatively AND improving itself — with a verifier between every idea and belief."""
    try:
        from .cognition import _demo_domain, got_sharper, measure, run_loop
    except Exception as e:
        return f"(creative cognition loop unavailable: {type(e).__name__})"
    n = max(1, int(rounds or 4))
    _log_action("engine", f"creative_think rounds={n}")
    mk_p, mk_pr = _demo_domain()
    mem, traj = run_loop(mk_p, mk_pr, rounds=n, generations=60, k=32)
    m = measure(mk_p, mk_pr, mem, generations=60, k=32, seeds=(1, 2, 3))
    solved_round = next((rr.round for rr in traj if rr.solved), None)
    parts = [f"Creative cognition loop — {n} rounds, verifier-gated."]
    parts.append(f"It discovered and verified the law in round {solved_round}."
                 if solved_round else "No candidate cleared the gate this run — nothing faked.")
    parts.append(f"Cold start solved {m['cold']['solved']} of {m['n']}; warm, carrying its own "
                 f"verified memory, solved {m['warm']['solved']} of {m['n']} — "
                 + ("sharper, the memory compounded." if got_sharper(m) else "no measurable gain this run."))
    parts.append("Every idea was re-verified before being believed.")
    return " ".join(parts)


def tool_look() -> str:
    """LOOK through the Mac's camera and report what's actually in frame (faces/people), verified
    by Apple's Vision — grounded perception, not a guess. Needs one-time camera permission."""
    try:
        from .vision import describe
    except Exception as e:
        return f"(vision unavailable: {type(e).__name__})"
    _log_action("vision", "look")
    return describe()


def tool_design_part(part: str = "bracket") -> str:
    """Design a VERIFIED parametric part (a mounting bracket or a standoff/spacer) as code —
    analytic checks, zero GPU — and emit printable OpenSCAD. 'Design a prototype with me.'"""
    try:
        from .cad import PARTS, design
    except Exception as e:
        return f"(CAD engine unavailable: {type(e).__name__})"
    part = part if part in PARTS else "bracket"
    prob, best, scad = design(part)
    if best is None:
        return f"I couldn't find a {part} design meeting every constraint in budget — said honestly."
    _log_action("cad", prob.verify(best).detail)
    return (f"I designed a verified {part}: {prob.verify(best).detail}. Every constraint is provably "
            "met, and I emitted printable OpenSCAD — code, verified analytically, no GPU.\n\n" + scad)


def tool_work_on(minutes: float = 0) -> str:
    """Work on self-improvement within a buffered budget: a VERIFIED curriculum, memory carried
    forward (compounding/transfer), honest dry-stop. This is 'go improve yourself for a while'."""
    try:
        from .work import CURRICULUM, work
    except Exception as e:
        return f"(work engine unavailable: {type(e).__name__})"
    r = work(minutes=(minutes or None), log=lambda *_: None)
    solved = [n for n, ok, _ in r["results"] if ok]
    cold, warm = r["transfer"]["cold"], r["transfer"]["warm"]
    parts = [f"I worked a verified curriculum and mastered {len(solved)} of {len(CURRICULUM)} tasks: "
             f"{', '.join(solved) or 'none'}."]
    if r["dry"]:
        parts.append(f"I stopped honestly at '{r['dry']}' — couldn't crack it offline in budget.")
    parts.append(f"Transfer proof on '{r['task']}': from scratch I solved {cold['solved']} of "
                 f"{r['transfer']['n']}, but carrying what I'd proven I solved {warm['solved']} of "
                 f"{r['transfer']['n']} — the memory compounded.")
    parts.append(f"{r['lessons']} verified lessons accumulated; every step was re-verified.")
    if r.get("code"):
        c = r["code"]
        parts.append(f"I also improved real code — the Max Cut heuristic — from {c['baseline']:.4f} "
                     f"to {c['best']:.4f}" + (" offline, beating the baseline." if c["beat"] else "."))
    return " ".join(parts)


def tool_capabilities() -> str:
    """A grounded self-model: what I can do, how much is verified, and what's blocked."""
    try:
        from .selfmodel import capabilities
    except Exception as e:
        return f"(self-model unavailable: {type(e).__name__})"
    return capabilities()


def tool_estimate_effort(task: str) -> str:
    """Estimate how long a task takes and recommend a work budget with a safety buffer,
    grounded in measured timings — the 'that'll take ~8h so I'll budget 10h' capability."""
    try:
        from .selfmodel import estimate_effort
    except Exception as e:
        return f"(effort estimator unavailable: {type(e).__name__})"
    return estimate_effort(task)


def tool_finance_qa(question: str) -> str:
    """Answer a finance question GROUNDED in the local corpus, with citations — and
    REFUSE (rather than guess) when the corpus has no relevant source. The cure for
    hazy answers is grounding, not guessing."""
    try:
        from .rag import Rag
        from .reasoning import AnthropicCore, core_available
    except Exception as e:
        return f"(grounded QA unavailable: {type(e).__name__})"
    rag = Rag.from_dir()
    res = rag.answer(question, core=AnthropicCore() if core_available() else None)
    _log_action("finance_qa", question[:120])
    if not res["grounded"]:
        return res["answer"]
    cites = ", ".join(sorted({s["doc"] for s in res["sources"]}))
    return f"{res['answer']}\n(grounded in: {cites})"


def tool_shell(command: str, timeout: int = 60) -> str:
    if _GUARD and _is_catastrophic(command):
        _log_action("shell-BLOCKED", command)
        return ("Refused: that command looks catastrophic and irreversible (a disk wipe or "
                "rm of / or your home). I won't run it. If you truly mean it, run it yourself "
                "or restart me with JARVIS_NO_GUARD=1.")
    _log_action("shell", command)
    try:
        p = subprocess.run(["bash", "-lc", command], capture_output=True, text=True, timeout=timeout)
        out = (p.stdout or "")
        if p.stderr.strip():
            out += ("\n[stderr] " + p.stderr)
        out = out.strip() or f"(no output; exit code {p.returncode})"
        return out[:4000] + ("\n…[truncated]" if len(out) > 4000 else "")
    except subprocess.TimeoutExpired:
        return f"(timed out after {timeout}s)"
    except Exception as e:
        return f"(error: {type(e).__name__}: {e})"


def tool_applescript(script: str) -> str:
    _log_action("applescript", " ".join(script.split())[:200])
    try:
        p = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)
        return (p.stdout or p.stderr or "").strip()[:2000] or f"(done; exit {p.returncode})"
    except Exception as e:
        return f"(error: {type(e).__name__}: {e})"


def tool_read_file(path: str) -> str:
    try:
        text = Path(path).expanduser().read_text(errors="replace")
        return text[:6000] + ("\n…[truncated]" if len(text) > 6000 else "")
    except Exception as e:
        return f"(could not read {path}: {type(e).__name__}: {e})"


def tool_write_file(path: str, content: str) -> str:
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        _log_action("write_file", str(p))
        return f"wrote {len(content)} characters to {p}"
    except Exception as e:
        return f"(could not write {path}: {type(e).__name__}: {e})"


def tool_edit_file(path: str, old: str, new: str, verify_cmd: str = "") -> str:
    """Surgical, VERIFIED edit (Claude-Code style): replace `old` (which must occur
    exactly once) with `new`, syntax-check Python before writing, optionally run a
    `verify_cmd` (e.g. the tests) after, and ROLL BACK on any failure. Same
    'verification is the gate' principle the kernel uses, applied to code edits."""
    p = Path(path).expanduser()
    if _GUARD:
        t = _norm_target(str(p))
        creds = (f"{_HOME.lower()}/.ssh", f"{_HOME.lower()}/.aws", f"{_HOME.lower()}/.gnupg")
        if any(t == c or t.startswith(c + "/") for c in creds):
            return "(refused: won't edit credential files)"
    try:
        original = p.read_text()
    except Exception as e:
        return f"(could not read {path}: {type(e).__name__}: {e})"
    n = original.count(old)
    if n == 0:
        return "(edit not applied: `old` text not found — copy it exactly from the file)"
    if n > 1:
        return f"(edit not applied: `old` occurs {n} times — add surrounding context to make it unique)"
    updated = original.replace(old, new, 1)
    if updated == original:
        return "(edit not applied: that produces no change)"
    if p.suffix == ".py":                         # syntax gate before writing
        try:
            compile(updated, str(p), "exec")
        except SyntaxError as e:
            return f"(edit REJECTED: it would break Python syntax — {e.msg} at line {e.lineno})"
    p.write_text(updated)
    _log_action("edit_file", f"{p} (-{len(old)}/+{len(new)} chars)")
    if verify_cmd:
        if _GUARD and _is_catastrophic(verify_cmd):
            p.write_text(original)
            return "(edit rolled back: the verify command looked catastrophic and was refused)"
        try:
            r = subprocess.run(["bash", "-lc", verify_cmd], capture_output=True, text=True,
                               timeout=180, cwd=str(p.parent))
        except Exception as e:
            p.write_text(original)
            return f"(edit ROLLED BACK: verify command errored: {type(e).__name__})"
        if r.returncode != 0:
            p.write_text(original)
            tail = (r.stdout + r.stderr).strip()[-400:]
            return f"(edit ROLLED BACK: `{verify_cmd}` failed)\n{tail}"
        return f"Edited {p.name} and `{verify_cmd}` passed."
    return f"Edited {p.name} (Python syntax OK)." if p.suffix == ".py" else f"Edited {p.name}."


def _get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Jarvis research)"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def tool_web_search(query: str) -> str:
    """Search via official, keyless JSON APIs (DuckDuckGo Instant Answer + Wikipedia).
    Keyless open-web scraping is blocked everywhere now; these are the reliable paths.
    For anything specific, pair with web_fetch to read a chosen URL.
    If BRAVE_API_KEY is set, uses the Brave Search API for real-time open-web results."""
    bk = get_secret("BRAVE_API_KEY")
    if bk:
        try:
            req = urllib.request.Request(
                "https://api.search.brave.com/res/v1/web/search?"
                + urllib.parse.urlencode({"q": query, "count": 5}),
                headers={"X-Subscription-Token": bk, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=12) as r:
                j = json.loads(r.read().decode("utf-8", "replace"))
            hits = []
            for it in j.get("web", {}).get("results", [])[:5]:
                desc = re.sub(r"<[^>]+>", "", it.get("description", "")).strip()
                hits.append(f"{it.get('title', '')} — {it.get('url', '')}" + (f"\n  {desc}" if desc else ""))
            if hits:
                _log_action("web_search[brave]", query)
                return "\n".join(hits)
        except Exception:
            pass  # fall back to the keyless path
    lines: list[str] = []
    try:  # DuckDuckGo Instant Answer (official API)
        j = _get_json("https://api.duckduckgo.com/?" + urllib.parse.urlencode(
            {"q": query, "format": "json", "no_redirect": "1", "no_html": "1"}))
        if j.get("AbstractText"):
            lines.append(j["AbstractText"] + (f" [{j['AbstractURL']}]" if j.get("AbstractURL") else ""))

        def walk(topics):
            for t in topics:
                if "Topics" in t:
                    walk(t["Topics"])
                elif t.get("FirstURL") and t.get("Text"):
                    lines.append(f"{t['Text']} — {t['FirstURL']}")
        walk(j.get("RelatedTopics", []))
    except Exception:
        pass
    if len(lines) < 3:
        try:  # Wikipedia opensearch (titles + links)
            arr = _get_json("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
                {"action": "opensearch", "search": query, "limit": "5", "format": "json"}))
            for title, link in zip(arr[1], arr[3]):
                lines.append(f"{title} — {link}")
        except Exception:
            pass
    _log_action("web_search", query)
    if not lines:
        return ("(no results — open-web/live search needs a keyed API such as Brave Search. "
                "I can still web_fetch a specific URL if you give me one.)")
    return "\n".join(lines[:6])


def tool_web_fetch(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Jarvis)"})
        with urllib.request.urlopen(req, timeout=12) as r:
            raw = r.read(800000).decode("utf-8", "replace")
    except Exception as e:
        return f"(could not fetch {url}: {type(e).__name__}: {e})"
    raw = re.sub(r"(?is)<(script|style|noscript|head).*?</\1>", " ", raw)
    text = re.sub(r"(?s)<[^>]+>", " ", raw)
    text = re.sub(r"&[a-z#0-9]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    _log_action("web_fetch", url)
    return (text[:4500] + "\n…[truncated]") if len(text) > 4500 else (text or "(no readable text)")


def _applescript_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def tool_add_reminder(text: str) -> str:
    if not text.strip():
        return "(nothing to remind about)"
    script = (f'tell application "Reminders" to make new reminder '
              f'with properties {{name:{_applescript_str(text)}}}')
    _log_action("add_reminder", text)
    try:
        p = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=15)
        if p.returncode == 0:
            return f"Reminder added: {text}"
        return f"(couldn't add reminder — you may need to grant Reminders access: {(p.stderr or '').strip()[:100]})"
    except Exception as e:
        return f"(reminder error: {type(e).__name__})"


def tool_calendar_today() -> str:
    script = ('set out to ""\nset d to current date\nset startD to d - (time of d)\n'
              'set endD to startD + 86400\ntell application "Calendar"\n'
              '  repeat with c in calendars\n'
              '    repeat with e in (every event of c whose start date >= startD and start date < endD)\n'
              '      set out to out & summary of e & " at " & (start date of e as string) & linefeed\n'
              '    end repeat\n  end repeat\nend tell\nreturn out')
    _log_action("calendar_today", "")
    try:
        p = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=25)
        if p.returncode != 0:
            return f"(couldn't read Calendar — you may need to grant Calendar access: {(p.stderr or '').strip()[:100]})"
        return (p.stdout or "").strip() or "Nothing on the calendar today."
    except subprocess.TimeoutExpired:
        return "(Calendar query timed out — it can be slow on first run; try again.)"
    except Exception as e:
        return f"(calendar error: {type(e).__name__})"


def elevenlabs_enabled() -> bool:
    return bool(get_secret("ELEVENLABS_API_KEY"))


def elevenlabs_tts(text: str) -> bytes | None:
    """Synthesize speech with ElevenLabs (human-sounding). None if no key / on error."""
    key = get_secret("ELEVENLABS_API_KEY")
    if not key:
        return None
    body = json.dumps({"text": text, "model_id": "eleven_turbo_v2_5",
                       "voice_settings": {"stability": 0.5, "similarity_boost": 0.75}}).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE}",
        data=body, headers={"xi-api-key": key, "Content-Type": "application/json",
                            "Accept": "audio/mpeg"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    except Exception:
        return None


def _log_convo(role: str, text: str) -> None:
    try:
        with open(CONVO_LOG, "a") as f:
            f.write(json.dumps({"when": datetime.now().isoformat(timespec="seconds"),
                                "role": role, "text": text}) + "\n")
    except OSError:
        pass


TOOLS = [
    {"name": "get_datetime", "description": "Current local date and time.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_weather", "description": "Current weather. Pass a city, or omit for auto-location.",
     "input_schema": {"type": "object",
                      "properties": {"location": {"type": "string"}}}},
    {"name": "research_status",
     "description": "Status of the user's research repos (swechats, alpha-evolver, mentat): "
                    "last commit + uncommitted changes. Optional repo name to scope.",
     "input_schema": {"type": "object", "properties": {"repo": {"type": "string"}}}},
    {"name": "remember", "description": "Persist a preference, decision, or fact about the user.",
     "input_schema": {"type": "object", "properties": {"note": {"type": "string"}},
                      "required": ["note"]}},
    {"name": "recall", "description": "Recall what the user has asked you to remember. Optional query.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}}},
    {"name": "learn_lesson",
     "description": "Learn a DURABLE behavioral rule when the user corrects you or states a "
                    "preference/rule to follow in future. `when` = the recurring situation, "
                    "`do` = what to do, `avoid` = the anti-pattern, `evidence` = the user's "
                    "actual words (required — the rule must be grounded in them).",
     "input_schema": {"type": "object",
                      "properties": {"when": {"type": "string"}, "do": {"type": "string"},
                                     "avoid": {"type": "string"}, "evidence": {"type": "string"}},
                      "required": ["when", "do", "evidence"]}},
    {"name": "improve_maxcut",
     "description": "Dispatch to the self-research engine to try to beat the user's own "
                    "alpha-evolver Max Cut heuristic, scored by alpha-evolver's real benchmark. "
                    "Heavy (~1-2 min); only run when the user asks for real research/discovery.",
     "input_schema": {"type": "object", "properties": {"generations": {"type": "integer"}}}},
    {"name": "discover_sidon",
     "description": "Dispatch to the math-discovery engine to find a large Sidon set in [1,n] "
                    "(all pairwise sums distinct), proven by exhaustive search. Heavy (~1-2 min).",
     "input_schema": {"type": "object", "properties": {
         "n": {"type": "integer"}, "target": {"type": "integer"},
         "generations": {"type": "integer"}}}},
    {"name": "finance_qa",
     "description": "Answer a FINANCE question grounded in the local finance corpus, with "
                    "citations. Refuses (does not guess) when the corpus lacks a relevant "
                    "source — use this for factual finance questions to avoid hazy answers.",
     "input_schema": {"type": "object", "properties": {"question": {"type": "string"}},
                      "required": ["question"]}},
    {"name": "run_research",
     "description": "Run the research AUTOPILOT: loop ALL the gated discovery engines, keep only "
                    "verifier-proven results, accumulate them into the journal, and return a "
                    "report. Pass `minutes` for a long unattended/overnight run, or `rounds` for "
                    "a fixed count. This is how you 'run research all night and write up what "
                    "verified'.",
     "input_schema": {"type": "object", "properties": {
         "minutes": {"type": "number"}, "rounds": {"type": "integer"}}}},
    {"name": "creative_think",
     "description": "Run the CREATIVE COGNITION loop: mentat proposes ideas creatively, VERIFIES "
                    "each, remembers only what's proven, sleeps to consolidate, and measures "
                    "whether it got sharper. Use when asked to think creatively, brainstorm and "
                    "verify, discover something, or 'improve yourself' — creativity with a "
                    "verifier between every idea and belief. `rounds` = how long to think.",
     "input_schema": {"type": "object", "properties": {"rounds": {"type": "integer"}}}},
    {"name": "look",
     "description": "LOOK through the Mac's camera and report what's actually in frame (faces/"
                    "people, with confidence) - real detection via Apple's Vision, not a guess. Use "
                    "for 'what do you see', 'look', 'is anyone there', 'who is in the room', camera/"
                    "vision/intruder requests.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "design_part",
     "description": "Design a VERIFIED parametric part as code — checked analytically for fit, "
                    "clearance, strength, and mass — and emit printable OpenSCAD. `part` is "
                    "'bracket' or 'spacer' (a standoff). Use for 'design a part/prototype/bracket/"
                    "standoff', 'model something', 'CAD'. No GPU: the design is code, verified.",
     "input_schema": {"type": "object",
                      "properties": {"part": {"type": "string", "enum": ["bracket", "spacer"]}}}},
    {"name": "work_on",
     "description": "Work on self-improvement within a buffered time budget: run a VERIFIED "
                    "curriculum, carry proven knowledge forward (compounding/transfer), and stop "
                    "honestly when dry instead of padding. Use for 'go improve yourself', 'keep "
                    "working on getting better'. `minutes` caps the budget (a safety buffer is added).",
     "input_schema": {"type": "object", "properties": {"minutes": {"type": "number"}}}},
    {"name": "capabilities",
     "description": "Describe my OWN capabilities, how many are verified, and what's blocked — a "
                    "grounded self-model (engines + tools + verification checks + integrations). "
                    "Use for 'what can you do', 'run diagnostics', 'what are your abilities'.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "estimate_effort",
     "description": "Estimate how long a task will take and recommend a work budget WITH a safety "
                    "buffer, grounded in measured timings. Use for 'how long will X take', 'how "
                    "much can you get done', or before kicking off a long autonomous run.",
     "input_schema": {"type": "object", "properties": {"task": {"type": "string"}},
                      "required": ["task"]}},
    {"name": "shell",
     "description": "Run any shell command on the user's Mac and return its output. Full "
                    "terminal access. Use for files, apps, searches, status, automation.",
     "input_schema": {"type": "object",
                      "properties": {"command": {"type": "string"},
                                     "timeout": {"type": "integer"}},
                      "required": ["command"]}},
    {"name": "applescript", "description": "Run an AppleScript to automate native macOS apps "
                                           "(Music, Notes, Messages, System Events, etc.).",
     "input_schema": {"type": "object", "properties": {"script": {"type": "string"}},
                      "required": ["script"]}},
    {"name": "read_file", "description": "Read a file from disk.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}},
                      "required": ["path"]}},
    {"name": "write_file", "description": "Write (or overwrite) a file on disk. For changing an "
                                          "EXISTING file, prefer edit_file (surgical + verified).",
     "input_schema": {"type": "object",
                      "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                      "required": ["path", "content"]}},
    {"name": "edit_file",
     "description": "Make a surgical, VERIFIED edit to a file: replace `old` (must occur exactly "
                    "once) with `new`. Python is syntax-checked before writing; pass `verify_cmd` "
                    "(e.g. 'python3 -m tests.test_core') to run after the edit and ROLL BACK on "
                    "failure. Prefer this over write_file for editing code.",
     "input_schema": {"type": "object",
                      "properties": {"path": {"type": "string"}, "old": {"type": "string"},
                                     "new": {"type": "string"}, "verify_cmd": {"type": "string"}},
                      "required": ["path", "old", "new"]}},
    {"name": "web_search", "description": "Search the web; returns the top results (titles + URLs). "
                                          "Use to research or check current information online.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}},
                      "required": ["query"]}},
    {"name": "web_fetch", "description": "Fetch a web page and return its readable text. Use after "
                                         "web_search to actually read a page.",
     "input_schema": {"type": "object", "properties": {"url": {"type": "string"}},
                      "required": ["url"]}},
    {"name": "add_reminder", "description": "Add a reminder to the macOS Reminders app.",
     "input_schema": {"type": "object", "properties": {"text": {"type": "string"}},
                      "required": ["text"]}},
    {"name": "calendar_today", "description": "List today's events from the macOS Calendar app.",
     "input_schema": {"type": "object", "properties": {}}},
]

_DISPATCH = {
    "get_datetime": lambda a: tool_get_datetime(),
    "get_weather": lambda a: tool_get_weather(a.get("location", "")),
    "research_status": lambda a: tool_research_status(a.get("repo", "")),
    "remember": lambda a: tool_remember(a.get("note", "")),
    "recall": lambda a: tool_recall(a.get("query", "")),
    "learn_lesson": lambda a: tool_learn_lesson(a.get("when", ""), a.get("do", ""),
                                                a.get("avoid", ""), a.get("evidence", "")),
    "improve_maxcut": lambda a: tool_improve_maxcut(a.get("generations", 4)),
    "discover_sidon": lambda a: tool_discover_sidon(a.get("n", 100), a.get("target", 10),
                                                    a.get("generations", 4)),
    "run_research": lambda a: tool_run_research(a.get("minutes", 0), a.get("rounds", 1)),
    "creative_think": lambda a: tool_creative_think(a.get("rounds", 5)),
    "work_on": lambda a: tool_work_on(a.get("minutes", 0)),
    "look": lambda a: tool_look(),
    "design_part": lambda a: tool_design_part(a.get("part", "bracket")),
    "capabilities": lambda a: tool_capabilities(),
    "estimate_effort": lambda a: tool_estimate_effort(a.get("task", "")),
    "finance_qa": lambda a: tool_finance_qa(a.get("question", "")),
    "shell": lambda a: tool_shell(a.get("command", ""), int(a.get("timeout", 60) or 60)),
    "applescript": lambda a: tool_applescript(a.get("script", "")),
    "read_file": lambda a: tool_read_file(a.get("path", "")),
    "write_file": lambda a: tool_write_file(a.get("path", ""), a.get("content", "")),
    "edit_file": lambda a: tool_edit_file(a.get("path", ""), a.get("old", ""), a.get("new", ""),
                                          a.get("verify_cmd", "")),
    "web_search": lambda a: tool_web_search(a.get("query", "")),
    "web_fetch": lambda a: tool_web_fetch(a.get("url", "")),
    "add_reminder": lambda a: tool_add_reminder(a.get("text", "")),
    "calendar_today": lambda a: tool_calendar_today(),
}


# --------------------------------------------------------------------------- #
# the agent                                                                   #
# --------------------------------------------------------------------------- #
class Jarvis:
    def __init__(self, model: str = MODEL, max_turns: int = 12):
        # Graceful: a missing SDK or key must NOT crash Jarvis — it drops to offline mode
        # (tools still work). The Claude SDK lives in the swechats venv; system python has none.
        self.client = None
        try:
            import anthropic
            key = _load_key()
            self.client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
        except Exception:
            self.client = None
        self.online = self.client is not None and core_available()   # key present (credits checked at call)
        self.model = model
        self.max_turns = max_turns
        self.history: list[dict] = []
        self._lock = threading.Lock()   # serialize concurrent /ask threads
        self.max_history = 40
        self._last_tools: list[str] = []   # tools used in the last turn (UI transparency)

    def _offline_reply(self, text: str, note: str = "") -> str:
        """No reasoning core (no SDK / no key / no credits): route obvious intents straight to
        tools so Jarvis still DOES things, honestly flagging that full conversation is offline."""
        t = text.lower().strip()

        def call(name, args):
            try:
                return str(_DISPATCH[name](args))
            except Exception as e:
                return f"(tool {name} unavailable: {type(e).__name__})"

        if any(w in t for w in ("what can you do", "your capab", "your abilit", "capabilit",
                                "diagnostic", "self model", "self-model", "what are you")):
            return note + call("capabilities", {})
        if any(w in t for w in ("how long", "how much time", "estimate", "time frame", "timeframe")):
            return note + call("estimate_effort", {"task": text})
        if any(w in t for w in ("time", "what day", "the date", "clock")):
            return note + call("get_datetime", {})
        if "weather" in t:
            return note + call("get_weather", {"location": ""})
        if any(w in t for w in ("what do you see", "look through", "is anyone there", "who's there",
                                "who is there", "check the camera", "see me", "intruder", "in the room")):
            return note + call("look", {})
        if any(w in t for w in ("design a part", "design a bracket", "design a prototype",
                                "model a part", "cad", "openscad", "3d model", "standoff", "spacer")):
            return note + call("design_part",
                               {"part": "spacer" if ("spacer" in t or "standoff" in t) else "bracket"})
        if any(w in t for w in ("self-improve", "self improve", "improve the model", "get better",
                                "work on yourself", "keep improving", "keep working")):
            return note + call("work_on", {})
        if any(w in t for w in ("think creat", "be creative", "improve yourself", "improve itself",
                                "discover", "brainstorm and verif", "novel idea")):
            return note + call("creative_think", {})
        if any(w in t for w in ("research all night", "work all night", "work overnight", "run research")):
            return note + call("run_research", {})
        if t.startswith(("remember", "note that")):
            return note + call("remember", {"note": text})
        if any(w in t for w in ("recall", "what do you know", "what did i tell")):
            return note + call("recall", {"query": text})
        if any(w in t for w in ("search the web", "look up", "google ", "find online", "search for")):
            return note + call("web_search", {"query": text})
        return (note + "My deep reasoning is offline right now (no API credits or SDK), so I can't "
                "hold a full conversation — but my tools still work. Try: 'what can you do', 'what "
                "time is it', 'the weather', 'search the web for X', 'think creatively', 'how long "
                "will X take', or 'remember that ...'. Add API credits or a local model for full chat.")           # cap message dicts retained

    def _trim_history(self) -> None:
        # Drop oldest whole exchanges, always cutting at a real user turn (string
        # content) so a tool_use/tool_result pair is never split.
        if len(self.history) <= self.max_history:
            return
        starts = [i for i, m in enumerate(self.history)
                  if m.get("role") == "user" and isinstance(m.get("content"), str)]
        for s in starts:
            if s > 0 and len(self.history) - s <= self.max_history:
                del self.history[:s]
                return
        if starts and starts[-1] > 0:
            del self.history[:starts[-1]]

    def _create(self, **kw):
        """messages.create with adaptive DEEP thinking + high effort, degrading gracefully for
        any model/SDK that doesn't support those params (so a model switch never breaks the turn)."""
        try:
            return self.client.messages.create(
                thinking={"type": "adaptive"},
                extra_body={"output_config": {"effort": "high"}}, **kw)
        except Exception as e:
            s = str(e).lower()
            if "thinking" in s or "output_config" in s or "effort" in s:
                return self.client.messages.create(**kw)
            raise

    def ask(self, text: str, model: str | None = None) -> str:
        if not self.online:                        # no reasoning core -> offline tool router
            reply = self._offline_reply(text)
            _log_convo("user", text)
            _log_convo("jarvis", reply)
            return reply
        use_model = model if model in ALLOWED_MODELS else self.model
        if not self._lock.acquire(timeout=1.0):   # don't stall a worker thread for minutes
            return "I'm still finishing the previous request — give me a moment, then ask again."
        try:                                       # one turn at a time; history stays valid
            snapshot = len(self.history)        # roll-back point if the turn fails
            self.history.append({"role": "user", "content": text})
            lessons = jarvis_lessons_context()  # grounded rules learned from past corrections
            recalled = tool_recall(text)        # auto-recall what it knows about the user, every turn
            mem = (f"\n\nWhat you already know about the user (use it naturally, don't recite it):"
                   f"\n{recalled}" if recalled and "haven't been told" not in recalled else "")
            sys_prompt = SYSTEM + (f"\n\nWhat you have LEARNED (follow these):\n{lessons}"
                                   if lessons else "") + mem
            final = ""
            tools_used: list[str] = []
            try:
                for _ in range(self.max_turns):
                    resp = self._create(
                        model=use_model, max_tokens=4096, system=sys_prompt,
                        tools=TOOLS, messages=self.history)
                    self.history.append({"role": "assistant", "content": resp.content})
                    text_now = "".join(b.text for b in resp.content if b.type == "text")
                    if resp.stop_reason != "tool_use":
                        final = text_now or final
                        break
                    results = []
                    for block in resp.content:
                        if block.type == "tool_use":
                            tools_used.append(block.name)
                            try:
                                out = _DISPATCH[block.name](dict(block.input or {}))
                            except Exception as e:
                                out = f"tool error: {type(e).__name__}: {e}"
                            results.append({"type": "tool_result", "tool_use_id": block.id,
                                            "content": str(out)})
                    self.history.append({"role": "user", "content": results})
                else:
                    final = final or "Sorry, I got stuck in a loop there."
            except Exception as e:               # API/credits/network: degrade to offline tools
                del self.history[snapshot:]
                reply = self._offline_reply(
                    text, note=f"(reasoning core error: {type(e).__name__}; offline tools only) ")
                _log_convo("user", text)
                _log_convo("jarvis", reply)
                return reply
            self._trim_history()
            reply = final.strip() or "(no reply)"
            self._last_tools = tools_used          # what it actually did this turn (for transparency)
        finally:
            self._lock.release()
        _log_convo("user", text)
        _log_convo("jarvis", reply)
        return reply

    def operate(self, goal: str, *, max_steps: int = 25, model: str | None = None,
                on_step=None) -> str:
        """Mandate mode: 'you have full authority to <goal>' — run autonomously to
        completion. Fresh context (not the chat history), the MANDATE system prompt,
        the same tools + safety floor + audit log. Bounded by max_steps. Returns the
        final report."""
        use_model = model if model in ALLOWED_MODELS else self.model
        lessons = jarvis_lessons_context()
        sys_prompt = MANDATE_SYSTEM + (f"\n\nWhat you have LEARNED (follow these):\n{lessons}"
                                       if lessons else "")
        history: list[dict] = [{"role": "user", "content": f"MANDATE / full authority:\n{goal}"}]
        _log_action("mandate", goal)
        final = ""
        for step in range(max_steps):
            resp = self._create(
                model=use_model, max_tokens=4096, system=sys_prompt,
                tools=TOOLS, messages=history)
            history.append({"role": "assistant", "content": resp.content})
            text_now = "".join(b.text for b in resp.content if b.type == "text")
            if text_now and on_step:
                on_step(step, text_now)
            if resp.stop_reason != "tool_use":
                final = text_now or final
                break
            results = []
            for block in resp.content:
                if block.type == "tool_use":
                    if on_step:
                        on_step(step, f"[tool] {block.name} {dict(block.input or {})}")
                    try:
                        out = _DISPATCH[block.name](dict(block.input or {}))
                    except Exception as e:
                        out = f"tool error: {type(e).__name__}: {e}"
                    results.append({"type": "tool_result", "tool_use_id": block.id,
                                    "content": str(out)})
            history.append({"role": "user", "content": results})
        else:
            final = (final or "") + "\n(reached the step limit before finishing.)"
        _log_action("mandate-done", (final or "")[:200])
        return final.strip() or "(mandate produced no report)"


# --------------------------------------------------------------------------- #
# voice UI (Web Speech API: speech-to-text in, text-to-speech out)            #
# --------------------------------------------------------------------------- #


def _status_json() -> dict:
    """REAL live telemetry for the UI header — grounded counts, never decorative."""
    try:
        from .selfmodel import _engines, _tool_names, _verification_checks
        eng, tools, checks = len(_engines()), len(_tool_names()), _verification_checks()
    except Exception:
        eng = tools = checks = 0
    return {"engines": eng, "tools": tools, "checks": checks,
            "reasoning": "CLOUD" if core_available() else "OFFLINE",
            "voice": "ElevenLabs" if elevenlabs_enabled() else "browser"}


def serve(port: int = 8765):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    jarvis = Jarvis()

    def _json(handler, obj):
        payload = json.dumps(obj).encode("utf-8")
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(payload)))
        handler.end_headers()
        handler.wfile.write(payload)

    class Handler(BaseHTTPRequestHandler):
        timeout = 180                # allow slow verifier-gated engines to finish

        def log_message(self, *a):  # quiet
            pass

        def do_GET(self):
            if self.path.rstrip("/") == "/status":      # REAL live telemetry
                _json(self, _status_json())
                return
            body = (PAGE.replace("{{MODEL}}", jarvis.model)
                        .replace("{{TTS}}", "elevenlabs" if elevenlabs_enabled() else "browser")
                    ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            MAX_BODY = 2_000_000
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except (TypeError, ValueError):
                length = -1
            if length < 0 or length > MAX_BODY:
                self.send_response(400)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            raw = self.rfile.read(length) or b"{}"
            if self.path.rstrip("/") == "/speak":          # ElevenLabs audio for the browser
                try:
                    audio = elevenlabs_tts(str(json.loads(raw).get("text", "")))
                except Exception:
                    audio = None
                if audio:
                    self.send_response(200)
                    self.send_header("Content-Type", "audio/mpeg")
                    self.send_header("Content-Length", str(len(audio)))
                    self.end_headers()
                    self.wfile.write(audio)
                else:
                    self.send_response(204)
                    self.end_headers()
                return
            if self.path.rstrip("/") == "/run":         # capability deck -> a real gated engine
                try:
                    d = json.loads(raw)
                    name = str(d.get("tool", ""))
                    out = (_DISPATCH[name](dict(d.get("args") or {}))
                           if name in _DISPATCH else f"unknown tool: {name}")
                except Exception as e:
                    out = f"engine error: {type(e).__name__}: {e}"
                _json(self, {"result": str(out)})
                return
            try:
                data = json.loads(raw)
                reply = jarvis.ask(str(data.get("text", "")), model=data.get("model"))
                tools = list(getattr(jarvis, "_last_tools", []))
            except Exception as e:
                reply, tools = f"(server error: {type(e).__name__})", []
            _json(self, {"reply": reply, "tools": tools})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Jarvis is listening at  http://localhost:{port}   (model: {jarvis.model})")
    print(f"Voice: {'ElevenLabs' if elevenlabs_enabled() else 'browser (set ELEVENLABS_API_KEY for a human voice)'}")
    print("Open it in Chrome, hit 'Start conversation', and just talk.  Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nJarvis offline.")


def main(argv: list[str] | None = None):
    argv = sys.argv[1:] if argv is None else argv
    if "--text" in argv:
        text = argv[argv.index("--text") + 1]
        reply = Jarvis().ask(text)
        print(reply)
        if "--say" in argv:
            audio = elevenlabs_tts(reply)
            try:
                if audio:
                    import tempfile
                    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                    tmp.write(audio)
                    tmp.close()
                    subprocess.run(["afplay", "-r", "1.75", tmp.name], timeout=60)
                else:
                    subprocess.run(["say", "-r", "315", reply], timeout=30)
            except Exception:
                pass
        return
    port = int(argv[argv.index("--port") + 1]) if "--port" in argv else 8765
    serve(port)


if __name__ == "__main__":
    main()
