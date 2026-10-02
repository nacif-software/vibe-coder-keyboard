"""Command-line interface. Every command takes --json for machine-readable output."""

import argparse
import json
import os
import sys
from pathlib import Path

from macropad import keys
from macropad.actions import MAX_STEPS, ActionError, format_action, parse_action
from macropad.device import PRODUCT_ID, VENDOR_ID, DeviceNotFound, LibUsb, WriteFailed
from macropad.device import interfaces as device_interfaces
from macropad.device import send
from macropad.layout import LayoutError, load, save
from macropad.protocol import LAYERS, LED_MODES, SLOT_IDS, bind_packets, led_packets

EXIT_OK, EXIT_INVALID, EXIT_NO_DEVICE, EXIT_WRITE_FAILED = 0, 1, 2, 3

LED_DESCRIPTIONS = {
    0: "off",
    1: "last pressed key stays lit, color changes on each press",
    2: "rainbow wave, left to right",
}

IDENTIFY_DIGITS = {
    **{f"key{n}": str(n) for n in range(1, 7)},
    "knob-left": "7",
    "knob-press": "8",
    "knob-right": "9",
}

ACTION_HELP = f"""\
action syntax:
  combo      cmd+shift+4          modifiers + at most one regular key
  sequence   cmd+a, cmd+c         up to {MAX_STEPS} combos, comma separated, played back-to-back
  media      volume-up            alone (no modifiers, not in a sequence)
  mouse      ctrl+scroll-up       modifiers allowed, not in a sequence
  modifiers  ctrl opt shift cmd (aliases: control, option/alt, command/win), r-prefixed for
             right-hand keys (rcmd, ropt, ...)
  run `macropad names` for every key, media and mouse name.

slots: {' '.join(SLOT_IDS)}
layers: {' '.join(map(str, LAYERS))} (default 1)

exit codes: 0 ok, 1 invalid input, 2 macropad not connected, 3 write failed
"""


def main(argv=None, usb=None) -> int:
    usb = usb or LibUsb()
    args = _build_parser().parse_args(argv)
    out = _Output(args.json)
    try:
        return args.handler(args, usb, out)
    except ActionError as exc:
        return out.error("invalid_action", str(exc), EXIT_INVALID, suggestions=exc.suggestions)
    except LayoutError as exc:
        return out.error("invalid_layout", "the layout file has problems", EXIT_INVALID,
                         details=exc.problems)
    except DeviceNotFound as exc:
        return out.error("device_not_found", str(exc), EXIT_NO_DEVICE)
    except WriteFailed as exc:
        return out.error("write_failed", str(exc), EXIT_WRITE_FAILED, details=exc.attempts)


# --- commands -------------------------------------------------------------------------------

def _cmd_set(args, usb, out):
    action = parse_action(args.action)
    layout = load(args.layout)
    packets = bind_packets(args.slot, args.layer, action)
    if args.dry_run:
        return out.packets(packets)
    info = send(packets, usb)
    layout.set_slot(args.layer, args.slot, args.action)
    save(layout, args.layout)
    canonical = format_action(action)
    return out.ok(
        {"layer": args.layer, "slot": args.slot, "action": canonical, "endpoint": f"0x{info['endpoint']:02x}"},
        f"layer {args.layer} {args.slot} = {canonical}",
    )


def _cmd_clear(args, usb, out):
    layout = load(args.layout)
    packets = bind_packets(args.slot, args.layer, None)
    if args.dry_run:
        return out.packets(packets)
    send(packets, usb)
    layout.clear_slot(args.layer, args.slot)
    save(layout, args.layout)
    return out.ok({"layer": args.layer, "slot": args.slot, "action": None},
                  f"layer {args.layer} {args.slot} cleared")


def _cmd_apply(args, usb, out):
    source = Path(args.file) if args.file else args.layout
    if not source.exists():
        hint = "" if args.file else "; record one with `macropad set` or pass a file"
        raise LayoutError([f"{source}: file not found{hint}"])
    layout = load(source)

    bindings = layout.bindings()
    packets = [p for (layer, slot), action in bindings.items()
               for p in bind_packets(slot, layer, action)]
    if layout.led is not None:
        packets += led_packets(layout.led)
    if args.dry_run:
        return out.packets(packets)

    send(packets, usb)
    if source.resolve() != args.layout.resolve():
        save(layout, args.layout)
    programmed = sum(action is not None for action in bindings.values())
    cleared = len(bindings) - programmed
    return out.ok(
        {"source": str(source), "programmed": programmed, "cleared": cleared, "led": layout.led},
        f"applied {source}: {programmed} slots programmed, {cleared} cleared"
        + (f", LED mode {layout.led}" if layout.led is not None else ""),
    )


def _cmd_led(args, usb, out):
    layout = load(args.layout)
    packets = led_packets(args.mode)
    if args.dry_run:
        return out.packets(packets)
    send(packets, usb)
    layout.led = args.mode
    save(layout, args.layout)
    return out.ok({"led": args.mode, "description": LED_DESCRIPTIONS[args.mode]},
                  f"LED mode {args.mode}: {LED_DESCRIPTIONS[args.mode]}")


