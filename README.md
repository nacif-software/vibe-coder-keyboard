# vibe-coder-keyboard

A macOS command-line tool (`macropad`) for programming the cheap **6-key + 1-knob RGB USB
macropads** sold on AliExpress. It replaces the vendor's Windows-only app, and it's designed to be
driven by an AI agent: you say *"make the knob control volume and key 3 take a region
screenshot"*, and the agent runs the commands.

Mappings are written to the pad's flash memory. They keep working on any computer, and this tool
doesn't need to be running.

## Supported device

| | |
|---|---|
| Product | **6 Keys 1 Mini Knob RGB Keyboard for Photoshop USB Mechanical Keyboard Gamer Macro Custom Keyboard Gaming Custom Programming Knob** (listed under the brand "GGBEE") |
| Where | [AliExpress item 1005009818579677](https://www.aliexpress.com/item/1005009818579677.html) |
| Vendor software | "MINI KeyBoard" (Windows, .NET, v1 2022). You don't need it |
| USB ID | **`1189:8890`** (vendor `0x1189`, product `0x8890`) |
| Chipset | The "CH57x" macropad family, the name the community uses for these boards (after [ch57x-keyboard-tool](https://github.com/kriomant/ch57x-keyboard-tool), which is named for WCH's CH57x microcontrollers). The exact chip in this unit **hasn't been confirmed**. The tool depends on the USB ID and protocol, not on the chip. |

Other macropads that report `1189:8890` (3-key, 12-key/2-knob, …) speak the same protocol. This
tool only exposes the 6 keys and 1 knob of this model.

## What it can do

- **Key combos:** any modifiers plus one key, e.g. `cmd+shift+4`
- **Key sequences:** up to 5 combos played back-to-back, e.g. `cmd+a, cmd+c`
- **Media keys:** volume, mute, play/pause, next/previous, brightness
- **Mouse:** left/right/middle click, scroll up/down, modifier+scroll (e.g. `ctrl+scroll-up`)
- **The knob:** turn left, press and turn right are three separate slots
- **3 layers** and **3 LED modes** (off / last-pressed key lit / rainbow wave)

What the hardware can't do: sequences longer than 5 keystrokes, delays between steps, typing
long text, or launching apps directly. For those, bind an unused shortcut and hook it up in
macOS Shortcuts.

## Status

**Working on real hardware.** The USB protocol was decoded from the vendor app before the pad
arrived, then confirmed on the device: combos, 5-step sequences, mouse, media keys and the knob
all behave as documented. No macOS permissions are needed (the tool talks to the pad over raw USB
with libusb, not through the keyboard APIs that require Input Monitoring).
[docs/protocol.md](docs/protocol.md) lists what's verified and the few things still untested.

## Install

Requires macOS, Python ≥ 3.11 and [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/nacif-software/vibe-coder-keyboard
cd vibe-coder-keyboard
uv tool install --editable .      # puts `macropad` on your PATH
```

## First time with the device

```sh
macropad status          # is it connected? (exit 2 if not)
macropad identify        # each key types a digit: learn which physical key is key1…key6
macropad apply           # restore your layout afterwards (once you have one)
```

## Commands

| Command | What it does |
|---|---|
| `macropad set SLOT ACTION [--layer N]` | Bind an action, write it to the pad, record it in the layout file |
| `macropad clear SLOT [--layer N]` | Make a slot do nothing |
| `macropad apply [FILE]` | Write a whole layout; slots the file doesn't map are **cleared** |
| `macropad led 0\|1\|2` | Backlight: off / last-pressed key lit / rainbow wave |
| `macropad show [--layer N]` | Print the recorded mapping of every slot |
| `macropad names` | Every valid slot, modifier, key, media and mouse name |
| `macropad status` | Connection check, USB interfaces, and the config endpoint |
| `macropad identify` | Temporarily map key1–6 → `1`–`6`, knob left/press/right → `7`/`8`/`9` (layer 1) |

Every command accepts `--json` (output on stdout, errors included), and every write command
accepts `--dry-run`, which validates the input and prints the USB packets without sending
anything.

**Slots:** `key1` … `key6`, `knob-left`, `knob-press`, `knob-right`. **Layers:** `1` `2` `3`
(default `1`).

**Exit codes:** `0` ok · `1` invalid input · `2` pad not connected · `3` USB write failed.

## Action syntax

| Kind | Example | Rules |
|---|---|---|
| Combo | `cmd+shift+4` | Any modifiers + at most one regular key |
| Sequence | `cmd+a, cmd+c` | Up to **5** combos, comma separated, played back-to-back (no delays) |
| Media | `volume-up`, `mute`, `play`, `next`, `prev`, `brightness-up` | Alone: no modifiers, not in a sequence |
| Mouse | `click`, `right-click`, `middle-click`, `scroll-up`, `ctrl+scroll-down` | Modifiers allowed, not in a sequence |

- Modifiers are `ctrl`, `opt`, `shift` and `cmd`. The aliases `control`, `option`/`alt` and
  `command`/`win` also work. Add an `r` prefix for the right-hand key (`rcmd`, `ropt`, …).
- `delete` is rejected as ambiguous. Use `backspace` (⌫) or `forward-delete` (⌦).
- You can't use `+` or `,` as keys, because they're separators. Use `shift+equal` and `comma`.
- F13–F24, `kp-enter` and `kp-equal` are valid HID codes, but the vendor app never offers them,
  so the firmware might not send them.

## The layout file

The pad can't be read back, so `macropad` records everything it writes in
`~/.config/macropad/layout.yaml`. You can override that path with `--layout` or `$MACROPAD_LAYOUT`.
`set`, `clear` and `led` update the file only after the pad accepts the write, and `apply FILE` makes
FILE the recorded layout.

```yaml
led: 1
layers:
  1:
    key1: cmd+c
    key2: cmd+v
    key3: shift+cmd+4
    key4: cmd+a, cmd+c
    knob-left: volume-down
    knob-press: mute
    knob-right: volume-up
```

If you program the pad from the Windows app, this file goes stale. Run `macropad apply` to make the
pad match the file again.

## Ready-made layout: Nacif's Vibe Coder Keyboard Keys

[`layouts/nacifs-vibe-coder-keyboard.md`](layouts/nacifs-vibe-coder-keyboard.md) is the layout
this pad was built for: driving Claude Code with dictation and these nine controls. The knob
opens the model picker and sets the effort level, two keys pick the model, the knob press
confirms, and the others scroll, cancel and push-to-talk. The guide explains each choice and the
one terminal setting it needs.

```sh
macropad apply layouts/nacifs-vibe-coder-keyboard.yaml
```

## Using it from an agent

[`skills/macropad/SKILL.md`](skills/macropad/SKILL.md) teaches an agent the workflow: read the
current state, run a dry run, write, and handle the device's limits. For Claude Code, link it in
once from the clone:

```sh
ln -s "$PWD/skills/macropad" ~/.claude/skills/macropad
```

Other agents can be pointed at the same file. `macropad --help` and `macropad names --json` are
also written for agents to read.

## How it works

The vendor app is an unobfuscated .NET program. Its CIL bytecode keeps every method name, so the
USB protocol could be recovered by disassembling it (with `dnfile` + `dncil`) without running it
or sniffing USB. [docs/protocol.md](docs/protocol.md) describes every packet.

## Development

See [AGENTS.md](AGENTS.md) for conventions (it's also `CLAUDE.md`).

```sh
uv run pytest            # hardware-free: the USB boundary is faked in tests/fakes.py
```

## License

[MIT](LICENSE)
