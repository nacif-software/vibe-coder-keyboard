---
name: macropad
description: Use when the user wants to configure, remap, or inspect their 6-key + 1-knob USB macropad (keys, knob, layers, backlight) - e.g. "make the knob control volume", "put screenshot on key 3", "what does key 2 do".
---

# Configuring the macropad

The `macropad` CLI writes mappings to the pad's flash. The pad can't be read back, so the CLI's
layout file is the only record of what each key does.

## Workflow

1. **Read the current state first:** `macropad show --json`. Every slot on every layer is listed,
   and `null` means the slot is unmapped.
2. **Turn the request into actions.** Use macOS shortcuts (the user is on a Mac). If you're unsure
   of a name, run `macropad names --json`.
3. **Validate before writing:** `macropad set SLOT 'ACTION' --dry-run --json`.
4. **Write:** `macropad set SLOT 'ACTION' [--layer N] --json`. Always quote the action.
5. **Report back** what each slot now does, based on the command output.

## Slots and syntax

Slots: `key1`…`key6`, `knob-left`, `knob-press`, `knob-right`. Layers 1–3 (default 1).
If the user refers to keys by physical position and you don't know the mapping, ask them to
run `macropad identify` (the digit each key types is its slot number), then `macropad apply`
to restore their layout.

| Kind | Example | Rules |
|---|---|---|
| Combo | `cmd+shift+4` | Modifiers + **one** regular key |
| Sequence | `cmd+a, cmd+c` | **Max 5 steps**, comma separated, no delays |
| Media | `volume-up`, `volume-down`, `mute`, `play`, `next`, `prev`, `brightness-up` | Alone |
| Mouse | `click`, `right-click`, `scroll-up`, `ctrl+scroll-down` | Not in a sequence |

- Modifiers are `ctrl`, `opt`, `shift` and `cmd`, with `r` prefixes for the right-hand keys.
- Use `backspace` or `forward-delete`, never `delete`. Use `comma` and `shift+equal` rather than
  `,` and `+`.

## What the device can't do

Typing text longer than 5 keystrokes, delays, launching apps directly, running scripts, and
per-app behavior are all out of reach. If the user asks for one of these, say so. Don't write a
substitute on your own. Offer the closest option (e.g. `cmd+z` ×5 instead of ×6) and wait for the
user to choose. A workaround is to bind an unused shortcut (for example `ctrl+opt+cmd+1`) and have
them assign it in macOS Shortcuts or System Settings > Keyboard > Shortcuts.

## Exit codes

`0` ok · `1` invalid input: read `error.message` and `error.suggestions`, fix it, retry ·
`2` pad not connected: stop at the first one, don't attempt the remaining writes, and ask the user
to plug it in · `3` write failed: retry once, then report `error.details`.

`macropad apply FILE` replaces the whole layout and clears every slot the file doesn't map. Only
use it when the user wants a full layout change, and run `macropad show` first.

## Ready-made layout for Claude Code

The repo ships `layouts/nacifs-vibe-coder-keyboard.yaml`: knob = model picker + effort, knob
press = enter, key3/key6 = up/down, key1 = esc, key2/key5 = page up/down, key4 = space
(push-to-talk). When the user asks for "the vibe coder layout" or to "set the pad up for Claude
Code", apply it. Read `layouts/nacifs-vibe-coder-keyboard.md` first: it explains each key and
flags the two slots that may need adapting (key4 for their dictation tool, `opt+p` if they
rebound the model picker). It needs *Use Option as Meta key* on in Terminal.app.
