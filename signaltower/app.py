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
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Signal Tower</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#0d1117;color:#c9d1d9;min-height:100vh;display:flex;align-items:center;justify-content:center}
.page{padding:2rem}
h1{font-size:1.3rem;color:#f0f6fc;margin-bottom:2rem;letter-spacing:.06em;text-transform:uppercase}
.layout{display:flex;gap:3rem;align-items:flex-start}
.panel{display:flex;flex-direction:column;gap:.55rem}
.lamp-row{display:flex;align-items:center;gap:.75rem;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:.6rem 1rem;min-width:360px}
.dot{width:14px;height:14px;border-radius:50%;flex-shrink:0}
.lamp-name{font-size:.85rem;font-weight:600;width:54px;letter-spacing:.04em}
select,input[type=number]{background:#0d1117;color:#c9d1d9;border:1px solid #30363d;border-radius:6px;padding:4px 8px;font-size:.85rem}
input[type=number]{width:76px}
button{background:#238636;color:#fff;border:none;border-radius:6px;padding:5px 14px;font-size:.85rem;cursor:pointer;transition:background .15s}
button:hover{background:#2ea043}
.status-badge{font-size:.78rem;color:#8b949e;font-style:italic;margin-left:auto}
.dur-label{font-size:.78rem;color:#6e7681}
@keyframes slow-blink{0%,100%{opacity:1}50%{opacity:.08}}
@keyframes fast-blink{0%,100%{opacity:1}50%{opacity:.08}}
.slow-blink{animation:slow-blink 1.8s ease-in-out infinite}
.fast-blink{animation:fast-blink .45s ease-in-out infinite}
</style>
</head>
<body>
<div class="page">
<h1>&#9650; Signal Tower</h1>
<div class="layout">
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

  <div class="panel" id="panel"></div>
</div>
</div>

<script>
const KEY   = "__API_KEY__";
const LAMPS = ["BLUE","WHITE","AMBER","RED","GREEN"];
const CTRL  = ["BLUE","WHITE"];
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
    const sel = document.createElement("select");
    sel.id = "mode-"+c;
    MODES.forEach(m => sel.append(Object.assign(document.createElement("option"), {value:m, textContent:m.replace(/_/g," ")})));

    const lbl = Object.assign(document.createElement("span"), {className:"dur-label", textContent:"s:"});

    const dur = Object.assign(document.createElement("input"), {type:"number", id:"dur-"+c, value:-1, min:-1, title:"Duration in seconds (−1 = indefinite)"});
    dur.style.width = "76px";

    const btn = Object.assign(document.createElement("button"), {textContent:"Set"});
    btn.onclick = () => sendSignal(c);

    row.append(sel, lbl, dur, btn);
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
  await fetch("/signal?key="+KEY, {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify({colour, mode, duration: isNaN(raw)?-1:raw})
  });
  pollState();
}

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
    colour: Literal["BLUE", "WHITE"]
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
