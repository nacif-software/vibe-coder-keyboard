"""Talk to the macropad over USB HID via hidapi (native IOHIDManager on macOS).

Which HID interface accepts the config reports isn't documented, so like the vendor tool
we probe: the first packet is tried on each interface (most likely first) and the rest of
the packets go to whichever accepted it.
"""

import hid

VENDOR_ID = 0x1189
PRODUCT_ID = 0x8890


class DeviceNotFound(RuntimeError):
    pass


class WriteFailed(RuntimeError):
    def __init__(self, message: str, attempts: list[str] | None = None):
        super().__init__(message)
        self.attempts = attempts or []


def interfaces(hid_module=hid) -> list[dict]:
    """The macropad's HID interfaces, one per path, most likely config interface first."""
    unique: dict[bytes, dict] = {}
    for info in sorted(hid_module.enumerate(VENDOR_ID, PRODUCT_ID), key=_priority):
        unique.setdefault(info["path"], info)
    return list(unique.values())


def send(packets: list[bytes], hid_module=hid) -> dict:
    """Write `packets` in order to the first interface that accepts them; returns its info."""
    candidates = interfaces(hid_module)
    if not candidates:
        raise DeviceNotFound(
            f"no macropad found (USB {VENDOR_ID:04x}:{PRODUCT_ID:04x}); is it plugged in?"
        )

    attempts = []
    for info in candidates:
        label = describe(info)
        dev = hid_module.device()
        try:
            dev.open_path(info["path"])
        except OSError as exc:
            attempts.append(f"{label}: open failed ({exc})")
            continue
        try:
            if not _write(dev, packets[0]):
                attempts.append(f"{label}: write rejected ({dev.error()})")
                continue
            for number, packet in enumerate(packets[1:], start=2):
                if not _write(dev, packet):
                    raise WriteFailed(
                        f"{label}: write failed on packet {number} of {len(packets)} "
                        f"({dev.error()}); the slot may be half-programmed, retry the command",
                        attempts,
                    )
            return info
        finally:
            dev.close()

    raise WriteFailed("no HID interface of the macropad accepted the config report", attempts)


def describe(info: dict) -> str:
    return (
        f"interface {info['interface_number']} "
        f"(usage page 0x{info['usage_page']:04x}, usage 0x{info['usage']:02x})"
    )


def _write(dev, packet: bytes) -> bool:
    try:
        return dev.write(packet) > 0
    except OSError:
        return False


def _priority(info: dict) -> int:
    page, usage = info["usage_page"], info["usage"]
    if page >= 0xFF00:
        return 0  # vendor-defined: where config reports normally live
    if (page, usage) == (0x01, 0x06):
        return 3  # keyboard: macOS may require Input Monitoring permission to open it
    if page == 0x01:
        return 2
    return 1
