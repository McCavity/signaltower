import time

from fastapi.testclient import TestClient

from fakes import FakeDevice, usb_timeout
from signaltower import hardware, watchdog
from signaltower.app import app

client = TestClient(app)   # ohne ``with``: kein Lifespan, kein echter Thread


def test_health_is_503_before_the_watchdog_ran():
    r = client.get("/health")
    assert r.status_code == 503


def test_health_turns_red_on_usb_timeout_and_green_after_recovery(monkeypatch):
    monkeypatch.setattr(hardware, "device", FakeDevice(failures=[usb_timeout()]))
    ctx = watchdog.LoopContext()
    t0 = time.monotonic() - 2

    watchdog.step(ctx, now=t0)
    assert client.get("/health").status_code == 503

    watchdog.step(ctx, now=t0 + watchdog.RETRY_BACKOFF_S)
    assert client.get("/health").status_code == 200


def test_health_is_503_when_the_loop_stalls(monkeypatch):
    monkeypatch.setattr(hardware, "device", FakeDevice())
    watchdog.step(watchdog.LoopContext(), now=time.monotonic() - 10)

    assert client.get("/health").status_code == 503


def test_health_goes_from_green_to_red_when_writes_keep_failing(monkeypatch):
    """Der Ablauf vom 02.10.: erst gesund, dann scheitert jeder Schreibvorgang."""
    dev = FakeDevice()
    monkeypatch.setattr(hardware, "device", dev)
    ctx = watchdog.LoopContext()
    t0 = time.monotonic() - 30

    watchdog.step(ctx, now=t0)
    dev._failures = [usb_timeout() for _ in range(1000)]
    for i in range(1, 300):                          # 30 s Dauerfehler bei 10 Hz
        watchdog.step(ctx, now=t0 + i * 0.1)

    r = client.get("/health")
    assert r.status_code == 503
    assert r.json()["write_age_s"] > 15
