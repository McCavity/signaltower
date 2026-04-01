from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Literal

import uvicorn
from fastapi import FastAPI, Request, Response
from pydantic import BaseModel, field_validator

from signaltower import state, watchdog


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


@app.get("/heartbeat")
def heartbeat():
    state.set_last_seen()
    return {"status": "ok"}


@app.get("/signal")
def get_signals():
    return state.get_requests()


@app.post("/signal", status_code=204)
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