def _cmd_show(args, usb, out):
    layout = load(args.layout)
    layers = [args.layer] if args.layer else list(LAYERS)
    table = {
        str(layer): {slot: layout.layers.get(layer, {}).get(slot) for slot in SLOT_IDS}
        for layer in layers
    }
    lines = [
        f"layout file: {args.layout}",
        "(the device can't be read back; this is what macropad last wrote to it)",
        f"led: {_led_text(layout.led)}",
    ]
    for layer, slots in table.items():
        lines.append(f"layer {layer}")
        lines += [f"  {slot:<11} {text or '-'}" for slot, text in slots.items()]
    return out.ok({"layout_file": str(args.layout), "led": layout.led, "layers": table},
                  "\n".join(lines))


def _cmd_names(args, usb, out):
    reference = {
        "slots": list(SLOT_IDS),
        "layers": list(LAYERS),
        "max_sequence_steps": MAX_STEPS,
        "led_modes": {str(mode): text for mode, text in LED_DESCRIPTIONS.items()},
        "modifiers": _with_aliases(keys.MODIFIERS, keys.MODIFIER_ALIASES),
        "keys": _with_aliases(keys.KEYS, keys.KEY_ALIASES),
        "media": _with_aliases(keys.MEDIA, keys.MEDIA_ALIASES),
        "mouse": _with_aliases(keys.MOUSE, keys.MOUSE_ALIASES),
        "unverified_keys": sorted(keys.UNVERIFIED_KEYS),
        "ambiguous": keys.AMBIGUOUS,
    }

    def section(title, table):
        entries = [name + (f" ({', '.join(aliases)})" if aliases else "")
                   for name, aliases in table.items()]
        return f"{title}:\n  " + "\n  ".join(_wrap(entries))

    text = "\n\n".join([
        section("modifiers", reference["modifiers"]),
        section("keys", reference["keys"]),
        section("media", reference["media"]),
        section("mouse", reference["mouse"]),
        "not offered by the vendor tool (may not work): " + " ".join(reference["unverified_keys"]),
        "ambiguous on macOS: delete/del -> use backspace (⌫) or forward-delete (⌦)",
        f"slots: {' '.join(SLOT_IDS)}   layers: 1 2 3   max sequence steps: {MAX_STEPS}",
    ])
    return out.ok(reference, text)


def _cmd_status(args, usb, out):
    found = device_interfaces(usb)
    usb_id = f"{VENDOR_ID:04x}:{PRODUCT_ID:04x}"
    if not found:
        return out.error("device_not_found", f"macropad {usb_id} not connected", EXIT_NO_DEVICE,
                         extra={"connected": False, "layout_file": str(args.layout)})
    config = next((i for i in found if i["config"]), None)
    config_endpoint = None
    if config:
        out_ep = next(e for e in config["endpoints"] if e["direction"] == "out")
        config_endpoint = {"interface_number": config["interface_number"],
                           "endpoint": out_ep["address"]}
    lines = [f"macropad {usb_id} connected, {len(found)} USB interface(s):"]
    for i in found:
        eps = ", ".join(f"{e['address']} {e['direction']} {e['type']}" for e in i["endpoints"])
        lines.append(f"  interface {i['interface_number']}: {eps}"
                     + ("   <- config channel" if i["config"] else ""))
    if config_endpoint is None:
        lines.append("warning: no interrupt OUT endpoint found; writes will fail")
    lines.append(f"layout file: {args.layout}")
    return out.ok({"connected": True, "usb_id": usb_id, "interfaces": found,
                   "config_endpoint": config_endpoint, "layout_file": str(args.layout)},
                  "\n".join(lines))


def _cmd_identify(args, usb, out):
    packets = [p for slot, digit in IDENTIFY_DIGITS.items()
               for p in bind_packets(slot, 1, parse_action(digit))]
    if args.dry_run:
        return out.packets(packets)
    send(packets, usb)
    text = (
        "layer 1 is now in identify mode: open a text field and press each key.\n"
        "the digit it types is its slot: 1-6 = key1-key6, knob turn left = 7, "
        "knob press = 8, knob turn right = 9.\n"
        "your layout file was not changed; run `macropad apply` to restore it."
    )
    return out.ok({"layer": 1, "mapping": IDENTIFY_DIGITS}, text)


# --- output ---------------------------------------------------------------------------------

class _Output:
    def __init__(self, as_json: bool):
        self.as_json = as_json

    def ok(self, data: dict, text: str) -> int:
        print(json.dumps({"ok": True, **data}) if self.as_json else text)
        return EXIT_OK

    def packets(self, packets: list[bytes]) -> int:
        trimmed = [bytes(p).rstrip(b"\x00") for p in packets]
        text = "\n".join(
            [f"dry run, nothing sent. {len(packets)} packets (each zero-padded to 64 bytes):"]
            + [f"  {p.hex(' ')}" for p in trimmed]
        )
        return self.ok({"dry_run": True, "packets": [p.hex() for p in trimmed]}, text)

    def error(self, type_, message, code, suggestions=None, details=None, extra=None) -> int:
        if self.as_json:
            error = {"type": type_, "message": message,
                     "suggestions": suggestions or [], "details": details or []}
            print(json.dumps({"ok": False, **(extra or {}), "error": error}))
        else:
            lines = [f"error: {message}"] + [f"  {d}" for d in details or []]
            print("\n".join(lines), file=sys.stderr)
        return code


