import json
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Literal

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import APIKeyHeader, APIKeyQuery
from pydantic import BaseModel, field_validator

from signaltower import state, watchdog

_UI_HTML = """\
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Signaltower</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@1,9..144,400;1,9..144,500&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{
  --tiefsee:#152C45;--tiefwasser:#1B3A5C;--kartenpapier:#F5F0E8;--vergilbt:#D8D0BC;
  --flachwasser:#7FB5B0;--kuestenblau:#3A7CA5;--kompassrose:#B8860B;--gefahrenmark:#C0392B;
  --rule:rgba(245,240,232,.18);--rule-strong:rgba(245,240,232,.42);
  --font-display:'Fraunces','Libre Caslon Text',ui-serif,Georgia,serif;
  --font-body:'Inter',-apple-system,system-ui,'Segoe UI',sans-serif;
  --font-mono:'JetBrains Mono','SFMono-Regular',Menlo,Consolas,monospace;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:var(--font-body);background:var(--tiefsee);color:var(--vergilbt);min-height:100vh;display:flex;align-items:center;justify-content:center;font-size:15px;line-height:1.6;-webkit-font-smoothing:antialiased}
.page{padding:32px 48px;max-width:920px;width:100%}
.kicker{font-family:var(--font-body);font-weight:500;font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--flachwasser);margin-bottom:8px}
h1{font-family:var(--font-display);font-style:italic;font-weight:400;font-size:32px;line-height:1.15;letter-spacing:-.005em;color:var(--kartenpapier);margin:0 0 32px}
.layout{display:flex;gap:48px;align-items:flex-start}
.panel{display:flex;flex-direction:column;gap:6px;flex:1;min-width:380px}
.lamp-row{display:flex;align-items:center;gap:12px;background:var(--tiefwasser);border:1px solid var(--rule);border-radius:4px;padding:10px 16px}
.dot{width:14px;height:14px;border-radius:50%;flex-shrink:0;box-shadow:inset 0 0 0 1px var(--rule)}
.lamp-name{font-family:var(--font-mono);font-weight:500;font-size:12px;width:64px;letter-spacing:.04em}
select,input[type=number]{font-family:var(--font-body);background:var(--tiefsee);color:var(--vergilbt);border:1px solid var(--rule);border-radius:4px;padding:5px 8px;font-size:13px}
select:focus,input[type=number]:focus{outline:none;border-color:var(--flachwasser)}
input[type=number]{width:80px;font-family:var(--font-mono);font-feature-settings:'tnum' 1}
.dur-label{font-family:var(--font-mono);font-size:11px;color:var(--flachwasser);letter-spacing:.05em}
.status-badge{font-family:var(--font-mono);font-size:11px;color:var(--flachwasser);margin-left:auto;letter-spacing:.04em}
.row-pad{display:flex;align-items:center;gap:10px;margin-left:auto}
.actions{margin-top:18px;display:flex;justify-content:flex-end}
button.set-all{font-family:var(--font-body);font-weight:600;font-size:13px;letter-spacing:.04em;background:var(--kompassrose);color:var(--tiefsee);border:none;border-radius:4px;padding:10px 22px;cursor:pointer;transition:background var(--dur-fast,120ms) ease,transform var(--dur-fast,120ms) ease;text-transform:uppercase;box-shadow:0 1px 0 rgba(0,0,0,.18)}
button.set-all:hover{background:#d4a017}
button.set-all:active{transform:translateY(1px)}
button.set-all:disabled{opacity:.5;cursor:wait}
.tower-wrap{padding:16px 16px 12px;background:var(--tiefwasser);border:1px solid var(--rule);border-radius:4px}
.caption{font-family:var(--font-mono);font-size:10.5px;color:var(--flachwasser);text-align:center;letter-spacing:.05em;margin-top:8px}
@keyframes slow-blink{0%,100%{opacity:1}50%{opacity:.08}}
@keyframes fast-blink{0%,100%{opacity:1}50%{opacity:.08}}
.slow-blink{animation:slow-blink 1.8s ease-in-out infinite}
.fast-blink{animation:fast-blink .45s ease-in-out infinite}
::selection{background:var(--kompassrose);color:var(--kartenpapier)}
</style>
</head>
<body>
<div class="page">
<div class="kicker">Status · Steuerung</div>
<h1>Signaltower</h1>
<div class="layout">
  <div class="tower-wrap">
  <svg width="100" height="340" viewBox="0 0 100 340" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <linearGradient id="gBLUE_on"  x1="0" y1="0" x2="1" y2="0"><stop offset="0%"   stop-color="#82b4ff"/><stop offset="40%" stop-color="#2979ff"/><stop offset="100%" stop-color="#1a55cc"/></linearGradient>
      <linearGradient id="gWHITE_on" x1="0" y1="0" x2="1" y2="0"><stop offset="0%"   stop-color="#ffffff"/><stop offset="40%" stop-color="#e8e8e8"/><stop offset="100%" stop-color="#b8b8b8"/></linearGradient>
      <linearGradient id="gAMBER_on" x1="0" y1="0" x2="1" y2="0"><stop offset="0%"   stop-color="#ffd060"/><stop offset="40%" stop-color="#ffab00"/><stop offset="100%" stop-color="#cc8800"/></linearGradient>
      <linearGradient id="gRED_on"   x1="0" y1="0" x2="1" y2="0"><stop offset="0%"   stop-color="#ff8070"/><stop offset="40%" stop-color="#f44336"/><stop offset="100%" stop-color="#b71c1c"/></linearGradient>
      <linearGradient id="gGREEN_on" x1="0" y1="0" x2="1" y2="0"><stop offset="0%"   stop-color="#69f0ae"/><stop offset="40%" stop-color="#00e676"/><stop offset="100%" stop-color="#00a050"/></linearGradient>
      <linearGradient id="gBLUE_off"  x1="0" y1="0" x2="1" y2="0"><stop offset="0%"  stop-color="#1a1d2e"/><stop offset="100%" stop-color="#0d0f1a"/></linearGradient>
      <linearGradient id="gWHITE_off" x1="0" y1="0" x2="1" y2="0"><stop offset="0%"  stop-color="#2c2c2c"/><stop offset="100%" stop-color="#1a1a1a"/></linearGradient>
      <linearGradient id="gAMBER_off" x1="0" y1="0" x2="1" y2="0"><stop offset="0%"  stop-color="#2a1e0a"/><stop offset="100%" stop-color="#1a1206"/></linearGradient>
      <linearGradient id="gRED_off"   x1="0" y1="0" x2="1" y2="0"><stop offset="0%"  stop-color="#2a1010"/><stop offset="100%" stop-color="#1a0808"/></linearGradient>
      <linearGradient id="gGREEN_off" x1="0" y1="0" x2="1" y2="0"><stop offset="0%"  stop-color="#0d2010"/><stop offset="100%" stop-color="#081408"/></linearGradient>
    </defs>
    <!-- top cap -->
    <rect x="37" y="4"  width="26" height="14" rx="4" fill="#252525"/>
    <rect x="26" y="16" width="48" height="10" rx="3" fill="#1e1e1e"/>
    <!-- lamp modules: BLUE WHITE AMBER RED GREEN (top → bottom) -->
    <rect id="mod-BLUE"  x="8" y="26"  width="84" height="52" rx="10" fill="url(#gBLUE_off)"  stroke="#333" stroke-width="1"/>
    <rect id="mod-WHITE" x="8" y="82"  width="84" height="52" rx="10" fill="url(#gWHITE_off)" stroke="#333" stroke-width="1"/>
    <rect id="mod-AMBER" x="8" y="138" width="84" height="52" rx="10" fill="url(#gAMBER_off)" stroke="#333" stroke-width="1"/>
    <rect id="mod-RED"   x="8" y="194" width="84" height="52" rx="10" fill="url(#gRED_off)"   stroke="#333" stroke-width="1"/>
    <rect id="mod-GREEN" x="8" y="250" width="84" height="52" rx="10" fill="url(#gGREEN_off)" stroke="#333" stroke-width="1"/>
    <!-- base -->
    <rect x="26" y="304" width="48" height="14" rx="3" fill="#1e1e1e"/>
    <rect x="14" y="316" width="72" height="20" rx="5" fill="#252525"/>
  </svg>
  <div class="caption">K8055 · rbhapp01</div>
  </div>

  <div style="flex:1">
    <div class="panel" id="panel"></div>
    <div class="actions">
      <button id="set-all" class="set-all">Lampen setzen</button>
    </div>
  </div>
</div>
</div>

<script>
const KEY   = "__API_KEY__";
const LAMPS = ["BLUE","WHITE","AMBER","RED","GREEN"];
const CTRL  = ["BLUE","WHITE","AMBER"];
const MODES = ["off","on","slow_blink","fast_blink"];
const ACTIVE= {BLUE:"#2979ff",WHITE:"#e0e0e0",AMBER:"#ffab00",RED:"#f44336",GREEN:"#00e676"};
const DIM   = {BLUE:"#1a1d2e",WHITE:"#2a2a2a",AMBER:"#2a1e0a",RED:"#2a1010",GREEN:"#0d2010"};

const panel = document.getElementById("panel");
LAMPS.forEach(c => {
  const row  = document.createElement("div");
  row.className = "lamp-row";

  const dot  = Object.assign(document.createElement("div"), {id:"dot-"+c, className:"dot"});
  dot.style.background = DIM[c];

  const name = Object.assign(document.createElement("div"), {className:"lamp-name", textContent:c});
  name.style.color = ACTIVE[c];

  row.append(dot, name);

  if (CTRL.includes(c)) {
    const pad = Object.assign(document.createElement("div"), {className:"row-pad"});

    const sel = document.createElement("select");
    sel.id = "mode-"+c;
    MODES.forEach(m => sel.append(Object.assign(document.createElement("option"), {value:m, textContent:m.replace(/_/g," ")})));

    const lbl = Object.assign(document.createElement("span"), {className:"dur-label", textContent:"s"});

    const dur = Object.assign(document.createElement("input"), {type:"number", id:"dur-"+c, value:-1, min:-1, title:"Duration in seconds (−1 = indefinite)"});

    pad.append(sel, lbl, dur);
    row.appendChild(pad);
  } else {
    const badge = Object.assign(document.createElement("span"), {id:"status-"+c, className:"status-badge", textContent:"off"});
    row.appendChild(badge);
  }

  panel.appendChild(row);
});

function applyMode(colour, mode) {
  const mod = document.getElementById("mod-"+colour);
  const dot = document.getElementById("dot-"+colour);
  const on  = mode !== "off";
  mod.classList.remove("slow-blink","fast-blink");
  dot.classList.remove("slow-blink","fast-blink");
  mod.setAttribute("fill","url(#g"+colour+(on?"_on":"_off")+")");
  dot.style.background = on ? ACTIVE[colour] : DIM[colour];
  if (mode==="slow_blink"){mod.classList.add("slow-blink");dot.classList.add("slow-blink");}
  if (mode==="fast_blink"){mod.classList.add("fast-blink");dot.classList.add("fast-blink");}
  const badge = document.getElementById("status-"+colour);
  if (badge) badge.textContent = mode.replace(/_/g," ");
}

async function pollState() {
  try {
    const r = await fetch("/lamps?key="+KEY);
    if (r.ok) { const d = await r.json(); LAMPS.forEach(c => applyMode(c, d[c]||"off")); }
  } catch(_){}
}

async function sendSignal(colour) {
  const mode = document.getElementById("mode-"+colour).value;
  const raw  = parseInt(document.getElementById("dur-"+colour).value, 10);
  return fetch("/signal?key="+KEY, {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({colour, mode, duration: isNaN(raw)?-1:raw})
  });
}

async function submitAll() {
  const btn = document.getElementById("set-all");
  btn.disabled = true;
  try {
    await Promise.all(CTRL.map(sendSignal));
    await pollState();
  } finally {
    btn.disabled = false;
  }
}

document.getElementById("set-all").addEventListener("click", submitAll);

pollState();
setInterval(pollState, 2000);
</script>
</body>
</html>
"""

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_api_key_query = APIKeyQuery(name="key", auto_error=False)


