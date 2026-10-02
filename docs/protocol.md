# Macropad USB protocol

Decoded from the vendor tool `MINI KeyBoard.exe` (the .NET assembly `HIDTester`, built 2022-06-05).
The tool isn't obfuscated, so its CIL bytecode keeps every method, field and string name. The
methods that matter are `FormMain.Download_Click`, `Send_SwLayer`, `Send_WriteFlash_Cmd` and
`Send_WriteFlashLED_Cmd`. The findings match
[ch57x-keyboard-tool](https://github.com/kriomant/ch57x-keyboard-tool)'s `k8890` driver.

## Transport

- USB `VID 0x1189`, `PID 0x8890`. The pad has four USB interfaces (confirmed on hardware):

  | Interface | Endpoint | What it is |
  |---|---|---|
  | 0 | `0x81` IN | boot keyboard (report ID 1, key range `0x00`–`0x91`) |
  | **1** | **`0x02` OUT, interrupt, 64 bytes** | **config channel** |
  | 2 | `0x83` IN | keyboard (report ID 1) + consumer/media (report ID 2) |
  | 3 | `0x82` IN | 3-button mouse |

- The config channel is **not** a HID report. Interface 1 is HID class, but its only endpoint is
  OUT, so macOS binds no HID driver to it and HID APIs (hidapi, IOHIDManager) can't see it.
  `macropad` writes raw 64-byte packets to `0x02` with libusb, which needs no special permissions
  on macOS. No HID descriptor declares report ID 3; the firmware just reads the endpoint.
- Each packet starts with `0x03` (the vendor tool's "report ID", kept as the first byte), followed
  by the payload, zero-padded to 64 bytes. The vendor tool also probes IDs 0 and 2 for older
  firmware, which `macropad` doesn't support.

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

## Verified on real hardware (2026-10-02)

- [x] Transport: interface 1, endpoint `0x02`, no delay needed between packets (36 packets in a
      row for `identify` all landed).
- [x] Physical layout: `key1`–`key3` top row left to right, `key4`–`key6` bottom row; knob turn
      left = `knob-left`, press = `knob-press`, turn right = `knob-right`.
- [x] Combos (`shift+1`, `cmd+a`), sequences with per-step modifiers (`shift+h, i`), the 5-step
      maximum (`h, e, l, l, o`), mouse (`scroll-down`, `right-click`) and media keys
      (`volume-up`, `volume-down`, `mute`).

## Still to verify

- [ ] That clearing with an empty keystroke really does nothing.
- [ ] Whether sequences longer than 5 steps work (the firmware might accept them even though the
      vendor tool stops at 5).
- [ ] F13–F24, `kp-enter`, `kp-equal` (all within interface 0's declared key range `0x00`–`0x91`).
- [ ] Whether the LED mode is global or per layer (it's currently always sent with layer 1).
- [ ] How the pad switches between layers physically.
