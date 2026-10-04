import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime

_lock = threading.Lock()


@dataclass
class LampState:
    mode: str = 'off'
    expires_at: datetime | None = None


_lamp_states: dict[str, LampState] = {
    colour: LampState() for colour in ('BLUE', 'WHITE', 'AMBER', 'RED', 'GREEN')
}

_last_seen: datetime = datetime.fromtimestamp(0)
_request_log: deque = deque(maxlen=100)

# Liveness of the watchdog thread, as monotonic timestamps.
_loop_tick: float | None = None
_last_write_ok: float | None = None

# /health fails when the loop has not ticked for this long (it ticks at 10 Hz) …
LOOP_STALE_S = 3.0
# … or when the tower was not written successfully for this long
# (the watchdog rewrites every 5 s, so three missed rewrites).
WRITE_STALE_S = 15.0


def set_lamp(colour: str, mode: str, expires_at: datetime | None):
    with _lock:
        _lamp_states[colour] = LampState(mode=mode, expires_at=expires_at)


def get_effective_lamp(colour: str) -> str:
    """Returns current mode, atomically expiring the lamp if its timer has elapsed."""
    now = datetime.now()
    with _lock:
        s = _lamp_states[colour]
        if s.expires_at is not None and now >= s.expires_at:
            _lamp_states[colour] = LampState()
            return 'off'
        return s.mode


def get_last_seen() -> datetime:
    with _lock:
        return _last_seen


def set_last_seen():
    global _last_seen
    with _lock:
        _last_seen = datetime.now()


def append_request(entry: dict):
    with _lock:
        _request_log.append(entry)


def get_all_lamps() -> dict:
    """Returns current effective mode for every lamp, expiring elapsed timers.
    BLUE/WHITE/AMBER are manual; GREEN/RED are derived from heartbeat elapsed
    time (120 s threshold), mirroring the watchdog."""
    now = datetime.now()
    with _lock:
        result = {}
        for colour in ("BLUE", "WHITE", "AMBER"):
            s = _lamp_states[colour]
            if s.expires_at is not None and now >= s.expires_at:
                _lamp_states[colour] = LampState()
                result[colour] = "off"
            else:
                result[colour] = s.mode
        elapsed = (now - _last_seen).total_seconds()
        result["GREEN"] = "on" if elapsed < 120 else "off"
        result["RED"]   = "on" if elapsed >= 120 else "off"
    return result


def record_loop_tick(now: float):
    global _loop_tick
    with _lock:
        _loop_tick = now


def record_write_ok(now: float):
    global _last_write_ok
    with _lock:
        _last_write_ok = now


def health(now: float) -> dict:
    """Is the tower really being driven? Ages in seconds, ``None`` = never."""
    with _lock:
        loop_age = None if _loop_tick is None else round(now - _loop_tick, 1)
        write_age = None if _last_write_ok is None else round(now - _last_write_ok, 1)
    ok = (
        loop_age is not None and loop_age <= LOOP_STALE_S
        and write_age is not None and write_age <= WRITE_STALE_S
    )
    return {"status": "ok" if ok else "fail", "loop_age_s": loop_age, "write_age_s": write_age}


def get_requests() -> list:
    with _lock:
        return list(_request_log)
