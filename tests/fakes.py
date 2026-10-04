import usb.core


class FakeDevice:
    """Simuliert den K8055: optional vorgegebene Fehler, dann Erfolg."""

    def __init__(self, failures=()):
        self._failures = list(failures)
        self.writes = []
        self.resets = 0

    def set_outputs(self, bitmask):
        if self._failures:
            raise self._failures.pop(0)
        self.writes.append(bitmask)

    def reset(self):
        self.resets += 1


def _timeout():
    return usb.core.USBTimeoutError("Operation timed out", -7, 110)


def usb_timeout():
    return usb.core.USBTimeoutError("Operation timed out", -7, 110)
