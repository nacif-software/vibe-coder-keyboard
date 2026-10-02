# AGENTS.md

`CLAUDE.md` is a symlink to this file. Two kinds of work happen in this repo:

## 1. Configuring the user's macropad

Follow [`skills/macropad/SKILL.md`](skills/macropad/SKILL.md). The short version:
- Start with `macropad show --json`.
- Validate with `--dry-run`, then write with `macropad set SLOT 'ACTION' --json`.
- Stop at the first exit code `2` (pad not connected).
- Never quietly substitute an action the device can't do. Offer the closest option and let the
  user choose.
- If the user asks for "the vibe coder layout" or to set the pad up for Claude Code, apply
  [`layouts/nacifs-vibe-coder-keyboard.yaml`](layouts/nacifs-vibe-coder-keyboard.yaml). The
  [guide](layouts/nacifs-vibe-coder-keyboard.md) explains every key and what may need adapting.

## 2. Working on the code

Python ≥ 3.11, managed with uv. `uv run pytest` runs everything with no hardware attached.

| Module | One job |
|---|---|
| `src/macropad/keys.py` | Name tables: HID key usages, modifier bits, consumer (media) codes, mouse |
| `src/macropad/actions.py` | Parse/format action strings (`cmd+shift+4`, `cmd+a, cmd+c`, `volume-up`) |
| `src/macropad/protocol.py` | Pure functions: action + slot + layer → 64-byte HID reports |
| `src/macropad/layout.py` | The layout YAML file, the only record of what the write-only device holds |
| `src/macropad/device.py` | libusb (pyusb) transport; writes to the pad's interrupt OUT endpoint |
| `src/macropad/cli.py` | argparse commands, `--json` output, exit codes |

Conventions:
- **Tests first.** Watch a new test fail before writing the code. Expected packet bytes are
  derived by hand from [`docs/protocol.md`](docs/protocol.md), never computed with the code under
  test.
- **Only the USB boundary is faked.** `tests/fakes.py` must mirror the real pyusb API:
  `get_active_configuration()` iterates interfaces, interfaces iterate endpoints
  (`bEndpointAddress`, `bmAttributes`), and `write(endpoint, data, timeout)` returns the byte
  count or raises `usb.core.USBError`. Its default interfaces are the real pad's (read from
  hardware). If the real API turns out to behave differently, fix the fake first.
- **Don't use HID APIs for the config channel.** It's a raw OUT endpoint that HID can't see
  (see `docs/protocol.md`).
- **The CLI contract is public API.** Every command supports `--json`. Errors go to stdout as
  `{"ok": false, "error": {...}}` when `--json` is set. Exit codes are 0/1/2/3. If you change the
  contract, update `--help`, `README.md` and `SKILL.md` together.
- **Protocol facts live in `docs/protocol.md`.** When something is confirmed (or disproved) on
  real hardware, update it and tick its checklist item.
- Tests never talk to a real device. Use `--dry-run` to inspect bytes.
- Never commit the vendor's `.exe` or any other third-party binary.
