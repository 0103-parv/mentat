"""The Jarvis holographic command center — an original UI backed by REAL mentat cognition.

Where the inspiration (driftworks J.A.R.V.I.S.) shows decorative telemetry ("99.2% cognition"),
this shows the truth: the live engine count, tool count, and number of passing verification checks,
plus a capability deck whose buttons run the actual verifier-gated engines and show what's proven.
The neural orb reacts to state. Dark, glassmorphic, sci-fi — but every number is grounded.

Served by jarvis.serve(); {{MODEL}} / {{TTS}} are filled in per request.
"""

PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JARVIS</title><style>
:root{color-scheme:dark;
  --bg:#05080e; --panel:rgba(16,24,38,.55); --line:rgba(80,160,220,.16);
  --cyan:#46e6ff; --teal:#4dd7c0; --amber:#ffb259; --ink:#e9f2fb; --dim:#7e93ad}
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,system-ui,sans-serif;background:
  radial-gradient(1100px 700px at 70% -10%,rgba(30,90,140,.18),transparent 60%),
  radial-gradient(900px 600px at 0% 110%,rgba(40,120,110,.13),transparent 55%),var(--bg);
  color:var(--ink);height:100vh;overflow:hidden}
.grid{display:grid;grid-template-rows:auto 1fr auto;height:100vh}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
/* header telemetry */
header{display:flex;align-items:center;justify-content:space-between;gap:18px;
  padding:12px 22px;border-bottom:1px solid var(--line);
  background:linear-gradient(180deg,rgba(10,16,26,.9),rgba(10,16,26,.4))}
.brand{font-weight:600;letter-spacing:.42em;color:var(--cyan);font-size:16px;text-shadow:0 0 18px rgba(70,230,255,.45)}
.brand small{display:block;letter-spacing:.06em;color:var(--dim);font-size:10.5px;margin-top:2px;font-weight:400}
.tele{display:flex;gap:9px;flex-wrap:wrap;justify-content:flex-end}
.chip{display:flex;flex-direction:column;align-items:flex-start;gap:1px;padding:6px 11px;border:1px solid var(--line);
  border-radius:9px;background:var(--panel);backdrop-filter:blur(6px);min-width:62px}
