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
from .reasoning import DEFAULT_MODEL, _load_key
from .secrets import get_secret
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
    "Be warm, direct, and proactive. Use your tools when they'd help rather than "
    "guessing. Whenever the user states a preference, decision, or fact about "
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


def tool_recall(query: str = "") -> str:
    mem = _load_memory()
    if not mem:
        return "I haven't been told anything to remember yet."
    if query:
        terms = {w for w in _tokens(query) if len(w) > 2}
        hits = [m["note"] for m in mem if terms & _tokens(m["note"])]
        if hits:
            return " | ".join(hits[-5:])
        # No keyword hit — return recent notes rather than wrongly claiming nothing.
    return " | ".join(m["note"] for m in mem[-5:])


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
    def __init__(self, model: str = MODEL, max_turns: int = 8):
        import anthropic
        key = _load_key()
        self.client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
        self.model = model
        self.max_turns = max_turns
        self.history: list[dict] = []
        self._lock = threading.Lock()   # serialize concurrent /ask threads
        self.max_history = 40           # cap message dicts retained

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

    def ask(self, text: str, model: str | None = None) -> str:
        use_model = model if model in ALLOWED_MODELS else self.model
        if not self._lock.acquire(timeout=1.0):   # don't stall a worker thread for minutes
            return "I'm still finishing the previous request — give me a moment, then ask again."
        try:                                       # one turn at a time; history stays valid
            snapshot = len(self.history)        # roll-back point if the turn fails
            self.history.append({"role": "user", "content": text})
            lessons = jarvis_lessons_context()  # grounded rules learned from past corrections
            sys_prompt = SYSTEM + (f"\n\nWhat you have LEARNED (follow these):\n{lessons}"
                                   if lessons else "")
            final = ""
            try:
                for _ in range(self.max_turns):
                    resp = self.client.messages.create(
                        model=use_model, max_tokens=1024, system=sys_prompt,
                        tools=TOOLS, messages=self.history)
                    self.history.append({"role": "assistant", "content": resp.content})
                    text_now = "".join(b.text for b in resp.content if b.type == "text")
                    if resp.stop_reason != "tool_use":
                        final = text_now or final
                        break
                    results = []
                    for block in resp.content:
                        if block.type == "tool_use":
                            try:
                                out = _DISPATCH[block.name](dict(block.input or {}))
                            except Exception as e:
                                out = f"tool error: {type(e).__name__}: {e}"
                            results.append({"type": "tool_result", "tool_use_id": block.id,
                                            "content": str(out)})
                    self.history.append({"role": "user", "content": results})
                else:
                    final = final or "Sorry, I got stuck in a loop there."
            except Exception as e:               # discard the partial, poisoning turn
                del self.history[snapshot:]
                reply = f"Sorry — I hit an error ({type(e).__name__}). Try again."
                _log_convo("user", text)
                _log_convo("jarvis", reply)
                return reply
            self._trim_history()
            reply = final.strip() or "(no reply)"
        finally:
            self._lock.release()
        _log_convo("user", text)
        _log_convo("jarvis", reply)
        return reply


# --------------------------------------------------------------------------- #
# voice UI (Web Speech API: speech-to-text in, text-to-speech out)            #
# --------------------------------------------------------------------------- #
PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Jarvis</title><style>
:root{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,system-ui,sans-serif;background:#0a0d13;color:#e8edf4;
  display:flex;flex-direction:column;height:100vh}
