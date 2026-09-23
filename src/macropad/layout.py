"""The layout file: the local source of truth for what the (write-only) device holds.

    led: 1                     # optional, 0-2
    layers:
      1:
        key1: cmd+c
        key4: cmd+a, cmd+c
        knob-right: volume-up
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from macropad.actions import Action, ActionError, format_action, parse_action
from macropad.protocol import LAYERS, LED_MODES, SLOT_IDS


class LayoutError(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


@dataclass
class Layout:
    led: int | None = None
    layers: dict[int, dict[str, str]] = field(default_factory=dict)

    def set_slot(self, layer: int, slot: str, action_text: str) -> None:
        """Store the canonical form of `action_text`; raises ActionError if it's invalid."""
        _check_slot(layer, slot)
        self.layers.setdefault(layer, {})[slot] = format_action(parse_action(action_text))

    def clear_slot(self, layer: int, slot: str) -> None:
        _check_slot(layer, slot)
        self.layers.get(layer, {}).pop(slot, None)
        if not self.layers.get(layer):
            self.layers.pop(layer, None)

    def bindings(self) -> dict[tuple[int, str], Action | None]:
        """Every (layer, slot) on the device; unmapped slots are None."""
        return {
            (layer, slot): _parse_or_none(self.layers.get(layer, {}).get(slot))
            for layer in LAYERS
            for slot in SLOT_IDS
        }


def load(path: Path) -> Layout:
    path = Path(path)
    if not path.exists():
        return Layout()
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise LayoutError([f"{path}: invalid YAML: {exc}"]) from exc
    if not isinstance(data, dict):
        raise LayoutError([f"{path}: expected a mapping with 'led' and 'layers'"])

    problems = [f"{key}: unknown top-level key" for key in data if key not in ("led", "layers")]

    led = data.get("led")
    if led is not None and led not in LED_MODES:
        problems.append(f"led: must be one of {list(LED_MODES)}, got {led!r}")

    layers: dict[int, dict[str, str]] = {}
    raw_layers = data.get("layers") or {}
    if not isinstance(raw_layers, dict):
        problems.append("layers: expected a mapping of layer number -> slots")
        raw_layers = {}
    for layer, slots in raw_layers.items():
        if layer not in LAYERS:
            problems.append(f"layers.{layer}: layer must be one of {list(LAYERS)}")
            continue
        if not isinstance(slots, dict):
            problems.append(f"layers.{layer}: expected a mapping of slot -> action")
            continue
        for slot, text in slots.items():
            where = f"layers.{layer}.{slot}"
            if slot not in SLOT_IDS:
                problems.append(f"{where}: unknown slot; expected one of {list(SLOT_IDS)}")
                continue
            if isinstance(text, bool) or not isinstance(text, (str, int)):
                problems.append(f"{where}: action must be a string, got {text!r}")
                continue
            text = str(text).strip()
            try:
                parse_action(text)
            except ActionError as exc:
                problems.append(f"{where}: {exc}")
                continue
            layers.setdefault(layer, {})[slot] = text

    if problems:
        raise LayoutError(problems)
    return Layout(led=led, layers=layers)


def save(layout: Layout, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict = {}
    if layout.led is not None:
        data["led"] = layout.led
    data["layers"] = {
        layer: {slot: layout.layers[layer][slot] for slot in SLOT_IDS if slot in layout.layers[layer]}
        for layer in sorted(layout.layers)
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def _check_slot(layer: int, slot: str) -> None:
    if layer not in LAYERS:
        raise ValueError(f"layer must be one of {list(LAYERS)}, got {layer}")
    if slot not in SLOT_IDS:
        raise ValueError(f"unknown slot {slot!r}; expected one of {list(SLOT_IDS)}")


def _parse_or_none(text: str | None) -> Action | None:
    return None if text is None else parse_action(text)
