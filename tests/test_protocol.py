"""Expected bytes are hand-derived from the vendor tool's Download_Click / Send_* methods.

Every packet is [report id 0x03] + payload, zero-padded to 64 bytes.
Payload layouts (from the vendor code):
  select layer   a1 <layer>
  key step       <slot> <layer<<4|1> <count> <index> <mods> <code>   index 0 carries mods only
  media          <slot> <layer<<4|2> <code lo> <code hi>
  mouse          <slot> <layer<<4|3> <buttons> <dx=0> <dy=0> <wheel> <mods>
  commit keys    aa aa
  led            b0 <layer<<4|8> <mode>, then aa a1
"""

import pytest

from macropad.actions import KeySequence, Keystroke, Media, Mouse
from macropad.protocol import SLOT_IDS, bind_packets, led_packets


def payloads(packets):
    """Strip the report id and zero padding so tests can compare short literals."""
    for packet in packets:
        assert len(packet) == 64
        assert packet[0] == 0x03
    return [bytes(packet[1:]).rstrip(b"\x00") for packet in packets]


def test_single_combo_on_key1_layer1():
    ctrl_a = KeySequence((Keystroke(0x01, 0x04),))
    assert payloads(bind_packets("key1", 1, ctrl_a)) == [
        bytes([0xA1, 0x01]),
        bytes([0x01, 0x11, 0x01, 0x00, 0x01]),        # index 0: mods only, code 0
        bytes([0x01, 0x11, 0x01, 0x01, 0x01, 0x04]),  # index 1: ctrl+a
        bytes([0xAA, 0xAA]),
    ]


def test_sequence_on_knob_right_layer2():
    cmd_c_then_v = KeySequence((Keystroke(0x08, 0x06), Keystroke(0x00, 0x19)))
    assert payloads(bind_packets("knob-right", 2, cmd_c_then_v)) == [
        bytes([0xA1, 0x02]),
        bytes([0x0F, 0x21, 0x02, 0x00, 0x08]),
        bytes([0x0F, 0x21, 0x02, 0x01, 0x08, 0x06]),
        bytes([0x0F, 0x21, 0x02, 0x02, 0x00, 0x19]),
        bytes([0xAA, 0xAA]),
    ]


def test_media_key_is_little_endian_consumer_code():
    assert payloads(bind_packets("knob-left", 1, Media(0xEA))) == [
        bytes([0xA1, 0x01]),
        bytes([0x0D, 0x12, 0xEA]),
        bytes([0xAA, 0xAA]),
    ]
    brightness = bind_packets("key2", 1, Media(0x182))
    assert payloads(brightness)[1] == bytes([0x02, 0x12, 0x82, 0x01])


def test_mouse_scroll_down_with_ctrl_on_layer3():
    ctrl_scroll_down = Mouse(buttons=0, wheel=-1, mods=0x01)
    assert payloads(bind_packets("knob-press", 3, ctrl_scroll_down)) == [
        bytes([0xA1, 0x03]),
        bytes([0x0E, 0x33, 0x00, 0x00, 0x00, 0xFF, 0x01]),
        bytes([0xAA, 0xAA]),
    ]


def test_mouse_right_click():
    assert payloads(bind_packets("key6", 1, Mouse(buttons=0x02, wheel=0, mods=0)))[1] == bytes(
        [0x06, 0x13, 0x02]
    )


def test_clearing_a_slot_binds_a_single_empty_keystroke():
    assert payloads(bind_packets("key4", 1, None)) == [
        bytes([0xA1, 0x01]),
        bytes([0x04, 0x11, 0x01]),
        bytes([0x04, 0x11, 0x01, 0x01]),
        bytes([0xAA, 0xAA]),
    ]


@pytest.mark.parametrize(
    "slot, vendor_id",
    [("key1", 1), ("key2", 2), ("key3", 3), ("key4", 4), ("key5", 5), ("key6", 6),
     ("knob-left", 13), ("knob-press", 14), ("knob-right", 15)],
)
def test_each_slot_is_addressed_by_its_vendor_key_id(slot, vendor_id):
    assert payloads(bind_packets(slot, 1, None))[1][0] == vendor_id
    assert slot in SLOT_IDS


def test_led_mode_packets():
    assert payloads(led_packets(2)) == [
        bytes([0xA1, 0x01]),
        bytes([0xB0, 0x18, 0x02]),
        bytes([0xAA, 0xA1]),
    ]


@pytest.mark.parametrize("layer", [0, 4])
def test_layer_out_of_range_is_rejected(layer):
    with pytest.raises(ValueError, match="layer"):
        bind_packets("key1", layer, None)


def test_unknown_slot_is_rejected():
    with pytest.raises(ValueError, match="slot"):
        bind_packets("key7", 1, None)


def test_led_mode_out_of_range_is_rejected():
    with pytest.raises(ValueError, match="mode"):
        led_packets(3)
