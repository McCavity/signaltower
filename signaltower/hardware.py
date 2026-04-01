import usb.core
import usb.util

VENDOR_ID = 0x10CF
PRODUCT_IDS = [0x5500, 0x5501, 0x5502, 0x5503]

SET_ANALOG_DIGITAL = 0x05


class K8055NotFoundError(Exception):
    pass


class K8055:
    def __init__(self, board_address: int = 0):
        self._product_id = PRODUCT_IDS[board_address]
        self._dev = None

    def _connect(self):
        dev = usb.core.find(idVendor=VENDOR_ID, idProduct=self._product_id)
        if dev is None:
            raise K8055NotFoundError(
                f"K8055 not found (VID=0x{VENDOR_ID:04X} PID=0x{self._product_id:04X})"
            )
        if dev.is_kernel_driver_active(0):
            dev.detach_kernel_driver(0)
        dev.set_configuration()
        self._dev = dev

    def set_outputs(self, bitmask: int):
        if self._dev is None:
            self._connect()
        packet = [0x00] * 8
        packet[0] = SET_ANALOG_DIGITAL
        packet[1] = bitmask & 0xFF
        self._dev.write(0x01, packet)


# Shared singleton — import this rather than instantiating K8055 directly.
device = K8055()