def _with_aliases(table: dict, aliases: dict) -> dict[str, list[str]]:
    return {name: [a for a, target in aliases.items() if target == name] for name in table}


def _led_text(mode):
    return "not set by macropad" if mode is None else f"{mode} ({LED_DESCRIPTIONS[mode]})"


def _wrap(entries: list[str], width: int = 88) -> list[str]:
    lines, line = [], ""
    for entry in entries:
        if line and len(line) + len(entry) + 2 > width:
            lines.append(line)
            line = ""
        line = f"{line}, {entry}" if line else entry
    return [*lines, line] if line else lines


# --- argument parsing ------------------------------------------------------------------------

class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(EXIT_INVALID, f"{self.prog}: error: {message}\n")


def _default_layout() -> Path:
    env = os.environ.get("MACROPAD_LAYOUT")
    return Path(env) if env else Path.home() / ".config" / "macropad" / "layout.yaml"


def _build_parser() -> argparse.ArgumentParser:
    common = _Parser(add_help=False)
    common.add_argument("--json", action="store_true", help="machine-readable output on stdout")
    common.add_argument("--layout", type=Path, default=_default_layout(),
                        help="layout file (default: $MACROPAD_LAYOUT or "
                             "~/.config/macropad/layout.yaml)")
    writes = _Parser(add_help=False)
    writes.add_argument("--dry-run", action="store_true",
                        help="validate and print the USB packets; send and save nothing")
    layer = _Parser(add_help=False)
    layer.add_argument("--layer", type=int, choices=LAYERS, default=1)

    parser = _Parser(
        prog="macropad",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Program the 6-key + 1-knob CH57x USB macropad (USB 1189:8890) from macOS.\n"
            "Mappings are stored in the device's flash, so they work on any computer without\n"
            "this tool running. The device can't be read back, so macropad records what it\n"
            "wrote in a layout file; `macropad show` prints it."
        ),
        epilog=ACTION_HELP + (
            "\nexamples:\n"
            "  macropad set key1 cmd+c\n"
            "  macropad set key4 'cmd+a, cmd+c'\n"
            "  macropad set knob-right volume-up && macropad set knob-left volume-down\n"
            "  macropad set key2 ctrl+scroll-up --layer 2\n"
            "  macropad show --json\n"
        ),
    )
    commands = parser.add_subparsers(title="commands", metavar="COMMAND", required=True)

    def command(name, handler, help_, parents, epilog=""):
        sub = commands.add_parser(name, help=help_, description=help_, epilog=epilog,
                                  parents=parents,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
        sub.set_defaults(handler=handler)
        return sub

    sub = command("set", _cmd_set, "bind an action to a slot, write it to the device, record it",
                  [common, writes, layer],
                  ACTION_HELP + "\nexamples:\n  macropad set key3 cmd+shift+4\n"
                  "  macropad set key4 'cmd+a, cmd+c'\n  macropad set knob-press mute\n"
                  "  macropad set key6 right-click --layer 3\n")
    sub.add_argument("slot", choices=list(SLOT_IDS))
    sub.add_argument("action", help="e.g. cmd+shift+4, 'cmd+a, cmd+c', volume-up, click")

    sub = command("clear", _cmd_clear, "make a slot do nothing, on the device and in the layout",
                  [common, writes, layer], "example:\n  macropad clear key2 --layer 2\n")
    sub.add_argument("slot", choices=list(SLOT_IDS))

    sub = command("apply", _cmd_apply,
                  "write a whole layout file to the device; slots it doesn't map are cleared",
                  [common, writes],
                  "the applied file becomes the recorded layout.\n"
                  "without FILE, re-applies the recorded layout (e.g. after `identify`).\n\n"
                  "file format:\n  led: 1\n  layers:\n    1:\n      key1: cmd+c\n"
                  "      key4: cmd+a, cmd+c\n      knob-right: volume-up\n")
    sub.add_argument("file", nargs="?", help="layout YAML to apply (default: the recorded layout)")

    sub = command("led", _cmd_led, "set the backlight mode", [common, writes],
                  "\n".join(f"  {m}  {t}" for m, t in LED_DESCRIPTIONS.items()) + "\n")
    sub.add_argument("mode", type=int, choices=LED_MODES)

    sub = command("show", _cmd_show, "print the recorded mapping of every slot", [common])
    sub.add_argument("--layer", type=int, choices=LAYERS, help="only this layer (default: all)")

    command("names", _cmd_names, "list every valid slot, modifier, key, media and mouse name",
            [common])
    command("status", _cmd_status, "check whether the macropad is connected (exit 2 if not)",
            [common])
    command("identify", _cmd_identify,
            "temporarily make each slot on layer 1 type a digit, to learn the physical layout",
            [common, writes])
    return parser


if __name__ == "__main__":
    sys.exit(main())