.chip b{font-size:14px;color:var(--cyan);letter-spacing:.02em}
.chip span{font-size:9px;letter-spacing:.18em;color:var(--dim);text-transform:uppercase}
.chip.amber b{color:var(--amber)} .chip.teal b{color:var(--teal)}
.dotpulse{width:7px;height:7px;border-radius:50%;background:var(--teal);box-shadow:0 0 10px var(--teal);animation:bp 1.6s infinite}
@keyframes bp{0%,100%{opacity:.4}50%{opacity:1}}
/* main */
main{display:grid;grid-template-columns:1.35fr .95fr;gap:0;min-height:0}
.stage{display:flex;flex-direction:column;min-height:0;border-right:1px solid var(--line)}
.orbwrap{position:relative;height:210px;display:flex;align-items:center;justify-content:center;flex:none}
#orb{position:absolute;inset:0;margin:auto}
.stateLbl{position:absolute;bottom:8px;font-size:11.5px;letter-spacing:.32em;text-transform:uppercase;color:var(--dim)}
.stateLbl.active{color:var(--cyan);text-shadow:0 0 12px rgba(70,230,255,.5)}
#log{flex:1;overflow:auto;padding:8px 22px 18px;display:flex;flex-direction:column;gap:11px}
.msg{max-width:88%;padding:10px 14px;border-radius:13px;line-height:1.5;white-space:pre-wrap;font-size:14px;word-break:break-word}
.you{align-self:flex-end;background:linear-gradient(180deg,#1f6bff,#1655d8);color:#fff;border-bottom-right-radius:4px}
.jarvis{align-self:flex-start;background:var(--panel);border:1px solid var(--line);border-bottom-left-radius:4px;backdrop-filter:blur(6px)}
.jarvis.sys{border-color:rgba(255,178,89,.3)}
.jarvis .rt{font-size:11px;color:var(--amber);letter-spacing:.06em;margin-bottom:4px;font-family:ui-monospace,monospace}
.jarvis .rt.ok{color:var(--teal)} .jarvis .rt.warn{color:var(--dim)}
/* capability deck */
.deck{padding:16px 16px 8px;overflow:auto;display:flex;flex-direction:column;gap:10px}
.deckhdr{font-size:10px;letter-spacing:.28em;color:var(--dim);text-transform:uppercase;padding:2px 4px 4px}
.cap{display:flex;align-items:center;gap:12px;padding:12px 13px;border:1px solid var(--line);border-radius:12px;
  background:var(--panel);backdrop-filter:blur(6px);cursor:pointer;transition:.16s;text-align:left}
.cap:hover{border-color:rgba(70,230,255,.45);transform:translateY(-1px);box-shadow:0 6px 22px rgba(20,90,140,.25)}
.cap:disabled{opacity:.5;cursor:wait}
.cap .ic{width:34px;height:34px;flex:none;display:flex;align-items:center;justify-content:center;border-radius:9px;
  background:rgba(70,230,255,.1);color:var(--cyan);font-size:17px}
.cap .ic.a{background:rgba(255,178,89,.12);color:var(--amber)} .cap .ic.t{background:rgba(77,215,192,.12);color:var(--teal)}
.cap .tt{font-size:13.5px;font-weight:500;color:var(--ink)}
.cap .sb{font-size:11px;color:var(--dim);margin-top:1px}
/* footer */
footer{display:flex;gap:11px;padding:13px 22px;align-items:center;border-top:1px solid var(--line);
  background:linear-gradient(0deg,rgba(10,16,26,.9),rgba(10,16,26,.3))}
#talk{display:flex;align-items:center;gap:9px;border:1px solid rgba(70,230,255,.4);border-radius:999px;padding:12px 18px;
  background:rgba(70,230,255,.08);color:var(--cyan);font-size:14px;font-weight:500;cursor:pointer;white-space:nowrap;transition:.15s}
#talk:hover{background:rgba(70,230,255,.16)}
#talk .dot{width:10px;height:10px;border-radius:50%;background:var(--cyan);box-shadow:0 0 10px var(--cyan)}
#talk.live{background:#dc2626;border-color:#dc2626;color:#fff}
#talk.live .dot{background:#fff;box-shadow:none;animation:pulse 1.1s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(255,255,255,.7)}100%{box-shadow:0 0 0 10px rgba(255,255,255,0)}}
form{flex:1;display:flex}
#text{flex:1;padding:12px 15px;border-radius:11px;border:1px solid var(--line);background:rgba(8,12,20,.8);color:var(--ink);font-size:14px}
#text:focus{outline:none;border-color:var(--cyan)}
select{background:rgba(8,12,20,.8);color:#cfe3f5;border:1px solid var(--line);border-radius:9px;padding:9px;font-size:11.5px;max-width:135px}
@media(max-width:760px){main{grid-template-columns:1fr}.deck{display:none}.orbwrap{height:150px}}
</style></head><body>
<div class="grid">
<header>
  <div class="brand">J A R V I S<small id="modelLabel">verification-gated cognition</small></div>
  <div class="tele" id="tele">
    <div class="chip"><b id="t-eng">—</b><span>engines</span></div>
    <div class="chip"><b id="t-tool">—</b><span>tools</span></div>
    <div class="chip teal"><b id="t-chk">—</b><span>verified</span></div>
    <div class="chip amber"><b id="t-rsn">—</b><span>reasoning</span></div>
    <div class="chip"><b><span class="dotpulse"></span></b><span id="t-voice">voice</span></div>
  </div>
</header>
<main>
  <section class="stage">
    <div class="orbwrap"><canvas id="orb" width="380" height="210"></canvas>
      <div class="stateLbl" id="stateLbl">standby</div></div>
    <div id="log"></div>
  </section>
  <aside class="deck">
    <div class="deckhdr">Capabilities — every result is verified</div>
    <button class="cap" data-tool="creative_think"><div class="ic">✷</div><div><div class="tt">Think creatively</div><div class="sb">propose → verify → keep, get sharper</div></div></button>
    <button class="cap" data-tool="work_on"><div class="ic t">⟳</div><div><div class="tt">Self-improve</div><div class="sb">a verified curriculum, compounding</div></div></button>
    <button class="cap" data-tool="look"><div class="ic t">◉</div><div><div class="tt">Look (vision)</div><div class="sb">camera + Apple Vision, real detection</div></div></button>
    <button class="cap" data-tool="design_part"><div class="ic a">⬡</div><div><div class="tt">Design a part</div><div class="sb">parametric CAD, verified, OpenSCAD</div></div></button>
    <button class="cap" data-tool="discover_sidon"><div class="ic">∑</div><div><div class="tt">Discover (math)</div><div class="sb">a proven Sidon set, exhaustively</div></div></button>
    <button class="cap" data-tool="capabilities"><div class="ic t">◈</div><div><div class="tt">Diagnostics</div><div class="sb">what I am, grounded — no vibes</div></div></button>
  </aside>
</main>
<footer>
  <button id="talk"><span class="dot"></span><span id="talkTxt">Start conversation</span></button>
  <form id="form"><input id="text" placeholder="speak, or type a command..." autocomplete="off"></form>
  <select id="voice" title="voice"></select><select id="model" title="model"></select>
</footer>
</div>
<script>
const MODEL_DEFAULT="{{MODEL}}", TTS_MODE="{{TTS}}";
const $=id=>document.getElementById(id);
const log=$('log'),talk=$('talk'),talkTxt=$('talkTxt'),form=$('form'),input=$('text'),
  voiceSel=$('voice'),modelSel=$('model'),modelLabel=$('modelLabel'),stateLbl=$('stateLbl');
let voices=[],convo=false,state='idle',pending='',timer=null;const SILENCE_MS=1400;

/* ---- live telemetry (REAL) ---- */
async function refreshStatus(){try{const s=await(await fetch('/status')).json();
  $('t-eng').textContent=s.engines;$('t-tool').textContent=s.tools;$('t-chk').textContent=s.checks;
  $('t-rsn').textContent=s.reasoning;$('t-voice').textContent=s.voice;}catch(e){}}
refreshStatus();setInterval(refreshStatus,15000);

/* ---- the neural orb (original; reacts to state) ---- */
const cv=$('orb'),cx=cv.getContext('2d');let tphase=0;
const PAL={idle:'#46e6ff',listening:'#46e6ff',thinking:'#ffb259',speaking:'#4dd7c0',working:'#ffb259'};
function orb(){tphase+=0.016;const w=cv.width,h=cv.height,cxp=w/2,cyp=h/2;cx.clearRect(0,0,w,h);
  const col=PAL[state]||PAL.idle;const hot=(state!=='idle');const R=58;
  for(let i=0;i<3;i++){const rr=R+i*13+Math.sin(tphase*1.4+i)*(hot?6:2);
    cx.beginPath();const a0=tphase*(i%2?-1:1)*(hot?1.1:0.4)+i*2;
    cx.arc(cxp,cyp,rr,a0,a0+Math.PI*1.25);cx.strokeStyle=col;cx.globalAlpha=hot?0.55-i*0.13:0.3-i*0.07;
    cx.lineWidth=2.2-i*0.5;cx.stroke();}
  cx.globalAlpha=1;const pts=42;
  for(let i=0;i<pts;i++){const a=(i/pts)*Math.PI*2+tphase*(hot?0.7:0.25);
    const pr=R-10+Math.sin(tphase*2+i*0.6)*(hot?9:3);const x=cxp+Math.cos(a)*pr,y=cyp+Math.sin(a)*pr*0.62;
    cx.beginPath();cx.arc(x,y,1.3,0,7);cx.fillStyle=col;cx.globalAlpha=hot?0.9:0.5;cx.fill();}
  const cr=20+Math.sin(tphase*2.2)*(hot?5:2);const g=cx.createRadialGradient(cxp,cyp,1,cxp,cyp,cr*2.4);
  g.addColorStop(0,col);g.addColorStop(1,'transparent');cx.globalAlpha=hot?0.55:0.3;
  cx.beginPath();cx.arc(cxp,cyp,cr*2.4,0,7);cx.fillStyle=g;cx.fill();cx.globalAlpha=1;
  requestAnimationFrame(orb);}orb();

/* ---- models + voices ---- */
const MODELS=[["claude-opus-4-8","opus 4.8 - smartest"],["claude-sonnet-4-6","sonnet 4.6 - balanced"],["claude-haiku-4-5","haiku 4.5 - fastest"]];
MODELS.forEach(([id,lbl])=>{const o=document.createElement('option');o.value=id;o.textContent=lbl;modelSel.appendChild(o);});
modelSel.value=localStorage.getItem('jarvisModel')||MODEL_DEFAULT||"claude-opus-4-8";
modelSel.onchange=()=>localStorage.setItem('jarvisModel',modelSel.value);
function pickDefault(list){const score=v=>{const n=v.name.toLowerCase();
  if(n.includes('google'))return 6;if(n.includes('(enhanced)')||n.includes('(premium)')||n.includes('siri'))return 5;
  if(/samantha|ava|allison|zoe|serena/.test(n))return 4;if(v.lang&&v.lang.toLowerCase()==='en-us')return 3;
  if(v.lang&&v.lang.toLowerCase().startsWith('en'))return 2;return 1;};
  return [...list].sort((a,b)=>score(b)-score(a))[0];}
function loadVoices(){if(TTS_MODE==='elevenlabs'){voiceSel.innerHTML='<option>ElevenLabs - human voice</option>';voiceSel.disabled=true;return;}
  voices=speechSynthesis.getVoices();if(!voices.length)return;
  const en=voices.filter(v=>v.lang&&v.lang.toLowerCase().startsWith('en'));const list=en.length?en:voices;
  voiceSel.innerHTML='';list.forEach(v=>{const o=document.createElement('option');o.value=v.name;o.textContent=v.name.split(' (')[0]+' - '+v.lang;voiceSel.appendChild(o);});
  const saved=localStorage.getItem('jarvisVoice'),def=pickDefault(list);
  voiceSel.value=(saved&&list.some(v=>v.name===saved))?saved:(def?def.name:list[0].name);}
loadVoices();if(window.speechSynthesis)speechSynthesis.onvoiceschanged=loadVoices;
voiceSel.onchange=()=>{localStorage.setItem('jarvisVoice',voiceSel.value);speak("Okay, this is the new voice.");};

/* ---- conversation ---- */
function add(who,t,rt){const d=document.createElement('div');d.className='msg '+who;
  if(rt){const r=document.createElement('div');r.className='rt'+(/NOT verified/.test(rt)?' warn':(/verified/.test(rt)?' ok':''));r.textContent=rt;d.appendChild(r);}
  const s=document.createElement('span');s.textContent=t;d.appendChild(s);log.appendChild(d);log.scrollTop=log.scrollHeight;}
function setState(s){state=s;const m={listening:'listening',thinking:'thinking',speaking:'speaking',working:'working',idle:'standby'};
  stateLbl.textContent=m[s]||'standby';stateLbl.classList.toggle('active',s!=='idle');}
async function speak(t){setState('speaking');
  if(TTS_MODE==='elevenlabs'){try{const r=await fetch('/speak',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t})});
    if(r.ok){const blob=await r.blob();if(blob.size>0){const url=URL.createObjectURL(blob);const a=new Audio(url);a.playbackRate=1.7;
      a.onended=()=>{URL.revokeObjectURL(url);convo?listen():setState('idle');};a.onerror=()=>{convo?listen():setState('idle');};a.play();return;}}}catch(e){}}
  try{const u=new SpeechSynthesisUtterance(t);u.rate=1.7;const v=voices.find(x=>x.name===voiceSel.value);if(v)u.voice=v;
    u.onend=()=>{convo?listen():setState('idle');};u.onerror=()=>{convo?listen():setState('idle');};
    speechSynthesis.cancel();speechSynthesis.speak(u);}catch(e){if(convo)listen();}}
