from contextlib import asynccontextmanager
from datetime import datetime
from time import sleep
from typing import Literal

import uvicorn
from fastapi import FastAPI, Request, Response
from pydantic import BaseModel, field_validator

from signaltower import hardware, state, watchdog

COLOURS = {"BLUE": 1, "WHITE": 2, "AMBER": 4, "RED": 8, "GREEN": 16}


def _apply(bitmask: int):
    state.set_towerstate(bitmask)
    try:
        hardware.device.set_outputs(bitmask)
    except hardware.K8055NotFoundError:
        pass


def switch(colour: str, mode: str, interval: int):
    bit = COLOURS[colour]
    current = state.get_towerstate()
    if mode == "on":
        if not current & bit:
            _apply(current ^ bit)
    elif mode == "off":
        if current & bit:
            _apply(current ^ bit)
    elif mode == "blink":
        pass
    elif mode == "once":
        if not current & bit:
            _apply(current ^ bit)
            sleep(interval / 1000)
            _apply(state.get_towerstate() ^ bit)


class SignalRequest(BaseModel):
    colour: Literal["BLUE", "WHITE", "AMBER", "RED", "GREEN"]
    mode: str
    interval: int = 0

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, v: str) -> str:
        normalised = v.lower()
        if normalised not in ("on", "off", "blink", "once"):
            raise ValueError(f"mode must be one of on/off/blink/once, got '{v}'")
        return normalised


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
    entry = {
        "timestamp": datetime.now(),
        "remote_addr": request.client.host,
        "endpoint": "/signal",
        "colour": body.colour,
        "mode": body.mode,
        "interval": body.interval,
    }
    state.append_request(entry)
    switch(body.colour, body.mode, body.interval)
    return Response(status_code=204)


def main():
    uvicorn.run("signaltower.app:app", host="0.0.0.0", port=5000)
