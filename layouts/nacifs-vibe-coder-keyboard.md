# Nacif's Vibe Coder Keyboard Keys

A layout for driving [Claude Code](https://claude.com/claude-code) in the terminal with
**dictation plus this pad**, no full keyboard needed. You speak the prompt, and the pad handles
everything else: picking the model and effort level, scrolling the transcript, confirming and
rejecting permission prompts.

```
┌───────────┬───────────┬───────────┐
│  key1     │  key2     │  key3     │      knob
│  esc      │  page up  │  ↑        │      turn left   opt+p, ←   (effort down)
├───────────┼───────────┼───────────┤      press       enter      (confirm)
│  key4     │  key5     │  key6     │      turn right  opt+p, →   (effort up)
│  space    │  page down│  ↓        │
└───────────┴───────────┴───────────┘
```

The layout file is [`nacifs-vibe-coder-keyboard.yaml`](nacifs-vibe-coder-keyboard.yaml), in this
folder.

## Apply it

```sh
macropad apply layouts/nacifs-vibe-coder-keyboard.yaml
```

That writes all nine slots and makes this file the recorded layout. Nothing else needs to run
afterwards: the mappings live in the pad.

## What each key does, and why

| Slot | Sends | In Claude Code |
|---|---|---|
| **knob turn right** | `opt+p, right` | Opens the model picker (`opt+p`) and moves the effort slider one step up. Turning further moves it further: once the picker is open the extra `opt+p` is ignored and only the arrow counts. |
| **knob turn left** | `opt+p, left` | Same, one step down. |
| **knob press** | `enter` | Confirms: closes the model picker with the chosen model and effort, approves a permission prompt, submits a dictated prompt. |
| **key3** | `up` | Moves up the model list while the picker is open. |
| **key6** | `down` | Moves down the model list. |
| **key1** | `esc` | Rejects a permission prompt, cancels a running turn, closes the picker without changing anything. |
| **key2** | `pageup` | Scrolls the transcript up. Hold it to keep scrolling. |
| **key5** | `pagedown` | Scrolls the transcript down. Hold it to keep scrolling. |
| **key4** | `space` | Push-to-talk for Claude Code's voice input. |

The typical flow: **turn the knob** to open the picker and set the effort, **key3/key6** to pick a
model, **press the knob** to confirm. **Key4** to dictate, **knob press** to send, **key1** to cancel.

## Decisions worth knowing

- **Why no second `opt+p` to close the picker.** `opt+p` only *opens* the picker from the chat
  box; inside the open picker it does nothing, so a closing `opt+p` is ignored. `enter` on the knob
  press closes it instead. The pad has no timers, so "close after N ms of inactivity" isn't possible
  on the device; it would need software running on the Mac.
- **Why Page Up/Down and not the scroll wheel.** The pad's firmware holds a keyboard key down for
  as long as you hold the physical key, so macOS auto-repeat makes `pageup`/`pagedown` keep
  scrolling while held. Mouse-wheel actions send exactly one notch per press and can't repeat.
  The wheel is also flipped by macOS natural scrolling. The trade-off: a page per step instead of a
  few lines.
- **Why key3/key6 are plain arrows.** They're only meant for the picker. In the chat box, `up` and
  `down` browse your prompt history instead, so open the picker with the knob first.
- **Terminal setting.** `opt+p` must reach Claude Code as a Meta keystroke. In Terminal.app, turn
  on *Use Option as Meta key* (Settings → Profiles → Keyboard). iTerm2 needs *Left Option key:
  Esc+*. Without it the knob types `π`.

## For agents

If a user asks for "the vibe coder layout", "Nacif's layout", or to "set up the pad for Claude
Code", apply the YAML above. Run `macropad show --json` first and tell the user that `apply`
replaces every slot, including ones they mapped themselves. To change only one key, use
`macropad set` instead; it leaves the rest alone.

If they use a different terminal or dictation tool, the two slots most likely to need adjusting
are **key4** (the push-to-talk key, which depends on their dictation setup) and the knob's `opt+p`
(if they rebound the model picker in `~/.claude/keybindings.json`).
