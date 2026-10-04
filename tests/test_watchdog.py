"""Watchdog-Härtung nach dem Ausfall vom 02.10.2026.

Damals beendete ein einzelner ``usb.core.USBTimeoutError`` den Schreib-Thread.
Der Prozess lebte weiter, die API meldete den Soll-Zustand, die Säule blieb
eingefroren. Diese Tests stellen genau das nach.
"""

from fakes import FakeDevice, usb_timeout as _timeout
from signaltower import hardware, state, watchdog


def test_usb_timeout_does_not_escape_and_next_tick_writes(monkeypatch):
    dev = FakeDevice(failures=[_timeout()])
    monkeypatch.setattr(hardware, "device", dev)
    ctx = watchdog.LoopContext()

    watchdog.tick(ctx, now=100.0)                                 # scheitert am Timeout
    watchdog.tick(ctx, now=100.0 + watchdog.RETRY_BACKOFF_S)      # muss erneut schreiben

    assert len(dev.writes) == 1
    assert dev.resets == 1


def test_unchanged_state_is_rewritten_after_reassert_interval(monkeypatch):
    dev = FakeDevice()
    monkeypatch.setattr(hardware, "device", dev)
    ctx = watchdog.LoopContext()

    watchdog.tick(ctx, now=100.0)
    watchdog.tick(ctx, now=101.0)                                   # unverändert, zu früh
    watchdog.tick(ctx, now=100.0 + watchdog.REASSERT_INTERVAL_S)    # fällig

    assert len(dev.writes) == 2
    assert dev.writes[0] == dev.writes[1]


def test_unexpected_error_in_tick_does_not_escape_step(monkeypatch):
    def boom(_colour):
        raise RuntimeError("unerwartet")

    monkeypatch.setattr(hardware, "device", FakeDevice())
    monkeypatch.setattr(state, "get_effective_lamp", boom)

    watchdog.step(watchdog.LoopContext(), now=100.0)   # darf nicht werfen


def test_write_failures_are_logged_rate_limited_and_recovery_is_logged(monkeypatch, caplog):
    dev = FakeDevice(failures=[_timeout() for _ in range(2)])   # je ein Versuch pro Block
    monkeypatch.setattr(hardware, "device", dev)
    ctx = watchdog.LoopContext()
    caplog.set_level("INFO", logger="signaltower.watchdog")

    for i in range(10):                                      # 1 s Dauerfehler
        watchdog.step(ctx, now=100.0 + i * 0.1)
    assert len([r for r in caplog.records if r.levelname == "WARNING"]) == 1

    for i in range(10):                                      # eine Minute später
        watchdog.step(ctx, now=100.0 + watchdog.ERROR_LOG_INTERVAL_S + i * 0.1)
    assert len([r for r in caplog.records if r.levelname == "WARNING"]) == 2

    watchdog.step(ctx, now=200.0)                            # Fehler aufgebraucht
    assert any("recovered" in r.getMessage() for r in caplog.records)


def test_missing_board_is_logged(monkeypatch, caplog):
    monkeypatch.setattr(hardware, "device", FakeDevice(failures=[hardware.K8055NotFoundError("weg")]))
    caplog.set_level("INFO", logger="signaltower.watchdog")

    watchdog.step(watchdog.LoopContext(), now=100.0)

    assert any(r.levelname == "WARNING" for r in caplog.records)


def test_failed_writes_back_off_instead_of_retrying_every_tick(monkeypatch):
    dev = FakeDevice(failures=[_timeout() for _ in range(100)])
    monkeypatch.setattr(hardware, "device", dev)
    ctx = watchdog.LoopContext()

    for i in range(10):                              # 1 s bei 10 Hz
        watchdog.step(ctx, now=100.0 + i * 0.1)

    assert dev.resets <= 2
