"""Select the 3D render surface implementation.

The offscreen :class:`~gui.volume.render_surface.VolumeRenderSurface` is the
default on every platform.  The legacy ``QVTKRenderWindowInteractor`` path is
available only as a field escape hatch via an environment variable; it
deadlocks the GUI thread on native macOS and is slated for removal.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from PySide6.QtWidgets import QWidget

_log = logging.getLogger(__name__)

LEGACY_ENV_VAR = "DICOMVIEWER_3D_LEGACY_INTERACTOR"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def legacy_interactor_requested(environ: dict[str, str] | None = None) -> bool:
    """Return ``True`` when the legacy interactor surface is explicitly enabled."""
    source = os.environ if environ is None else environ
    return source.get(LEGACY_ENV_VAR, "").strip().lower() in _TRUTHY


def create_render_surface(parent: QWidget | None = None) -> Any:
    """Return the render surface for the 3D viewer.

    Falls back to the offscreen surface if the legacy path is requested but
    cannot be constructed, so a stale environment variable can never leave the
    user without a 3D viewer.
    """
    if legacy_interactor_requested():
        try:
            from gui.volume.legacy_surface import LegacyInteractorSurface

            _log.warning(
                "%s is set: using the legacy VTK interactor surface, which "
                "hangs the UI on native macOS.",
                LEGACY_ENV_VAR,
            )
            return LegacyInteractorSurface(parent)
        except Exception:
            _log.error(
                "Legacy interactor surface unavailable; using the offscreen "
                "surface instead."
            )

    from gui.volume.render_surface import VolumeRenderSurface

    return VolumeRenderSurface(parent)