header{display:flex;align-items:center;justify-content:space-between;gap:14px;
  padding:13px 22px;border-bottom:1px solid #161d29;background:#0c1018}
.brand{font-weight:600;letter-spacing:.34em;color:#8fd6ff;font-size:15px}
.brand small{display:block;letter-spacing:.03em;color:#5d6b7e;font-size:11px;margin-top:3px;font-weight:400}
.sel{display:flex;gap:8px}
select{background:#0f141d;color:#cfe3f5;border:1px solid #222c3a;border-radius:9px;padding:8px 10px;font-size:12.5px;max-width:165px}
#log{flex:1;overflow:auto;padding:24px;display:flex;flex-direction:column;gap:13px;max-width:820px;width:100%;margin:0 auto}
.msg{max-width:76%;padding:11px 15px;border-radius:15px;line-height:1.55;white-space:pre-wrap;font-size:15px}
.you{align-self:flex-end;background:#1f5fff;color:#fff;border-bottom-right-radius:5px}
.jarvis{align-self:flex-start;background:#141b27;border:1px solid #222c3a;border-bottom-left-radius:5px}
#live{min-height:22px;text-align:center;color:#7c8aa0;font-size:13.5px;padding:2px 22px 8px}
#live .it{color:#aebccf}
footer{display:flex;gap:12px;padding:14px 22px 22px;align-items:center;max-width:820px;width:100%;margin:0 auto}
#talk{display:flex;align-items:center;gap:10px;border:none;border-radius:999px;padding:13px 20px;
  background:#1f5fff;color:#fff;font-size:14.5px;font-weight:500;cursor:pointer;white-space:nowrap}
#talk .dot{width:11px;height:11px;border-radius:50%;background:#fff;opacity:.92}
#talk.live{background:#dc2626}
#talk.live .dot{animation:pulse 1.1s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(255,255,255,.7)}100%{box-shadow:0 0 0 11px rgba(255,255,255,0)}}
form{flex:1;display:flex}
#text{flex:1;padding:13px 16px;border-radius:12px;border:1px solid #222c3a;background:#0f141d;color:#e8edf4;font-size:15px}
#text:focus{outline:none;border-color:#1f5fff}
</style></head><body>
<header>
  <div class="brand">JARVIS<small id="modelLabel">...</small></div>
  <div class="sel"><select id="voice" title="voice"></select><select id="model" title="model"></select></div>
</header>
<div id="log"></div>
<div id="live"></div>
<footer>
  <button id="talk"><span class="dot"></span><span id="talkTxt">Start conversation</span></button>
  <form id="form"><input id="text" placeholder="or type..." autocomplete="off"></form>
</footer>
<script>
const MODEL_DEFAULT="{{MODEL}}";
const TTS_MODE="{{TTS}}";
const $=id=>document.getElementById(id);
const log=$('log'),live=$('live'),talk=$('talk'),talkTxt=$('talkTxt'),form=$('form'),input=$('text'),
  voiceSel=$('voice'),modelSel=$('model'),modelLabel=$('modelLabel');
let voices=[],convo=false,state='idle',pending='',timer=null;
const SILENCE_MS=1400;

const MODELS=[["claude-opus-4-8","opus 4.8 - smartest"],["claude-sonnet-4-6","sonnet 4.6 - balanced"],["claude-haiku-4-5","haiku 4.5 - fastest"]];
MODELS.forEach(([id,lbl])=>{const o=document.createElement('option');o.value=id;o.textContent=lbl;modelSel.appendChild(o);});
modelSel.value=localStorage.getItem('jarvisModel')||MODEL_DEFAULT||"claude-opus-4-8";
function showModel(){modelLabel.textContent=modelSel.value.replace('claude-','');}
showModel();modelSel.onchange=()=>{localStorage.setItem('jarvisModel',modelSel.value);showModel();};

function pickDefault(list){const score=v=>{const n=v.name.toLowerCase();
  if(n.includes('google'))return 6;
  if(n.includes('(enhanced)')||n.includes('(premium)')||n.includes('siri'))return 5;
  if(/samantha|ava|allison|zoe|nicky|serena/.test(n))return 4;
  if(v.lang&&v.lang.toLowerCase()==='en-us')return 3;
  if(v.lang&&v.lang.toLowerCase().startsWith('en'))return 2;return 1;};
  return [...list].sort((a,b)=>score(b)-score(a))[0];}
function loadVoices(){if(TTS_MODE==='elevenlabs'){voiceSel.innerHTML='<option>ElevenLabs - server voice</option>';voiceSel.disabled=true;return;}
  voices=speechSynthesis.getVoices();if(!voices.length)return;
  const en=voices.filter(v=>v.lang&&v.lang.toLowerCase().startsWith('en'));const list=en.length?en:voices;
  voiceSel.innerHTML='';list.forEach(v=>{const o=document.createElement('option');o.value=v.name;o.textContent=v.name.replace(/ \\(.+\\)/,'')+' - '+v.lang;voiceSel.appendChild(o);});
  const saved=localStorage.getItem('jarvisVoice'),def=pickDefault(list);
  voiceSel.value=(saved&&list.some(v=>v.name===saved))?saved:(def?def.name:list[0].name);}
loadVoices();if(window.speechSynthesis)speechSynthesis.onvoiceschanged=loadVoices;
voiceSel.onchange=()=>{localStorage.setItem('jarvisVoice',voiceSel.value);speak("Okay, this is the new voice.");};

function add(who,t){const d=document.createElement('div');d.className='msg '+who;d.textContent=t;log.appendChild(d);log.scrollTop=log.scrollHeight;}
function setState(s){state=s;const m={thinking:'thinking...',speaking:'speaking...',idle:''};if(s!=='listening')live.textContent=m[s]||'';}
function showLive(txt){live.textContent='';const a=document.createElement('span');a.textContent='listening... ';
  const b=document.createElement('span');b.className='it';b.textContent=txt;live.append(a,b);}
async function speak(t){setState('speaking');
  if(TTS_MODE==='elevenlabs'){try{
    const r=await fetch('/speak',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t})});
    if(r.ok){const blob=await r.blob();if(blob.size>0){const url=URL.createObjectURL(blob);const a=new Audio(url);a.playbackRate=1.75;
      a.onended=()=>{URL.revokeObjectURL(url);convo?listen():setState('idle');};
      a.onerror=()=>{convo?listen():setState('idle');};a.play();return;}}}catch(e){}}
  try{const u=new SpeechSynthesisUtterance(t);u.rate=1.75;u.pitch=1.0;
    const v=voices.find(x=>x.name===voiceSel.value);if(v)u.voice=v;
    u.onend=()=>{convo?listen():setState('idle');};
    u.onerror=()=>{convo?listen():setState('idle');};
    speechSynthesis.cancel();speechSynthesis.speak(u);}catch(e){if(convo)listen();}}
async function ask(t){add('you',t);try{rec&&rec.stop();}catch(e){}setState('thinking');
  try{const r=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({text:t,model:modelSel.value})});
    const j=await r.json();add('jarvis',j.reply);speak(j.reply);}
  catch(e){add('jarvis','(could not reach the server)');convo?listen():setState('idle');}}

const SR=window.SpeechRecognition||window.webkitSpeechRecognition;let rec=null;
if(SR){rec=new SR();rec.lang='en-US';rec.continuous=true;rec.interimResults=true;
  rec.onresult=e=>{if(state!=='listening')return;let interim='';
    for(let i=e.resultIndex;i<e.results.length;i++){const r=e.results[i];
      if(r.isFinal)pending+=r[0].transcript+' ';else interim+=r[0].transcript;}
    showLive((pending+interim).trim());clearTimeout(timer);timer=setTimeout(finalize,SILENCE_MS);};
  rec.onerror=e=>{if(e.error==='no-speech'||e.error==='aborted')return;live.textContent='mic: '+e.error;};
  rec.onend=()=>{if(convo&&state==='listening'){try{rec.start();}catch(e){}}};}
function finalize(){const t=pending.trim();pending='';if(!t)return;setState('thinking');try{rec.stop();}catch(e){}ask(t);}
function listen(){if(!convo)return;setState('listening');showLive('');try{rec.start();}catch(e){}}
function startConvo(){if(!SR){live.textContent='This browser has no speech recognition - use Chrome, or type below.';return;}
  convo=true;talk.classList.add('live');talkTxt.textContent='Stop';speechSynthesis.cancel();listen();}
function stopConvo(){convo=false;talk.classList.remove('live');talkTxt.textContent='Start conversation';
  try{rec.stop();}catch(e){}speechSynthesis.cancel();clearTimeout(timer);setState('idle');}
talk.onclick=()=>convo?stopConvo():startConvo();
form.onsubmit=e=>{e.preventDefault();const t=input.value.trim();if(t){input.value='';ask(t);}};
add('jarvis','Online. Hit Start conversation and just talk - I will keep listening, hands-free, and pauses will not cut you off. Or type below.');
</script></body></html>"""


def serve(port: int = 8765):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    jarvis = Jarvis()

    class Handler(BaseHTTPRequestHandler):
        timeout = 30                 # bound a stalled read so a worker thread can't hang

        def log_message(self, *a):  # quiet
            pass

        def do_GET(self):
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
            try:
                data = json.loads(raw)
                reply = jarvis.ask(str(data.get("text", "")), model=data.get("model"))
            except Exception as e:
                reply = f"(server error: {type(e).__name__})"
            body = json.dumps({"reply": reply}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

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
