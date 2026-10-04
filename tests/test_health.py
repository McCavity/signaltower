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

    watchdog.step(ctx, now=time.monotonic())
    assert client.get("/health").status_code == 503

    watchdog.step(ctx, now=time.monotonic())
    assert client.get("/health").status_code == 200


def test_health_is_503_when_the_loop_stalls(monkeypatch):
    monkeypatch.setattr(hardware, "device", FakeDevice())
    watchdog.step(watchdog.LoopContext(), now=time.monotonic() - 10)

    assert client.get("/health").status_code == 503
