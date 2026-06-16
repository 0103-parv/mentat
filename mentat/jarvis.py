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
ALLOWED_MODELS = {"claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5"}
MEMORY_PATH = Path(__file__).parent / "jarvis_memory.json"
ACTIONS_LOG = Path(__file__).parent / "jarvis_actions.log"
REPOS = {name: Path.home() / name for name in ("swechats", "alpha-evolver", "mentat")}

# Full machine control, with ONE floor: refuse catastrophic, irreversible commands.
# Voice STT can garble input, so a disk-wipe / rm-of-home guard protects the user.
# Set JARVIS_NO_GUARD=1 to remove even that.
_GUARD = os.environ.get("JARVIS_NO_GUARD") != "1"
_RM_RF = re.compile(r"\brm\b[^|;&\n]*-[a-z]*[rf][a-z]*\b", re.I)
_CATA_TARGET = re.compile(r"(^|\s)(/|/\*|~|~/|~/\*|\$home|\$home/|\$home/\*)(\s|$)", re.I)
_CATASTROPHIC = [
    re.compile(r"--no-preserve-root", re.I),
    re.compile(r"\bmkfs\b|\bnewfs\b", re.I),
    re.compile(r"\bdiskutil\b[^\n]*\b(erase|reformat|partitiondisk)\b", re.I),
    re.compile(r"\bdd\b[^\n]*\bof=/dev/", re.I),
    re.compile(r">\s*/dev/(disk|rdisk|sd[a-z])", re.I),
    re.compile(r":\(\)\s*\{[^}]*:\s*\|\s*:[^}]*&[^}]*\}\s*;", re.I),  # fork bomb
]


def _is_catastrophic(cmd: str) -> bool:
    if _RM_RF.search(cmd) and _CATA_TARGET.search(cmd):   # rm -rf of / ~ $HOME /*
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
    "themselves, call `remember` so you don't forget it next time. "
    "You can also CONTROL this Mac: `shell` runs any terminal command, `applescript` "
    "automates native apps, and `read_file` / `write_file` access files. Use them to "
    "actually get things done — open apps, manage files, search the machine, automate "
    "tasks — the way a power user works at the terminal. Before anything destructive or "
    "irreversible (deleting or overwriting files, changing system settings, installing or "
    "removing software, sending messages on the user's behalf), say what you're about to "
    "do and get a quick confirmation first. For routine, safe actions just do them and "
    "report back briefly. If you don't know something and have no tool for it, say so."
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
    {"name": "write_file", "description": "Write (or overwrite) a file on disk.",
     "input_schema": {"type": "object",
                      "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                      "required": ["path", "content"]}},
]

_DISPATCH = {
    "get_datetime": lambda a: tool_get_datetime(),
    "get_weather": lambda a: tool_get_weather(a.get("location", "")),
    "research_status": lambda a: tool_research_status(a.get("repo", "")),
    "remember": lambda a: tool_remember(a.get("note", "")),
    "recall": lambda a: tool_recall(a.get("query", "")),
    "shell": lambda a: tool_shell(a.get("command", ""), int(a.get("timeout", 60) or 60)),
    "applescript": lambda a: tool_applescript(a.get("script", "")),
    "read_file": lambda a: tool_read_file(a.get("path", "")),
    "write_file": lambda a: tool_write_file(a.get("path", ""), a.get("content", "")),
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

    def ask(self, text: str, model: str | None = None) -> str:
        use_model = model if model in ALLOWED_MODELS else self.model
        self.history.append({"role": "user", "content": text})
        final = ""
        for _ in range(self.max_turns):
            resp = self.client.messages.create(
                model=use_model, max_tokens=1024, system=SYSTEM,
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
function loadVoices(){voices=speechSynthesis.getVoices();if(!voices.length)return;
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
function speak(t){try{const u=new SpeechSynthesisUtterance(t);u.rate=1.0;u.pitch=1.0;
  const v=voices.find(x=>x.name===voiceSel.value);if(v)u.voice=v;
  setState('speaking');
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
        def log_message(self, *a):  # quiet
            pass

        def do_GET(self):
            body = PAGE.replace("{{MODEL}}", jarvis.model).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            try:
                data = json.loads(self.rfile.read(length) or b"{}")
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
            try:
                subprocess.run(["say", reply], timeout=30)
            except Exception:
                pass
        return
    port = int(argv[argv.index("--port") + 1]) if "--port" in argv else 8765
    serve(port)


if __name__ == "__main__":
    main()
