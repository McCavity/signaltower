import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Literal

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, field_validator

from signaltower import state, watchdog

_api_key_header = APIKeyHeader(name="X-API-Key")


def _require_api_key(key: str = Depends(_api_key_header)):
    expected = os.environ.get("SIGNALTOWER_API_KEY", "")
    if not expected or not secrets.compare_digest(key, expected):
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


def main():
    uvicorn.run("signaltower.app:app", host="0.0.0.0", port=5000)
