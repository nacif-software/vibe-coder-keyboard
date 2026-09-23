# Macropad USB protocol

Decoded from the vendor tool `MINI KeyBoard.exe` (the .NET assembly `HIDTester`, built 2022-06-05).
The tool isn't obfuscated, so its CIL bytecode keeps every method, field and string name. The
methods that matter are `FormMain.Download_Click`, `Send_SwLayer`, `Send_WriteFlash_Cmd` and
`Send_WriteFlashLED_Cmd`. The findings match
[ch57x-keyboard-tool](https://github.com/kriomant/ch57x-keyboard-tool)'s `k8890` driver.

## Transport

- USB `VID 0x1189`, `PID 0x8890`, HID output reports.
- Report ID `0x03`. The vendor tool probes report IDs 3, 0 and 2, and uses the first one the
  device accepts. Report ID 0 is an older firmware that has no layers; `macropad` doesn't support
  it.
- Each report is the report ID followed by the payload, zero-padded to 64 bytes.

## Payloads

`L` is the layer (1–3), `S` is the slot ID.

| Purpose | Bytes |
|---|---|
| Select layer | `a1 L` |
| Key step | `S (L<<4 \| 1) count index mods code`. Index 0 carries the first step's mods with code 0; indexes 1…count are the keystrokes |
| Media key | `S (L<<4 \| 2) code_lo code_hi` (HID consumer usage) |
| Mouse | `S (L<<4 \| 3) buttons dx dy wheel mods`. buttons: 1 = left, 2 = right, 4 = middle; wheel: `01` up, `ff` down |
| Commit binding | `aa aa` |
| LED mode | `b0 (L<<4 \| 8) mode`, then `aa a1` |

Binding one slot sends *select layer*, then the binding packet(s), then *commit*.

**Slot IDs:** buttons 1–12 (`key1`–`key6` are 1–6), knob 1 = 13 (turn left), 14 (press), 15 (turn
right). Knob 2 (16–18) exists on bigger models.

**Modifier bits:** ctrl `01`, shift `02`, alt/opt `04`, win/cmd `08`; right-hand variants are `<< 4`.

**Sequence limit:** the vendor code fills steps 1–5 and no more. The ch57x driver enforces the
same limit.

## Not in the vendor tool

- **Clearing a slot.** The vendor tool's "clear" only resets its UI. `macropad` clears a slot by
  binding one empty keystroke (mods 0, code 0).
- **Reading the configuration back.** The device has no read command.

## To verify on real hardware

- [ ] Which HID interface accepts report 3 (see `macropad status`), and whether writes need a delay
      between packets.
- [ ] Physical position of key1–key6 (run `macropad identify`).
- [ ] That clearing with an empty keystroke really does nothing.
- [ ] Whether sequences longer than 5 steps work (the firmware might accept them even though the
      vendor tool stops at 5).
- [ ] F13–F24, `kp-enter`, `kp-equal`.
- [ ] Whether the LED mode is global or per layer (it's currently always sent with layer 1).
- [ ] How the pad switches between layers physically.
