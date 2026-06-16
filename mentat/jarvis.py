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
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from .reasoning import DEFAULT_MODEL, _load_key
import os

MODEL = os.environ.get("MENTAT_MODEL", DEFAULT_MODEL)
MEMORY_PATH = Path(__file__).parent / "jarvis_memory.json"
REPOS = {name: Path.home() / name for name in ("swechats", "alpha-evolver", "mentat")}

SYSTEM = (
    "You are Jarvis, a personal operations assistant for a high-school researcher who "
    "is building AI systems (the repos swechats, alpha-evolver, and mentat). "
    "Your replies are read ALOUD by a speech synthesizer, so: keep them to 1-3 short "
    "sentences, plain conversational English, NO markdown, NO bullet lists, no emoji. "
    "Be warm, direct, and proactive. Use your tools when they'd help rather than "
    "guessing. Whenever the user states a preference, decision, or fact about "
    "themselves, call `remember` so you don't forget it next time. If you don't know "
    "something and have no tool for it, say so briefly."
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
]

_DISPATCH = {
    "get_datetime": lambda a: tool_get_datetime(),
    "get_weather": lambda a: tool_get_weather(a.get("location", "")),
    "research_status": lambda a: tool_research_status(a.get("repo", "")),
    "remember": lambda a: tool_remember(a.get("note", "")),
    "recall": lambda a: tool_recall(a.get("query", "")),
}


# --------------------------------------------------------------------------- #
# the agent                                                                   #
# --------------------------------------------------------------------------- #
class Jarvis:
    def __init__(self, model: str = MODEL, max_turns: int = 6):
        import anthropic
        key = _load_key()
        self.client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
        self.model = model
        self.max_turns = max_turns
        self.history: list[dict] = []

    def ask(self, text: str) -> str:
        self.history.append({"role": "user", "content": text})
        final = ""
        for _ in range(self.max_turns):
            resp = self.client.messages.create(
                model=self.model, max_tokens=1024, system=SYSTEM,
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
        return final.strip() or "(no reply)"


# --------------------------------------------------------------------------- #
# voice UI (Web Speech API: speech-to-text in, text-to-speech out)            #
# --------------------------------------------------------------------------- #
PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Jarvis</title><style>
:root{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,system-ui,sans-serif;background:#0b0e14;color:#e6e6e6;
  display:flex;flex-direction:column;height:100vh}
header{padding:18px 22px;font-weight:600;letter-spacing:.12em;color:#7fd1ff;border-bottom:1px solid #1b2330}
#log{flex:1;overflow:auto;padding:22px;display:flex;flex-direction:column;gap:12px}
.msg{max-width:78%;padding:11px 15px;border-radius:14px;line-height:1.5;white-space:pre-wrap}
.you{align-self:flex-end;background:#1d4ed8}
.jarvis{align-self:flex-start;background:#161c28;border:1px solid #232c3c}
#status{min-height:20px;color:#8aa0b8;font-size:13px;padding:0 22px}
footer{display:flex;gap:10px;padding:16px 22px 24px;align-items:center}
#mic{width:62px;height:62px;border-radius:50%;border:none;background:#1d4ed8;color:#fff;font-size:24px;cursor:pointer;flex:none}
#mic.on{background:#dc2626;animation:p 1.1s infinite}
@keyframes p{0%{box-shadow:0 0 0 0 rgba(220,38,38,.6)}100%{box-shadow:0 0 0 16px rgba(220,38,38,0)}}
#text{flex:1;padding:13px 15px;border-radius:12px;border:1px solid #232c3c;background:#0f141d;color:#e6e6e6;font-size:15px}
</style></head><body>
<header>J A R V I S</header>
<div id="log"></div>
<div id="status">tap the mic and talk, or type below</div>
<footer>
  <button id="mic" title="hold a conversation">🎙</button>
  <form id="form" style="flex:1;display:flex;gap:10px"><input id="text" placeholder="type a message…" autocomplete="off"><button style="display:none"></button></form>
</footer>
<script>
const log=document.getElementById('log'),statusEl=document.getElementById('status'),
  mic=document.getElementById('mic'),form=document.getElementById('form'),input=document.getElementById('text');
let st='idle',micOn=false;
function setStatus(s){st=s;statusEl.textContent=s}
function add(who,t){const d=document.createElement('div');d.className='msg '+who;d.textContent=t;log.appendChild(d);log.scrollTop=log.scrollHeight}
function speak(t){try{const u=new SpeechSynthesisUtterance(t);u.rate=1.05;speechSynthesis.cancel();speechSynthesis.speak(u)}catch(e){}}
async function ask(t){add('you',t);setStatus('thinking…');
  try{const r=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t})});
    const j=await r.json();add('jarvis',j.reply);setStatus('idle');speak(j.reply);}
  catch(e){add('jarvis','(could not reach Jarvis — is the server running?)');setStatus('idle');}}
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;let rec=null;
if(SR){rec=new SR();rec.lang='en-US';rec.interimResults=false;rec.maxAlternatives=1;
  rec.onresult=e=>ask(e.results[0][0].transcript);
  rec.onerror=e=>setStatus('mic: '+e.error);
  rec.onend=()=>{micOn=false;mic.classList.remove('on');if(st==='listening…')setStatus('idle');};}
mic.onclick=()=>{if(!SR){setStatus('this browser has no speech recognition — type instead');return;}
  if(micOn){rec.stop();return;}speechSynthesis.cancel();micOn=true;mic.classList.add('on');setStatus('listening…');rec.start();};
form.onsubmit=e=>{e.preventDefault();const t=input.value.trim();if(t){input.value='';ask(t);}};
add('jarvis','Online. Ask me about your repos, the weather, the time — or tell me something to remember.');
</script></body></html>"""


def serve(port: int = 8765):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    jarvis = Jarvis()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # quiet
            pass

        def do_GET(self):
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            try:
                data = json.loads(self.rfile.read(length) or b"{}")
                reply = jarvis.ask(str(data.get("text", "")))
            except Exception as e:
                reply = f"(server error: {type(e).__name__})"
            body = json.dumps({"reply": reply}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Jarvis is listening at  http://localhost:{port}")
    print("Open it in Chrome, tap the mic, and talk.  Ctrl-C to stop.")
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
            try:
                subprocess.run(["say", reply], timeout=30)
            except Exception:
                pass
        return
    port = int(argv[argv.index("--port") + 1]) if "--port" in argv else 8765
    serve(port)


if __name__ == "__main__":
    main()
