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


def get_requests() -> list:
    with _lock:
        return list(_request_log)