def _require_api_key(
    header_key: str | None = Depends(_api_key_header),
    query_key: str | None = Depends(_api_key_query),
):
    expected = os.environ.get("SIGNALTOWER_API_KEY", "")
    key = header_key or query_key
    if not expected or not key or not secrets.compare_digest(key, expected):
        raise HTTPException(status_code=403, detail="Invalid or missing API key")


class SignalRequest(BaseModel):
    colour: Literal["BLUE", "WHITE", "AMBER"]
    mode: Literal["off", "on", "slow_blink", "fast_blink"]
    duration: int | None = None

    @field_validator("duration")
    @classmethod
    def validate_duration(cls, v: int | None) -> int | None:
        if v == 0:
            raise ValueError("duration must be > 0 or -1 (indefinite), not 0")
        return v


@asynccontextmanager
async def lifespan(app: FastAPI):
    watchdog.start()
    yield


app = FastAPI(lifespan=lifespan)


def _serializable(obj):
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if isinstance(obj, dict):
        return {k: _serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serializable(i) for i in obj]
    return obj


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    if request.method == "POST" and request.url.path == "/signal":
        try:
            raw = await request.body()
            payload = json.loads(raw) if raw else None
        except Exception:
            payload = None
        state.append_request({
            "timestamp": datetime.now(),
            "remote_addr": request.client.host if request.client else "unknown",
            "endpoint": "/signal",
            "error": "validation_error",
            "validation_errors": _serializable(exc.errors()),
            "payload": payload,
        })
    return JSONResponse(status_code=422, content=_serializable({"detail": exc.errors()}))


