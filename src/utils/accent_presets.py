"""Accent color presets shared by config and GUI layers."""

from __future__ import annotations

from typing import NamedTuple


class AccentPreset(NamedTuple):
    label: str
    accent: str
    accent_light: str
    accent_dark: str
    accent_soft: str
    accent_muted: str


ACCENT_PRESETS: dict[str, AccentPreset] = {
    "steel-blue": AccentPreset(
        label="Steel Blue",
        accent="#4285da",
        accent_light="#5a9de5",
        accent_dark="#1a5da5",
        accent_soft="#e8f2fd",
        accent_muted="#16283a",
    ),
    "violet": AccentPreset(
        label="Violet",
        accent="#7c4dff",
        accent_light="#9e72ff",
        accent_dark="#5530cc",
        accent_soft="#f0e9ff",
        accent_muted="#251f3a",
    ),
    "navy": AccentPreset(
        label="Navy",
        accent="#1565c0",
        accent_light="#2979ff",
        accent_dark="#0d47a1",
        accent_soft="#e7f1fb",
        accent_muted="#142437",
    ),
    "garnet": AccentPreset(
        label="Garnet",
        accent="#a0303f",
        accent_light="#c94050",
        accent_dark="#6e1f2b",
        accent_soft="#f6e5e7",
        accent_muted="#32151a",
    ),
}

DEFAULT_ACCENT_ID = "steel-blue"


def get_preset(accent_id: str) -> AccentPreset:
    """Return the preset for *accent_id*, falling back to the default."""
    return ACCENT_PRESETS.get(accent_id, ACCENT_PRESETS[DEFAULT_ACCENT_ID])
