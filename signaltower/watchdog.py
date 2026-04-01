import threading
from datetime import datetime
from time import sleep

from signaltower import state, hardware

COLOURS = {"BLUE": 1, "WHITE": 2, "AMBER": 4, "RED": 8, "GREEN": 16}


def _apply(bitmask: int):
    state.set_towerstate(bitmask)
    try:
        hardware.device.set_outputs(bitmask)
    except hardware.K8055NotFoundError:
        pass


def _watchdog_loop():
    while True:
        elapsed = (datetime.now() - state.get_last_seen()).total_seconds()
        current = state.get_towerstate()
        if elapsed > 300:
            target = COLOURS["RED"]
        elif elapsed > 60:
            target = COLOURS["AMBER"]
        else:
            target = COLOURS["GREEN"]
        mask = COLOURS["RED"] | COLOURS["AMBER"] | COLOURS["GREEN"]
        new_state = (current & ~mask) | target
        if new_state != current:
            _apply(new_state)
        sleep(10)


def start():
    t = threading.Thread(target=_watchdog_loop, daemon=True)
    t.start()
