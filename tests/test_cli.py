import json

import pytest
import yaml

from fakes import FakeDevice, FakeUsb
from macropad.cli import main


@pytest.fixture
def layout_path(tmp_path):
    return tmp_path / "layout.yaml"


@pytest.fixture
def fake():
    return FakeUsb(FakeDevice())


def run(argv, fake, layout_path):
    return main([*argv, "--layout", str(layout_path)], usb=fake)


def sent_payloads(fake):
    """Report-id-stripped, zero-trimmed payloads the device received, in order."""
    assert all(endpoint == 0x02 for endpoint, _ in fake.device.written)
    return [bytes(p[1:]).rstrip(b"\x00") for _, p in fake.device.written]


def saved(layout_path):
    return yaml.safe_load(layout_path.read_text())


# --- set -------------------------------------------------------------------------------

def test_set_programs_the_slot_and_records_it(fake, layout_path, capsys):
    assert run(["set", "key3", "cmd+shift+4"], fake, layout_path) == 0
    assert sent_payloads(fake) == [
        bytes([0xA1, 0x01]),
        bytes([0x03, 0x11, 0x01, 0x00, 0x0A]),
        bytes([0x03, 0x11, 0x01, 0x01, 0x0A, 0x21]),
        bytes([0xAA, 0xAA]),
    ]
    assert saved(layout_path) == {"layers": {1: {"key3": "shift+cmd+4"}}}
    assert "key3" in capsys.readouterr().out


def test_set_on_another_layer_uses_that_layer(fake, layout_path):
    assert run(["set", "knob-right", "volume-up", "--layer", "2"], fake, layout_path) == 0
    assert sent_payloads(fake)[:2] == [bytes([0xA1, 0x02]), bytes([0x0F, 0x22, 0xE9])]
    assert saved(layout_path) == {"layers": {2: {"knob-right": "volume-up"}}}


def test_set_keeps_other_slots_in_the_layout(fake, layout_path):
    run(["set", "key1", "cmd+c"], fake, layout_path)
    run(["set", "key2", "cmd+v"], fake, layout_path)
    assert saved(layout_path) == {"layers": {1: {"key1": "cmd+c", "key2": "cmd+v"}}}


def test_invalid_action_sends_nothing_and_exits_1(fake, layout_path, capsys):
    assert run(["set", "key1", "cmd+pagedwn"], fake, layout_path) == 1
    assert fake.device.written == []
    assert not layout_path.exists()
    assert "pagedown" in capsys.readouterr().err


def test_sequence_over_the_limit_is_rejected(fake, layout_path, capsys):
    assert run(["set", "key1", "a, b, c, d, e, f"], fake, layout_path) == 1
    assert "5" in capsys.readouterr().err
    assert fake.device.written == []


def test_missing_device_exits_2_and_leaves_layout_untouched(layout_path, capsys):
    assert run(["set", "key1", "a"], FakeUsb(None), layout_path) == 2
    assert not layout_path.exists()
    assert "plugged in" in capsys.readouterr().err


def test_write_failure_exits_3_and_leaves_layout_untouched(layout_path):
    fake = FakeUsb(FakeDevice(fail_on_packet=3))
    assert run(["set", "key1", "a"], fake, layout_path) == 3
    assert not layout_path.exists()


def test_dry_run_prints_packets_without_touching_device_or_layout(fake, layout_path, capsys):
    assert run(["set", "key1", "ctrl+a", "--dry-run"], fake, layout_path) == 0
    assert fake.device.written == []
    assert not layout_path.exists()
    assert "03 01 11 01 01 01 04" in capsys.readouterr().out


def test_set_json_success(fake, layout_path, capsys):
    assert run(["set", "key4", "cmd+a, cmd+c", "--json"], fake, layout_path) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["layer"] == 1
    assert out["slot"] == "key4"
    assert out["action"] == "cmd+a, cmd+c"


def test_json_errors_are_structured_on_stdout(fake, layout_path, capsys):
    assert run(["set", "key1", "cmd+pagedwn", "--json"], fake, layout_path) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert out["error"]["type"] == "invalid_action"
    assert "pagedown" in out["error"]["suggestions"]


def test_dry_run_json_lists_hex_packets(fake, layout_path, capsys):
    run(["set", "key1", "ctrl+a", "--dry-run", "--json"], fake, layout_path)
    out = json.loads(capsys.readouterr().out)
    assert out["dry_run"] is True
    assert out["packets"][2] == "03011101010104"


def test_unknown_slot_is_a_usage_error_exit_1(fake, layout_path, capsys):
    with pytest.raises(SystemExit) as exc:
        run(["set", "key7", "a"], fake, layout_path)
    assert exc.value.code == 1
    assert fake.device.written == []


# --- clear -----------------------------------------------------------------------------

def test_clear_blanks_the_slot_on_device_and_in_layout(fake, layout_path):
    run(["set", "key1", "a"], fake, layout_path)
    run(["set", "key2", "b"], fake, layout_path)
    fake.device.written.clear()

    assert run(["clear", "key1"], fake, layout_path) == 0
    assert sent_payloads(fake)[1:3] == [bytes([0x01, 0x11, 0x01]), bytes([0x01, 0x11, 0x01, 0x01])]
    assert saved(layout_path) == {"layers": {1: {"key2": "b"}}}


