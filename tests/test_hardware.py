from signaltower import hardware


class FakeUsbDev:
    def __init__(self):
        self.packets = []

    def is_kernel_driver_active(self, _iface):
        return False

    def set_configuration(self):
        pass

    def write(self, _endpoint, packet):
        self.packets.append(packet)


def test_reset_makes_next_write_reconnect(monkeypatch):
    found = []

    def fake_find(**_kwargs):
        dev = FakeUsbDev()
        found.append(dev)
        return dev

    monkeypatch.setattr(hardware.usb.core, "find", fake_find)
    monkeypatch.setattr(hardware.usb.util, "dispose_resources", lambda _dev: None)
    k = hardware.K8055()

    k.set_outputs(1)
    k.reset()
    k.set_outputs(2)

    assert len(found) == 2
    assert found[1].packets[0][1] == 2
