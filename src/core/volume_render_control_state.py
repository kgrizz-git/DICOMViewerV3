"""
Volume render control state model.

A lightweight, VTK-free dataclass that captures every user-visible control
setting in the 3D volume viewer.  The widget can be tested against this model
without instantiating a live renderer, and state can be compared, serialised,
and diffed as a plain Python object.

Inputs:
    - Control values from the widget UI (slider positions, combo indices,
      spinbox values).

Outputs:
    - A frozen snapshot of the viewer's logical state.
    - Helpers for default construction and comparison.

Requirements:
    - None (pure Python, no VTK / Qt dependency).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class VolumeRenderControlState:
    """
    Snapshot of every user-visible control in the 3D volume viewer.

    Field naming tracks the UI labels, not the VTK API names, so the model
    can be compared to the widget without translation.
    """

    # --- Preset ---
    preset_name: str = ""
    is_user_preset: bool = False
    base_preset_name: str = ""
    scalar_domain_label: str = ""

    # --- Visibility (opacity / contrast) ---
    opacity_percent: float = 100.0
    contrast_depth: int = 50  # 0..100 slider position (50 = neutral)

    # --- Window / Level ---
    window: float = 2000.0
    level: float = 0.0

    # --- Threshold ---
    threshold: int = 0

    # --- Appearance ---
    background_name: str = "Black"
    background_rgb: tuple[float, float, float] = (0.0, 0.0, 0.0)

    # --- Quality / render method (Phase 4) ---
    quality_mode: str = "Normal"
    render_method: str = "Auto"

    # --- Render status readout (Phase 2, T7) ---
    mapper_mode: str = ""
    volume_dimensions: tuple[int, int, int] | None = None

    # --- Interaction ---
    is_interacting: bool = False

    def to_preset_record(self) -> dict[str, Any]:
        """
        Return a dict suitable for ``snapshot_current_settings`` / user-preset
        persistence (only the subset of fields that user presets store).
        """
        return {
            "name": self.preset_name if self.is_user_preset else "",
            "base_preset": self.base_preset_name or self.preset_name,
            "opacity": self.opacity_percent,
            "window": self.window,
            "level": self.level,
            "threshold": self.threshold,
        }


def default_state() -> VolumeRenderControlState:
    """Return a state with the same defaults the widget uses at startup."""
    return VolumeRenderControlState()
