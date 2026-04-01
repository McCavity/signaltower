import threading
from collections import deque
from datetime import datetime

_lock = threading.Lock()

_towerstate: int = 0
_last_seen: datetime = datetime.fromtimestamp(0)
_last_started: datetime = datetime.now()
_request_log: deque = deque(maxlen=100)

_request_log.append({
    "timestamp": _last_started,
    "remote_addr": "127.0.0.1",
    "endpoint": None,
    "colour": "GREEN",
    "mode": "on",
})


def get_towerstate() -> int:
    with _lock:
        return _towerstate


def set_towerstate(val: int):
    global _towerstate
    with _lock:
        _towerstate = val


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
