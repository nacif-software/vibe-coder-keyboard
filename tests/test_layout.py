import pytest

from macropad.actions import KeySequence, Keystroke, Media
from macropad.layout import Layout, LayoutError, load, save


def test_missing_file_loads_as_empty_layout(tmp_path):
    layout = load(tmp_path / "nope.yaml")
    assert layout.led is None
    assert layout.layers == {}


def test_set_stores_canonical_text_and_survives_a_round_trip(tmp_path):
    path = tmp_path / "sub" / "layout.yaml"
    layout = Layout()
    layout.set_slot(1, "key3", "Command+Shift+4")
    layout.set_slot(2, "knob-right", "vol-up")
    layout.led = 1
    save(layout, path)

    reloaded = load(path)
    assert reloaded.layers == {1: {"key3": "shift+cmd+4"}, 2: {"knob-right": "volume-up"}}
    assert reloaded.led == 1


def test_clearing_the_last_slot_of_a_layer_drops_the_layer():
    layout = Layout()
    layout.set_slot(1, "key1", "a")
    layout.clear_slot(1, "key1")
    assert layout.layers == {}


def test_bindings_cover_every_slot_of_every_layer():
    layout = Layout()
    layout.set_slot(2, "key1", "ctrl+a")
    layout.set_slot(3, "knob-press", "mute")
    bindings = layout.bindings()

    assert len(bindings) == 3 * 9
    assert bindings[(2, "key1")] == KeySequence((Keystroke(0x01, 0x04),))
    assert bindings[(3, "knob-press")] == Media(0xE2)
    assert bindings[(1, "key1")] is None


def test_hand_written_file_with_sequences_loads(tmp_path):
    path = tmp_path / "layout.yaml"
    path.write_text(
        "led: 2\n"
        "layers:\n"
        "  1:\n"
        "    key1: cmd+a, cmd+c\n"
        "    key2: 7\n"
    )
    layout = load(path)
    assert layout.layers == {1: {"key1": "cmd+a, cmd+c", "key2": "7"}}
    assert layout.led == 2


def test_problems_are_reported_with_their_location(tmp_path):
    path = tmp_path / "layout.yaml"
    path.write_text(
        "led: 5\n"
        "layers:\n"
        "  1:\n"
        "    key9: a\n"
        "    key2: cmd+pagedwn\n"
        "  4:\n"
        "    key1: a\n"
    )
    with pytest.raises(LayoutError) as exc:
        load(path)
    problems = "\n".join(exc.value.problems)
    assert "led" in problems
    assert "layers.1.key9" in problems
    assert "layers.1.key2" in problems and "pagedown" in problems
    assert "layers.4" in problems


def test_invalid_yaml_is_a_layout_error(tmp_path):
    path = tmp_path / "layout.yaml"
    path.write_text("layers: [unclosed\n")
    with pytest.raises(LayoutError):
        load(path)
