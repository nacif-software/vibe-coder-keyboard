import pytest

from fakes import MACROPAD_INTERFACES, OTHER_KEYBOARD, FakeHid, hid_info
from macropad.device import DeviceNotFound, WriteFailed, interfaces, send

PACKETS = [b"\x03\xa1\x01", b"\x03\x01\x11", b"\x03\xaa\xaa"]


def test_no_macropad_connected_raises_device_not_found():
    fake = FakeHid([OTHER_KEYBOARD])
    with pytest.raises(DeviceNotFound):
        send(PACKETS, hid_module=fake)
    assert fake.opened == []


def test_packets_go_to_the_vendor_defined_interface_first():
    fake = FakeHid([OTHER_KEYBOARD, *MACROPAD_INTERFACES])
    used = send(PACKETS, hid_module=fake)
    assert used["path"] == b"vendor"
    assert fake.written == {b"vendor": PACKETS}
    assert fake.closed == [b"vendor"]


def test_falls_back_when_an_interface_rejects_the_first_packet():
    fake = FakeHid(MACROPAD_INTERFACES, rejects_writes={b"vendor"})
    used = send(PACKETS, hid_module=fake)
    assert used["path"] == b"consumer"
    assert fake.written == {b"consumer": PACKETS}
    assert b"vendor" in fake.closed


def test_falls_back_when_an_interface_cannot_be_opened():
    fake = FakeHid(MACROPAD_INTERFACES, unopenable={b"vendor", b"consumer"})
    used = send(PACKETS, hid_module=fake)
    assert used["path"] == b"mouse"


def test_keyboard_interface_is_the_last_resort():
    fake = FakeHid(MACROPAD_INTERFACES)
    assert [info["path"] for info in interfaces(fake)] == [
        b"vendor", b"consumer", b"mouse", b"kbd",
    ]


def test_collections_sharing_a_path_are_tried_once():
    shared = [hid_info(b"if1", 0x0C, 0x01, 1), hid_info(b"if1", 0x01, 0x02, 1)]
    fake = FakeHid(shared, rejects_writes={b"if1"})
    with pytest.raises(WriteFailed):
        send(PACKETS, hid_module=fake)
    assert fake.opened == [b"if1"]


def test_every_interface_refusing_raises_write_failed_with_reasons():
    fake = FakeHid(MACROPAD_INTERFACES, rejects_writes={b"vendor", b"consumer", b"mouse"},
                   unopenable={b"kbd"})
    with pytest.raises(WriteFailed) as exc:
        send(PACKETS, hid_module=fake)
    assert len(exc.value.attempts) == 4
    assert fake.written == {}


def test_failure_after_the_first_packet_does_not_switch_interfaces():
    fake = FakeHid(MACROPAD_INTERFACES, fail_after={b"vendor": 1})
    with pytest.raises(WriteFailed, match="2 of 3"):
        send(PACKETS, hid_module=fake)
    assert list(fake.written) == [b"vendor"]
    assert fake.closed == [b"vendor"]