async function ask(t){add('you',t);try{rec&&rec.stop();}catch(e){}setState('thinking');const t0=performance.now();
  try{const r=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t,model:modelSel.value})});
    const j=await r.json();
    const used=(j.tools&&j.tools.length)?' · ↳ '+[...new Set(j.tools)].join(', '):'';
    add('jarvis',j.reply,((performance.now()-t0)/1000).toFixed(1)+'s · '+modelSel.value.replace('claude-','')+used+' · live, NOT verified');speak(j.reply);}
  catch(e){add('jarvis','(could not reach the server)');convo?listen():setState('idle');}}

/* ---- capability deck → real verifier-gated engines ---- */
document.querySelectorAll('.cap').forEach(b=>b.onclick=async()=>{
  const tool=b.dataset.tool;document.querySelectorAll('.cap').forEach(x=>x.disabled=true);setState('working');
  add('you','▸ '+b.querySelector('.tt').textContent);const t0=performance.now();
  try{const r=await fetch('/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({tool})});
    const j=await r.json();add('jarvis',j.result,((performance.now()-t0)/1000).toFixed(1)+'s · '+tool+' · verified');}
  catch(e){add('jarvis','(engine error)');}
  document.querySelectorAll('.cap').forEach(x=>x.disabled=false);setState('idle');refreshStatus();});

/* ---- voice loop ---- */
const SR=window.SpeechRecognition||window.webkitSpeechRecognition;let rec=null;
if(SR){rec=new SR();rec.lang='en-US';rec.continuous=true;rec.interimResults=true;
  rec.onresult=e=>{if(state!=='listening')return;let interim='';
    for(let i=e.resultIndex;i<e.results.length;i++){const r=e.results[i];if(r.isFinal)pending+=r[0].transcript+' ';else interim+=r[0].transcript;}
    stateLbl.textContent='listening · '+(pending+interim).trim().slice(-42);clearTimeout(timer);timer=setTimeout(finalize,SILENCE_MS);};
  rec.onend=()=>{if(convo&&state==='listening'){try{rec.start();}catch(e){}}};}
function finalize(){const t=pending.trim();pending='';if(!t)return;setState('thinking');try{rec.stop();}catch(e){}ask(t);}
function listen(){if(!convo)return;setState('listening');try{rec.start();}catch(e){}}
function startConvo(){if(!SR){add('jarvis','This browser has no speech recognition — use Chrome, or type below.');return;}
  convo=true;talk.classList.add('live');talkTxt.textContent='Stop';speechSynthesis.cancel();listen();}
function stopConvo(){convo=false;talk.classList.remove('live');talkTxt.textContent='Start conversation';
  try{rec.stop();}catch(e){}speechSynthesis.cancel();clearTimeout(timer);setState('idle');}
talk.onclick=()=>convo?stopConvo():startConvo();
form.onsubmit=e=>{e.preventDefault();const t=input.value.trim();if(t){input.value='';ask(t);}};
add('jarvis','Online. Honest about what is what: the CAPABILITIES on the right are verifier-gated — those results are proven. This conversation is me reasoning live (Opus 4.8) — it is NOT verified and I can be wrong, so call it out and I will check. Tools (weather, web, files) can also be off. Start a conversation, tap a capability, or type a command.');
</script></body></html>"""
