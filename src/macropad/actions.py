"""Parse and format the action strings bound to macropad slots.

Syntax:
  combo     cmd+shift+4          any modifiers + at most one regular key
  sequence  cmd+a, cmd+c         up to MAX_STEPS combos, comma separated
  media     volume-up            alone, no modifiers
  mouse     ctrl+scroll-up       modifiers allowed, not in a sequence
"""

import difflib
from dataclasses import dataclass

from macropad import keys

MAX_STEPS = 5


class ActionError(ValueError):
    def __init__(self, message: str, suggestions: list[str] | None = None):
        super().__init__(message)
        self.suggestions = suggestions or []


@dataclass(frozen=True)
class Keystroke:
    mods: int
    code: int


@dataclass(frozen=True)
class KeySequence:
    steps: tuple[Keystroke, ...]


@dataclass(frozen=True)
class Media:
    code: int


@dataclass(frozen=True)
class Mouse:
    buttons: int
    wheel: int
    mods: int


Action = KeySequence | Media | Mouse

_ALL_NAMES = [
    *keys.MODIFIERS, *keys.MODIFIER_ALIASES,
    *keys.KEYS, *keys.KEY_ALIASES,
    *keys.MEDIA, *keys.MEDIA_ALIASES,
    *keys.MOUSE, *keys.MOUSE_ALIASES,
]


def parse_action(text: str) -> Action:
    raw_steps = [step.strip() for step in text.split(",")]
    if not any(raw_steps):
        raise ActionError("action is empty")
    if not all(raw_steps):
        raise ActionError(f"empty step in sequence {text.strip()!r}")
    if len(raw_steps) > MAX_STEPS:
        raise ActionError(
            f"sequence has {len(raw_steps)} steps; the device plays at most {MAX_STEPS}"
        )

    parsed = [_parse_step(step) for step in raw_steps]
    if len(parsed) > 1:
        for step in parsed:
            if not isinstance(step, Keystroke):
                raise ActionError("media and mouse actions cannot be part of a sequence")
        return KeySequence(tuple(parsed))
    step = parsed[0]
    return KeySequence((step,)) if isinstance(step, Keystroke) else step


def _parse_step(step: str) -> Keystroke | Media | Mouse:
    tokens = [token.strip().lower() for token in step.split("+")]
    if not all(tokens):
        raise ActionError(f"empty key name in {step!r} ('+' is a separator, use shift+equal)")

    mods = 0
    others = []
    for token in tokens:
        name = keys.MODIFIER_ALIASES.get(token, token)
        if name in keys.MODIFIERS:
            mods |= keys.MODIFIERS[name]
        else:
            others.append(token)

    if len(others) > 1:
        raise ActionError(f"only one regular key per step, got {others} in {step!r}")
    if not others:
        return Keystroke(mods, 0)

    token = others[0]
    media = keys.MEDIA_ALIASES.get(token, token)
    if media in keys.MEDIA:
        if mods:
            raise ActionError(f"media key {media!r} cannot take modifiers")
        return Media(keys.MEDIA[media])

    mouse = keys.MOUSE_ALIASES.get(token, token)
    if mouse in keys.MOUSE:
        buttons, wheel = keys.MOUSE[mouse]
        return Mouse(buttons=buttons, wheel=wheel, mods=mods)

    if token in keys.AMBIGUOUS:
        options = keys.AMBIGUOUS[token]
        raise ActionError(f"{token!r} is ambiguous on macOS; use one of {options}", options)

    key = keys.KEY_ALIASES.get(token, token)
    if key not in keys.KEYS:
        suggestions = difflib.get_close_matches(token, _ALL_NAMES, n=3, cutoff=0.6)
        hint = f"; did you mean {' or '.join(suggestions)}?" if suggestions else ""
        raise ActionError(f"unknown key {token!r}{hint}", suggestions)
    return Keystroke(mods, keys.KEYS[key])


def format_action(action: Action) -> str:
    if isinstance(action, Media):
        return _name_for(keys.MEDIA, action.code)
    if isinstance(action, Mouse):
        mouse = next(n for n, v in keys.MOUSE.items() if v == (action.buttons, action.wheel))
        return "+".join([*_mod_names(action.mods), mouse])
    return ", ".join(_format_keystroke(step) for step in action.steps)


def _format_keystroke(stroke: Keystroke) -> str:
    parts = _mod_names(stroke.mods)
    if stroke.code:
        parts.append(_name_for(keys.KEYS, stroke.code))
    return "+".join(parts)


def _mod_names(mods: int) -> list[str]:
    return [name for name, bit in keys.MODIFIERS.items() if mods & bit]


def _name_for(table: dict[str, int], code: int) -> str:
    return next(name for name, value in table.items() if value == code)
