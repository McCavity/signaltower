import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime

from signaltower import hardware, state

log = logging.getLogger(__name__)

COLOURS = {'BLUE': 1, 'WHITE': 2, 'AMBER': 4, 'RED': 8, 'GREEN': 16}
MANUAL_LAMPS = ('BLUE', 'WHITE', 'AMBER')

# Heartbeat freshness threshold. Below: GREEN; at or above: RED.
# 120 s tolerates ~2 missed minute-ticks from the upstream heartbeat script
# (e.g. ioBroker timer jitter) before signalling outage.
_HEARTBEAT_TIMEOUT_S = 120

# Half-periods in seconds for each blink mode
BLINK_HALF_PERIOD = {
    'slow_blink': 0.5,
    'fast_blink': 0.25,
}

# A zone change (GREEN ↔ RED) must be seen for this many consecutive ticks
# before it is committed to hardware. At 0.1 s per tick, 5 ticks = 0.5 s
# of stability required. Prevents brief threshold crossings from causing
# visible flicker.
_ZONE_DEBOUNCE_TICKS = 5

# Rewrite the current bitmask at least this often, even if nothing changed.
# A write that silently got lost (board reset, USB hiccup) heals by itself.
REASSERT_INTERVAL_S = 5.0

# While a fault persists, repeat the warning at most this often (the loop
# runs at 10 Hz and would otherwise flood the journal).
ERROR_LOG_INTERVAL_S = 60.0

# After a failed write, wait this long before the next attempt. Reconnecting
# at 10 Hz would hammer the bus and may reset the board's outputs (flicker).
RETRY_BACKOFF_S = 1.0


def _blink_on(mode: str) -> bool:
    half = BLINK_HALF_PERIOD[mode]
    return int(time.time() / half) % 2 == 0


def _current_zone(elapsed: float) -> str:
    return 'RED' if elapsed >= _HEARTBEAT_TIMEOUT_S else 'GREEN'


@dataclass
class LoopContext:
    last_bitmask: int = -1
    committed_zone: str | None = None   # last zone written to hardware
    zone_candidate: str | None = None   # zone we're waiting to confirm
    zone_ticks: int = 0
    last_write: float | None = None     # monotonic time of last successful write
    last_error_log: float | None = None # monotonic time of last logged fault
    failing: bool = False
    retry_after: float = 0.0            # no write attempt before this time


def tick(ctx: LoopContext, now: float):
    """One pass of the watchdog loop. ``now`` is a monotonic timestamp."""
    # --- manual lamps (BLUE / WHITE) ---
    bitmask = 0
    for colour in MANUAL_LAMPS:
        mode = state.get_effective_lamp(colour)
        if mode == 'on' or (mode in BLINK_HALF_PERIOD and _blink_on(mode)):
            bitmask |= COLOURS[colour]

    # --- watchdog zone (GREEN / AMBER / RED) with debounce ---
    elapsed = (datetime.now() - state.get_last_seen()).total_seconds()
    new_zone = _current_zone(elapsed)

    if ctx.committed_zone is None:
        ctx.committed_zone = new_zone           # first tick: commit immediately
    elif new_zone == ctx.committed_zone:
        ctx.zone_candidate = None               # stable – cancel any pending change
        ctx.zone_ticks = 0
    else:
        if new_zone == ctx.zone_candidate:
            ctx.zone_ticks += 1
            if ctx.zone_ticks >= _ZONE_DEBOUNCE_TICKS:
                ctx.committed_zone = new_zone   # sustained long enough: commit
                ctx.zone_candidate = None
                ctx.zone_ticks = 0
        else:
            ctx.zone_candidate = new_zone       # new candidate, start counting
            ctx.zone_ticks = 1

    bitmask |= COLOURS[ctx.committed_zone]

    due = ctx.last_write is None or now - ctx.last_write >= REASSERT_INTERVAL_S
    if (bitmask != ctx.last_bitmask or due) and now >= ctx.retry_after:
        try:
            hardware.device.set_outputs(bitmask)
            ctx.last_bitmask = bitmask
            ctx.last_write = now
            state.record_write_ok(now)
            if ctx.failing:
                log.info("K8055 write recovered")
                ctx.failing = False
                ctx.last_error_log = None
        except hardware.K8055NotFoundError as exc:
            ctx.retry_after = now + RETRY_BACKOFF_S
            _log_fault(ctx, now, "K8055 not found: %s", exc)
        except Exception as exc:
            # A single USB timeout killed this thread on 2026-10-02 and froze
            # the tower for 34 h while the API kept answering. Drop the handle
            # so the next tick reconnects and writes again.
            hardware.device.reset()
            ctx.retry_after = now + RETRY_BACKOFF_S
            _log_fault(ctx, now, "K8055 write failed: %r", exc)


def _log_fault(ctx: LoopContext, now: float, msg: str, *args, **kwargs):
    ctx.failing = True
    if ctx.last_error_log is None or now - ctx.last_error_log >= ERROR_LOG_INTERVAL_S:
        log.warning(msg, *args, **kwargs)
        ctx.last_error_log = now


def step(ctx: LoopContext, now: float):
    """Run one tick; nothing raised in here may end the watchdog thread."""
    state.record_loop_tick(now)
    try:
        tick(ctx, now)
    except Exception:
        _log_fault(ctx, now, "watchdog tick failed", exc_info=True)


def _loop():
    ctx = LoopContext()
    while True:
        step(ctx, time.monotonic())
        time.sleep(0.1)


def start():
    t = threading.Thread(target=_loop, daemon=True)
    t.start()