# --- apply -----------------------------------------------------------------------------

def test_apply_makes_the_device_match_the_file(fake, layout_path, tmp_path, capsys):
    source = tmp_path / "mine.yaml"
    source.write_text("led: 0\nlayers:\n  2:\n    key1: cmd+a, cmd+c\n")

    assert run(["apply", str(source), "--json"], fake, layout_path) == 0
    payloads = sent_payloads(fake)
    # the mapped slot, with its 2-step sequence
    assert bytes([0x01, 0x21, 0x02, 0x02, 0x08, 0x06]) in payloads
    # an unmapped slot on another layer is cleared
    assert bytes([0x0F, 0x31, 0x01, 0x01]) in payloads
    # LED last (mode 0 is indistinguishable from padding once trailing zeros are trimmed)
    assert payloads[-2:] == [bytes([0xB0, 0x18]), bytes([0xAA, 0xA1])]
    # the applied file becomes the recorded layout
    assert saved(layout_path) == {"led": 0, "layers": {2: {"key1": "cmd+a, cmd+c"}}}
    out = json.loads(capsys.readouterr().out)
    assert out["programmed"] == 1
    assert out["cleared"] == 26


def test_apply_without_file_uses_the_recorded_layout(fake, layout_path):
    layout_path.write_text("layers:\n  1:\n    key5: esc\n")
    assert run(["apply"], fake, layout_path) == 0
    assert bytes([0x05, 0x11, 0x01, 0x01, 0x00, 0x29]) in sent_payloads(fake)


def test_apply_invalid_file_sends_nothing_and_lists_every_problem(fake, layout_path, tmp_path,
                                                                   capsys):
    source = tmp_path / "bad.yaml"
    source.write_text("layers:\n  1:\n    key9: a\n    key1: cmd+nope\n")
    assert run(["apply", str(source), "--json"], fake, layout_path) == 1
    assert fake.device.written == []
    out = json.loads(capsys.readouterr().out)
    assert out["error"]["type"] == "invalid_layout"
    assert len(out["error"]["details"]) == 2


# --- led -------------------------------------------------------------------------------

def test_led_sets_mode_and_records_it(fake, layout_path):
    assert run(["led", "2"], fake, layout_path) == 0
    assert sent_payloads(fake)[1] == bytes([0xB0, 0x18, 0x02])
    assert saved(layout_path)["led"] == 2


# --- show / names / status / identify ----------------------------------------------------

def test_show_json_lists_every_slot_of_every_layer(fake, layout_path, capsys):
    run(["set", "key2", "cmd+v"], fake, layout_path)
    capsys.readouterr()
    assert run(["show", "--json"], fake, layout_path) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["layers"]["1"]["key2"] == "cmd+v"
    assert out["layers"]["1"]["key1"] is None
    assert set(out["layers"]) == {"1", "2", "3"}
    assert len(out["layers"]["3"]) == 9


def test_show_text_marks_empty_slots(fake, layout_path, capsys):
    run(["set", "knob-press", "mute"], fake, layout_path)
    capsys.readouterr()
    run(["show", "--layer", "1"], fake, layout_path)
    out = capsys.readouterr().out
    assert "knob-press" in out and "mute" in out
    assert "key1" in out


def test_names_json_is_a_complete_reference(fake, layout_path, capsys):
    assert run(["names", "--json"], fake, layout_path) == 0
    out = json.loads(capsys.readouterr().out)
    assert "knob-right" in out["slots"]
    assert out["max_sequence_steps"] == 5
    assert "pagedown" in out["keys"]
    assert "return" in out["keys"]["enter"]
    assert "cmd" in out["modifiers"]
    assert "volume-up" in out["media"]
    assert "scroll-up" in out["mouse"]


def test_status_reports_connected_interfaces(fake, layout_path, capsys):
    assert run(["status", "--json"], fake, layout_path) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["connected"] is True
    assert len(out["interfaces"]) == 4
    assert out["config_endpoint"] == {"interface_number": 1, "endpoint": "0x02"}
    assert fake.device.written == []


def test_status_when_disconnected_exits_2(layout_path, capsys):
    assert run(["status", "--json"], FakeUsb(None), layout_path) == 2
    assert json.loads(capsys.readouterr().out)["connected"] is False


def test_identify_maps_slots_to_digits_without_changing_layout(fake, layout_path):
    layout_path.write_text("layers:\n  1:\n    key1: cmd+c\n")
    assert run(["identify"], fake, layout_path) == 0
    payloads = sent_payloads(fake)
    assert bytes([0x01, 0x11, 0x01, 0x01, 0x00, 0x1E]) in payloads  # key1 types "1"
    assert bytes([0x06, 0x11, 0x01, 0x01, 0x00, 0x23]) in payloads  # key6 types "6"
    assert bytes([0x0F, 0x11, 0x01, 0x01, 0x00, 0x26]) in payloads  # knob-right types "9"
    assert saved(layout_path) == {"layers": {1: {"key1": "cmd+c"}}}


def test_apply_with_nothing_recorded_refuses_instead_of_wiping_the_device(fake, layout_path,
                                                                           capsys):
    assert run(["apply"], fake, layout_path) == 1
    assert fake.device.written == []
    assert "macropad set" in capsys.readouterr().err
