"""Build the USB HID output reports that program the macropad.

Decoded from the vendor's Windows tool ("MINI KeyBoard", HIDTester.FormMain.Download_Click).
Each report is REPORT_ID followed by a payload, zero-padded to PACKET_SIZE bytes.
Binding one slot = select layer, one or more binding payloads, commit.
"""

from macropad.actions import Action, KeySequence, Keystroke, Media, Mouse

REPORT_ID = 0x03
PACKET_SIZE = 64
LAYERS = (1, 2, 3)
LED_MODES = (0, 1, 2)

SLOT_IDS: dict[str, int] = {
    **{f"key{n}": n for n in range(1, 7)},
    "knob-left": 13,
    "knob-press": 14,
    "knob-right": 15,
}

_TYPE_KEYS = 0x1
_TYPE_MEDIA = 0x2
_TYPE_MOUSE = 0x3
_TYPE_LED = 0x8

_SELECT_LAYER = 0xA1
_COMMIT = 0xAA
_COMMIT_KEYS = 0xAA
_COMMIT_LED = 0xA1
_LED_TARGET = 0xB0

# Clearing isn't a vendor feature: bind one keystroke with no modifiers and no key.
_EMPTY = KeySequence((Keystroke(0, 0),))


def bind_packets(slot: str, layer: int, action: Action | None) -> list[bytes]:
    """Packets that bind `action` to `slot` on `layer`; None clears the slot."""
    if slot not in SLOT_IDS:
        raise ValueError(f"unknown slot {slot!r}; expected one of {list(SLOT_IDS)}")
    if layer not in LAYERS:
        raise ValueError(f"layer must be one of {LAYERS}, got {layer}")

    slot_id = SLOT_IDS[slot]
    action = action or _EMPTY

    if isinstance(action, Media):
        lo, hi = action.code.to_bytes(2, "little")
        body = [_packet(slot_id, _kind(layer, _TYPE_MEDIA), lo, hi)]
    elif isinstance(action, Mouse):
        body = [_packet(slot_id, _kind(layer, _TYPE_MOUSE), action.buttons, 0, 0,
                        action.wheel & 0xFF, action.mods)]
    else:
        steps = action.steps
        # Index 0 carries only the first step's modifiers; indexes 1..n are the keystrokes.
        body = [_packet(slot_id, _kind(layer, _TYPE_KEYS), len(steps), 0, steps[0].mods, 0)]
        body += [
            _packet(slot_id, _kind(layer, _TYPE_KEYS), len(steps), i, step.mods, step.code)
            for i, step in enumerate(steps, start=1)
        ]

    return [_packet(_SELECT_LAYER, layer), *body, _packet(_COMMIT, _COMMIT_KEYS)]


def led_packets(mode: int) -> list[bytes]:
    """Packets that set the backlight: 0 off, 1 last-pressed key lit, 2 rainbow wave."""
    if mode not in LED_MODES:
        raise ValueError(f"LED mode must be one of {LED_MODES}, got {mode}")
    return [
        _packet(_SELECT_LAYER, 1),
        _packet(_LED_TARGET, _kind(1, _TYPE_LED), mode),
        _packet(_COMMIT, _COMMIT_LED),
    ]


def _kind(layer: int, type_: int) -> int:
    return (layer << 4) | type_


def _packet(*payload: int) -> bytes:
    return bytes([REPORT_ID, *payload]).ljust(PACKET_SIZE, b"\x00")
