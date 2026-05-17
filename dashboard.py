"""
HouseMusicSwarm Dashboard
Run: python dashboard.py
Open: http://localhost:8765
"""

import os
from datetime import datetime
from pathlib import Path

import httpx
import psutil
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

load_dotenv()

app = FastAPI(title="HouseMusicSwarm Dashboard")
OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>HouseMusicSwarm</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  body{background:#08080f;font-family:system-ui,sans-serif}
  .card{background:#10101c;border:1px solid #1c1c30;border-radius:12px;transition:border-color .2s}
  .card:hover{border-color:#6d28d9}
  .glow{box-shadow:0 0 14px rgba(109,40,217,.45);border-color:#7c3aed!important}
  .bar{height:8px;border-radius:999px;overflow:hidden;background:#1c1c30}
  .fill{height:100%;border-radius:999px;transition:width .6s ease}
  .dot{width:9px;height:9px;border-radius:50%;display:inline-block;flex-shrink:0}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
  .pulse{animation:pulse 2.2s infinite}
  .mono{font-family:ui-monospace,monospace}
  ::-webkit-scrollbar{width:4px}
  ::-webkit-scrollbar-track{background:#10101c}
  ::-webkit-scrollbar-thumb{background:#2d2d4e;border-radius:2px}
</style>
</head>
<body class="text-gray-200 p-5 min-h-screen">

<!-- ── Header ── -->
<div class="flex items-center justify-between mb-6">
  <div class="flex items-center gap-3">
    <span class="text-4xl select-none">🎵</span>
    <div>
      <h1 class="text-xl font-bold text-white tracking-tight">HouseMusicSwarm</h1>
      <p class="text-xs text-gray-600">OpenSwarm · Local AI Agent Dashboard</p>
    </div>
  </div>
  <div class="text-right">
    <div id="clock" class="text-xl mono text-violet-400 font-semibold"></div>
    <div id="date" class="text-xs text-gray-600 mt-0.5"></div>
  </div>
</div>

<!-- ── Status Strip ── -->
<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
  <div class="card p-4">
    <div class="text-xs text-gray-600 mb-2 uppercase tracking-wider">Ollama</div>
    <div class="flex items-center gap-2">
      <span id="o-dot" class="dot bg-gray-700"></span>
      <span id="o-status" class="text-sm font-semibold">checking…</span>
    </div>
    <div id="o-ver" class="text-xs text-gray-600 mt-1 mono"></div>
  </div>

  <div class="card p-4">
    <div class="text-xs text-gray-600 mb-2 uppercase tracking-wider">Active Model</div>
    <div id="cfg-model" class="text-sm font-semibold text-violet-400 truncate mono">—</div>
    <div id="loaded-model" class="text-xs text-gray-600 mt-1"></div>
  </div>

  <div class="card p-4">
    <div class="text-xs text-gray-600 mb-2 uppercase tracking-wider">CPU</div>
    <div class="flex justify-between text-xs mb-2">
      <span id="cpu-pct" class="font-semibold">0%</span>
      <span id="cpu-freq" class="text-gray-600 mono"></span>
    </div>
    <div class="bar"><div id="cpu-fill" class="fill bg-violet-600" style="width:0%"></div></div>
  </div>

  <div class="card p-4">
    <div class="text-xs text-gray-600 mb-2 uppercase tracking-wider">RAM</div>
    <div class="flex justify-between text-xs mb-2">
      <span id="ram-used" class="font-semibold">— GB</span>
      <span id="ram-tot" class="text-gray-600">/ — GB</span>
    </div>
    <div class="bar"><div id="ram-fill" class="fill bg-blue-600" style="width:0%"></div></div>
  </div>
</div>

<!-- ── Main Grid ── -->
<div class="grid grid-cols-1 lg:grid-cols-3 gap-4">

  <!-- Agents 2/3 -->
  <div class="lg:col-span-2">
    <div class="text-xs text-gray-600 uppercase tracking-wider mb-3">Agent Roster</div>
    <div id="agents" class="grid grid-cols-2 xl:grid-cols-4 gap-3"></div>
  </div>

  <!-- Sidebar 1/3 -->
  <div class="flex flex-col gap-4">

    <!-- Installed Models -->
    <div>
      <div class="text-xs text-gray-600 uppercase tracking-wider mb-3">Installed Models</div>
      <div id="models" class="flex flex-col gap-2">
        <p class="text-xs text-gray-700">Loading…</p>
      </div>
    </div>

    <!-- Config -->
    <div class="card p-4">
      <div class="text-xs text-gray-600 uppercase tracking-wider mb-3">Environment</div>
      <div class="space-y-2 text-xs">
        <div class="flex justify-between gap-2">
          <span class="text-gray-600 shrink-0">Model</span>
          <span id="env-model" class="text-violet-400 mono truncate">—</span>
        </div>
        <div class="flex justify-between gap-2">
          <span class="text-gray-600 shrink-0">Ollama URL</span>
          <span class="text-gray-400 mono">localhost:11434</span>
        </div>
        <div class="flex justify-between gap-2">
          <span class="text-gray-600 shrink-0">Agents</span>
          <span class="text-gray-400">8 specialists</span>
        </div>
        <div class="flex justify-between gap-2">
          <span class="text-gray-600 shrink-0">Framework</span>
          <span class="text-gray-400">Agency Swarm</span>
        </div>
      </div>
    </div>

    <!-- Launch -->
    <div class="card p-4">
      <div class="text-xs text-gray-600 uppercase tracking-wider mb-3">Launch Commands</div>
      <div class="space-y-2">
        <div class="text-xs mono bg-black/40 rounded-lg px-3 py-2 text-gray-400 select-all">python swarm.py</div>
        <div class="text-xs mono bg-black/40 rounded-lg px-3 py-2 text-gray-400 select-all">python server.py</div>
        <div class="text-xs mono bg-black/40 rounded-lg px-3 py-2 text-gray-400 select-all">ollama serve</div>
      </div>
    </div>

  </div>
</div>

<!-- ── Footer ── -->
<div class="mt-6 text-center text-xs text-gray-700">
  Refreshes every 3 s · <span id="last-update">—</span>
</div>

<script>
const AGENTS = [
  {name:"Orchestrator",   role:"Routes every request to the right specialist", icon:"🎯", c:"#7c3aed"},
  {name:"Virtual Asst",  role:"Email, calendar, Slack, 10k+ integrations",    icon:"🤖", c:"#2563eb"},
  {name:"Deep Research", role:"Web research with citations & sources",          icon:"🔬", c:"#059669"},
  {name:"Data Analyst",  role:"Charts, stats, IPython kernel",                  icon:"📊", c:"#d97706"},
  {name:"Slides Agent",  role:"HTML decks → PPTX export",                      icon:"📽️", c:"#dc2626"},
  {name:"Docs Agent",    role:"Word documents and PDFs",                        icon:"📄", c:"#6d28d9"},
  {name:"Image Agent",   role:"Generate & edit images (Gemini / fal.ai)",       icon:"🖼️", c:"#db2777"},
  {name:"Video Agent",   role:"Generate & edit video (Sora / Veo / Seedance)",  icon:"🎬", c:"#0891b2"},
];

// render agents once
const ag = document.getElementById('agents');
AGENTS.forEach(a => {
  const d = document.createElement('div');
  d.className = 'card p-4 flex flex-col gap-2';
  d.innerHTML = `
    <span class="text-2xl">${a.icon}</span>
    <span class="text-sm font-semibold text-white leading-tight">${a.name}</span>
    <span class="text-xs text-gray-600 leading-snug">${a.role}</span>
    <div class="flex items-center gap-1.5 mt-auto pt-1">
      <span class="dot pulse" style="background:${a.c}"></span>
      <span class="text-xs text-gray-700">ready</span>
    </div>`;
  ag.appendChild(d);
});

// clock
function tick(){
  const n=new Date();
  document.getElementById('clock').textContent=n.toLocaleTimeString();
  document.getElementById('date').textContent=n.toLocaleDateString(undefined,{weekday:'long',month:'long',day:'numeric',year:'numeric'});
}
tick(); setInterval(tick,1000);

// status
async function pollStatus(){
  try{
    const d=await fetch('/api/status').then(r=>r.json());
    document.getElementById('o-dot').className='dot '+(d.ollama_ok?'bg-green-500':'bg-red-500');
    document.getElementById('o-status').textContent=d.ollama_ok?'Connected':'Offline';
    document.getElementById('o-ver').textContent=d.ollama_ok?'v'+d.ollama_version:'run: ollama serve';
    const m=d.default_model.replace('ollama/','');
    document.getElementById('cfg-model').textContent=m;
    document.getElementById('env-model').textContent=m;
    document.getElementById('loaded-model').textContent=d.loaded_model?'▶ '+d.loaded_model+' in RAM':'idle — loads on first call';
    const c=d.cpu_pct;
    document.getElementById('cpu-pct').textContent=c+'%';
    document.getElementById('cpu-freq').textContent=d.cpu_freq_ghz?d.cpu_freq_ghz+' GHz':'';
    document.getElementById('cpu-fill').style.width=c+'%';
    document.getElementById('cpu-fill').className='fill '+(c>80?'bg-red-500':c>55?'bg-yellow-500':'bg-violet-600');
    document.getElementById('ram-used').textContent=d.ram_used_gb+' GB';
    document.getElementById('ram-tot').textContent='/ '+d.ram_total_gb+' GB';
    document.getElementById('ram-fill').style.width=d.ram_pct+'%';
    document.getElementById('ram-fill').className='fill '+(d.ram_pct>85?'bg-red-500':d.ram_pct>65?'bg-yellow-500':'bg-blue-600');
    document.getElementById('last-update').textContent='Last updated '+d.ts;
  }catch(e){
    document.getElementById('o-status').textContent='dashboard error';
  }
}

// models
async function pollModels(){
  try{
    const d=await fetch('/api/models').then(r=>r.json());
    const el=document.getElementById('models');
    if(!d.models.length){el.innerHTML='<p class="text-xs text-gray-700">Ollama offline or no models</p>';return;}
    el.innerHTML=d.models.map(m=>`
      <div class="card p-3 flex items-center justify-between ${m.active?'glow':''}">
        <div class="min-w-0">
          <div class="text-xs font-semibold truncate ${m.active?'text-violet-400':'text-gray-300'}">${m.name}</div>
          <div class="text-xs text-gray-700 mono">${m.size_gb} GB</div>
        </div>
        ${m.active
          ? '<span class="text-xs font-bold text-violet-400 shrink-0 ml-2">ACTIVE</span>'
          : `<button onclick="switchModel('${m.name}')" class="text-xs text-gray-600 hover:text-white shrink-0 ml-2 px-2 py-1 rounded hover:bg-violet-900/50 transition-colors">USE</button>`}
      </div>`).join('');
  }catch(e){}
}

async function switchModel(name){
  await fetch('/api/switch/'+encodeURIComponent(name),{method:'POST'});
  await Promise.all([pollModels(),pollStatus()]);
}

pollStatus(); pollModels();
setInterval(pollStatus,3000);
setInterval(pollModels,10000);
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def root():
    return _HTML


@app.get("/api/status")
async def api_status():
    ollama_ok = False
    ollama_version = "—"
    loaded_model = None
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get(f"{OLLAMA_BASE}/api/version")
            if r.status_code == 200:
                ollama_ok = True
                ollama_version = r.json().get("version", "—")
            ps = await client.get(f"{OLLAMA_BASE}/api/ps")
            if ps.status_code == 200:
                ms = ps.json().get("models", [])
                if ms:
                    loaded_model = ms[0].get("name")
    except Exception:
        pass

    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    try:
        freq = psutil.cpu_freq()
        cpu_freq_ghz = round(freq.current / 1000, 2) if freq else None
    except Exception:
        cpu_freq_ghz = None

    return {
        "ollama_ok": ollama_ok,
        "ollama_version": ollama_version,
        "loaded_model": loaded_model,
        "default_model": os.getenv("DEFAULT_MODEL", "not set"),
        "cpu_pct": cpu,
        "cpu_freq_ghz": cpu_freq_ghz,
        "ram_used_gb": round(mem.used / 1e9, 1),
        "ram_total_gb": round(mem.total / 1e9, 1),
        "ram_pct": round(mem.percent, 1),
        "ts": datetime.now().strftime("%H:%M:%S"),
    }


@app.get("/api/models")
async def api_models():
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{OLLAMA_BASE}/api/tags")
            if r.status_code == 200:
                current = os.getenv("DEFAULT_MODEL", "").replace("ollama/", "")
                return {
                    "models": [
                        {
                            "name": m["name"],
                            "size_gb": round(m.get("size", 0) / 1e9, 1),
                            "active": (
                                m["name"] == current
                                or m["name"].split(":")[0] == current.split(":")[0]
                            ),
                        }
                        for m in r.json().get("models", [])
                    ]
                }
    except Exception:
        pass
    return {"models": []}


@app.post("/api/switch/{model_name:path}")
async def api_switch(model_name: str):
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        lines = env_path.read_text().splitlines()
        new_lines, found = [], False
        for line in lines:
            if line.startswith("DEFAULT_MODEL="):
                new_lines.append(f"DEFAULT_MODEL=ollama/{model_name}")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"DEFAULT_MODEL=ollama/{model_name}")
        env_path.write_text("\n".join(new_lines) + "\n")
    os.environ["DEFAULT_MODEL"] = f"ollama/{model_name}"
    return {"ok": True, "model": f"ollama/{model_name}"}


if __name__ == "__main__":
    print("\n  HouseMusicSwarm Dashboard")
    print("  Open → http://localhost:8765\n")
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="warning")
