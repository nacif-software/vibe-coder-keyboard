import pytest

from fakes import FakeDevice, FakeEndpoint, FakeInterface, FakeUsb
from macropad.device import DeviceNotFound, WriteFailed, interfaces, send

PACKETS = [b"\x03\xa1\x01", b"\x03\x01\x11", b"\x03\xaa\xaa"]


def test_no_macropad_connected_raises_device_not_found():
    with pytest.raises(DeviceNotFound, match="plugged in"):
        send(PACKETS, usb=FakeUsb(None))


def test_packets_go_in_order_to_the_interrupt_out_endpoint():
    dev = FakeDevice()
    usb = FakeUsb(dev)
    used = send(PACKETS, usb=usb)
    assert dev.written == [(0x02, p) for p in PACKETS]
    assert used == {"interface_number": 1, "endpoint": 0x02}
    assert usb.disposed == [dev]


def test_out_endpoint_is_found_wherever_it_is():
    dev = FakeDevice(interfaces=[
        FakeInterface(0, [FakeEndpoint(0x81)]),
        FakeInterface(2, [FakeEndpoint(0x84), FakeEndpoint(0x04)]),
    ])
    assert send(PACKETS, usb=FakeUsb(dev)) == {"interface_number": 2, "endpoint": 0x04}


def test_bulk_out_endpoints_are_not_the_config_channel():
    dev = FakeDevice(interfaces=[FakeInterface(1, [FakeEndpoint(0x02, attributes=0x02)])])
    with pytest.raises(WriteFailed, match="OUT endpoint"):
        send(PACKETS, usb=FakeUsb(dev))
    assert dev.written == []


def test_kernel_driver_is_detached_from_the_config_interface_only():
    dev = FakeDevice(kernel_driver_on={0, 1})
    send(PACKETS, usb=FakeUsb(dev))
    assert dev.detached == [1]


def test_usb_error_mid_stream_reports_the_failing_packet_and_still_disposes():
    dev = FakeDevice(fail_on_packet=2)
    usb = FakeUsb(dev)
    with pytest.raises(WriteFailed, match="packet 2 of 3"):
        send(PACKETS, usb=usb)
    assert usb.disposed == [dev]


def test_short_write_is_a_failure():
    with pytest.raises(WriteFailed, match="packet 3 of 3"):
        send(PACKETS, usb=FakeUsb(FakeDevice(short_on_packet=3)))


def test_interfaces_describe_endpoints_and_mark_the_config_one():
    found = interfaces(usb=FakeUsb(FakeDevice()))
    assert [i["interface_number"] for i in found] == [0, 1, 2, 3]
    config = [i for i in found if i["config"]]
    assert [i["interface_number"] for i in config] == [1]
    assert config[0]["endpoints"] == [{"address": "0x02", "direction": "out", "type": "interrupt"}]
    assert found[0]["endpoints"][0]["direction"] == "in"


def test_interfaces_is_empty_when_disconnected():
    assert interfaces(usb=FakeUsb(None)) == []
