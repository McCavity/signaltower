import threading
import time
from datetime import datetime

from signaltower import hardware, state

COLOURS = {'BLUE': 1, 'WHITE': 2, 'AMBER': 4, 'RED': 8, 'GREEN': 16}
MANUAL_LAMPS = ('BLUE', 'WHITE')

# Half-periods in seconds for each blink mode
BLINK_HALF_PERIOD = {
    'slow_blink': 0.5,
    'fast_blink': 0.25,
}


def _blink_on(mode: str) -> bool:
    half = BLINK_HALF_PERIOD[mode]
    return int(time.time() / half) % 2 == 0


def _compute_bitmask() -> int:
    bitmask = 0

    for colour in MANUAL_LAMPS:
        mode = state.get_effective_lamp(colour)
        if mode == 'on' or (mode in BLINK_HALF_PERIOD and _blink_on(mode)):
            bitmask |= COLOURS[colour]

    elapsed = (datetime.now() - state.get_last_seen()).total_seconds()
    if elapsed > 300:
        bitmask |= COLOURS['RED']
    elif elapsed > 60:
        bitmask |= COLOURS['AMBER']
    else:
        bitmask |= COLOURS['GREEN']

    return bitmask


def _loop():
    last_bitmask = -1
    while True:
        bitmask = _compute_bitmask()
        if bitmask != last_bitmask:
            try:
                hardware.device.set_outputs(bitmask)
                last_bitmask = bitmask
            except hardware.K8055NotFoundError:
                pass
        time.sleep(0.1)


def start():
    t = threading.Thread(target=_loop, daemon=True)
    t.start()