@app.get("/heartbeat", dependencies=[Depends(_require_api_key)])
def heartbeat():
    state.set_last_seen()
    return {"status": "ok"}


@app.get("/signal", dependencies=[Depends(_require_api_key)])
def get_signals():
    return state.get_requests()


@app.post("/signal", status_code=204, dependencies=[Depends(_require_api_key)])
def switch_signal(body: SignalRequest, request: Request):
    if body.duration is not None and body.duration > 0:
        expires_at = datetime.now() + timedelta(seconds=body.duration)
    else:
        expires_at = None

    state.append_request({
        "timestamp": datetime.now(),
        "remote_addr": request.client.host,
        "endpoint": "/signal",
        "colour": body.colour,
        "mode": body.mode,
        "duration": body.duration,
    })
    state.set_lamp(body.colour, body.mode, expires_at)
    return Response(status_code=204)


@app.get("/lamps", dependencies=[Depends(_require_api_key)])
def get_lamps():
    return state.get_all_lamps()


@app.get("/ui", response_class=HTMLResponse)
def ui(
    _: None = Depends(_require_api_key),
    key: str | None = Depends(_api_key_query),
    header_key: str | None = Depends(_api_key_header),
):
    api_key = key or header_key or ""
    return HTMLResponse(_UI_HTML.replace("__API_KEY__", api_key))


def main():
    uvicorn.run("signaltower.app:app", host="0.0.0.0", port=5000)
