"""A stand-in for pyusb/libusb, the only thing faked. Mirrors the real API:
dev.get_active_configuration() iterates interfaces, an interface iterates endpoints,
dev.write(endpoint, data, timeout) returns the byte count or raises usb.core.USBError.
"""

import usb.core

INTERRUPT = 0x03


class FakeEndpoint:
    def __init__(self, address, attributes=INTERRUPT, max_packet=64):
        self.bEndpointAddress = address
        self.bmAttributes = attributes
        self.wMaxPacketSize = max_packet


class FakeInterface:
    def __init__(self, number, endpoints, class_=3):
        self.bInterfaceNumber = number
        self.bInterfaceClass = class_
        self.bAlternateSetting = 0
        self._endpoints = endpoints

    def __iter__(self):
        return iter(self._endpoints)


def macropad_interfaces():
    """What the real 1189:8890 pad reports (read with libusb on real hardware)."""
    return [
        FakeInterface(0, [FakeEndpoint(0x81)]),              # keyboard, IN
        FakeInterface(1, [FakeEndpoint(0x02)]),              # config, interrupt OUT
        FakeInterface(2, [FakeEndpoint(0x83, max_packet=4)]),  # keyboard + media, IN
        FakeInterface(3, [FakeEndpoint(0x82, max_packet=4)]),  # mouse, IN
    ]


class FakeDevice:
    def __init__(self, interfaces=None, fail_on_packet=None, short_on_packet=None,
                 kernel_driver_on=()):
        self.interfaces = macropad_interfaces() if interfaces is None else interfaces
        self.fail_on_packet = fail_on_packet    # 1-based packet number that raises USBError
        self.short_on_packet = short_on_packet  # 1-based packet number that writes 0 bytes
        self.kernel_driver_on = set(kernel_driver_on)
        self.detached: list[int] = []
        self.written: list[tuple[int, bytes]] = []

    def get_active_configuration(self):
        return list(self.interfaces)

    def is_kernel_driver_active(self, interface):
        return interface in self.kernel_driver_on

    def detach_kernel_driver(self, interface):
        self.detached.append(interface)
        self.kernel_driver_on.discard(interface)

    def write(self, endpoint, data, timeout=None):
        number = len(self.written) + 1
        if number == self.fail_on_packet:
            raise usb.core.USBError("Pipe error", errno=32)
        if number == self.short_on_packet:
            return 0
        self.written.append((endpoint, bytes(data)))
        return len(data)


class FakeUsb:
    """The backend: finds the pad (or not) and disposes of it."""

    def __init__(self, device=None):
        self.device = device
        self.disposed: list = []

    def find(self):
        return self.device

    def dispose(self, device):
        self.disposed.append(device)
