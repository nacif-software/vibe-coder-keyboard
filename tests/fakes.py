"""A stand-in for the `hid` module (hidapi) — the USB boundary is the only thing faked."""


def hid_info(path, usage_page, usage, interface_number, vendor_id=0x1189, product_id=0x8890):
    """An hid.enumerate() entry with every field the real binding returns."""
    return {
        "path": path,
        "vendor_id": vendor_id,
        "product_id": product_id,
        "serial_number": "",
        "release_number": 0x0100,
        "manufacturer_string": "",
        "product_string": "",
        "usage_page": usage_page,
        "usage": usage,
        "interface_number": interface_number,
        "bus_type": 1,
    }


# What a CH57x macropad typically exposes: boot keyboard, mouse + consumer, vendor config.
MACROPAD_INTERFACES = [
    hid_info(b"kbd", 0x01, 0x06, 0),
    hid_info(b"mouse", 0x01, 0x02, 1),
    hid_info(b"consumer", 0x0C, 0x01, 1),
    hid_info(b"vendor", 0xFF00, 0x01, 2),
]

OTHER_KEYBOARD = hid_info(b"wooting", 0x01, 0x06, 0, vendor_id=0x31E3, product_id=0x1232)


class FakeHid:
    def __init__(self, interfaces, rejects_writes=(), unopenable=(), fail_after=None):
        self.interfaces = list(interfaces)
        self.rejects_writes = set(rejects_writes)
        self.unopenable = set(unopenable)
        self.fail_after = fail_after  # path -> number of successful writes before failing
        self.written: dict[bytes, list[bytes]] = {}
        self.opened: list[bytes] = []
        self.closed: list[bytes] = []

    def enumerate(self, vendor_id=0, product_id=0):
        return [
            dict(info)
            for info in self.interfaces
            if (not vendor_id or info["vendor_id"] == vendor_id)
            and (not product_id or info["product_id"] == product_id)
        ]

    def device(self):
        return _FakeDevice(self)


class _FakeDevice:
    def __init__(self, hid):
        self._hid = hid
        self._path = None

    def open_path(self, path):
        if path in self._hid.unopenable:
            raise OSError("open failed")
        self._path = path
        self._hid.opened.append(path)

    def write(self, buff):
        if self._path is None:
            raise ValueError("not open")
        data = bytes(buff)
        if self._path in self._hid.rejects_writes:
            return -1
        limit = (self._hid.fail_after or {}).get(self._path)
        sent = self._hid.written.setdefault(self._path, [])
        if limit is not None and len(sent) >= limit:
            return -1
        sent.append(data)
        return len(data)

    def error(self):
        return "IOHIDDeviceSetReport failed: (0xE00002F0) unsupported"

    def close(self):
        self._hid.closed.append(self._path)
