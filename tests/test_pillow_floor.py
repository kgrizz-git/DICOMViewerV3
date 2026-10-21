"""Guards the Pillow security floor in requirements.in and the lock."""

from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_MIN = (13, 0, 0)


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(p) for p in text.split("."))


def test_requirements_in_pillow_floor_is_at_least_13() -> None:
    lines = (_ROOT / "requirements.in").read_text(encoding="utf-8").splitlines()
    floors = [
        m.group(1)
        for line in lines
        if (m := re.match(r"^pillow\s*>=\s*([0-9][0-9.]*)", line, re.IGNORECASE))
    ]
    assert len(floors) == 1, "requirements.in must declare exactly one Pillow >= floor"
    assert _version(floors[0]) >= _MIN


def test_requirements_lock_pins_pillow_at_or_above_floor() -> None:
    text = (_ROOT / "requirements.txt").read_text(encoding="utf-8")
    match = re.search(r"^pillow==([0-9][0-9.]*)", text, re.IGNORECASE | re.MULTILINE)
    assert match, "requirements.txt must pin pillow"
    assert _version(match.group(1)) >= _MIN
