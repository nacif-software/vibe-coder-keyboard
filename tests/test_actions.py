import pytest

from macropad.actions import (
    ActionError,
    KeySequence,
    Keystroke,
    Media,
    Mouse,
    format_action,
    parse_action,
)

# HID modifier bits: ctrl=0x01 shift=0x02 opt=0x04 cmd=0x08, right-hand variants << 4.
# HID key codes: a=0x04 c=0x06 v=0x19 z=0x1d 4=0x21 left=0x50 f13=0x68 backspace=0x2a.


def test_combo_sets_modifier_bits_and_key_code():
    assert parse_action("cmd+shift+4") == KeySequence((Keystroke(0x0A, 0x21),))


def test_plain_key_has_no_modifiers():
    assert parse_action("f13") == KeySequence((Keystroke(0x00, 0x68),))


def test_sequence_steps_are_comma_separated_and_keep_order():
    assert parse_action("cmd+a, cmd+c") == KeySequence(
        (Keystroke(0x08, 0x04), Keystroke(0x08, 0x06))
    )


def test_each_step_of_a_sequence_has_its_own_modifiers():
    assert parse_action("cmd+c, ctrl+opt+left, v") == KeySequence(
        (Keystroke(0x08, 0x06), Keystroke(0x05, 0x50), Keystroke(0x00, 0x19))
    )


def test_five_steps_is_the_maximum():
    assert len(parse_action("a, a, a, a, a").steps) == 5
    with pytest.raises(ActionError, match="5"):
        parse_action("a, a, a, a, a, a")


def test_mac_aliases_match_short_names():
    assert parse_action("command+option+control+z") == parse_action("cmd+opt+ctrl+z")
    assert parse_action("alt+z") == parse_action("opt+z")


def test_right_hand_modifiers_use_high_bits():
    assert parse_action("rcmd+rshift+z") == KeySequence((Keystroke(0x80 | 0x20, 0x1D),))


def test_case_and_whitespace_are_ignored():
    assert parse_action("  Cmd + Shift + 4 ") == parse_action("cmd+shift+4")


def test_modifier_only_step_is_allowed():
    assert parse_action("shift") == KeySequence((Keystroke(0x02, 0x00),))


def test_symbol_aliases_resolve_to_named_keys():
    assert parse_action("cmd+/") == parse_action("cmd+slash")
    assert parse_action("cmd+[") == parse_action("cmd+lbracket")


def test_unknown_key_suggests_close_names():
    with pytest.raises(ActionError) as exc:
        parse_action("cmd+pagedwn")
    assert "pagedown" in exc.value.suggestions


def test_plain_delete_is_rejected_as_ambiguous_on_macos():
    with pytest.raises(ActionError) as exc:
        parse_action("delete")
    assert {"backspace", "forward-delete"} <= set(exc.value.suggestions)
    assert parse_action("backspace") == KeySequence((Keystroke(0x00, 0x2A),))


def test_two_regular_keys_in_one_step_is_an_error():
    with pytest.raises(ActionError, match="one"):
        parse_action("a+b")


def test_empty_action_is_an_error():
    with pytest.raises(ActionError):
        parse_action("   ")
    with pytest.raises(ActionError):
        parse_action("cmd+a,,cmd+c")


def test_media_key_uses_consumer_code():
    assert parse_action("volume-up") == Media(0xE9)
    assert parse_action("play") == Media(0xCD)


def test_media_key_cannot_take_modifiers_or_be_in_a_sequence():
    with pytest.raises(ActionError):
        parse_action("cmd+mute")
    with pytest.raises(ActionError):
        parse_action("cmd+a, mute")


def test_mouse_click_sets_button_bit():
    assert parse_action("click") == Mouse(buttons=0x01, wheel=0, mods=0)
    assert parse_action("right-click") == Mouse(buttons=0x02, wheel=0, mods=0)
    assert parse_action("middle-click") == Mouse(buttons=0x04, wheel=0, mods=0)


def test_mouse_scroll_with_modifier():
    assert parse_action("ctrl+scroll-up") == Mouse(buttons=0, wheel=1, mods=0x01)
    assert parse_action("shift+scroll-down") == Mouse(buttons=0, wheel=-1, mods=0x02)


def test_mouse_action_cannot_be_in_a_sequence():
    with pytest.raises(ActionError):
        parse_action("click, click")


@pytest.mark.parametrize(
    "text, canonical",
    [
        ("Command + Shift + 4", "shift+cmd+4"),
        ("cmd+a,cmd+c", "cmd+a, cmd+c"),
        ("control+option+Left", "ctrl+opt+left"),
        ("cmd+/", "cmd+slash"),
        ("VOLUME-UP", "volume-up"),
        ("ctrl+wheel-up", "ctrl+scroll-up"),
        ("rcmd+x", "rcmd+x"),
    ],
)
def test_format_produces_canonical_text(text, canonical):
    assert format_action(parse_action(text)) == canonical
