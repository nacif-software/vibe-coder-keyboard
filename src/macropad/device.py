"""Talk to the macropad over raw USB via libusb (pyusb).

The config channel isn't a HID report: the pad has a HID-class interface (interface 1 on
real hardware) whose only endpoint is an interrupt OUT pipe (0x02). macOS binds no HID
driver to it, so HID APIs can't see it; libusb writes to it directly, no permissions needed.
"""

import usb.core as usb_core
import usb.util as usb_util
from usb.core import USBError

VENDOR_ID = 0x1189
PRODUCT_ID = 0x8890
TIMEOUT_MS = 1000

_INTERRUPT = 0x03


class DeviceNotFound(RuntimeError):
    pass


class WriteFailed(RuntimeError):
    def __init__(self, message: str, attempts: list[str] | None = None):
        super().__init__(message)
        self.attempts = attempts or []


class LibUsb:
    """The real backend."""

    def find(self):
        import libusb_package

        return usb_core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID,
                             backend=libusb_package.get_libusb1_backend())

    def dispose(self, device):
        usb_util.dispose_resources(device)


def interfaces(usb=None) -> list[dict]:
    """Every USB interface of the pad with its endpoints; the config one is marked."""
    usb = usb or LibUsb()
    dev = usb.find()
    if dev is None:
        return []
    try:
        config = _config_endpoint(dev)
        return [
            {
                "interface_number": intf.bInterfaceNumber,
                "class": intf.bInterfaceClass,
                "config": config is not None and intf.bInterfaceNumber == config[0],
                "endpoints": [
                    {
                        "address": f"0x{ep.bEndpointAddress:02x}",
                        "direction": "in" if ep.bEndpointAddress & 0x80 else "out",
                        "type": ["control", "isochronous", "bulk", "interrupt"][ep.bmAttributes & 0x03],
                    }
                    for ep in intf
                ],
            }
            for intf in dev.get_active_configuration()
        ]
    finally:
        usb.dispose(dev)


def send(packets: list[bytes], usb=None) -> dict:
    """Write `packets` in order to the pad's config endpoint; returns where they went."""
    usb = usb or LibUsb()
    dev = usb.find()
    if dev is None:
        raise DeviceNotFound(
            f"no macropad found (USB {VENDOR_ID:04x}:{PRODUCT_ID:04x}); is it plugged in?"
        )
    try:
        config = _config_endpoint(dev)
        if config is None:
            raise WriteFailed("the pad has no interrupt OUT endpoint to send config to")
        interface, endpoint = config
        _detach_kernel_driver(dev, interface)
        for number, packet in enumerate(packets, start=1):
            where = f"endpoint 0x{endpoint:02x}: packet {number} of {len(packets)}"
            try:
                written = dev.write(endpoint, packet, timeout=TIMEOUT_MS)
            except USBError as exc:
                raise WriteFailed(f"{where} failed ({exc}); retry the command") from exc
            if written != len(packet):
                raise WriteFailed(f"{where} wrote {written} of {len(packet)} bytes; retry")
        return {"interface_number": interface, "endpoint": endpoint}
    finally:
        usb.dispose(dev)


def _config_endpoint(dev) -> tuple[int, int] | None:
    for intf in dev.get_active_configuration():
        for ep in intf:
            if not ep.bEndpointAddress & 0x80 and ep.bmAttributes & 0x03 == _INTERRUPT:
                return intf.bInterfaceNumber, ep.bEndpointAddress
    return None


def _detach_kernel_driver(dev, interface: int) -> None:
    try:
        if dev.is_kernel_driver_active(interface):
            dev.detach_kernel_driver(interface)
    except (NotImplementedError, USBError):
        pass  # not supported on this platform, or nothing to detach
