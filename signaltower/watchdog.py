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

# A zone change (GREEN→AMBER→RED or back) must be seen for this many
# consecutive ticks before it is committed to hardware.  At 0.1 s per tick,
# 5 ticks = 0.5 s of stability required.  This prevents brief threshold
# crossings (e.g. a heartbeat that is a fraction of a second late) from
# causing a visible flicker.
_ZONE_DEBOUNCE_TICKS = 5


def _blink_on(mode: str) -> bool:
    half = BLINK_HALF_PERIOD[mode]
    return int(time.time() / half) % 2 == 0


def _current_zone(elapsed: float) -> str:
    if elapsed > 300:
        return 'RED'
    if elapsed > 60:
        return 'AMBER'
    return 'GREEN'


def _loop():
    last_bitmask = -1
    committed_zone = None   # last zone written to hardware
    zone_candidate = None   # zone we're waiting to confirm
    zone_ticks = 0

    while True:
        # --- manual lamps (BLUE / WHITE) ---
        bitmask = 0
        for colour in MANUAL_LAMPS:
            mode = state.get_effective_lamp(colour)
            if mode == 'on' or (mode in BLINK_HALF_PERIOD and _blink_on(mode)):
                bitmask |= COLOURS[colour]

        # --- watchdog zone (GREEN / AMBER / RED) with debounce ---
        elapsed = (datetime.now() - state.get_last_seen()).total_seconds()
        new_zone = _current_zone(elapsed)

        if committed_zone is None:
            committed_zone = new_zone           # first tick: commit immediately
        elif new_zone == committed_zone:
            zone_candidate = None               # stable – cancel any pending change
            zone_ticks = 0
        else:
            if new_zone == zone_candidate:
                zone_ticks += 1
                if zone_ticks >= _ZONE_DEBOUNCE_TICKS:
                    committed_zone = new_zone   # sustained long enough: commit
                    zone_candidate = None
                    zone_ticks = 0
            else:
                zone_candidate = new_zone       # new candidate, start counting
                zone_ticks = 1

        bitmask |= COLOURS[committed_zone]

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
